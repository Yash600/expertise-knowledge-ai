"""
db/sessions.py — Session and message store.

Uses PostgreSQL (Supabase) in production and SQLite as local fallback.

Why dual-mode:
  - SQLite: zero-config for local dev, but ephemeral on Render free tier.
  - PostgreSQL: persistent across redeploys, horizontally scalable.

The DATABASE_URL env var controls which is used:
  - Set  → PostgreSQL (production)
  - Unset → SQLite (local dev)

Schema:
  sessions  — one row per conversation (id, user_id, title, timestamps, preview)
  messages  — one row per message (session_id, role, content, created_at)
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

# ── Backend detection ─────────────────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DATABASE_URL", "")
_USE_POSTGRES = bool(DATABASE_URL)


# ── PostgreSQL backend ────────────────────────────────────────────────────────

def _pg_conn():
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def _init_pg() -> None:
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id    TEXT PRIMARY KEY,
                    user_id       TEXT NOT NULL,
                    title         TEXT NOT NULL DEFAULT 'New Chat',
                    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    message_count INTEGER DEFAULT 0,
                    last_preview  TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_user
                    ON sessions(user_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS messages (
                    id          BIGSERIAL PRIMARY KEY,
                    session_id  TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    role        TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id, id ASC);
            """)
        conn.commit()


def _pg_ensure_session(session_id: str, user_id: str) -> None:
    now = _now()
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO sessions (session_id, user_id, title, created_at, updated_at)
                   VALUES (%s, %s, 'New Chat', %s, %s)
                   ON CONFLICT (session_id) DO NOTHING""",
                (session_id, user_id, now, now),
            )
        conn.commit()


def _pg_append_messages(session_id: str, user_id: str, user_msg: str, assistant_msg: str) -> None:
    now = _now()
    preview = assistant_msg[:120].replace("\n", " ")
    title_snippet = user_msg[:60]

    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO sessions (session_id, user_id, title, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (session_id) DO NOTHING""",
                (session_id, user_id, title_snippet, now, now),
            )
            cur.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (%s, %s, %s, %s)",
                (session_id, "user", user_msg, now),
            )
            cur.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (%s, %s, %s, %s)",
                (session_id, "assistant", assistant_msg, now),
            )
            cur.execute(
                """UPDATE sessions
                   SET updated_at = %s,
                       last_preview = %s,
                       message_count = message_count + 2,
                       title = CASE WHEN title = 'New Chat' THEN %s ELSE title END
                   WHERE session_id = %s""",
                (now, preview, title_snippet, session_id),
            )
        conn.commit()


def _pg_delete_session(session_id: str, user_id: str) -> bool:
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM sessions WHERE session_id = %s AND user_id = %s",
                (session_id, user_id),
            )
            deleted = cur.rowcount > 0
        conn.commit()
    return deleted


def _pg_list_sessions(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT session_id, title,
                          created_at::text, updated_at::text,
                          message_count, last_preview
                   FROM sessions
                   WHERE user_id = %s
                   ORDER BY updated_at DESC
                   LIMIT %s""",
                (user_id, limit),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def _pg_get_session_messages(session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT session_id, title, created_at::text, updated_at::text, message_count, last_preview FROM sessions WHERE session_id = %s AND user_id = %s",
                (session_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            session = dict(zip(cols, row))

            cur.execute(
                "SELECT role, content FROM messages WHERE session_id = %s ORDER BY id ASC",
                (session_id,),
            )
            msgs = [{"role": r[0], "content": r[1]} for r in cur.fetchall()]

    return {**session, "messages": msgs}


# ── SQLite backend (local dev fallback) ───────────────────────────────────────

import sqlite3

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "sessions.db"
_lock = threading.Lock()


def _sqlite_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_sqlite() -> None:
    with _lock, _sqlite_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id    TEXT PRIMARY KEY,
                user_id       TEXT NOT NULL,
                title         TEXT NOT NULL DEFAULT 'New Chat',
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL,
                message_count INTEGER DEFAULT 0,
                last_preview  TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, updated_at DESC);
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id ASC);
        """)
        conn.commit()


def _sqlite_ensure_session(session_id: str, user_id: str) -> None:
    now = _now()
    with _lock, _sqlite_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (session_id, user_id, title, created_at, updated_at) VALUES (?, ?, 'New Chat', ?, ?)",
            (session_id, user_id, now, now),
        )
        conn.commit()


def _sqlite_append_messages(session_id: str, user_id: str, user_msg: str, assistant_msg: str) -> None:
    now = _now()
    preview = assistant_msg[:120].replace("\n", " ")
    title_snippet = user_msg[:60]
    with _lock, _sqlite_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (session_id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, title_snippet, now, now),
        )
        conn.executemany(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            [(session_id, "user", user_msg, now), (session_id, "assistant", assistant_msg, now)],
        )
        conn.execute(
            """UPDATE sessions SET updated_at=?, last_preview=?, message_count=message_count+2,
               title=CASE WHEN title='New Chat' THEN ? ELSE title END WHERE session_id=?""",
            (now, preview, title_snippet, session_id),
        )
        conn.commit()


def _sqlite_delete_session(session_id: str, user_id: str) -> bool:
    with _lock, _sqlite_conn() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE session_id=? AND user_id=?", (session_id, user_id))
        conn.commit()
        return cur.rowcount > 0


def _sqlite_list_sessions(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    with _sqlite_conn() as conn:
        rows = conn.execute(
            "SELECT session_id, title, created_at, updated_at, message_count, last_preview FROM sessions WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def _sqlite_get_session_messages(session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    with _sqlite_conn() as conn:
        session = conn.execute("SELECT * FROM sessions WHERE session_id=? AND user_id=?", (session_id, user_id)).fetchone()
        if not session:
            return None
        msgs = conn.execute("SELECT role, content FROM messages WHERE session_id=? ORDER BY id ASC", (session_id,)).fetchall()
    return {**dict(session), "messages": [{"role": r["role"], "content": r["content"]} for r in msgs]}


# ── Public API (auto-selects backend) ─────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    if _USE_POSTGRES:
        print(f"  Session store: PostgreSQL")
        _init_pg()
    else:
        print(f"  Session store: SQLite ({_DB_PATH})")
        _init_sqlite()


def ensure_session(session_id: str, user_id: str) -> None:
    if _USE_POSTGRES:
        _pg_ensure_session(session_id, user_id)
    else:
        _sqlite_ensure_session(session_id, user_id)


def append_messages(session_id: str, user_id: str, user_msg: str, assistant_msg: str) -> None:
    if _USE_POSTGRES:
        _pg_append_messages(session_id, user_id, user_msg, assistant_msg)
    else:
        _sqlite_append_messages(session_id, user_id, user_msg, assistant_msg)


def delete_session(session_id: str, user_id: str) -> bool:
    if _USE_POSTGRES:
        return _pg_delete_session(session_id, user_id)
    return _sqlite_delete_session(session_id, user_id)


def list_sessions(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    if _USE_POSTGRES:
        return _pg_list_sessions(user_id, limit)
    return _sqlite_list_sessions(user_id, limit)


def get_session_messages(session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    if _USE_POSTGRES:
        return _pg_get_session_messages(session_id, user_id)
    return _sqlite_get_session_messages(session_id, user_id)
