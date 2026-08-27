"use client";

import React, { useEffect, useMemo, useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useAuthStore } from "../../../store/authStore";
import { useRepoStore } from "../../../store/repoStore";
import { AddProjectModal } from "../../../components/repositories/AddProjectModal";
import { IngestModal } from "../../../components/repositories/IngestModal";
import { githubApi } from "../../../lib/api";
import { ConnectedRepository } from "../../../lib/types";
import {
  Search,
  Plus,
  FolderGit2,
  GitBranch,
  GitPullRequest,
  Bot,
  CheckCircle2,
  Sparkles,
  LayoutGrid,
  List,
  RefreshCw,
  Lock,
  Globe,
  Github,
  X,
} from "lucide-react";

interface ProjectRow {
  key: string;
  name: string;
  fullName: string;
  defaultBranch: string;
  isPrivate: boolean;
  htmlUrl?: string;
  source: "github" | "local";
  isIngested: boolean;
  // True until the indexed-repos check has resolved at least once — lets
  // the UI show a neutral "Checking..." state instead of flashing
  // "Not Indexed" while the AI service is still warming up its connections.
  checkingIndexStatus: boolean;
  connectedRepo: ConnectedRepository;
}

function ProjectsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { token } = useAuthStore();
  const {
    connectedRepos,
    indexedRepos,
    indexedReposLoaded,
    fetchConnectedRepos,
    fetchIndexedRepos,
    syncInstallations,
    isLoading,
  } = useRepoStore();

  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [ingestTarget, setIngestTarget] = useState<ConnectedRepository | null>(null);
  const [bannerDismissed, setBannerDismissed] = useState(false);

  // Mount-time load: reuses cached data if another page already fetched it
  // this session, instead of re-hitting the (slow, per-request) AI service
  // every time this page is visited.
  const loadIfNeeded = () => {
    if (!token) return;
    fetchConnectedRepos(token);
    fetchIndexedRepos(token);
  };

  // Explicit refresh: data is known to have changed (added/ingested a repo,
  // synced with GitHub), so always force a fresh fetch regardless of cache.
  const refresh = () => {
    if (!token) return;
    fetchConnectedRepos(token, true);
    fetchIndexedRepos(token, true);
  };

  useEffect(() => {
    loadIfNeeded();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // Handle the redirect GitHub sends back after installing/updating the App
  // (installation_id + setup_action query params) — sync immediately instead
  // of waiting on a webhook or a manual refresh.
  useEffect(() => {
    const installationId = searchParams.get("installation_id");
    const setupAction = searchParams.get("setup_action");
    if (!installationId || !token) return;

    githubApi
      .handleInstallationCallback(token, installationId, setupAction || undefined)
      .then(() => {
        fetchConnectedRepos(token, true);
        fetchIndexedRepos(token, true);
      })
      .catch((err) => console.warn("GitHub installation sync failed:", err))
      .finally(() => {
        router.replace("/dashboard");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, token]);

  const handleSyncWithGitHub = async () => {
    if (!token) return;
    await syncInstallations(token);
    await fetchIndexedRepos(token, true);
  };

  // Every project a user can see comes from their own connectedRepositories
  // row (GitHub-connected or a local ingestion, both owned by this user) —
  // never from the AI service's raw index directly, so no other user's data
  // can appear here.
  const projects: ProjectRow[] = useMemo(() => {
    return connectedRepos.map((r) => {
      const isIngested =
        indexedRepos.includes(r.name) ||
        indexedRepos.includes(r.fullName) ||
        indexedRepos.some((idx) => r.fullName.endsWith(`/${idx}`) || idx.endsWith(`/${r.name}`));

      return {
        key: r.id,
        name: r.name,
        fullName: r.fullName,
        defaultBranch: r.defaultBranch || "main",
        isPrivate: r.isPrivate,
        htmlUrl: r.htmlUrl,
        source: r.htmlUrl ? "github" : "local",
        isIngested,
        checkingIndexStatus: !indexedReposLoaded,
        connectedRepo: r,
      } as ProjectRow;
    });
  }, [connectedRepos, indexedRepos, indexedReposLoaded]);

  const filteredProjects = projects.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.fullName.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Only prompt to ingest once we've actually confirmed indexed status —
  // otherwise this would fire for every repo during the brief window right
  // after a restart while the AI service is still warming up.
  const notYetIngested = indexedReposLoaded
    ? projects.filter((p) => p.source === "github" && !p.isIngested)
    : [];

  return (
    <div className="flex-1 flex flex-col">
      {/* Top Header */}
      <header className="h-14 border-b border-zinc-800/80 px-6 flex items-center justify-between bg-[#0a0a0a]/50 backdrop-blur-md sticky top-0 z-20">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-semibold text-white">All Projects</h1>
          <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400 font-mono">
            {projects.length}
          </span>
        </div>

        <div className="flex items-center gap-2.5">
          <Link
            href="/chat"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs font-medium text-zinc-300 hover:text-white hover:border-zinc-700 transition-colors"
          >
            <Sparkles className="w-3.5 h-3.5 text-blue-400" />
            <span>Agent Chat</span>
          </Link>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white text-black text-xs font-semibold hover:bg-zinc-200 transition-colors cursor-pointer shadow-xs"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add New</span>
          </button>
        </div>
      </header>

      {/* Main Body */}
      <div className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto space-y-6">
        {/* New-repos-need-ingesting banner */}
        {!bannerDismissed && notYetIngested.length > 0 && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-blue-500/10 border border-blue-500/25 text-sm">
            <Sparkles className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-blue-100">
                {notYetIngested.length === 1
                  ? `"${notYetIngested[0]!.name}" is connected but not indexed yet.`
                  : `${notYetIngested.length} connected repos aren't indexed yet.`}
              </p>
              <div className="flex flex-wrap gap-2 mt-2">
                {notYetIngested.map((p) => (
                  <button
                    key={p.key}
                    onClick={() => setIngestTarget(p.connectedRepo)}
                    className="text-[11px] font-medium px-2.5 py-1 rounded-md bg-white text-black hover:bg-zinc-200 transition-colors cursor-pointer"
                  >
                    Ingest {p.name}
                  </button>
                ))}
              </div>
            </div>
            <button
              onClick={() => setBannerDismissed(true)}
              className="text-blue-300/70 hover:text-blue-200 shrink-0"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Controls Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              placeholder="Search Projects... [/]"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-[#0a0a0a] border border-zinc-800/80 rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600 transition-colors"
            />
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleSyncWithGitHub}
              className="p-2 rounded-lg bg-[#0a0a0a] border border-zinc-800/80 text-zinc-400 hover:text-white hover:border-zinc-700 transition-colors cursor-pointer"
              title="Sync live with GitHub"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            </button>
            <div className="flex items-center bg-[#0a0a0a] border border-zinc-800/80 rounded-lg p-0.5">
              <button
                onClick={() => setViewMode("grid")}
                className={`p-1.5 rounded-md transition-colors cursor-pointer ${
                  viewMode === "grid" ? "bg-zinc-800 text-white" : "text-zinc-500 hover:text-zinc-300"
                }`}
                title="Grid view"
              >
                <LayoutGrid className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setViewMode("list")}
                className={`p-1.5 rounded-md transition-colors cursor-pointer ${
                  viewMode === "list" ? "bg-zinc-800 text-white" : "text-zinc-500 hover:text-zinc-300"
                }`}
                title="List view"
              >
                <List className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        {/* Projects Grid / List */}
        {isLoading && projects.length === 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((n) => (
              <div
                key={n}
                className="h-44 rounded-xl bg-[#0a0a0a] border border-zinc-800/80 p-5 animate-pulse flex flex-col justify-between"
              >
                <div className="space-y-3">
                  <div className="w-24 h-4 bg-zinc-800 rounded" />
                  <div className="w-40 h-3 bg-zinc-800/60 rounded" />
                </div>
                <div className="w-32 h-3 bg-zinc-800/40 rounded" />
              </div>
            ))}
          </div>
        ) : filteredProjects.length === 0 ? (
          <div className="text-center py-16 px-4 rounded-2xl bg-[#0a0a0a] border border-zinc-800/80 border-dashed max-w-lg mx-auto space-y-4">
            <div className="w-12 h-12 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto text-zinc-400">
              <FolderGit2 className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-white">No projects found</h3>
              <p className="text-xs text-zinc-500 max-w-xs mx-auto">
                {searchQuery
                  ? `No projects match "${searchQuery}"`
                  : "Connect a GitHub repository or ingest a local directory to get started."}
              </p>
            </div>
            <button
              onClick={() => setIsAddModalOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-white text-black font-semibold text-xs rounded-lg hover:bg-zinc-200 transition-colors shadow-xs cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add New Project</span>
            </button>
          </div>
        ) : viewMode === "grid" ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredProjects.map((project) => (
              <ProjectCard key={project.key} project={project} />
            ))}
          </div>
        ) : (
          <div className="bg-[#0a0a0a] border border-zinc-800/80 rounded-xl overflow-hidden divide-y divide-zinc-800/80">
            {filteredProjects.map((project) => (
              <div
                key={project.key}
                className="p-4 hover:bg-[#0f0f0f] transition-colors flex items-center justify-between gap-4"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-300 shrink-0">
                    {project.source === "github" ? (
                      <Github className="w-4 h-4 text-white" />
                    ) : (
                      <FolderGit2 className="w-4 h-4 text-blue-400" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <Link
                      href={`/dashboard/projects/${encodeURIComponent(project.key)}`}
                      className="text-sm font-semibold text-white hover:text-blue-400 transition-colors truncate block"
                    >
                      {project.name}
                    </Link>
                    <span className="text-xs text-zinc-500 truncate block">{project.fullName}</span>
                  </div>
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  <span className="text-[11px] font-mono text-zinc-400 bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800">
                    {project.defaultBranch}
                  </span>
                  <Link
                    href={`/dashboard/projects/${encodeURIComponent(project.key)}`}
                    className="px-3 py-1.5 rounded-lg bg-zinc-800 text-xs font-medium text-white hover:bg-zinc-700 transition-colors"
                  >
                    Manage
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <AddProjectModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSuccess={refresh}
      />

      <IngestModal
        isOpen={!!ingestTarget}
        repo={ingestTarget}
        onClose={() => setIngestTarget(null)}
        onSuccess={() => {
          if (token) fetchIndexedRepos(token, true);
        }}
      />
    </div>
  );
}

function ProjectCard({ project }: { project: ProjectRow }) {
  return (
    <div className="group relative bg-[#0a0a0a] hover:bg-[#0f0f0f] border border-zinc-800/80 hover:border-zinc-700 rounded-xl p-5 transition-all duration-200 flex flex-col justify-between h-52 shadow-xs">
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-300 font-bold shrink-0 group-hover:border-zinc-700 transition-colors">
              {project.source === "github" ? (
                <Github className="w-4 h-4 text-white" />
              ) : (
                <FolderGit2 className="w-4 h-4 text-blue-400" />
              )}
            </div>
            <div className="min-w-0">
              <Link
                href={`/dashboard/projects/${encodeURIComponent(project.key)}`}
                className="text-sm font-bold text-white hover:text-blue-400 transition-colors truncate block"
              >
                {project.name}
              </Link>
              <span className="text-[11px] text-zinc-500 font-mono truncate block">
                {project.fullName}
              </span>
            </div>
          </div>
          {project.checkingIndexStatus ? (
            <span className="flex items-center gap-1 text-[11px] text-zinc-400 bg-zinc-800/60 border border-zinc-700/60 px-2 py-0.5 rounded-full shrink-0">
              <RefreshCw className="w-3 h-3 animate-spin" />
              <span>Checking...</span>
            </span>
          ) : project.isIngested ? (
            <span className="flex items-center gap-1 text-[11px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full shrink-0">
              <CheckCircle2 className="w-3 h-3" />
              <span>Ready</span>
            </span>
          ) : (
            <span className="flex items-center gap-1 text-[11px] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full shrink-0">
              <Sparkles className="w-3 h-3" />
              <span>Not Indexed</span>
            </span>
          )}
        </div>

        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <GitBranch className="w-3.5 h-3.5 text-zinc-500" />
            <span className="font-mono text-[11px] text-zinc-300 bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800">
              {project.defaultBranch}
            </span>
            {project.source === "github" ? (
              project.isPrivate ? (
                <span className="flex items-center gap-1 text-[10px] text-zinc-400 bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800">
                  <Lock className="w-2.5 h-2.5" />
                  Private
                </span>
              ) : (
                <span className="flex items-center gap-1 text-[10px] text-zinc-400 bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800">
                  <Globe className="w-2.5 h-2.5" />
                  Public
                </span>
              )
            ) : (
              <span className="text-[10px] text-zinc-400 bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800">
                Local
              </span>
            )}
          </div>
          <p className="text-xs text-zinc-500 truncate">
            {project.source === "github"
              ? "GitHub App connected & webhook active"
              : "Indexed code intelligence & agent graph"}
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-zinc-800/60 mt-auto">
        <div className="flex items-center gap-2">
          <Link
            href={`/prs?repoFullName=${encodeURIComponent(project.fullName)}`}
            className="flex items-center gap-1 text-xs text-zinc-400 hover:text-white px-2 py-1 rounded hover:bg-zinc-800/60 transition-colors"
          >
            <GitPullRequest className="w-3.5 h-3.5 text-purple-400" />
            <span>PR Reviews</span>
          </Link>
          <Link
            href={`/chat?repo=${encodeURIComponent(project.fullName)}`}
            className="flex items-center gap-1 text-xs text-zinc-400 hover:text-white px-2 py-1 rounded hover:bg-zinc-800/60 transition-colors"
          >
            <Bot className="w-3.5 h-3.5 text-emerald-400" />
            <span>Chat</span>
          </Link>
        </div>
        <Link
          href={`/dashboard/projects/${encodeURIComponent(project.key)}`}
          className="text-xs font-semibold text-zinc-300 hover:text-white transition-colors"
        >
          Open &rarr;
        </Link>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center font-mono text-xs text-zinc-500">Loading Projects...</div>}>
      <ProjectsContent />
    </Suspense>
  );
}
