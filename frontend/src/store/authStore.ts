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

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  isLoading: false,
  isInitialized: false,
  error: null,

  setToken: (token: string | null) => {
    if (typeof window !== "undefined") {
      if (token) {
        localStorage.setItem("sentinel_token", token);
      } else {
        localStorage.removeItem("sentinel_token");
      }
    }
    set({ token });
  },

  setUser: (user: User | null) => {
    set({ user });
  },

  initialize: async () => {
    if (typeof window === "undefined") return;

    const savedToken = localStorage.getItem("sentinel_token");
    if (!savedToken) {
      set({ isInitialized: true, token: null, user: null });
      return;
    }

    // Mock token support for testing / offline preview
    if (savedToken.startsWith("mock_")) {
      const mockUser: User = {
        id: "usr_mock_12345",
        username: "sentinel-dev",
        name: "Sentinel Developer",
        email: "developer@sentinel-ai.local",
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
      console.warn("Failed to restore session token:", err);
      // Only remove if unauthorized 401/403
      if (err.message && (err.message.includes("401") || err.message.includes("403") || err.message.includes("Unauthorized"))) {
        localStorage.removeItem("sentinel_token");
        set({ token: null, user: null, isLoading: false, isInitialized: true, error: err.message });
      } else {
        // Fallback placeholder profile for offline/dev resilience
        const fallbackUser: User = {
          id: "usr_session",
          username: "developer",
          name: "Developer",
          email: null,
          avatarUrl: "",
          githubId: "0000",
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        set({ token: savedToken, user: fallbackUser, isLoading: false, isInitialized: true, error: null });
      }
    }
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
      localStorage.removeItem("sentinel_token");
    }
    set({ token: null, user: null, error: null });
    if (typeof window !== "undefined") {
      window.location.href = "/";
    }
  },
}));
