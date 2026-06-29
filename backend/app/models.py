"""
models.py — All Pydantic request/response schemas for the FastAPI app.
"""

from __future__ import annotations

from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ── Ask / Chat ────────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="User's question")
    session_id: str = Field(..., description="Conversation session ID for memory")


class SourceCitation(BaseModel):
    filename: str
    page: Optional[int] = None
    chunk_id: str
    confidence: float


class AskResponse(BaseModel):
    answer: str
    sources: List[SourceCitation]
    confidence: float
    session_id: str
    reasoning_mode: str  # "single_doc" | "multi_doc"
    rewritten_query: str


# ── Document Ingestion ────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    doc_id: str
    filename: str
    file_type: str
    chunk_count: int
    page_count: int
    ingested_at: datetime
    size_bytes: int


class IngestResponse(BaseModel):
    success: bool
    document: DocumentResponse
    message: str


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int


class DeleteDocumentResponse(BaseModel):
    success: bool
    doc_id: str
    message: str


# ── Feedback ──────────────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    session_id: str
    question: str
    answer: str
    rating: int = Field(..., ge=1, le=2, description="1 = thumbs down, 2 = thumbs up")
    comment: Optional[str] = Field(None, max_length=1000)


class FeedbackResponse(BaseModel):
    success: bool
    feedback_id: str
    message: str


class FeedbackItem(BaseModel):
    id: str
    user_id: str
    session_id: str
    question: str
    answer: str
    rating: int
    comment: Optional[str]
    created_at: datetime


class FeedbackListResponse(BaseModel):
    feedback: List[FeedbackItem]
    total: int
    page: int
    page_size: int


# ── Sessions ──────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class SessionResponse(BaseModel):
    session_id: str
    messages: List[ChatMessage]
    message_count: int


class DeleteSessionResponse(BaseModel):
    success: bool
    session_id: str
    message: str


# ── Health / Metrics ──────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    environment: str
    qdrant: str
    database: str


class MetricsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    total_queries: int
    total_feedback: int
    avg_confidence: float
    avg_faithfulness: Optional[float] = None
    avg_answer_relevance: Optional[float] = None
