"""
summarizer.py — Generate a document-level summary chunk at ingestion time.

The summary is stored in Qdrant with metadata: { chunk_type: "summary", doc_id, filename }
It is used to answer aggregation queries (how many, list all, overview, etc.)
without scrolling every chunk.

Strategy: pass the first 300 chars of every page to Groq — enough to understand
structure without overflowing the context window.
"""

from __future__ import annotations

import os
from typing import List, Dict, Any

from dotenv import load_dotenv

load_dotenv()


def generate_document_summary(pages: List[Dict[str, Any]], filename: str) -> str | None:
    """
    Generate a concise factual summary of the document.

    Args:
        pages: List of page dicts from the loader (each has 'text' and 'metadata').
        filename: Original filename, used for context.

    Returns:
        Summary string, or None if generation fails.
    """
    if not pages:
        return None

    from langchain_groq import ChatGroq
    from langchain.schema import HumanMessage, SystemMessage

    # Take a 300-char snapshot of every page — covers structure without
    # overwhelming the LLM context window for large docs.
    page_snapshots = "\n".join(
        f"[Page {p['metadata'].get('page', i+1)}]: {p['text'][:300].replace(chr(10), ' ')}"
        for i, p in enumerate(pages)
    )

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
        max_tokens=600,
    )

    messages = [
        SystemMessage(content=(
            "You are a document analyst. Given page snippets from a document, "
            "produce a factual structural summary that covers:\n"
            "1. Document type and title (if present)\n"
            "2. All major sections and their names\n"
            "3. Exact item counts per section if the document contains numbered questions "
            "(e.g. 'Section 1: Q1–Q18 = 18 questions')\n"
            "4. Total number of questions/items (if applicable)\n"
            "5. Key topics and concepts covered\n\n"
            "Be precise. Count from the page snippets. Do NOT guess or extrapolate."
        )),
        HumanMessage(content=(
            f"Filename: {filename}\n"
            f"Total pages: {len(pages)}\n\n"
            f"Page snippets:\n{page_snapshots}\n\n"
            f"Write the factual structural summary:"
        )),
    ]

    try:
        result = llm.invoke(messages)
        summary = result.content.strip()
        print(f"  Summary generated for {filename} ({len(summary)} chars)")
        return summary
    except Exception as e:
        print(f"  Summary generation failed: {e}")
        return None
