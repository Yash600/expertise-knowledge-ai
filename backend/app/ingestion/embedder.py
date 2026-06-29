"""
embedder.py — Generate embeddings with BAAI/bge-small-en-v1.5 and upsert to Qdrant.

Uses fastembed (ONNX Runtime) instead of sentence-transformers/torch.
- ~80 MB RAM vs ~350 MB for torch — fits Render free tier (512 MB)
- Same BGE model weights, identical 384-dim output vectors
- Batches embeddings in groups of 64 to stay within memory limits.
"""

from __future__ import annotations

import os
import uuid
from typing import List, Dict, Any

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    PayloadSchemaType,
)

load_dotenv()

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIMENSION", "384"))
COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "enterprise_docs")
BATCH_SIZE = 64

# ── Singletons (lazy init) ────────────────────────────────────────────────────
_model = None
_client: QdrantClient | None = None


def get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        print(f"  Loading embedding model (fastembed): {EMBEDDING_MODEL}")
        _model = TextEmbedding(model_name=EMBEDDING_MODEL)
    return _model


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        url = os.getenv("QDRANT_URL")
        api_key = os.getenv("QDRANT_API_KEY")
        _client = QdrantClient(url=url, api_key=api_key)
    return _client


def _embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of texts, returning list of float vectors."""
    model = get_model()
    return [vec.tolist() for vec in model.embed(texts)]


def ensure_collection() -> None:
    """Create Qdrant collection if it doesn't exist."""
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        client.create_payload_index(COLLECTION, "filename", PayloadSchemaType.KEYWORD)
        client.create_payload_index(COLLECTION, "doc_id", PayloadSchemaType.KEYWORD)
        client.create_payload_index(COLLECTION, "page", PayloadSchemaType.INTEGER)
        print(f"  Created Qdrant collection: {COLLECTION}")
    else:
        print(f"  Qdrant collection exists: {COLLECTION}")


def embed_summary(doc_id: str, filename: str, summary_text: str) -> None:
    """Embed and upsert a single document-level summary chunk."""
    client = get_client()
    ensure_collection()

    # BGE retrieval prefix
    prefixed = f"Represent this document for retrieval: {summary_text}"
    vector = _embed_texts([prefixed])[0]

    summary_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"summary:{doc_id}"))
    point_id = str(uuid.UUID(summary_id))

    point = PointStruct(
        id=point_id,
        vector=vector,
        payload={
            "text": summary_text,
            "doc_id": doc_id,
            "filename": filename,
            "chunk_type": "summary",
            "page": 0,
        },
    )
    client.upsert(collection_name=COLLECTION, points=[point])
    print(f"  Summary chunk stored for {filename}")


def embed_and_upsert(chunks: List[Dict[str, Any]]) -> int:
    """Embed chunks and upsert to Qdrant. Returns total points upserted."""
    if not chunks:
        return 0

    client = get_client()
    ensure_collection()

    texts = [c["text"] for c in chunks]
    total = 0

    for i in range(0, len(texts), BATCH_SIZE):
        batch_chunks = chunks[i: i + BATCH_SIZE]
        batch_texts = texts[i: i + BATCH_SIZE]

        prefixed = [f"Represent this document for retrieval: {t}" for t in batch_texts]
        vectors = _embed_texts(prefixed)

        points = [
            PointStruct(
                id=chunk["metadata"]["chunk_id"],
                vector=vec,
                payload={
                    "text": chunk["text"],
                    **chunk["metadata"],
                },
            )
            for chunk, vec in zip(batch_chunks, vectors)
        ]

        client.upsert(collection_name=COLLECTION, points=points)
        total += len(points)
        print(f"  Upserted batch {i // BATCH_SIZE + 1}: {len(points)} chunks")

    return total


def delete_document(doc_id: str) -> int:
    """Remove all chunks belonging to a document from Qdrant."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    client = get_client()
    result = client.delete(
        collection_name=COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        ),
    )
    return result.status
