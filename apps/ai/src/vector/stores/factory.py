"""Factory: resolve VECTOR_DB env key -> concrete BaseVectorStore instance."""
import logging

from src.vector.stores.chroma_store import ChromaStore
from src.vector.stores.qdrant_store import QdrantStore
from src.vector.stores.pinecone_store import PineconeStore
from src.vector.stores.supabase_store import SupabaseStore
from src.vector.stores.memory_store import MemoryStore

logger = logging.getLogger(__name__)

_VALID_STORES = ("chroma_local", "chroma_cloud", "qdrant", "pinecone", "supabase", "memory")


def get_vector_store(settings, embedder):
    """
    Return the appropriate vector store based on settings.vector_db.

    Valid values for VECTOR_DB:
        chroma_local  -- ChromaDB local persistent storage
        chroma_cloud  -- ChromaDB Cloud (requires CHROMA_API_KEY, CHROMA_TENANT, CHROMA_DATABASE)
        qdrant        -- Qdrant (requires QDRANT_URL, QDRANT_API_KEY)
        pinecone      -- Pinecone (requires PINECONE_API_KEY, PINECONE_INDEX)
        supabase      -- Supabase pgvector (requires SUPABASE_URL, SUPABASE_SERVICE_KEY)
        memory        -- In-memory store (for tests only, data is lost on restart)

    Raises:
        ValueError: if VECTOR_DB is not a recognised value.
    """
    key = settings.vector_db.lower().strip()
    logger.info("Initialising vector store: %s", key)

    match key:
        case "chroma_local" | "chroma_cloud":
            return ChromaStore(settings, embedder)
        case "qdrant":
            return QdrantStore(settings, embedder)
        case "pinecone":
            return PineconeStore(settings, embedder)
        case "supabase":
            return SupabaseStore(settings, embedder)
        case "memory":
            return MemoryStore(embedder)
        case _:
            raise ValueError(
                f"Unknown VECTOR_DB='{settings.vector_db}'. "
                f"Valid options: {', '.join(_VALID_STORES)}"
            )
