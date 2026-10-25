from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    repo_id: str
    message: str
    branch: Optional[str] = "main"
    history: Optional[List[ChatMessage]] = []
    project_id: Optional[str] = "default"
    team_id: Optional[str] = None
    root_directory: Optional[str] = None


class Citation(BaseModel):
    id: int
    file_path: str
    symbol: Optional[str] = None
    lines: Optional[str] = None
    snippet: str
    source_type: str  # 'vector' or 'graph'
    distance: Optional[float] = None


class ToolStep(BaseModel):
    id: str
    tool_name: str
    title: str
    status: str  # 'completed', 'failed', 'running'
    latency_ms: float
    args: Dict[str, Any]
    summary: str
    raw_output: Any


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]
    tool_steps: List[ToolStep]
    repo_id: str
    branch: str
    total_latency_ms: float


class IngestRequest(BaseModel):
    repo_id: str
    repo_dir: Optional[str] = None
    full_name: Optional[str] = None
    access_token: Optional[str] = None
    branch: Optional[str] = "main"
    extraction_mode: Optional[str] = "fast"
    project_id: Optional[str] = "default"
    team_id: Optional[str] = None
    root_directory: Optional[str] = None


class IngestUrlRequest(BaseModel):
    repo_url: str
    repo_id: Optional[str] = None
    branch: Optional[str] = "main"
    extraction_mode: Optional[str] = "fast"
    project_id: Optional[str] = "default"
    team_id: Optional[str] = None
    root_directory: Optional[str] = None


class ReindexRequest(BaseModel):
    repo_id: str
    branch: Optional[str] = "main"
    base_commit_sha: Optional[str] = None
    target_commit_sha: Optional[str] = "HEAD"
    repo_dir: Optional[str] = None
    full_name: Optional[str] = None
    access_token: Optional[str] = None
    force_full: Optional[bool] = False
    project_id: Optional[str] = "default"
    team_id: Optional[str] = None
    root_directory: Optional[str] = None


class PromptUpdateRequest(BaseModel):
    text: str


class ContextApiRequest(BaseModel):
    query: str
    repository_ids: Optional[List[str]] = []
    branch: Optional[str] = "main"
    commit_sha: Optional[str] = None
    max_items: Optional[int] = 20
    max_tokens: Optional[int] = 8000
    include_graph: Optional[bool] = True
    include_semantic: Optional[bool] = True
    include_source: Optional[bool] = True
    include_github: Optional[bool] = True
    hops: Optional[int] = 1


class PRReviewRequest(BaseModel):
    repo_id: str
    pr_number: int
    base_branch: str = "main"
    head_branch: str
    title: str
    body: Optional[str] = ""
    diff_text: Optional[str] = None
    project_id: Optional[str] = "default"
    team_id: Optional[str] = None
    root_directory: Optional[str] = None


class PRFixRequest(BaseModel):
    repo_id: str
    pr_number: int
    base_branch: str = "main"
    issues: List[Dict[str, Any]]
    diff_text: str = ""
    existing_file_contents: Optional[Dict[str, str]] = None


class InvestigationRequest(BaseModel):
    query: str
    repo_id: str
    branch: Optional[str] = "main"
    is_incident: bool = False
    incident_context: Optional[Dict[str, Any]] = None
    max_steps: Optional[int] = 8


class IssueAnalyzeRequest(BaseModel):
    repo_id: str
    issue_number: int
    title: str
    body: Optional[str] = ""
    author: Optional[str] = "unknown"
    labels: Optional[List[str]] = []
    existing_issues: Optional[List[Dict[str, Any]]] = None


class DocGenerateRequest(BaseModel):
    repo_id: str
    doc_type: str = "workflow_guide"  # "workflow_guide", "onboarding_doc", "weekly_changelog"
    topic: str
    branch: Optional[str] = "main"
    feed_to_kb: bool = True
    merged_prs: Optional[List[Dict[str, Any]]] = None


class CodePlanRequest(BaseModel):
    repo_id: str
    issue_title: str
    issue_description: str
    trigger_source: str = "review"
    affected_files: Optional[List[str]] = None
    branch: Optional[str] = "main"


class CodeExecuteRequest(BaseModel):
    plan: Dict[str, Any]
    existing_file_contents: Dict[str, str]
    maintainer_notes: Optional[str] = None

