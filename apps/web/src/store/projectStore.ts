import { create } from "zustand";
import { Project, ConnectedRepository, UpdateProjectInput } from "../lib/types";
import { teamsApi, projectsApi } from "../lib/api";

interface ProjectState {
  projects: Project[];
  activeProject: Project | null;
  loadedTeamSlug: string | null;
  isLoading: boolean;
  error: string | null;
  getActiveProject: () => Project | null;
  setActiveProject: (projectOrSlug: Project | string) => void;
  fetchTeamProjects: (token: string, teamSlug: string, force?: boolean) => Promise<Project[]>;
  createProject: (
    token: string,
    teamSlug: string,
    name: string,
    description?: string
  ) => Promise<Project>;
  updateProject: (
    token: string,
    projectIdOrSlug: string,
    updates: UpdateProjectInput
  ) => Promise<Project>;
  deleteProject: (token: string, projectIdOrSlug: string) => Promise<boolean>;
  fetchProjectDetails: (token: string, projectIdOrSlug: string, force?: boolean) => Promise<Project | null>;
  attachRepository: (
    token: string,
    projectIdOrSlug: string,
    repositoryId: string
  ) => Promise<ConnectedRepository | null>;
  detachRepository: (
    token: string,
    projectIdOrSlug: string,
    repositoryId: string
  ) => Promise<boolean>;
}

const teamProjectsPromisesMap = new Map<string, Promise<Project[]>>();
const projectDetailsPromisesMap = new Map<string, Promise<Project | null>>();

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  activeProject: null,
  loadedTeamSlug: null,
  isLoading: false,
  error: null,

  getActiveProject: () => {
    return get().activeProject || get().projects[0] || null;
  },

  setActiveProject: (projectOrSlug: Project | string) => {
    const { projects } = get();
    if (typeof projectOrSlug === "string") {
      const found = projects.find((p) => p.slug === projectOrSlug || p.id === projectOrSlug);
      if (found) {
        set({ activeProject: found });
      }
    } else {
      set({ activeProject: projectOrSlug });
    }
  },

  fetchTeamProjects: async (token: string, teamSlug: string, force = false) => {
    if (!teamSlug) return [];

    if (!force && get().loadedTeamSlug === teamSlug && get().projects.length > 0) {
      return get().projects;
    }

    if (teamProjectsPromisesMap.has(teamSlug)) {
      return teamProjectsPromisesMap.get(teamSlug)!;
    }

    const promise = (async () => {
      set({ isLoading: true, error: null });
      try {
        const data = await teamsApi.getTeamProjects(token, teamSlug);
        const projects = data.projects || [];
        const currentActive = get().activeProject;

        let nextActive = currentActive
          ? projects.find((p) => p.id === currentActive.id || p.slug === currentActive.slug) || projects[0] || null
          : projects[0] || null;

        set({ projects, activeProject: nextActive, loadedTeamSlug: teamSlug, isLoading: false });
        return projects;
      } catch (err: any) {
        set({ error: err.message || "Failed to fetch projects", isLoading: false });
        return get().projects;
      } finally {
        teamProjectsPromisesMap.delete(teamSlug);
      }
    })();

    teamProjectsPromisesMap.set(teamSlug, promise);
    return promise;
  },

  createProject: async (
    token: string,
    teamSlug: string,
    name: string,
    description?: string
  ) => {
    set({ isLoading: true, error: null });
    try {
      const data = await teamsApi.createTeamProject(token, teamSlug, name, description);
      const newProj = data.project;
      const updated = [newProj, ...get().projects];
      set({ projects: updated, activeProject: newProj, isLoading: false });
      return newProj;
    } catch (err: any) {
      set({ error: err.message || "Failed to create project", isLoading: false });
      throw err;
    }
  },

  updateProject: async (
    token: string,
    projectIdOrSlug: string,
    updates: UpdateProjectInput
  ) => {
    set({ isLoading: true, error: null });
    try {
      const data = await projectsApi.updateProject(token, projectIdOrSlug, updates);
      const updatedProj = data.project;
      const updatedList = get().projects.map((p) =>
        p.id === updatedProj.id || p.slug === projectIdOrSlug ? { ...p, ...updatedProj } : p
      );
      set({
        projects: updatedList,
        activeProject:
          get().activeProject?.id === updatedProj.id || get().activeProject?.slug === projectIdOrSlug
            ? { ...get().activeProject, ...updatedProj }
            : get().activeProject,
        isLoading: false,
      });
      return updatedProj;
    } catch (err: any) {
      set({ error: err.message || "Failed to update project", isLoading: false });
      throw err;
    }
  },

  deleteProject: async (token: string, projectIdOrSlug: string) => {
    set({ isLoading: true, error: null });
    try {
      await projectsApi.deleteProject(token, projectIdOrSlug);
      const remaining = get().projects.filter(
        (p) => p.id !== projectIdOrSlug && p.slug !== projectIdOrSlug
      );
      set({
        projects: remaining,
        activeProject: remaining[0] || null,
        isLoading: false,
      });
      return true;
    } catch (err: any) {
      set({ error: err.message || "Failed to delete project", isLoading: false });
      throw err;
    }
  },

  fetchProjectDetails: async (token: string, projectIdOrSlug: string, force = false) => {
    if (!projectIdOrSlug) return null;

    const currentActive = get().activeProject;
    if (
      !force &&
      currentActive &&
      (currentActive.id === projectIdOrSlug || currentActive.slug === projectIdOrSlug) &&
      currentActive.repositories !== undefined
    ) {
      return currentActive;
    }

    if (projectDetailsPromisesMap.has(projectIdOrSlug)) {
      return projectDetailsPromisesMap.get(projectIdOrSlug)!;
    }

    const promise = (async () => {
      try {
        const data = await projectsApi.getProject(token, projectIdOrSlug);
        const projectWithDetails: Project = {
          ...data.project,
          repositories: data.repositories || [],
          latestBuild: data.builds?.[0] || null,
          repositoryCount: (data.repositories || []).length,
        };

        set((state) => ({
          activeProject: projectWithDetails,
          projects: state.projects.some((p) => p.id === projectWithDetails.id)
            ? state.projects.map((p) => (p.id === projectWithDetails.id ? projectWithDetails : p))
            : [projectWithDetails, ...state.projects],
        }));

        return projectWithDetails;
      } catch (err) {
        console.warn("Could not fetch project details:", err);
        return null;
      } finally {
        projectDetailsPromisesMap.delete(projectIdOrSlug);
      }
    })();

    projectDetailsPromisesMap.set(projectIdOrSlug, promise);
    return promise;
  },

  attachRepository: async (
    token: string,
    projectIdOrSlug: string,
    repositoryId: string
  ) => {
    try {
      const res = await projectsApi.attachRepository(token, projectIdOrSlug, repositoryId);
      if (res.repository) {
        // Refresh project details
        await get().fetchProjectDetails(token, projectIdOrSlug);
        return res.repository;
      }
      return null;
    } catch (err) {
      console.error("Failed to attach repository:", err);
      throw err;
    }
  },

  detachRepository: async (
    token: string,
    projectIdOrSlug: string,
    repositoryId: string
  ) => {
    try {
      const res = await projectsApi.detachRepository(token, projectIdOrSlug, repositoryId);
      if (res.success) {
        await get().fetchProjectDetails(token, projectIdOrSlug);
        return true;
      }
      return false;
    } catch (err) {
      console.error("Failed to detach repository:", err);
      return false;
    }
  },
}));
