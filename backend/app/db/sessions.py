"""
db/sessions.py — SQLite-backed session and message store.

Why SQLite (not MemorySaver alone):
  LangGraph's MemorySaver lives only in the backend process — it resets on restart.
  SQLite persists sessions + messages to disk so users can resume old chats even
  after the server restarts. On resume, we pass stored messages as chat_history
  to LangGraph's initial state and it picks up naturally.

Schema:
  sessions  — one row per conversation (id, user_id, title, timestamps, preview)
  messages  — one row per Q&A message (session_id, role, content, created_at)
"""

from __future__ import annotations

import sqlite3
import threading
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# DB file lives next to this package
_DB_PATH = Path(__file__).parent.parent.parent / "data" / "sessions.db"
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # safe concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Called at startup."""
    with _lock, _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                user_id      TEXT NOT NULL,
                title        TEXT NOT NULL DEFAULT 'New Chat',
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL,
                message_count INTEGER DEFAULT 0,
                last_preview TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user
                ON sessions(user_id, updated_at DESC);

            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, id ASC);
        """)
        conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Write operations ──────────────────────────────────────────────────────────

def ensure_session(session_id: str, user_id: str) -> None:
    """Create session row if it doesn't exist yet."""
    now = _now()
    with _lock, _conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO sessions
               (session_id, user_id, title, created_at, updated_at)
               VALUES (?, ?, 'New Chat', ?, ?)""",
            (session_id, user_id, now, now),
        )
        conn.commit()


def append_messages(
    session_id: str,
    user_id: str,
    user_msg: str,
    assistant_msg: str,
) -> None:
    """
    Append one Q&A turn to the messages table and update session metadata.
    Title is set from the first user message (max 60 chars).
    """
    now = _now()
    preview = assistant_msg[:120].replace("\n", " ")
    title_snippet = user_msg[:60]

    with _lock, _conn() as conn:
        # Ensure session exists
        conn.execute(
            """INSERT OR IGNORE INTO sessions
               (session_id, user_id, title, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, user_id, title_snippet, now, now),
        )
        # Insert both messages
        conn.executemany(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            [
                (session_id, "user", user_msg, now),
                (session_id, "assistant", assistant_msg, now),
            ],
        )
        # Update title only if it's still 'New Chat'
        conn.execute(
            """UPDATE sessions
               SET updated_at = ?,
                   last_preview = ?,
                   message_count = message_count + 2,
                   title = CASE WHEN title = 'New Chat' THEN ? ELSE title END
               WHERE session_id = ?""",
            (now, preview, title_snippet, session_id),
        )
        conn.commit()


def delete_session(session_id: str, user_id: str) -> bool:
    with _lock, _conn() as conn:
        cur = conn.execute(
            "DELETE FROM sessions WHERE session_id = ? AND user_id = ?",
            (session_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


# ── Read operations ───────────────────────────────────────────────────────────

def list_sessions(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Return sessions for a user, newest first."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT session_id, title, created_at, updated_at,
                      message_count, last_preview
               FROM sessions
               WHERE user_id = ?
               ORDER BY updated_at DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_session_messages(session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Return session metadata + all messages, or None if not found/wrong user."""
    with _conn() as conn:
        session = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not session:
            return None

        msgs = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()

    return {
        **dict(session),
        "messages": [{"role": r["role"], "content": r["content"]} for r in msgs],
    }
