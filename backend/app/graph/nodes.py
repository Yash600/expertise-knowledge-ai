"""
nodes.py — LangGraph node implementations for the RAG pipeline.

Query lifecycle:
  1. rewrite_query       — Rephrase using chat history
  2. classify_query      — LLM classifies intent:
                            CONVERSATIONAL | DOCUMENT_QUERY | AGGREGATION | OUT_OF_SCOPE
  3. retrieve            — Fetch chunks based on query type:
                            CONVERSATIONAL  → skip (no retrieval)
                            AGGREGATION     → summary chunks only
                            DOCUMENT_QUERY  → semantic+BM25+rerank
                            OUT_OF_SCOPE    → skip
  4. route_reasoning     — single_doc vs multi_doc (or direct for conversational)
  5. generate            — Strictly grounded answer (resists manipulation, no hallucination)
  6. map_reduce_generate — Multi-doc: per-chunk map + reduce
  7. update_memory       — Append to chat history
"""

from __future__ import annotations

import os
from typing import List, Dict, Any

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage, AIMessage

from .state import RAGState

load_dotenv()

GROQ_MODEL = "llama-3.3-70b-versatile"
MULTI_DOC_THRESHOLD = int(os.getenv("MULTI_DOC_THRESHOLD", "3"))
MEMORY_WINDOW = int(os.getenv("MEMORY_WINDOW", "6"))

_llm: ChatGroq | None = None


def _get_llm() -> ChatGroq:
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            model=GROQ_MODEL,
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.1,
            max_tokens=1024,
        )
    return _llm


def _llm_invoke(messages: list, retries: int = 3) -> Any:
    """
    Invoke LLM with smart retry on rate-limit (429) or server errors (5xx).

    - RPM (requests/minute) limit: waits 2s → 4s → 8s, retries up to `retries` times.
    - TPD (tokens/day) limit: detected when Groq says "try again in Xm Ys" with X > 1 min.
      In that case we do NOT retry (it would take minutes to clear) — raise immediately so
      the caller can degrade gracefully instead of blocking the pipeline.
    """
    import re
    import time
    llm = _get_llm()
    last_exc = None
    for attempt in range(retries):
        try:
            return llm.invoke(messages)
        except Exception as e:
            err_str = str(e)
            is_rate = "429" in err_str or "rate" in err_str.lower()
            is_server = "503" in err_str or "502" in err_str

            if not (is_rate or is_server):
                raise  # auth errors, bad requests — no retry

            # Parse "Please try again in Xm Ys" from the error body
            m = re.search(r"try again in\s+(?:(\d+)m)?([\d.]+)s", err_str)
            if m:
                minutes = int(m.group(1) or 0)
                seconds = float(m.group(2) or 0)
                wait_secs = minutes * 60 + seconds
                if wait_secs > 60:
                    # Daily token limit (TPD) — retrying in 8s is pointless
                    print(f"  [TPD limit] Groq requires {wait_secs:.0f}s wait — skipping retry.")
                    raise  # let caller handle gracefully

            wait = 2 ** (attempt + 1)  # 2s, 4s, 8s — fine for RPM limits
            print(f"  [retry {attempt+1}/{retries}] Groq error: {e}. Waiting {wait}s...")
            time.sleep(wait)
            last_exc = e
    raise last_exc


def _format_history(history: List[Dict]) -> List:
    messages = []
    for msg in history[-MEMORY_WINDOW:]:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    return messages


# ── Node 1: Query Rewriter ────────────────────────────────────────────────────

def rewrite_query(state: RAGState) -> RAGState:
    query = state["query"]
    history = state.get("chat_history", [])

    if not history:
        return {**state, "rewritten_query": query}

    llm = _get_llm()
    system = SystemMessage(content=(
        "You are a query rewriter for a RAG system. "
        "Given the conversation history and the user's latest question, "
        "rewrite the question to be a clear, self-contained search query. "
        "Output ONLY the rewritten query. No explanation."
    ))
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in history[-MEMORY_WINDOW:]
    )
    human = HumanMessage(content=(
        f"Conversation history:\n{history_text}\n\n"
        f"User's latest question: {query}\n\n"
        f"Rewritten query:"
    ))

    try:
        result = _llm_invoke([system, human])
        rewritten = result.content.strip()
    except Exception:
        rewritten = query

    return {**state, "rewritten_query": rewritten}


# ── Node 2: Query Classifier ──────────────────────────────────────────────────

