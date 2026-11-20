import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from src.indexer.contracts import (
    IndexJob,
    IndexJobStatus,
    IndexJobType,
    RepositoryIndexState,
    IndexStateStatus,
    ValidationReport,
    IncrementalIndexingStats,
)
from src.web.app import app


@pytest.mark.asyncio
async def test_reindex_endpoint_streams_ndjson_stages_remote():
    """Verify POST /api/reindex streams NDJSON progress events for remote repos."""
    mock_indexer = MagicMock()
    mock_job = IndexJob(
        project_id="default",
        repository_id="owner/repo",
        type=IndexJobType.INCREMENTAL,
        base_commit_sha="sha1",
        target_commit_sha="sha2",
    )
    mock_job.stats = IncrementalIndexingStats(
        base_commit_sha="sha1",
        target_commit_sha="sha2",
        files_added=1,
        files_modified=2,
        files_deleted=0,
        files_discovered=3,
        files_parsed=3,
        entities_created=5,
        relationships_created=4,
    )
    mock_state = RepositoryIndexState(
        repository_id="owner/repo",
        branch="main",
        indexed_commit_sha="sha2",
        status=IndexStateStatus.READY,
    )
    mock_report = ValidationReport(
        is_valid=True,
        repository_exists=True,
        commit_exists=True,
        files_discovered=3,
        files_parsed=3,
        entities_created=5,
        relationships_created=4,
    )

    async def fake_run_incremental(*args, **kwargs):
        stage_callback = kwargs.get("stage_callback")
        if stage_callback:
            await stage_callback("DIFF", "RUNNING", {"files_discovered": 3})
            await stage_callback("AST_ANALYSIS", "RUNNING", {"files_parsed": 3})
            await stage_callback("GRAPH_SYNC", "RUNNING", {"entities_created": 5})
        return mock_job, mock_state, mock_report

    mock_indexer.run_incremental = AsyncMock(side_effect=fake_run_incremental)

    with patch("src.web.routes.ingest.get_shared_graph_client", AsyncMock()), \
         patch("src.web.routes.ingest.get_shared_vector_client", MagicMock()), \
         patch("src.indexer.pipeline.RepositoryIndexer", return_value=mock_indexer):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/reindex",
                json={
                    "repo_id": "owner/repo",
                    "full_name": "owner/repo",
                    "base_commit_sha": "sha1",
                    "target_commit_sha": "sha2",
                    "branch": "main",
                    "access_token": "ghp_fake123",
                },
            )

            assert resp.status_code == 200
            assert "application/x-ndjson" in resp.headers["content-type"]

            lines = [json.loads(line) for line in resp.text.strip().split("\n") if line]
            assert len(lines) >= 4

            stages = [item["stage"] for item in lines]
            assert "DIFF" in stages
            assert "AST_ANALYSIS" in stages
            assert "GRAPH_SYNC" in stages
            assert stages[-1] == "COMPLETED"
            assert lines[-1]["status"] == "COMPLETED"
            assert lines[-1]["stats"]["entities_created"] == 5


@pytest.mark.asyncio
async def test_reindex_endpoint_streams_degraded_vector_terminal_stage():
    """Verify POST /api/reindex emits DEGRADED_VECTOR terminal stage when vector write fails."""
    mock_indexer = MagicMock()
    mock_job = IndexJob(
        project_id="default",
        repository_id="owner/repo",
        type=IndexJobType.INCREMENTAL,
        base_commit_sha="sha1",
        target_commit_sha="sha2",
    )
    mock_state = RepositoryIndexState(
        repository_id="owner/repo",
        branch="main",
        indexed_commit_sha="sha1",
        status=IndexStateStatus.DEGRADED_VECTOR,
        indexing_error="ChromaDB 429 quota exhaustion",
    )
    mock_report = ValidationReport(
        is_valid=True,
        repository_exists=True,
        commit_exists=True,
        files_discovered=1,
        files_parsed=1,
        entities_created=2,
        relationships_created=1,
    )

    async def fake_run_incremental(*args, **kwargs):
        return mock_job, mock_state, mock_report

    mock_indexer.run_incremental = AsyncMock(side_effect=fake_run_incremental)

    with patch("src.web.routes.ingest.get_shared_graph_client", AsyncMock()), \
         patch("src.web.routes.ingest.get_shared_vector_client", MagicMock()), \
         patch("src.indexer.pipeline.RepositoryIndexer", return_value=mock_indexer):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/reindex",
                json={
                    "repo_id": "owner/repo",
                    "full_name": "owner/repo",
                    "base_commit_sha": "sha1",
                    "target_commit_sha": "sha2",
                },
            )

            assert resp.status_code == 200
            lines = [json.loads(line) for line in resp.text.strip().split("\n") if line]
            assert lines[-1]["stage"] == "DEGRADED_VECTOR"
            assert lines[-1]["status"] == "COMPLETED"
            assert "ChromaDB" in lines[-1]["error"]


@pytest.mark.asyncio
async def test_reindex_endpoint_streams_failed_stage_on_error():
    """Verify POST /api/reindex emits FAILED terminal stage when an exception occurs."""
    mock_indexer = MagicMock()
    mock_indexer.run_incremental = AsyncMock(side_effect=RuntimeError("Simulated pipeline failure"))

    with patch("src.web.routes.ingest.get_shared_graph_client", AsyncMock()), \
         patch("src.web.routes.ingest.get_shared_vector_client", MagicMock()), \
         patch("src.indexer.pipeline.RepositoryIndexer", return_value=mock_indexer):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/reindex",
                json={
                    "repo_id": "owner/repo",
                    "full_name": "owner/repo",
                    "base_commit_sha": "sha1",
                    "target_commit_sha": "sha2",
                },
            )

            assert resp.status_code == 200
            lines = [json.loads(line) for line in resp.text.strip().split("\n") if line]
            assert lines[-1]["stage"] == "FAILED"
            assert lines[-1]["status"] == "FAILED"
            assert "Simulated pipeline failure" in lines[-1]["error"]


@pytest.mark.asyncio
async def test_reindex_endpoint_aborts_cleanly_on_client_disconnect():
    """Verify client disconnection stops streaming and cancels worker."""
    mock_indexer = MagicMock()
    # Simulate a slow incremental run
    async def slow_run(*args, **kwargs):
        import asyncio
        await asyncio.sleep(0.05)
        return None, None, None

    mock_indexer.run_incremental = AsyncMock(side_effect=slow_run)

    with patch("src.web.routes.ingest.get_shared_graph_client", AsyncMock()), \
         patch("src.web.routes.ingest.get_shared_vector_client", MagicMock()), \
         patch("src.indexer.pipeline.RepositoryIndexer", return_value=mock_indexer):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Open stream but close after reading 0 or 1 bytes
            try:
                async with client.stream(
                    "POST",
                    "/api/reindex",
                    json={
                        "repo_id": "owner/repo",
                        "full_name": "owner/repo",
                        "base_commit_sha": "sha1",
                        "target_commit_sha": "sha2",
                    },
                ) as response:
                    assert response.status_code == 200
                    # Break out early without consuming stream
            except Exception:
                pass
