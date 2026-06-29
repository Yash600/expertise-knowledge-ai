"""
main.py — FastAPI application entry point.

Wires all routers, configures CORS, and sets up startup/shutdown events.
"""


from __future__ import annotations
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import os
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routers import ingest, ask, documents, feedback, sessions, eval as eval_router
from app.config import get_settings
from app.models import HealthResponse, MetricsResponse

load_dotenv()

settings = get_settings()

app = FastAPI(
    title="Enterprise Knowledge Assistant API",
    description="RAG-powered enterprise Q&A over internal documents",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(ask.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(eval_router.router, prefix="/api/v1")

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    """Pre-warm models and build BM25 index on startup."""
    print("Starting Enterprise Knowledge Assistant API...")

    # Init SQLite session store
    try:
        from app.db.sessions import init_db
        init_db()
        print("  Session store ready")
    except Exception as e:
        print(f"  Session store init failed (non-fatal): {e}")

    # Build BM25 index from existing Qdrant data
    try:
        from app.retrieval.keyword import build_bm25_index
        build_bm25_index()
    except Exception as e:
        print(f"  BM25 index build failed (non-fatal): {e}")

    # Pre-load LangGraph pipeline (connects to Postgres checkpointer)
    try:
        from app.graph.pipeline import get_graph
        get_graph()
    except Exception as e:
        print(f"  LangGraph init failed (non-fatal): {e}")

    # NOTE: ML models (embedder, reranker) are NOT pre-loaded at startup.
    # They load lazily on the first request to keep startup RAM under 512 MB
    # (Render free tier limit). The models are baked into the Docker image
    # via the build-time RUN steps, so first-request latency is disk I/O only.

    print("API ready.")


# ── Health & Metrics ──────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    """Service health check."""
    qdrant_status = "ok"
    db_status = "ok"

    try:
        from app.ingestion.embedder import get_client
        get_client().get_collections()
    except Exception:
        qdrant_status = "error"

    try:
        import asyncpg
        conn = await asyncpg.connect(settings.supabase_database_url, timeout=3)
        await conn.close()
    except Exception:
        db_status = "error"

    return HealthResponse(
        status="ok" if qdrant_status == "ok" else "degraded",
        environment=settings.environment,
        qdrant=qdrant_status,
        database=db_status,
    )


@app.get("/metrics", response_model=MetricsResponse, tags=["system"])
async def metrics():
    """Basic usage metrics aggregated from Qdrant and Supabase."""
    total_chunks = 0
    total_docs = 0

    try:
        from app.ingestion.embedder import get_client
        client = get_client()
        info = client.get_collection(settings.qdrant_collection_name)
        total_chunks = info.points_count or 0

        # Count unique doc_ids
        doc_ids: set = set()
        offset = None
        while True:
            results, offset = client.scroll(
                collection_name=settings.qdrant_collection_name,
                limit=500,
                offset=offset,
                with_payload=["doc_id"],
                with_vectors=False,
            )
            for r in results:
                doc_ids.add(r.payload.get("doc_id", ""))
            if offset is None:
                break
        total_docs = len(doc_ids)
    except Exception:
        pass

    total_queries = 0
    total_feedback = 0
    avg_confidence = 0.0

    try:
        import asyncpg
        conn = await asyncpg.connect(settings.supabase_database_url, timeout=3)
        total_feedback = await conn.fetchval("SELECT COUNT(*) FROM feedback") or 0
        await conn.close()
    except Exception:
        pass

    return MetricsResponse(
        total_documents=total_docs,
        total_chunks=total_chunks,
        total_queries=total_queries,
        total_feedback=total_feedback,
        avg_confidence=avg_confidence,
    )


@app.get("/", tags=["system"])
async def root():
    return {"message": "Enterprise Knowledge Assistant API", "docs": "/docs"}
