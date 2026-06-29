"""
keyword.py — Sparse BM25 retrieval over all indexed chunks.

The BM25 index is built at startup from all chunks fetched from Qdrant.
This avoids keeping a separate store — Qdrant is the single source of truth.

The index is rebuilt automatically if it is empty or explicitly refreshed.
"""

from __future__ import annotations

import os
from typing import List, Dict, Any

from dotenv import load_dotenv
from rank_bm25 import BM25Okapi
from qdrant_client import QdrantClient

load_dotenv()

COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "enterprise_docs")
TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "10"))

# In-memory index state
_bm25: BM25Okapi | None = None
_corpus: List[Dict[str, Any]] = []   # parallel list of chunk dicts


def _get_client() -> QdrantClient:
    return QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
    )


def _tokenize(text: str) -> List[str]:
    """Simple whitespace + lowercase tokenizer."""
    return text.lower().split()


def build_bm25_index() -> None:
    """
    Fetch all chunks from Qdrant and build the BM25 index.
    Call this once at app startup (or after ingestion).
    """
    global _bm25, _corpus

    client = _get_client()

    # Scroll through all points
    all_chunks: List[Dict[str, Any]] = []
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
            all_chunks.append({
                "text": r.payload.get("text", ""),
                "metadata": {k: v for k, v in r.payload.items() if k != "text"},
            })
        if offset is None:
            break

    if not all_chunks:
        print("  BM25: No chunks found in Qdrant. Index is empty.")
        _bm25 = None
        _corpus = []
        return

    _corpus = all_chunks
    tokenized = [_tokenize(c["text"]) for c in _corpus]
    _bm25 = BM25Okapi(tokenized)
    print(f"  BM25 index built: {len(_corpus)} chunks")


def keyword_search(query: str, top_k: int = TOP_K) -> List[Dict[str, Any]]:
    """
    BM25 search over the in-memory corpus.

    Returns:
        List of dicts with keys: text, score, metadata.
        Score is the raw BM25 score (higher = more relevant).
    """
    global _bm25, _corpus

    if _bm25 is None or not _corpus:
        build_bm25_index()

    if _bm25 is None:
        return []

    tokens = _tokenize(query)
    scores = _bm25.get_scores(tokens)

    # Get top-k indices sorted by score descending
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    return [
        {
            "text": _corpus[i]["text"],
            "score": float(scores[i]),
            "metadata": _corpus[i]["metadata"],
        }
        for i in top_indices
        if scores[i] > 0  # exclude zero-score results
    ]


def refresh_index() -> None:
    """Force rebuild of BM25 index (call after new documents are ingested)."""
    global _bm25, _corpus
    _bm25 = None
    _corpus = []
    build_bm25_index()
