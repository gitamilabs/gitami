"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "../../../store/authStore";
import { useRepoStore } from "../../../store/repoStore";
import { prApi } from "../../../lib/api";
import { PRData } from "../../../lib/types";
import { formatTimeAgo } from "../../../lib/utils";
import {
  Activity,
  GitPullRequest,
  FolderGit2,
  ShieldCheck,
  ShieldAlert,
  RefreshCw,
} from "lucide-react";

type FeedEntry =
  | { type: "repo_connected"; date: string; repoFullName: string; repoId: string }
  | { type: "pr_reviewed"; date: string; pr: PRData };

function ActivityContent() {
  const { token } = useAuthStore();
  const { connectedRepos, fetchConnectedRepos } = useRepoStore();
  const [prs, setPrs] = useState<PRData[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const load = async () => {
    setIsLoading(true);
    try {
      if (token) await fetchConnectedRepos(token);
      const data = await prApi.listPullRequests(undefined, token || undefined);
      setPrs(data.pullRequests || []);
    } catch (err) {
      console.warn("Failed to load activity feed:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const feed: FeedEntry[] = useMemo(() => {
    const entries: FeedEntry[] = [];

    for (const r of connectedRepos) {
      entries.push({ type: "repo_connected", date: r.createdAt, repoFullName: r.fullName, repoId: r.id });
    }

    for (const pr of prs) {
      if (pr.review?.createdAt) {
        entries.push({ type: "pr_reviewed", date: pr.review.createdAt, pr });
      }
    }

    return entries.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  }, [connectedRepos, prs]);

  return (
    <div className="flex-1 flex flex-col">
      <header className="h-14 border-b border-zinc-800/80 px-6 flex items-center justify-between bg-[#0a0a0a]/50 backdrop-blur-md sticky top-0 z-20">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-semibold text-white flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-400" />
            Activity Logs
          </h1>
        </div>
        <button
          onClick={load}
          className="p-2 rounded-lg bg-[#0a0a0a] border border-zinc-800/80 text-zinc-400 hover:text-white hover:border-zinc-700 transition-colors cursor-pointer"
          title="Refresh"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
        </button>
      </header>

      <div className="flex-1 p-6 md:p-8 max-w-3xl w-full mx-auto space-y-6">
        <p className="text-xs text-zinc-500">
          A timeline of repository connections and AI PR review completions across your workspace.
        </p>

        {isLoading && feed.length === 0 ? (
          <div className="space-y-2">
            {[1, 2, 3].map((n) => (
              <div key={n} className="h-16 rounded-xl bg-[#0a0a0a] border border-zinc-800/80 animate-pulse" />
            ))}
          </div>
        ) : feed.length === 0 ? (
          <div className="text-center py-16 rounded-2xl bg-[#0a0a0a] border border-zinc-800/80 border-dashed space-y-3">
            <Activity className="w-10 h-10 text-zinc-600 mx-auto" />
            <h3 className="text-sm font-semibold text-white">No activity yet</h3>
            <p className="text-xs text-zinc-500 max-w-sm mx-auto">
              Connect a repository or run a PR review to see events show up here.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {feed.map((entry, i) => {
              if (entry.type === "repo_connected") {
                return (
                  <Link
                    key={`repo-${entry.repoId}-${i}`}
                    href={`/dashboard/projects/${encodeURIComponent(entry.repoId)}`}
                    className="flex items-center gap-3.5 p-4 rounded-xl bg-[#0a0a0a] border border-zinc-800/80 hover:border-zinc-700 transition-colors"
                  >
                    <div className="p-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 shrink-0">
                      <FolderGit2 className="w-4 h-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-zinc-200">
                        Connected <span className="font-semibold text-white">{entry.repoFullName}</span>
                      </p>
                    </div>
                    <span className="text-[11px] text-zinc-500 font-mono shrink-0">
                      {formatTimeAgo(entry.date)}
                    </span>
                  </Link>
                );
              }

              const pr = entry.pr;
              const isAccept = pr.review?.verdict === "ACCEPT";
              return (
                <Link
                  key={`pr-${pr.id}`}
                  href={`/prs?repoFullName=${encodeURIComponent(pr.repoFullName)}`}
                  className="flex items-center gap-3.5 p-4 rounded-xl bg-[#0a0a0a] border border-zinc-800/80 hover:border-zinc-700 transition-colors"
                >
                  <div
                    className={`p-2 rounded-lg border shrink-0 ${
                      isAccept
                        ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                        : "bg-amber-500/10 border-amber-500/20 text-amber-400"
                    }`}
                  >
                    {isAccept ? <ShieldCheck className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-zinc-200 truncate">
                      <GitPullRequest className="w-3 h-3 inline -mt-0.5 mr-1 text-zinc-500" />
                      AI review <span className="font-semibold text-white">{pr.review?.verdict}</span> on{" "}
                      <span className="font-mono">#{pr.prNumber}</span> in {pr.repoFullName}
                    </p>
                    <p className="text-[11px] text-zinc-500 truncate mt-0.5">{pr.title}</p>
                  </div>
                  <span className="text-[11px] text-zinc-500 font-mono shrink-0">
                    {formatTimeAgo(entry.date)}
                  </span>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ActivityPage() {
  return <ActivityContent />;
}
