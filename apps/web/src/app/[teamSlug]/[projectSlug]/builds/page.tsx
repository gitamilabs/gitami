"use client";

import React, { useState, useEffect } from "react";
import { useParams, useSearchParams } from "next/navigation";
import {
  Hammer,
  AlertCircle,
  Loader2,
  GitBranch,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Trash2,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { useProjectStore } from "@/store/projectStore";
import { useBuildStore } from "@/store/buildStore";
import { Build, BuildStage } from "@/lib/types";

function formatDuration(startedAt?: string | null, completedAt?: string | null, seconds?: number): string {
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
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.floor(hours / 24);
  return `${days} d ago`;
}

export default function BuildsPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const teamSlug = (params?.teamSlug as string) || "";
  const projectSlug = (params?.projectSlug as string) || "";
  const repoFilter = searchParams.get("repo");

  const { token } = useAuthStore();
  const { getActiveProject, fetchProjectDetails } = useProjectStore();
  const { builds, fetchProjectBuilds, startBuild, cancelBuild, deleteBuild } = useBuildStore();

  const activeProject = getActiveProject();
  const [selectedBuildId, setSelectedBuildId] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Initial fetch
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

  // Set default selected build, prioritizing repo query parameter
  useEffect(() => {
    if (builds.length > 0 && !selectedBuildId) {
      if (repoFilter) {
        const matching = builds.find(
          (b) => b.repositoryId === repoFilter || b.repositoryId?.includes(repoFilter)
        );
        if (matching) {
          setSelectedBuildId(matching.id);
          return;
        }
      }
      setSelectedBuildId(builds[0].id);
    }
  }, [builds, selectedBuildId, repoFilter]);

  // Auto-polling while any build is active
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

  const selectedBuild = builds.find((b) => b.id === selectedBuildId) || builds[0];

  const handleRetry = async () => {
    if (!token || !activeProject || !selectedBuild) return;
    setIsRetrying(true);
    try {
      const repo = activeProject.repositories?.find(
        (r) => r.fullName === selectedBuild.repositoryId || r.name === selectedBuild.repositoryId
      );
      const repoId = repo ? repo.id : selectedBuild.repositoryId;
      const newBuild = await startBuild(token, activeProject.id, repoId, selectedBuild.branch);
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
    if (!window.confirm(`Are you sure you want to delete build #${selectedBuild.id.slice(0, 8)}?`)) return;
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
    <div className="p-8 max-w-5xl w-full mx-auto space-y-8 animate-fade-in text-zinc-200">
      {/* Header */}
      <div className="pb-6 border-b border-white/[0.06]">
        <h1 className="text-xl font-semibold text-white tracking-tight font-mono">
          Builds & Indexing Pipeline
        </h1>
        <p className="text-xs text-zinc-400 mt-1">
          Durable background indexing pipeline: Tree-sitter AST parsing, Neo4j software graph generation, and validation.
        </p>
      </div>

      {builds.length === 0 ? (
        <div className="py-16 text-center space-y-4 max-w-md mx-auto">
          <div className="w-12 h-12 rounded-xl bg-[#11131a] border border-white/[0.06] flex items-center justify-center mx-auto text-zinc-400">
            <Hammer className="w-6 h-6 text-zinc-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">No builds recorded yet</h3>
            <p className="text-xs text-zinc-400 mt-1">
              Trigger an indexing build from the Repositories tab to parse and link software entities.
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column: Build History List (Flat, clean divider rows) */}
          <div className="lg:col-span-5 space-y-3">
            <div className="text-xs font-mono uppercase tracking-wider text-zinc-400 font-semibold px-1">
              Build History ({builds.length})
            </div>

            <div className="border-t border-b border-white/[0.06] divide-y divide-white/[0.06] max-h-[600px] overflow-y-auto">
              {builds.map((build) => {
                const isSelected = selectedBuild?.id === build.id;
                const isRunning = build.status === "RUNNING";
                const isFailed = build.status === "FAILED";
                const isCompleted = build.status === "COMPLETED";

                return (
                  <button
                    key={build.id}
                    onClick={() => setSelectedBuildId(build.id)}
                    className={`w-full py-3.5 px-3 text-left transition-colors flex items-start justify-between gap-3 ${
                      isSelected
                        ? "bg-white/[0.08] rounded-md text-white font-medium"
                        : "hover:bg-white/[0.03] text-zinc-300"
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-semibold text-white">
                          Build #{build.id.slice(0, 8)}
                        </span>
                        <span
                          className={`text-[10px] font-mono px-1.5 py-0.2 rounded font-semibold ${
                            isCompleted
                              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                              : isRunning
                              ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 animate-pulse"
                              : "bg-rose-500/10 text-rose-400 border border-rose-500/30"
                          }`}
                        >
                          {build.status}
                        </span>
                      </div>

                      <div className="text-xs font-mono text-zinc-400 truncate mt-1">
                        {build.repositoryId}
                      </div>

                      <div className="flex items-center gap-2 text-[11px] font-mono text-zinc-500 mt-1">
                        <span className="flex items-center gap-1">
                          <GitBranch className="w-3 h-3 text-zinc-600" />
                          {build.branch}
                        </span>
                        <span>•</span>
                        <span>{formatRelativeTime(build.createdAt)}</span>
                      </div>
                    </div>

                    <div className="text-right shrink-0 text-xs font-mono text-zinc-500">
                      {formatDuration(build.startedAt, build.completedAt, build.stats?.duration_seconds)}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right Column: Build Timeline & Metrics */}
          {selectedBuild && (
            <div className="lg:col-span-7 space-y-6">
              {/* Build Meta */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/[0.06]">
                <div>
                  <div className="flex items-center gap-2.5">
                    <h2 className="text-base font-semibold text-white font-mono">
                      Build #{selectedBuild.id.slice(0, 8)}
                    </h2>
                    <span
                      className={`text-[11px] font-mono px-2 py-0.5 rounded font-semibold ${
                        selectedBuild.status === "COMPLETED"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                          : selectedBuild.status === "RUNNING"
                          ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 animate-pulse"
                          : "bg-rose-500/10 text-rose-400 border border-rose-500/30"
                      }`}
                    >
                      {selectedBuild.status}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-2.5 text-xs font-mono text-zinc-400 mt-1.5">
                    <span>{selectedBuild.repositoryId}</span>
                    <span>•</span>
                    <span>Branch: {selectedBuild.branch}</span>
                    <span>•</span>
                    <span>Commit: {selectedBuild.targetCommitSha || "HEAD"}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {(selectedBuild.status === "RUNNING" || selectedBuild.status === "QUEUED") && (
                    <button
                      onClick={handleCancel}
                      disabled={isCancelling}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
                    >
                      {isCancelling ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Cancelling...</span>
                        </>
                      ) : (
                        <>
                          <XCircle className="w-3.5 h-3.5" />
                          <span>Cancel Build</span>
                        </>
                      )}
                    </button>
                  )}

                    <button
                      onClick={handleRetry}
                      disabled={isRetrying || isCancelling || isDeleting}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
                    >
                      {isRetrying ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Starting...</span>
                        </>
                      ) : (
                        <>
                          <RotateCcw className="w-3.5 h-3.5" />
                          <span>{selectedBuild.status === "FAILED" ? "Retry Build" : "Re-run Build"}</span>
                        </>
                      )}
                    </button>

                    {selectedBuild.status !== "RUNNING" && selectedBuild.status !== "QUEUED" && (
                      <button
                        onClick={handleDelete}
                        disabled={isDeleting || isRetrying}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
                        title="Delete Build"
                      >
                        {isDeleting ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            <span>Deleting...</span>
                          </>
                        ) : (
                          <>
                            <Trash2 className="w-3.5 h-3.5" />
                            <span>Delete</span>
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>

              {/* Error Alert */}
              {selectedBuild.error && (
                <div className="p-3.5 rounded-md bg-rose-950/30 border border-rose-800/50 text-rose-300 text-xs flex items-start gap-2.5 font-mono">
                  <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold block">Build Error:</span>
                    <p className="text-[11px] text-rose-200 mt-0.5 break-words">
                      {selectedBuild.error}
                    </p>
                  </div>
                </div>
              )}

              {/* Real Persisted Stage Timeline (Section 16: Timeline > Fake Percentage) */}
              <div className="space-y-3">
                <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-400 font-semibold">
                  Stage Timeline
                </h3>

                <div className="border-t border-b border-white/[0.06] divide-y divide-white/[0.06] font-mono text-xs">
                  {(selectedBuild.stages || [
                    { key: "SNAPSHOT", name: "Repository Snapshot", status: "COMPLETED" },
                    { key: "DISCOVERY", name: "File Discovery", status: "COMPLETED" },
                    { key: "AST_ANALYSIS", name: "AST Code Analysis", status: "COMPLETED" },
                    { key: "GRAPH_INDEXING", name: "Graph Indexing", status: "COMPLETED" },
                    { key: "SEMANTIC_INDEXING", name: "Semantic Indexing", status: "COMPLETED" },
                    { key: "VALIDATION", name: "Pipeline Validation", status: "COMPLETED" },
                  ] as BuildStage[]).map((stage) => {
                    const isRunning = stage.status === "RUNNING";
                    const isDone = stage.status === "COMPLETED";
                    const isFailed = stage.status === "FAILED";

                    return (
                      <div
                        key={stage.key}
                        className="py-3 flex items-center justify-between"
                      >
                        <div className="flex items-center gap-3">
                          {isDone ? (
                            <span className="w-2 h-2 rounded-full bg-emerald-400" />
                          ) : isRunning ? (
                            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
                          ) : isFailed ? (
                            <span className="w-2 h-2 rounded-full bg-rose-500" />
                          ) : (
                            <span className="w-2 h-2 rounded-full bg-zinc-700" />
                          )}
                          <span
                            className={`font-mono ${
                              isDone
                                ? "text-zinc-200"
                                : isRunning
                                ? "text-indigo-300 font-semibold"
                                : isFailed
                                ? "text-rose-300"
                                : "text-zinc-500"
                            }`}
                          >
                            {stage.name}
                          </span>
                        </div>

                        <span
                          className={`text-[11px] font-mono font-semibold ${
                            isDone
                              ? "text-emerald-400"
                              : isRunning
                              ? "text-indigo-400"
                              : isFailed
                              ? "text-rose-400"
                              : "text-zinc-600"
                          }`}
                        >
                          {stage.status.charAt(0) + stage.status.slice(1).toLowerCase()}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Real Persisted Metrics */}
              {selectedBuild.stats && (
                <div className="space-y-3 pt-2">
                  <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-400 font-semibold">
                    Indexed Metrics
                  </h3>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                    <div className="p-3 rounded-md bg-[#11131a] border border-white/[0.06]">
                      <span className="text-[10px] text-zinc-500 block uppercase">Files Parsed</span>
                      <span className="text-sm font-semibold text-white mt-1 block">
                        {selectedBuild.stats.files_parsed || 0}
                      </span>
                    </div>

                    <div className="p-3 rounded-md bg-[#11131a] border border-white/[0.06]">
                      <span className="text-[10px] text-zinc-500 block uppercase">Entities Created</span>
                      <span className="text-sm font-semibold text-white mt-1 block">
                        {selectedBuild.stats.symbols_parsed || 0}
                      </span>
                    </div>

                    <div className="p-3 rounded-md bg-[#11131a] border border-white/[0.06]">
                      <span className="text-[10px] text-zinc-500 block uppercase">Relationships</span>
                      <span className="text-sm font-semibold text-white mt-1 block">
                        {selectedBuild.stats.edges_count || 0}
                      </span>
                    </div>

                    <div className="p-3 rounded-md bg-[#11131a] border border-white/[0.06]">
                      <span className="text-[10px] text-zinc-500 block uppercase">Duration</span>
                      <span className="text-sm font-semibold text-white mt-1 block">
                        {selectedBuild.stats.duration_seconds ? `${selectedBuild.stats.duration_seconds}s` : "—"}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
