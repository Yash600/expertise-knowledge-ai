"""
reranker.py — Cross-encoder reranker for final chunk selection.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2 (fast, ~22MB, runs locally).
Takes the fused top-10 candidates and scores each (query, chunk) pair.
Returns top-N chunks (default 3) sorted by reranker score.

This is the final gate before chunks are sent to the LLM.
"""

from __future__ import annotations

import os
from typing import List, Dict, Any

from dotenv import load_dotenv
from sentence_transformers import CrossEncoder

load_dotenv()

RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
TOP_N = int(os.getenv("RERANKER_TOP_N", "3"))

_reranker: CrossEncoder | None = None


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        print(f"  Loading reranker: {RERANKER_MODEL}")
        _reranker = CrossEncoder(RERANKER_MODEL, max_length=512)
    return _reranker


def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_n: int = TOP_N,
) -> List[Dict[str, Any]]:
    """
    Rerank candidate chunks using cross-encoder.

    Args:
        query: The user's (possibly rewritten) query.
        candidates: List of chunk dicts from RRF fusion.
        top_n: Number of top chunks to return.

    Returns:
        Top-N chunks sorted by reranker score descending,
        with "reranker_score" and "confidence" fields added.
    """
    if not candidates:
        return []

    reranker = _get_reranker()

    pairs = [(query, c["text"]) for c in candidates]
    scores = reranker.predict(pairs).tolist()

    # Attach reranker score to each candidate
    scored = [
        {**c, "reranker_score": float(s)}
        for c, s in zip(candidates, scores)
    ]

    # Sort by reranker score descending
    scored.sort(key=lambda x: x["reranker_score"], reverse=True)
    top = scored[:top_n]

    # Add normalized confidence (0-1) using sigmoid
    import math
    for item in top:
        item["confidence"] = round(1 / (1 + math.exp(-item["reranker_score"])), 4)

    return top


def full_retrieval_pipeline(
    query: str,
    top_n: int = TOP_N,
) -> List[Dict[str, Any]]:
    """
    Run the complete retrieval pipeline:
    semantic search + BM25 -> RRF fusion -> rerank -> top N chunks.

    This is a convenience function for testing and direct use.
    In production, the LangGraph pipeline calls each step individually.
    """
    from .semantic import semantic_search
    from .keyword import keyword_search
    from .fusion import fuse_results

    semantic = semantic_search(query)
    keyword = keyword_search(query)
    fused = fuse_results(semantic, keyword)
    return rerank(query, fused, top_n=top_n)
