import io
from typing import Dict

import fitz
import pikepdf
from PIL import Image, ImageChops, ImageOps
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

app = FastAPI(title="PDF Compressor API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Original-Size", "X-Compressed-Size", "X-Reduction"] # Add this line
)


def compress_pdf(data: bytes) -> bytes:
    """
    Compress a PDF using a two-stage approach:

    1. PyMuPDF stage for image-heavy optimisation:
       - Detect image usage DPI and downsample images above 150 DPI.
       - Re-encode using JPEG 2000 when available, otherwise high-effort JPEG.
       - Convert to grayscale / indexed palette where it provides savings.
       - Simulate JBIG2-style optimisation for bitonal scans via 1-bit encoding.
    2. pikepdf stage for structural optimisation:
       - Garbage collection, object streams, and linearisation.
    """
    def _pixmap_to_pil(pix: fitz.Pixmap) -> Image.Image:
        if pix.alpha:
            pix = fitz.Pixmap(pix, 0)

        if pix.n == 1:
            return Image.frombytes("L", (pix.width, pix.height), pix.samples)

        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    def _looks_near_grayscale(img: Image.Image) -> bool:
        rgb = img.convert("RGB")
        stat = ImageOps.autocontrast(rgb).resize((128, 128), Image.Resampling.BILINEAR)
        r, g, b = stat.split()
        diff_rg = ImageChops.difference(r, g).getbbox() is None
        diff_gb = ImageChops.difference(g, b).getbbox() is None
        if diff_rg and diff_gb:
            return True

        # Fallback tolerance check: average per-channel variance delta.
        px = list(stat.getdata())
        total = len(px)
        if total == 0:
            return False
        avg_delta = sum(abs(pr - pg) + abs(pg - pb) + abs(pr - pb) for pr, pg, pb in px) / (3 * total)
        return avg_delta < 8

    def _is_bitonal_scan(img: Image.Image) -> bool:
        gray = img.convert("L")
        tiny = gray.resize((max(32, gray.width // 6), max(32, gray.height // 6)), Image.Resampling.BILINEAR)
        hist = tiny.histogram()
        total = sum(hist) or 1
        extremes = hist[0] + hist[255]
        strong_bw = extremes / total > 0.55
        low_mid = sum(hist[40:215]) / total < 0.20
        return strong_bw and low_mid

    def _encode_raster(img: Image.Image, prefer_lossy: bool) -> bytes:
        buf = io.BytesIO()

        if img.mode == "1":
            # 1-bit image output is a practical stand-in for JBIG2-like gains.
            img.save(buf, format="PNG", optimize=True, compress_level=9)
            return buf.getvalue()

        if not prefer_lossy:
            img.save(buf, format="PNG", optimize=True, compress_level=9)
            return buf.getvalue()

        try:
            # Pillow uses OpenJPEG support if installed; falls back to JPEG when unavailable.
            img.save(
                buf,
                format="JPEG2000",
                quality_mode="rates",
                quality_layers=[14],
            )
            return buf.getvalue()
        except Exception:
            buf = io.BytesIO()
            img.convert("RGB").save(
                buf,
                format="JPEG",
                quality=58,
                optimize=True,
                progressive=True,
                subsampling=2,
            )
            return buf.getvalue()

    # Stage 1: image-aware optimisation with PyMuPDF.
    with fitz.open(stream=data, filetype="pdf") as doc:
        image_usage: Dict[int, Dict[str, int]] = {}

        for page_number in range(doc.page_count):
            page = doc.load_page(page_number)
            for entry in page.get_images(full=True):
                xref = entry[0]
                if xref not in image_usage:
                    image_usage[xref] = {
                        "page_number": page_number,
                        "max_target_w": 0,
                        "max_target_h": 0,
                    }

                rects = page.get_image_rects(xref)
                for rect in rects:
                    target_w = int(max(1, round((rect.width / 72.0) * 150)))
                    target_h = int(max(1, round((rect.height / 72.0) * 150)))
                    image_usage[xref]["max_target_w"] = max(image_usage[xref]["max_target_w"], target_w)
                    image_usage[xref]["max_target_h"] = max(image_usage[xref]["max_target_h"], target_h)

        for xref, usage in image_usage.items():
            try:
                pix = fitz.Pixmap(doc, xref)
            except Exception:
                continue

            img = _pixmap_to_pil(pix)
            orig_w, orig_h = img.size

            target_w = usage["max_target_w"] or orig_w
            target_h = usage["max_target_h"] or orig_h
            needs_downsample = orig_w > int(target_w * 1.1) or orig_h > int(target_h * 1.1)

            if needs_downsample:
                resize_w = min(orig_w, max(1, target_w))
                resize_h = min(orig_h, max(1, target_h))
                img = img.resize((resize_w, resize_h), Image.Resampling.LANCZOS)

            if _is_bitonal_scan(img):
                # Simulate JBIG2-like compression for scanned B/W content.
                img = img.convert("L").point(lambda p: 255 if p > 170 else 0, mode="1")
                encoded = _encode_raster(img, prefer_lossy=False)
            else:
                prefer_lossy = True

                if _looks_near_grayscale(img):
                    img = img.convert("L")
                    prefer_lossy = True
                else:
                    # Indexed palette conversion can reduce bpp for graphics-heavy pages.
                    try:
                        img = img.convert("P", palette=Image.ADAPTIVE, colors=128)
                        prefer_lossy = False
                    except Exception:
                        img = img.convert("RGB")
                        prefer_lossy = True

                encoded = _encode_raster(img, prefer_lossy=prefer_lossy)

            page = doc.load_page(usage["page_number"])
            try:
                page.replace_image(xref, stream=encoded)
            except Exception:
                # Some edge-case image objects cannot be replaced safely; skip those.
                continue

        stage1 = io.BytesIO()
        doc.save(stage1, garbage=4, deflate=True, clean=True)

    # Stage 2: structural cleanup with pikepdf.
    src = io.BytesIO(stage1.getvalue())
    dst = io.BytesIO()

    with pikepdf.open(src) as pdf:
        pdf.remove_unreferenced_resources()

        pdf.save(
            dst,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
            linearize=True,
            recompress_flate=True,
            compress_streams=True,
            stream_decode_level=pikepdf.StreamDecodeLevel.generalized,
        )

    return dst.getvalue()


@app.post("/compress")
async def compress_endpoint(file: UploadFile = File(...)):
    """
    Receive a PDF, compress it, and stream the result back.

    Returns:
        StreamingResponse  — compressed PDF binary
        X-Original-Size    — original file size in bytes (header)
        X-Compressed-Size  — compressed file size in bytes (header)
        X-Reduction        — percentage reduction rounded to 2 dp (header)
    """
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        # Accept octet-stream too — some browsers/OS send that for .pdf
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(
                status_code=415,
                detail="Only PDF files are accepted.",
            )

    raw: bytes = await file.read()

    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        compressed: bytes = compress_pdf(raw)
    except pikepdf.PdfError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not process PDF: {exc}",
        )

    original_size = len(raw)
    compressed_size = len(compressed)
    reduction = round((1 - compressed_size / original_size) * 100, 2) if original_size else 0

    safe_name = (file.filename or "compressed.pdf").replace(" ", "_")

    return StreamingResponse(
        io.BytesIO(compressed),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="compressed_{safe_name}"',
            "X-Original-Size": str(original_size),
            "X-Compressed-Size": str(compressed_size),
            "X-Reduction": str(reduction),
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok", "version": app.version}