_QUERY_TYPE_PROMPT = """\
You are a query classifier for an Enterprise Knowledge Assistant.

The assistant has access to a knowledge base of uploaded company documents.
It can ONLY answer questions that are grounded in those documents.

Classify the user's query into exactly one of these types:

CONVERSATIONAL  — Pure greeting or chitchat with no information need.
                  Examples: "hi", "hello", "thanks", "who are you", "what can you do"

OVERVIEW        — Asks for a COUNT, TOTAL, or HIGH-LEVEL SUMMARY of the document structure.
                  Does NOT need full question text — just structure/counts.
                  Examples: "how many questions", "total number of sections", "what topics are covered",
                  "give me an overview", "summarize the document", "what subjects does this cover"

FULL_SCAN       — Needs to READ or LIST actual CONTENT across the WHOLE document.
                  Requires every page/chunk, not just counts.
                  Examples: "list all questions", "list questions related to physics",
                  "show all questions with options", "list full question with options",
                  "list all chemistry questions", "give me all questions from section 2",
                  "list every question", "show me all problems"

DOCUMENT_QUERY  — A specific targeted question answerable from a few sections of the knowledge base.
                  Examples: "what is the leave policy", "explain question 5", "what does section 2 say",
                  "what is the answer to Q12"

AMBIGUOUS       — The query is too vague or context-free to answer meaningfully.
                  Ask for clarification instead of guessing.
                  Examples: "tell me more", "what about the other one?", "explain that",
                  "more details", "and?", single-word queries like "policy" with no context

OUT_OF_SCOPE    — Cannot be answered from a document knowledge base.
                  Examples: "what is the capital of France", "write me a poem", "solve 2+2",
                  coding help, weather, current events

Rules:
- "list questions related to X" → always FULL_SCAN (needs actual question text from every page)
- "how many questions" → OVERVIEW (needs count, not full text)
- Short vague follow-ups with unclear referents (this/that/it/other) → AMBIGUOUS
- If the user argues for extra info ("I have XYZ reason, can I get more"), classify as DOCUMENT_QUERY
- When in doubt between DOCUMENT_QUERY and OUT_OF_SCOPE, prefer DOCUMENT_QUERY.
- Output ONLY one word: CONVERSATIONAL, OVERVIEW, FULL_SCAN, DOCUMENT_QUERY, AMBIGUOUS, or OUT_OF_SCOPE.
"""


def classify_query(state: RAGState) -> RAGState:
    """
    Classify the query to decide retrieval strategy.
    Sets state['query_type']: CONVERSATIONAL | AGGREGATION | DOCUMENT_QUERY | OUT_OF_SCOPE
    """
    query = state.get("rewritten_query") or state["query"]
    llm = _get_llm()

    try:
        result = _llm_invoke([
            SystemMessage(content=_QUERY_TYPE_PROMPT),
            HumanMessage(content=f"User query: {query}\n\nClassification:"),
        ])
        raw = result.content.strip().upper().split()[0]
        valid = {"CONVERSATIONAL", "OVERVIEW", "FULL_SCAN", "DOCUMENT_QUERY", "AMBIGUOUS", "OUT_OF_SCOPE"}
        query_type = raw if raw in valid else "DOCUMENT_QUERY"
    except Exception:
        query_type = "DOCUMENT_QUERY"  # safe default

    return {**state, "query_type": query_type}


# ── Node 3: Retrieve ──────────────────────────────────────────────────────────

def retrieve(state: RAGState) -> RAGState:
    """
    Fetch chunks based on query_type:
      CONVERSATIONAL  → no retrieval (direct LLM response)
      OUT_OF_SCOPE    → no retrieval (refusal)
      OVERVIEW        → summary chunks only (structure/counts, not full text)
      FULL_SCAN       → ALL content chunks (for listing questions, showing full content)
      DOCUMENT_QUERY  → semantic+BM25+rerank (top-N targeted)
    """
    query_type = state.get("query_type", "DOCUMENT_QUERY")

    if query_type in ("CONVERSATIONAL", "OUT_OF_SCOPE", "AMBIGUOUS"):
        return {**state, "retrieved_chunks": []}

    query = state.get("rewritten_query") or state["query"]

    try:
        if query_type == "OVERVIEW":
            # Use pre-generated summary chunk — fast, covers structure/counts
            from app.retrieval.semantic import get_summary_chunks
            chunks = get_summary_chunks()
            if not chunks:
                # No summary yet (doc indexed before this feature) — fall back to full scan
                from app.retrieval.semantic import scroll_all_chunks
                chunks = scroll_all_chunks()

        elif query_type == "FULL_SCAN":
            # Scroll every content chunk in reading order — needed for listing
            from app.retrieval.semantic import scroll_all_chunks
            chunks = scroll_all_chunks()

        else:  # DOCUMENT_QUERY
            from app.retrieval.reranker import full_retrieval_pipeline
            # Increase top_n for broader coverage on targeted queries
            chunks = full_retrieval_pipeline(query, top_n=6)

        return {**state, "retrieved_chunks": chunks}

    except Exception as e:
        return {**state, "retrieved_chunks": [], "error": f"Retrieval failed: {e}"}


