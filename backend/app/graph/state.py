"""
state.py — RAGState TypedDict shared across all LangGraph nodes.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, TypedDict


class Message(TypedDict):
    role: str       # "user" | "assistant"
    content: str


class RAGState(TypedDict):
    # ── Input ─────────────────────────────────────────────────────────────────
    query: str                          # Original user question
    session_id: str                     # Conversation session ID
    user_id: str                        # Clerk user ID

    # ── Query rewriting ───────────────────────────────────────────────────────
    rewritten_query: str                # Query after rewrite_query node

    # ── Query classification ──────────────────────────────────────────────────
    query_type: str                     # CONVERSATIONAL | OVERVIEW | FULL_SCAN | DOCUMENT_QUERY | AMBIGUOUS | OUT_OF_SCOPE

    # ── Chat history ──────────────────────────────────────────────────────────
    chat_history: List[Message]         # Last N messages (memory window)

    # ── Retrieval ─────────────────────────────────────────────────────────────
    retrieved_chunks: List[Dict[str, Any]]   # Chunks after retrieval

    # ── Routing ───────────────────────────────────────────────────────────────
    reasoning_mode: str                 # "direct" | "single_doc" | "multi_doc"

    # ── Generation ────────────────────────────────────────────────────────────
    answer: str                         # Final LLM-generated answer
    sources: List[Dict[str, Any]]       # Source citations for the answer
    confidence: float                   # Average confidence of top chunks

    # ── Error handling ────────────────────────────────────────────────────────
    error: Optional[str]                # Set if any node fails
