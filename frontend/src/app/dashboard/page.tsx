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
        {/* Welcome Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass-panel rounded-3xl p-6 border border-slate-800">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="primary" size="sm" className="font-mono text-[10px]">
                Control Plane & Knowledge Base
              </Badge>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Welcome back, {user?.name || user?.username || "Developer"}
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              Here is your live codebase graph status and agentic intelligence overview.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <Link href="/ingest">
              <Button
                variant="secondary"
                size="sm"
                leftIcon={<Plus className="w-4 h-4 text-indigo-400" />}
              >
                Ingest New Repo
              </Button>
            </Link>
            <Link href="/chat">
              <Button
                variant="glow"
                size="sm"
                rightIcon={<ArrowRight className="w-4 h-4" />}
              >
                Open RAG Chat
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
          />
          <StatCard
            title="Vector KB Passages"
            value={vectorCount > 0 ? vectorCount : "2,450+"}
            subtitle="ChromaDB Embeddings"
            icon={<Database className="w-5 h-5" />}
            accentColor="cyan"
          />
          <StatCard
            title="Graph Repositories"
            value={graphRepos.length > 0 ? graphRepos.length : indexedRepos.length}
            subtitle="Neo4j AST Call Trees"
            icon={<Share2 className="w-5 h-5" />}
            accentColor="purple"
          />
          <StatCard
            title="Dual-LLM Engine"
            value="Active"
            subtitle="Gemini 2.0 + Groq Llama"
            icon={<Bot className="w-5 h-5" />}
            accentColor="emerald"
          />
        </div>

        {/* GitHub App Install Banner if no connected repos */}
        {connectedRepos.length === 0 && !isLoading && <InstallBanner />}

        {/* Connected Repositories Section */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-100">
                Connected Repositories
              </h2>
              <p className="text-xs text-slate-400">
                Repositories indexed for AST blast radius analysis and agentic chat.
              </p>
            </div>
            <Link
              href="/repositories"
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
            >
              View all &rarr;
            </Link>
          </div>

          {isLoading ? (
            <div className="p-8 text-center glass-card rounded-2xl border border-slate-800 text-xs text-slate-400 font-mono">
              Loading repositories...
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
            <div className="p-8 text-center glass-card rounded-2xl border border-slate-800">
              <FolderGit2 className="w-10 h-10 text-slate-600 mx-auto mb-2" />
              <p className="text-sm font-semibold text-slate-300">
                No GitHub Repositories Connected Yet
              </p>
              <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1">
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


        {/* Knowledge Base Fast Query Shortcuts */}
        <div className="glass-panel rounded-3xl p-6 border border-slate-800 space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-400" />
            <h3 className="text-sm font-bold text-slate-200">
              Available Knowledge Base Spaces
            </h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {indexedRepos.map((repoName) => (
              <Link
                key={repoName}
                href={`/chat?repo=${encodeURIComponent(repoName)}`}
                className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/90 hover:bg-indigo-950/60 border border-slate-800 hover:border-indigo-700/60 text-xs text-slate-200 font-mono transition-all"
              >
                <div className="w-2 h-2 rounded-full bg-cyan-400" />
                <span>{repoName}</span>
                <span className="text-[10px] text-indigo-400">&rarr;</span>
              </Link>
            ))}
          </div>
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
