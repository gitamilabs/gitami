import {
  AuthMeResponse,
  RepositoriesResponse,
  InstallationsResponse,
  InstallUrlResponse,
  HealthResponse,
  ReposResponse,
  IngestRequest,
  IngestResponse,
  ChatRequest,
  ChatResponse,
  SSEEvent,
  PRData,
  PRReviewData,
  PRIssueItem,
  ConnectedRepository,
  AIServiceConfig,
  PromptInfo,
  PromptsResponse,
  PromptUpdateResponse,
  Team,
  TeamMember,
  UpdateTeamInput,
  UpdateProjectInput,
  UpdateRepoInput,
  CreatePRInput,
  UpdatePRInput,
  Project,
  Build,
  GraphData,
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000/api/v1";

const INTELLIGENCE_BASE_URL = `${API_BASE_URL}/intelligence`;

// ==========================================
// Control Plane API (api-service on Bun/Hono)
// ==========================================

export const authApi = {
  getLoginUrl: (): string => {
    return `${API_BASE_URL}/auth/github`;
  },

  getMe: async (token: string): Promise<AuthMeResponse> => {
    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Failed to fetch user profile (${res.status})`);
    }
    return res.json();
  },

  logout: async (token: string): Promise<{ success: boolean; message: string }> => {
    const res = await fetch(`${API_BASE_URL}/auth/logout`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    return res.json();
  },
};

export const githubApi = {
  getInstallUrl: async (
    token: string,
    teamSlug?: string,
    projectSlug?: string
  ): Promise<InstallUrlResponse> => {
    const params = new URLSearchParams();
    if (teamSlug) params.append("teamSlug", teamSlug);
    if (projectSlug) params.append("projectSlug", projectSlug);
    const queryString = params.toString() ? `?${params.toString()}` : "";
    const res = await fetch(`${API_BASE_URL}/github/install-url${queryString}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch installation URL");
    }
    return res.json();
  },

  getInstallations: async (token: string): Promise<InstallationsResponse> => {
    const res = await fetch(`${API_BASE_URL}/github/installations`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch GitHub installations");
    }
    return res.json();
  },

  getRepositories: async (token: string, force = false): Promise<RepositoriesResponse> => {
    const url = force
      ? `${API_BASE_URL}/github/repositories?force=true`
      : `${API_BASE_URL}/github/repositories`;
    const res = await fetch(url, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch connected repositories");
    }
    return res.json();
  },

  syncRepositories: async (token: string): Promise<RepositoriesResponse> => {
    const res = await fetch(`${API_BASE_URL}/github/repositories/sync`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to sync GitHub repositories");
    }
    return res.json();
  },

  getRepository: async (token: string, repoId: string): Promise<{ repository: ConnectedRepository }> => {
    const res = await fetch(`${API_BASE_URL}/github/repositories/${encodeURIComponent(repoId)}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch repository details");
    }
    return res.json();
  },

  updateRepository: async (
    token: string,
    repoId: string,
    updates: UpdateRepoInput
  ): Promise<{ repository: ConnectedRepository }> => {
    const res = await fetch(`${API_BASE_URL}/github/repositories/${encodeURIComponent(repoId)}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(updates),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to update repository");
    }
    return res.json();
  },

  disconnectRepository: async (
    token: string,
    repoId: string
  ): Promise<{ success: boolean; message: string }> => {
    const res = await fetch(`${API_BASE_URL}/github/repositories/${encodeURIComponent(repoId)}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to disconnect repository");
    }
    return res.json();
  },

  handleInstallationCallback: async (
    token: string,
    installationId: string,
    setupAction?: string
  ): Promise<any> => {
    const params = new URLSearchParams({
      installation_id: installationId,
      ...(setupAction ? { setup_action: setupAction } : {}),
    });
    const res = await fetch(`${API_BASE_URL}/github/callback?${params.toString()}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to sync GitHub installation");
    }
    return res.json();
  },

  ingestRepository: async (
    token: string,
    repoId: string,
    branch?: string
  ): Promise<{ success: boolean; repository: any; ingestResult: IngestResponse }> => {
    const res = await fetch(`${API_BASE_URL}/github/repositories/${repoId}/ingest`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ branch }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Failed to ingest repository (${res.status})`);
    }
    return res.json();
  },

  /**
   * Ingests a local filesystem directory, authenticated so the resulting
   * knowledge-base entry is recorded as owned by the current user.
   */
  ingestLocal: async (
    token: string,
    payload: { repo_id: string; repo_dir: string; branch?: string }
  ): Promise<{ success: boolean; repository: any; ingestResult: IngestResponse }> => {
    const res = await fetch(`${API_BASE_URL}/github/ingest-local`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Failed to ingest repository (${res.status})`);
    }
    return res.json();
  },

  /**
   * Lists Knowledge Base repo names scoped to the current user's own
   * connected/ingested repositories only (never other users' data).
   */
  listIndexedRepos: async (
    token: string
  ): Promise<{ repos: string[]; vector_count?: number }> => {
    const res = await fetch(`${API_BASE_URL}/github/indexed-repos`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch indexed repositories");
    }
    return res.json();
  },

  /**
   * Forces a live re-sync of GitHub App installations & repositories
   * (as opposed to just re-reading the cached DB rows).
   */
  syncInstallations: async (
    token: string
  ): Promise<{ success: boolean; repositories: ConnectedRepository[] }> => {
    const res = await fetch(`${API_BASE_URL}/github/sync`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to sync GitHub installations");
    }
    return res.json();
  },
};


