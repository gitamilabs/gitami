import pytest
from src.indexer.contracts import (
    IndexJob,
    IndexJobType,
    IndexJobStatus,
    RepositoryIndexState,
    IndexStateStatus,
    IndexingStats,
)


def test_index_job_creation():
    job = IndexJob(
        project_id="proj_123",
        repository_id="owner/repo",
        type=IndexJobType.INITIAL,
        target_commit_sha="abc1234567890",
        branch="main",
    )
    assert job.status == IndexJobStatus.QUEUED
    assert job.progress == 0
    assert job.stage == "PENDING"
    assert job.started_at is None
    assert job.completed_at is None


def test_valid_state_transitions():
    job = IndexJob(
        repository_id="owner/repo",
        target_commit_sha="abc1234567890",
    )
    # Transition to RUNNING
    job.transition_to(IndexJobStatus.RUNNING, stage="SNAPSHOT")
    assert job.status == IndexJobStatus.RUNNING
    assert job.stage == "SNAPSHOT"
    assert job.started_at is not None
    assert job.completed_at is None

    # Transition to COMPLETED
    job.transition_to(IndexJobStatus.COMPLETED, stage="COMPLETED")
    assert job.status == IndexJobStatus.COMPLETED
    assert job.completed_at is not None


def test_invalid_state_transitions():
    job = IndexJob(
        repository_id="owner/repo",
        target_commit_sha="abc1234567890",
    )
    # Cannot jump directly from QUEUED to COMPLETED
    with pytest.raises(ValueError, match="Invalid IndexJob status transition"):
        job.transition_to(IndexJobStatus.COMPLETED)

    # Move to RUNNING then FAILED
    job.transition_to(IndexJobStatus.RUNNING)
    job.transition_to(IndexJobStatus.FAILED, error="Connection timeout")
    assert job.status == IndexJobStatus.FAILED
    assert job.error == "Connection timeout"

    # Terminal state cannot transition anywhere
    with pytest.raises(ValueError, match="Invalid IndexJob status transition"):
        job.transition_to(IndexJobStatus.RUNNING)


def test_repository_index_state_creation():
    state = RepositoryIndexState(
        repository_id="owner/repo",
        branch="main",
        indexed_commit_sha="deadbeef12345678",
        status=IndexStateStatus.READY,
        stats={"entities_created": 42},
    )
    assert state.status == IndexStateStatus.READY
    assert state.index_version == "v1"
    assert state.schema_version == "v1"
    assert state.parser_version == "1.0.0"
    assert state.stats["entities_created"] == 42
