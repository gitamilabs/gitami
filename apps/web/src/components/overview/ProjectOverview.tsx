"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "../../store/authStore";
import { useRepoStore } from "../../store/repoStore";
import { useProjectStore } from "../../store/projectStore";
import { useBuildStore } from "../../store/buildStore";
import { prApi } from "../../lib/api";
import { PRData, ConnectedRepository, Build } from "../../lib/types";
import { formatTimeAgo } from "../../lib/utils";
import {
  FolderGit2,
  GitBranch,
  Hammer,
  Share2,
  GitPullRequest,
  ArrowRight,
  Plus,
  Lock,
  Globe,
  CheckCircle2,
  Clock,
  AlertCircle,
  Sparkles,
  Zap,
  ChevronRight,
} from "lucide-react";

interface ProjectOverviewProps {
  onOpenConnectRepo?: () => void;
}

export const ProjectOverview: React.FC<ProjectOverviewProps> = ({ onOpenConnectRepo }) => {
  const { token } = useAuthStore();
  const {
    connectedRepos,
    indexedRepos,
    fetchConnectedRepos,
    fetchIndexedRepos,
    isLoading,
  } = useRepoStore();
  const { getActiveProject } = useProjectStore();
  const { getActiveBuilds, builds } = useBuildStore();

  const [prs, setPrs] = useState<PRData[]>([]);
  const [loadingPrs, setLoadingPrs] = useState(false);

  const activeProject = getActiveProject();
  const activeBuilds = getActiveBuilds();
  const projectBuilds = builds;

  // Initial fetch
  useEffect(() => {
    if (token) {
      fetchConnectedRepos(token);
      fetchIndexedRepos(token);
    }
  }, [token, fetchConnectedRepos, fetchIndexedRepos]);

  // Load pull requests for overview
  useEffect(() => {
    let isMounted = true;
    setLoadingPrs(true);
    prApi
      .listPullRequests(undefined, token || undefined)
      .then((data) => {
        if (isMounted) {
          setPrs(data.pullRequests || []);
          setLoadingPrs(false);
        }
      })
      .catch((err) => {
        console.warn("Could not fetch PRs for overview:", err);
        if (isMounted) setLoadingPrs(false);
      });

    return () => {
      isMounted = false;
    };
  }, [token]);

  // Determine repositories belonging to the active project
  const projectRepos: ConnectedRepository[] = React.useMemo(() => {
    if (activeProject?.repositories && activeProject.repositories.length > 0) {
      return activeProject.repositories;
    }
    return connectedRepos;
  }, [activeProject, connectedRepos]);

  const hasRepositories = projectRepos.length > 0;
  const runningBuild = activeBuilds[0];

  // --------------------------------------------------------------------------
  // ONBOARDING VIEW (Vercel-inspired simplicity for empty project)
  // --------------------------------------------------------------------------
  if (!hasRepositories && !isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 md:p-12 text-zinc-100 max-w-2xl mx-auto">
        <div className="w-full space-y-8 animate-fade-in">
          {/* Welcome Header */}
          <div className="space-y-3 text-center">
            <div className="w-12 h-12 rounded-xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-center mx-auto text-zinc-100">
              <FolderGit2 className="w-6 h-6 text-zinc-300" />
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Welcome to GitAmi
            </h1>
            <p className="text-sm text-zinc-400 max-w-md mx-auto leading-relaxed">
              Understand and maintain your codebase with continuous software intelligence.
            </p>
          </div>

          {/* Primary Action Card */}
          <div className="bg-[#11131a] border border-white/[0.06] rounded-xl p-6 space-y-5 shadow-sm">
            <div className="space-y-1">
              <h2 className="text-sm font-semibold text-white">Connect your repository</h2>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Connect your GitHub repositories via the GitAmi GitHub App. GitAmi indexes your codebase intelligence in the background immediately.
              </p>
            </div>

            <div className="pt-1 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
              <button
                onClick={onOpenConnectRepo}
                className="flex items-center justify-center gap-2 px-4 py-2.5 bg-white hover:bg-zinc-200 text-black text-xs font-semibold rounded-lg transition-colors cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                <span>Connect GitHub Repository</span>
              </button>
            </div>
          </div>

          {/* How It Works Explainer */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 text-xs">
            <div className="p-3.5 rounded-lg bg-[#0c0d12] border border-white/[0.06] space-y-1">
              <p className="font-semibold text-zinc-200">1. Instant Connection</p>
              <p className="text-[11px] text-zinc-400 leading-relaxed">
                Connect your repository with zero build setup or manual configuration.
              </p>
            </div>
            <div className="p-3.5 rounded-lg bg-[#0c0d12] border border-white/[0.06] space-y-1">
              <p className="font-semibold text-zinc-200">2. Background Index</p>
              <p className="text-[11px] text-zinc-400 leading-relaxed">
                Builds run asynchronously so you can navigate and use GitAmi right away.
              </p>
            </div>
            <div className="p-3.5 rounded-lg bg-[#0c0d12] border border-white/[0.06] space-y-1">
              <p className="font-semibold text-zinc-200">3. Live Intelligence</p>
              <p className="text-[11px] text-zinc-400 leading-relaxed">
                Explore AST call graphs, ask agent questions, and review pull requests.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // --------------------------------------------------------------------------
  // PROJECT OVERVIEW (With real repositories connected)
  // --------------------------------------------------------------------------
  return (
    <div className="flex-1 p-6 md:p-8 max-w-5xl w-full mx-auto space-y-6 text-zinc-100 animate-fade-in">
      {/* 1. Project Identity Card */}
      <div className="bg-[#11131a] border border-white/[0.06] rounded-xl p-6 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-white tracking-tight">
              {activeProject?.name || "Main Project"}
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-white/[0.04] text-zinc-400 border border-white/[0.06]">
              Project
            </span>
          </div>
          <p className="text-xs text-zinc-400">
            {activeProject?.description || "Software maintenance & codebase intelligence workspace"}
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={onOpenConnectRepo}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-100 hover:bg-white text-black text-xs font-semibold rounded-md transition-colors cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Connect Repository</span>
          </button>
        </div>
      </div>

      {/* 2. Active Background Build Notification Banner */}
      {runningBuild && (
        <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-500/20 flex items-center justify-between gap-4 text-xs animate-fade-in">
          <div className="flex items-center gap-3 min-w-0">
            <div className="p-2 rounded-lg bg-indigo-500/20 text-indigo-300">
              <Hammer className="w-4 h-4 animate-bounce" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white">Indexing Build in Progress</span>
                <span className="text-[10px] font-mono text-indigo-300 bg-indigo-500/20 px-1.5 py-0.2 rounded">
                  {runningBuild.id}
                </span>
              </div>
              <p className="text-[11px] text-indigo-200/80 mt-0.5 truncate">
                {runningBuild.stage} for repository <span className="font-mono text-white">{runningBuild.repositoryId}</span>. Running in background.
              </p>
            </div>
          </div>

          <Link
            href="/builds"
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors shrink-0 text-xs"
          >
            <span>View Builds</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      )}

      {/* 3. Repositories Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 font-mono">
              Connected Repositories ({projectRepos.length})
            </h2>
          </div>
          <Link
            href="/repositories"
            className="text-xs text-zinc-400 hover:text-white flex items-center gap-1 font-medium transition-colors"
          >
            <span>Manage Repositories</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="bg-[#11131a] border border-white/[0.06] rounded-xl divide-y divide-white/[0.06] overflow-hidden">
          {projectRepos.slice(0, 4).map((repo) => {
            const isIndexed = indexedRepos.includes(repo.name) || indexedRepos.includes(repo.fullName);
            const isCurrentlyBuilding = activeBuilds.some(
              (b) => b.repositoryId === repo.id
            );

            return (
              <div
                key={repo.id}
                className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-white/[0.02] transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center text-zinc-300 shrink-0">
                    <FolderGit2 className="w-4 h-4 text-zinc-400" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-zinc-100 truncate">{repo.fullName}</span>
                      {repo.isPrivate ? (
                        <Lock className="w-3 h-3 text-zinc-500" />
                      ) : (
                        <Globe className="w-3 h-3 text-zinc-500" />
                      )}
                    </div>
                    <p className="text-[11px] text-zinc-500 font-mono mt-0.5 flex items-center gap-2">
                      <GitBranch className="w-3 h-3" />
                      <span>{repo.defaultBranch || "main"}</span>
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3 self-end sm:self-auto">
                  {isCurrentlyBuilding ? (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 flex items-center gap-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
                      Indexing in background...
                    </span>
                  ) : isIndexed ? (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" />
                      Indexed
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-white/[0.06] text-zinc-400">
                      Not Indexed
                    </span>
                  )}

                  <Link
                    href={`/graph?repo=${encodeURIComponent(repo.fullName)}`}
                    className="text-xs text-zinc-400 hover:text-white px-2.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-colors"
                  >
                    Graph
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. Two-Column Activity: Recent Builds & Recent PR Reviews */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Recent Builds */}
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 font-mono flex items-center gap-1.5">
              <Hammer className="w-3.5 h-3.5 text-zinc-400" />
              <span>Recent Builds</span>
            </h2>
            <Link
              href="/builds"
              className="text-xs text-zinc-400 hover:text-white flex items-center gap-1 font-medium transition-colors"
            >
              <span>All Builds</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="bg-[#11131a] border border-white/[0.06] rounded-xl divide-y divide-white/[0.06] overflow-hidden min-h-[140px]">
            {projectBuilds.length === 0 ? (
              <div className="p-6 text-center text-xs text-zinc-500 space-y-1">
                <p>No builds recorded for this project yet.</p>
                <p className="text-[11px] text-zinc-600">Trigger repository indexing to create a build.</p>
              </div>
            ) : (
              projectBuilds.slice(0, 3).map((b: Build) => (
                <div key={b.id} className="p-3.5 flex items-center justify-between gap-3 text-xs">
                  <div className="min-w-0 space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-zinc-300 font-medium">{b.id}</span>
                      <span
                        className={`text-[10px] font-mono px-1.5 py-0.2 rounded ${
                          b.status === "COMPLETED"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : b.status === "RUNNING"
                            ? "bg-indigo-500/10 text-indigo-300 border border-indigo-500/20"
                            : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                        }`}
                      >
                        {b.status}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-500 font-mono truncate">
                      {b.repositoryId} • {b.branch}
                    </p>
                  </div>
                  <span className="text-[11px] text-zinc-500 shrink-0 font-mono">
                    {formatTimeAgo(b.createdAt)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Recent PR Reviews */}
        <div className="space-y-3">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 font-mono flex items-center gap-1.5">
              <GitPullRequest className="w-3.5 h-3.5 text-zinc-400" />
              <span>Recent PR Reviews</span>
            </h2>
            <Link
              href="/prs"
              className="text-xs text-zinc-400 hover:text-white flex items-center gap-1 font-medium transition-colors"
            >
              <span>All Reviews</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="bg-[#11131a] border border-white/[0.06] rounded-xl divide-y divide-white/[0.06] overflow-hidden min-h-[140px]">
            {loadingPrs ? (
              <div className="p-6 text-center text-xs text-zinc-500">Loading reviews...</div>
            ) : prs.length === 0 ? (
              <div className="p-6 text-center text-xs text-zinc-500 space-y-1">
                <p>No PR reviews yet.</p>
                <p className="text-[11px] text-zinc-600">Open or sync a pull request to run evaluation.</p>
              </div>
            ) : (
              prs.slice(0, 3).map((pr) => (
                <div key={pr.id} className="p-3.5 flex items-center justify-between gap-3 text-xs">
                  <div className="min-w-0 space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-zinc-400">#{pr.prNumber}</span>
                      <span className="text-zinc-200 font-medium truncate">{pr.title}</span>
                    </div>
                    <p className="text-[11px] text-zinc-500 font-mono truncate">
                      {pr.repoFullName} {pr.authorLogin ? `by ${pr.authorLogin}` : ""}
                    </p>
                  </div>
                  {pr.review ? (
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold shrink-0 ${
                        pr.review.verdict === "ACCEPT"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                      }`}
                    >
                      {pr.review.verdict}
                    </span>
                  ) : (
                    <span className="text-[10px] font-mono text-zinc-500 shrink-0">Pending</span>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
