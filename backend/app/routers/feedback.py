"""
routers/feedback.py — POST /feedback, GET /feedback (admin)

Stores user thumbs up/down ratings and optional comments in Supabase.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status, Query
from dotenv import load_dotenv

from app.auth import get_current_user, get_admin_user
from app.models import (
    FeedbackRequest,
    FeedbackResponse,
    FeedbackItem,
    FeedbackListResponse,
)

load_dotenv()

router = APIRouter(prefix="/feedback", tags=["feedback"])

DB_URL = os.getenv("SUPABASE_DATABASE_URL", "")

_pool: asyncpg.Pool | None = None


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)
        # Create table if it doesn't exist
        async with _pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    comment TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
    return _pool


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    user: dict = Depends(get_current_user),
):
    """Submit thumbs up (2) or thumbs down (1) feedback with optional comment."""
    feedback_id = str(uuid.uuid4())

    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO feedback (id, user_id, session_id, question, answer, rating, comment, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                feedback_id,
                user["user_id"],
                request.session_id,
                request.question,
                request.answer,
                request.rating,
                request.comment,
                datetime.now(timezone.utc),
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store feedback: {e}",
        )

    return FeedbackResponse(
        success=True,
        feedback_id=feedback_id,
        message="Feedback recorded. Thank you!",
    )


@router.get("", response_model=FeedbackListResponse)
async def get_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rating: int | None = Query(None, ge=1, le=2),
    admin: dict = Depends(get_admin_user),
):
    """
    Admin: retrieve paginated feedback.
    Filter by rating: 1 = thumbs down, 2 = thumbs up.
    """
    offset = (page - 1) * page_size

    try:
        pool = await _get_pool()
        async with pool.acquire() as conn:
            if rating is not None:
                rows = await conn.fetch(
                    "SELECT * FROM feedback WHERE rating = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    rating, page_size, offset,
                )
                total = await conn.fetchval("SELECT COUNT(*) FROM feedback WHERE rating = $1", rating)
            else:
                rows = await conn.fetch(
                    "SELECT * FROM feedback ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                    page_size, offset,
                )
                total = await conn.fetchval("SELECT COUNT(*) FROM feedback")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch feedback: {e}",
        )

    items = [
        FeedbackItem(
            id=r["id"],
            user_id=r["user_id"],
            session_id=r["session_id"],
            question=r["question"],
            answer=r["answer"],
            rating=r["rating"],
            comment=r["comment"],
            created_at=r["created_at"],
        )
        for r in rows
    ]

    return FeedbackListResponse(
        feedback=items,
        total=total or 0,
        page=page,
        page_size=page_size,
    )
