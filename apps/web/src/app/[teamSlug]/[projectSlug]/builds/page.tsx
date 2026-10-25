"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  GitBranch,
  GitCommit,
  RotateCcw,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Trash2,
  Loader2,
  Search,
  Play,
  Copy,
  Check,
  ArrowUpRight,
  Folder,
  Clock,
  RefreshCw,
  FolderGit2,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { useProjectStore } from "@/store/projectStore";
import { useBuildStore } from "@/store/buildStore";
import { Build, BuildStage, ConnectedRepository } from "@/lib/types";

function formatDuration(
  startedAt?: string | null,
  completedAt?: string | null,
  seconds?: number
): string {
  if (seconds && seconds > 0) {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  }
  if (!startedAt) return "—";
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const diffSec = Math.max(0, Math.floor((end - start) / 1000));
  if (diffSec < 60) return `${diffSec}s`;
  return `${Math.floor(diffSec / 60)}m ${diffSec % 60}s`;
}

function formatRelativeTime(dateString?: string): string {
  if (!dateString) return "Recently";
  const diff = Date.now() - new Date(dateString).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function formatTimestamp(dateString?: string): string {
  if (!dateString) return "—";
  return new Date(dateString).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

const DEFAULT_STAGES: BuildStage[] = [
  { key: "SNAPSHOT", name: "Repository Snapshot", status: "QUEUED" },
  { key: "DISCOVERY", name: "File Discovery & Scoping", status: "QUEUED" },
  { key: "AST_ANALYSIS", name: "AST Symbol Analysis", status: "QUEUED" },
  { key: "GRAPH_INDEXING", name: "Knowledge Graph Linking", status: "QUEUED" },
  { key: "SEMANTIC_INDEXING", name: "Semantic Vector Embeddings", status: "QUEUED" },
  { key: "VALIDATION", name: "Graph Validation & Integrity", status: "QUEUED" },
];

export default function BuildsPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const teamSlug = (params?.teamSlug as string) || "";
  const projectSlug = (params?.projectSlug as string) || "";
  const repoQuery = searchParams.get("repo");

  const { token } = useAuthStore();
  const { getActiveProject, fetchProjectDetails } = useProjectStore();
  const {
    builds,
    fetchProjectBuilds,
    startBuild,
    cancelBuild,
    deleteBuild,
  } = useBuildStore();

  const activeProject = getActiveProject();

  // Filter & Search states
  const [statusFilter, setStatusFilter] = useState<
    "ALL" | "RUNNING" | "COMPLETED" | "FAILED"
  >("ALL");
  const [repoFilter, setRepoFilter] = useState<string>(repoQuery || "ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedBuildId, setSelectedBuildId] = useState<string | null>(null);

  // Action states
  const [isRetrying, setIsRetrying] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [copiedCommit, setCopiedCommit] = useState(false);

  // Trigger modal state
  const [isTriggerModalOpen, setIsTriggerModalOpen] = useState(false);
  const [triggerRepoId, setTriggerRepoId] = useState("");
  const [triggerBranch, setTriggerBranch] = useState("");
  const [isStartingBuild, setIsStartingBuild] = useState(false);

  const repos = useMemo(() => {
    return activeProject?.repositories || [];
  }, [activeProject]);

  // Initial load
  useEffect(() => {
    if (token && projectSlug) {
      fetchProjectDetails(token, projectSlug);
    }
  }, [token, projectSlug, fetchProjectDetails]);

  useEffect(() => {
    if (token && activeProject) {
      fetchProjectBuilds(token, activeProject.id);
    }
  }, [token, activeProject, fetchProjectBuilds]);

  // Auto-polling when active builds exist
  useEffect(() => {
    if (!token || !activeProject) return;

    const hasActiveBuild = builds.some(
      (b) => b.status === "RUNNING" || b.status === "QUEUED"
    );

    if (!hasActiveBuild) return;

    const interval = setInterval(() => {
      fetchProjectBuilds(token, activeProject.id);
    }, 2500);

    return () => clearInterval(interval);
  }, [token, activeProject, builds, fetchProjectBuilds]);

  // Strict sorting by recency (newest createdAt first)
  const sortedBuilds = useMemo(() => {
    return [...builds].sort((a, b) => {
      const timeA = new Date(a.createdAt || 0).getTime();
      const timeB = new Date(b.createdAt || 0).getTime();
      return timeB - timeA;
    });
  }, [builds]);

  // Filtered builds
  const filteredBuilds = useMemo(() => {
    return sortedBuilds.filter((build) => {
      // Status filter
      if (statusFilter === "RUNNING") {
        if (build.status !== "RUNNING" && build.status !== "QUEUED") return false;
      } else if (statusFilter === "COMPLETED") {
        if (build.status !== "COMPLETED") return false;
      } else if (statusFilter === "FAILED") {
        if (build.status !== "FAILED" && build.status !== "CANCELLED") return false;
      }

      // Repository filter
      if (repoFilter !== "ALL") {
        const repoMatches =
          build.repositoryId === repoFilter ||
          build.repositoryId?.toLowerCase().includes(repoFilter.toLowerCase());
        if (!repoMatches) return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        const matchesBranch = build.branch?.toLowerCase().includes(query);
        const matchesSha = build.targetCommitSha?.toLowerCase().includes(query);
        const matchesRepo = build.repositoryId?.toLowerCase().includes(query);
        const matchesId = build.id?.toLowerCase().includes(query);
        if (!matchesBranch && !matchesSha && !matchesRepo && !matchesId) {
          return false;
        }
      }

      return true;
    });
  }, [sortedBuilds, statusFilter, repoFilter, searchQuery]);

  // Status counts for badge tabs
  const counts = useMemo(() => {
    const active = sortedBuilds.filter(
      (b) => b.status === "RUNNING" || b.status === "QUEUED"
    ).length;
    const completed = sortedBuilds.filter((b) => b.status === "COMPLETED").length;
    const failed = sortedBuilds.filter(
      (b) => b.status === "FAILED" || b.status === "CANCELLED"
    ).length;
    return {
      all: sortedBuilds.length,
      active,
      completed,
      failed,
    };
  }, [sortedBuilds]);

  // Auto-select first build or keep selection in view
  useEffect(() => {
    if (filteredBuilds.length > 0) {
      if (!selectedBuildId || !filteredBuilds.some((b) => b.id === selectedBuildId)) {
        setSelectedBuildId(filteredBuilds[0].id);
      }
    } else {
      setSelectedBuildId(null);
    }
  }, [filteredBuilds, selectedBuildId]);

  const selectedBuild = useMemo(() => {
    return sortedBuilds.find((b) => b.id === selectedBuildId) || null;
  }, [sortedBuilds, selectedBuildId]);

  // Linked repository information for the selected build
  const selectedRepoObj = useMemo(() => {
    if (!selectedBuild || !repos.length) return null;
    return (
      repos.find(
        (r) =>
          r.fullName?.toLowerCase() === selectedBuild.repositoryId?.toLowerCase() ||
          r.name?.toLowerCase() === selectedBuild.repositoryId?.toLowerCase() ||
          r.id === selectedBuild.repositoryId
      ) || null
    );
  }, [selectedBuild, repos]);

  const handleManualRefresh = async () => {
    if (!token || !activeProject) return;
    setIsRefreshing(true);
    try {
      await fetchProjectBuilds(token, activeProject.id);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleCopySha = (sha: string) => {
    navigator.clipboard.writeText(sha);
    setCopiedCommit(true);
    setTimeout(() => setCopiedCommit(false), 2000);
  };

  const handleOpenTriggerModal = () => {
    if (repos.length > 0) {
      const defaultRepo = repos[0];
      setTriggerRepoId(defaultRepo.id);
      setTriggerBranch(defaultRepo.defaultBranch || "main");
    }
    setIsTriggerModalOpen(true);
  };

  const handleTriggerBuild = async () => {
    if (!token || !activeProject || !triggerRepoId) return;
    setIsStartingBuild(true);
    try {
      const newBuild = await startBuild(
        token,
        activeProject.id,
        triggerRepoId,
        triggerBranch || "main"
      );
      setIsTriggerModalOpen(false);
      setSelectedBuildId(newBuild.id);
    } catch (err) {
      console.error("Failed to start build:", err);
    } finally {
      setIsStartingBuild(false);
    }
  };

  const handleRetry = async () => {
    if (!token || !activeProject || !selectedBuild) return;
    setIsRetrying(true);
    try {
      const repoId = selectedRepoObj ? selectedRepoObj.id : selectedBuild.repositoryId;
      const newBuild = await startBuild(
        token,
        activeProject.id,
        repoId,
        selectedBuild.branch
      );
      setSelectedBuildId(newBuild.id);
    } catch (err) {
      console.error("Failed to retry build:", err);
    } finally {
      setIsRetrying(false);
    }
  };

  const handleCancel = async () => {
    if (!token || !selectedBuild) return;
    setIsCancelling(true);
    try {
      await cancelBuild(token, selectedBuild.id);
      if (activeProject) {
        await fetchProjectBuilds(token, activeProject.id);
      }
    } catch (err) {
      console.error("Failed to cancel build:", err);
    } finally {
      setIsCancelling(false);
    }
  };

  const handleDelete = async () => {
    if (!token || !selectedBuild) return;
    const confirmText = `Delete build #${selectedBuild.id.slice(0, 8)}?`;
    if (!window.confirm(confirmText)) return;
    setIsDeleting(true);
    try {
      await deleteBuild(token, selectedBuild.id);
      setSelectedBuildId(null);
    } catch (err) {
      console.error("Failed to delete build:", err);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-6xl w-full mx-auto space-y-6 text-zinc-200">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-white/[0.06]">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-white tracking-tight">
              Builds
            </h1>
            {counts.active > 0 && (
              <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                {counts.active} active
              </span>
            )}
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Indexing runs, AST parsing pipelines, and knowledge graph sync history.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleManualRefresh}
            disabled={isRefreshing}
            className="p-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] border border-white/[0.06] transition-colors cursor-pointer"
            title="Refresh builds"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-white" : ""}`}
            />
          </button>

          {repos.length > 0 && (
            <button
              onClick={handleOpenTriggerModal}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-white hover:bg-zinc-200 text-black rounded-lg text-xs font-medium transition-all shadow-sm cursor-pointer"
            >
              <Play className="w-3 h-3 fill-black" />
              <span>Trigger Build</span>
            </button>
          )}
        </div>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Status Filter Tabs */}
        <div className="flex items-center gap-1 p-1 rounded-lg bg-white/[0.03] border border-white/[0.06] self-start">
          <button
            onClick={() => setStatusFilter("ALL")}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
              statusFilter === "ALL"
                ? "bg-white/[0.08] text-white shadow-sm"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            All
            <span className="ml-1.5 text-[10px] text-zinc-500">
              {counts.all}
            </span>
          </button>
          <button
            onClick={() => setStatusFilter("RUNNING")}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
              statusFilter === "RUNNING"
                ? "bg-white/[0.08] text-white shadow-sm"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Building
            {counts.active > 0 && (
              <span className="ml-1.5 px-1 rounded-full text-[10px] bg-blue-500/20 text-blue-400 font-semibold">
                {counts.active}
              </span>
            )}
          </button>
          <button
            onClick={() => setStatusFilter("COMPLETED")}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
              statusFilter === "COMPLETED"
                ? "bg-white/[0.08] text-white shadow-sm"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Completed
            <span className="ml-1.5 text-[10px] text-zinc-500">
              {counts.completed}
            </span>
          </button>
          <button
            onClick={() => setStatusFilter("FAILED")}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
              statusFilter === "FAILED"
                ? "bg-white/[0.08] text-white shadow-sm"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Failed
            <span className="ml-1.5 text-[10px] text-zinc-500">
              {counts.failed}
            </span>
          </button>
        </div>

        {/* Search & Repository Filter */}
        <div className="flex items-center gap-2">
          {/* Repository Dropdown */}
          {repos.length > 1 && (
            <select
              value={repoFilter}
              onChange={(e) => setRepoFilter(e.target.value)}
              className="px-2.5 py-1.5 bg-white/[0.03] hover:bg-white/[0.05] border border-white/[0.08] rounded-lg text-xs text-zinc-300 focus:outline-none focus:border-white/20 transition-colors cursor-pointer"
            >
              <option value="ALL" className="bg-[#12131a] text-zinc-300">
                All Repositories
              </option>
              {repos.map((r) => (
                <option
                  key={r.id}
                  value={r.fullName || r.name}
                  className="bg-[#12131a] text-zinc-300"
                >
                  {r.name || r.fullName}
                  {r.rootDirectory ? ` (${r.rootDirectory})` : ""}
                </option>
              ))}
            </select>
          )}

          {/* Search Input */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter by branch, commit, ID..."
              className="w-48 sm:w-60 pl-8 pr-3 py-1.5 bg-white/[0.03] border border-white/[0.08] rounded-lg text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-white/20 focus:bg-white/[0.05] transition-all"
            />
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {sortedBuilds.length === 0 ? (
        <div className="py-20 text-center space-y-4 max-w-sm mx-auto">
          <div className="w-12 h-12 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mx-auto text-zinc-400">
            <FolderGit2 className="w-5 h-5 text-zinc-400" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-white">No builds recorded yet</h3>
            <p className="text-xs text-zinc-500 mt-1">
              Trigger your first indexing run to extract code symbols and generate your software knowledge graph.
            </p>
          </div>
          {repos.length > 0 && (
            <button
              onClick={handleOpenTriggerModal}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-white hover:bg-zinc-200 text-black rounded-lg text-xs font-medium transition-colors cursor-pointer"
            >
              <Play className="w-3 h-3 fill-black" />
              <span>Trigger Initial Build</span>
            </button>
          )}
        </div>
      ) : filteredBuilds.length === 0 ? (
        <div className="py-16 text-center space-y-3">
          <p className="text-xs text-zinc-400">
            No builds found matching your current filter.
          </p>
          <button
            onClick={() => {
              setStatusFilter("ALL");
              setRepoFilter("ALL");
              setSearchQuery("");
            }}
            className="text-xs text-zinc-300 hover:text-white underline underline-offset-4 cursor-pointer"
          >
            Clear all filters
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Build List */}
          <div className="lg:col-span-5 space-y-2">
            <div className="flex items-center justify-between px-1 text-[11px] font-medium text-zinc-500 uppercase tracking-wider">
              <span>Runs ({filteredBuilds.length})</span>
              <span>Duration</span>
            </div>

            <div className="rounded-xl border border-white/[0.06] bg-[#0b0c10] divide-y divide-white/[0.04] overflow-hidden">
              {filteredBuilds.map((build) => {
                const isSelected = selectedBuild?.id === build.id;
                const isRunning =
                  build.status === "RUNNING" || build.status === "QUEUED";
                const isFailed =
                  build.status === "FAILED" || build.status === "CANCELLED";
                const isCompleted = build.status === "COMPLETED";

                const repoName =
                  build.repositoryId?.split("/").pop() || build.repositoryId;

                return (
                  <button
                    key={build.id}
                    onClick={() => setSelectedBuildId(build.id)}
                    className={`w-full p-3.5 text-left transition-all flex items-start justify-between gap-3 cursor-pointer group ${
                      isSelected
                        ? "bg-white/[0.06] text-white"
                        : "hover:bg-white/[0.02] text-zinc-300"
                    }`}
                  >
                    <div className="flex items-start gap-3 min-w-0">
                      {/* Status Icon */}
                      <div className="pt-0.5 shrink-0">
                        {isRunning ? (
                          <div className="w-5 h-5 rounded-md bg-blue-500/10 border border-blue-500/30 flex items-center justify-center text-blue-400">
                            <Loader2 className="w-3 h-3 animate-spin" />
                          </div>
                        ) : isCompleted ? (
                          <div className="w-5 h-5 rounded-md bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                            <CheckCircle2 className="w-3 h-3" />
                          </div>
                        ) : (
                          <div className="w-5 h-5 rounded-md bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
                            <XCircle className="w-3 h-3" />
                          </div>
                        )}
                      </div>

                      {/* Info */}
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-white font-mono">
                            #{build.id.slice(0, 7)}
                          </span>
                          <span
                            className={`text-[10px] px-1.5 py-0.2 rounded font-medium ${
                              isCompleted
                                ? "bg-emerald-500/10 text-emerald-400"
                                : isRunning
                                ? "bg-blue-500/10 text-blue-400 animate-pulse"
                                : "bg-rose-500/10 text-rose-400"
                            }`}
                          >
                            {build.status.toLowerCase()}
                          </span>
                        </div>

                        <div className="flex items-center gap-1.5 text-xs text-zinc-400 mt-1 truncate">
                          <span className="text-zinc-300 font-medium truncate">
                            {repoName}
                          </span>
                          <span className="text-zinc-600">•</span>
                          <span className="inline-flex items-center gap-1 text-zinc-400 font-mono text-[11px] truncate">
                            <GitBranch className="w-2.5 h-2.5 text-zinc-500 shrink-0" />
                            {build.branch || "main"}
                          </span>
                        </div>

                        <div className="text-[11px] text-zinc-500 mt-1">
                          {formatRelativeTime(build.createdAt)}
                        </div>
                      </div>
                    </div>

                    <div className="text-right shrink-0 pt-0.5">
                      <span className="text-xs font-mono text-zinc-400">
                        {formatDuration(
                          build.startedAt,
                          build.completedAt,
                          build.stats?.duration_seconds
                        )}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right Column: Build Details Inspector */}
          {selectedBuild ? (
            <div className="lg:col-span-7 space-y-6">
              {/* Header Box */}
              <div className="p-5 rounded-xl border border-white/[0.06] bg-[#0c0d12] space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2.5">
                      <h2 className="text-base font-semibold text-white font-mono">
                        Build #{selectedBuild.id.slice(0, 8)}
                      </h2>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          selectedBuild.status === "COMPLETED"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : selectedBuild.status === "RUNNING" ||
                              selectedBuild.status === "QUEUED"
                            ? "bg-blue-500/10 text-blue-400 border border-blue-500/20 animate-pulse"
                            : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                        }`}
                      >
                        {selectedBuild.status}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-500 mt-1">
                      Triggered {formatTimestamp(selectedBuild.createdAt)}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    {selectedBuild.status === "COMPLETED" && (
                      <Link
                        href={`/${teamSlug}/${projectSlug}/graph?repo=${encodeURIComponent(
                          selectedBuild.repositoryId
                        )}`}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-zinc-300 hover:text-white border border-white/[0.08] text-xs font-medium transition-colors"
                      >
                        <span>View Graph</span>
                        <ArrowUpRight className="w-3.5 h-3.5 text-zinc-400" />
                      </Link>
                    )}

                    {(selectedBuild.status === "RUNNING" ||
                      selectedBuild.status === "QUEUED") && (
                      <button
                        onClick={handleCancel}
                        disabled={isCancelling}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-medium transition-colors cursor-pointer"
                      >
                        {isCancelling ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <XCircle className="w-3.5 h-3.5" />
                        )}
                        <span>Cancel</span>
                      </button>
                    )}

                    <button
                      onClick={handleRetry}
                      disabled={isRetrying || isCancelling || isDeleting}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-zinc-200 text-black text-xs font-medium transition-colors cursor-pointer disabled:opacity-50"
                    >
                      {isRetrying ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <RotateCcw className="w-3.5 h-3.5" />
                      )}
                      <span>
                        {selectedBuild.status === "FAILED" ? "Retry" : "Re-run"}
                      </span>
                    </button>

                    {selectedBuild.status !== "RUNNING" &&
                      selectedBuild.status !== "QUEUED" && (
                        <button
                          onClick={handleDelete}
                          disabled={isDeleting || isRetrying}
                          className="p-2 rounded-lg text-zinc-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors cursor-pointer"
                          title="Delete build record"
                        >
                          {isDeleting ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="w-3.5 h-3.5" />
                          )}
                        </button>
                      )}
                  </div>
                </div>

                {/* Metadata Pills */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-3 border-t border-white/[0.04] text-xs">
                  <div>
                    <span className="text-[11px] text-zinc-500 block">Repository</span>
                    <span className="text-zinc-200 font-medium truncate block mt-0.5">
                      {selectedBuild.repositoryId}
                    </span>
                    {selectedRepoObj?.rootDirectory && (
                      <span className="inline-flex items-center gap-1 mt-1 px-1.5 py-0.5 rounded text-[10px] bg-white/[0.04] text-zinc-400 font-mono">
                        <Folder className="w-2.5 h-2.5 text-zinc-500" />
                        {selectedRepoObj.rootDirectory}
                      </span>
                    )}
                  </div>

                  <div>
                    <span className="text-[11px] text-zinc-500 block">Branch</span>
                    <span className="text-zinc-200 font-mono inline-flex items-center gap-1 mt-0.5">
                      <GitBranch className="w-3 h-3 text-zinc-500" />
                      {selectedBuild.branch || "main"}
                    </span>
                  </div>

                  <div>
                    <span className="text-[11px] text-zinc-500 block">Commit</span>
                    <div className="flex items-center gap-1 mt-0.5">
                      <span className="text-zinc-300 font-mono text-[11px]">
                        {selectedBuild.targetCommitSha
                          ? selectedBuild.targetCommitSha.slice(0, 7)
                          : "HEAD"}
                      </span>
                      {selectedBuild.targetCommitSha && (
                        <button
                          onClick={() => handleCopySha(selectedBuild.targetCommitSha)}
                          className="p-1 rounded text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer"
                          title="Copy commit SHA"
                        >
                          {copiedCommit ? (
                            <Check className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Error Callout */}
              {selectedBuild.error && (
                <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-800/30 text-rose-300 text-xs space-y-2">
                  <div className="flex items-center gap-2 font-medium text-rose-200">
                    <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                    <span>Pipeline failure</span>
                  </div>
                  <pre className="p-3 rounded-lg bg-black/40 border border-rose-900/40 text-[11px] text-rose-200/90 font-mono overflow-x-auto whitespace-pre-wrap">
                    {selectedBuild.error}
                  </pre>
                </div>
              )}

              {/* Stage Stepper */}
              <div className="p-5 rounded-xl border border-white/[0.06] bg-[#0c0d12] space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold text-white uppercase tracking-wider">
                    Pipeline Stages
                  </h3>
                  <span className="text-[11px] text-zinc-500 font-mono">
                    {selectedBuild.stages?.filter((s) => s.status === "COMPLETED").length || 0} of {selectedBuild.stages?.length || DEFAULT_STAGES.length} completed
                  </span>
                </div>

                <div className="space-y-3">
                  {(selectedBuild.stages || DEFAULT_STAGES).map((stage, idx) => {
                    const isDone = stage.status === "COMPLETED";
                    const isRunning = stage.status === "RUNNING";
                    const isFailed = stage.status === "FAILED";

                    return (
                      <div
                        key={stage.key || idx}
                        className="flex items-center justify-between p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                      >
                        <div className="flex items-center gap-3">
                          <div className="shrink-0">
                            {isDone ? (
                              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                            ) : isRunning ? (
                              <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                            ) : isFailed ? (
                              <XCircle className="w-4 h-4 text-rose-400" />
                            ) : (
                              <div className="w-4 h-4 rounded-full border border-zinc-700 bg-zinc-900" />
                            )}
                          </div>
                          <div>
                            <span
                              className={`text-xs font-medium block ${
                                isDone
                                  ? "text-zinc-200"
                                  : isRunning
                                  ? "text-blue-300 font-semibold"
                                  : isFailed
                                  ? "text-rose-300"
                                  : "text-zinc-500"
                              }`}
                            >
                              {stage.name}
                            </span>
                          </div>
                        </div>

                        <span
                          className={`text-[11px] font-mono px-2 py-0.5 rounded text-right ${
                            isDone
                              ? "text-emerald-400/90"
                              : isRunning
                              ? "text-blue-400 animate-pulse font-semibold"
                              : isFailed
                              ? "text-rose-400 font-semibold"
                              : "text-zinc-600"
                          }`}
                        >
                          {stage.status.toLowerCase()}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Indexed Metrics */}
              {selectedBuild.stats && (
                <div className="p-5 rounded-xl border border-white/[0.06] bg-[#0c0d12] space-y-4">
                  <h3 className="text-xs font-semibold text-white uppercase tracking-wider">
                    Indexed Metrics
                  </h3>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <span className="text-[11px] text-zinc-500 block">Files Parsed</span>
                      <span className="text-base font-semibold text-white font-mono mt-1 block">
                        {selectedBuild.stats.files_parsed?.toLocaleString() || 0}
                      </span>
                    </div>

                    <div className="p-3.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <span className="text-[11px] text-zinc-500 block">Symbols & Entities</span>
                      <span className="text-base font-semibold text-white font-mono mt-1 block">
                        {selectedBuild.stats.symbols_parsed?.toLocaleString() || 0}
                      </span>
                    </div>

                    <div className="p-3.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <span className="text-[11px] text-zinc-500 block">Relationships</span>
                      <span className="text-base font-semibold text-white font-mono mt-1 block">
                        {selectedBuild.stats.edges_count?.toLocaleString() || 0}
                      </span>
                    </div>

                    <div className="p-3.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <span className="text-[11px] text-zinc-500 block">Execution Time</span>
                      <span className="text-base font-semibold text-white font-mono mt-1 block">
                        {selectedBuild.stats.duration_seconds
                          ? `${selectedBuild.stats.duration_seconds}s`
                          : "—"}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>
      )}

      {/* Trigger Build Modal */}
      {isTriggerModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-md rounded-xl border border-white/[0.08] bg-[#0f1016] shadow-2xl overflow-hidden">
            <div className="p-5 border-b border-white/[0.06] flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">Trigger Index Build</h3>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Start durable AST analysis and software graph synchronization.
                </p>
              </div>
              <button
                onClick={() => setIsTriggerModalOpen(false)}
                className="text-zinc-500 hover:text-zinc-300 text-xs p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                  Select Repository
                </label>
                <select
                  value={triggerRepoId}
                  onChange={(e) => {
                    setTriggerRepoId(e.target.value);
                    const matching = repos.find((r) => r.id === e.target.value);
                    if (matching) {
                      setTriggerBranch(matching.defaultBranch || "main");
                    }
                  }}
                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-xs text-zinc-200 focus:outline-none focus:border-white/20 transition-colors"
                >
                  {repos.map((r) => (
                    <option key={r.id} value={r.id} className="bg-[#12131a]">
                      {r.fullName || r.name}
                      {r.rootDirectory ? ` (root: ${r.rootDirectory})` : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                  Target Branch
                </label>
                <input
                  type="text"
                  value={triggerBranch}
                  onChange={(e) => setTriggerBranch(e.target.value)}
                  placeholder="e.g. main"
                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-xs text-zinc-200 font-mono focus:outline-none focus:border-white/20 transition-colors"
                />
              </div>
            </div>

            <div className="p-4 border-t border-white/[0.06] bg-black/20 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setIsTriggerModalOpen(false)}
                className="px-3.5 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-white transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleTriggerBuild}
                disabled={isStartingBuild || !triggerRepoId}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-white hover:bg-zinc-200 text-black text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
              >
                {isStartingBuild ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Starting...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3 h-3 fill-black" />
                    <span>Start Build</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
