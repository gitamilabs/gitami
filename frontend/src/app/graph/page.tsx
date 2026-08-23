"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ProtectedRoute } from "../../components/auth/ProtectedRoute";
import { Sidebar } from "../../components/layout/Sidebar";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import {
  Share2,
  FolderGit2,
  Search,
  Layers,
  Code2,
  ArrowRight,
  Database,
  Shield,
  Zap,
  Activity,
} from "lucide-react";

interface NodeItem {
  id: string;
  name: string;
  kind: "module" | "function" | "class" | "component" | "method";
  file: string;
  lines: string;
  callers: string[];
  callees: string[];
  docstring?: string;
  blastRisk?: number;
}

const SAMPLE_GRAPH_NODES: NodeItem[] = [
  {
    id: "auth.ts::handleCallback",
    name: "handleCallback",
    kind: "function",
    file: "backend/api-service/src/modules/auth/auth.service.ts",
    lines: "174-184",
    callers: ["auth.routes.ts::GET /github/callback"],
    callees: ["exchangeCodeForToken", "fetchGitHubUserProfile", "upsertUser", "signSessionToken"],
    docstring: "Handles the full OAuth callback flow: exchange code → fetch profile → upsert user → sign JWT.",
    blastRisk: 3.2,
  },
  {
    id: "auth.ts::signSessionToken",
    name: "signSessionToken",
    kind: "function",
    file: "backend/api-service/src/modules/auth/auth.service.ts",
    lines: "188-194",
    callers: ["handleCallback"],
    callees: ["SignJWT.sign"],
    docstring: "Signs a JWT session token for a given user ID with HS256 algorithm.",
    blastRisk: 4.8,
  },
  {
    id: "app.py::AutonomousAgentLoop",
    name: "AutonomousAgentLoop",
    kind: "class",
    file: "backend/ai-service/src/ai_service/agent/agent_loop.py",
    lines: "10-314",
    callers: ["app.py::agent_chat_stream"],
    callees: ["_call_llm_json", "execute_tool_by_name", "_extract_summary_and_citations"],
    docstring: "Autonomous ReAct Agent Loop executing iterative tool calls and SSE streaming trace.",
    blastRisk: 7.5,
  },
  {
    id: "app.py::DualLLMClient",
    name: "DualLLMClient",
    kind: "class",
    file: "backend/ai-service/src/ai_service/agent/llm_client.py",
    lines: "15-120",
    callers: ["AutonomousAgentLoop", "agent_chat_query"],
    callees: ["google.genai.Client", "groq.Groq"],
    docstring: "Pairs Gemini 2.0 Flash orchestrator with Groq Llama-3.3-70B high-throughput worker.",
    blastRisk: 8.2,
  },
  {
    id: "Navbar.tsx::Navbar",
    name: "Navbar",
    kind: "component",
    file: "frontend/src/components/layout/Navbar.tsx",
    lines: "20-120",
    callers: ["layout.tsx::RootLayout"],
    callees: ["useAuthStore", "aiApi.checkHealth"],
    docstring: "Top navigation bar with service status and authentication controls.",
    blastRisk: 1.2,
  },
];

