"""Unit tests for the vector store factory and in-memory store."""
import pytest
from unittest.mock import MagicMock


class MockEmbedder:
    dimension = 4

    def __call__(self, input):
        return [[float(i) for i in range(self.dimension)] for _ in input]


class MockSettings:
    vector_db = "memory"
    chroma_persist_dir = "./chroma_db"
    chroma_api_key = ""
    chroma_tenant = ""
    chroma_database = ""
    chroma_batch_size = 40
    qdrant_url = "http://localhost:6333"
    qdrant_api_key = ""
    qdrant_collection = "knowledge_base"
    qdrant_batch_size = 100
    pinecone_api_key = "pk-test"
    pinecone_index = "knowledge-base"
    pinecone_environment = "us-east-1"
    pinecone_batch_size = 100
    supabase_url = "https://test.supabase.co"
    supabase_service_key = "svc-key"
    supabase_table = "knowledge_base"
    supabase_batch_size = 50


def make_settings(vector_db="memory"):
    s = MockSettings()
    s.vector_db = vector_db
    return s


def test_factory_returns_memory_store():
    from src.vector.stores.memory_store import MemoryStore
    from src.vector.stores.factory import get_vector_store

    store = get_vector_store(make_settings("memory"), MockEmbedder())
    assert isinstance(store, MemoryStore)


def test_factory_raises_on_unknown_backend():
    from src.vector.stores.factory import get_vector_store

    with pytest.raises(ValueError, match="Unknown VECTOR_DB"):
        get_vector_store(make_settings("not_a_store"), MockEmbedder())


# ── In-memory store integration tests ────────────────────────────────────────

def make_memory_store():
    from src.vector.stores.memory_store import MemoryStore
    return MemoryStore(MockEmbedder())


def test_memory_upsert_and_query():
    store = make_memory_store()
    store.upsert(["id1"], ["hello world"], [{"repo": "r1", "branch": "main"}])
    results = store.query(["hello"], n_results=1)
    assert results["ids"][0] == ["id1"]
    assert results["documents"][0][0] == "hello world"


def test_memory_delete():
    store = make_memory_store()
    store.upsert(["id1", "id2"], ["doc a", "doc b"], [{"repo": "r1"}, {"repo": "r2"}])
    store.delete({"repo": "r1"})
    results = store.get({"repo": "r1"})
    assert results["ids"] == []


def test_memory_update():
    store = make_memory_store()
    store.upsert(["id1"], ["doc"], [{"commit_hash": "abc"}])
    store.update(["id1"], [{"commit_hash": "xyz"}])
    results = store.get({"commit_hash": "xyz"})
    assert "id1" in results["ids"]


def test_memory_where_and_filter():
    store = make_memory_store()
    store.upsert(
        ["id1", "id2"],
        ["doc a", "doc b"],
        [{"repo": "r1", "branch": "main"}, {"repo": "r1", "branch": "dev"}],
    )
    results = store.query(
        ["doc"],
        n_results=5,
        where={"$and": [{"repo": "r1"}, {"branch": "main"}]},
    )
    assert results["ids"][0] == ["id1"]


def test_memory_ne_filter():
    store = make_memory_store()
    store.upsert(
        ["id1", "id2"],
        ["doc a", "doc b"],
        [{"last_valid_commit": "old"}, {"last_valid_commit": "new"}],
    )
    results = store.get({"last_valid_commit": {"$ne": "new"}})
    assert results["ids"] == ["id1"]
