"use client";

import React, { useState, useEffect } from "react";
import { ConnectedRepository, IngestResponse } from "../../lib/types";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { useAuthStore } from "../../store/authStore";
import { useRepoStore } from "../../store/repoStore";
import Link from "next/link";
import {
  Database,
  Sparkles,
  Layers,
  GitBranch,
  Lock,
  Globe,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  RefreshCw,
  X,
  Code2,
  Share2,
  Cpu,
  Clock,
  ShieldCheck,
} from "lucide-react";

interface IngestModalProps {
  isOpen: boolean;
  repo: ConnectedRepository | null;
  onClose: () => void;
  onSuccess?: () => void;
}

type IngestPhase = "confirm" | "ingesting" | "success" | "error";

interface StageInfo {
  id: number;
  label: string;
  desc: string;
}

const INGEST_STAGES: StageInfo[] = [
  { id: 1, label: "Stream GitHub Archive", desc: "Fetching in-memory tarball via GitHub App (0 disk writes)" },
  { id: 2, label: "Tree-sitter AST Parsing", desc: "Extracting functions, classes, methods, and call sites" },
  { id: 3, label: "Neo4j Graph Construction", desc: "Mapping File, Symbol, CALLS, and IMPORTS edges" },
  { id: 4, label: "ChromaDB Vector Embeddings", desc: "Generating semantic code embeddings with Gemini" },
  { id: 5, label: "Dependency & Import Linker", desc: "Resolving cross-file imports & finalizing Knowledge Base" },
];

