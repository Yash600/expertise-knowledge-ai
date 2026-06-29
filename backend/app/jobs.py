"""
jobs.py — In-memory job store for async ingestion tasks.

Jobs are keyed by job_id (UUID). Each job has:
  status: "pending" | "processing" | "done" | "error"
  message: human-readable status string
  document: DocumentResponse (set when done)
  error: error detail (set when failed)
"""

from __future__ import annotations
from typing import Dict, Any
import threading

_store: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def create_job(job_id: str) -> None:
    with _lock:
        _store[job_id] = {
            "status": "pending",
            "message": "Queued for processing...",
            "document": None,
            "error": None,
        }


def update_job(job_id: str, **kwargs) -> None:
    with _lock:
        if job_id in _store:
            _store[job_id].update(kwargs)


def get_job(job_id: str) -> Dict[str, Any] | None:
    with _lock:
        return dict(_store.get(job_id, {}))


def delete_job(job_id: str) -> None:
    with _lock:
        _store.pop(job_id, None)
