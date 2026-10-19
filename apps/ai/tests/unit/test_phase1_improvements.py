import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from src.indexer.pipeline import RepositoryIndexer
from src.indexer.contracts import IndexJobType
from src.parsing.models import ParseResult, SymbolNode
from src.vector.stores.chroma_store import ChromaStore
from src.vector.stores.memory_store import MemoryStore
from src.web.app import app


@pytest.mark.asyncio
async def test_indexer_run_with_pre_parsed_results():
    """Verify RepositoryIndexer.run accepts pre-parsed results and indexes them without requiring repo_dir on disk."""
    mock_vector = MagicMock()
    mock_vector.add_code_entries_batch.return_value = {"total": 1, "successful": 1, "failed": 0}

    indexer = RepositoryIndexer(
        graph_client=None,
        vector_client=mock_vector,
    )

    meaningful_sym = SymbolNode(
        name="compute_total",
        qualified_name="compute_total",
        kind="function",
        language="python",
        file_path="src/billing.py",
        start_line=10,
        end_line=20,
        signature="def compute_total(items: list[Item]) -> float:",
        code_body="return sum(item.price * item.quantity for item in items)",
        docstring="Compute the aggregate bill amount including applicable line item rates.",
    )

    pr = ParseResult(
        file_path="src/billing.py",
        language="python",
        symbols=[meaningful_sym],
    )

    job, state, report = await indexer.run(
        repo_id="test-org/remote-repo",
        target_commit_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        branch="main",
        validate_only=True,
        parse_results=[pr],
    )

    assert report.is_valid is True
    assert job.target_commit_sha == "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    assert job.stats.files_parsed == 1
    assert job.stats.entities_created == 2  # 1 file + 1 symbol
    assert mock_vector.add_code_entries_batch.called
    added_entries = mock_vector.add_code_entries_batch.call_args[0][0]
    assert len(added_entries) == 1
    assert added_entries[0]["symbol"] == "compute_total"
    assert added_entries[0]["repo"] == "test-org/remote-repo"


@pytest.mark.asyncio
async def test_indexer_symbol_cleaner_drops_trivial_noise():
    """Verify trivial stubs, getters, and empty bodies are dropped from vector indexing to prevent DB flooding."""
    mock_vector = MagicMock()
    indexer = RepositoryIndexer(
        graph_client=None,
        vector_client=mock_vector,
    )

    trivial_stub = SymbolNode(
        name="get_id",
        qualified_name="Item.get_id",
        kind="method",
        language="python",
        file_path="src/item.py",
        start_line=1,
        end_line=2,
        signature="def get_id(self):",
        code_body="return self.id",
        docstring="",
    )

    meaningful_func = SymbolNode(
        name="process_order",
        qualified_name="process_order",
        kind="function",
        language="python",
        file_path="src/order.py",
        start_line=10,
        end_line=25,
        signature="def process_order(order_id: str, payment: Payment):",
        code_body="validated = validate_payment(payment)\nexecute_transaction(order_id, validated)\nsend_receipt(order_id)",
        docstring="Process incoming order against payment gateway and dispatch confirmation receipt.",
    )

    pr = ParseResult(
        file_path="src/order.py",
        language="python",
        symbols=[trivial_stub, meaningful_func],
    )

    await indexer.run(
        repo_id="test-org/clean-repo",
        target_commit_sha="c1c2c3c4",
        validate_only=True,
        parse_results=[pr],
    )

    assert mock_vector.add_code_entries_batch.called
    added_entries = mock_vector.add_code_entries_batch.call_args[0][0]
    # Only the meaningful symbol should be indexed into the vector DB
    indexed_names = [e["symbol"] for e in added_entries]
    assert "process_order" in indexed_names
    assert "get_id" not in indexed_names


def test_chroma_store_bounded_paging():
    """Verify ChromaStore pagination in get_distinct_repos and get(limit, offset)."""
    mock_settings = MagicMock()
    mock_settings.chroma_batch_size = 100
    mock_settings.chroma_api_key = None
    mock_settings.chroma_tenant = None
    mock_settings.chroma_database = None
    mock_settings.chroma_persist_dir = "./chroma_db"

    mock_embedder = MagicMock()
    mock_embedder.dimension = 384

    with patch("chromadb.PersistentClient") as mock_chroma:
        mock_col = MagicMock()
        mock_chroma.return_value.get_or_create_collection.return_value = mock_col
        mock_col.get.return_value = {"embeddings": []}

        store = ChromaStore(mock_settings, mock_embedder)

        # Test get with limit and offset
        store.get(where={"repo": "test/repo"}, limit=50, offset=10)
        mock_col.get.assert_called_with(where={"repo": "test/repo"}, limit=50, offset=10)

        # Test bounded paging in get_distinct_repos
        mock_col.get.side_effect = [
            {"metadatas": [{"repo": "repo-a"}, {"repo": "repo-b"}]},
            {"metadatas": []},
        ]
        repos = store.get_distinct_repos()
        assert repos == ["repo-a", "repo-b"]


def test_api_reindex_and_cleaned_webhooks():
    """Verify /api/reindex route exists and leaked webhook routes are removed."""
    client = TestClient(app)

    # 1. Old root webhook route is no longer accepting webhooks
    res_root = client.post("/", json={"action": "opened"})
    assert res_root.status_code in (404, 405)

    # 2. Old webhooks route is no longer present
    res_wh = client.post("/webhooks", json={"action": "opened"})
    assert res_wh.status_code in (404, 405)

    # 3. New /api/reindex route validates request
    res_reindex_bad = client.post("/api/reindex", json={})
    assert res_reindex_bad.status_code == 422  # validation error (missing repo_id)


@pytest.mark.asyncio
async def test_mcp_tool_retrieve_context():
    """Verify tool_retrieve_context connects ContextEngine and returns valid JSON response."""
    from src.mcp.tools import execute_tool_by_name

    mock_graph = AsyncMock()
    mock_vector = MagicMock()
    mock_vector.query.return_value = {"documents": [["def foo(): pass"]], "metadatas": [[{"file_path": "foo.py"}]]}

    res_json_str = await execute_tool_by_name(
        tool_name="retrieve_context",
        tool_args={"query": "where is foo", "max_items": 5},
        graph_client=mock_graph,
        vector_client=mock_vector,
        repo_id="test/repo",
        branch="main",
    )

    import json
    parsed = json.loads(res_json_str)
    assert "items" in parsed or "query" in parsed or "total_items" in parsed

