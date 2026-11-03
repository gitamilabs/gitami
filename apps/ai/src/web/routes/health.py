from fastapi import APIRouter

from src.agents.llm_client import GEMINI_MODELS, GROQ_MODELS, LOCAL_MODELS
from src.config import settings

router = APIRouter(tags=["health"])


@router.get("/api/health")
@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "ai-service-kb"}


@router.get("/api/config")
async def get_system_config():
    """Get active system configuration including Vector DB, Embedder, and Model lists."""
    orch_model = (
        f"local/{settings.local_orchestrator_model}"
        if settings.orchestrator_provider == "local"
        else (GEMINI_MODELS[0] if GEMINI_MODELS else "gemini-3.6-flash")
    )
    worker_model = (
        f"local/{settings.local_worker_model}"
        if settings.worker_provider == "local"
        else (GROQ_MODELS[0] if GROQ_MODELS else "openai/gpt-oss-120b")
    )

    return {
        "vector_db": settings.vector_db,
        "embedder": settings.embedder,
        "models": {
            "gemini_models": GEMINI_MODELS,
            "groq_models": GROQ_MODELS,
            "local_models": LOCAL_MODELS,
            "primary_orchestrator": orch_model,
            "worker_model": worker_model,
            "orchestrator_provider": settings.orchestrator_provider,
            "worker_provider": settings.worker_provider,
        },
        "local_llm": {
            "url": settings.local_llm_url,
            "orchestrator_model": settings.local_orchestrator_model,
            "worker_model": settings.local_worker_model,
            "orchestrator_provider": settings.orchestrator_provider,
            "worker_provider": settings.worker_provider,
            "has_local_llm": bool(settings.local_llm_url),
        },
        "storage": {
            "qdrant_collection": settings.qdrant_collection,
            "pinecone_index": settings.pinecone_index,
            "supabase_table": settings.supabase_table,
            "chroma_persist_dir": settings.chroma_persist_dir,
        },
        "chroma_tenant": settings.chroma_tenant,
        "chroma_database": settings.chroma_database,
        "chroma_batch_size": settings.chroma_batch_size,
        "gemini_embedding_model": settings.gemini_embedding_model,
        "fastembed_model": settings.fastembed_model,
        "neo4j_uri": settings.neo4j_uri,
        "neo4j_user": settings.neo4j_user,
        "neo4j_database": settings.neo4j_database,
        "has_gemini_api_key": bool(settings.gemini_api_key),
        "has_groq_api_key": bool(settings.groq_api_key),
        "has_local_llm": bool(settings.local_llm_url),
    }
