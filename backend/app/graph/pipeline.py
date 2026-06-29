"""
pipeline.py — Compile the LangGraph RAG pipeline.

Graph flow:
  rewrite_query → classify_query → retrieve → route_reasoning
      → [direct]      direct_respond      → update_memory
      → [single_doc]  generate            → update_memory
      → [multi_doc]   map_reduce_generate → update_memory
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import RAGState
from .nodes import (
    rewrite_query,
    classify_query,
    retrieve,
    route_reasoning,
    direct_respond,
    generate,
    map_reduce_generate,
    update_memory,
)

load_dotenv()

_compiled_graph = None


def _route_to_generator(state: RAGState) -> str:
    """Conditional edge: pick generate node based on reasoning_mode."""
    mode = state.get("reasoning_mode", "single_doc")
    if mode == "direct":
        return "direct_respond"
    elif mode == "multi_doc":
        return "map_reduce_generate"
    return "generate"


def build_graph(checkpointer=None):
    builder = StateGraph(RAGState)

    builder.add_node("rewrite_query", rewrite_query)
    builder.add_node("classify_query", classify_query)
    builder.add_node("retrieve", retrieve)
    builder.add_node("route_reasoning", route_reasoning)
    builder.add_node("direct_respond", direct_respond)
    builder.add_node("generate", generate)
    builder.add_node("map_reduce_generate", map_reduce_generate)
    builder.add_node("update_memory", update_memory)

    builder.set_entry_point("rewrite_query")
    builder.add_edge("rewrite_query", "classify_query")
    builder.add_edge("classify_query", "retrieve")
    builder.add_edge("retrieve", "route_reasoning")

    builder.add_conditional_edges(
        "route_reasoning",
        _route_to_generator,
        {
            "direct_respond": "direct_respond",
            "generate": "generate",
            "map_reduce_generate": "map_reduce_generate",
        },
    )

    builder.add_edge("direct_respond", "update_memory")
    builder.add_edge("generate", "update_memory")
    builder.add_edge("map_reduce_generate", "update_memory")
    builder.add_edge("update_memory", END)

    return builder.compile(checkpointer=checkpointer)


def get_graph():
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    print("  LangGraph: using in-memory checkpointer")
    _compiled_graph = build_graph(checkpointer=MemorySaver())
    return _compiled_graph


async def run_pipeline(
    query: str,
    session_id: str,
    user_id: str,
    chat_history: list | None = None,
) -> dict[str, Any]:
    graph = get_graph()

    initial_state: RAGState = {
        "query": query,
        "session_id": session_id,
        "user_id": user_id,
        "rewritten_query": "",
        "query_type": "DOCUMENT_QUERY",
        "chat_history": chat_history or [],
        "retrieved_chunks": [],
        "reasoning_mode": "single_doc",
        "answer": "",
        "sources": [],
        "confidence": 0.0,
        "error": None,
    }

    config = {"configurable": {"thread_id": session_id}}
    result = await graph.ainvoke(initial_state, config=config)
    return result
