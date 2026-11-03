import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_env_file = Path(__file__).resolve().parent.parent / ".env"
if "PYTEST_CURRENT_TEST" not in os.environ and _env_file.exists():
    load_dotenv(_env_file, override=True)


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    # ── Selector keys ─────────────────────────────────────────────────────────
    # VECTOR_DB: chroma_local | chroma_cloud | qdrant | pinecone | supabase | memory
    vector_db: str = "chroma_local"
    # EMBEDDER: gemini | openai | fastembed
    embedder: str = "fastembed"

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    chroma_persist_dir: str = "./chroma_db"
    chroma_api_key: str = ""
    chroma_tenant: str = ""
    chroma_database: str = ""
    chroma_batch_size: int = 40

    # ── Qdrant ────────────────────────────────────────────────────────────────
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "knowledge_base"
    qdrant_batch_size: int = 100

    # ── Pinecone ──────────────────────────────────────────────────────────────
    pinecone_api_key: str = ""
    pinecone_index: str = "knowledge-base"
    pinecone_environment: str = ""
    pinecone_batch_size: int = 100

    # ── Supabase pgvector ─────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_table: str = "knowledge_base"
    supabase_batch_size: int = 50

    # ── Gemini embedder ───────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_embedding_model: str = "models/gemini-embedding-001"

    # ── OpenAI embedder ───────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"

    # ── FastEmbed (local ONNX, ~130 MB, no GPU needed) ────────────────────────
    fastembed_model: str = "BAAI/bge-small-en-v1.5"

    # ── Neo4j ─────────────────────────────────────────────────────────────────
    neo4j_uri: str = ""
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    # ── Groq ──────────────────────────────────────────────────────────────────
    groq_api_key: str = ""

    # ── Local LLM (Ollama / vLLM / LM Studio / LocalAI / llama.cpp) ────────────
    # Endpoint compatible with OpenAI chat completions protocol
    local_llm_url: str = "https://deflate-monotype-ecosystem.ngrok-free.dev/v1"
    local_llm_api_key: str = "ollama"
    local_llm_timeout: float = 120.0
    local_orchestrator_model: str = "qwen2.5-coder:32b"
    local_worker_model: str = "qwen2.5-coder:32b"

    # Provider routing: "auto" | "local" | "gemini" | "groq"
    orchestrator_provider: str = "gemini"
    worker_provider: str = "local"

    model_config = SettingsConfigDict(
        env_file=(
            ".env",
            ".env.local",
            str(__import__("pathlib").Path(__file__).resolve().parent.parent / ".env"),
            str(__import__("pathlib").Path(__file__).resolve().parent.parent / ".env.local"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