// ==========================================
// AI Service API (ai-service on FastAPI)
// ==========================================

export const aiApi = {
  checkHealth: async (): Promise<HealthResponse> => {
    const res = await fetch(`${INTELLIGENCE_BASE_URL}/health`);
    if (!res.ok) {
      throw new Error(`Intelligence Service health check failed (${res.status})`);
    }
    return res.json();
  },

  getConfig: async (): Promise<AIServiceConfig> => {
    const res = await fetch(`${INTELLIGENCE_BASE_URL}/config`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error || "Failed to fetch AI configuration");
    }
    return res.json();
  },

  listPrompts: async (): Promise<PromptsResponse> => {
    const res = await fetch(`${INTELLIGENCE_BASE_URL}/prompts`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error || "Failed to fetch AI prompts");
    }
    return res.json();
  },

  getPrompt: async (key: string): Promise<PromptInfo> => {
    const res = await fetch(`${INTELLIGENCE_BASE_URL}/prompts/${key}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error || `Failed to fetch prompt '${key}'`);
    }
    return res.json();
  },

  updatePrompt: async (key: string, text: string): Promise<PromptUpdateResponse> => {
    const res = await fetch(`${INTELLIGENCE_BASE_URL}/prompts/${key}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error || `Failed to update prompt '${key}'`);
    }
    return res.json();
  },

  resetPrompt: async (key: string): Promise<PromptUpdateResponse> => {
    const res = await fetch(`${INTELLIGENCE_BASE_URL}/prompts/${key}/reset`, {
      method: "POST",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error || `Failed to reset prompt '${key}'`);
    }
    return res.json();
  },

  listRepos: async (): Promise<ReposResponse> => {
    const res = await fetch(`${INTELLIGENCE_BASE_URL}/repos`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch indexed repositories");
    }
    return res.json();
  },

  chatQuery: async (payload: ChatRequest): Promise<ChatResponse> => {
    const res = await fetch(`${INTELLIGENCE_BASE_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error || "Chat request failed");
    }
    return res.json();
  },

  /**
   * Stream autonomous ReAct reasoning, tool steps, and final citations via SSE
   */
  streamChat: async (
    payload: ChatRequest,
    onEvent: (event: SSEEvent) => void,
    onError: (err: Error) => void,
    onComplete: () => void,
    signal?: AbortSignal
  ): Promise<void> => {
    try {
      const response = await fetch(`${INTELLIGENCE_BASE_URL}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
        signal,
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `Streaming error (${response.status})`);
      }

      if (!response.body) {
        throw new Error("ReadableStream not supported in response body");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) continue;

          const jsonStr = trimmed.replace(/^data:\s*/, "");
          if (!jsonStr) continue;

          try {
            const parsed = JSON.parse(jsonStr) as SSEEvent;
            onEvent(parsed);
          } catch (e) {
            console.warn("Failed to parse SSE event data:", jsonStr, e);
          }
        }
      }

      onComplete();
    } catch (err: any) {
      if (err.name === "AbortError") {
        console.log("Chat stream was aborted by user.");
        onComplete();
      } else {
        onError(err);
      }
    }
  },

  getGraphReport: async (repoId: string, branch: string = "main"): Promise<{ status: string; repo_id: string; report_markdown: string }> => {
    const res = await fetch(`${INTELLIGENCE_BASE_URL}/graph-report/${encodeURIComponent(repoId)}?branch=${encodeURIComponent(branch)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error || "Failed to generate graph report");
    }
    return res.json();
  },

  /**
   * Curated Investigation Agent
   */
  investigate: async (params: {
    query: string;
    repoId: string;
    branch?: string;
    isIncident?: boolean;
    incidentContext?: Record<string, any>;
    maxSteps?: number;
  }): Promise<any> => {
    const res = await fetch(`${INTELLIGENCE_BASE_URL}/investigate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: params.query,
        repo_id: params.repoId,
        branch: params.branch || "main",
        is_incident: params.isIncident || false,
        incident_context: params.incidentContext,
        max_steps: params.maxSteps || 8,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Investigation request failed");
    }
    return res.json();
  },

  /**
   * Curated Issue Agent
   */
  analyzeIssue: async (params: {
    repoId: string;
    issueNumber: number;
    title: string;
    body?: string;
    author?: string;
    labels?: string[];
    existingIssues?: any[];
  }): Promise<any> => {
    const res = await fetch(`${INTELLIGENCE_BASE_URL}/issue/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo_id: params.repoId,
        issue_number: params.issueNumber,
        title: params.title,
        body: params.body || "",
        author: params.author || "unknown",
        labels: params.labels || [],
        existing_issues: params.existingIssues,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Issue analysis failed");
    }
    return res.json();
  },

  /**
   * Curated Doc Agent
   */
  generateDoc: async (params: {
    repoId: string;
    docType?: string;
    topic: string;
    branch?: string;
    feedToKb?: boolean;
    mergedPrs?: any[];
  }): Promise<any> => {
    const res = await fetch(`${INTELLIGENCE_BASE_URL}/doc/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo_id: params.repoId,
        doc_type: params.docType || "workflow_guide",
        topic: params.topic,
        branch: params.branch || "main",
        feed_to_kb: params.feedToKb !== false,
        merged_prs: params.mergedPrs,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Doc generation failed");
    }
    return res.json();
  },

  /**
   * Curated Code Agent Stage 1: Plan
   */
  planCodeFix: async (params: {
    repoId: string;
    issueTitle: string;
    issueDescription: string;
    triggerSource?: string;
    affectedFiles?: string[];
    branch?: string;
  }): Promise<any> => {
    const res = await fetch(`${INTELLIGENCE_BASE_URL}/code/plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo_id: params.repoId,
        issue_title: params.issueTitle,
        issue_description: params.issueDescription,
        trigger_source: params.triggerSource || "review",
        affected_files: params.affectedFiles,
        branch: params.branch || "main",
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Code fix planning failed");
    }
    return res.json();
  },

  /**
   * Curated Code Agent Stage 2: Execute
   */
  executeCodeFix: async (params: {
    plan: any;
    existingFileContents: Record<string, string>;
    maintainerNotes?: string;
  }): Promise<any> => {
    const res = await fetch(`${INTELLIGENCE_BASE_URL}/code/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan: params.plan,
        existing_file_contents: params.existingFileContents,
        maintainer_notes: params.maintainerNotes,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Code fix execution failed");
    }
    return res.json();
  },
};

