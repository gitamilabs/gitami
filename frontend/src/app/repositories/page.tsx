"use client";

import React, { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { ProtectedRoute } from "../../components/auth/ProtectedRoute";
import { Sidebar } from "../../components/layout/Sidebar";
import { RepoCard } from "../../components/repositories/RepoCard";
import { InstallBanner } from "../../components/repositories/InstallBanner";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { useAuthStore } from "../../store/authStore";
import { useRepoStore } from "../../store/repoStore";
import { githubApi } from "../../lib/api";
import { IngestModal } from "../../components/repositories/IngestModal";
import { ConnectedRepository } from "../../lib/types";
import {
  FolderGit2,
  Search,
  RefreshCw,
  Plus,
  Github,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Sparkles,
} from "lucide-react";

function RepositoriesContent() {
  const searchParams = useSearchParams();
  const { token } = useAuthStore();
  const {
    connectedRepos,
    installations,
    indexedRepos,
    fetchConnectedRepos,
    fetchInstallations,
    fetchIndexedRepos,
    disconnectRepo,
    isLoading,
  } = useRepoStore();

  const [searchQuery, setSearchQuery] = useState("");
  const [syncStatus, setSyncStatus] = useState<string | null>(null);
  const [selectedRepoForIngest, setSelectedRepoForIngest] = useState<ConnectedRepository | null>(null);

  useEffect(() => {
    if (!token) return;

    fetchIndexedRepos();

    // Check if redirected from GitHub App installation callback
    const installationId = searchParams.get("installation_id");
    const setupAction = searchParams.get("setup_action");

    if (installationId) {
      setSyncStatus("Syncing newly installed GitHub repositories...");
      githubApi
        .handleInstallationCallback(token, installationId, setupAction || undefined)
        .then(() => {
          setSyncStatus("GitHub repositories synced successfully!");
          fetchConnectedRepos(token);
          fetchInstallations(token);
          fetchIndexedRepos();
          setTimeout(() => setSyncStatus(null), 4000);
        })
        .catch((err) => {
          setSyncStatus(`Sync error: ${err.message}`);
        });
    } else {
      fetchConnectedRepos(token);
      fetchInstallations(token);
    }
  }, [token, searchParams, fetchConnectedRepos, fetchInstallations, fetchIndexedRepos]);


  const handleDisconnect = async (repoId: string) => {
    if (token) {
      await disconnectRepo(token, repoId);
    }
  };

  const handleRefresh = () => {
    if (token) {
      fetchConnectedRepos(token);
      fetchInstallations(token);
    }
  };

  const filteredRepos = connectedRepos.filter(
    (repo) =>
      repo.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      repo.fullName.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 gap-6">
      <Sidebar />

      <div className="flex-1 space-y-6 min-w-0">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass-panel rounded-3xl p-6 border border-slate-800">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="primary" size="sm" className="font-mono text-[10px]">
                GitHub App Integrations
              </Badge>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Connected Repositories
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              Manage GitHub App installations and repositories with active AST analysis.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
              onClick={handleRefresh}
              isLoading={isLoading}
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Sync notification banner */}
        {syncStatus && (
          <div className="p-4 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 flex items-center gap-3 text-indigo-200 text-xs font-mono animate-fade-in">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{syncStatus}</span>
          </div>
        )}

        {/* GitHub Installations Overview */}
        {installations.length > 0 && (
          <div className="glass-panel rounded-2xl p-4 border border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2">
              <Github className="w-4 h-4 text-slate-300" />
              <span className="text-slate-300 font-medium">
                Active Installations:
              </span>
              {installations.map((inst) => (
                <Badge key={inst.id} variant="info" size="sm" className="font-mono">
                  {inst.accountLogin} ({inst.accountType})
                </Badge>
              ))}
            </div>
            <span className="text-slate-400 font-mono text-[11px]">
              {connectedRepos.length} Repositories Synchronized
            </span>
          </div>
        )}

        {/* GitHub App Install CTA */}
        <InstallBanner />

        {/* Search and Filters */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search connected repositories..."
              aria-label="Search connected repositories"
              className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        {/* Repositories Grid */}
        {isLoading ? (
          <div className="p-12 text-center glass-card rounded-2xl border border-slate-800 text-xs text-slate-400 font-mono">
            Loading repositories from database...
          </div>
        ) : filteredRepos.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredRepos.map((repo) => {
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
          <div className="p-12 text-center glass-card rounded-2xl border border-slate-800">
            <FolderGit2 className="w-12 h-12 text-slate-600 mx-auto mb-3" />
            <h3 className="text-base font-bold text-slate-200">
              {searchQuery ? "No matching repositories found" : "No Connected Repositories"}
            </h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1">
              {searchQuery
                ? "Try adjusting your search query."
                : "Install the Sentinel GitHub App to connect your repositories."}
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
    </div>
  );
}


export default function RepositoriesPage() {
  return (
    <ProtectedRoute>
      <Suspense fallback={<div className="p-8 text-center font-mono text-xs text-slate-400">Loading repositories...</div>}>
        <RepositoriesContent />
      </Suspense>
    </ProtectedRoute>
  );
}
