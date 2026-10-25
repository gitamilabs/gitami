import { create } from "zustand";
import { User } from "../lib/types";
import { authApi } from "../lib/api";

interface AuthState {
  token: string | null;
  user: User | null;
  isLoading: boolean;
  isInitialized: boolean;
  error: string | null;
  setToken: (token: string | null) => void;
  setUser: (user: User | null) => void;
  initialize: () => Promise<void>;
  login: () => void;
  logout: () => Promise<void>;
  fetchUser: () => Promise<void>;
}

let initPromise: Promise<void> | null = null;

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  isLoading: false,
  isInitialized: false,
  error: null,

  setToken: (token: string | null) => {
    if (typeof window !== "undefined") {
      if (token) {
        localStorage.setItem("gitami_token", token);
        document.cookie = `gitami_token=${token}; path=/; max-age=2592000; SameSite=Lax`;
      } else {
        localStorage.removeItem("gitami_token");
        localStorage.removeItem("sentinel_token");
        document.cookie = "gitami_token=; path=/; max-age=0; SameSite=Lax";
      }
    }
    set({ token });
  },

  setUser: (user: User | null) => {
    set({ user });
  },

  initialize: async () => {
    if (typeof window === "undefined") return;

    if (get().isInitialized && get().user) {
      return;
    }

    if (initPromise) {
      return initPromise;
    }

    initPromise = (async () => {
      const savedToken = localStorage.getItem("gitami_token") || localStorage.getItem("sentinel_token");
      if (!savedToken) {
        document.cookie = "gitami_token=; path=/; max-age=0; SameSite=Lax";
        document.cookie = "gitami_team=; path=/; max-age=0; SameSite=Lax";
        set({ isInitialized: true, token: null, user: null });
        return;
      }

      // Mock token support for testing / offline preview
      if (savedToken.startsWith("mock_")) {
        const mockUser: User = {
          id: "usr_mock_12345",
          username: "gitami-dev",
          name: "GitAmi Developer",
          email: "developer@gitami.local",
          avatarUrl: "",
          githubId: "87654321",
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        set({ token: savedToken, user: mockUser, isInitialized: true, isLoading: false, error: null });
        return;
      }

      set({ token: savedToken, isLoading: true });
      try {
        const { user } = await authApi.getMe(savedToken);
        set({ user, isLoading: false, isInitialized: true, error: null });
      } catch (err: any) {
        console.warn("Session token invalid or expired. Resetting session:", err);
        localStorage.removeItem("gitami_token");
        localStorage.removeItem("sentinel_token");
        document.cookie = "gitami_token=; path=/; max-age=0; SameSite=Lax";
        document.cookie = "gitami_team=; path=/; max-age=0; SameSite=Lax";
        set({ token: null, user: null, isLoading: false, isInitialized: true, error: null });
      } finally {
        initPromise = null;
      }
    })();

    return initPromise;
  },

  fetchUser: async () => {
    const { token } = get();
    if (!token) return;

    if (token.startsWith("mock_")) return;

    set({ isLoading: true });
    try {
      const { user } = await authApi.getMe(token);
      set({ user, isLoading: false, error: null });
    } catch (err: any) {
      set({ isLoading: false, error: err.message });
    }
  },

  login: () => {
    if (typeof window !== "undefined") {
      window.location.href = authApi.getLoginUrl();
    }
  },

  logout: async () => {
    const { token } = get();
    if (token && !token.startsWith("mock_")) {
      try {
        await authApi.logout(token);
      } catch (err) {
        console.warn("Logout error:", err);
      }
    }
    if (typeof window !== "undefined") {
      localStorage.removeItem("gitami_token");
      localStorage.removeItem("sentinel_token");
      document.cookie = "gitami_token=; path=/; max-age=0; SameSite=Lax";
      document.cookie = "gitami_team=; path=/; max-age=0; SameSite=Lax";
    }
    set({ token: null, user: null, error: null });
    if (typeof window !== "undefined") {
      window.location.href = "/";
    }
  },
}));
