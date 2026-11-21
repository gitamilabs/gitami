"""Factory: resolve VECTOR_DB env key -> concrete BaseVectorStore instance."""
import logging

from src.vector.stores.chroma_store import ChromaStore
from src.vector.stores.memory_store import MemoryStore

logger = logging.getLogger(__name__)

_VALID_STORES = ("chroma_local", "chroma_cloud", "memory")


def get_vector_store(settings, embedder):
    """
    Return the appropriate vector store based on settings.vector_db.

    Valid values for VECTOR_DB:
        chroma_local  -- ChromaDB local persistent storage
        chroma_cloud  -- ChromaDB Cloud (requires CHROMA_API_KEY, CHROMA_TENANT, CHROMA_DATABASE)
        memory        -- In-memory store (for tests only, data is lost on restart)

    Raises:
        ValueError: if VECTOR_DB is not a recognised value.
    """
    key = settings.vector_db.lower().strip()
    logger.info("Initialising vector store: %s", key)

    match key:
        case "chroma_local" | "chroma_cloud":
            return ChromaStore(settings, embedder)
        case "memory":
            return MemoryStore(embedder)
        case _:
            raise ValueError(
                f"Unknown VECTOR_DB='{settings.vector_db}'. "
                f"Valid options: {', '.join(_VALID_STORES)}"
            )