function GraphContent() {
  const [search, setSearch] = useState("");
  const [selectedKind, setSelectedKind] = useState<string>("all");
  const [activeNode, setActiveNode] = useState<NodeItem>(SAMPLE_GRAPH_NODES[0]);

  const filteredNodes = SAMPLE_GRAPH_NODES.filter((node) => {
    const matchesSearch =
      node.name.toLowerCase().includes(search.toLowerCase()) ||
      node.file.toLowerCase().includes(search.toLowerCase());
    const matchesKind = selectedKind === "all" || node.kind === selectedKind;
    return matchesSearch && matchesKind;
  });

  const getKindColor = (kind: string) => {
    switch (kind) {
      case "function":
        return "bg-indigo-500/10 text-indigo-400 border-indigo-500/30";
      case "class":
        return "bg-purple-500/10 text-purple-400 border-purple-500/30";
      case "component":
        return "bg-pink-500/10 text-pink-400 border-pink-500/30";
      case "method":
        return "bg-cyan-500/10 text-cyan-400 border-cyan-500/30";
      default:
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
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
              Neo4j AST Topology Explorer
            </Badge>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Knowledge Base Code Graph & AST
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Explore symbols, callers, callees, and transitive blast radius paths mapped by Tree-sitter and Neo4j.
          </p>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-slate-400 font-medium mr-1">Node Kinds:</span>
          <button
            onClick={() => setSelectedKind("all")}
            className={`px-2.5 py-1 rounded-lg border text-xs font-mono transition-colors ${
              selectedKind === "all"
                ? "bg-slate-800 text-white border-slate-600"
                : "bg-slate-900 text-slate-400 border-slate-800"
            }`}
          >
            All
          </button>
          <button
            onClick={() => setSelectedKind("function")}
            className={`px-2.5 py-1 rounded-lg border text-xs font-mono transition-colors ${
              selectedKind === "function"
                ? "bg-indigo-600/30 text-indigo-300 border-indigo-500"
                : "bg-indigo-950/40 text-indigo-400 border-indigo-900/60"
            }`}
          >
            Function
          </button>
          <button
            onClick={() => setSelectedKind("class")}
            className={`px-2.5 py-1 rounded-lg border text-xs font-mono transition-colors ${
              selectedKind === "class"
                ? "bg-purple-600/30 text-purple-300 border-purple-500"
                : "bg-purple-950/40 text-purple-400 border-purple-900/60"
            }`}
          >
            Class
          </button>
          <button
            onClick={() => setSelectedKind("component")}
            className={`px-2.5 py-1 rounded-lg border text-xs font-mono transition-colors ${
              selectedKind === "component"
                ? "bg-pink-600/30 text-pink-300 border-pink-500"
                : "bg-pink-950/40 text-pink-400 border-pink-900/60"
            }`}
          >
            React Component
          </button>
        </div>

        {/* Main Grid: Left Node List + Right Inspector */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Node List */}
          <div className="lg:col-span-5 glass-panel rounded-3xl p-4 border border-slate-800 space-y-3">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search symbol or file path..."
                className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
              {filteredNodes.map((node) => {
                const isSelected = activeNode.id === node.id;
                return (
                  <div
                    key={node.id}
                    onClick={() => setActiveNode(node)}
                    className={`p-3 rounded-2xl border cursor-pointer transition-all ${
                      isSelected
                        ? "bg-indigo-950/40 border-indigo-500 shadow-md shadow-indigo-600/10"
                        : "glass-card border-slate-800/80 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-xs font-bold text-slate-200 font-mono">
                        {node.name}
                      </span>
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${getKindColor(
                          node.kind
                        )}`}
                      >
                        {node.kind}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 font-mono truncate">
                      {node.file}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Node Inspector */}
          <div className="lg:col-span-7 glass-panel rounded-3xl p-6 border border-slate-800 space-y-5">
            <div className="flex items-start justify-between border-b border-slate-800/80 pb-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`text-xs font-mono px-2.5 py-0.5 rounded-full border ${getKindColor(
                      activeNode.kind
                    )}`}
                  >
                    {activeNode.kind}
                  </span>
                  <span className="text-xs font-mono text-slate-400">
                    Lines: {activeNode.lines}
                  </span>
                </div>
                <h2 className="text-xl font-bold text-white font-mono">
                  {activeNode.name}
                </h2>
                <p className="text-xs text-slate-400 font-mono mt-0.5 break-all">
                  {activeNode.file}
                </p>
              </div>

              {activeNode.blastRisk && (
                <div className="text-right p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/30">
                  <p className="text-[10px] uppercase font-mono text-rose-400 font-semibold">
                    Blast Risk
                  </p>
                  <p className="text-lg font-bold text-rose-300 font-mono">
                    {activeNode.blastRisk.toFixed(1)} / 10
                  </p>
                </div>
              )}
            </div>

            {/* Docstring */}
            {activeNode.docstring && (
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
                  Docstring / Description
                </p>
                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300 leading-relaxed font-mono">
                  {activeNode.docstring}
                </div>
              </div>
            )}

            {/* Callers vs Callees */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-3.5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-2">
                <p className="text-xs font-semibold text-indigo-300 flex items-center gap-1.5 font-mono">
                  <Share2 className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Incoming Callers ({activeNode.callers.length})</span>
                </p>
                <ul className="space-y-1 text-[11px] font-mono text-slate-300">
                  {activeNode.callers.map((c, i) => (
                    <li
                      key={i}
                      className="p-1.5 rounded-lg bg-slate-950/80 border border-slate-800/60 truncate"
                    >
                      {c}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="p-3.5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-2">
                <p className="text-xs font-semibold text-cyan-300 flex items-center gap-1.5 font-mono">
                  <ArrowRight className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Outgoing Callees ({activeNode.callees.length})</span>
                </p>
                <ul className="space-y-1 text-[11px] font-mono text-slate-300">
                  {activeNode.callees.map((c, i) => (
                    <li
                      key={i}
                      className="p-1.5 rounded-lg bg-slate-950/80 border border-slate-800/60 truncate"
                    >
                      {c}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Action shortcut */}
            <div className="pt-2">
              <Link
                href={`/chat?repo=final-year-project`}
                className="block"
              >
                <Button
                  variant="secondary"
                  size="sm"
                  rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                  className="w-full text-xs"
                >
                  Query Blast Radius in Agentic Chat for &quot;{activeNode.name}&quot;
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function GraphPage() {
  return (
    <ProtectedRoute>
      <GraphContent />
    </ProtectedRoute>
  );
}
