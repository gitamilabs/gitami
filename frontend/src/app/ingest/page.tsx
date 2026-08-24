"use client";

import React, { useState, useEffect } from "react";
import { ProtectedRoute } from "../../components/auth/ProtectedRoute";
import { Sidebar } from "../../components/layout/Sidebar";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { IngestModal } from "../../components/repositories/IngestModal";
import { aiApi } from "../../lib/api";
import { IngestResponse, ConnectedRepository } from "../../lib/types";
import { useAuthStore } from "../../store/authStore";
import { useRepoStore } from "../../store/repoStore";
import Link from "next/link";
import {
  Database,
  Share2,
  FolderGit2,
  GitBranch,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Layers,
  ArrowRight,
  Clock,
  Code2,
  Github,
  Globe,
  Lock,
  RefreshCw,
  Folder,
  ShieldCheck,
} from "lucide-react";

function IngestContent() {
  const { token } = useAuthStore();
  const {
    connectedRepos,
    indexedRepos,
    fetchConnectedRepos,
    fetchIndexedRepos,
  } = useRepoStore();

  const [activeTab, setActiveTab] = useState<"github" | "local">("github");

  // Local directory mode state
  const [repoId, setRepoId] = useState("final-year-project");
  const [repoDir, setRepoDir] = useState("c:\\Users\\sumed\\PycharmProjects\\final-year-project");
  const [branch, setBranch] = useState("main");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // GitHub in-memory modal state
  const [selectedRepoForModal, setSelectedRepoForModal] = useState<ConnectedRepository | null>(null);
  const [selectedGithubRepoId, setSelectedGithubRepoId] = useState<string>("");

  useEffect(() => {
    if (token) {
      fetchConnectedRepos(token);
      fetchIndexedRepos();
    }
  }, [token, fetchConnectedRepos, fetchIndexedRepos]);

  useEffect(() => {
    if (connectedRepos.length > 0 && !selectedGithubRepoId) {
      setSelectedGithubRepoId(connectedRepos[0].id);
    }
  }, [connectedRepos, selectedGithubRepoId]);

  const selectedRepo = connectedRepos.find((r) => r.id === selectedGithubRepoId) || connectedRepos[0];

  const handleLocalIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoId.trim() || !repoDir.trim()) return;

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await aiApi.ingestRepo({
        repo_id: repoId.trim(),
        repo_dir: repoDir.trim(),
        branch: branch.trim() || "main",
      });
      setResult(res);
      await fetchIndexedRepos();
    } catch (err: any) {
      setError(err.message || "Failed to complete repository ingestion.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 gap-6">
      <Sidebar />

      <div className="flex-1 space-y-6 min-w-0">
        {/* Header */}
        <div className="glass-panel rounded-3xl p-6 border border-slate-800">
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="primary" size="sm" className="font-mono text-[10px]">
              Knowledge Base Ingestion Engine
            </Badge>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Ingest Codebase into Neo4j & ChromaDB
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Builds structural dependency graphs in Neo4j and generates semantic code embeddings with Gemini in ChromaDB.
          </p>
        </div>

        {/* Tab Selector */}
        <div className="flex items-center gap-2 border-b border-slate-800/80 pb-3 text-xs">
          <button
            onClick={() => setActiveTab("github")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl font-mono transition-all ${
              activeTab === "github"
                ? "bg-indigo-600/30 text-indigo-300 border border-indigo-500 shadow-md shadow-indigo-600/10 font-bold"
                : "bg-slate-900 text-slate-400 border border-slate-800 hover:text-slate-200"
            }`}
          >
            <Github className="w-4 h-4" />
            <span>Connected GitHub Repos (In-Memory Stream)</span>
          </button>

          <button
            onClick={() => setActiveTab("local")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl font-mono transition-all ${
              activeTab === "local"
                ? "bg-indigo-600/30 text-indigo-300 border border-indigo-500 shadow-md shadow-indigo-600/10 font-bold"
                : "bg-slate-900 text-slate-400 border border-slate-800 hover:text-slate-200"
            }`}
          >
            <Folder className="w-4 h-4" />
            <span>Local Filesystem Directory</span>
          </button>
        </div>

        {/* ========================================================= */}
        {/* TAB 1: CONNECTED GITHUB REPOSITORIES (IN-MEMORY STREAM) */}
        {/* ========================================================= */}
        {activeTab === "github" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-7 glass-panel rounded-3xl p-6 border border-slate-800 space-y-5">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
                  <Github className="w-4 h-4 text-indigo-400" />
                  Select Repository to Ingest
                </h2>
                <span className="text-[11px] font-mono text-slate-400">
                  {connectedRepos.length} Connected
                </span>
              </div>

              {/* In-Memory Streaming Feature Notice */}
              <div className="p-3.5 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-start gap-2.5 text-cyan-200 text-xs">
                <ShieldCheck className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                <div className="leading-relaxed">
                  <strong className="text-cyan-300">0 Local Disk Clone Footprint:</strong> Ingestion streams files in-memory via GitHub Tarball API and builds AST graphs directly.
                </div>
              </div>

              {connectedRepos.length > 0 ? (
                <div className="space-y-4 text-xs">
                  <div>
                    <label className="block text-slate-300 font-medium mb-1 font-mono">
                      Choose Connected Repository:
                    </label>
                    <select
                      value={selectedGithubRepoId}
                      onChange={(e) => setSelectedGithubRepoId(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-indigo-500"
                    >
                      {connectedRepos.map((r) => {
                        const isIngested =
                          indexedRepos.includes(r.name) ||
                          indexedRepos.includes(r.fullName);
                        return (
                          <option key={r.id} value={r.id}>
                            {r.fullName} {isIngested ? "(✓ Ingested)" : "(Not Ingested)"}
                          </option>
                        );
                      })}
                    </select>
                  </div>

                  {selectedRepo && (
                    <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-3 font-mono">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Status:</span>
                        {indexedRepos.includes(selectedRepo.name) ||
                        indexedRepos.includes(selectedRepo.fullName) ? (
                          <span className="flex items-center gap-1 text-emerald-400">
                            <CheckCircle2 className="w-3.5 h-3.5" /> Ingested & Ready
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-amber-400">
                            <Sparkles className="w-3.5 h-3.5" /> Ready for Ingestion
                          </span>
                        )}
                      </div>

                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Default Branch:</span>
                        <span className="text-cyan-400">{selectedRepo.defaultBranch}</span>
                      </div>

                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Visibility:</span>
                        <span className="text-slate-200">
                          {selectedRepo.isPrivate ? "Private" : "Public"}
                        </span>
                      </div>
                    </div>
                  )}

                  <div className="pt-2">
                    <Button
                      variant="glow"
                      size="md"
                      onClick={() => selectedRepo && setSelectedRepoForModal(selectedRepo)}
                      leftIcon={<Sparkles className="w-4 h-4" />}
                      className="w-full"
                    >
                      {selectedRepo &&
                      (indexedRepos.includes(selectedRepo.name) ||
                        indexedRepos.includes(selectedRepo.fullName))
                        ? "Re-index Repository into Knowledge Base"
                        : "Ingest Selected Repository"}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3">
                  <FolderGit2 className="w-10 h-10 text-slate-600 mx-auto" />
                  <p className="text-slate-300 font-bold">No Connected Repositories Found</p>
                  <p className="text-slate-400 text-xs max-w-sm mx-auto">
                    Install the Sentinel GitHub App from the Repositories page to connect your repositories.
                  </p>
                  <Link href="/repositories">
                    <Button variant="secondary" size="sm" className="mt-2">
                      Go to Connected Repositories
                    </Button>
                  </Link>
                </div>
              )}
            </div>

            {/* Right Info Box */}
            <div className="lg:col-span-5 space-y-4">
              <div className="glass-card rounded-3xl p-5 border border-slate-800 space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-cyan-400" />
                  Ingestion Pipeline Overview
                </h3>
                <ul className="space-y-2 text-xs text-slate-400 font-mono">
                  <li className="flex items-start gap-2">
                    <span className="w-4 h-4 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-[10px] shrink-0 mt-0.5">
                      1
                    </span>
                    <span><strong>In-Memory Tarball Stream</strong> (GitHub App Token)</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="w-4 h-4 rounded-full bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-[10px] shrink-0 mt-0.5">
                      2
                    </span>
                    <span><strong>Tree-sitter AST Parsing</strong> (Python, JS, TS, React)</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="w-4 h-4 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center text-[10px] shrink-0 mt-0.5">
                      3
                    </span>
                    <span><strong>Neo4j Call Graph</strong> (CALLS & IMPORTS edges)</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[10px] shrink-0 mt-0.5">
                      4
                    </span>
                    <span><strong>ChromaDB Vector Embeddings</strong> (Gemini Embeddings)</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* TAB 2: LOCAL FILESYSTEM DIRECTORY */}
        {/* ========================================================= */}
        {activeTab === "local" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-7 glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
              <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <Folder className="w-4 h-4 text-indigo-400" />
                Local Directory Indexing Configuration
              </h2>

              <form onSubmit={handleLocalIngest} className="space-y-4 text-xs">
                <div>
                  <label className="block text-slate-300 font-medium mb-1">
                    Repository Identifier (repo_id)
                  </label>
                  <input
                    type="text"
                    value={repoId}
                    onChange={(e) => setRepoId(e.target.value)}
                    placeholder="e.g. final-year-project"
                    required
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">
                    Local Repository Directory Path (repo_dir)
                  </label>
                  <input
                    type="text"
                    value={repoDir}
                    onChange={(e) => setRepoDir(e.target.value)}
                    placeholder="e.g. c:\Users\sumed\PycharmProjects\final-year-project"
                    required
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">
                    Git Branch
                  </label>
                  <input
                    type="text"
                    value={branch}
                    onChange={(e) => setBranch(e.target.value)}
                    placeholder="main"
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div className="pt-2">
                  <Button
                    type="submit"
                    variant="glow"
                    size="md"
                    isLoading={isLoading}
                    leftIcon={<Sparkles className="w-4 h-4" />}
                    className="w-full"
                  >
                    {isLoading ? "Parsing AST & Embedding Code..." : "Start Local Ingestion"}
                  </Button>
                </div>
              </form>
            </div>

            {/* Right Info Box */}
            <div className="lg:col-span-5 space-y-4">
              {error && (
                <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2.5">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold">Ingestion Failed</p>
                    <p className="mt-0.5 font-mono">{error}</p>
                  </div>
                </div>
              )}

              {result && (
                <div className="glass-panel rounded-3xl p-5 border border-emerald-500/30 bg-emerald-950/20 space-y-4 animate-fade-in">
                  <div className="flex items-center gap-2 text-emerald-400">
                    <CheckCircle2 className="w-5 h-5" />
                    <span className="text-sm font-bold">Ingestion Completed Successfully!</span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                    <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
                      <p className="text-slate-400 text-[10px] uppercase">Symbols Parsed</p>
                      <p className="text-base font-bold text-slate-100">{result.symbols_parsed}</p>
                    </div>
                    <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
                      <p className="text-slate-400 text-[10px] uppercase">Files Vectorized</p>
                      <p className="text-base font-bold text-cyan-400">{result.files_parsed}</p>
                    </div>
                    <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
                      <p className="text-slate-400 text-[10px] uppercase">Graph Edges</p>
                      <p className="text-base font-bold text-indigo-400">{result.edges_count}</p>
                    </div>
                    <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800">
                      <p className="text-slate-400 text-[10px] uppercase">Duration</p>
                      <p className="text-base font-bold text-amber-400">{result.duration_seconds.toFixed(2)}s</p>
                    </div>
                  </div>

                  <Link href={`/chat?repo=${encodeURIComponent(result.repo_id)}`} className="block">
                    <Button
                      variant="glow"
                      size="sm"
                      rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                      className="w-full"
                    >
                      Chat with Ingested KB ({result.repo_id})
                    </Button>
                  </Link>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Ingestion Confirmation & Progress Modal */}
        <IngestModal
          isOpen={!!selectedRepoForModal}
          repo={selectedRepoForModal}
          onClose={() => setSelectedRepoForModal(null)}
          onSuccess={() => {
            fetchIndexedRepos();
          }}
        />
      </div>
    </div>
  );
}

export default function IngestPage() {
  return (
    <ProtectedRoute>
      <IngestContent />
    </ProtectedRoute>
  );
}
