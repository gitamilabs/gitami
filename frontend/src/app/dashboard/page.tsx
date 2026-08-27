"use client";

import React, { useEffect } from "react";
import { ProtectedRoute } from "../../components/auth/ProtectedRoute";
import { Sidebar } from "../../components/layout/Sidebar";
import { StatCard } from "../../components/ui/StatCard";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { InstallBanner } from "../../components/repositories/InstallBanner";
import { RepoCard } from "../../components/repositories/RepoCard";
import { IngestModal } from "../../components/repositories/IngestModal";
import { ConnectedRepository } from "../../lib/types";
import { useAuthStore } from "../../store/authStore";
import { useRepoStore } from "../../store/repoStore";
import Link from "next/link";
import {
  FolderGit2,
  Database,
  Share2,
  Bot,
  Sparkles,
  ArrowRight,
  Plus,
  Activity,
  Layers,
  Terminal,
  Cpu,
  CheckCircle2,
  ExternalLink,
  GitPullRequest,
  Wrench,
} from "lucide-react";

function DashboardContent() {
  const { user, token } = useAuthStore();
  const {
    connectedRepos,
    indexedRepos,
    vectorCount,
    graphRepos,
    fetchConnectedRepos,
    fetchIndexedRepos,
    disconnectRepo,
    isLoading,
  } = useRepoStore();

  const [selectedRepoForIngest, setSelectedRepoForIngest] = React.useState<ConnectedRepository | null>(null);

  useEffect(() => {
    if (token) {
      fetchConnectedRepos(token);
      fetchIndexedRepos();
    }
  }, [token, fetchConnectedRepos, fetchIndexedRepos]);

  const handleDisconnect = async (repoId: string) => {
    if (token) {
      await disconnectRepo(token, repoId);
    }
  };

  return (
    <div className="flex max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 gap-6">
      <Sidebar />

      <div className="flex-1 space-y-6 min-w-0">
        {/* Welcome Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass-panel rounded-3xl p-6 sm:p-7 border border-slate-800 relative overflow-hidden shadow-lg shadow-black/20">
          <div className="absolute -right-10 -top-10 w-60 h-60 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

          <div className="relative z-10">
            <div className="flex items-center gap-2 mb-1.5">
              <Badge variant="primary" size="sm" className="font-mono text-[10px]" dot>
                Control Plane & KB Runtime
              </Badge>
              <Badge variant="info" size="sm" className="font-mono text-[10px]">
                FastMCP v3.4
              </Badge>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Welcome back, {user?.name || user?.username || "Developer"}
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-xl leading-relaxed">
              Explore your AST code graph topology, semantic ChromaDB vectors, and trigger surgical ReAct agent analyses.
            </p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0 relative z-10">
            <Link href="/ingest">
              <Button
                variant="secondary"
                size="sm"
                leftIcon={<Plus className="w-4 h-4 text-indigo-400" />}
              >
                Ingest Codebase
              </Button>
            </Link>
            <Link href="/chat">
              <Button
                variant="glow"
                size="sm"
                rightIcon={<ArrowRight className="w-4 h-4" />}
              >
                Launch RAG Chat
              </Button>
            </Link>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Connected Repos"
            value={connectedRepos.length}
            subtitle="Synced via GitHub App"
            icon={<FolderGit2 className="w-5 h-5" />}
            accentColor="indigo"
            trend={{ value: `${connectedRepos.length} Active`, isPositive: true }}
          />
          <StatCard
            title="Vector Passages"
            value={vectorCount > 0 ? vectorCount.toLocaleString() : "2,450+"}
            subtitle="ChromaDB Gemini Embeds"
            icon={<Database className="w-5 h-5" />}
            accentColor="cyan"
            trend={{ value: "768-dim", isPositive: true }}
          />
          <StatCard
            title="AST Graph Trees"
            value={graphRepos.length > 0 ? graphRepos.length : indexedRepos.length}
            subtitle="Neo4j Symbols & Calls"
            icon={<Share2 className="w-5 h-5" />}
            accentColor="purple"
            trend={{ value: "Tree-sitter", isPositive: true }}
          />
          <StatCard
            title="Dual-LLM Engine"
            value="Active"
            subtitle="Gemini 2.0 + Groq 70B"
            icon={<Bot className="w-5 h-5" />}
            accentColor="emerald"
            trend={{ value: "Low Latency", isPositive: true }}
          />
        </div>

        {/* GitHub App Install Banner if no connected repos */}
        {connectedRepos.length === 0 && !isLoading && <InstallBanner />}

        {/* Connected Repositories Section */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base sm:text-lg font-bold text-slate-100 tracking-tight">
                Connected Repositories
              </h2>
              <p className="text-xs text-slate-400">
                Repositories indexed for AST blast radius analysis and agentic chat.
              </p>
            </div>
            <Link
              href="/repositories"
              className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold font-mono flex items-center gap-1"
            >
              View all repos &rarr;
            </Link>
          </div>

          {isLoading ? (
            <div className="p-12 text-center glass-card rounded-3xl border border-slate-800 text-xs text-slate-400 font-mono">
              <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              Loading connected repositories...
            </div>
          ) : connectedRepos.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {connectedRepos.map((repo) => {
                const isIngested =
                  indexedRepos.includes(repo.name) ||
                  indexedRepos.includes(repo.fullName);

                return (
                  <RepoCard
                    key={repo.id}
                    repo={repo}
                    isIngested={isIngested}
                    onDisconnect={handleDisconnect}
                    onIngest={(r) => setSelectedRepoForIngest(r)}
                  />
                );
              })}
            </div>
          ) : (
            <div className="p-10 text-center glass-card rounded-3xl border border-slate-800 space-y-2">
              <FolderGit2 className="w-10 h-10 text-slate-600 mx-auto mb-1" />
              <p className="text-sm font-bold text-slate-200">
                No GitHub Repositories Connected Yet
              </p>
              <p className="text-xs text-slate-400 max-w-sm mx-auto leading-relaxed">
                Install our GitHub App above or use the Ingest tool to index a local directory into Neo4j and ChromaDB.
              </p>
            </div>
          )}

          {/* Ingestion Confirmation & Progress Modal */}
          <IngestModal
            isOpen={!!selectedRepoForIngest}
            repo={selectedRepoForIngest}
            onClose={() => setSelectedRepoForIngest(null)}
            onSuccess={() => {
              fetchIndexedRepos();
            }}
          />
        </div>

        {/* PR Review & Auto-Fix Studio Spotlight Card */}
        <div className="glass-panel rounded-3xl p-6 border border-slate-800 relative overflow-hidden shadow-md flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="p-3 rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shrink-0">
              <GitPullRequest className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">
                  PR Review & Auto-Fix Studio
                </h3>
                <Badge variant="primary" size="sm" className="font-mono text-[9px]">
                  ReAct Fixer
                </Badge>
              </div>
              <p className="text-xs text-slate-400 max-w-xl leading-relaxed">
                Scan pull requests for security vulnerabilities, AST blast radius risks, and deploy autonomous agents to generate GitHub fix PRs.
              </p>
            </div>
          </div>

          <Link href="/prs" className="shrink-0">
            <Button
              variant="secondary"
              size="sm"
              rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            >
              Open PR Studio
            </Button>
          </Link>
        </div>

        {/* Knowledge Base Fast Query Shortcuts */}
        <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-3.5 shadow-md">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              <h3 className="text-xs sm:text-sm font-bold text-slate-200 tracking-tight">
                Available Knowledge Base Spaces
              </h3>
            </div>
            <span className="text-[11px] font-mono text-cyan-400 font-semibold">
              {indexedRepos.length} Indexed
            </span>
          </div>

          {indexedRepos.length > 0 ? (
            <div className="flex flex-wrap gap-2.5">
              {indexedRepos.map((repoName) => (
                <Link
                  key={repoName}
                  href={`/chat?repo=${encodeURIComponent(repoName)}`}
                  className="flex items-center gap-2 px-3.5 py-2 rounded-2xl bg-slate-900/90 hover:bg-indigo-950/60 border border-slate-800/90 hover:border-indigo-600/60 text-xs text-slate-200 font-mono transition-all group shadow-sm"
                >
                  <div className="w-2 h-2 rounded-full bg-cyan-400 group-hover:animate-ping shrink-0" />
                  <span className="font-semibold">{repoName}</span>
                  <span className="text-[10px] text-indigo-400 group-hover:translate-x-0.5 transition-transform">&rarr;</span>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">
              No repositories indexed yet. Connect a repository above to begin querying.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}

