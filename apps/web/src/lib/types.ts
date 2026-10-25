// ==========================================
// Control Plane (api-service) Models & Types
// ==========================================

export interface User {
  id: string;
  githubId: string;
  github_id?: string;
  username: string;
  name?: string;
  email?: string | null;
  avatarUrl: string;
  avatar_url?: string;
  createdAt: string;
  created_at?: string;
  updatedAt: string;
  updated_at?: string;
}

export interface AuthMeResponse {
  user: User;
}

export interface ConnectedRepository {
  id: string;
  installationId: string;
  userId: string;
  githubRepoId: string;
  name: string;
  fullName: string;
  isPrivate: boolean;
  htmlUrl: string;
  defaultBranch: string;
  rootDirectory?: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface GitHubInstallation {
  id: string;
  userId: string;
  installationId: string;
  accountLogin: string;
  accountType: string;
  createdAt: string;
  updatedAt: string;
}

export interface RepositoriesResponse {
  repositories: ConnectedRepository[];
}

export interface InstallationsResponse {
  installations: GitHubInstallation[];
}

export interface InstallUrlResponse {
  installUrl: string;
}

// ==========================================
// AI Service (ai-service) Models & Types
// ==========================================

export interface HealthResponse {
  status: string;
  service: string;
  timestamp?: string;
}

export interface ReposResponse {
  repos: string[];
  vector_count?: number;
  graph_repos?: string[];
  error?: string;
}

export interface IngestRequest {
  repo_id: string;
  repo_dir?: string;
  full_name?: string;
  access_token?: string;
  branch?: string;
}

export interface IngestResponse {
  status: string;
  repo_id: string;
  symbols_parsed: number;
  files_parsed: number;
  packages: number;
  edges_count: number;
  duration_seconds: number;
}

export interface IngestRepoResult {
  success: boolean;
  repository?: ConnectedRepository;
  ingestResult?: IngestResponse;
  error?: string;
}


export interface AIServiceConfig {
  vector_db: string;
  embedder: string;
  models: {
    gemini_models: string[];
    groq_models: string[];
    primary_orchestrator: string;
    worker_model: string;
  };
  storage: {
    qdrant_collection?: string;
    pinecone_index?: string;
    supabase_table?: string;
    chroma_persist_dir?: string;
  };
}

export interface PromptInfo {
  key: string;
  title: string;
  description: string;
  prompt: string;
  default_prompt: string;
  is_customized: boolean;
}

export interface PromptsResponse {
  prompts: PromptInfo[];
}

export interface PromptUpdateResponse {
  status: string;
  prompt: PromptInfo;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatRequest {
  repo_id: string;
  message: string;
  branch?: string;
  project_id?: string;
  team_id?: string;
  history?: ChatMessage[];
  root_directory?: string | null;
}

export interface Citation {
  id: number;
  file_path: string;
  symbol?: string | null;
  lines?: string | null;
  snippet: string;
  source_type: "vector" | "graph" | string;
  distance?: number | null;
}

export interface ToolStep {
  id: string;
  tool_name: string;
  title: string;
  status: "running" | "completed" | "failed";
  latency_ms: number;
  args: Record<string, any>;
  summary: string;
  raw_output: any;
  step_index?: number;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  tool_steps: ToolStep[];
  repo_id: string;
  branch: string;
  total_latency_ms: number;
}

// ==========================================
// SSE ReAct Streaming Event Payloads
// ==========================================

export type SSEEventType =
  | "thought"
  | "tool_start"
  | "tool_end"
  | "answer_delta"
  | "citations"
  | "done"
  | "error";

export interface SSEThoughtEvent {
  type: "thought";
  step_index: number;
  content: string;
}

export interface SSEToolStartEvent {
  type: "tool_start";
  step_id: string;
  step_index: number;
  tool_name: string;
  title: string;
  args: Record<string, any>;
}

export interface SSEToolEndEvent {
  type: "tool_end";
  step_id: string;
  step_index: number;
  tool_name: string;
  title: string;
  status: "completed" | "failed";
  latency_ms: number;
  args: Record<string, any>;
  summary: string;
  raw_output: any;
}

export interface SSEAnswerDeltaEvent {
  type: "answer_delta";
  delta: string;
}

export interface SSECitationsEvent {
  type: "citations";
  citations: Citation[];
}

export interface SSEDoneEvent {
  type: "done";
  total_latency_ms: number;
}

export interface SSEErrorEvent {
  type: "error";
  message: string;
}

export type SSEEvent =
  | SSEThoughtEvent
  | SSEToolStartEvent
  | SSEToolEndEvent
  | SSEAnswerDeltaEvent
  | SSECitationsEvent
  | SSEDoneEvent
  | SSEErrorEvent;

// ==========================================
// Pull Request Review & Auto-Fixer Types
// ==========================================

export interface PRIssueItem {
  id: string;
  prId?: string;
  title: string;
  description: string;
  category: "bug" | "security" | "logical_error" | "convention" | "blast_radius" | string;
  severity: "error" | "warning" | "info" | string;
  filePath: string;
  line: number;
  suggestedFix?: string;
  isFixed?: boolean;
  fixPrUrl?: string;
}

export interface PRReviewData {
  id?: string;
  prId?: string;
  verdict: "ACCEPT" | "SUGGEST" | "REJECT" | string;
  riskScore: number;
  summary: string;
  agentRationale?: string;
  status?: string;
  createdAt?: string;
}

export interface PRData {
  id: string;
  repoFullName: string;
  prNumber: number;
  title: string;
  body?: string;
  state: "open" | "closed" | "merged" | string;
  status: "pending" | "reviewed" | "skipped_ai_fix" | string;
  baseBranch: string;
  headBranch: string;
  authorLogin?: string;
  htmlUrl?: string;
  review?: PRReviewData | null;
  issues?: PRIssueItem[];
  createdAt?: string;
  updatedAt?: string;
}

// ==========================================
// Workspace, Team, Project, & Build Types
// ==========================================

export interface Team {
  id: string;
  name: string;
  slug: string;
  createdAt: string;
  updatedAt: string;
}

export interface TeamMember {
  id: string;
  organizationId: string;
  userId: string;
  role: "OWNER" | "MEMBER" | "VIEWER" | string;
  createdAt: string;
  user: {
    id: string;
    username: string;
    email: string | null;
    avatarUrl: string;
  };
}

export interface UpdateTeamInput {
  name?: string;
  slug?: string;
}

export interface UpdateProjectInput {
  name?: string;
  description?: string;
  slug?: string;
}

export interface UpdateRepoInput {
  defaultBranch?: string;
  isActive?: boolean;
  name?: string;
  rootDirectory?: string | null;
}

export interface CreatePRInput {
  repoFullName: string;
  prNumber?: number;
  title: string;
  body?: string;
  baseBranch?: string;
  headBranch: string;
  htmlUrl?: string;
}

export interface UpdatePRInput {
  title?: string;
  body?: string;
  state?: "open" | "closed" | "merged" | string;
  status?: string;
}

export interface Project {
  id: string;
  organizationId: string;
  name: string;
  slug: string;
  description?: string | null;
  createdAt: string;
  updatedAt: string;
  repositoryCount?: number;
  repositories?: ConnectedRepository[];
  latestBuild?: Build | null;
  status?: "BUILDING" | "READY" | "IDLE" | string;
}

export interface BuildStage {
  key: string;
  name: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
}

export interface BuildStats {
  symbols_parsed?: number;
  files_parsed?: number;
  packages?: number;
  edges_count?: number;
  duration_seconds?: number;
}

export interface Build {
  id: string;
  projectId: string;
  repositoryId: string;
  type: string;
  targetCommitSha: string;
  branch: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
  progress: number;
  stage: string;
  stats?: BuildStats | null;
  error?: string | null;
  createdAt: string;
  startedAt?: string | null;
  completedAt?: string | null;
  stages?: BuildStage[];
  currentStage?: string;
}

export interface GraphCommunity {
  id: number;
  label: string;
  size: number;
  color: string;
  borderColor: string;
  paletteName: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type:
    | "Repository"
    | "Directory"
    | "File"
    | "Class"
    | "Function"
    | "Method"
    | "Interface"
    | "Type"
    | "Test"
    | "Schema"
    | "Enum"
    | "Router"
    | "Relation"
    | "Variable"
    | "Package"
    | "Inferred"
    | string;
  communityId?: number;
  communityLabel?: string;
  communityColor?: string;
  communityBorder?: string;
  degree?: number;
  inDegree?: number;
  outDegree?: number;
  importance?: number;
  level?: number;
  path?: string;
  parentId?: string;
  childCount?: number;
  isFolder?: boolean;
  isFile?: boolean;
  isRoot?: boolean;
  props?: Record<string, any>;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

export interface GraphEdge {
  id?: string;
  source: string;
  target: string;
  relation:
    | "CONTAINS"
    | "DEFINES"
    | "HAS_METHOD"
    | "CALLS"
    | "IMPORTS"
    | "DEPENDS_ON"
    | "DEPENDS_ON_FILE"
    | "EXTENDS"
    | "IMPLEMENTS"
    | "TESTS"
    | string;
  type?: string;
  props?: Record<string, any>;
}

export interface GraphData {
  status: "READY" | "NOT_INDEXED" | "BUILDING" | "FAILED" | "NO_REPOSITORY";
  message?: string;
  repository?: ConnectedRepository;
  build?: Build;
  nodes: GraphNode[];
  edges: GraphEdge[];
  communities?: GraphCommunity[];
  stats?: {
    nodeCount: number;
    edgeCount: number;
    communityCount: number;
    extractedCount?: number;
    inferredCount?: number;
    directoryCount?: number;
    fileCount?: number;
    symbolCount?: number;
    synthesizedCount?: number;
    observedCount?: number;
  };
  totalNodes?: number;
  totalEdges?: number;
}



