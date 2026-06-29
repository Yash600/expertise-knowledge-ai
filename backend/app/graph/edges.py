"""
edges.py — Conditional routing logic for the LangGraph pipeline.
"""

from .state import RAGState


def route_to_generator(state: RAGState) -> str:
    """
    After route_reasoning node: decide which generation node to call.
    Returns the name of the next node.
    """
    if state.get("error"):
        return "generate"  # Fallback to direct generation on error

    mode = state.get("reasoning_mode", "single_doc")
    if mode == "multi_doc":
        return "map_reduce_generate"
    return "generate"
