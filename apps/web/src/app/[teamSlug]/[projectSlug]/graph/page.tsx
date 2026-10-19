"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Share2,
  Hammer,
  AlertCircle,
  Play,
  RotateCcw,
  Loader2,
  FileText,
  ArrowRight,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuthStore } from "@/store/authStore";
import { useProjectStore } from "@/store/projectStore";
import { useBuildStore } from "@/store/buildStore";
import dynamic from "next/dynamic";
import { projectsApi, aiApi } from "@/lib/api";
import { GraphData } from "@/lib/types";

const VisGraph = dynamic(
  () => import("@/components/graph/VisGraph").then((mod) => mod.VisGraph),
  {
    ssr: false,
    loading: () => (
      <div className="flex-1 flex items-center justify-center bg-[#0c0d12]">
        <div className="flex flex-col items-center gap-2">
          <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-mono text-zinc-500">Loading Software Graph...</span>
        </div>
      </div>
    ),
  }
);

export default function GraphPage() {
  const params = useParams();
  const teamSlug = (params?.teamSlug as string) || "";
  const projectSlug = (params?.projectSlug as string) || "";

  const { token } = useAuthStore();
  const { getActiveProject } = useProjectStore();
  const { startBuild } = useBuildStore();

  const activeProject = getActiveProject();
  const repos = activeProject?.repositories || [];

  const [selectedRepoId, setSelectedRepoId] = useState<string>("");
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [viewMode, setViewMode] = useState<"graph" | "report">("graph");
  const [reportMarkdown, setReportMarkdown] = useState<string>("");
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [isStartingBuild, setIsStartingBuild] = useState(false);

  // Set default repo
  useEffect(() => {
    if (repos.length > 0 && !selectedRepoId) {
      setSelectedRepoId(repos[0].id);
    }
  }, [repos, selectedRepoId]);

  // Fetch live Neo4j graph data
  const fetchGraph = async () => {
    if (!token || !activeProject) return;
    setIsLoading(true);
    try {
      const data = await projectsApi.getGraph(
        token,
        activeProject.id,
        selectedRepoId || undefined,
        undefined,
        450
      );
      setGraphData(data);
    } catch (err) {
      console.warn("Could not fetch graph data:", err);
      setGraphData({
        status: "NOT_INDEXED",
        nodes: [],
        edges: [],
        message: "Failed to load knowledge graph",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();
  }, [token, activeProject?.id, selectedRepoId]);

  // Secondary architectural report fetch
  useEffect(() => {
    if (viewMode === "report" && !reportMarkdown && graphData?.repository) {
      setIsLoadingReport(true);
      aiApi
        .getGraphReport(graphData.repository.fullName)
        .then((res) => setReportMarkdown(res.report_markdown || "No architectural report available."))
        .catch(() => setReportMarkdown("Could not generate architectural report at this time."))
        .finally(() => setIsLoadingReport(false));
    }
  }, [viewMode, reportMarkdown, graphData?.repository]);

  const handleStartBuild = async () => {
    if (!token || !activeProject) return;
    const targetRepo = repos.find((r) => r.id === selectedRepoId) || repos[0];
    if (!targetRepo) return;

    setIsStartingBuild(true);
    try {
      await startBuild(token, activeProject.id, targetRepo.id, targetRepo.defaultBranch || "main");
      await fetchGraph();
    } catch (err) {
      console.error("Failed to start build:", err);
    } finally {
      setIsStartingBuild(false);
    }
  };

  const projectBase = `/${teamSlug}/${projectSlug}`;

  // 1. Loading state
  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-[#0c0d12]">
        <div className="text-center space-y-3">
          <Loader2 className="w-7 h-7 text-indigo-400 animate-spin mx-auto" />
          <p className="text-xs font-mono text-zinc-400">Loading Software Knowledge Graph...</p>
        </div>
      </div>
    );
  }

  // 2. Truthful empty / building / failed states
  if (graphData?.status === "NO_REPOSITORY") {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-[#0c0d12]">
        <div className="max-w-md w-full text-center space-y-4 py-12">
          <div className="w-12 h-12 rounded-xl bg-[#11131a] border border-white/[0.06] flex items-center justify-center mx-auto text-zinc-400">
            <Share2 className="w-6 h-6 text-zinc-400" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-white">No repository connected</h2>
            <p className="text-xs text-zinc-400 mt-1">
              Connect a repository to generate and explore the software knowledge graph.
            </p>
          </div>
          <Link
            href={`${projectBase}/repositories`}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold transition-colors"
          >
            <span>Connect Repository</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    );
  }

  if (graphData?.status === "BUILDING") {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-[#0c0d12]">
        <div className="max-w-md w-full text-center space-y-4 py-12">
          <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mx-auto text-indigo-400">
            <Hammer className="w-6 h-6 animate-bounce" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-white">
              Project intelligence is being generated
            </h2>
            <p className="text-xs text-zinc-400 mt-1">
              {graphData.build ? `Build #${graphData.build.id.slice(0, 8)} • ` : ""}
              Parsing AST and creating relationships in Neo4j...
            </p>
          </div>
          <Link
            href={`${projectBase}/builds`}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold transition-colors"
          >
            <span>View Build Status</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    );
  }

  if (graphData?.status === "NOT_INDEXED") {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-[#0c0d12]">
        <div className="max-w-md w-full text-center space-y-4 py-12">
          <div className="w-12 h-12 rounded-xl bg-[#11131a] border border-white/[0.06] flex items-center justify-center mx-auto text-zinc-400">
            <Share2 className="w-6 h-6 text-zinc-400" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-white">Codebase not indexed yet</h2>
            <p className="text-xs text-zinc-400 mt-1">
              Start an indexing build to parse symbols, caller hierarchies, and dependencies into Neo4j.
            </p>
          </div>
          <button
            onClick={handleStartBuild}
            disabled={isStartingBuild}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
          >
            {isStartingBuild ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Starting Build...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 text-emerald-600" />
                <span>Start Build</span>
              </>
            )}
          </button>
        </div>
      </div>
    );
  }

  if (graphData?.status === "FAILED") {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-[#0c0d12]">
        <div className="max-w-md w-full text-center space-y-4 py-12">
          <div className="w-12 h-12 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center mx-auto text-rose-400">
            <AlertCircle className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-white">Indexing pipeline failed</h2>
            <p className="text-xs text-zinc-400 mt-1">
              {graphData.message || "Failed during AST analysis or graph insertion."}
            </p>
          </div>
          <div className="flex items-center justify-center gap-3">
            <Link
              href={`${projectBase}/builds`}
              className="px-3.5 py-1.5 rounded-md bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-200 text-xs font-semibold transition-colors"
            >
              View Build
            </Link>
            <button
              onClick={handleStartBuild}
              disabled={isStartingBuild}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold transition-colors cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Retry</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 3. READY: Primary Interactive Graph
  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden relative bg-[#0c0d12]">
      {/* Top Header: Scope & Mode Toggle */}
      <div className="h-11 px-4 border-b border-white/[0.06] bg-[#0c0d12]/90 backdrop-blur-md flex items-center justify-between shrink-0 z-20">
        <div className="flex items-center gap-3">
          {repos.length > 1 ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-500 font-mono">Scope:</span>
              <select
                value={selectedRepoId}
                onChange={(e) => setSelectedRepoId(e.target.value)}
                className="bg-white/[0.04] border border-white/[0.08] rounded px-2 py-0.5 text-xs text-zinc-200 font-mono focus:outline-none"
              >
                {repos.map((r) => (
                  <option key={r.id} value={r.id} className="bg-[#11131a] text-zinc-200">
                    {r.name}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-xs font-mono text-zinc-400">
              <span className="text-zinc-500">Repository:</span>
              <span className="text-zinc-200 font-medium">{repos[0]?.name || projectSlug}</span>
            </div>
          )}
        </div>

        {/* View Mode Toggle: Interactive Graph (Primary) vs Report (Secondary) */}
        <div className="flex items-center gap-1 bg-white/[0.03] border border-white/[0.06] rounded-md p-0.5 text-xs font-medium">
          <button
            onClick={() => setViewMode("graph")}
            className={`px-2.5 py-0.5 rounded transition-colors flex items-center gap-1.5 cursor-pointer text-xs ${
              viewMode === "graph"
                ? "bg-white/[0.08] text-white font-semibold"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Share2 className="w-3 h-3" />
            <span>Graph</span>
          </button>
          <button
            onClick={() => setViewMode("report")}
            className={`px-2.5 py-0.5 rounded transition-colors flex items-center gap-1.5 cursor-pointer text-xs ${
              viewMode === "report"
                ? "bg-white/[0.08] text-white font-semibold"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <FileText className="w-3 h-3" />
            <span>Report</span>
          </button>
        </div>
      </div>

      {/* Main Surface: Graph occupies full-width canvas */}
      <div className="flex-1 relative overflow-hidden">
        {viewMode === "graph" ? (
          graphData ? (
            <VisGraph data={graphData} />
          ) : null
        ) : (
          <div className="h-full overflow-y-auto p-8 max-w-4xl mx-auto">
            {isLoadingReport ? (
              <div className="p-12 text-center space-y-3">
                <Loader2 className="w-6 h-6 text-zinc-500 animate-spin mx-auto" />
                <p className="text-xs font-mono text-zinc-500">
                  Generating architectural report...
                </p>
              </div>
            ) : (
              <div className="prose prose-invert prose-xs max-w-none bg-[#11131a] p-8 rounded-xl border border-white/[0.06] font-sans leading-relaxed">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {reportMarkdown}
                </ReactMarkdown>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
