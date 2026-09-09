from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class ContextItemType(str, Enum):
    SYMBOL = "symbol"
    FILE = "file"
    CALL_GRAPH = "call_graph"
    DEPENDENCY = "dependency"
    HERITAGE = "heritage"
    TEST = "test"
    SEMANTIC_CODE = "semantic_code"
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    ISSUE = "issue"
    DOCUMENTATION = "documentation"


@dataclass
class ContextSource:
    """Authentic provenance for a context item. No fabricated fields."""
    kind: str  # "graph", "semantic", "source_code", "git_commit", "github_pr", "github_issue"
    repository_id: str
    file_path: Optional[str] = None
    entity_uid: Optional[str] = None
    commit_sha: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    issue_number: Optional[int] = None
    pr_number: Optional[int] = None
    confidence: float = 1.0


@dataclass
class ContextItem:
    """Single unit of structured evidence returned by Context Engine."""
    id: str
    type: ContextItemType
    title: str
    content: str
    relevance_score: float = 0.0
    source: ContextSource = field(default_factory=lambda: ContextSource(kind="unknown", repository_id=""))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthorizedScope:
    """Security boundary representing authorized project and repository access."""
    project_id: str
    allowed_repo_ids: Set[str]
    repo_paths: Dict[str, Path] = field(default_factory=dict)
    default_branch: str = "main"


@dataclass
class ContextBudget:
    max_items: int = 20
    max_tokens: int = 8000


@dataclass
class ContextRequest:
    project_id: str
    query: str
    repository_ids: List[str] = field(default_factory=list)
    branch: str = "main"
    commit_sha: Optional[str] = None
    max_items: int = 20
    max_tokens: int = 8000
    include_graph: bool = True
    include_semantic: bool = True
    include_source: bool = True
    include_github: bool = True
    hops: int = 1


@dataclass
class ProviderError:
    provider: str
    error: str
    recoverable: bool = True


@dataclass
class RetrievalMetadata:
    durations_ms: Dict[str, float] = field(default_factory=dict)
    candidates_per_provider: Dict[str, int] = field(default_factory=dict)
    deduplicated_count: int = 0
    budget_applied: bool = False
    query_intent: str = "general"


@dataclass
class ContextResult:
    """Deterministic, structured context evidence returned to Agents/Chat."""
    query: str
    project_id: str
    items: List[ContextItem]
    sources: List[ContextSource]
    total_candidates: int
    returned_items: int
    truncated: bool
    retrieval_metadata: RetrievalMetadata
    errors: List[ProviderError] = field(default_factory=list)
