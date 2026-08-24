import { create } from "zustand";
import { ConnectedRepository, GitHubInstallation } from "../lib/types";
import { githubApi, aiApi } from "../lib/api";

interface RepoState {
  connectedRepos: ConnectedRepository[];
  installations: GitHubInstallation[];
  indexedRepos: string[];
  vectorCount: number;
  graphRepos: string[];
  isLoading: boolean;
  error: string | null;

  fetchConnectedRepos: (token: string) => Promise<void>;
  fetchInstallations: (token: string) => Promise<void>;
  fetchIndexedRepos: () => Promise<void>;
  disconnectRepo: (token: string, repoId: string) => Promise<boolean>;
  ingestConnectedRepo: (
    token: string,
    repoId: string,
    branch?: string
  ) => Promise<any>;
  getInstallUrl: (token: string) => Promise<string>;
}

export const useRepoStore = create<RepoState>((set, get) => ({
  connectedRepos: [],
  installations: [],
  indexedRepos: ["final-year-project", "demo-mern", "integration-test-mern"],
  vectorCount: 0,
  graphRepos: [],
  isLoading: false,
  error: null,

  fetchConnectedRepos: async (token: string) => {
    set({ isLoading: true, error: null });
    try {
      const data = await githubApi.getRepositories(token);
      set({ connectedRepos: data.repositories || [], isLoading: false });
    } catch (err: any) {
      console.warn("Failed to fetch connected repositories:", err);
      set({ isLoading: false, error: err.message });
    }
  },

  fetchInstallations: async (token: string) => {
    try {
      const data = await githubApi.getInstallations(token);
      set({ installations: data.installations || [] });
    } catch (err: any) {
      console.warn("Failed to fetch installations:", err);
    }
  },

  fetchIndexedRepos: async () => {
    try {
      const data = await aiApi.listRepos();
      set({
        indexedRepos: data.repos || ["final-year-project"],
        vectorCount: data.vector_count || 0,
        graphRepos: data.graph_repos || [],
      });
    } catch (err: any) {
      console.warn("Failed to fetch indexed repos from AI Service:", err);
    }
  },

  disconnectRepo: async (token: string, repoId: string): Promise<boolean> => {
    try {
      await githubApi.disconnectRepository(token, repoId);
      set((state) => ({
        connectedRepos: state.connectedRepos.filter((r) => r.id !== repoId),
      }));
      return true;
    } catch (err: any) {
      set({ error: err.message });
      return false;
    }
  },

  ingestConnectedRepo: async (
    token: string,
    repoId: string,
    branch?: string
  ): Promise<any> => {
    const res = await githubApi.ingestRepository(token, repoId, branch);
    await get().fetchIndexedRepos();
    return res.ingestResult;
  },

  getInstallUrl: async (token: string): Promise<string> => {
    const data = await githubApi.getInstallUrl(token);
    return data.installUrl;
  },
}));

