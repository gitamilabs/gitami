import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.indexer.contracts import (
    DiffResult,
    ChangedFile,
    ChangedFileType,
    IndexStateStatus,
    RepositoryIndexState,
)
from src.indexer.pipeline import RepositoryIndexer
from src.context.contracts import AuthorizedScope
from src.context.semantic_retriever import SemanticRetriever


@pytest.mark.asyncio
async def test_advances_commit_sha_only_when_both_graph_and_vector_succeed():
    """When both graph and vector succeed, index commit advances and status is READY."""
    mock_graph_client = AsyncMock()
    mock_vector_client = MagicMock()
    mock_differ = MagicMock()

    diff_res = DiffResult(
        base_commit_sha="sha1",
        target_commit_sha="sha2",
        is_ancestor=True,
        changed_files=[
            ChangedFile(path="src/main.py", change_type=ChangedFileType.MODIFIED)
        ],
        change_percentage=0.05,
        is_safe_incremental=True,
    )
    mock_differ.compute_diff.return_value = diff_res

    indexer = RepositoryIndexer(
        graph_client=mock_graph_client,
        vector_client=mock_vector_client,
        differ=mock_differ,
    )

    class MockSnapshot:
        def __init__(self, *args, **kwargs):
            self.resolved_commit_sha = "sha2"
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read_bytes(self, path):
            return b'def hello():\n    """Greet user with welcoming message."""\n    return "Welcome to Gitami!"\n'

    with patch("src.indexer.pipeline.RepositorySnapshot", MockSnapshot):
        job, state, report = await indexer.run_incremental(
            repo_dir="/mock/repo",
            repo_id="test-repo",
            target_commit_sha="sha2",
            base_commit_sha="sha1",
            branch="main",
        )

    assert state.status == IndexStateStatus.READY
    assert state.indexed_commit_sha == "sha2"
    assert mock_vector_client.add_code_entries_batch.called
    assert mock_vector_client.roll_forward_commit.called


@pytest.mark.asyncio
async def test_vector_failure_transitions_to_degraded_vector():
    """Fault injection: vector client raises HTTP 429 rate limit. State becomes DEGRADED_VECTOR."""
    mock_graph_client = AsyncMock()
    mock_vector_client = MagicMock()
    # Simulate HTTP 429 Too Many Requests
    mock_vector_client.add_code_entries_batch.side_effect = Exception("429 Client Error: Too Many Requests for url")

    mock_differ = MagicMock()
    diff_res = DiffResult(
        base_commit_sha="sha1",
        target_commit_sha="sha2",
        is_ancestor=True,
        changed_files=[
            ChangedFile(path="src/main.py", change_type=ChangedFileType.MODIFIED)
        ],
        change_percentage=0.05,
        is_safe_incremental=True,
    )
    mock_differ.compute_diff.return_value = diff_res

    indexer = RepositoryIndexer(
        graph_client=mock_graph_client,
        vector_client=mock_vector_client,
        differ=mock_differ,
    )

    class MockSnapshot:
        def __init__(self, *args, **kwargs):
            self.resolved_commit_sha = "sha2"
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read_bytes(self, path):
            return b'def hello():\n    """Greet user with welcoming message."""\n    return "Welcome to Gitami!"\n'

    with patch("src.indexer.pipeline.RepositorySnapshot", MockSnapshot):
        job, state, report = await indexer.run_incremental(
            repo_dir="/mock/repo",
            repo_id="test-repo",
            target_commit_sha="sha2",
            base_commit_sha="sha1",
            branch="main",
        )

    # Graph writes succeeded, but vector failed -> DEGRADED_VECTOR
    assert state.status == IndexStateStatus.DEGRADED_VECTOR
    assert state.indexed_commit_sha == "sha1"  # Not rolled forward yet
    assert state.pending_target_sha == "sha2"
    assert state.pending_vector_entries is not None
    assert len(state.pending_vector_entries) >= 1


@pytest.mark.asyncio
async def test_retry_pending_vectors_self_heals():
    """Asynchronous retry execution processes pending embeddings and transitions to READY."""
    mock_vector_client = MagicMock()
    indexer = RepositoryIndexer(vector_client=mock_vector_client)

    state = RepositoryIndexState(
        repository_id="test-repo",
        branch="main",
        indexed_commit_sha="sha1",
        status=IndexStateStatus.DEGRADED_VECTOR,
    )
    state.pending_target_sha = "sha2"
    state.pending_vector_entries = [
        {"repo": "test-repo", "file_path": "src/main.py", "symbol": "hello"}
    ]

    healed_state = await indexer.retry_pending_vectors(
        repo_id="test-repo",
        branch="main",
        current_state=state,
    )

    assert healed_state.status == IndexStateStatus.READY
    assert healed_state.indexed_commit_sha == "sha2"
    assert healed_state.pending_vector_entries is None
    assert mock_vector_client.add_code_entries_batch.called
    assert mock_vector_client.roll_forward_commit.called


@pytest.mark.asyncio
async def test_semantic_retriever_degrades_confidence_for_degraded_vector():
    """SemanticRetriever cuts confidence score in half when repository is in DEGRADED_VECTOR status."""
    mock_client = MagicMock()
    mock_client.query.return_value = {
        "documents": [["def foo(): return 1"]],
        "metadatas": [[{"repo": "test-repo", "symbol": "foo", "file_path": "foo.py"}]],
        "distances": [[0.2]],
        "ids": [["vec_1"]],
    }

    retriever = SemanticRetriever(mock_client)
    scope = AuthorizedScope(allowed_repo_ids=["test-repo"], project_id="default")

    # Regular retrieval
    items_normal = await retriever.retrieve(query="foo", scope=scope, repo_status=IndexStateStatus.READY)
    assert len(items_normal) == 1
    normal_score = items_normal[0].relevance_score

    # Degraded retrieval
    items_degraded = await retriever.retrieve(query="foo", scope=scope, repo_status=IndexStateStatus.DEGRADED_VECTOR)
    assert len(items_degraded) == 1
    degraded_score = items_degraded[0].relevance_score

    # Verify score is discounted
    assert degraded_score < normal_score
    assert items_degraded[0].metadata.get("degraded_vector") is True
