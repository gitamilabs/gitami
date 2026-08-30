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
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000/api/v1";

const AI_SERVICE_BASE_URL =
  process.env.NEXT_PUBLIC_AI_SERVICE_URL || "http://localhost:8000";

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
  getInstallUrl: async (token: string): Promise<InstallUrlResponse> => {
    const res = await fetch(`${API_BASE_URL}/github/install-url`, {
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

  getRepositories: async (token: string): Promise<RepositoriesResponse> => {
    const res = await fetch(`${API_BASE_URL}/github/repositories`, {
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

  disconnectRepository: async (
    token: string,
    repoId: string
  ): Promise<{ success: boolean; message: string }> => {
    const res = await fetch(`${API_BASE_URL}/github/repositories/${repoId}`, {
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
    const res = await fetch(`${AI_SERVICE_BASE_URL}/api/health`);
    if (!res.ok) {
      throw new Error(`AI Service health check failed (${res.status})`);
    }
    return res.json();
  },

  getConfig: async (): Promise<AIServiceConfig> => {
    const res = await fetch(`${AI_SERVICE_BASE_URL}/api/config`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error || "Failed to fetch AI service configuration");
    }
    return res.json();
  },

  listPrompts: async (): Promise<PromptsResponse> => {
    const res = await fetch(`${AI_SERVICE_BASE_URL}/api/prompts`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error || "Failed to fetch AI system prompts");
    }
    return res.json();
  },

  getPrompt: async (key: string): Promise<PromptInfo> => {
    const res = await fetch(`${AI_SERVICE_BASE_URL}/api/prompts/${key}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error || `Failed to fetch prompt '${key}'`);
    }
    return res.json();
  },

  updatePrompt: async (key: string, text: string): Promise<PromptUpdateResponse> => {
    const res = await fetch(`${AI_SERVICE_BASE_URL}/api/prompts/${key}`, {
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
    const res = await fetch(`${AI_SERVICE_BASE_URL}/api/prompts/${key}/reset`, {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error || `Failed to reset prompt '${key}'`);
    }
    return res.json();
  },

  listRepos: async (): Promise<ReposResponse> => {
    const res = await fetch(`${AI_SERVICE_BASE_URL}/api/repos`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || "Failed to fetch indexed repositories");
    }
    return res.json();
  },

  ingestRepo: async (payload: IngestRequest): Promise<IngestResponse> => {
    const res = await fetch(`${AI_SERVICE_BASE_URL}/api/ingest`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.error || "Repository ingestion failed");
    }
    return res.json();
  },

  chatQuery: async (payload: ChatRequest): Promise<ChatResponse> => {
    const res = await fetch(`${AI_SERVICE_BASE_URL}/api/chat`, {
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
      const response = await fetch(`${AI_SERVICE_BASE_URL}/api/chat/stream`, {
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
};

// ==========================================
// PR Review & Fixer API (api-service)
// ==========================================

export const prApi = {
  listPullRequests: async (
    repoFullName?: string,
    token?: string
  ): Promise<{ pullRequests: PRData[] }> => {
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
};