export const IngestModal: React.FC<IngestModalProps> = ({
  isOpen,
  repo,
  onClose,
  onSuccess,
}) => {
  const { token } = useAuthStore();
  const { ingestConnectedRepo } = useRepoStore();

  const [phase, setPhase] = useState<IngestPhase>("confirm");
  const [branch, setBranch] = useState<string>("main");
  const [agreed, setAgreed] = useState<boolean>(true);
  const [currentStage, setCurrentStage] = useState<number>(1);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Initialize state when repo changes
  useEffect(() => {
    if (repo) {
      setBranch(repo.defaultBranch || "main");
      setPhase("confirm");
      setAgreed(true);
      setCurrentStage(1);
      setElapsedSeconds(0);
      setResult(null);
      setErrorMessage(null);
    }
  }, [repo, isOpen]);

  // Elapsed timer during ingestion
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (phase === "ingesting") {
      interval = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [phase]);

  // Progressive simulated stage tracker while waiting for response
  useEffect(() => {
    let stageTimer: NodeJS.Timeout | null = null;
    if (phase === "ingesting") {
      stageTimer = setInterval(() => {
        setCurrentStage((prev) => (prev < 5 ? prev + 1 : prev));
      }, 2400);
    }
    return () => {
      if (stageTimer) clearInterval(stageTimer);
    };
  }, [phase]);

  if (!isOpen || !repo) return null;

  const handleStartIngestion = async () => {
    if (!token) return;
    setPhase("ingesting");
    setCurrentStage(1);
    setElapsedSeconds(0);
    setErrorMessage(null);

    try {
      const res = await ingestConnectedRepo(token, repo.id, branch.trim() || repo.defaultBranch);
      setResult(res);
      setPhase("success");
      if (onSuccess) onSuccess();
    } catch (err: any) {
      console.error("Ingestion failed:", err);
      setErrorMessage(err.message || "Failed to ingest repository.");
      setPhase("error");
    }
  };

  const handleClose = () => {
    if (phase === "ingesting") return; // Prevent closing while in-flight
    onClose();
  };

  const formatTimer = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}s`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xl animate-fade-in">
      <div
        className="glass-panel rounded-3xl border border-slate-800 w-full max-w-xl shadow-2xl overflow-hidden relative flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="p-6 border-b border-slate-800/80 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 shadow-inner">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <Badge variant="primary" size="sm" className="font-mono text-[10px]" dot>
                  Neo4j & ChromaDB
                </Badge>
                {repo.isPrivate ? (
                  <Badge variant="warning" size="sm" className="text-[10px]">
                    <Lock className="w-2.5 h-2.5" /> Private
                  </Badge>
                ) : (
                  <Badge variant="info" size="sm" className="text-[10px]">
                    <Globe className="w-2.5 h-2.5" /> Public
                  </Badge>
                )}
              </div>
              <h2 className="text-lg font-bold text-white tracking-tight mt-0.5">
                {phase === "confirm" && "Confirm Repository Ingestion"}
                {phase === "ingesting" && "Ingesting Codebase into Knowledge Base"}
                {phase === "success" && "Ingestion Completed Successfully!"}
                {phase === "error" && "Ingestion Encountered an Error"}
              </h2>
            </div>
          </div>

          {phase !== "ingesting" && (
            <button
              onClick={handleClose}
              className="p-2 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-colors"
              aria-label="Close modal"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5 text-xs">
          {/* PHASE 1: CONFIRMATION VIEW */}
          {phase === "confirm" && (
            <div className="space-y-4">
              {/* Repository Summary Card */}
              <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-3 shadow-inner">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[11px] font-mono text-slate-400">Target Repository</p>
                    <p className="text-sm font-bold text-slate-100 font-mono">{repo.fullName}</p>
                  </div>
                  <span className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-slate-800 border border-slate-700 text-slate-300">
                    ID: {repo.name}
                  </span>
                </div>

                <div className="pt-2 border-t border-slate-800/80 flex items-center gap-3">
                  <label className="text-slate-400 font-medium shrink-0 flex items-center gap-1 font-mono">
                    <GitBranch className="w-3.5 h-3.5 text-cyan-400" />
                    Target Branch:
                  </label>
                  <input
                    type="text"
                    value={branch}
                    onChange={(e) => setBranch(e.target.value)}
                    placeholder="main"
                    className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-indigo-500 shadow-inner"
                  />
                </div>
              </div>

              {/* In-Memory Zero-Disk Feature Badge */}
              <div className="p-3.5 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-start gap-2.5 text-cyan-200">
                <ShieldCheck className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                <div className="text-[11px] leading-relaxed">
                  <span className="font-bold text-cyan-300">In-Memory Streaming Ingestion:</span>{" "}
                  Code files are streamed directly from GitHub into memory and parsed via Tree-sitter AST with <strong>zero local disk footprint</strong>.
                </div>
              </div>

              {/* Pipeline Breakdown Steps */}
              <div className="space-y-2">
                <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 font-mono">
                  <Layers className="w-3.5 h-3.5 text-indigo-400" />
                  What will happen during ingestion:
                </p>
                <div className="grid grid-cols-1 gap-2 font-mono">
                  <div className="p-2.5 rounded-xl bg-slate-900/60 border border-slate-800 flex items-start gap-2.5">
                    <span className="w-4 h-4 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-[10px] shrink-0 mt-0.5 font-bold">
                      1
                    </span>
                    <div>
                      <p className="font-bold text-slate-200">Tree-sitter AST Parsing</p>
                      <p className="text-[10px] text-slate-400">Extracts AST symbols, classes, functions, and call hierarchy in Python/JS/TS/React.</p>
                    </div>
                  </div>

                  <div className="p-2.5 rounded-xl bg-slate-900/60 border border-slate-800 flex items-start gap-2.5">
                    <span className="w-4 h-4 rounded-full bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-[10px] shrink-0 mt-0.5 font-bold">
                      2
                    </span>
                    <div>
                      <p className="font-bold text-slate-200">Neo4j Graph Construction</p>
                      <p className="text-[10px] text-slate-400">Maps File nodes, Symbol nodes, CALLS relationships, and IMPORTS edges.</p>
                    </div>
                  </div>

                  <div className="p-2.5 rounded-xl bg-slate-900/60 border border-slate-800 flex items-start gap-2.5">
                    <span className="w-4 h-4 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center text-[10px] shrink-0 mt-0.5 font-bold">
                      3
                    </span>
                    <div>
                      <p className="font-bold text-slate-200">ChromaDB Vector Embeddings</p>
                      <p className="text-[10px] text-slate-400">Generates semantic code embeddings using Gemini models for fast hybrid search.</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Agreement Checkbox */}
              <label className="flex items-center gap-2.5 p-3 rounded-2xl bg-slate-900/60 border border-slate-800 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={agreed}
                  onChange={(e) => setAgreed(e.target.checked)}
                  className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 bg-slate-800 border-slate-700"
                />
                <span className="text-xs text-slate-300">
                  I agree to ingest and index this repository into the Neo4j Knowledge Graph and ChromaDB Vector Store.
                </span>
              </label>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-2">
                <Button variant="secondary" size="md" onClick={handleClose}>
                  Cancel
                </Button>
                <Button
                  variant="glow"
                  size="md"
                  disabled={!agreed || !branch.trim()}
                  onClick={handleStartIngestion}
                  leftIcon={<Sparkles className="w-4 h-4" />}
                >
                  Confirm & Start Ingestion
                </Button>
              </div>
            </div>
          )}

          {/* PHASE 2: INGESTING LOADING SCREEN */}
          {phase === "ingesting" && (
            <div className="space-y-6 py-4">
              {/* Animated Glowing Radar Pulse */}
              <div className="flex flex-col items-center justify-center text-center space-y-3">
                <div className="relative w-20 h-20 flex items-center justify-center">
                  <div className="absolute inset-0 rounded-full bg-indigo-500/20 animate-ping" />
                  <div className="absolute inset-2 rounded-full bg-cyan-500/30 animate-pulse" />
                  <div className="w-14 h-14 rounded-2xl bg-indigo-600/30 border border-indigo-500/50 flex items-center justify-center text-indigo-300 relative shadow-lg shadow-indigo-500/20">
                    <RefreshCw className="w-6 h-6 animate-spin" />
                  </div>
                </div>

                <div>
                  <h3 className="text-base font-bold text-white font-mono">
                    Ingesting {repo.name}...
                  </h3>
                  <p className="text-xs text-slate-400 font-mono mt-0.5 flex items-center justify-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-amber-400" />
                    Elapsed Time: <span className="font-bold text-slate-200">{formatTimer(elapsedSeconds)}</span>
                  </p>
                </div>
              </div>

              {/* Multi-Stage Step Progress Tracker */}
              <div className="space-y-2 font-mono">
                {INGEST_STAGES.map((stage) => {
                  const isPast = stage.id < currentStage;
                  const isCurrent = stage.id === currentStage;
                  const isFuture = stage.id > currentStage;

                  return (
                    <div
                      key={stage.id}
                      className={`p-3 rounded-2xl border transition-all flex items-center justify-between gap-3 ${
                        isCurrent
                          ? "bg-indigo-950/40 border-indigo-500/60 shadow-md shadow-indigo-500/10"
                          : isPast
                          ? "bg-emerald-950/20 border-emerald-500/30 text-slate-300"
                          : "bg-slate-900/40 border-slate-800 text-slate-500"
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        {isPast ? (
                          <div className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          </div>
                        ) : isCurrent ? (
                          <div className="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center shrink-0">
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          </div>
                        ) : (
                          <div className="w-5 h-5 rounded-full bg-slate-800 text-slate-500 flex items-center justify-center text-[10px] shrink-0 font-bold">
                            {stage.id}
                          </div>
                        )}
                        <div className="min-w-0">
                          <p className={`font-bold truncate text-xs ${isCurrent ? "text-indigo-200" : isPast ? "text-slate-200" : "text-slate-500"}`}>
                            {stage.label}
                          </p>
                          <p className="text-[10px] text-slate-400 truncate">{stage.desc}</p>
                        </div>
                      </div>

                      <span className="text-[10px] uppercase font-bold shrink-0">
                        {isPast && <span className="text-emerald-400">Done</span>}
                        {isCurrent && <span className="text-indigo-400 animate-pulse">Running</span>}
                        {isFuture && <span className="text-slate-600">Pending</span>}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* PHASE 3: SUCCESS VIEW */}
          {phase === "success" && result && (
            <div className="space-y-5 py-2 animate-fade-in">
              <div className="text-center space-y-1.5">
                <div className="w-12 h-12 rounded-2xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 flex items-center justify-center mx-auto shadow-lg shadow-emerald-500/20">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <h3 className="text-base font-bold text-white font-mono">
                  {repo.name} Ingested Successfully!
                </h3>
                <p className="text-xs text-slate-400">
                  AST call graphs have been built in Neo4j and vector embeddings are ready in ChromaDB.
                </p>
              </div>

              {/* Statistics Summary Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono text-xs">
                <div className="p-3 rounded-2xl bg-slate-900 border border-slate-800 text-center shadow-inner">
                  <p className="text-[10px] uppercase text-slate-400">Symbols</p>
                  <p className="text-lg font-bold text-indigo-400 mt-0.5">{result.symbols_parsed}</p>
                </div>
                <div className="p-3 rounded-2xl bg-slate-900 border border-slate-800 text-center shadow-inner">
                  <p className="text-[10px] uppercase text-slate-400">Files</p>
                  <p className="text-lg font-bold text-cyan-400 mt-0.5">{result.files_parsed}</p>
                </div>
                <div className="p-3 rounded-2xl bg-slate-900 border border-slate-800 text-center shadow-inner">
                  <p className="text-[10px] uppercase text-slate-400">Graph Edges</p>
                  <p className="text-lg font-bold text-purple-400 mt-0.5">{result.edges_count}</p>
                </div>
                <div className="p-3 rounded-2xl bg-slate-900 border border-slate-800 text-center shadow-inner">
                  <p className="text-[10px] uppercase text-slate-400">Duration</p>
                  <p className="text-lg font-bold text-amber-400 mt-0.5">{result.duration_seconds.toFixed(2)}s</p>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="space-y-2 pt-2">
                <Link
                  href={`/chat?repo=${encodeURIComponent(result.repo_id)}&branch=${encodeURIComponent(branch)}`}
                  className="block"
                  onClick={onClose}
                >
                  <Button
                    variant="glow"
                    size="md"
                    rightIcon={<ArrowRight className="w-4 h-4" />}
                    className="w-full"
                  >
                    Chat with Codebase ({result.repo_id})
                  </Button>
                </Link>

                <div className="flex items-center gap-2">
                  <Link
                    href={`/graph?repo=${encodeURIComponent(result.repo_id)}`}
                    className="flex-1"
                    onClick={onClose}
                  >
                    <Button variant="secondary" size="sm" className="w-full text-xs">
                      Explore AST Graph
                    </Button>
                  </Link>

                  <Button variant="secondary" size="sm" onClick={onClose} className="text-xs">
                    Done
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* PHASE 4: ERROR VIEW */}
          {phase === "error" && (
            <div className="space-y-4 py-2 animate-fade-in">
              <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-bold text-sm text-rose-200">Ingestion Failed</p>
                  <p className="font-mono text-slate-300 break-words">{errorMessage}</p>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <Button variant="secondary" size="md" onClick={handleClose}>
                  Close
                </Button>
                <Button
                  variant="glow"
                  size="md"
                  onClick={handleStartIngestion}
                  leftIcon={<RefreshCw className="w-4 h-4" />}
                >
                  Try Again
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

