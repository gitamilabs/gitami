"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuthStore } from "../../../store/authStore";
import { useRepoStore } from "../../../store/repoStore";
import { useBuildStore } from "../../../store/buildStore";
import { useProjectStore } from "../../../store/projectStore";
import { prApi } from "../../../lib/api";
import { PRData, Build } from "../../../lib/types";
import { Sidebar } from "../../../components/layout/Sidebar";
import { TopBar } from "../../../components/layout/TopBar";
import { ProtectedRoute } from "../../../components/auth/ProtectedRoute";
import {
  Activity as ActivityIcon,
  GitPullRequest,
  FolderGit2,
  Hammer,
  RefreshCw,
  Clock,
  ArrowRight,
} from "lucide-react";

function formatRelativeTime(dateString?: string): string {
  if (!dateString) return "Recently";
  const diff = Date.now() - new Date(dateString).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

type FeedEntry =
  | { type: "repo_connected"; date: string; title: string; desc: string }
  | { type: "build_completed"; date: string; title: string; desc: string; build: Build }
  | { type: "pr_reviewed"; date: string; title: string; desc: string };

export default function WorkspaceActivityPage() {
  const params = useParams();
  const teamSlug = (params?.teamSlug as string) || "";

  const { token } = useAuthStore();
  const { connectedRepos, fetchConnectedRepos } = useRepoStore();
  const { builds } = useBuildStore();
  const { projects } = useProjectStore();

  const [prs, setPrs] = useState<PRData[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (token) {
      fetchConnectedRepos(token);
    }
  }, [token, fetchConnectedRepos]);

  const feed: FeedEntry[] = useMemo(() => {
    const entries: FeedEntry[] = [];

    for (const r of connectedRepos) {
      entries.push({
        type: "repo_connected",
        date: r.createdAt,
        title: `Repository connected: ${r.fullName}`,
        desc: `Default branch ${r.defaultBranch || "main"}`,
      });
    }

    for (const b of builds) {
      entries.push({
        type: "build_completed",
        date: b.completedAt || b.createdAt,
        title: `Build #${b.id.slice(0, 8)} ${b.status.toLowerCase()}`,
        desc: `${b.repositoryId} (${b.branch}) • ${b.stage}`,
        build: b,
      });
    }

    entries.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
    return entries;
  }, [connectedRepos, builds]);

  return (
    <ProtectedRoute>
      <div className="flex h-screen bg-[#0c0d12] text-zinc-100 overflow-hidden select-none">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
          <TopBar />
          <main className="flex-1 overflow-y-auto p-8 max-w-5xl w-full mx-auto space-y-6">
            <div className="pb-6 border-b border-white/[0.06]">
              <h1 className="text-xl font-bold text-white tracking-tight font-mono">
                Workspace Activity
              </h1>
              <p className="text-xs text-zinc-400 mt-1">
                Real-time audit log of repository connections, builds, and automated reviews.
              </p>
            </div>

            {feed.length === 0 ? (
              <div className="p-12 text-center border border-white/[0.06] rounded-xl bg-[#11131a] space-y-3">
                <ActivityIcon className="w-8 h-8 text-zinc-600 mx-auto" />
                <p className="text-xs text-zinc-400">No activity recorded yet in this workspace.</p>
              </div>
            ) : (
              <div className="border border-white/[0.06] rounded-xl overflow-hidden divide-y divide-white/[0.06] bg-[#11131a] font-mono text-xs">
                {feed.map((entry, idx) => (
                  <div
                    key={idx}
                    className="p-4 flex items-center justify-between hover:bg-white/[0.02] transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      {entry.type === "build_completed" ? (
                        <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                          <Hammer className="w-4 h-4" />
                        </div>
                      ) : (
                        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                          <FolderGit2 className="w-4 h-4" />
                        </div>
                      )}

                      <div>
                        <div className="text-white font-medium">{entry.title}</div>
                        <div className="text-[11px] text-zinc-500 mt-0.5">{entry.desc}</div>
                      </div>
                    </div>

                    <span className="text-[11px] text-zinc-500 shrink-0">
                      {formatRelativeTime(entry.date)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </main>
        </div>
      </div>
    </ProtectedRoute>
  );
}
