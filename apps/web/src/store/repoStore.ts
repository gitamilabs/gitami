import { create } from "zustand";
import { ConnectedRepository, GitHubInstallation } from "../lib/types";
import { githubApi } from "../lib/api";

interface RepoState {
  connectedRepos: ConnectedRepository[];
  installations: GitHubInstallation[];
  indexedRepos: string[];
  // True once each list has been fetched at least once this session. Lets
  // fetches be "fetch once, reuse everywhere" instead of every page
  // (Dashboard, PRs, project detail, Settings, chat) independently
  // re-hitting the API on every mount — pass `force: true` to bypass this
  // when the data is known to be stale (after a sync/ingest/disconnect).
  connectedReposLoaded: boolean;
  indexedReposLoaded: boolean;
  vectorCount: number;
  graphRepos: string[];
  isLoading: boolean;
  error: string | null;

  fetchConnectedRepos: (token: string, force?: boolean) => Promise<void>;
  fetchInstallations: (token: string) => Promise<void>;
  fetchIndexedRepos: (token: string, force?: boolean) => Promise<void>;
  syncInstallations: (token: string) => Promise<void>;
  disconnectRepo: (token: string, repoId: string) => Promise<boolean>;
  ingestConnectedRepo: (
    token: string,
    repoId: string,
    branch?: string
  ) => Promise<any>;
  getInstallUrl: (token: string) => Promise<string>;
}

// Module-level (not store state, so they never trigger re-renders) in-flight
// promise trackers. The `loaded` flags above only stop a *second* call made
// after the first one finished — they do nothing to stop a second call made
// *while the first is still pending*, which is exactly what happens when
// React's Strict Mode double-invokes an effect, or Sidebar/Dashboard/chat's
// RepoSelector all mount within the same tick. Every one of those calls saw
// `loaded: false` and fired its own request, and since each request opens a
// fresh Neo4j connection on the AI service, they queued up and got slower
// and slower the more of them piled on. Caching the in-flight promise itself
// means every concurrent caller shares the one real request.
let connectedReposInFlight: Promise<void> | null = null;
let indexedReposInFlight: Promise<void> | null = null;

export const useRepoStore = create<RepoState>((set, get) => ({
  connectedRepos: [],
  installations: [],
  indexedRepos: [],
  connectedReposLoaded: false,
  indexedReposLoaded: false,
  vectorCount: 0,
  graphRepos: [],
  isLoading: false,
  error: null,

  fetchConnectedRepos: async (token: string, force = false) => {
    if (!token) return;
    if (!force && get().connectedReposLoaded) return;
    if (connectedReposInFlight) return connectedReposInFlight;

    connectedReposInFlight = (async () => {
      set({ isLoading: true, error: null });
      try {
        const data = await githubApi.getRepositories(token);
        set({ connectedRepos: data.repositories || [], connectedReposLoaded: true, isLoading: false });
      } catch (err: any) {
        console.warn("Failed to fetch connected repositories:", err);
        set({ isLoading: false, error: err.message });
      } finally {
        connectedReposInFlight = null;
      }
    })();
    return connectedReposInFlight;
  },

  fetchInstallations: async (token: string) => {
    try {
      const data = await githubApi.getInstallations(token);
      set({ installations: data.installations || [] });
    } catch (err: any) {
      console.warn("Failed to fetch installations:", err);
    }
  },

  // Scoped to the current user's own repos only — never a global list.
  fetchIndexedRepos: async (token: string, force = false) => {
    if (!token) return;
    if (!force && get().indexedReposLoaded) return;
    if (indexedReposInFlight) return indexedReposInFlight;

    indexedReposInFlight = (async () => {
      try {
        const data = await githubApi.listIndexedRepos(token);
        set({
          indexedRepos: data.repos || [],
          vectorCount: data.vector_count || 0,
          indexedReposLoaded: true,
        });
      } catch (err: any) {
        console.warn("Failed to fetch indexed repos:", err);
        set({ indexedReposLoaded: true });
      } finally {
        indexedReposInFlight = null;
      }
    })();
    return indexedReposInFlight;
  },

  // Forces a live GitHub re-sync (not just a re-read of cached DB rows) —
  // catches repos added to an existing installation that never triggered a
  // redirect or webhook back to the app.
  syncInstallations: async (token: string) => {
    set({ isLoading: true, error: null });
    try {
      const data = await githubApi.syncInstallations(token);
      set({ connectedRepos: data.repositories || [], connectedReposLoaded: true, isLoading: false });
    } catch (err: any) {
      console.warn("Failed to sync GitHub installations:", err);
      set({ isLoading: false, error: err.message });
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
    await get().fetchIndexedRepos(token, true);
    return res.ingestResult;
  },

  getInstallUrl: async (token: string): Promise<string> => {
    const data = await githubApi.getInstallUrl(token);
    return data.installUrl;
  },
}));
