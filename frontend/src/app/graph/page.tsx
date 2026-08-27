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
  GitBranch,
  FileCode,
  Sparkles,
  ArrowDownRight,
  CornerDownRight,
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
  sampleCode?: string;
}

const SAMPLE_GRAPH_NODES: NodeItem[] = [
  {
    id: "auth.ts::handleCallback",
    name: "handleCallback",
    kind: "function",
    file: "backend/api-service/src/modules/auth/auth.service.ts",
    lines: "174-184",
    callers: ["auth.routes.ts::GET /github/callback", "auth.controller.ts::callbackHandler"],
    callees: ["exchangeCodeForToken", "fetchGitHubUserProfile", "upsertUser", "signSessionToken"],
    docstring: "Handles the full OAuth callback flow: exchange code → fetch profile → upsert user → sign JWT session.",
    blastRisk: 3.2,
    sampleCode: `export async function handleCallback(code: string): Promise<AuthSession> {\n  const token = await exchangeCodeForToken(code);\n  const profile = await fetchGitHubUserProfile(token);\n  const user = await upsertUser(profile);\n  const sessionToken = await signSessionToken(user.id);\n  return { user, sessionToken };\n}`,
  },
  {
    id: "auth.ts::signSessionToken",
    name: "signSessionToken",
    kind: "function",
    file: "backend/api-service/src/modules/auth/auth.service.ts",
    lines: "188-194",
    callers: ["handleCallback", "refreshTokenHandler"],
    callees: ["SignJWT.sign", "jose.createSecretKey"],
    docstring: "Signs a JWT session token for a given user ID with HS256 algorithm and 7-day expiration.",
    blastRisk: 4.8,
    sampleCode: `export async function signSessionToken(userId: string): Promise<string> {\n  return new SignJWT({ sub: userId })\n    .setProtectedHeader({ alg: "HS256" })\n    .setExpirationTime("7d")\n    .sign(JWT_SECRET);\n}`,
  },
  {
    id: "agent_loop.py::AutonomousAgentLoop",
    name: "AutonomousAgentLoop",
    kind: "class",
    file: "backend/ai-service/src/ai_service/agent/agent_loop.py",
    lines: "10-314",
    callers: ["app.py::agent_chat_stream", "test_chat_page.py::test_agent"],
    callees: ["_call_llm_json", "execute_tool_by_name", "_extract_summary_and_citations"],
    docstring: "Autonomous ReAct Agent Loop executing iterative tool calls, reasoning traces, and SSE streaming.",
    blastRisk: 7.5,
    sampleCode: `class AutonomousAgentLoop:\n    def __init__(self, llm_client: DualLLMClient):\n        self.llm = llm_client\n\n    async def stream_query(self, user_query: str, repo_id: str):\n        async for event in self._react_cycle(user_query, repo_id):\n            yield f"data: {event.json()}\\n\\n"`,
  },
  {
    id: "llm_client.py::DualLLMClient",
    name: "DualLLMClient",
    kind: "class",
    file: "backend/ai-service/src/ai_service/agent/llm_client.py",
    lines: "15-120",
    callers: ["AutonomousAgentLoop", "agent_chat_query"],
    callees: ["google.genai.Client", "groq.Groq"],
    docstring: "Pairs Gemini 2.0 Flash orchestrator with Groq Llama-3.3-70B high-throughput AST hunk worker.",
    blastRisk: 8.2,
    sampleCode: `class DualLLMClient:\n    def __init__(self):\n        self.gemini = genai.Client(api_key=GEMINI_API_KEY)\n        self.groq = Groq(api_key=GROQ_API_KEY)\n\n    def generate_plan(self, prompt: str) -> str:\n        return self.gemini.models.generate_content(...)`,
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
    sampleCode: `export const Navbar: React.FC = () => {\n  const { user, token, login } = useAuthStore();\n  return <header className="glass-panel sticky top-0 ...">...</header>;\n};`,
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

  const getKindBadgeVariant = (kind: string): "primary" | "secondary" | "success" | "warning" | "danger" | "info" | "purple" => {
    switch (kind) {
      case "function":
        return "primary";
      case "class":
        return "purple";
      case "component":
        return "info";
      case "method":
        return "info";
      default:
        return "success";
    }
  };

  const getRiskColor = (risk: number) => {
    if (risk >= 7.0) return "text-rose-400 border-rose-500/30 bg-rose-500/10";
    if (risk >= 4.0) return "text-amber-400 border-amber-500/30 bg-amber-500/10";
    return "text-emerald-400 border-emerald-500/30 bg-emerald-500/10";
  };

  return (
    <div className="flex max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 gap-6">
      <Sidebar />

      <div className="flex-1 space-y-6 min-w-0">
        {/* Header */}
        <div className="glass-panel rounded-2xl p-6 border border-slate-800 relative overflow-hidden">

          <div className="relative z-10">
            <div className="flex items-center gap-2 mb-1.5">
              <Badge variant="primary" size="sm" className="font-mono text-[10px]" dot>
                Neo4j AST Topology Explorer
              </Badge>
              <Badge variant="info" size="sm" className="font-mono text-[10px]">
                Tree-sitter Parsed
              </Badge>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Knowledge Base Code Graph & AST
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-2xl">
              Inspect symbol declarations, cross-file callers, outgoing callees, and deterministic blast radius scores mapped in Neo4j.
            </p>
          </div>
        </div>

        {/* Visual Graph Topology Flow Banner */}
        <div className="glass-panel rounded-2xl p-6 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
              <Share2 className="w-4 h-4 text-indigo-400" />
              <span>AST Call Graph Dependency Flow</span>
            </h3>
            <span className="text-[11px] font-mono text-slate-400">
              Active Symbol: <strong className="text-indigo-300">{activeNode.name}</strong>
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs items-center">
            {/* Left: Incoming Callers */}
            <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-indigo-400 font-bold text-xs">
                <span>Incoming Callers</span>
                <Badge variant="primary" size="sm">{activeNode.callers.length}</Badge>
              </div>
              <div className="space-y-1 max-h-28 overflow-y-auto">
                {activeNode.callers.map((caller, i) => (
                  <div
                    key={i}
                    className="p-2 rounded-xl bg-slate-950/80 border border-slate-800/80 text-[11px] text-slate-300 truncate"
                  >
                    {caller}
                  </div>
                ))}
              </div>
            </div>

            {/* Center: Active Symbol Node */}
            <div className="p-5 rounded-xl bg-indigo-950/40 border-2 border-indigo-500/80 text-center space-y-2 shadow-lg shadow-indigo-500/10 relative">
              <Badge variant={getKindBadgeVariant(activeNode.kind)} size="sm" className="font-mono text-[10px]">
                {activeNode.kind.toUpperCase()}
              </Badge>
              <h4 className="text-sm font-bold text-white truncate">{activeNode.name}</h4>
              <p className="text-[10px] text-slate-400 truncate">Lines: {activeNode.lines}</p>
              <div className="text-[10px] text-cyan-300 bg-cyan-950/40 py-1 px-2 rounded-lg border border-cyan-900/40 truncate">
                {activeNode.file.split("/").pop()}
              </div>
            </div>

            {/* Right: Outgoing Callees */}
            <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-cyan-400 font-bold text-xs">
                <span>Outgoing Callees</span>
                <Badge variant="info" size="sm">{activeNode.callees.length}</Badge>
              </div>
              <div className="space-y-1 max-h-28 overflow-y-auto">
                {activeNode.callees.map((callee, i) => (
                  <div
                    key={i}
                    className="p-2 rounded-xl bg-slate-950/80 border border-slate-800/80 text-[11px] text-slate-300 truncate"
                  >
                    {callee}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-slate-400 font-medium font-mono text-[11px] mr-1">Symbol Type:</span>
          {(["all", "function", "class", "component", "method"] as const).map((kind) => (
            <button
              key={kind}
              onClick={() => setSelectedKind(kind)}
              className={`px-3 py-1 rounded-xl border text-xs font-mono font-medium transition-all ${
                selectedKind === kind
                  ? "bg-indigo-600/30 text-indigo-200 border-indigo-500 shadow-sm"
                  : "bg-slate-900/80 text-slate-400 border-slate-800 hover:text-slate-200"
              }`}
            >
              {kind.charAt(0).toUpperCase() + kind.slice(1)}
            </button>
          ))}
        </div>

        {/* Main Grid: Left Node List + Right Detailed Inspector */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Node List */}
          <div className="lg:col-span-5 glass-panel rounded-2xl p-4 border border-slate-800 space-y-3">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search symbol, class, or path..."
                className="w-full bg-slate-900/90 border border-slate-800 rounded-xl pl-10 pr-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-mono shadow-inner"
              />
            </div>

            <div className="space-y-2 max-h-[560px] overflow-y-auto pr-1">
              {filteredNodes.map((node) => {
                const isSelected = activeNode.id === node.id;
                return (
                  <div
                    key={node.id}
                    onClick={() => setActiveNode(node)}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? "bg-indigo-950/50 border-indigo-500 shadow-md shadow-indigo-600/15"
                        : "glass-card border-slate-800/80 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-xs font-bold text-slate-100 font-mono">
                        {node.name}
                      </span>
                      <Badge
                        variant={getKindBadgeVariant(node.kind)}
                        size="sm"
                        className="font-mono text-[9px]"
                      >
                        {node.kind}
                      </Badge>
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
          <div className="lg:col-span-7 glass-panel rounded-2xl p-6 border border-slate-800 space-y-5">
            <div className="flex items-start justify-between border-b border-slate-800/80 pb-5 gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <Badge variant={getKindBadgeVariant(activeNode.kind)} size="sm" className="font-mono">
                    {activeNode.kind}
                  </Badge>
                  <span className="text-xs font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded-md">
                    Lines: {activeNode.lines}
                  </span>
                </div>
                <h2 className="text-2xl font-black text-white font-mono tracking-tight">
                  {activeNode.name}
                </h2>
                <p className="text-xs text-slate-400 font-mono mt-1 break-all">
                  {activeNode.file}
                </p>
              </div>

              {activeNode.blastRisk && (
                <div
                  className={`text-right p-3 rounded-xl border ${getRiskColor(
                    activeNode.blastRisk
                  )} shrink-0 shadow-sm`}
                >
                  <p className="text-[10px] uppercase font-mono font-bold tracking-wider">
                    Blast Risk
                  </p>
                  <p className="text-xl font-extrabold font-mono mt-0.5">
                    {activeNode.blastRisk.toFixed(1)} / 10
                  </p>
                </div>
              )}
            </div>

            {/* Docstring */}
            {activeNode.docstring && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono mb-1.5">
                  Docstring / Functional Purpose
                </p>
                <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 text-xs text-slate-200 leading-relaxed font-sans shadow-inner">
                  {activeNode.docstring}
                </div>
              </div>
            )}

            {/* Code Snippet Preview */}
            {activeNode.sampleCode && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono mb-1.5">
                  AST Symbol Source Hunk
                </p>
                <pre className="p-3.5 rounded-xl bg-slate-950/90 border border-slate-800 text-xs text-indigo-300 font-mono overflow-x-auto leading-relaxed shadow-inner">
                  {activeNode.sampleCode}
                </pre>
              </div>
            )}

            {/* Callers vs Callees Breakdown */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2.5">
                <div className="flex items-center justify-between text-indigo-300 font-bold font-mono text-xs">
                  <span className="flex items-center gap-1.5">
                    <Share2 className="w-3.5 h-3.5 text-indigo-400" />
                    Incoming Callers
                  </span>
                  <Badge variant="primary" size="sm">{activeNode.callers.length}</Badge>
                </div>
                <ul className="space-y-1.5 text-[11px] font-mono text-slate-300">
                  {activeNode.callers.map((c, i) => (
                    <li
                      key={i}
                      className="p-2 rounded-xl bg-slate-950/80 border border-slate-800/80 truncate"
                    >
                      {c}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2.5">
                <div className="flex items-center justify-between text-cyan-300 font-bold font-mono text-xs">
                  <span className="flex items-center gap-1.5">
                    <ArrowRight className="w-3.5 h-3.5 text-cyan-400" />
                    Outgoing Callees
                  </span>
                  <Badge variant="info" size="sm">{activeNode.callees.length}</Badge>
                </div>
                <ul className="space-y-1.5 text-[11px] font-mono text-slate-300">
                  {activeNode.callees.map((c, i) => (
                    <li
                      key={i}
                      className="p-2 rounded-xl bg-slate-950/80 border border-slate-800/80 truncate"
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
                  variant="glow"
                  size="md"
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                  className="w-full text-xs"
                >
                  Ask Agentic RAG about &quot;{activeNode.name}&quot; Blast Radius
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

