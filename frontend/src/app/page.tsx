"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuthStore } from "../store/authStore";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import {
  Shield,
  Bot,
  GitFork,
  Database,
  Share2,
  Github,
  Sparkles,
  Zap,
  CheckCircle2,
  ArrowRight,
  Code2,
  Terminal,
  Activity,
  Layers,
  Cpu,
  Check,
  X as CloseIcon,
  Search,
  Lock,
} from "lucide-react";

export default function LandingPage() {
  const { token, login } = useAuthStore();
  const [activeArchTab, setActiveArchTab] = useState<"graph" | "vector" | "agent" | "mcp">("graph");

  const features = [
    {
      title: "AST-Level Static Code Graphs",
      description:
        "Parsed via Tree-sitter into multi-tenant Neo4j graphs capturing functions, classes, CALLS, IMPORTS, and cross-file dependencies.",
      icon: <Share2 className="w-5 h-5 text-indigo-400" />,
      badge: "Neo4j Graph DB",
      accent: "indigo",
    },
    {
      title: "Dual-LLM Agentic RAG",
      description:
        "Orchestrated with Google Gemini 2.0 Flash for ReAct planning and Groq Llama-3.3-70B for high-throughput AST hunk auditing.",
      icon: <Bot className="w-5 h-5 text-cyan-400" />,
      badge: "Gemini + Groq",
      accent: "cyan",
    },
    {
      title: "Transitive Ripple Blast Radius",
      description:
        "Deterministic graph algorithms calculate the downstream blast radius and risk score across all caller hierarchies before merging PRs.",
      icon: <Zap className="w-5 h-5 text-rose-400" />,
      badge: "Risk Engine",
      accent: "rose",
    },
    {
      title: "Semantic Vector Search",
      description:
        "ChromaDB semantic embeddings powered by Gemini embeddings with staleness management and batch chunk deduplication.",
      icon: <Database className="w-5 h-5 text-emerald-400" />,
      badge: "ChromaDB",
      accent: "emerald",
    },
    {
      title: "Model Context Protocol (MCP)",
      description:
        "Exposes rich Knowledge Base tools (hybrid search, blast radius, symbol inspection) via FastMCP for external AI pairing.",
      icon: <Terminal className="w-5 h-5 text-amber-400" />,
      badge: "FastMCP 3.4",
      accent: "amber",
    },
    {
      title: "GitHub App & Control Plane",
      description:
        "High-performance Bun + Hono API gateway with GitHub OAuth, webhook signature verification, and automated PR evaluations.",
      icon: <GitFork className="w-5 h-5 text-purple-400" />,
      badge: "Bun + Hono",
      accent: "purple",
    },
  ];

  const stats = [
    { value: "< 250ms", label: "AST Graph Traversal", subtitle: "Deterministic Cypher queries" },
    { value: "0 Disk Writes", label: "In-Memory Tarball Stream", subtitle: "GitHub API tarball streaming" },
    { value: "100% Verified", label: "Ground Truth Citations", subtitle: "Exact file, line & symbol IDs" },
    { value: "Dual-LLM", label: "ReAct Agent Engine", subtitle: "Gemini 2.0 + Groq 70B" },
  ];

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)]">
      {/* Hero Section */}
      <section className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-20 text-center relative overflow-hidden">
        {/* Glow backdrop circles */}
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[380px] bg-gradient-to-r from-indigo-500/15 via-cyan-500/10 to-indigo-500/15 rounded-full blur-[140px] pointer-events-none -z-10" />

        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs font-semibold mb-8 shadow-sm shadow-indigo-500/10 animate-fade-in">
          <Sparkles className="w-4 h-4 text-indigo-400" />
          <span>Next-Gen Autonomous Codebase Knowledge Base & AST Graph</span>
        </div>

        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-black tracking-tight text-white max-w-5xl mx-auto leading-[1.12]">
          Architectural Code Graph &{" "}
          <span className="bg-gradient-to-r from-indigo-400 via-cyan-400 to-indigo-300 bg-clip-text text-transparent">
            Agentic RAG
          </span>
        </h1>

        <p className="mt-6 text-base sm:text-lg text-slate-300 max-w-2xl mx-auto leading-relaxed font-sans">
          Stop relying on naive regex linters and hallucinating diff reviewers.
          Sentinel pairs <strong>Neo4j AST code graphs</strong> with <strong>ChromaDB vector embeddings</strong> to answer complex cross-file dependency and ripple blast radius questions.
        </p>

        {/* CTA Buttons */}
        <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
          {token ? (
            <Link href="/chat">
              <Button
                variant="glow"
                size="lg"
                rightIcon={<ArrowRight className="w-4 h-4" />}
              >
                Launch Agentic RAG Chat
              </Button>
            </Link>
          ) : (
            <Button
              variant="glow"
              size="lg"
              leftIcon={<Github className="w-5 h-5" />}
              rightIcon={<ArrowRight className="w-4 h-4" />}
              onClick={() => login()}
            >
              Get Started with GitHub
            </Button>
          )}

          <Link href="/chat">
            <Button variant="secondary" size="lg" leftIcon={<Bot className="w-4 h-4 text-cyan-400" />}>
              Try Live Demo Chat
            </Button>
          </Link>
        </div>

        {/* Stats Strip */}
        <div className="mt-14 max-w-5xl mx-auto grid grid-cols-2 lg:grid-cols-4 gap-4 text-left">
          {stats.map((stat, i) => (
            <div
              key={i}
              className="glass-card rounded-2xl p-4 border border-slate-800/80 shadow-sm"
            >
              <p className="text-xl sm:text-2xl font-extrabold text-white font-mono">{stat.value}</p>
              <p className="text-xs font-bold text-slate-200 mt-0.5">{stat.label}</p>
              <p className="text-[11px] text-slate-400 mt-0.5 font-mono truncate">{stat.subtitle}</p>
            </div>
          ))}
        </div>

        {/* Live Architecture Flow Preview Card with Interactive Tabs */}
        <div className="mt-12 max-w-5xl mx-auto glass-panel-elevated rounded-3xl p-6 sm:p-8 border border-slate-800 shadow-2xl relative text-left">
          {/* Header Bar */}
          <div className="flex flex-wrap items-center justify-between border-b border-slate-800/80 pb-4 mb-6 gap-3">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-rose-500/80 inline-block" />
              <span className="w-3 h-3 rounded-full bg-amber-500/80 inline-block" />
              <span className="w-3 h-3 rounded-full bg-emerald-500/80 inline-block" />
              <span className="text-xs font-mono text-slate-400 ml-2 font-medium">
                sentinel-dual-knowledge-base-runtime.yaml
              </span>
            </div>

            {/* Tab Buttons */}
            <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-900 border border-slate-800">
              <button
                onClick={() => setActiveArchTab("graph")}
                className={`px-3 py-1 rounded-lg text-xs font-mono font-medium transition-all ${
                  activeArchTab === "graph"
                    ? "bg-indigo-600/30 text-indigo-300 border border-indigo-500/50 shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                1. AST Neo4j
              </button>
              <button
                onClick={() => setActiveArchTab("vector")}
                className={`px-3 py-1 rounded-lg text-xs font-mono font-medium transition-all ${
                  activeArchTab === "vector"
                    ? "bg-cyan-600/30 text-cyan-300 border border-cyan-500/50 shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                2. ChromaDB
              </button>
              <button
                onClick={() => setActiveArchTab("agent")}
                className={`px-3 py-1 rounded-lg text-xs font-mono font-medium transition-all ${
                  activeArchTab === "agent"
                    ? "bg-purple-600/30 text-purple-300 border border-purple-500/50 shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                3. Dual-LLM Loop
              </button>
              <button
                onClick={() => setActiveArchTab("mcp")}
                className={`px-3 py-1 rounded-lg text-xs font-mono font-medium transition-all ${
                  activeArchTab === "mcp"
                    ? "bg-amber-600/30 text-amber-300 border border-amber-500/50 shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                4. FastMCP
              </button>
            </div>
          </div>

          {/* Interactive Tab Body */}
          {activeArchTab === "graph" && (
            <div className="space-y-4 animate-fade-in font-mono text-xs">
              <div className="flex items-center justify-between text-indigo-400 font-bold">
                <div className="flex items-center gap-2">
                  <Share2 className="w-4 h-4" />
                  <span>AST Call Graph Construction (Neo4j Multi-Tenant)</span>
                </div>
                <Badge variant="primary" size="sm">Indexed in ~3.8s</Badge>
              </div>
              <p className="text-slate-300 text-xs font-sans leading-relaxed">
                Tree-sitter extracts Symbol nodes (functions, classes, methods) with start/end lines and constructs directional CALLS and IMPORTS edges for exact transitive graph queries.
              </p>
              <div className="p-3.5 rounded-2xl bg-slate-950/90 border border-slate-800 text-indigo-300 space-y-1.5">
                <p className="text-slate-500 text-[11px] font-mono">// Cypher Transitive Blast Radius Query</p>
                <p className="text-slate-200">
                  MATCH (root:Symbol &#123; name: $symbol_name &#125;)
                </p>
                <p className="text-indigo-300">
                  MATCH path = (root)&lt;-[:CALLS*1..4]-(caller:Symbol)
                </p>
                <p className="text-emerald-400">
                  RETURN caller.name, length(path) AS depth, caller.file ORDER BY depth ASC
                </p>
              </div>
            </div>
          )}

          {activeArchTab === "vector" && (
            <div className="space-y-4 animate-fade-in font-mono text-xs">
              <div className="flex items-center justify-between text-cyan-400 font-bold">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4" />
                  <span>ChromaDB Semantic Vector KB (Gemini Embeddings)</span>
                </div>
                <Badge variant="info" size="sm">768-dim Vectors</Badge>
              </div>
              <p className="text-slate-300 text-xs font-sans leading-relaxed">
                High-density code chunking with AST context: function signatures, docstrings, and bodies are embedded with Gemini embedding models and filtered by repository tenant space.
              </p>
              <div className="p-3.5 rounded-2xl bg-slate-950/90 border border-slate-800 text-cyan-300 space-y-1.5">
                <p className="text-slate-500 text-[11px] font-mono">// Hybrid Vector Query with Metadata Filter</p>
                <p className="text-slate-200">
                  collection = chroma_client.get_collection(&quot;repo_knowledge_base&quot;)
                </p>
                <p className="text-cyan-300">
                  results = collection.query(query_texts=[&quot;authentication JWT session token verification&quot;], where=&#123;&quot;repo&quot;: &quot;final-year-project&quot;&#125;)
                </p>
                <p className="text-emerald-400">
                  // Returns top-k passages with cosine similarity scores &gt; 0.86
                </p>
              </div>
            </div>
          )}

          {activeArchTab === "agent" && (
            <div className="space-y-4 animate-fade-in font-mono text-xs">
              <div className="flex items-center justify-between text-purple-400 font-bold">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4" />
                  <span>Dual-LLM Autonomous ReAct Loop (Gemini + Groq)</span>
                </div>
                <Badge variant="purple" size="sm">SSE Streaming</Badge>
              </div>
              <p className="text-slate-300 text-xs font-sans leading-relaxed">
                Google Gemini 2.0 Flash acts as the autonomous planning brain executing tool steps, while Groq Llama-3.3-70B verifies AST hunks at ultra-low latency with Server-Sent Events (SSE).
              </p>
              <div className="p-3.5 rounded-2xl bg-slate-950/90 border border-slate-800 text-purple-300 space-y-1.5">
                <p className="text-slate-500 text-[11px] font-mono">// Autonomous ReAct Trace Stream</p>
                <p className="text-slate-200">event: thought &#8594; &quot;Step 1: Inspect call hierarchy for handleCallback&quot;</p>
                <p className="text-purple-300">event: tool_call &#8594; get_blast_radius(symbol=&quot;handleCallback&quot;)</p>
                <p className="text-emerald-400">event: answer_chunk &#8594; &quot;Modifying handleCallback impacts 4 direct callers and 2 downstream services [1][2]&quot;</p>
              </div>
            </div>
          )}

          {activeArchTab === "mcp" && (
            <div className="space-y-4 animate-fade-in font-mono text-xs">
              <div className="flex items-center justify-between text-amber-400 font-bold">
                <div className="flex items-center gap-2">
                  <Terminal className="w-4 h-4" />
                  <span>Model Context Protocol (FastMCP 3.4 API Tools)</span>
                </div>
                <Badge variant="warning" size="sm">FastMCP SDK</Badge>
              </div>
              <p className="text-slate-300 text-xs font-sans leading-relaxed">
                Exposes standardized tool interfaces to IDE AI assistants (Claude, Cursor, Copilot) via FastMCP server endpoints for blast radius, symbol inspection, and vector lookups.
              </p>
              <div className="p-3.5 rounded-2xl bg-slate-950/90 border border-slate-800 text-amber-300 space-y-1.5">
                <p className="text-slate-500 text-[11px] font-mono">// MCP Tool Registration</p>
                <p className="text-slate-200">@mcp.tool()</p>
                <p className="text-amber-300">def calculate_blast_radius(symbol: str, depth: int = 3) -&gt; BlastRadiusResult:</p>
                <p className="text-emerald-400">    &quot;&quot;&quot;Evaluates ripple impact across AST hierarchy in Neo4j.&quot;&quot;&quot;</p>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Feature Grid */}
      <section className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 border-t border-slate-800/80">
        <div className="text-center max-w-3xl mx-auto mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs font-semibold mb-3">
            <span>Enterprise Microservice Suite</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Built for Complex Codebases & Multi-File Architecture
          </h2>
          <p className="mt-3 text-sm sm:text-base text-slate-400">
            Engineered for engineering organizations requiring deep architectural guarantees and surgical PR patch synthesis.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, i) => (
            <div
              key={i}
              className="glass-card glass-card-hover rounded-3xl p-6 border border-slate-800 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="p-3 rounded-2xl bg-slate-900 border border-slate-800 shadow-inner">
                    {feature.icon}
                  </div>
                  <Badge variant="primary" size="sm" className="font-mono text-[10px]">
                    {feature.badge}
                  </Badge>
                </div>
                <h3 className="text-base sm:text-lg font-bold text-slate-100 mb-2 tracking-tight">
                  {feature.title}
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed font-sans">
                  {feature.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Comparison Section: Traditional Linter vs Sentinel */}
      <section className="w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="glass-panel rounded-3xl p-6 sm:p-8 border border-slate-800">
          <div className="text-center mb-8">
            <h3 className="text-2xl font-bold text-white tracking-tight">
              Why Sentinel AST Graph Beats Naive LLM Reviewers
            </h3>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              Deterministic graph topology vs blind LLM token completions.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
            <div className="p-5 rounded-2xl bg-rose-500/5 border border-rose-500/20 space-y-3">
              <div className="flex items-center gap-2 text-rose-400 font-bold text-sm">
                <CloseIcon className="w-4 h-4" />
                <span>Naive LLM Diff Reviewers</span>
              </div>
              <ul className="space-y-2 text-slate-400 font-sans text-xs">
                <li className="flex items-start gap-2">
                  <span className="text-rose-400 font-bold">&#10007;</span>
                  <span>Blind to cross-file call hierarchies and un-imported callers.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-rose-400 font-bold">&#10007;</span>
                  <span>Hallucinates function signatures not present in PR diff.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-rose-400 font-bold">&#10007;</span>
                  <span>Cannot compute transitive ripple blast radius before merging.</span>
                </li>
              </ul>
            </div>

            <div className="p-5 rounded-2xl bg-emerald-500/5 border border-emerald-500/30 space-y-3">
              <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
                <Check className="w-4 h-4" />
                <span>Sentinel AI Platform</span>
              </div>
              <ul className="space-y-2 text-slate-300 font-sans text-xs">
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 font-bold">&#10003;</span>
                  <span>Tree-sitter AST mapped to Neo4j CALLS & IMPORTS graph.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 font-bold">&#10003;</span>
                  <span>Exact citation cards with line numbers and ground truth snippets.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 font-bold">&#10003;</span>
                  <span>Deterministic blast risk calculation on every commit & PR.</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="w-full border-t border-slate-800/80 py-8 text-center text-xs text-slate-400">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-indigo-400" />
            <span className="font-bold text-slate-300">Sentinel AI Platform</span>
            <span>— Autonomous Knowledge Base Engine</span>
          </div>
          <p className="font-mono text-[11px] text-slate-500">
            FastMCP • Tree-sitter • Neo4j • ChromaDB • Gemini 2.0 Flash • Groq
          </p>
        </div>
      </footer>
    </div>
  );
}

