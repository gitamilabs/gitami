"use client";

import React from "react";
import { useRepoStore } from "@/store/repoStore";
import { Github, ExternalLink, ShieldCheck, CheckCircle2 } from "lucide-react";

export const GitHubSettings: React.FC = () => {
  const { installations } = useRepoStore();

  return (
    <div className="space-y-6 animate-fade-in">
      {/* GitHub App Installations */}
      <section className="bg-[#11131a] border border-white/[0.06] rounded-xl p-6 space-y-5 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/[0.06] pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Github className="w-4 h-4 text-white" />
              <h2 className="text-sm font-bold text-white tracking-tight">GitHub App Installations</h2>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Authorized organizations and user accounts granted to the GitAmi GitHub App
            </p>
          </div>
          <a
            href="https://github.com/settings/installations"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.08] text-xs text-blue-400 hover:text-blue-300 hover:bg-white/[0.06] font-medium transition-all shrink-0"
          >
            <span>Manage on GitHub</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>

        {installations.length === 0 ? (
          <div className="p-8 text-center rounded-xl bg-[#0c0d12] border border-white/[0.06] space-y-2">
            <p className="text-xs text-zinc-400">No GitHub App installations found for this account.</p>
            <p className="text-[11px] text-zinc-500">
              Install the GitAmi GitHub App on your organization or repositories to enable PR reviews and webhooks.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {installations.map((inst) => (
              <div
                key={inst.id}
                className="flex items-center justify-between p-4 rounded-xl bg-[#0c0d12] border border-white/[0.06]"
              >
                <div className="flex items-center gap-3.5">
                  <div className="w-9 h-9 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-white shrink-0">
                    <Github className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-zinc-100">{inst.accountLogin}</p>
                    <p className="text-[11px] text-zinc-400 font-mono">
                      Type: <span className="text-zinc-300">{inst.accountType}</span> • Installation ID:{" "}
                      <span className="text-zinc-300">{inst.installationId}</span>
                    </p>
                  </div>
                </div>
                <span className="px-2.5 py-1 rounded-full text-[10px] font-mono font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3 h-3" />
                  Authorized
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Permissions Breakdown */}
      <section className="bg-[#11131a] border border-white/[0.06] rounded-xl p-6 space-y-4 shadow-sm">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-bold text-white tracking-tight">GitAmi GitHub App Capabilities</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <div className="p-3.5 rounded-xl bg-[#0c0d12] border border-white/[0.06] space-y-1">
            <p className="font-semibold text-zinc-200">Pull Request Reviews</p>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              Automated multi-perspective reviews, risk calculations, and architectural impact evaluations.
            </p>
          </div>
          <div className="p-3.5 rounded-xl bg-[#0c0d12] border border-white/[0.06] space-y-1">
            <p className="font-semibold text-zinc-200">Webhook Event Sync</p>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              Real-time push, PR opened/synchronized webhooks for incremental graph indexing.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};