# ── Node 4: Route Reasoning ───────────────────────────────────────────────────

def route_reasoning(state: RAGState) -> RAGState:
    """
    Route to: direct_respond, generate, or map_reduce_generate.
      CONVERSATIONAL / OUT_OF_SCOPE → direct
      OVERVIEW / FULL_SCAN          → multi_doc (map-reduce over all chunks)
      DOCUMENT_QUERY                → single_doc (few chunks) or multi_doc (many docs)
    """
    query_type = state.get("query_type", "DOCUMENT_QUERY")
    chunks = state.get("retrieved_chunks", [])

    if query_type in ("CONVERSATIONAL", "OUT_OF_SCOPE", "AMBIGUOUS"):
        mode = "direct"
    elif query_type in ("OVERVIEW", "FULL_SCAN"):
        mode = "multi_doc"
    else:
        unique_docs = {c["metadata"].get("doc_id", "") for c in chunks}
        mode = "multi_doc" if len(unique_docs) >= MULTI_DOC_THRESHOLD else "single_doc"

    return {**state, "reasoning_mode": mode}


# ── Node 5: Direct Response (no retrieval) ────────────────────────────────────

def direct_respond(state: RAGState) -> RAGState:
    """
    Handle CONVERSATIONAL and OUT_OF_SCOPE queries without retrieval.
    """
    query_type = state.get("query_type", "DOCUMENT_QUERY")
    query = state.get("rewritten_query") or state["query"]

    if query_type == "CONVERSATIONAL":
        system = SystemMessage(content=(
            "You are an Enterprise Knowledge Assistant. "
            "Respond warmly and briefly to greetings and chitchat. "
            "Let the user know you're here to answer questions about their uploaded documents. "
            "Do not make up information. Keep it to 1-2 sentences."
        ))
    elif query_type == "AMBIGUOUS":
        # Use chat history to ask a targeted clarifying question
        history = state.get("chat_history", [])
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in history[-4:]
        ) if history else "No prior conversation."
        system = SystemMessage(content=(
            "You are an Enterprise Knowledge Assistant. "
            "The user's query is too vague to answer accurately. "
            "Based on the conversation history, ask ONE specific clarifying question "
            "to understand what they need. Be concise and friendly. "
            "Do not guess or make assumptions about what they want."
        ))
        query = (
            f"Conversation so far:\n{history_text}\n\n"
            f"Vague query: {query}\n\n"
            f"Ask a targeted clarifying question:"
        )
    else:  # OUT_OF_SCOPE
        system = SystemMessage(content=(
            "You are an Enterprise Knowledge Assistant. "
            "Your role is strictly to answer questions based on uploaded documents. "
            "The user has asked something outside that scope. "
            "Politely explain you can only help with questions about the uploaded knowledge base. "
            "Do not answer the out-of-scope question. Keep it to 1-2 sentences."
        ))

    try:
        llm = _get_llm()
        result = _llm_invoke([system, HumanMessage(content=query)])
        answer = result.content.strip()
    except Exception as e:
        if query_type == "CONVERSATIONAL":
            answer = "Hello! I'm your Enterprise Knowledge Assistant. Ask me anything about your uploaded documents."
        else:
            answer = "I can only answer questions based on the documents in your knowledge base. This question is outside my scope."

    return {**state, "answer": answer, "sources": [], "confidence": 1.0}


# ── Strict generation system prompt ──────────────────────────────────────────

_STRICT_SYSTEM = """\
You are an Enterprise Knowledge Assistant. Your job is to answer questions
using ONLY the provided document context below.

STRICT RULES — follow these without exception:
1. Base your answer EXCLUSIVELY on the provided context. Do not use outside knowledge.
2. If the context does not contain enough information to answer fully, say exactly:
   "The uploaded documents do not contain enough information to answer this fully."
3. If someone provides a reason or argument and asks for information beyond the context
   (e.g., "I have XYZ situation, can I get extra leaves?"), do NOT extrapolate.
   Instead say: "Based on the documents, I can only confirm what is stated:
   [quote the relevant policy]. For exceptions beyond this, please check with the
   relevant authority."
4. Do not guess, infer, or hallucinate. Only state what is explicitly in the context.
5. Cite sources by filename and page number.
"""


# ── Node 6: Direct Generation (single-doc) ───────────────────────────────────

