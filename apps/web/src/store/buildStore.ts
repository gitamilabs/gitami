import { create } from "zustand";
import { Build } from "../lib/types";
import { projectsApi } from "../lib/api";

interface BuildState {
  builds: Build[];
  activeBuild: Build | null;
  isLoading: boolean;
  error: string | null;
  getActiveBuilds: () => Build[];
  fetchProjectBuilds: (token: string, projectIdOrSlug: string) => Promise<Build[]>;
  fetchBuildDetails: (token: string, buildId: string) => Promise<Build | null>;
  startBuild: (
    token: string,
    projectIdOrSlug: string,
    repositoryId: string,
    branch?: string
  ) => Promise<Build>;
  cancelBuild: (token: string, buildId: string) => Promise<Build | null>;
  deleteBuild: (token: string, buildId: string) => Promise<boolean>;
}

export const useBuildStore = create<BuildState>((set, get) => ({
  builds: [],
  activeBuild: null,
  isLoading: false,
  error: null,

  getActiveBuilds: () => {
    return get().builds.filter((b) => b.status === "RUNNING" || b.status === "QUEUED");
  },

  fetchProjectBuilds: async (token: string, projectIdOrSlug: string) => {
    try {
      const data = await projectsApi.getBuilds(token, projectIdOrSlug);
      const builds = data.builds || [];
      set({ builds });
      return builds;
    } catch (err: any) {
      console.warn("Failed to fetch project builds:", err);
      return [];
    }
  },

  fetchBuildDetails: async (token: string, buildId: string) => {
    try {
      const data = await projectsApi.getBuild(token, buildId);
      const build = data.build;
      if (build) {
        set((state) => ({
          activeBuild: build,
          builds: state.builds.some((b) => b.id === build.id)
            ? state.builds.map((b) => (b.id === build.id ? build : b))
            : [build, ...state.builds],
        }));
      }
      return build || null;
    } catch (err: any) {
      console.warn("Failed to fetch build details:", err);
      return null;
    }
  },

  startBuild: async (
    token: string,
    projectIdOrSlug: string,
    repositoryId: string,
    branch = "main"
  ) => {
    set({ isLoading: true, error: null });
    try {
      const res = await projectsApi.startBuild(token, projectIdOrSlug, repositoryId, branch);
      const newBuild = res.build;
      const updated = [newBuild, ...get().builds.filter((b) => b.id !== newBuild.id)];
      set({ builds: updated, activeBuild: newBuild, isLoading: false });
      return newBuild;
    } catch (err: any) {
      set({ error: err.message || "Failed to start build", isLoading: false });
      throw err;
    }
  },

  cancelBuild: async (token: string, buildId: string) => {
    try {
      const res = await projectsApi.cancelBuild(token, buildId);
      const updatedBuild = res.build;
      if (updatedBuild) {
        set((state) => ({
          builds: state.builds.map((b) => (b.id === updatedBuild.id ? updatedBuild : b)),
          activeBuild: state.activeBuild?.id === updatedBuild.id ? updatedBuild : state.activeBuild,
        }));
      }
      return updatedBuild || null;
    } catch (err: any) {
      console.warn("Failed to cancel build:", err);
      return null;
    }
  },

  deleteBuild: async (token: string, buildId: string) => {
    try {
      await projectsApi.deleteBuild(token, buildId);
      set((state) => ({
        builds: state.builds.filter((b) => b.id !== buildId),
        activeBuild: state.activeBuild?.id === buildId ? null : state.activeBuild,
      }));
      return true;
    } catch (err: any) {
      console.warn("Failed to delete build:", err);
      return false;
    }
  },
}));
