"use client";

import React from "react";
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
} from "lucide-react";

export default function LandingPage() {
  const { token, login } = useAuthStore();

  const features = [
    {
      title: "AST-Level Static Code Graphs",
      description:
        "Parsed via Tree-sitter into multi-tenant Neo4j graphs capturing functions, classes, CALLS, IMPORTS, and cross-file dependencies.",
      icon: <Share2 className="w-6 h-6 text-indigo-400" />,
      badge: "Neo4j Graph DB",
    },
    {
      title: "Dual-LLM Agentic RAG",
      description:
        "Orchestrated with Google Gemini 2.0 Flash for planning and Groq Llama-3.3-70B for high-throughput AST hunk auditing.",
      icon: <Bot className="w-6 h-6 text-cyan-400" />,
      badge: "Gemini + Groq",
    },
    {
      title: "Transitive Ripple Blast Radius",
      description:
        "Deterministic graph algorithms calculate the downstream blast radius and risk score across all caller hierarchies before merging PRs.",
      icon: <Zap className="w-6 h-6 text-rose-400" />,
      badge: "Risk Engine",
    },
    {
      title: "Semantic Vector Search",
      description:
        "ChromaDB semantic embeddings powered by Gemini embeddings with staleness management and batch chunk deduplication.",
      icon: <Database className="w-6 h-6 text-emerald-400" />,
      badge: "ChromaDB",
    },
    {
      title: "Model Context Protocol (MCP)",
      description:
        "Exposes rich Knowledge Base tools (hybrid search, blast radius, symbol inspection) via FastMCP for AI pairing.",
      icon: <Terminal className="w-6 h-6 text-amber-400" />,
      badge: "FastMCP 3.4",
    },
    {
      title: "GitHub App & Control Plane",
      description:
        "High-performance Bun + Hono API gateway with GitHub OAuth, webhook signature verification, and automated PR evaluations.",
      icon: <GitFork className="w-6 h-6 text-purple-400" />,
      badge: "Bun + Hono",
    },
  ];

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)]">
      {/* Hero Section */}
      <section className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-20 text-center relative overflow-hidden">
        {/* Glow backdrop circles */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-indigo-500/10 rounded-full blur-[120px] pointer-events-none -z-10" />

        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs font-semibold mb-6 shadow-sm shadow-indigo-500/10 animate-fade-in">
          <Sparkles className="w-4 h-4 text-indigo-400" />
          <span>Next-Gen Autonomous Code Intelligence & Review Platform</span>
        </div>

        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white max-w-4xl mx-auto leading-[1.15]">
          Architectural Code Graph &{" "}
          <span className="bg-gradient-to-r from-indigo-400 via-cyan-400 to-indigo-300 bg-clip-text text-transparent">
            Agentic RAG
          </span>
        </h1>

        <p className="mt-6 text-base sm:text-lg text-slate-300 max-w-2xl mx-auto leading-relaxed">
          Stop relying on naive regex linters and hallucinating LLM diff reviewers.
          Sentinel combines <strong>Neo4j AST code graphs</strong> with <strong>ChromaDB vector embeddings</strong> to answer complex cross-file dependency and ripple impact questions.
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

        {/* Live Architecture Flow Preview Card */}
        <div className="mt-16 max-w-5xl mx-auto glass-panel rounded-3xl p-6 sm:p-8 border border-slate-800 shadow-2xl relative">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-4 mb-6">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-rose-500/80 inline-block" />
              <span className="w-3 h-3 rounded-full bg-amber-500/80 inline-block" />
              <span className="w-3 h-3 rounded-full bg-emerald-500/80 inline-block" />
              <span className="text-xs font-mono text-slate-400 ml-2">
                sentinel-dual-knowledge-base-landscape.yaml
              </span>
            </div>
            <Badge variant="primary" size="sm" className="font-mono">
              FastMCP v3.4 Engine
            </Badge>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-left font-mono text-xs">
            <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-2">
              <div className="flex items-center gap-2 text-indigo-400 font-bold">
                <Share2 className="w-4 h-4" />
                <span>1. AST Graph (Neo4j)</span>
              </div>
              <p className="text-slate-400 text-[11px] leading-relaxed font-sans">
                Tree-sitter extracts files, functions, classes, and calls. Multi-tenant isolated with Cypher indexes.
              </p>
              <div className="text-[10px] text-indigo-300/80 bg-indigo-950/40 p-2 rounded-lg border border-indigo-900/40 truncate">
                {"MATCH (s:Symbol)-[:CALLS*1..3]->(d) RETURN blast_radius"}
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-2">
              <div className="flex items-center gap-2 text-cyan-400 font-bold">
                <Database className="w-4 h-4" />
                <span>2. Vector KB (ChromaDB)</span>
              </div>
              <p className="text-slate-400 text-[11px] leading-relaxed font-sans">
                Semantic embeddings of signatures, docstrings, and bodies with Gemini models & staleness tracking.
              </p>
              <div className="text-[10px] text-cyan-300/80 bg-cyan-950/40 p-2 rounded-lg border border-cyan-900/40 truncate">
                {"collection.query(where={\"repo\": repo_id})"}
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-2">
              <div className="flex items-center gap-2 text-purple-400 font-bold">
                <Cpu className="w-4 h-4" />
                <span>3. Dual-LLM ReAct Loop</span>
              </div>
              <p className="text-slate-400 text-[11px] leading-relaxed font-sans">
                Gemini 2.0 Flash orchestrates tool actions; Groq Llama-3.3-70B audits code diffs at ~250 tokens/sec.
              </p>
              <div className="text-[10px] text-purple-300/80 bg-purple-950/40 p-2 rounded-lg border border-purple-900/40 truncate">
                {"SSE stream: thought -> tool_end -> cited answer"}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 border-t border-slate-800/80">
        <div className="text-center max-w-3xl mx-auto mb-14">
          <h2 className="text-2xl sm:text-4xl font-bold text-white tracking-tight">
            Complete Microservice Feature Suite
          </h2>
          <p className="mt-3 text-sm sm:text-base text-slate-400">
            Engineered for enterprise codebases requiring deep architectural guarantees and surgical PR patch synthesis.
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
                  <div className="p-3 rounded-2xl bg-slate-900 border border-slate-800">
                    {feature.icon}
                  </div>
                  <Badge variant="primary" size="sm" className="font-mono text-[10px]">
                    {feature.badge}
                  </Badge>
                </div>
                <h3 className="text-lg font-bold text-slate-100 mb-2">
                  {feature.title}
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {feature.description}
                </p>
              </div>
            </div>
          ))}
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
          <p className="font-mono text-[11px]">
            FastMCP • Tree-sitter • Neo4j • ChromaDB • Gemini 2.0 Flash • Groq
          </p>
        </div>
      </footer>
    </div>
  );
}
