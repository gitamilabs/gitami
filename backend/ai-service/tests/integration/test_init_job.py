import pytest
from pathlib import Path
from unittest.mock import AsyncMock
from ai_service.jobs.init_job import run_init_job

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.mark.asyncio
async def test_run_init_job_python_sample():
    mock_client = AsyncMock()
    mock_client.execute_query.return_value = []

    res = await run_init_job(
        repo_id="py_sample_repo",
        branch="main",
        repo_dir=FIXTURES_DIR / "python_sample",
        client=mock_client,
    )

    assert res.status in ("SUCCESS", "CACHED")
    assert res.symbols_count >= 3
    assert res.duration_seconds >= 0.0


@pytest.mark.asyncio
async def test_run_init_job_mern_sample():
    mock_client = AsyncMock()
    mock_client.execute_query.return_value = []

    res = await run_init_job(
        repo_id="mern_sample_repo",
        branch="main",
        repo_dir=FIXTURES_DIR / "mern_sample",
        client=mock_client,
    )

    assert res.status in ("SUCCESS", "CACHED")
    assert res.symbols_count >= 3
    assert res.duration_seconds >= 0.0
