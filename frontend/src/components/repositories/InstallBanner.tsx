"use client";

import React, { useState } from "react";
import { useAuthStore } from "../../store/authStore";
import { useRepoStore } from "../../store/repoStore";
import { Button } from "../ui/Button";
import { Github, Sparkles, ExternalLink, ShieldCheck } from "lucide-react";

export const InstallBanner: React.FC = () => {
  const { token } = useAuthStore();
  const { getInstallUrl } = useRepoStore();
  const [loading, setLoading] = useState(false);

  const handleInstall = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const url = await getInstallUrl(token);
      window.location.href = url;
    } catch (err) {
      console.error("Failed to fetch GitHub App install URL:", err);
      setLoading(false);
    }
  };

  return (
    <div className="relative rounded-3xl p-6 sm:p-8 bg-gradient-to-br from-indigo-950/80 via-slate-900 to-slate-950 border border-indigo-500/30 overflow-hidden shadow-xl shadow-indigo-950/30">
      {/* Background glow circle */}
      <div className="absolute -right-12 -top-12 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="space-y-2 max-w-xl">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5" />
            <span>GitHub App Integration</span>
          </div>
          <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
            Connect Your GitHub Repositories
          </h2>
          <p className="text-sm text-slate-300 leading-relaxed">
            Install the Sentinel GitHub App to give our AST parsing & AI Service secure read access to your repositories and automatic PR review webhooks.
          </p>
        </div>

        <Button
          variant="glow"
          size="lg"
          isLoading={loading}
          leftIcon={<Github className="w-5 h-5" />}
          rightIcon={<ExternalLink className="w-4 h-4 opacity-70" />}
          onClick={handleInstall}
          className="shrink-0 w-full sm:w-auto"
        >
          Install Sentinel App
        </Button>
      </div>
    </div>
  );
};
