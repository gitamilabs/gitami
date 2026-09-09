import pytest
from pathlib import Path
from unittest.mock import AsyncMock
from src.indexer.pipeline import RepositoryIndexer
from src.indexer.contracts import IndexJobStatus, IndexStateStatus

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.mark.asyncio
async def test_pipeline_python_sample_fixture():
    mock_client = AsyncMock()
    mock_client.execute_query.return_value = []

    indexer = RepositoryIndexer(graph_client=mock_client)
    job, state, report = await indexer.run(
        repo_dir=FIXTURES_DIR / "python_sample",
        repo_id="test_org/py_sample",
        target_commit_sha="HEAD",
        branch="main",
        project_id="project_alpha",
    )

    assert job.status == IndexJobStatus.COMPLETED
    assert job.stage == "COMPLETED"
    assert job.progress == 95 or job.progress == 100
    assert state.status == IndexStateStatus.READY
    assert state.repository_id == "test_org/py_sample"
    assert report.is_valid is True
    assert job.stats.files_discovered >= 3
    assert job.stats.entities_created >= 3


@pytest.mark.asyncio
async def test_pipeline_mern_sample_fixture():
    mock_client = AsyncMock()
    mock_client.execute_query.return_value = []

    indexer = RepositoryIndexer(graph_client=mock_client)
    job, state, report = await indexer.run(
        repo_dir=FIXTURES_DIR / "mern_sample",
        repo_id="test_org/mern_sample",
        target_commit_sha="HEAD",
        branch="main",
    )

    assert job.status == IndexJobStatus.COMPLETED
    assert state.status == IndexStateStatus.READY
    assert report.is_valid is True
    assert job.stats.files_parsed >= 3


@pytest.mark.asyncio
async def test_pipeline_idempotent_reindexing():
    """Verify that running indexer twice on the exact same commit produces identical metrics."""
    mock_client = AsyncMock()
    mock_client.execute_query.return_value = []

    indexer = RepositoryIndexer(graph_client=mock_client)
    job1, state1, report1 = await indexer.run(
        repo_dir=FIXTURES_DIR / "python_sample",
        repo_id="test_org/py_sample",
        target_commit_sha="HEAD",
    )

    job2, state2, report2 = await indexer.run(
        repo_dir=FIXTURES_DIR / "python_sample",
        repo_id="test_org/py_sample",
        target_commit_sha="HEAD",
    )

    assert job1.stats.files_discovered == job2.stats.files_discovered
    assert job1.stats.files_parsed == job2.stats.files_parsed
    assert job1.stats.entities_created == job2.stats.entities_created
    assert state1.status == state2.status == IndexStateStatus.READY
