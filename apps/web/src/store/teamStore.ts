import { create } from "zustand";
import { Team, UpdateTeamInput } from "../lib/types";
import { teamsApi } from "../lib/api";

interface TeamState {
  teams: Team[];
  activeTeam: Team | null;
  isLoading: boolean;
  error: string | null;
  fetchTeams: (token: string, force?: boolean) => Promise<Team[]>;
  createTeam: (token: string, name: string) => Promise<Team>;
  updateTeam: (token: string, teamSlug: string, updates: UpdateTeamInput) => Promise<Team>;
  deleteTeam: (token: string, teamSlug: string) => Promise<boolean>;
  setActiveTeam: (teamOrSlug: Team | string) => void;
}

let fetchTeamsPromise: Promise<Team[]> | null = null;

export const useTeamStore = create<TeamState>((set, get) => ({
  teams: [],
  activeTeam: null,
  isLoading: false,
  error: null,

  fetchTeams: async (token: string, force = false) => {
    // Return cached teams if already loaded and not forced
    if (!force && get().teams.length > 0) {
      return get().teams;
    }

    // Deduplicate in-flight requests
    if (fetchTeamsPromise) {
      return fetchTeamsPromise;
    }

    fetchTeamsPromise = (async () => {
      set({ isLoading: true, error: null });
      try {
        const data = await teamsApi.getTeams(token);
        const teams = data.teams || [];
        const currentActive = get().activeTeam;

        let nextActive = currentActive
          ? teams.find((t) => t.id === currentActive.id || t.slug === currentActive.slug) || teams[0] || null
          : teams[0] || null;

        if (typeof window !== "undefined" && nextActive?.slug) {
          document.cookie = `gitami_team=${nextActive.slug}; path=/; max-age=2592000; SameSite=Lax`;
        }

        set({ teams, activeTeam: nextActive, isLoading: false });
        return teams;
      } catch (err: any) {
        set({ error: err.message || "Failed to fetch teams", isLoading: false });
        return get().teams;
      } finally {
        fetchTeamsPromise = null;
      }
    })();

    return fetchTeamsPromise;
  },

  createTeam: async (token: string, name: string) => {
    set({ isLoading: true, error: null });
    try {
      const data = await teamsApi.createTeam(token, name);
      const created = data.team;
      const updated = [...get().teams, created];
      if (typeof window !== "undefined" && created?.slug) {
        document.cookie = `gitami_team=${created.slug}; path=/; max-age=2592000; SameSite=Lax`;
      }
      set({ teams: updated, activeTeam: created, isLoading: false });
      return created;
    } catch (err: any) {
      set({ error: err.message || "Failed to create team", isLoading: false });
      throw err;
    }
  },

  updateTeam: async (token: string, teamSlug: string, updates: UpdateTeamInput) => {
    set({ isLoading: true, error: null });
    try {
      const data = await teamsApi.updateTeam(token, teamSlug, updates);
      const updatedTeam = data.team;
      const updatedList = get().teams.map((t) => (t.slug === teamSlug ? updatedTeam : t));
      if (typeof window !== "undefined" && updatedTeam?.slug) {
        document.cookie = `gitami_team=${updatedTeam.slug}; path=/; max-age=2592000; SameSite=Lax`;
      }
      set({
        teams: updatedList,
        activeTeam: get().activeTeam?.slug === teamSlug ? updatedTeam : get().activeTeam,
        isLoading: false,
      });
      return updatedTeam;
    } catch (err: any) {
      set({ error: err.message || "Failed to update team", isLoading: false });
      throw err;
    }
  },

  deleteTeam: async (token: string, teamSlug: string) => {
    set({ isLoading: true, error: null });
    try {
      await teamsApi.deleteTeam(token, teamSlug);
      const refreshed = await teamsApi.getTeams(token);
      const teams = refreshed.teams || [];
      const nextActive = teams[0] || null;
      if (typeof window !== "undefined" && nextActive?.slug) {
        document.cookie = `gitami_team=${nextActive.slug}; path=/; max-age=2592000; SameSite=Lax`;
      }
      set({ teams, activeTeam: nextActive, isLoading: false });
      return true;
    } catch (err: any) {
      set({ error: err.message || "Failed to delete team", isLoading: false });
      throw err;
    }
  },

  setActiveTeam: (teamOrSlug: Team | string) => {
    const { teams } = get();
    if (typeof teamOrSlug === "string") {
      const found = teams.find((t) => t.slug === teamOrSlug || t.id === teamOrSlug);
      if (found) {
        if (typeof window !== "undefined") {
          document.cookie = `gitami_team=${found.slug}; path=/; max-age=2592000; SameSite=Lax`;
        }
        set({ activeTeam: found });
      }
    } else {
      if (typeof window !== "undefined" && teamOrSlug?.slug) {
        document.cookie = `gitami_team=${teamOrSlug.slug}; path=/; max-age=2592000; SameSite=Lax`;
      }
      set({ activeTeam: teamOrSlug });
    }
  },
}));

