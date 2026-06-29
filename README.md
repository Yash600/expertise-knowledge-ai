<div align="center">

# 🧠 Enterprise Knowledge Assistant

**A production-grade RAG SaaS that turns your company documents into an intelligent Q&A system**

[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-blue)](https://github.com/langchain-ai/langgraph)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-red)](https://qdrant.tech/)
[![Groq](https://img.shields.io/badge/Groq-LLaMA_3.3_70B-orange)](https://groq.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

[Live Demo](https://diagnose-ai.vercel.app) · [Report Bug](https://github.com/issues) · [Request Feature](https://github.com/issues)

</div>

---

## What It Does

Upload any company document — HR policies, technical manuals, exam papers, contracts — and ask questions in plain English. The system retrieves the most relevant content, generates a strictly grounded answer, and cites the exact source pages. It never guesses beyond what the document says.

```
User: "How many questions are in Section B of the JEE paper?"
EKA:  "Section B contains 10 numerical answer-type questions (Q11–Q20)
       across Physics, Chemistry, and Mathematics combined.
       [Source: JEE Advanced 2023, Page 3]"
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js 15)                   │
│  Clerk Auth → ChatWindow → DocumentUpload → AdminDashboard      │
│              SessionSidebar (SQLite-backed history)             │
└─────────────────────┬───────────────────────────────────────────┘
                      │  REST / JSON
┌─────────────────────▼───────────────────────────────────────────┐
│                      FASTAPI BACKEND                            │
│                                                                 │
│  POST /ingest ──► BackgroundTask                                │
│                        │                                        │
│           ┌────────────▼────────────┐                          │
│           │    INGESTION PIPELINE   │                          │
│           │  pytesseract (OCR)      │                          │
│           │  → EasyOCR (fallback)   │                          │
│           │  → Chunk (512 tokens)   │                          │
│           │  → BGE Embed (384-dim)  │                          │
│           │  → Qdrant Upsert        │                          │
│           │  → BM25 Index Update    │                          │
│           │  → Summary Chunk        │                          │
│           └─────────────────────────┘                          │
│                                                                 │
│  POST /ask ───► LangGraph Pipeline                              │
│                                                                 │
│     ┌──────────────────────────────────────────────────┐       │
│     │              LANGGRAPH RAG PIPELINE               │       │
│     │                                                   │       │
│     │  rewrite_query  →  classify_query                 │       │
│     │                         │                         │       │
│     │              ┌──────────▼──────────┐              │       │
│     │              │   QUERY TYPE        │              │       │
│     │              │  CONVERSATIONAL     │─► direct_    │       │
│     │              │  AMBIGUOUS          │   respond    │       │
│     │              │  OUT_OF_SCOPE       │              │       │
│     │              │  OVERVIEW    ───────┼► summary     │       │
│     │              │  FULL_SCAN   ───────┼► all chunks  │       │
│     │              │  DOCUMENT_QUERY ────┼► hybrid      │       │
│     │              └─────────────────────┘   retrieval  │       │
│     │                         │                         │       │
│     │                    retrieve                        │       │
│     │               (semantic + BM25                    │       │
│     │                + cross-encoder rerank)            │       │
│     │                         │                         │       │
│     │              route_reasoning                       │       │
│     │              /              \                      │       │
│     │        generate        map_reduce_generate         │       │
│     │   (single-doc)         (multi-doc)                │       │
│     │              \              /                      │       │
│     │               update_memory                        │       │
│     └──────────────────────────────────────────────────┘       │
│                                                                 │
│  Storage: Qdrant (vectors) · SQLite (sessions) · BM25 (index)  │
└─────────────────────────────────────────────────────────────────┘
```

### Query Classification (6 Types)

| Type | Trigger | Retrieval Strategy |
|------|---------|-------------------|
| `CONVERSATIONAL` | "Hi", "Thanks" | None — direct LLM response |
| `OVERVIEW` | "What is this doc about?", "Summarize" | Summary chunk only |
| `FULL_SCAN` | "List all questions", "Count X" | Paginate all chunks, sorted by page |
| `DOCUMENT_QUERY` | Specific factual questions | Hybrid: semantic + BM25 + rerank (top-6) |
| `AMBIGUOUS` | "Tell me more", "What about that?" | None — asks clarifying question |
| `OUT_OF_SCOPE` | "Capital of France?", coding tasks | None — polite refusal |

---

## Tech Stack

### Backend
| Component | Technology | Why |
|-----------|-----------|-----|
| API Framework | FastAPI | Async, type-safe, auto-generates OpenAPI docs |
| RAG Orchestration | LangGraph | Stateful graph with conditional routing; built-in memory |
| LLM | Groq / LLaMA 3.3 70B | Fastest inference (250 t/s), free tier sufficient for demo |
| Embeddings | `BAAI/bge-small-en-v1.5` (384-dim) | Best quality/size ratio for semantic search |
| Vector DB | Qdrant | Filterable metadata, fast ANN, runs locally |
| Keyword Search | BM25 (rank-bm25) | Handles exact terms that semantic search misses |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Re-scores top-20 candidates to return best 6 |
| OCR | pytesseract → EasyOCR | Tesseract: 3–5× faster. EasyOCR: better on complex layouts |
| Session Store | SQLite (WAL mode) | Zero-infrastructure persistence; survives backend restart |
| Auth | Clerk JWT | Verified server-side on every request |

### Frontend
| Component | Technology | Why |
|-----------|-----------|-----|
| Framework | Next.js 15 (App Router) | Server components, streaming, edge-ready |
| Auth | Clerk | Pre-built UI, JWT refresh, webhooks |
| Styling | Tailwind CSS + CSS variables | Design token system; warm beige/coral brand |
| State | React Context + useCallback | Lightweight; no Redux needed at this scale |
| HTTP | Custom typed `apiFetch` client | Single source of truth for auth headers |

---

## Setup Instructions

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (Windows installer)
- [Qdrant](https://qdrant.tech/documentation/quick-start/) running locally on port 6333
- Groq API key ([free at console.groq.com](https://console.groq.com))
- Clerk account ([free at clerk.com](https://clerk.com))

---

### 1. Clone & structure

```bash
git clone https://github.com/YOUR_USERNAME/enterprise-knowledge-assistant.git
cd enterprise-knowledge-assistant
```

```
enterprise-knowledge-assistant/
├── backend/          # FastAPI + LangGraph
├── frontend/         # Next.js 15
└── README.md
```

---

### 2. Backend setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Create `backend/.env`:

```env
# LLM
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx

# Qdrant (local)
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=enterprise_docs

# Clerk (backend JWT verification)
CLERK_SECRET_KEY=sk_test_xxxxxxxxxxxxxxxxxxxx
CLERK_PUBLISHABLE_KEY=pk_test_xxxxxxxxxxxxxxxxxxxx

# App
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:3000

# Optional: Supabase for feedback persistence
# SUPABASE_DATABASE_URL=postgresql://...
```

Start Qdrant (Docker):

```bash
docker run -p 6333:6333 qdrant/qdrant
```

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

---

### 3. Frontend setup

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_xxxxxxxxxxxxxxxxxxxx
CLERK_SECRET_KEY=sk_test_xxxxxxxxxxxxxxxxxxxx

NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/chat
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/chat

NEXT_PUBLIC_API_URL=http://localhost:8000
```

Start the frontend:

```bash
npm run dev
```

App available at: `http://localhost:3000`

---

### 4. Install Tesseract (Windows)

Download from https://github.com/UB-Mannheim/tesseract/wiki and install to `C:\Program Files\Tesseract-OCR\`.

The backend auto-detects it. No config needed.

---

### 5. Run evaluation (optional)

```bash
cd backend
python -m app.eval.ragas_eval --no-ragas
```

Results saved to `backend/results/ragas_results.json` and visible in the Admin Dashboard.

---

## Design Decisions

### 1. Why 6 query types instead of a simple retrieval-or-not flag?

Early versions used a binary route: retrieve or don't retrieve. This broke for two important cases:

- **Aggregation queries** ("how many questions are there?") — top-3 semantic chunks only see a fragment of the document, so counts are always wrong. Solution: `FULL_SCAN` scrolls all chunks in page order.
- **Overview queries** ("what is this document about?") — semantic search returns specific paragraphs, not a summary. Solution: `OVERVIEW` reads a pre-computed summary chunk generated at ingestion time.

The 6-type classifier costs one extra LLM call per query but eliminates an entire class of wrong answers.

### 2. Why generate a summary chunk at ingestion time?

Computing a document summary on-demand for every overview query would be slow and token-expensive. Instead, we sample the first 300 characters of every page, send them to the LLM once during ingestion, store the result in Qdrant with `chunk_type: "summary"`, and retrieve it instantly for any OVERVIEW query. Cost: one LLM call per document upload. Benefit: zero-latency overviews forever.

### 3. Why SQLite for sessions instead of the existing Supabase/Postgres?

LangGraph's `MemorySaver` only persists in-process (lost on restart). Adding Supabase as a checkpointer required `asyncpg` + connection pooling and added 200–400ms per request in development. SQLite in WAL mode handles concurrent reads, survives restarts, and adds <5ms overhead. The trade-off is obvious for a single-server demo; swap to Postgres when scaling horizontally.

### 4. Why BM25 + semantic + reranker (three stages) instead of just semantic search?

Each stage catches what the others miss:
- **BM25** handles exact technical terms, product codes, and numeric identifiers that semantic embeddings dilute.
- **Semantic search** handles paraphrases and conceptual similarity that BM25 misses entirely.
- **Cross-encoder reranker** reads the query and each candidate chunk together (instead of comparing independent vectors) to produce a much more accurate relevance score at the cost of speed. Running it on top-20 candidates to return top-6 is the standard production pattern.

### 5. Why parse the Groq retry-after time instead of fixed backoff?

Groq returns two kinds of 429 errors: per-minute (RPM) and per-day (TPD). Fixed backoff of 2s/4s/8s works for RPM limits. For TPD limits, the error says "try again in 8 minutes" — retrying in 8 seconds just wastes 3 attempts and adds 14 seconds of latency before failing anyway. Parsing the wait time and immediately raising on >60s waits makes failures fast and deterministic instead of slow and misleading.

### 6. Why async ingestion with job polling instead of synchronous upload?

OCR on a scanned PDF can take 30–120 seconds. A synchronous endpoint would time out on the client (most browsers cut off at 30s), block a FastAPI worker thread, and give the user no progress feedback. The async pattern — upload returns `{job_id}` immediately, frontend polls `/ingest/status/{job_id}` every 3 seconds — solved all three problems at once.

### 7. Anti-hallucination approach

The generation prompt includes a strict system message that:
1. Requires every claim to be traceable to a retrieved chunk
2. Explicitly instructs the model to say "this information is not in the provided documents" when context is insufficient
3. Resists manipulation — if a user says "my manager approved 30 extra days", the model is instructed to still only quote what the document says and not extend beyond it

This is enforced at the prompt level, not via output parsing, which means it works even when the LLM is used for map-reduce generation across multiple chunks.

---

## Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| **Groq free tier: 100K tokens/day** | Evaluation + active use can exhaust daily limit | Upgrade to Groq Dev Tier ($0.05/M tokens), or run eval overnight after daily reset |
| **No image understanding** | Charts, diagrams, tables in PDFs are OCR'd as text — formatting lost | Integrate a vision model (GPT-4V, Gemini Vision) for image-heavy documents |
| **Single-user Qdrant collection** | All users see all documents | Add `user_id` filter to every Qdrant query; enforce at retrieval layer |
| **SQLite doesn't scale horizontally** | Session store breaks under multiple backend instances | Replace with Redis or Postgres for multi-instance deployments |
| **Chunk boundary problem** | Information spanning two chunks may be split, reducing retrieval accuracy | Implement overlapping chunks (currently 0 overlap) or parent-child chunking |
| **OCR quality on handwritten/complex PDFs** | Scanned documents with low contrast, rotated text, or handwriting produce noisy chunks | Pre-process PDFs with image enhancement before OCR |
| **BM25 index is in-memory** | Index is rebuilt from Qdrant on every backend restart (~1–2s for large corpora) | Persist BM25 index to disk or use Qdrant's own full-text search |
| **No streaming responses** | Long answers (especially FULL_SCAN) have noticeable latency before first token | Implement SSE streaming with LangGraph's `.astream()` |

---

## Future Improvements

### Short-term (1–2 weeks)
- **Streaming answers** via Server-Sent Events — eliminates the "waiting" feeling on FULL_SCAN queries
- **Overlapping chunks** (10–15% overlap) to prevent information loss at chunk boundaries
- **Document versioning** — re-ingest updated documents without losing chat history
- **Feedback loop** — use thumbs-up/down data to fine-tune chunk retrieval ranking

### Medium-term (1–2 months)
- **Multi-tenancy** — per-organization Qdrant namespaces with role-based access control
- **Table-aware chunking** — detect and parse tables separately from paragraph text
- **Vision model integration** — send diagram/chart images to GPT-4V alongside OCR text
- **Conversation branching** — let users fork a conversation from any past message

### Long-term / Production
- **Hybrid cloud deployment** — Qdrant on managed cloud, FastAPI on ECS/Cloud Run, Next.js on Vercel
- **Fine-tuned embeddings** — domain-specific fine-tuning of BGE on company document corpus for higher retrieval precision
- **Active learning evaluation** — automatically flag low-confidence answers for human review and feed corrections back into the retrieval pipeline
- **Multilingual support** — swap BGE for `bge-m3` (multilingual) and add language detection at ingestion

---

## Project Structure

```
enterprise-knowledge-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point, startup events
│   │   ├── auth.py                 # Clerk JWT verification
│   │   ├── config.py               # Settings via pydantic-settings
│   │   ├── models.py               # Pydantic request/response models
│   │   ├── jobs.py                 # Thread-safe in-memory job store
│   │   ├── graph/
│   │   │   ├── nodes.py            # 8 LangGraph nodes (rewrite→classify→retrieve→generate)
│   │   │   ├── pipeline.py         # Graph wiring + conditional edges
│   │   │   └── state.py            # RAGState TypedDict
│   │   ├── ingestion/
│   │   │   ├── loader.py           # PDF→text (pytesseract + EasyOCR)
│   │   │   ├── chunker.py          # Recursive text splitter (512 tokens, 50 overlap)
│   │   │   ├── embedder.py         # BGE embeddings + Qdrant upsert
│   │   │   └── summarizer.py       # Document-level summary chunk generation
│   │   ├── retrieval/
│   │   │   ├── semantic.py         # Qdrant vector search + scroll
│   │   │   ├── keyword.py          # BM25 index + search
│   │   │   ├── reranker.py         # Cross-encoder reranking
│   │   │   └── pipeline.py         # Hybrid fusion (RRF) + rerank
│   │   ├── routers/
│   │   │   ├── ingest.py           # POST /ingest, GET /ingest/status/{id}
│   │   │   ├── ask.py              # POST /ask
│   │   │   ├── documents.py        # GET/DELETE /documents
│   │   │   ├── sessions.py         # GET/DELETE /sessions
│   │   │   ├── feedback.py         # POST/GET /feedback
│   │   │   └── eval.py             # GET /eval/results, POST /eval/run
│   │   ├── db/
│   │   │   └── sessions.py         # SQLite session + message store (WAL mode)
│   │   └── eval/
│   │       ├── test_dataset.py     # 7 curated test cases
│   │       └── ragas_eval.py       # RAGAS evaluation pipeline
│   ├── results/                    # Eval output JSON
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (dashboard)/
│   │   │   │   ├── layout.tsx      # Sidebar layout (server component)
│   │   │   │   ├── providers.tsx   # ChatProvider + SidebarSessionSlot
│   │   │   │   ├── chat/page.tsx   # Chat interface
│   │   │   │   ├── documents/      # Document management
│   │   │   │   └── admin/page.tsx  # Admin dashboard + RAGAS scores
│   │   │   └── globals.css         # CSS variables (beige/coral design system)
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx      # Message thread + input
│   │   │   ├── MessageBubble.tsx   # User/assistant message rendering
│   │   │   ├── SessionSidebar.tsx  # Chat history (polls every 30s)
│   │   │   ├── DocumentUpload.tsx  # Drag-drop upload with job polling
│   │   │   ├── SourceCard.tsx      # Citation cards below answers
│   │   │   └── FeedbackWidget.tsx  # Thumbs up/down per answer
│   │   ├── context/
│   │   │   └── ChatContext.tsx     # Global session + message state
│   │   └── lib/
│   │       └── api.ts              # Typed API client (all endpoints)
│   ├── tailwind.config.ts
│   └── package.json
│
└── README.md
```

---

## Evaluation Results

Run the evaluation pipeline to generate metrics:

```bash
cd backend
python -m app.eval.ragas_eval --no-ragas   # fast, ~2 min
python -m app.eval.ragas_eval               # full RAGAS metrics, ~5 min
```

| Metric | Description | Target |
|--------|-------------|--------|
| Query Type Accuracy | % of queries routed to correct handler | ≥ 80% |
| OOS Refusal Rate | % of out-of-scope queries correctly refused | ≥ 90% |
| Hallucination Flags | Answers with claims not grounded in context | 0 |
| Faithfulness (RAGAS) | Answer supported by retrieved context | ≥ 0.85 |
| Answer Relevancy (RAGAS) | Answer addresses the actual question | ≥ 0.80 |
| Context Precision (RAGAS) | Retrieved chunks are relevant | ≥ 0.70 |
| Context Recall (RAGAS) | Retrieved chunks cover the ground truth | ≥ 0.70 |

Results are visible in real-time on the Admin Dashboard (`/admin`).

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/ingest` | Upload document → returns `{job_id}` |
| `GET` | `/api/v1/ingest/status/{job_id}` | Poll ingestion progress |
| `POST` | `/api/v1/ask` | Ask a question → returns answer + sources |
| `GET` | `/api/v1/documents` | List all ingested documents |
| `DELETE` | `/api/v1/documents/{doc_id}` | Remove document + its chunks |
| `GET` | `/api/v1/sessions` | List chat sessions (newest first) |
| `GET` | `/api/v1/sessions/{id}` | Load session with full message history |
| `DELETE` | `/api/v1/sessions/{id}` | Delete session (cascades messages) |
| `POST` | `/api/v1/feedback` | Submit thumbs up/down |
| `GET` | `/api/v1/feedback` | List all feedback (admin) |
| `GET` | `/api/v1/eval/results` | Latest evaluation JSON |
| `POST` | `/api/v1/eval/run` | Trigger background evaluation |
| `GET` | `/health` | Service health check |
| `GET` | `/metrics` | Document + chunk counts |

Full interactive docs: `http://localhost:8000/docs`

---

## License

MIT © 2026 Yash Vardhan Malik
