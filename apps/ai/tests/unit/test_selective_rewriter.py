import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.indexer.graph_indexer import GraphIndexer
from src.graph.writer import upsert_call_edges
from src.parsing.models import CallEdge, ParseResult, SymbolNode
from src.indexer.pipeline import RepositoryIndexer
from src.indexer.contracts import DiffResult, ChangedFile, ChangedFileType, IndexStateStatus


@pytest.mark.asyncio
async def test_find_affected_files_detects_incoming_callers():
    """Verify find_affected_files queries callers, importers, and dependents."""
    mock_client = AsyncMock()
    # Mock Neo4j execute_query returning caller file
    mock_client.execute_query.return_value = [
        {"affected_files": ["src/service.py", "src/client.ts"]}
    ]

    indexer = GraphIndexer(mock_client)
    affected = await indexer.find_affected_files("test-repo", ["src/math.py"])

    assert "src/service.py" in affected
    assert "src/client.ts" in affected
    assert mock_client.execute_query.called

    query, params = mock_client.execute_query.call_args[0]
    assert "MATCH (caller)-[:CALLS]->(s)" in query
    assert params["repo_id"] == "test-repo"
    assert params["changed_paths"] == ["src/math.py"]


@pytest.mark.asyncio
async def test_upsert_call_edges_scoped_to_local_or_imports():
    """Verify upsert_call_edges enforces scoping and eliminates false cross-file edges."""
    mock_client = AsyncMock()
    mock_client.execute_query.return_value = []

    calls = [
        CallEdge(
            caller_symbol="src/service.py::run",
            callee_name="calculate",
            file_path="src/service.py",
            line=10,
        )
    ]

    await upsert_call_edges(mock_client, repo_id="test-repo", branch="main", calls=calls)

    assert mock_client.execute_query.called
    query, params = mock_client.execute_query.call_args[0]

    # Verify callee is scoped to same file or imports
    assert "callee.file_path = caller.file_path" in query
    assert "IMPORTS" in query or "DEPENDS_ON_FILE" in query
    assert params["repo_id"] == "test-repo"
    assert params["branch"] == "main"


@pytest.mark.asyncio
async def test_callee_deletion_and_symbol_reconciliation_cleans_dangling_edges():
    """Verify delete_file_and_symbols and reconcile_file_symbols execute DETACH DELETE."""
    mock_client = AsyncMock()
    indexer = GraphIndexer(mock_client)

    # 1. Test delete_file_and_symbols
    await indexer.delete_file_and_symbols("test-repo", "src/old_module.py")
    assert mock_client.execute_query.called
    query_del, params_del = mock_client.execute_query.call_args[0]
    assert "DETACH DELETE f, s" in query_del
    assert params_del["file_path"] == "src/old_module.py"

    # 2. Test reconcile_file_symbols removes obsolete symbol
    mock_client.reset_mock()
    # Mock existing symbols
    mock_client.execute_query.side_effect = [
        [{"uid": "func:test-repo:src/math.py::old_func"}, {"uid": "func:test-repo:src/math.py::kept_func"}], # fetch
        [], # update file
        [], # delete stale
        [], # upsert active
    ]

    kept_sym = SymbolNode(
        name="kept_func",
        kind="function",
        file_path="src/math.py",
        language="python",
        start_line=1,
        end_line=5,
        signature="def kept_func()",
    )

    c, u, d = await indexer.reconcile_file_symbols(
        repo_id="test-repo",
        file_path="src/math.py",
        new_symbols=[kept_sym],
        commit_sha="sha222",
        branch="main",
    )

    assert d == 1  # 1 stale symbol deleted
    # Check delete query was DETACH DELETE
    del_calls = [c for c in mock_client.execute_query.call_args_list if "DETACH DELETE s" in c[0][0]]
    assert len(del_calls) == 1
    assert "func:test-repo:src/math.py::old_func" in del_calls[0][0][1]["stale_uids"]


@pytest.mark.asyncio
async def test_selective_caller_rewiring_does_not_touch_unrelated_files():
    """
    Synthetic multi-file test:
    math.py is modified.
    service.py calls math.py.
    unrelated.py has no dependency on math.py.
    Only math.py (modified) and service.py (affected caller) are read and parsed.
    """
    mock_graph_client = AsyncMock()
    mock_differ = MagicMock()

    # Differ reports only math.py modified
    diff_res = DiffResult(
        base_commit_sha="sha1",
        target_commit_sha="sha2",
        is_ancestor=True,
        changed_files=[
            ChangedFile(path="src/math.py", change_type=ChangedFileType.MODIFIED)
        ],
        change_percentage=0.05,
        is_safe_incremental=True,
    )
    mock_differ.compute_diff.return_value = diff_res

    # Mock GraphIndexer find_affected_files returns only service.py
    mock_graph_client.execute_query.side_effect = lambda query, params=None: (
        [{"affected_files": ["src/service.py"]}]
        if "MATCH (f:File" in query and "CALLS" in query
        else [
            {"paths": ["src/math.py", "src/service.py", "src/unrelated.py"]},
            {"names": ["calculate", "run", "unrelated_task"]},
            {"names": []},
        ] if "paths" in query or "names" in query
        else []
    )

    indexer = RepositoryIndexer(
        graph_client=mock_graph_client,
        differ=mock_differ,
    )

    # In-memory snapshot provider
    read_paths = []
    class MockSnapshot:
        def __init__(self, *args, **kwargs):
            self.resolved_commit_sha = "sha2"
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read_bytes(self, path):
            read_paths.append(path)
            if path == "src/math.py":
                return b"def calculate(): return 100\n"
            elif path == "src/service.py":
                return b"from src.math import calculate\ndef run(): return calculate()\n"
            elif path == "src/unrelated.py":
                return b"def unrelated_task(): pass\n"
            raise FileNotFoundError(path)

    with patch("src.indexer.pipeline.RepositorySnapshot", MockSnapshot):
        job, state, report = await indexer.run_incremental(
            repo_dir="/mock/repo",
            repo_id="test-repo",
            target_commit_sha="sha2",
            base_commit_sha="sha1",
            branch="main",
        )

    assert state.status == IndexStateStatus.READY
    # Crucial assertion: math.py (modified) and service.py (affected caller) were read.
    # unrelated.py was NEVER read!
    assert "src/math.py" in read_paths
    assert "src/service.py" in read_paths
    assert "src/unrelated.py" not in read_paths
