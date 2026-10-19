"use client";

import React from "react";
import Link from "next/link";
import { Hammer, CheckCircle2, AlertCircle, ArrowRight, GitBranch, Clock, Layers } from "lucide-react";
import { Build } from "@/lib/types";

interface BuildStatusSummaryProps {
  build?: Build | null;
  teamSlug: string;
  projectSlug: string;
  showWhenEmpty?: boolean;
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
  return `${days}d ago`;
}

export const BuildStatusSummary: React.FC<BuildStatusSummaryProps> = ({
  build,
  teamSlug,
  projectSlug,
  showWhenEmpty = false,
}) => {
  const projectBase = `/${teamSlug}/${projectSlug}`;

  if (!build) {
    if (!showWhenEmpty) return null;
    return (
      <div className="p-4 rounded-lg bg-[#11131a] border border-white/[0.06] flex items-center justify-between text-xs">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-white/[0.04] border border-white/[0.06] flex items-center justify-center text-zinc-500">
            <Hammer className="w-4 h-4" />
          </div>
          <div>
            <div className="font-medium text-zinc-300">No indexing builds yet</div>
            <div className="text-zinc-500 text-[11px]">Connect a repository to index AST call graphs and symbol intelligence</div>
          </div>
        </div>
        <Link
          href={`${projectBase}/builds`}
          className="text-xs text-zinc-400 hover:text-white flex items-center gap-1 transition-colors"
        >
          <span>Builds</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    );
  }

  const isRunning = build.status === "RUNNING" || build.status === "QUEUED";
  const isCompleted = build.status === "COMPLETED";
  const isFailed = build.status === "FAILED";

  const stages = build.stages || [
    { key: "SNAPSHOT", name: "Snapshot", status: isCompleted ? "COMPLETED" : "RUNNING" },
    { key: "DISCOVERY", name: "Discovery", status: isCompleted ? "COMPLETED" : "QUEUED" },
    { key: "AST_ANALYSIS", name: "AST Parser", status: isCompleted ? "COMPLETED" : "QUEUED" },
    { key: "GRAPH_BUILD", name: "Neo4j Graph", status: isCompleted ? "COMPLETED" : "QUEUED" },
    { key: "VECTOR_INDEX", name: "Vector KB", status: isCompleted ? "COMPLETED" : "QUEUED" },
  ];

  return (
    <div
      className={`rounded-lg p-4 transition-all ${
        isRunning
          ? "bg-[#11131a] border border-indigo-500/30"
          : isFailed
          ? "bg-[#11131a] border border-rose-500/30"
          : "bg-[#11131a] border border-white/[0.06]"
      }`}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          {isRunning ? (
            <div className="w-7 h-7 rounded-md bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
              <Hammer className="w-3.5 h-3.5 animate-bounce" />
            </div>
          ) : isCompleted ? (
            <div className="w-7 h-7 rounded-md bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
              <CheckCircle2 className="w-3.5 h-3.5" />
            </div>
          ) : (
            <div className="w-7 h-7 rounded-md bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400 shrink-0">
              <AlertCircle className="w-3.5 h-3.5" />
            </div>
          )}

          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-white font-mono">
                Build #{build.id.slice(0, 8)}
              </span>
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded font-mono font-medium ${
                  isRunning
                    ? "bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 animate-pulse"
                    : isCompleted
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                }`}
              >
                {build.status}
              </span>
            </div>
            <div className="text-[11px] text-zinc-500 font-mono mt-0.5 flex items-center gap-2">
              <span className="flex items-center gap-1">
                <GitBranch className="w-3 h-3 text-zinc-600" />
                {build.branch || "main"}
              </span>
              <span>•</span>
              <span>{formatRelativeTime(build.createdAt)}</span>
              {build.stats?.duration_seconds !== undefined && (
                <>
                  <span>•</span>
                  <span>{build.stats.duration_seconds.toFixed(1)}s</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 self-end sm:self-auto">
          {isCompleted && (
            <Link
              href={`${projectBase}/graph`}
              className="px-2.5 py-1 text-xs font-medium text-zinc-300 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] rounded border border-white/[0.08] transition-colors flex items-center gap-1.5"
            >
              <Layers className="w-3 h-3 text-indigo-400" />
              <span>Explore Graph</span>
            </Link>
          )}
          <Link
            href={`${projectBase}/builds`}
            className="text-xs text-zinc-400 hover:text-white flex items-center gap-1 transition-colors"
          >
            <span>Details</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </div>

      {/* Stage Tracker & Live Metrics */}
      <div className="pt-3 flex flex-col md:flex-row md:items-center justify-between gap-3">
        {/* Stage Timeline */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {stages.map((stg, i) => (
            <div key={stg.key} className="flex items-center gap-1.5">
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded flex items-center gap-1 ${
                  stg.status === "COMPLETED"
                    ? "bg-white/[0.04] text-zinc-300 border border-white/[0.06]"
                    : stg.status === "RUNNING"
                    ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 animate-pulse font-semibold"
                    : "bg-white/[0.02] text-zinc-600 border border-white/[0.04]"
                }`}
              >
                {stg.status === "COMPLETED" && <span className="text-emerald-400">✓</span>}
                {stg.status === "RUNNING" && <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-ping" />}
                {stg.name}
              </span>
              {i < stages.length - 1 && <span className="text-zinc-750 text-xs">→</span>}
            </div>
          ))}
        </div>

        {/* Real Stats Metrics */}
        {build.stats && (
          <div className="flex items-center gap-3 text-[11px] font-mono text-zinc-400 shrink-0">
            {build.stats.files_parsed !== undefined && (
              <span>{build.stats.files_parsed} files</span>
            )}
            {build.stats.symbols_parsed !== undefined && (
              <>
                <span className="text-zinc-700">•</span>
                <span>{build.stats.symbols_parsed.toLocaleString()} symbols</span>
              </>
            )}
            {build.stats.edges_count !== undefined && (
              <>
                <span className="text-zinc-700">•</span>
                <span>{build.stats.edges_count.toLocaleString()} relationships</span>
              </>
            )}
          </div>
        )}
      </div>

      {/* Error display if failed */}
      {isFailed && build.error && (
        <div className="mt-3 p-2.5 rounded bg-rose-950/20 border border-rose-900/40 text-xs text-rose-300 font-mono">
          {build.error}
        </div>
      )}
    </div>
  );
};
