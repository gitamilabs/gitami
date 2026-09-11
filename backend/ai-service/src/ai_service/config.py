from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    # ── Selector keys ─────────────────────────────────────────────────────────
    # LLM_PROVIDER: ollama | gemini | groq
    llm_provider: str = "ollama"
    # VECTOR_DB: chroma_local | chroma_cloud | qdrant | pinecone | supabase | memory
    vector_db: str = "chroma_cloud"
    # EMBEDDER: gemini | openai | fastembed | ollama
    embedder: str = "gemini"

    # ── Ollama Local LLM ──────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:32b"
    ollama_timeout: float = 60.0
    ollama_embedding_model: str = "nomic-embed-text"

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

    # ── Joern CPG Sidecar ─────────────────────────────────────────────────────
    joern_url: str = "http://localhost:8088"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
