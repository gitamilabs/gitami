"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  FolderGit2,
  Plus,
  GitBranch,
  Lock,
  Globe,
  Play,
  Trash2,
  Loader2,
  ExternalLink,
  Pencil,
  CheckCircle2,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { useProjectStore } from "@/store/projectStore";
import { useRepoStore } from "@/store/repoStore";
import { useBuildStore } from "@/store/buildStore";
import { ConnectRepositoryModal } from "@/components/repositories/ConnectRepositoryModal";
import { EditRepositoryModal } from "@/components/repositories/EditRepositoryModal";
import { ConnectedRepository } from "@/lib/types";

function formatRelativeTime(dateString?: string): string {
  if (!dateString) return "Recently";
  const diff = Date.now() - new Date(dateString).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.floor(hours / 24);
  return `${days} d ago`;
}

export default function RepositoriesPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const teamSlug = (params?.teamSlug as string) || "";
  const projectSlug = (params?.projectSlug as string) || "";

  const { token } = useAuthStore();
  const { fetchConnectedRepos } = useRepoStore();
  const { projects, activeProject: storeActiveProject, fetchProjectDetails, detachRepository } = useProjectStore();
  const { startBuild } = useBuildStore();

  const [isConnectOpen, setIsConnectOpen] = useState(false);
  const [repoToEdit, setRepoToEdit] = useState<ConnectedRepository | null>(null);
  const [startingBuildId, setStartingBuildId] = useState<string | null>(null);
  const [detachingRepoId, setDetachingRepoId] = useState<string | null>(null);
  const [installedSuccessBanner, setInstalledSuccessBanner] = useState(false);

  useEffect(() => {
    if (token && projectSlug) {
      fetchProjectDetails(token, projectSlug);
    }
  }, [token, projectSlug, fetchProjectDetails]);

  // Handle GitHub App redirect return (?installed=true)
  useEffect(() => {
    const installed = searchParams.get("installed");
    if (installed === "true" && token) {
      setInstalledSuccessBanner(true);
      fetchConnectedRepos(token, true);
      setIsConnectOpen(true);
      router.replace(`/${teamSlug}/${projectSlug}/repositories`);
    }
  }, [searchParams, token, teamSlug, projectSlug, fetchConnectedRepos, router]);

  const activeProject =
    (storeActiveProject?.slug === projectSlug || storeActiveProject?.id === projectSlug)
      ? storeActiveProject
      : projects.find((p) => p.slug === projectSlug || p.id === projectSlug) || null;

  const repos = activeProject?.repositories || [];

  const handleStartBuild = async (repoId: string, branch: string) => {
    if (!token || !activeProject) return;
    setStartingBuildId(repoId);
    try {
      await startBuild(token, activeProject.id, repoId, branch);
      await fetchProjectDetails(token, projectSlug);
    } catch (err) {
      console.error("Failed to start build:", err);
    } finally {
      setStartingBuildId(null);
    }
  };

  const handleDetach = async (repoId: string) => {
    if (!token || !activeProject) return;
    setDetachingRepoId(repoId);
    try {
      await detachRepository(token, activeProject.id, repoId);
    } catch (err) {
      console.error("Failed to detach repository:", err);
    } finally {
      setDetachingRepoId(null);
    }
  };

  return (
    <div className="p-8 max-w-5xl w-full mx-auto space-y-8 animate-fade-in text-zinc-200">
      {installedSuccessBanner && (
        <div className="flex items-center justify-between p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs animate-fade-in">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>GitHub App connected successfully! Select a repository below to link it to this project.</span>
          </div>
          <button
            onClick={() => setInstalledSuccessBanner(false)}
            className="text-emerald-400/60 hover:text-emerald-300 text-xs font-mono cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-white/[0.06]">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight font-mono">
            Connected Repositories
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Repositories in this project scope for AST indexing, blast radius checks, and PR reviews.
          </p>
        </div>

        {repos.length > 0 && (
          <button
            onClick={() => setIsConnectOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-zinc-200 text-black rounded-md text-xs font-semibold transition-colors cursor-pointer shrink-0"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Connect Repository</span>
          </button>
        )}
      </div>

      {repos.length === 0 ? (
        <div className="py-16 text-center space-y-4 max-w-md mx-auto">
          <div className="w-12 h-12 rounded-xl bg-[#11131a] border border-white/[0.06] flex items-center justify-center mx-auto text-zinc-400">
            <FolderGit2 className="w-6 h-6 text-zinc-300" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">No repositories connected</h3>
            <p className="text-xs text-zinc-400 mt-1">
              Connect a GitHub repository or import a local codebase to begin indexing.
            </p>
          </div>
          <button
            onClick={() => setIsConnectOpen(true)}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold transition-colors cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Connect Repository</span>
          </button>
        </div>
      ) : (
        <div className="border-t border-b border-white/[0.06] divide-y divide-white/[0.06]">
          {repos.map((repo) => {
            const isStarting = startingBuildId === repo.id;
            const isDetaching = detachingRepoId === repo.id;
            return (
              <div
                key={repo.id}
                className="py-4 flex items-center justify-between hover:bg-white/[0.02] transition-colors"
              >
                <div className="flex items-center gap-3.5 min-w-0 pr-4">
                  <div className="w-8 h-8 rounded-md bg-white/[0.04] border border-white/[0.06] flex items-center justify-center text-zinc-400 shrink-0">
                    {repo.isPrivate ? (
                      <Lock className="w-3.5 h-3.5 text-zinc-500" />
                    ) : (
                      <Globe className="w-3.5 h-3.5 text-zinc-500" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-white font-mono truncate">
                      {repo.fullName}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-zinc-500 font-mono mt-0.5">
                      <span className="flex items-center gap-1">
                        <GitBranch className="w-3 h-3 text-zinc-600" />
                        {repo.defaultBranch || "main"}
                      </span>
                      {repo.htmlUrl && (
                        <>
                          <span>•</span>
                          <a
                            href={repo.htmlUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="hover:text-zinc-300 transition-colors flex items-center gap-1"
                          >
                            <span>GitHub</span>
                            <ExternalLink className="w-2.5 h-2.5" />
                          </a>
                        </>
                      )}
                      <span>•</span>
                      <span>Synced {formatRelativeTime(repo.updatedAt)}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2.5 shrink-0">
                  <button
                    onClick={() => handleStartBuild(repo.id, repo.defaultBranch || "main")}
                    disabled={isStarting}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-200 hover:text-white text-xs font-mono font-medium transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    {isStarting ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Starting...</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-3 h-3 text-emerald-400" />
                        <span>Build</span>
                      </>
                    )}
                  </button>

                  <button
                    onClick={() => setRepoToEdit(repo)}
                    className="p-1.5 text-zinc-400 hover:text-white hover:bg-white/[0.05] rounded-md transition-colors cursor-pointer"
                    title="Edit Repository Settings"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>

                  <button
                    onClick={() => handleDetach(repo.id)}
                    disabled={isDetaching}
                    className="p-1.5 text-zinc-500 hover:text-rose-400 hover:bg-white/[0.05] rounded-md transition-colors cursor-pointer"
                    title="Detach Repository"
                  >
                    {isDetaching ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {activeProject && (
        <ConnectRepositoryModal
          isOpen={isConnectOpen}
          onClose={() => setIsConnectOpen(false)}
          teamSlug={teamSlug}
          projectSlug={projectSlug}
          projectId={activeProject.id}
          onSuccess={() => {
            if (token) fetchProjectDetails(token, projectSlug);
          }}
        />
      )}

      {repoToEdit && (
        <EditRepositoryModal
          isOpen={!!repoToEdit}
          onClose={() => setRepoToEdit(null)}
          repository={repoToEdit}
          onSuccess={() => {
            if (token) fetchProjectDetails(token, projectSlug);
          }}
        />
      )}
    </div>
  );
}