// ==========================================
// PR Review & Fixer API (api-service)
// ==========================================

export const prApi = {
  listPullRequests: async (
    repoFullName?: string,
    token?: string,
    projectId?: string
  ): Promise<{ pullRequests: PRData[] }> => {
    const params = new URLSearchParams();
    if (repoFullName) params.append("repoFullName", repoFullName);
    if (projectId) params.append("projectId", projectId);
    const queryString = params.toString() ? `?${params.toString()}` : "";
    const url = `${API_BASE_URL}/prs${queryString}`;
    const headers: Record<string, string> = { Accept: "application/json" };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const res = await fetch(url, { headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch pull requests");
    }
    return res.json();
  },

  syncPullRequests: async (
    token?: string,
    repoFullName?: string
  ): Promise<{ success: boolean; pullRequests: PRData[] }> => {
    const url = repoFullName
      ? `${API_BASE_URL}/prs?repoFullName=${encodeURIComponent(repoFullName)}`
      : `${API_BASE_URL}/prs`;
    const headers: Record<string, string> = { Accept: "application/json" };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const res = await fetch(url, { headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to sync pull requests from GitHub");
    }
    return res.json();
  },

  getPullRequest: async (id: string, token?: string): Promise<{ pullRequest: PRData }> => {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const res = await fetch(`${API_BASE_URL}/prs/${id}`, { headers });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch PR details");
    }
    return res.json();
  },

  reviewPullRequest: async (id: string, token?: string): Promise<{ success: boolean; pullRequest: PRData }> => {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const res = await fetch(`${API_BASE_URL}/prs/${id}/review`, {
      method: "POST",
      headers,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to evaluate PR");
    }
    return res.json();
  },

  fixSelectedIssues: async (
    id: string,
    issueIds: string[],
    token?: string
  ): Promise<{ success: boolean; fixPrUrl?: string; message?: string }> => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const res = await fetch(`${API_BASE_URL}/prs/${id}/fix`, {
      method: "POST",
      headers,
      body: JSON.stringify({ issueIds }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to execute AI fix");
    }
    return res.json();
  },

  createPullRequest: async (
    token: string,
    payload: CreatePRInput
  ): Promise<{ pullRequest: PRData }> => {
    const res = await fetch(`${API_BASE_URL}/prs`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to create pull request");
    }
    return res.json();
  },

  updatePullRequest: async (
    token: string,
    id: string,
    updates: UpdatePRInput
  ): Promise<{ pullRequest: PRData }> => {
    const res = await fetch(`${API_BASE_URL}/prs/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(updates),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to update pull request");
    }
    return res.json();
  },

  deletePullRequest: async (
    token: string,
    id: string
  ): Promise<{ success: boolean; message: string }> => {
    const res = await fetch(`${API_BASE_URL}/prs/${encodeURIComponent(id)}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to delete pull request");
    }
    return res.json();
  },

  updateIssue: async (
    token: string,
    issueId: string,
    updates: { isFixed?: boolean; title?: string; severity?: string }
  ): Promise<{ issue: PRIssueItem }> => {
    const res = await fetch(`${API_BASE_URL}/prs/issues/${encodeURIComponent(issueId)}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(updates),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to update issue");
    }
    return res.json();
  },
};

// ==========================================
// Teams & Projects Control Plane APIs
// ==========================================

export const teamsApi = {
  getTeams: async (token: string): Promise<{ teams: Team[] }> => {
    const res = await fetch(`${API_BASE_URL}/teams`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch teams");
    }
    return res.json();
  },

  createTeam: async (token: string, name: string): Promise<{ team: Team }> => {
    const res = await fetch(`${API_BASE_URL}/teams`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to create team");
    }
    return res.json();
  },

  getTeamBySlug: async (token: string, teamSlug: string): Promise<{ team: Team }> => {
    const res = await fetch(`${API_BASE_URL}/teams/${encodeURIComponent(teamSlug)}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch team");
    }
    return res.json();
  },

  getTeamProjects: async (
    token: string,
    teamSlug: string
  ): Promise<{ projects: Project[]; team: Team }> => {
    const res = await fetch(
      `${API_BASE_URL}/teams/${encodeURIComponent(teamSlug)}/projects`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch team projects");
    }
    return res.json();
  },

  createTeamProject: async (
    token: string,
    teamSlug: string,
    name: string,
    description?: string
  ): Promise<{ project: Project }> => {
    const res = await fetch(
      `${API_BASE_URL}/teams/${encodeURIComponent(teamSlug)}/projects`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ name, description }),
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to create project");
    }
    return res.json();
  },

  updateTeam: async (
    token: string,
    teamSlug: string,
    updates: UpdateTeamInput
  ): Promise<{ team: Team }> => {
    const res = await fetch(`${API_BASE_URL}/teams/${encodeURIComponent(teamSlug)}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(updates),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to update team");
    }
    return res.json();
  },

  deleteTeam: async (
    token: string,
    teamSlug: string
  ): Promise<{ success: boolean; message: string }> => {
    const res = await fetch(`${API_BASE_URL}/teams/${encodeURIComponent(teamSlug)}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to delete team");
    }
    return res.json();
  },

  getTeamMembers: async (
    token: string,
    teamSlug: string
  ): Promise<{ members: TeamMember[] }> => {
    const res = await fetch(`${API_BASE_URL}/teams/${encodeURIComponent(teamSlug)}/members`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch team members");
    }
    return res.json();
  },

  addTeamMember: async (
    token: string,
    teamSlug: string,
    usernameOrEmail: string,
    role: string = "MEMBER"
  ): Promise<{ member: TeamMember }> => {
    const res = await fetch(`${API_BASE_URL}/teams/${encodeURIComponent(teamSlug)}/members`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ usernameOrEmail, role }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to add team member");
    }
    return res.json();
  },

  updateTeamMemberRole: async (
    token: string,
    teamSlug: string,
    memberId: string,
    role: string
  ): Promise<{ member: TeamMember }> => {
    const res = await fetch(
      `${API_BASE_URL}/teams/${encodeURIComponent(teamSlug)}/members/${encodeURIComponent(memberId)}`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ role }),
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to update member role");
    }
    return res.json();
  },

  removeTeamMember: async (
    token: string,
    teamSlug: string,
    memberId: string
  ): Promise<{ success: boolean; message: string }> => {
    const res = await fetch(
      `${API_BASE_URL}/teams/${encodeURIComponent(teamSlug)}/members/${encodeURIComponent(memberId)}`,
      {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to remove member");
    }
    return res.json();
  },
};

