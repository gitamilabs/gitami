"use client";
import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "../store/authStore";
import { useTeamStore } from "../store/teamStore";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Navbar } from "../components/layout/Navbar";
import { GitamiLogo } from "../components/layout/GitamiLogo";
import {
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
  Check,
  X as CloseIcon,
  Search,
  Lock,
} from "lucide-react";

export default function LandingPage() {
  const router = useRouter();
  const { token, login, isInitialized, initialize } = useAuthStore();
  const { activeTeam, fetchTeams } = useTeamStore();
  const [activeArchTab, setActiveArchTab] = useState<"graph" | "context" | "vector" | "agent">("graph");

  useEffect(() => {
    if (!isInitialized) {
      initialize();
    }
  }, [isInitialized, initialize]);

  useEffect(() => {
    if (isInitialized && token) {
      if (activeTeam) {
        router.replace(`/${activeTeam.slug}`);
      } else {
        fetchTeams(token)
          .then((teams) => {
            if (teams && teams.length > 0) {
              router.replace(`/${teams[0].slug}`);
            } else {
              router.replace("/aryanracha");
            }
          })
          .catch(() => {
            router.replace("/aryanracha");
          });
      }
    }
  }, [token, isInitialized, activeTeam, router, fetchTeams]);

  const hasSavedToken =
    typeof window !== "undefined" &&
    !!(localStorage.getItem("gitami_token") || localStorage.getItem("sentinel_token"));

  if (token || (hasSavedToken && !isInitialized)) {
    return (
      <div className="min-h-screen bg-[#0c0d12] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-mono text-zinc-400">Entering GitAmi Workspace...</span>
        </div>
      </div>
    );
  }

  const features = [
    {
      title: "AST-Level Static Code Graphs",
      description:
        "Parsed via Tree-sitter into multi-tenant Neo4j software graphs capturing functions, classes, CALLS, IMPORTS, EXTENDS, and cross-file dependencies.",
      icon: <Share2 className="w-5 h-5 text-indigo-400" />,
      badge: "Neo4j V1 Graph",
      accent: "indigo",
    },
    {
      title: "Governed Context Engine",
      description:
        "Authorization security boundary, graph neighborhood expansion, provenance validation, and deterministic multi-factor ranking.",
      icon: <Layers className="w-5 h-5 text-cyan-400" />,
      badge: "Context Engine V1",
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
        "Pluggable vector embeddings with staleness management, chunk deduplication, and strict repository boundary post-filtering.",
      icon: <Database className="w-5 h-5 text-emerald-400" />,
      badge: "Vector Memory",
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
      badge: "Control Plane",
      accent: "purple",
    },
  ];

  const stats = [
    { value: "< 250ms", label: "AST Graph Traversal", subtitle: "Deterministic Cypher queries" },
    { value: "0 Disk Writes", label: "In-Memory Tarball Stream", subtitle: "GitHub API tarball streaming" },
    { value: "100% Strict", label: "Graph Equivalence", subtitle: "Full vs Incremental Indexing" },
    { value: "Governed", label: "Context Engine", subtitle: "Multi-factor ranked evidence" },
  ];

  return (
    <div className="flex flex-col min-h-screen bg-[#0c0d12] text-zinc-100">
      {/* Public Navbar explicitly mounted on marketing page */}
      <Navbar />

      {/* Hero Section */}
      <section className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-20 text-center relative overflow-hidden">
        {/* Subtle backdrop glow */}
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[380px] bg-indigo-500/[0.06] rounded-full blur-[140px] pointer-events-none -z-10" />

        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs font-semibold mb-8 shadow-sm shadow-indigo-500/10">
          <Sparkles className="w-4 h-4 text-indigo-400" />
          <span>V1 Incremental Software Graph & Context Engine Active</span>
        </div>

        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold text-white tracking-tight leading-tight max-w-4xl mx-auto">
          Autonomous Software Intelligence for{" "}
          <span className="bg-gradient-to-r from-indigo-400 via-indigo-300 to-violet-400 bg-clip-text text-transparent">
            Modern Engineering
          </span>
        </h1>

        <p className="mt-6 text-sm sm:text-base lg:text-lg text-zinc-400 max-w-2xl mx-auto leading-relaxed">
          GitAmi combines <strong>Tree-sitter AST software graphs</strong> in Neo4j with a <strong>governed Context Engine</strong> and vector memory to give developers authoritative, permission-aware codebase intelligence.
        </p>

        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
          {token ? (
            <Link href={activeTeam ? `/${activeTeam.slug}` : "/aryanracha"}>
              <Button size="lg" variant="primary" rightIcon={<ArrowRight className="w-4 h-4" />}>
                Open GitAmi Workspace
              </Button>
            </Link>
          ) : (
            <Button
              size="lg"
              variant="primary"
              leftIcon={<Github className="w-5 h-5" />}
              onClick={() => login()}
            >
              Sign in with GitHub
            </Button>
          )}

          <Link href={activeTeam ? `/${activeTeam.slug}` : "/aryanracha"}>
            <Button size="lg" variant="secondary" rightIcon={<ArrowRight className="w-4 h-4" />}>
              Explore Workspace
            </Button>
          </Link>
        </div>

        {/* Stats Grid */}
        <div id="stats" className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto mt-16 text-left">
          {stats.map((s, idx) => (
            <div
              key={idx}
              className="p-4 rounded-xl bg-[#11131a] border border-white/[0.06] hover:border-white/[0.12] transition-colors"
            >
              <div className="text-xl sm:text-2xl font-mono font-bold text-white">{s.value}</div>
              <div className="text-xs font-semibold text-zinc-300 mt-1">{s.label}</div>
              <div className="text-[11px] text-zinc-500 mt-0.5">{s.subtitle}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Architecture Showcase */}
      <section id="features" className="w-full max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center max-w-2xl mx-auto mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs font-semibold mb-3">
            <Layers className="w-3.5 h-3.5" />
            <span>Multi-Tier Architecture</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            How GitAmi Reasons Over Code
          </h2>
          <p className="mt-2 text-xs sm:text-sm text-zinc-400">
            A governed pipeline from raw Git commits to structured, permission-aware evidence.
          </p>
        </div>

        <div className="flex items-center justify-center gap-2 mb-6 border-b border-white/[0.06] pb-2">
          {(["graph", "context", "vector", "agent"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveArchTab(tab)}
              className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all capitalize ${
                activeArchTab === tab
                  ? "bg-white/[0.08] text-white shadow-xs"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {tab === "graph" && "1. Neo4j Graph"}
              {tab === "context" && "2. Context Engine"}
              {tab === "vector" && "3. Vector Memory"}
              {tab === "agent" && "4. Agents & Chat"}
            </button>
          ))}
        </div>

        <div className="p-6 rounded-2xl bg-[#11131a] border border-white/[0.06] text-xs font-mono">
          {activeArchTab === "graph" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-indigo-300">
                <span className="font-bold">Neo4j V1 Software Graph Ontology</span>
                <Badge variant="primary" size="sm">Deterministic UIDs</Badge>
              </div>
              <p className="text-zinc-300 font-sans leading-relaxed">
                AST-extracted declarations, lexical scopes, and structural relationships mapped to Cypher:
              </p>
              <div className="p-4 rounded-xl bg-[#0c0d12] border border-white/[0.06] text-indigo-300 space-y-1">
                <p className="text-zinc-500">// Bounded Neighborhood Traversal</p>
                <p className="text-white">MATCH (caller)-[:CALLS]-&gt;(callee)</p>
                <p className="text-white">WHERE callee.name = $symbol_name AND callee.repo_id IN $allowed_repos</p>
                <p className="text-white">RETURN caller.name, type(r), callee.name</p>
              </div>
            </div>
          )}

          {activeArchTab === "context" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-cyan-300">
                <span className="font-bold">Context Engine Governed Retrieval</span>
                <Badge variant="info" size="sm">Zero Direct DB Access</Badge>
              </div>
              <p className="text-zinc-300 font-sans leading-relaxed">
                Pre-retrieval authorization, multi-provider parallel fetching, provider-aware deduplication, and budget constraints:
              </p>
              <div className="p-4 rounded-xl bg-[#0c0d12] border border-white/[0.06] text-cyan-300 space-y-1">
                <p className="text-zinc-500">// ContextRequest &amp; AuthorizedScope</p>
                <p className="text-white">context = await context_engine.retrieve(ContextRequest(</p>
                <p className="text-cyan-400">    project_id=&quot;org_proj&quot;, query=&quot;Who calls authenticate?&quot;</p>
                <p className="text-white">))</p>
              </div>
            </div>
          )}

          {activeArchTab === "vector" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-emerald-300">
                <span className="font-bold">Pluggable Semantic Vector KB</span>
                <Badge variant="success" size="sm">Repo Boundary Filtered</Badge>
              </div>
              <p className="text-zinc-300 font-sans leading-relaxed">
                Embeds functions, classes, PR discussions, and commit messages with strict post-filtering to guarantee project isolation:
              </p>
              <div className="p-4 rounded-xl bg-[#0c0d12] border border-white/[0.06] text-emerald-300 space-y-1">
                <p className="text-zinc-500">// VectorKB Query with Boundary Check</p>
                <p className="text-white">{'res = vector_client.query(query_texts=[q], where={"repo": repo_id})'}</p>
                <p className="text-emerald-400">assert all(doc.repo in scope.allowed_repo_ids for doc in res)</p>
              </div>
            </div>
          )}

          {activeArchTab === "agent" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-amber-300">
                <span className="font-bold">Autonomous Agents &amp; Codebase Chat</span>
                <Badge variant="warning" size="sm">Evidence Powered</Badge>
              </div>
              <p className="text-zinc-300 font-sans leading-relaxed">
                Agents consume structured evidence from the Context Engine with full provenance citations and exact line numbers:
              </p>
              <div className="p-4 rounded-xl bg-[#0c0d12] border border-white/[0.06] text-amber-300 space-y-1">
                <p className="text-zinc-500">// Agent Response with Citations</p>
                <p className="text-white">answer = model.generate(prompt=build_prompt(context.items))</p>
                <p className="text-amber-400">citations = [item.source for item in context.items]</p>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Feature Grid */}
      <section className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 border-t border-white/[0.06]">
        <div className="text-center max-w-3xl mx-auto mb-12">
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Engineered for Production Repositories
          </h2>
          <p className="mt-2 text-xs sm:text-sm text-zinc-400">
            Deterministic graph algorithms and governed retrieval provide ground-truth certainty.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, i) => (
            <div
              key={i}
              className="p-6 rounded-xl bg-[#11131a] border border-white/[0.06] hover:border-white/[0.12] transition-colors flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="p-2.5 rounded-lg bg-white/[0.04] border border-white/[0.06]">
                    {feature.icon}
                  </div>
                  <Badge variant="primary" size="sm" className="font-mono text-[10px]">
                    {feature.badge}
                  </Badge>
                </div>
                <h3 className="text-base font-bold text-white mb-2 tracking-tight">
                  {feature.title}
                </h3>
                <p className="text-xs text-zinc-400 leading-relaxed font-sans">
                  {feature.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Comparison Section */}
      <section className="w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-16 border-t border-white/[0.06]">
        <div className="text-center mb-10">
          <h3 className="text-2xl font-bold text-white tracking-tight">
            Why GitAmi Graph &amp; Context Engine Beats Naive Reviewers
          </h3>
          <p className="text-xs text-zinc-400 mt-1">
            Deterministic graph topology vs blind LLM token completions.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
          <div className="p-5 rounded-xl bg-rose-500/5 border border-rose-500/20 space-y-3">
            <div className="flex items-center gap-2 text-rose-400 font-bold text-sm">
              <CloseIcon className="w-4 h-4" />
              <span>Naive LLM Diff Reviewers</span>
            </div>
            <ul className="space-y-2 text-zinc-400 font-sans text-xs">
              <li className="flex items-start gap-2">
                <span className="text-rose-400 font-bold">&#10007;</span>
                <span>Blind to cross-file call hierarchies and transitive callers.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-rose-400 font-bold">&#10007;</span>
                <span>Hallucinates function signatures not present in PR diff.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-rose-400 font-bold">&#10007;</span>
                <span>Cannot compute deterministic blast radius before merging.</span>
              </li>
            </ul>
          </div>

          <div className="p-5 rounded-xl bg-emerald-500/5 border border-emerald-500/30 space-y-3">
            <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
              <Check className="w-4 h-4" />
              <span>GitAmi Platform</span>
            </div>
            <ul className="space-y-2 text-zinc-300 font-sans text-xs">
              <li className="flex items-start gap-2">
                <span className="text-emerald-400 font-bold">&#10003;</span>
                <span>Tree-sitter AST mapped to Neo4j CALLS &amp; IMPORTS graph.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400 font-bold">&#10003;</span>
                <span>Governed Context Engine with strict multi-factor ranking.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-400 font-bold">&#10003;</span>
                <span>Deterministic blast risk calculation on every commit &amp; PR.</span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="w-full border-t border-white/[0.06] py-8 text-center text-xs text-zinc-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <GitamiLogo size="sm" />
          <p className="font-mono text-[11px] text-zinc-600">
            Tree-sitter • Neo4j • Context Engine • Vector Memory • FastMCP
          </p>
        </div>
      </footer>
    </div>
  );
}
