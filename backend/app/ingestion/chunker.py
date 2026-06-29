"""
chunker.py — Split page-level docs into overlapping chunks for RAG.

Strategy: LangChain RecursiveCharacterTextSplitter with tiktoken (cl100k_base)
for accurate token counting. Chunk size: 512 tokens, overlap: 100 tokens.

Each output chunk inherits metadata from its source page and adds:
    "chunk_index": int   (0-indexed within the source document)
    "chunk_id": str      (uuid4 — unique per chunk, used as Qdrant point ID)
"""

import uuid
from typing import List, Dict, Any

import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Shared tokenizer (cl100k_base used by GPT-3.5/4, close enough for counting)
_TOKENIZER = tiktoken.get_encoding("cl100k_base")


def _token_len(text: str) -> int:
    return len(_TOKENIZER.encode(text))


def build_splitter(chunk_size: int = 512, chunk_overlap: int = 100) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=_token_len,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=False,
    )


def chunk_documents(
    pages: List[Dict[str, Any]],
    chunk_size: int = 512,
    chunk_overlap: int = 100,
) -> List[Dict[str, Any]]:
    """
    Split a list of page dicts into smaller overlapping chunk dicts.
    Returns list of chunks with metadata preserved + chunk_id added.
    """
    splitter = build_splitter(chunk_size, chunk_overlap)
    chunks: List[Dict[str, Any]] = []
    doc_chunk_counters: Dict[str, int] = {}  # doc_id -> running index

    for page in pages:
        doc_id = page["metadata"]["doc_id"]
        texts = splitter.split_text(page["text"])

        for text in texts:
            if not text.strip():
                continue
            idx = doc_chunk_counters.get(doc_id, 0)
            doc_chunk_counters[doc_id] = idx + 1

            chunk = {
                "text": text,
                "metadata": {
                    **page["metadata"],
                    "chunk_index": idx,
                    "chunk_id": str(uuid.uuid4()),
                    "token_count": _token_len(text),
                }
            }
            chunks.append(chunk)

    return chunks
