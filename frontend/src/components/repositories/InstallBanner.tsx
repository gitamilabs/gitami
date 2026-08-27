"use client";

import React, { useState } from "react";
import { useAuthStore } from "../../store/authStore";
import { useRepoStore } from "../../store/repoStore";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { Github, Sparkles, ExternalLink, ShieldCheck, Zap, Lock } from "lucide-react";

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
    <div className="relative rounded-3xl p-6 sm:p-8 bg-gradient-to-br from-indigo-950/90 via-slate-900/90 to-slate-950 border border-indigo-500/30 overflow-hidden shadow-2xl shadow-indigo-950/40">
      {/* Ambient gradient glow */}
      <div className="absolute -right-12 -top-12 w-72 h-72 bg-indigo-500/15 rounded-full blur-3xl pointer-events-none" />

      <div className="relative z-10 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
        <div className="space-y-3 max-w-xl">
          <div className="inline-flex items-center gap-2">
            <Badge variant="primary" size="sm" dot className="font-mono text-[10px]">
              GitHub App Integration
            </Badge>
            <Badge variant="success" size="sm" className="font-mono text-[10px]">
              Verified Webhooks
            </Badge>
          </div>

          <h2 className="text-xl sm:text-2xl font-black text-white tracking-tight">
            Connect Your GitHub Repositories
          </h2>
          <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
            Install the Sentinel GitHub App to give our AST parsing & AI Service secure read access to your repositories and automatic PR review webhooks.
          </p>

          <div className="flex flex-wrap gap-2 pt-1">
            <span className="flex items-center gap-1 text-[11px] font-mono text-slate-400 bg-slate-900/80 px-2.5 py-1 rounded-lg border border-slate-800">
              <Lock className="w-3 h-3 text-emerald-400" /> Read-Only Tokens
            </span>
            <span className="flex items-center gap-1 text-[11px] font-mono text-slate-400 bg-slate-900/80 px-2.5 py-1 rounded-lg border border-slate-800">
              <Zap className="w-3 h-3 text-cyan-400" /> Zero Disk Persistence
            </span>
            <span className="flex items-center gap-1 text-[11px] font-mono text-slate-400 bg-slate-900/80 px-2.5 py-1 rounded-lg border border-slate-800">
              <ShieldCheck className="w-3 h-3 text-indigo-400" /> HMAC SHA256 Webhook Sig
            </span>
          </div>
        </div>

        <Button
          variant="glow"
          size="lg"
          isLoading={loading}
          leftIcon={<Github className="w-5 h-5" />}
          rightIcon={<ExternalLink className="w-4 h-4 opacity-70" />}
          onClick={handleInstall}
          className="shrink-0 w-full sm:w-auto text-sm font-semibold"
        >
          Install Sentinel App
        </Button>
      </div>
    </div>
  );
};

