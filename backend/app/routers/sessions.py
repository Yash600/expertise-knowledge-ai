"""
routers/sessions.py — Session history endpoints.

GET  /sessions              — list all sessions for the current user (newest first)
GET  /sessions/{id}         — get a session with its full message history
DELETE /sessions/{id}       — delete a session
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List

from app.auth import get_current_user
from app.db import sessions as db

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionSummary(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    last_preview: str


class ChatMessage(BaseModel):
    role: str
    content: str


class SessionDetail(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    messages: List[ChatMessage]


@router.get("", response_model=List[SessionSummary])
async def list_sessions(user: dict = Depends(get_current_user)):
    """Return all sessions for the current user, newest first."""
    return db.list_sessions(user["user_id"])


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, user: dict = Depends(get_current_user)):
    """Return a session with its full message history."""
    data = db.get_session_messages(session_id, user["user_id"])
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    return data


@router.delete("/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    """Delete a session and all its messages."""
    deleted = db.delete_session(session_id, user["user_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}
