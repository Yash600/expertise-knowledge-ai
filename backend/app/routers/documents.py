"""
routers/documents.py — GET /documents, DELETE /documents/{doc_id}

Lists all indexed documents and allows deletion (removes from Qdrant).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from dotenv import load_dotenv

from app.auth import get_current_user
from app.models import DocumentListResponse, DocumentResponse, DeleteDocumentResponse
from app.ingestion.embedder import delete_document
from app.retrieval.keyword import refresh_index

load_dotenv()

router = APIRouter(prefix="/documents", tags=["documents"])

COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "enterprise_docs")

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
        )
    return _client


@router.get("", response_model=DocumentListResponse)
async def list_documents(user: dict = Depends(get_current_user)):
    """
    List all indexed documents with metadata (filename, chunk count, page count).
    Aggregated from Qdrant payloads — no separate DB needed.
    """
    client = _get_client()

    # Scroll all points and aggregate by doc_id
    doc_map: dict[str, dict] = {}
    offset = None

    while True:
        results, offset = client.scroll(
            collection_name=COLLECTION,
            limit=500,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for r in results:
            p = r.payload
            doc_id = p.get("doc_id", "")
            if not doc_id:
                continue

            if doc_id not in doc_map:
                doc_map[doc_id] = {
                    "doc_id": doc_id,
                    "filename": p.get("filename", "unknown"),
                    "file_type": p.get("file_type", "unknown"),
                    "chunk_count": 0,
                    "pages": set(),
                    "ingested_at": datetime.now(timezone.utc),
                    "size_bytes": 0,
                }
            doc_map[doc_id]["chunk_count"] += 1
            page = p.get("page")
            if page:
                doc_map[doc_id]["pages"].add(page)

        if offset is None:
            break

    documents = [
        DocumentResponse(
            doc_id=d["doc_id"],
            filename=d["filename"],
            file_type=d["file_type"],
            chunk_count=d["chunk_count"],
            page_count=len(d["pages"]) or 1,
            ingested_at=d["ingested_at"],
            size_bytes=d["size_bytes"],
        )
        for d in doc_map.values()
    ]

    return DocumentListResponse(documents=documents, total=len(documents))


@router.delete("/{doc_id}", response_model=DeleteDocumentResponse)
async def delete_doc(
    doc_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Remove a document and all its chunks from Qdrant.
    Also rebuilds the BM25 index.
    """
    # Verify document exists
    client = _get_client()
    results, _ = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        ),
        limit=1,
        with_payload=False,
        with_vectors=False,
    )
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found",
        )

    delete_document(doc_id)
    refresh_index()

    return DeleteDocumentResponse(
        success=True,
        doc_id=doc_id,
        message=f"Document {doc_id} and all its chunks have been removed",
    )
