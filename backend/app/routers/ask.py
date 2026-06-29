"""
routers/ask.py — POST /ask

Runs the full LangGraph RAG pipeline and returns the answer with sources.
Also persists each Q&A turn to SQLite so session history survives restarts.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.models import AskRequest, AskResponse, SourceCitation
from app.graph.pipeline import run_pipeline

router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("", response_model=AskResponse)
async def ask(
    request: AskRequest,
    user: dict = Depends(get_current_user),
):
    """
    Ask a question against the indexed knowledge base.
    Returns answer, source citations, and confidence score.
    """
    if not request.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty",
        )

    user_id = user["user_id"]

    try:
        result = await run_pipeline(
            query=request.question,
            session_id=request.session_id,
            user_id=user_id,
        )
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline error: {type(e).__name__}: {e}\n{traceback.format_exc()}",
        )

    answer = result.get("answer", "")

    # ── Persist to SQLite (non-blocking, fire-and-forget on error) ────────────
    try:
        from app.db.sessions import append_messages
        append_messages(
            session_id=request.session_id,
            user_id=user_id,
            user_msg=request.question,
            assistant_msg=answer,
        )
    except Exception as e:
        print(f"  [warn] Session persist failed: {e}")

    sources = [
        SourceCitation(
            filename=s.get("filename", "Unknown"),
            page=s.get("page"),
            chunk_id=s.get("chunk_id") or str(uuid.uuid4()),
            confidence=s.get("confidence", 0.0),
        )
        for s in result.get("sources", [])
    ]

    return AskResponse(
        answer=answer,
        sources=sources,
        confidence=result.get("confidence", 0.0),
        session_id=request.session_id,
        reasoning_mode=result.get("reasoning_mode", "single_doc"),
        rewritten_query=result.get("rewritten_query", request.question),
    )
