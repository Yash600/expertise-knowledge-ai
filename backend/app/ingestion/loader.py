"""
loader.py — Load PDF, TXT, DOCX files and return structured document chunks.

Each chunk is a dict:
{
    "text": str,
    "metadata": {
        "filename": str,
        "file_type": str,
        "page": int,        # 1-indexed; 0 for non-paged formats
        "source": str,      # absolute file path
        "doc_id": str,      # uuid5(filename)
    }
}

Scanned PDFs (image-based, no text layer) are handled via EasyOCR fallback.
EasyOCR downloads its English model (~100MB) on first use.
"""

import uuid
from pathlib import Path
from typing import List, Dict, Any

import fitz   # PyMuPDF
import docx   # python-docx


def _doc_id(filename: str) -> str:
    """Deterministic UUID from filename so re-ingestion is idempotent."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, filename))


# ── OCR via pytesseract (fast) with EasyOCR fallback ─────────────────────────

import shutil

_TESSERACT_CMD = None  # resolved once on first OCR call

def _find_tesseract() -> str | None:
    """Locate Tesseract binary on common Windows/Linux paths."""
    # Check PATH first
    found = shutil.which("tesseract")
    if found:
        return found
    # Common Windows install locations
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
    ]
    import os
    for c in candidates:
        c = c.format(os.environ.get("USERNAME", ""))
        if os.path.isfile(c):
            return c
    return None


def _ocr_page(page: fitz.Page) -> str:
    """
    Render a PDF page and run OCR.
    Uses pytesseract if Tesseract is installed (fast), otherwise falls back to EasyOCR.
    """
    import io
    from PIL import Image

    # Render at 200 DPI
    pix = page.get_pixmap(dpi=200)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

    # ── Try pytesseract first (fast) ──────────────────────────────────────────
    global _TESSERACT_CMD
    if _TESSERACT_CMD is None:
        _TESSERACT_CMD = _find_tesseract() or ""

    if _TESSERACT_CMD:
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD
            text = pytesseract.image_to_string(img, lang="eng", config="--psm 3")
            return text.strip()
        except Exception as e:
            print(f"  pytesseract failed ({e}), falling back to EasyOCR...")

    # ── Fallback: EasyOCR ─────────────────────────────────────────────────────
    import numpy as np
    try:
        import easyocr
    except ImportError:
        raise RuntimeError(
            "No OCR engine available. Install Tesseract (https://github.com/UB-Mannheim/tesseract/wiki) "
            "OR run: pip install easyocr"
        )

    print("  Loading EasyOCR model (first run downloads ~100MB)...")
    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    results = reader.readtext(np.array(img), detail=0, paragraph=True)
    return "\n".join(results).strip()


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_pdf(path: Path, progress_cb=None) -> List[Dict[str, Any]]:
    """
    Load a PDF file.
    progress_cb: optional callable(message: str) for reporting OCR progress.
    """
    doc = fitz.open(str(path))
    pages = []
    scanned_pages = 0
    total_pages = len(doc)

    for i, page in enumerate(doc):
        text = page.get_text("text").strip()

        if not text:
            # No text layer — try OCR
            scanned_pages += 1
            if progress_cb:
                progress_cb(f"OCR page {i+1}/{total_pages} (scanned document)...")
            try:
                text = _ocr_page(page)
            except Exception as e:
                print(f"  OCR failed on page {i+1}: {e}")
                text = ""

        if not text:
            continue

        pages.append({
            "text": text,
            "metadata": {
                "filename": path.name,
                "file_type": "pdf",
                "page": i + 1,
                "source": str(path),
                "doc_id": _doc_id(path.name),
                "ocr": scanned_pages > 0,
            }
        })

    doc.close()

    if scanned_pages:
        print(f"  OCR applied to {scanned_pages} scanned page(s) in {path.name}")

    return pages


def load_txt(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return []
    return [{
        "text": text,
        "metadata": {
            "filename": path.name,
            "file_type": "txt",
            "page": 0,
            "source": str(path),
            "doc_id": _doc_id(path.name),
        }
    }]


def load_docx(path: Path) -> List[Dict[str, Any]]:
    doc = docx.Document(str(path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs)
    if not text:
        return []
    return [{
        "text": text,
        "metadata": {
            "filename": path.name,
            "file_type": "docx",
            "page": 0,
            "source": str(path),
            "doc_id": _doc_id(path.name),
        }
    }]


LOADERS = {
    ".pdf": load_pdf,
    ".txt": load_txt,
    ".docx": load_docx,
}


def load_document(path: str | Path, progress_cb=None) -> List[Dict[str, Any]]:
    """Load a single file. Returns list of page-level dicts.
    progress_cb: optional callable(message: str) forwarded to PDF loader for OCR progress.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    loader = LOADERS.get(suffix)
    if loader is None:
        raise ValueError(f"Unsupported file type: {suffix}. Supported: {list(LOADERS)}")
    if suffix == ".pdf" and progress_cb is not None:
        return loader(path, progress_cb=progress_cb)
    return loader(path)


def load_directory(directory: str | Path) -> List[Dict[str, Any]]:
    """Load all supported files from a directory (non-recursive)."""
    directory = Path(directory)
    all_pages = []
    for ext in LOADERS:
        for file in sorted(directory.glob(f"*{ext}")):
            print(f"  Loading: {file.name}")
            pages = load_document(file)
            print(f"    -> {len(pages)} page(s) extracted")
            all_pages.extend(pages)
    return all_pages
