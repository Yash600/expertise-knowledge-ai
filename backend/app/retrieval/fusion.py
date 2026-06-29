"""
fusion.py — Reciprocal Rank Fusion (RRF) to merge semantic + keyword results.

RRF formula: score(d) = sum(1 / (k + rank(d))) for each result list
where k=60 is the standard constant that dampens the effect of high ranks.

Deduplication is by chunk_id. The unified list is sorted by RRF score descending.
"""

from __future__ import annotations

from typing import List, Dict, Any

RRF_K = 60  # Standard RRF constant


def reciprocal_rank_fusion(
    *result_lists: List[Dict[str, Any]],
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """
    Merge multiple ranked result lists using Reciprocal Rank Fusion.

    Each result dict must have a "metadata" key containing "chunk_id".

    Args:
        *result_lists: Any number of ranked lists (semantic, keyword, etc.)
        top_k: Number of results to return after fusion.

    Returns:
        Unified list sorted by RRF score, with "rrf_score" added to each item.
    """
    # chunk_id -> cumulative RRF score
    rrf_scores: Dict[str, float] = {}
    # chunk_id -> best result dict (for payload reconstruction)
    best_result: Dict[str, Dict[str, Any]] = {}

    for result_list in result_lists:
        for rank, result in enumerate(result_list):
            chunk_id = result["metadata"].get("chunk_id", "")
            if not chunk_id:
                continue

            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)

            # Keep the result with the highest original score for payload
            if chunk_id not in best_result or result.get("score", 0) > best_result[chunk_id].get("score", 0):
                best_result[chunk_id] = result

    # Sort by RRF score descending and return top_k
    sorted_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)[:top_k]

    fused = []
    for cid in sorted_ids:
        item = {**best_result[cid], "rrf_score": rrf_scores[cid]}
        fused.append(item)

    return fused


def fuse_results(
    semantic_results: List[Dict[str, Any]],
    keyword_results: List[Dict[str, Any]],
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """Convenience wrapper: fuse semantic + keyword results."""
    return reciprocal_rank_fusion(semantic_results, keyword_results, top_k=top_k)
