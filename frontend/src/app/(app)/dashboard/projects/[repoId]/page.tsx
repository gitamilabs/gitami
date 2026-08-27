"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuthStore } from "../../../../../store/authStore";
import { useRepoStore } from "../../../../../store/repoStore";
import { IngestModal } from "../../../../../components/repositories/IngestModal";
import {
  ArrowLeft,
  GitBranch,
  Lock,
  Globe,
  Github,
  FolderGit2,
  CheckCircle2,
  Sparkles,
  GitPullRequest,
  Bot,
  ExternalLink,
  Trash2,
  RefreshCw,
} from "lucide-react";

function ProjectDetailContent() {
  const params = useParams<{ repoId: string }>();
  const router = useRouter();
  const repoKey = decodeURIComponent(params.repoId);

  const { token } = useAuthStore();
  const {
    connectedRepos,
    indexedRepos,
    indexedReposLoaded,
    fetchConnectedRepos,
    fetchIndexedRepos,
    disconnectRepo,
    isLoading,
  } = useRepoStore();

  const [isIngestModalOpen, setIsIngestModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (token) {
      fetchConnectedRepos(token);
      fetchIndexedRepos(token);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const connected = connectedRepos.find((r) => r.id === repoKey);
  const name = connected?.name || (repoKey.includes("/") ? repoKey.split("/")[1] : repoKey);
  const fullName = connected?.fullName || repoKey;
  const isIngested = indexedRepos.includes(name) || indexedRepos.includes(fullName);

  const notFound = !connected && !isIngested && connectedRepos.length + indexedRepos.length > 0 && !isLoading;

  const handleDisconnect = async () => {
    if (!connected || !token) return;
    if (!confirm(`Disconnect ${connected.fullName}? This removes GitHub App access to this repository.`)) return;
    setIsDeleting(true);
    const ok = await disconnectRepo(token, connected.id);
    setIsDeleting(false);
    if (ok) router.push("/dashboard");
  };

  return (
    <div className="flex-1 flex flex-col">
      <header className="h-14 border-b border-zinc-800/80 px-6 flex items-center gap-3 bg-[#0a0a0a]/50 backdrop-blur-md sticky top-0 z-20">
        <Link
          href="/dashboard"
          className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Projects</span>
        </Link>
        <span className="text-zinc-700">/</span>
        <h1 className="text-sm font-semibold text-white truncate">{name}</h1>
      </header>

      <div className="flex-1 p-6 md:p-8 max-w-4xl w-full mx-auto space-y-6">
        {notFound ? (
          <div className="text-center py-16 rounded-2xl bg-[#0a0a0a] border border-zinc-800/80 border-dashed space-y-3">
            <FolderGit2 className="w-10 h-10 text-zinc-600 mx-auto" />
            <h3 className="text-sm font-semibold text-white">Project not found</h3>
            <p className="text-xs text-zinc-500">
              &ldquo;{repoKey}&rdquo; isn&rsquo;t a connected or indexed project.
            </p>
            <Link
              href="/dashboard"
              className="inline-block text-xs font-semibold text-blue-400 hover:text-blue-300"
            >
              &larr; Back to Projects
            </Link>
          </div>
        ) : (
          <>
            {/* Overview card */}
            <div className="bg-[#0a0a0a] border border-zinc-800/80 rounded-xl p-6 space-y-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-10 h-10 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center shrink-0">
                    {connected ? (
                      <Github className="w-5 h-5 text-white" />
                    ) : (
                      <FolderGit2 className="w-5 h-5 text-blue-400" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-base font-bold text-white truncate">{fullName}</h2>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span className="flex items-center gap-1 text-[11px] text-zinc-400 bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800 font-mono">
                        <GitBranch className="w-3 h-3" />
                        {connected?.defaultBranch || "main"}
                      </span>
                      {connected && (
                        <span className="flex items-center gap-1 text-[11px] text-zinc-400 bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800">
                          {connected.isPrivate ? (
                            <>
                              <Lock className="w-3 h-3" /> Private
                            </>
                          ) : (
                            <>
                              <Globe className="w-3 h-3" /> Public
                            </>
                          )}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {!indexedReposLoaded ? (
                  <span className="flex items-center gap-1 text-[11px] text-zinc-400 bg-zinc-800/60 border border-zinc-700/60 px-2.5 py-1 rounded-full shrink-0">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Checking...</span>
                  </span>
                ) : isIngested ? (
                  <span className="flex items-center gap-1 text-[11px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full shrink-0">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Ready</span>
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-[11px] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 rounded-full shrink-0">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Not Indexed</span>
                  </span>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2 pt-4 border-t border-zinc-800/60">
                <button
                  onClick={() => setIsIngestModalOpen(true)}
                  disabled={!connected || !indexedReposLoaded}
                  title={connected ? undefined : "Re-ingest local directory projects from Add New Project"}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white text-black text-xs font-semibold hover:bg-zinc-200 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>{!indexedReposLoaded ? "Checking..." : isIngested ? "Re-index" : "Ingest Now"}</span>
                </button>

                {connected?.htmlUrl && (
                  <a
                    href={connected.htmlUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs font-medium text-zinc-300 hover:text-white hover:border-zinc-700 transition-colors"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>Open on GitHub</span>
                  </a>
                )}

                {connected && (
                  <button
                    onClick={handleDisconnect}
                    disabled={isDeleting}
                    className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/25 text-xs font-medium text-red-400 hover:bg-red-500/15 transition-colors cursor-pointer disabled:opacity-50"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>{isDeleting ? "Disconnecting..." : "Disconnect"}</span>
                  </button>
                )}
              </div>
            </div>

            {/* Quick links */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Link
                href={`/prs?repoFullName=${encodeURIComponent(fullName)}`}
                className="group bg-[#0a0a0a] hover:bg-[#0f0f0f] border border-zinc-800/80 hover:border-zinc-700 rounded-xl p-5 transition-all flex items-center gap-3.5"
              >
                <div className="p-2.5 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400 shrink-0">
                  <GitPullRequest className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white group-hover:text-blue-400 transition-colors">
                    PR Reviews
                  </h3>
                  <p className="text-xs text-zinc-500 mt-0.5">Agentic review & auto-fix for this repo&rsquo;s pull requests.</p>
                </div>
              </Link>

              <Link
                href={`/chat?repo=${encodeURIComponent(fullName)}`}
                className="group bg-[#0a0a0a] hover:bg-[#0f0f0f] border border-zinc-800/80 hover:border-zinc-700 rounded-xl p-5 transition-all flex items-center gap-3.5"
              >
                <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 shrink-0">
                  <Bot className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white group-hover:text-blue-400 transition-colors">
                    Codebase Chat
                  </h3>
                  <p className="text-xs text-zinc-500 mt-0.5">Ask the ReAct agent about this repo&rsquo;s knowledge base.</p>
                </div>
              </Link>
            </div>
          </>
        )}
      </div>

      {connected && (
        <IngestModal
          isOpen={isIngestModalOpen}
          repo={connected}
          onClose={() => setIsIngestModalOpen(false)}
          onSuccess={() => token && fetchIndexedRepos(token, true)}
        />
      )}
    </div>
  );
}

export default function ProjectDetailPage() {
  return <ProjectDetailContent />;
}