export const projectsApi = {
  getProject: async (
    token: string,
    projectIdOrSlug: string
  ): Promise<{
    project: Project;
    organization: Team;
    repositories: ConnectedRepository[];
    builds: Build[];
  }> => {
    const res = await fetch(
      `${API_BASE_URL}/projects/${encodeURIComponent(projectIdOrSlug)}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch project details");
    }
    return res.json();
  },

  attachRepository: async (
    token: string,
    projectIdOrSlug: string,
    repositoryId: string
  ): Promise<{ success: boolean; repository: ConnectedRepository }> => {
    const res = await fetch(
      `${API_BASE_URL}/projects/${encodeURIComponent(projectIdOrSlug)}/repositories`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ repositoryId }),
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to connect repository to project");
    }
    return res.json();
  },

  detachRepository: async (
    token: string,
    projectIdOrSlug: string,
    repositoryId: string
  ): Promise<{ success: boolean }> => {
    const res = await fetch(
      `${API_BASE_URL}/projects/${encodeURIComponent(
        projectIdOrSlug
      )}/repositories/${encodeURIComponent(repositoryId)}`,
      {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to disconnect repository");
    }
    return res.json();
  },

  getBuilds: async (
    token: string,
    projectIdOrSlug: string
  ): Promise<{ builds: Build[] }> => {
    const res = await fetch(
      `${API_BASE_URL}/projects/${encodeURIComponent(projectIdOrSlug)}/builds`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch builds");
    }
    return res.json();
  },

  startBuild: async (
    token: string,
    projectIdOrSlug: string,
    repositoryId: string,
    branch?: string
  ): Promise<{ success: boolean; build: Build }> => {
    const res = await fetch(
      `${API_BASE_URL}/projects/${encodeURIComponent(projectIdOrSlug)}/builds`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ repositoryId, branch }),
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to start build");
    }
    return res.json();
  },

  getBuild: async (token: string, buildId: string): Promise<{ build: Build }> => {
    const res = await fetch(`${API_BASE_URL}/builds/${encodeURIComponent(buildId)}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch build");
    }
    return res.json();
  },

  cancelBuild: async (token: string, buildId: string): Promise<{ success: boolean; build: Build }> => {
    const res = await fetch(`${API_BASE_URL}/builds/${encodeURIComponent(buildId)}/cancel`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to cancel build");
    }
    return res.json();
  },

  getGraph: async (
    token: string,
    projectIdOrSlug: string,
    repoId?: string,
    branch?: string,
    maxNodes?: number
  ): Promise<GraphData> => {
    const params = new URLSearchParams();
    if (repoId) params.append("repoId", repoId);
    if (branch) params.append("branch", branch);
    if (maxNodes) params.append("maxNodes", String(maxNodes));
    const qs = params.toString() ? `?${params.toString()}` : "";

    const res = await fetch(
      `${API_BASE_URL}/projects/${encodeURIComponent(projectIdOrSlug)}/graph${qs}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch knowledge graph");
    }
    return res.json();
  },

  updateProject: async (
    token: string,
    projectIdOrSlug: string,
    updates: UpdateProjectInput
  ): Promise<{ project: Project }> => {
    const res = await fetch(
      `${API_BASE_URL}/projects/${encodeURIComponent(projectIdOrSlug)}`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(updates),
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to update project");
    }
    return res.json();
  },

  deleteProject: async (
    token: string,
    projectIdOrSlug: string
  ): Promise<{ success: boolean; message: string }> => {
    const res = await fetch(
      `${API_BASE_URL}/projects/${encodeURIComponent(projectIdOrSlug)}`,
      {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to delete project");
    }
    return res.json();
  },

  updateBuild: async (
    token: string,
    buildId: string,
    updates: { status?: string; stage?: string; error?: string }
  ): Promise<{ success: boolean; build: Build }> => {
    const res = await fetch(`${API_BASE_URL}/builds/${encodeURIComponent(buildId)}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(updates),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to update build");
    }
    return res.json();
  },

  deleteBuild: async (
    token: string,
    buildId: string
  ): Promise<{ success: boolean; message: string }> => {
    const res = await fetch(`${API_BASE_URL}/builds/${encodeURIComponent(buildId)}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to delete build");
    }
    return res.json();
  },
};


