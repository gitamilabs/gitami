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
