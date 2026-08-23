"use client";

import React, { useEffect } from "react";
import { useAuthStore } from "../../store/authStore";
import { Button } from "../ui/Button";
import { Github, ShieldAlert, Loader2 } from "lucide-react";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { token, isInitialized, isLoading, login, initialize } = useAuthStore();

  useEffect(() => {
    if (!isInitialized) {
      initialize();
    }
  }, [isInitialized, initialize]);

  if (!isInitialized || isLoading) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
        <p className="text-sm text-slate-400 font-mono">Authenticating session with Sentinel...</p>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center p-6 text-center max-w-md mx-auto">
        <div className="w-16 h-16 rounded-3xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center mb-4 shadow-lg shadow-indigo-500/10">
          <ShieldAlert className="w-8 h-8 text-indigo-400" />
        </div>
        <h2 className="text-xl font-bold text-slate-100 mb-2">Authentication Required</h2>
        <p className="text-sm text-slate-400 mb-6 leading-relaxed">
          Please sign in with your GitHub account to access connected repositories, codebase analysis, and Agentic RAG chat.
        </p>
        <Button
          variant="glow"
          size="lg"
          leftIcon={<Github className="w-5 h-5" />}
          onClick={() => login()}
          className="w-full"
        >
          Sign in with GitHub
        </Button>
      </div>
    );
  }

  return <>{children}</>;
};
