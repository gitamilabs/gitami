"""Integration tests for VectorKBClient using VECTOR_DB=memory and mocked embedder."""
import os
import pytest
from unittest.mock import patch, MagicMock


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def use_memory_backend(monkeypatch):
    """Force VECTOR_DB=memory and EMBEDDER=gemini for all tests in this module."""
    monkeypatch.setenv("VECTOR_DB", "memory")
    monkeypatch.setenv("EMBEDDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


@pytest.fixture
def mock_gemini_embedder():
    """Return a mock GeminiEmbedder that produces deterministic 4-dim vectors."""
    mock = MagicMock()
    mock.dimension = 4
    mock.return_value = [[1.0, 0.0, 0.0, 0.0]]
    mock.side_effect = lambda input: [[float(i) for i in range(4)] for _ in input]
    return mock


@pytest.fixture
def client(mock_gemini_embedder):
    with (
        patch("src.vector.embedders.gemini_embedder.GeminiEmbedder.__init__", return_value=None),
        patch("src.vector.embedders.gemini_embedder.GeminiEmbedder.__call__", mock_gemini_embedder.side_effect),
        patch("src.vector.embedders.gemini_embedder.GeminiEmbedder.dimension", new=4, create=True),
    ):
        # Reload settings from env
        import importlib
        import src.config as cfg_module
        importlib.reload(cfg_module)

        from src.vector.client import VectorKBClient
        return VectorKBClient()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_client_instantiates_with_memory_backend(client):
    from src.vector.stores.memory_store import MemoryStore
    assert isinstance(client._store, MemoryStore)


def test_add_code_entry_and_query(client):
    client.add_code_entry(
        repo="test/repo",
        branch="main",
        file_path="src/app.py",
        symbol="main_func",
        signature="def main_func():",
        description="Entry point of the app.",
        commit_hash="abc123",
    )
    results = client.query(["main function"], n_results=1)
    assert len(results["documents"][0]) == 1
    assert "main_func" in results["documents"][0][0]


def test_add_code_entries_batch(client):
    entries = [
        {
            "repo": "r1", "branch": "main", "file_path": "a.py",
            "symbol": "foo", "signature": "def foo():", "description": "foo fn",
            "code_body": "", "commit_hash": "abc",
        },
        {
            "repo": "r1", "branch": "main", "file_path": "b.py",
            "symbol": "bar", "signature": "def bar():", "description": "bar fn",
            "code_body": "", "commit_hash": "abc",
        },
    ]
    client.add_code_entries_batch(entries)
    results = client.query(["function"], n_results=5)
    assert len(results["documents"][0]) == 2


def test_add_pr_entry(client):
    client.add_pr_entry(
        repo="r1", branch="main", pr_id="42",
        description_text="Refactor auth module.",
        commit_hash="def456",
    )
    results = client.query(["auth"], n_results=1)
    assert results["documents"][0][0] == "Refactor auth module."


def test_delete_helper(client):
    client.add_code_entry(
        repo="del-test", branch="main", file_path="x.py",
        symbol="x", signature="def x():", description="x fn",
        commit_hash="aaa",
    )
    client.delete(where={"repo": "del-test"})
    results = client.query(["x function"], n_results=5, where={"repo": "del-test"})
    assert results["documents"][0] == []


def test_delete_stale_entries(client):
    client.add_code_entry(
        repo="r1", branch="main", file_path="old.py",
        symbol="old_fn", signature="def old_fn():", description="old",
        commit_hash="old_hash",
    )
    client.add_code_entry(
        repo="r1", branch="main", file_path="new.py",
        symbol="new_fn", signature="def new_fn():", description="new",
        commit_hash="new_hash",
    )
    client.delete_stale_entries(repo="r1", branch="main", latest_commit_hash="new_hash")
    results = client.query(["function"], n_results=5)
    docs = results["documents"][0]
    assert any("new_fn" in d for d in docs)
    assert not any("old_fn" in d for d in docs)


def test_sanitize_document_size():
    from src.vector.client import _sanitize_document_size, MAX_DOCUMENT_BYTES

    # Small doc unaffected
    small = "def hello(): pass"
    assert _sanitize_document_size(small) == small

    # Massive doc truncated strictly to <= MAX_DOCUMENT_BYTES
    massive = "x" * (MAX_DOCUMENT_BYTES * 3)
    sanitized = _sanitize_document_size(massive)
    assert len(sanitized.encode("utf-8")) <= MAX_DOCUMENT_BYTES
    assert "... [truncated for vector index]" in sanitized


def test_oversized_code_body_is_truncated(client):
    from src.vector.client import MAX_DOCUMENT_BYTES

    huge_code = "print('hello world')\n" * 2000  # ~42,000 bytes
    client.add_code_entry(
        repo="huge-repo",
        branch="main",
        file_path="huge.py",
        symbol="HugeClass",
        signature="class HugeClass:",
        description="Huge class description",
        commit_hash="h123",
        code_body=huge_code,
    )
    results = client.query(["HugeClass"], n_results=1, where={"repo": "huge-repo"})
    assert len(results["documents"][0]) == 1
    doc = results["documents"][0][0]
    assert len(doc.encode("utf-8")) <= MAX_DOCUMENT_BYTES
    assert "[implementation truncated]" in doc or "[truncated for vector index]" in doc


@pytest.mark.asyncio
async def test_batch_upsert_arbitrary_records(client):
    records = [
        {"content": "API Documentation for users", "file_path": "docs/api.md", "name": "API Docs"},
        {"content": "Architecture Guide", "file_path": "docs/arch.md", "name": "Arch Guide"},
    ]
    res = await client.batch_upsert("doc-repo", records)
    assert res["total"] == 2
    assert res["successful"] == 2
    assert res["failed"] == 0

