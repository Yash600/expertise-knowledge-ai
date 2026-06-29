from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM
    groq_api_key: str = ""

    # Qdrant
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "enterprise_docs"

    # Supabase / Postgres
    supabase_database_url: str = ""

    # Clerk
    clerk_secret_key: str = ""
    clerk_jwks_url: str = ""

    # Embedding & Reranker
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # RAG config
    chunk_size: int = 512
    chunk_overlap: int = 100
    retrieval_top_k: int = 10
    reranker_top_n: int = 3
    memory_window: int = 6
    multi_doc_threshold: int = 3

    # App
    environment: str = "development"
    allowed_origins: str = "http://localhost:3000"
    next_public_api_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
