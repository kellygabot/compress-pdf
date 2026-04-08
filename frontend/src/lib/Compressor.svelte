<script lang="ts">
  // ─── Types ────────────────────────────────────────────────────────────────
  interface CompressionResult {
    blob: Blob;
    originalSize: number;
    compressedSize: number;
    reduction: number;
    filename: string;
  }

  type Phase = "idle" | "dragging" | "compressing" | "done" | "error";

  // ─── State ────────────────────────────────────────────────────────────────
  let phase = $state<Phase>("idle");
  let file = $state<File | null>(null);
  let result = $state<CompressionResult | null>(null);
  let errorMsg = $state<string>("");

  // ─── Derived ──────────────────────────────────────────────────────────────
  const reductionLabel = $derived(
    result ? `${result.reduction.toFixed(1)}% smaller` : ""
  );

  const originalLabel = $derived(
    file ? formatBytes(file.size) : ""
  );

  const compressedLabel = $derived(
    result ? formatBytes(result.compressedSize) : ""
  );

  const dropZoneClass = $derived(
    [
      "drop-zone",
      phase === "dragging" ? "drop-zone--active" : "",
      phase === "done" ? "drop-zone--done" : "",
    ]
      .filter(Boolean)
      .join(" ")
  );

  // ─── Helpers ──────────────────────────────────────────────────────────────
  function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 ** 2).toFixed(2)} MB`;
  }

  function reset() {
    phase = "idle";
    file = null;
    result = null;
    errorMsg = "";
  }

  // ─── File handling ────────────────────────────────────────────────────────
  function pickFile(incoming: File | null | undefined) {
    if (!incoming) return;
    if (incoming.type !== "application/pdf") {
      errorMsg = "Please upload a valid PDF file.";
      phase = "error";
      return;
    }
    file = incoming;
    compress(incoming);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    phase = "idle";
    pickFile(e.dataTransfer?.files?.[0]);
  }

  function onInputChange(e: Event) {
    pickFile((e.target as HTMLInputElement).files?.[0]);
  }

  // ─── Compression ─────────────────────────────────────────────────────────
  async function compress(src: File) {
    phase = "compressing";

    const form = new FormData();
    form.append("file", src);

    try {
      const res = await fetch("http://localhost:8000/compress", {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail ?? `Server error ${res.status}`);
      }

      const blob = await res.blob();

      result = {
        blob,
        originalSize: Number(res.headers.get("X-Original-Size") ?? src.size),
        compressedSize: Number(res.headers.get("X-Compressed-Size") ?? blob.size),
        reduction: Number(res.headers.get("X-Reduction") ?? 0),
        filename: `compressed_${src.name}`,
      };

      phase = "done";
    } catch (err: unknown) {
      errorMsg = err instanceof Error ? err.message : "Compression failed.";
      phase = "error";
    }
  }

  // ─── Download ─────────────────────────────────────────────────────────────
  function downloadResult() {
    if (!result) return;
    const url = URL.createObjectURL(result.blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = result.filename;
    a.click();
    URL.revokeObjectURL(url);
  }
</script>

<!-- ─── Markup ──────────────────────────────────────────────────────────── -->
<div class="compressor">
  <!-- Header -->
  <header class="compressor__header">
    <span class="compressor__eyebrow">Lightweight</span>
    <h1 class="compressor__title">PDF Compressor</h1>
    <p class="compressor__subtitle">
      Drop your file below — we'll shrink it without sacrificing quality.
    </p>
  </header>

  <!-- Drop Zone -->
  <div
    class={dropZoneClass}
    ondragover={(e) => { e.preventDefault(); phase = "dragging"; }}
    ondragleave={() => { if (phase === "dragging") phase = "idle"; }}
    ondrop={onDrop}
    role="region"
    aria-label="PDF compression drop zone"
  >
    <input
      id="pdf-upload"
      type="file"
      accept=".pdf,application/pdf"
      class="drop-zone__input"
      onchange={onInputChange}
      disabled={phase === "compressing"}
    />

    <label for="pdf-upload" class="drop-zone__content">
      {#if phase === "idle" || phase === "dragging"}
        <div class="drop-zone__icon" aria-hidden="true">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <rect width="48" height="48" rx="14" fill="var(--primary-alpha)"/>
            <path d="M24 14v14M17 21l7-7 7 7" stroke="var(--primary)" stroke-width="2.2"
              stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M13 34h22" stroke="var(--primary)" stroke-width="2.2"
              stroke-linecap="round"/>
          </svg>
        </div>
        <p class="drop-zone__label">
          {phase === "dragging" ? "Release to upload" : "Drag & drop your PDF"}
        </p>
        <p class="drop-zone__hint">or click to browse files</p>

      {:else if phase === "compressing"}
        <div class="spinner" aria-label="Compressing…">
          <div class="spinner__ring"></div>
        </div>
        <p class="drop-zone__label">Compressing<span class="ellipsis"></span></p>
        <p class="drop-zone__hint">{file?.name}</p>

      {:else if phase === "done" && result}
        <div class="drop-zone__icon drop-zone__icon--success" aria-hidden="true">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <rect width="48" height="48" rx="14" fill="var(--success-alpha)"/>
            <path d="M15 24l7 7 11-12" stroke="var(--success)" stroke-width="2.4"
              stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <p class="drop-zone__label">Done!</p>
        <p class="drop-zone__hint">{file?.name}</p>

      {:else if phase === "error"}
        <div class="drop-zone__icon drop-zone__icon--error" aria-hidden="true">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <rect width="48" height="48" rx="14" fill="var(--error-alpha)"/>
            <path d="M17 17l14 14M31 17L17 31" stroke="var(--error)" stroke-width="2.2"
              stroke-linecap="round"/>
          </svg>
        </div>
        <p class="drop-zone__label">Upload failed</p>
        <p class="drop-zone__hint drop-zone__hint--error">{errorMsg}</p>
      {/if}
    </label>
  </div>

  <!-- Stats card — only visible after successful compression -->
  {#if phase === "done" && result}
    <div class="stats-card" role="region" aria-label="Compression results">
      <div class="stat">
        <span class="stat__label">Original</span>
        <span class="stat__value">{originalLabel}</span>
      </div>

      <div class="stat stat--accent">
        <span class="stat__label">Reduced by</span>
        <span class="stat__value stat__value--highlight">{reductionLabel}</span>
      </div>

      <div class="stat">
        <span class="stat__label">Compressed</span>
        <span class="stat__value">{compressedLabel}</span>
      </div>
    </div>

    <!-- Actions -->
    <div class="actions">
      <button class="btn btn--primary" onclick={downloadResult}>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M8 2v8M4 7l4 4 4-4" stroke="currentColor" stroke-width="1.6"
            stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M2 14h12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
        </svg>
        Download PDF
      </button>
      <button class="btn btn--ghost" onclick={reset}>
        Compress another
      </button>
    </div>
  {:else if phase === "error"}
    <div class="actions">
      <button class="btn btn--ghost" onclick={reset}>Try again</button>
    </div>
  {/if}
</div>

<!-- ─── Styles ─────────────────────────────────────────────────────────── -->
<style>
  /* ── CSS Variables ─────────────────────────────────────────────────────── */
  :global(:root) {
    --primary:        #3B82F6;
    --primary-dark:   #2563EB;
    --primary-alpha:  rgba(59, 130, 246, 0.10);
    --success:        #10B981;
    --success-alpha:  rgba(16, 185, 129, 0.10);
    --error:          #EF4444;
    --error-alpha:    rgba(239, 68, 68, 0.10);

    --bg:             #F9FAFB;
    --card-bg:        #FFFFFF;
    --ghost-bg:       #F1F5F9;
    --border:         rgba(0, 0, 0, 0.08);

    --text-primary:   #0F172A;
    --text-secondary: #64748B;
    --text-hint:      #94A3B8;

    --radius-sm:      8px;
    --radius-md:      16px;
    --radius-lg:      24px;

    --shadow-card:    0 1px 3px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.05);
    --shadow-btn:     0 1px 2px rgba(59,130,246,0.24), 0 4px 12px rgba(59,130,246,0.18);

    --transition:     all 0.2s ease-in-out;

    /* Typography tokens */
    --font-serif:     'Playfair Display', 'Georgia', serif;
    --font-sans:      'DM Sans', 'Helvetica Neue', sans-serif;
  }

  /* Google Fonts import */
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=DM+Sans:wght@400;500;600&display=swap');

  /* ── Layout ─────────────────────────────────────────────────────────────── */
  .compressor {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 24px;
    width: 100%;
    max-width: 520px;
    margin: 0 auto;
    padding: 40px 24px 48px;
    font-family: var(--font-sans);
    color: var(--text-primary);
  }

  /* ── Header ─────────────────────────────────────────────────────────────── */
  .compressor__header {
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }

  .compressor__eyebrow {
    font-family: var(--font-sans);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--primary);
    background: var(--primary-alpha);
    padding: 4px 12px;
    border-radius: 99px;
  }

  .compressor__title {
    font-family: var(--font-serif);
    font-size: clamp(28px, 6vw, 38px);
    font-weight: 700;
    line-height: 1.15;
    letter-spacing: -0.02em;
    color: var(--text-primary);
    margin: 0;
  }

  .compressor__subtitle {
    font-size: 14px;
    color: var(--text-secondary);
    margin: 0;
    max-width: 340px;
    line-height: 1.6;
  }

  /* ── Drop Zone ──────────────────────────────────────────────────────────── */
  .drop-zone {
    position: relative;
    width: 100%;
    min-height: 220px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 40px 24px;
    background: var(--card-bg);
    border: 2px dashed rgba(59, 130, 246, 0.35);
    border-radius: var(--radius-lg);
    cursor: pointer;
    transition: var(--transition);
    box-shadow: var(--shadow-card);
    box-sizing: border-box;
  }

  .drop-zone:hover,
  .drop-zone:focus-visible {
    border-color: var(--primary);
    background: var(--primary-alpha);
    outline: none;
  }

  .drop-zone--active {
    background: #F0F7FF;
    border-color: var(--primary);
    border-style: solid;
    transform: scale(1.01);
  }

  .drop-zone--done {
    border-style: solid;
    border-color: var(--success);
    background: var(--success-alpha);
  }

  .drop-zone__input {
    position: absolute;
    inset: 0;
    opacity: 0;
    width: 100%;
    height: 100%;
    cursor: pointer;
  }

  .drop-zone__icon {
    transition: var(--transition);
  }

  .drop-zone__label {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
    text-align: center;
  }

  .drop-zone__hint {
    font-size: 13px;
    color: var(--text-hint);
    margin: 0;
    text-align: center;
    max-width: 280px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .drop-zone__hint--error {
    color: var(--error);
  }

  /* ── Spinner ─────────────────────────────────────────────────────────────── */
  .spinner {
    position: relative;
    width: 48px;
    height: 48px;
  }

  .spinner__ring {
    width: 100%;
    height: 100%;
    border: 3px solid var(--primary-alpha);
    border-top-color: var(--primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* Animated ellipsis */
  .ellipsis::after {
    content: '';
    animation: dots 1.4s steps(4, end) infinite;
  }
  @keyframes dots {
    0%   { content: ''; }
    25%  { content: '.'; }
    50%  { content: '..'; }
    75%  { content: '...'; }
  }

  /* ── Stats Card ──────────────────────────────────────────────────────────── */
  .stats-card {
    width: 100%;
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    gap: 8px;
    padding: 20px 24px;
    background: var(--card-bg);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-card);
    animation: fadeUp 0.28s ease-out both;
  }

  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }

  .stat:first-child { align-items: flex-start; }
  .stat:last-child  { align-items: flex-end; }

  .stat__label {
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-hint);
  }

  .stat__value {
    font-size: 17px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .stat--accent {
    background: var(--primary-alpha);
    border-radius: var(--radius-sm);
    padding: 10px 16px;
  }

  .stat__value--highlight {
    color: var(--primary);
    font-size: 18px;
  }

  /* ── Actions ─────────────────────────────────────────────────────────────── */
  .actions {
    display: flex;
    gap: 12px;
    width: 100%;
    justify-content: center;
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 11px 22px;
    border-radius: var(--radius-sm);
    font-family: var(--font-sans);
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    border: none;
    transition: var(--transition);
  }

  .btn--primary {
    background: var(--primary);
    color: #fff;
    box-shadow: var(--shadow-btn);
  }

  .btn--primary:hover {
    background: var(--primary-dark);
    transform: translateY(-1px);
  }

  .btn--primary:active {
    transform: translateY(0);
  }

  .btn--ghost {
    background: var(--ghost-bg);
    color: var(--text-secondary);
  }

  .btn--ghost:hover {
    background: #E2E8F0;
    color: var(--text-primary);
  }

  .drop-zone {
    position: relative;
    /* ... your existing styles ... */
  }

  /* This makes the label fill the entire parent div */
  .drop-zone__content {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    cursor: pointer;
  }

  .drop-zone__input {
    position: absolute;
    inset: 0;
    opacity: 0;
    width: 100%;
    height: 100%;
    cursor: pointer;
    z-index: 10; /* Ensures the hidden input catches the drop event first */
  }

</style>