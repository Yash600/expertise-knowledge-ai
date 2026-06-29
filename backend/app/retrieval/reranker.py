"""
reranker.py — Lightweight score-based reranker (no cross-encoder).

Cross-encoder (sentence-transformers) was removed to stay within Render's
512 MB free-tier RAM limit. Reranking is now done by sorting on the existing
semantic similarity score from Qdrant, which is already high-quality with BGE.
"""

from __future__ import annotations

from typing import List, Dict, Any
import math
import os

TOP_N = int(os.getenv("RERANKER_TOP_N", "3"))


def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_n: int = TOP_N,
) -> List[Dict[str, Any]]:
    """
    Rerank candidates by their Qdrant cosine similarity score.
    Returns top_n results with a normalized confidence field.
    """
    if not candidates:
        return []

    # Sort by existing semantic score (already cosine similarity from Qdrant)
    sorted_candidates = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)
    top = sorted_candidates[:top_n]

    # Normalize score to 0-1 confidence via sigmoid
    for item in top:
        score = item.get("score", 0.5)
        item["reranker_score"] = score
        item["confidence"] = round(1 / (1 + math.exp(-score * 5)), 4)

    return top


def full_retrieval_pipeline(
    query: str,
    top_n: int = TOP_N,
) -> List[Dict[str, Any]]:
    """Run the complete retrieval pipeline: semantic + BM25 -> RRF fusion -> rerank."""
    from .semantic import semantic_search
    from .keyword import keyword_search
    from .fusion import fuse_results

    semantic = semantic_search(query)
    keyword = keyword_search(query)
    fused = fuse_results(semantic, keyword)
    return rerank(query, fused, top_n=top_n)
