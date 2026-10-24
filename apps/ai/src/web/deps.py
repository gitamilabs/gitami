from typing import Optional
from src.graph.client import Neo4jClient
from src.vector.client import VectorKBClient

_shared_graph_client: Optional[Neo4jClient] = None
_shared_vector_client: Optional[VectorKBClient] = None


async def get_shared_graph_client() -> Neo4jClient:
    """Provides a shared, long-lived Neo4jClient to avoid driver recreation overhead."""
    global _shared_graph_client
    if _shared_graph_client is None:
        _shared_graph_client = Neo4jClient()
        await _shared_graph_client.connect()
    return _shared_graph_client


def get_shared_vector_client() -> VectorKBClient:
    """Provides a shared VectorKBClient instance."""
    global _shared_vector_client
    if _shared_vector_client is None:
        _shared_vector_client = VectorKBClient()
    return _shared_vector_client


async def close_shared_clients() -> None:
    """Closes shared client connections during application shutdown."""
    global _shared_graph_client, _shared_vector_client
    if _shared_graph_client is not None:
        await _shared_graph_client.close()
        _shared_graph_client = None
    _shared_vector_client = None
