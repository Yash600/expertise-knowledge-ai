"""
semantic.py — Dense retrieval via Qdrant cosine similarity.

Query is embedded with the same BGE model used at ingestion time,
using the retrieval prefix recommended by BGE authors.
Returns top-K scored results with full payload.
"""

from __future__ import annotations

import os
from typing import List, Dict, Any

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

load_dotenv()

COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "enterprise_docs")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "10"))

_model: SentenceTransformer | None = None
_client: QdrantClient | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
        )
    return _client


def get_summary_chunks() -> List[Dict[str, Any]]:
    """
    Retrieve only document-level summary chunks (chunk_type='summary').
    Used for aggregation queries — these contain pre-computed structural overviews.
    """
    client = _get_client()
    qdrant_filter = Filter(
        must=[FieldCondition(key="chunk_type", match=MatchValue(value="summary"))]
    )
    results, _ = client.scroll(
        collection_name=COLLECTION,
        scroll_filter=qdrant_filter,
        limit=100,  # shouldn't have more than 100 indexed docs at once
        with_payload=True,
    )
    return [
        {
            "text": r.payload.get("text", ""),
            "score": 1.0,
            "confidence": 0.95,
            "metadata": {k: v for k, v in r.payload.items() if k != "text"},
        }
        for r in results
    ]


def scroll_all_chunks(
    filter_doc_id: str | None = None,
    batch_size: int = 100,
) -> List[Dict[str, Any]]:
    """
    Scroll through ALL chunks in the collection (no similarity limit).
    Used for aggregation queries (count, list-all, total, etc.).
    Optionally filtered to a single document.
    """
    client = _get_client()
    qdrant_filter = None
    if filter_doc_id:
        qdrant_filter = Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=filter_doc_id))]
        )

    all_chunks = []
    offset = None
    while True:
        results, next_offset = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=qdrant_filter,
            limit=batch_size,
            offset=offset,
            with_payload=True,
        )
        for r in results:
            all_chunks.append({
                "text": r.payload.get("text", ""),
                "score": 1.0,
                "confidence": 0.9,
                "metadata": {k: v for k, v in r.payload.items() if k != "text"},
            })
        if next_offset is None:
            break
        offset = next_offset

    # Sort by page number for logical reading order
    all_chunks.sort(key=lambda c: c["metadata"].get("page", 0))
    return all_chunks


def semantic_search(
    query: str,
    top_k: int = TOP_K,
    filter_doc_id: str | None = None,
) -> List[Dict[str, Any]]:
    """
    Search Qdrant by cosine similarity.

    Args:
        query: Natural language query string.
        top_k: Number of results to return.
        filter_doc_id: If set, restrict search to a single document.

    Returns:
        List of dicts with keys: text, score, metadata.
    """
    model = _get_model()
    client = _get_client()

    # BGE retrieval prefix
    query_vector = model.encode(
        f"Represent this sentence for searching relevant passages: {query}",
        normalize_embeddings=True,
    ).tolist()

    qdrant_filter = None
    if filter_doc_id:
        qdrant_filter = Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=filter_doc_id))]
        )

    results = client.search(
        collection_name=COLLECTION,
        query_vector=query_vector,
        limit=top_k,
        query_filter=qdrant_filter,
        with_payload=True,
    )

    return [
        {
            "text": r.payload.get("text", ""),
            "score": r.score,
            "metadata": {k: v for k, v in r.payload.items() if k != "text"},
        }
        for r in results
    ]
