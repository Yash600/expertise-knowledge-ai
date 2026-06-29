"""
routers/ingest.py — POST /ingest  +  GET /ingest/status/{job_id}

Upload flow:
  1. POST /ingest  → validates file, saves to temp, starts background task, returns job_id immediately
  2. Background task runs load → chunk → embed → upsert (may take minutes for OCR)
  3. GET /ingest/status/{job_id} → returns { status, message, document?, error? }
"""

from __future__ import annotations

import os
import uuid
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse

from app.auth import get_current_user
from app.models import DocumentResponse
from app.ingestion.loader import load_document
from app.ingestion.chunker import chunk_documents
from app.ingestion.embedder import embed_and_upsert, embed_summary
from app.ingestion.summarizer import generate_document_summary
from app.retrieval.keyword import refresh_index
from app import jobs

router = APIRouter(prefix="/ingest", tags=["ingestion"])

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _run_ingestion(job_id: str, tmp_path: str, suffix: str,
                   original_name: str, file_size: int) -> None:
    """Background task: load → chunk → embed → upsert. Updates job store throughout."""
    try:
        jobs.update_job(job_id, status="processing", message="Extracting text...")

        def _progress(msg: str):
            jobs.update_job(job_id, status="processing", message=msg)

        pages = load_document(tmp_path, progress_cb=_progress)
        if not pages:
            jobs.update_job(job_id, status="error",
                            error="Could not extract text from the file. It may be empty or corrupted.")
            return

        # Override filename in metadata
        for page in pages:
            page["metadata"]["filename"] = original_name

        jobs.update_job(job_id, status="processing", message="Chunking document...")
        chunks = chunk_documents(pages)

        jobs.update_job(job_id, status="processing",
                        message=f"Embedding {len(chunks)} chunks...")
        chunk_count = embed_and_upsert(chunks)

        jobs.update_job(job_id, status="processing", message="Generating document summary...")
        doc_id_for_summary = pages[0]["metadata"]["doc_id"]
        summary_text = generate_document_summary(pages, original_name)
        if summary_text:
            embed_summary(doc_id_for_summary, original_name, summary_text)

        jobs.update_job(job_id, status="processing", message="Rebuilding search index...")
        refresh_index()

        doc_id = pages[0]["metadata"]["doc_id"]
        page_count = len(pages)

        doc = DocumentResponse(
            doc_id=doc_id,
            filename=original_name,
            file_type=suffix.lstrip("."),
            chunk_count=chunk_count,
            page_count=page_count,
            ingested_at=datetime.now(timezone.utc),
            size_bytes=file_size,
        )

        jobs.update_job(
            job_id,
            status="done",
            message=f"Indexed {chunk_count} chunks from {page_count} page(s)",
            document=doc.model_dump(mode="json"),
        )

    except Exception as e:
        jobs.update_job(job_id, status="error", error=str(e))

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@router.post("")
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """
    Upload a document. Returns a job_id immediately.
    Poll GET /ingest/status/{job_id} for progress.
    """
    # Validate file type
    content_type = file.content_type or ""
    suffix = ALLOWED_TYPES.get(content_type)
    if not suffix:
        name = file.filename or ""
        ext = Path(name).suffix.lower()
        if ext in (".pdf", ".docx", ".txt"):
            suffix = ext
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {content_type}. Supported: PDF, DOCX, TXT",
            )

    # Read & size-check
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large: {len(content)/1024/1024:.1f}MB. Max: 50MB",
        )

    # Save to a temp file that persists until the background task finishes
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(content)
    tmp.close()

    job_id = str(uuid.uuid4())
    jobs.create_job(job_id)

    background_tasks.add_task(
        _run_ingestion,
        job_id=job_id,
        tmp_path=tmp.name,
        suffix=suffix,
        original_name=file.filename or f"document{suffix}",
        file_size=len(content),
    )

    return JSONResponse({"job_id": job_id, "status": "pending",
                         "message": "Upload received. Processing in background."})


@router.get("/status/{job_id}")
async def ingest_status(job_id: str, user: dict = Depends(get_current_user)):
    """Poll ingestion job status."""
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
