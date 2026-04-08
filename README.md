# PDF Compressor

A local PDF compression app with a FastAPI backend and a Svelte 5 frontend.

The backend applies a two-stage compression pipeline:

1. PyMuPDF optimizes image-heavy PDFs by downsampling and re-encoding images when possible.
2. pikepdf performs structural cleanup and linearization.

The frontend provides a drag-and-drop upload flow and shows the original size, compressed size, and reduction percentage.

## Features

- Drag-and-drop PDF upload UI
- PDF compression through a FastAPI endpoint
- Downloadable compressed output
- Compression stats returned in response headers
- Local development workflow that runs backend and frontend together

## Project Structure

- `backend/main.py` - FastAPI app and compression logic
- `main.py` - Root import entrypoint for the backend app
- `start.py` - Launches backend and frontend together for local development
- `start-backend.cmd` - Windows helper to start the backend only
- `frontend/` - Svelte app and UI components
- `documents/v1_review.md` - Review notes and observations

## Requirements

- Python 3.11+ recommended
- Node.js 18+ recommended
- A Python virtual environment for backend dependencies

## Setup

### 1. Create and activate a Python virtual environment

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install backend dependencies

Install the packages used by the FastAPI backend:

```powershell
pip install fastapi uvicorn pymupdf pikepdf pillow python-multipart
```

### 3. Install frontend dependencies

```powershell
cd frontend
npm install
```

## Running the App

### Run backend and frontend together

From the repository root:

```powershell
python start.py
```

This starts:

- Backend: http://localhost:8000
- Frontend: http://localhost:5173

### Run backend only

```powershell
.\start-backend.cmd
```

### Run frontend only

```powershell
cd frontend
npm run dev
```

## API

### `GET /health`

Returns a simple health check response:

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

### `POST /compress`

Uploads a PDF and returns the compressed file as a streaming response.

Accepted content types:

- `application/pdf`
- `application/octet-stream` when the filename ends with `.pdf`

Response headers:

- `X-Original-Size`
- `X-Compressed-Size`
- `X-Reduction`

Example using `curl`:

```powershell
curl -F "file=@sample.pdf" http://localhost:8000/compress --output compressed.pdf
```

## Frontend Behavior

The Svelte UI uploads directly to `http://localhost:8000/compress`, then shows:

- original file size
- compressed file size
- reduction percentage
- a download button for the compressed PDF

## Notes

- The backend currently allows requests from `http://localhost:5173` only.
- The app is intended for local development unless you update the CORS and API configuration.
- Large PDFs can be CPU- and memory-intensive to process.

## Troubleshooting

- If the backend does not start, make sure the `.venv` virtual environment exists and contains the required packages.
- If the frontend does not start, make sure Node.js and `npm` are installed and available on your PATH.
- If you change backend or frontend ports, update the hardcoded URLs in the frontend and CORS settings in the backend.
