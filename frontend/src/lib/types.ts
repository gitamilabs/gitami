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


export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatRequest {
  repo_id: string;
  message: string;
  branch?: string;
  history?: ChatMessage[];
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

