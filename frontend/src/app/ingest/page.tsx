"use client";

import React, { useState } from "react";
import { ProtectedRoute } from "../../components/auth/ProtectedRoute";
import { Sidebar } from "../../components/layout/Sidebar";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { aiApi } from "../../lib/api";
import { IngestResponse } from "../../lib/types";
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
} from "lucide-react";

function IngestContent() {
  const { fetchIndexedRepos } = useRepoStore();

  const [repoId, setRepoId] = useState("final-year-project");
  const [repoDir, setRepoDir] = useState("c:\\Users\\sumed\\PycharmProjects\\final-year-project");
  const [branch, setBranch] = useState("main");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleIngest = async (e: React.FormEvent) => {
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
            Traverses source code with Tree-sitter AST parser, builds structural dependency graphs in Neo4j, and generates semantic code embeddings with Gemini models in ChromaDB.
          </p>
        </div>

        {/* Form and Preview */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7 glass-panel rounded-3xl p-6 border border-slate-800 space-y-4">
            <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Database className="w-4 h-4 text-indigo-400" />
              Repository Indexing Configuration
            </h2>

            <form onSubmit={handleIngest} className="space-y-4 text-xs">
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
                <p className="text-[11px] text-slate-400 mt-1">
                  Multi-tenant namespace key used in Neo4j graph and ChromaDB metadata.
                </p>
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
                <p className="text-[11px] text-slate-400 mt-1">
                  Absolute filesystem directory containing source code files.
                </p>
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
                  {isLoading ? "Parsing AST & Embedding Code..." : "Start Knowledge Base Ingestion"}
                </Button>
              </div>
            </form>
          </div>

          {/* Right Info / Preset Box */}
          <div className="lg:col-span-5 space-y-4">
            <div className="glass-card rounded-3xl p-5 border border-slate-800 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                Ingestion Pipeline Stages
              </h3>
              <ul className="space-y-2 text-xs text-slate-400">
                <li className="flex items-start gap-2">
                  <span className="w-4 h-4 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-mono text-[10px] shrink-0 mt-0.5">
                    1
                  </span>
                  <span><strong>Tree-sitter AST Parsing</strong> (Python, JS, TS, TSX, React components)</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-4 h-4 rounded-full bg-cyan-500/20 text-cyan-400 flex items-center justify-center font-mono text-[10px] shrink-0 mt-0.5">
                    2
                  </span>
                  <span><strong>Neo4j Graph Construction</strong> (File, Symbol, CALLS, IMPORTS edges)</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-4 h-4 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center font-mono text-[10px] shrink-0 mt-0.5">
                    3
                  </span>
                  <span><strong>ChromaDB Vector Embeddings</strong> (Batch deduplication + staleness keys)</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-mono text-[10px] shrink-0 mt-0.5">
                    4
                  </span>
                  <span><strong>Import Linker Pass</strong> (Resolves relative & package dependencies)</span>
                </li>
              </ul>
            </div>

            {/* Error Display */}
            {error && (
              <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2.5 animate-fade-in">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Ingestion Failed</p>
                  <p className="mt-0.5 font-mono">{error}</p>
                </div>
              </div>
            )}

            {/* Result Stats Display */}
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
