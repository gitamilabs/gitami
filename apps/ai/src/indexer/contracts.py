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
    INCREMENTAL = "INCREMENTAL"
    FULL_REINDEX = "FULL_REINDEX"


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
    IndexJobStatus.QUEUED: {IndexJobStatus.RUNNING, IndexJobStatus.FAILED, IndexJobStatus.CANCELLED},
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


class ChangedFileType(str, Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    RENAMED = "RENAMED"


class ChangedFile(BaseModel):
    """Represents a single changed file between two git commits."""
    path: str
    change_type: ChangedFileType
    old_path: Optional[str] = None
    language: str = "unknown"


class DiffResult(BaseModel):
    """Typed outcome of comparing a base commit and target commit."""
    base_commit_sha: str
    target_commit_sha: str
    is_ancestor: bool = True
    changed_files: List[ChangedFile] = Field(default_factory=list)
    change_percentage: float = 0.0
    is_safe_incremental: bool = True
    fallback_reason: Optional[str] = None

    @property
    def added(self) -> List[ChangedFile]:
        return [f for f in self.changed_files if f.change_type == ChangedFileType.ADDED]

    @property
    def modified(self) -> List[ChangedFile]:
        return [f for f in self.changed_files if f.change_type == ChangedFileType.MODIFIED]

    @property
    def deleted(self) -> List[ChangedFile]:
        return [f for f in self.changed_files if f.change_type == ChangedFileType.DELETED]

    @property
    def renamed(self) -> List[ChangedFile]:
        return [f for f in self.changed_files if f.change_type == ChangedFileType.RENAMED]


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


class IncrementalIndexingStats(IndexingStats):
    """Fine-grained statistics captured specifically during incremental indexing."""
    base_commit_sha: Optional[str] = None
    target_commit_sha: Optional[str] = None
    files_added: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    files_renamed: int = 0
    files_affected: int = 0
    entities_reconciled: int = 0
    relationships_reconciled: int = 0


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
    previous_commit_sha: Optional[str] = None
    index_version: str = "v1"
    schema_version: str = "v1"
    parser_version: str = "1.0.0"
    status: IndexStateStatus = IndexStateStatus.INITIALIZING
    generation: int = 1
    stats: Dict[str, Any] = Field(default_factory=dict)
    indexing_error: Optional[str] = None
    last_successful_index_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def advance_to(
        self,
        new_commit_sha: str,
        stats: Optional[Dict[str, Any]] = None,
        schema_version: str = "v1",
        parser_version: str = "1.0.0",
    ) -> None:
        """Atomically roll forward repository state to new target commit."""
        now = datetime.now(timezone.utc)
        self.previous_commit_sha = self.indexed_commit_sha
        self.indexed_commit_sha = new_commit_sha
        self.generation += 1
        self.schema_version = schema_version
        self.parser_version = parser_version
        self.status = IndexStateStatus.READY
        self.indexing_error = None
        self.last_successful_index_at = now
        self.updated_at = now
        if stats is not None:
            self.stats = stats

