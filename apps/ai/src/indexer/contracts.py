import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IndexJobType(str, Enum):
    INITIAL = "INITIAL"
    PUSH = "PUSH"
    MANUAL = "MANUAL"
    REINDEX = "REINDEX"


class IndexJobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class IndexStateStatus(str, Enum):
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    STALE = "STALE"
    FAILED = "FAILED"


# Valid state transitions for IndexJob
VALID_TRANSITIONS = {
    IndexJobStatus.QUEUED: {IndexJobStatus.RUNNING, IndexJobStatus.CANCELLED},
    IndexJobStatus.RUNNING: {IndexJobStatus.COMPLETED, IndexJobStatus.FAILED, IndexJobStatus.CANCELLED},
    IndexJobStatus.COMPLETED: set(),
    IndexJobStatus.FAILED: set(),
    IndexJobStatus.CANCELLED: set(),
}


class DiscoveredFile(BaseModel):
    """Metadata for a source file discovered in the repository snapshot."""
    file_path: str
    language: str
    size_bytes: int
    sha256: str


class IndexingStats(BaseModel):
    """Fine-grained statistics captured across the indexing pipeline."""
    files_discovered: int = 0
    files_parsed: int = 0
    files_skipped: int = 0
    parse_errors: int = 0
    entities_created: int = 0
    relationships_created: int = 0
    duration_seconds: float = 0.0
    details: Dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    """Validation outcome prior to marking index state as READY."""
    is_valid: bool
    repository_exists: bool
    commit_exists: bool
    files_discovered: int
    files_parsed: int
    entities_created: int
    relationships_created: int
    fatal_errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class IndexJob(BaseModel):
    """Canonical model for a repository indexing execution job."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = "default"
    repository_id: str
    type: IndexJobType = IndexJobType.INITIAL
    base_commit_sha: Optional[str] = None
    target_commit_sha: str
    branch: str = "main"
    status: IndexJobStatus = IndexJobStatus.QUEUED
    progress: int = 0
    stage: str = "PENDING"
    stats: IndexingStats = Field(default_factory=IndexingStats)
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def transition_to(self, new_status: IndexJobStatus, stage: Optional[str] = None, error: Optional[str] = None) -> None:
        """Validate and apply a status transition."""
        allowed = VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(f"Invalid IndexJob status transition from '{self.status.value}' to '{new_status.value}'")

        self.status = new_status
        if stage:
            self.stage = stage
        if error:
            self.error = error

        now = datetime.now(timezone.utc)
        if new_status == IndexJobStatus.RUNNING and not self.started_at:
            self.started_at = now
        elif new_status in (IndexJobStatus.COMPLETED, IndexJobStatus.FAILED, IndexJobStatus.CANCELLED):
            self.completed_at = now


class RepositoryIndexState(BaseModel):
    """Canonical state representation of an indexed repository branch."""
    repository_id: str
    branch: str = "main"
    indexed_commit_sha: str
    index_version: str = "v1"
    schema_version: str = "v1"
    parser_version: str = "1.0.0"
    status: IndexStateStatus = IndexStateStatus.INITIALIZING
    stats: Dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