def generate(state: RAGState) -> RAGState:
    """Strictly grounded single-doc generation."""
    llm = _get_llm()
    query = state.get("rewritten_query") or state["query"]
    chunks = state.get("retrieved_chunks", [])

    if not chunks:
        return {
            **state,
            "answer": "I could not find relevant information in the knowledge base to answer your question.",
            "sources": [],
            "confidence": 0.0,
        }

    context = "\n\n---\n\n".join(
        f"[Source: {c['metadata'].get('filename', 'Unknown')}, "
        f"Page: {c['metadata'].get('page', 'N/A')}]\n{c['text']}"
        for c in chunks
    )

    messages = _format_history(state.get("chat_history", []))
    messages.append(HumanMessage(content=f"Context:\n{context}\n\nQuestion: {query}"))

    try:
        result = _llm_invoke([SystemMessage(content=_STRICT_SYSTEM)] + messages)
        answer = result.content.strip()
    except Exception as e:
        answer = f"Generation failed: {e}"

    avg_confidence = round(
        sum(c.get("confidence", 0.5) for c in chunks) / len(chunks), 4
    )
    sources = [
        {
            "filename": c["metadata"].get("filename"),
            "page": c["metadata"].get("page"),
            "chunk_id": c["metadata"].get("chunk_id") or "",
            "confidence": c.get("confidence", 0.0),
        }
        for c in chunks
    ]
    return {**state, "answer": answer, "sources": sources, "confidence": avg_confidence}


# ── Node 7: Map-Reduce Generation ────────────────────────────────────────────

def map_reduce_generate(state: RAGState) -> RAGState:
    """
    Multi-doc / aggregation path: map each chunk independently, then reduce.
    For aggregation, the summary chunks are already compact so map is lightweight.
    """
    llm = _get_llm()
    query = state.get("rewritten_query") or state["query"]
    chunks = state.get("retrieved_chunks", [])

    if not chunks:
        return {
            **state,
            "answer": "I could not find relevant information in the knowledge base to answer your question.",
            "sources": [],
            "confidence": 0.0,
        }

    # MAP
    summaries = []
    for chunk in chunks:
        map_prompt = [
            SystemMessage(content=(
                "You are a document analyst. Extract ONLY the information from this excerpt "
                "that is directly relevant to the question. "
                "If not relevant, reply with exactly: NOT_RELEVANT"
            )),
            HumanMessage(content=(
                f"Question: {query}\n\n"
                f"Excerpt from {chunk['metadata'].get('filename', 'document')} "
                f"(page {chunk['metadata'].get('page', 'N/A')}):\n{chunk['text']}\n\n"
                f"Relevant information:"
            )),
        ]
        try:
            result = _llm_invoke(map_prompt)
            summary = result.content.strip()
        except Exception:
            summary = chunk["text"][:300]

        if summary.upper() != "NOT_RELEVANT":
            summaries.append({
                "summary": summary,
                "filename": chunk["metadata"].get("filename"),
                "page": chunk["metadata"].get("page"),
            })

    if not summaries:
        return {
            **state,
            "answer": "The uploaded documents do not contain enough information to answer this question.",
            "sources": [],
            "confidence": 0.0,
        }

    # REDUCE
    combined = "\n\n".join(
        f"[{s['filename']}, p.{s['page']}]: {s['summary']}" for s in summaries
    )

    reduce_messages = [
        SystemMessage(content=(
            _STRICT_SYSTEM + "\n\n"
            "You are synthesizing information from document summaries. "
            "Answer the question completely and accurately based ONLY on these summaries."
        )),
        HumanMessage(content=f"Document summaries:\n{combined}\n\nQuestion: {query}\n\nAnswer:"),
    ]

    try:
        result = _llm_invoke(reduce_messages)
        answer = result.content.strip()
    except Exception as e:
        answer = f"Synthesis failed: {e}"

    avg_confidence = round(
        sum(c.get("confidence", 0.5) for c in chunks) / len(chunks), 4
    )
    sources = [
        {
            "filename": c["metadata"].get("filename"),
            "page": c["metadata"].get("page"),
            "chunk_id": c["metadata"].get("chunk_id") or "",
            "confidence": c.get("confidence", 0.0),
        }
        for c in chunks
    ]
    return {**state, "answer": answer, "sources": sources, "confidence": avg_confidence}


# ── Node 8: Update Memory ─────────────────────────────────────────────────────

def update_memory(state: RAGState) -> RAGState:
    history = list(state.get("chat_history", []))
    history.append({"role": "user", "content": state["query"]})
    history.append({"role": "assistant", "content": state.get("answer", "")})

    max_messages = MEMORY_WINDOW * 2
    if len(history) > max_messages:
        history = history[-max_messages:]

    return {**state, "chat_history": history}
