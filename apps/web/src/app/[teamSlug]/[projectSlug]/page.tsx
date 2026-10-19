"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  FolderGit2,
  ArrowRight,
  Plus,
  GitBranch,
  Play,
  Layers,
  ChevronRight,
  Pencil,
  Trash2,
  Settings,
} from "lucide-react";
import { useProjectStore } from "@/store/projectStore";
import { useBuildStore } from "@/store/buildStore";
import { useAuthStore } from "@/store/authStore";
import { ConnectRepositoryModal } from "@/components/repositories/ConnectRepositoryModal";
import { EditProjectModal } from "@/components/projects/EditProjectModal";
import { DeleteProjectModal } from "@/components/projects/DeleteProjectModal";
import { BuildStatusSummary } from "@/components/builds/BuildStatusSummary";

function formatRelativeTime(dateString?: string): string {
  if (!dateString) return "Recently";
  const diff = Date.now() - new Date(dateString).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function ProjectOverviewPage() {
  const params = useParams();
  const teamSlug = (params?.teamSlug as string) || "";
  const projectSlug = (params?.projectSlug as string) || "";

  const { token } = useAuthStore();
  const { projects, activeProject: storeActiveProject, fetchProjectDetails } = useProjectStore();
  const { startBuild, getActiveBuilds } = useBuildStore();

  const router = useRouter();
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  useEffect(() => {
    if (token && projectSlug) {
      fetchProjectDetails(token, projectSlug);
    }
  }, [token, projectSlug, fetchProjectDetails]);

  const activeProject =
    (storeActiveProject?.slug === projectSlug || storeActiveProject?.id === projectSlug)
      ? storeActiveProject
      : projects.find((p) => p.slug === projectSlug || p.id === projectSlug) || null;

  const repos = activeProject?.repositories || [];
  const activeBuilds = getActiveBuilds();
  const latestBuild = activeBuilds[0] || activeProject?.latestBuild;
  const hasRepositories = repos.length > 0;

  const projectBase = `/${teamSlug}/${projectSlug}`;

  // Onboarding screen if project has no repositories connected yet
  if (!hasRepositories) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 bg-[#0c0d12]">
        <div className="max-w-md w-full text-center space-y-5 py-12">
          <div className="w-12 h-12 rounded-lg bg-[#11131a] border border-white/[0.06] flex items-center justify-center mx-auto text-zinc-400">
            <FolderGit2 className="w-6 h-6 text-zinc-300" />
          </div>

          <div className="space-y-1.5">
            <h2 className="text-base font-semibold text-white tracking-tight">
              Connect a repository to get started
            </h2>
            <p className="text-xs text-zinc-500 leading-relaxed">
              Import a repository to start AST call graph analysis, software intelligence indexing, and automated PR reviews.
            </p>
          </div>

          <div className="flex items-center justify-center gap-3">
            <button
              onClick={() => setIsConnectModalOpen(true)}
              className="inline-flex items-center justify-center gap-2 py-2 px-4 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold transition-colors cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>Connect Repository</span>
            </button>
            {activeProject && (
              <button
                onClick={() => setIsDeleteModalOpen(true)}
                className="inline-flex items-center justify-center gap-1.5 py-2 px-3 rounded-md bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-rose-400 text-xs font-medium transition-colors cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Delete Project</span>
              </button>
            )}
          </div>

          {activeProject && (
            <>
              <ConnectRepositoryModal
                isOpen={isConnectModalOpen}
                onClose={() => setIsConnectModalOpen(false)}
                teamSlug={teamSlug}
                projectSlug={projectSlug}
                projectId={activeProject.id}
                onSuccess={() => {
                  if (token) fetchProjectDetails(token, projectSlug, true);
                }}
              />
              <DeleteProjectModal
                isOpen={isDeleteModalOpen}
                onClose={() => setIsDeleteModalOpen(false)}
                project={activeProject}
                onSuccess={() => {
                  router.push(`/${teamSlug}`);
                }}
              />
            </>
          )}
        </div>
      </div>
    );
  }

  // Flat, Vercel-like Project Overview
  return (
    <div className="p-8 max-w-5xl w-full mx-auto space-y-8 animate-fade-in text-zinc-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-white/[0.06]">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight font-mono">
            {activeProject?.name || projectSlug}
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            {activeProject?.description || "Project Workspace Overview"}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setIsConnectModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-zinc-200 text-black rounded-md text-xs font-semibold transition-colors cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Repository</span>
          </button>
          <button
            onClick={() => setIsEditModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-200 hover:text-white rounded-md text-xs font-medium transition-colors cursor-pointer"
            title="Edit Project Settings"
          >
            <Pencil className="w-3.5 h-3.5" />
            <span>Settings</span>
          </button>
          <button
            onClick={() => setIsDeleteModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-rose-400 hover:text-rose-300 rounded-md text-xs font-medium transition-colors cursor-pointer"
            title="Delete Project"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Delete</span>
          </button>
        </div>
      </div>

      {/* Prominent Live/Latest Build Summary Banner */}
      {latestBuild && (
        <section className="space-y-2">
          <div className="text-[10px] uppercase font-mono tracking-wider text-zinc-500 font-semibold">
            Build Intelligence
          </div>
          <BuildStatusSummary
            build={latestBuild}
            teamSlug={teamSlug}
            projectSlug={projectSlug}
          />
        </section>
      )}

      {/* Connected Repositories (List with subtle 1px dividers, no card-in-card) */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs uppercase font-mono tracking-wider text-zinc-400 font-semibold">
            Repositories ({repos.length})
          </h2>
          <Link
            href={`${projectBase}/repositories`}
            className="text-xs text-zinc-400 hover:text-white flex items-center gap-1 transition-colors"
          >
            <span>Manage</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        <div className="border-t border-b border-white/[0.06] divide-y divide-white/[0.06]">
          {repos.map((repo) => (
            <div
              key={repo.id}
              className="py-3.5 px-2 flex items-center justify-between hover:bg-white/[0.02] transition-colors rounded"
            >
              <div className="min-w-0 pr-4">
                <div className="font-mono text-sm text-zinc-100 font-medium truncate">
                  {repo.fullName}
                </div>
                <div className="text-xs text-zinc-500 font-mono mt-1 flex items-center gap-2">
                  <span className="flex items-center gap-1">
                    <GitBranch className="w-3 h-3 text-zinc-600" />
                    {repo.defaultBranch || "main"}
                  </span>
                  <span>•</span>
                  <span>Updated {formatRelativeTime(repo.updatedAt)}</span>
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <button
                  onClick={() => {
                    if (token && activeProject) {
                      startBuild(token, activeProject.id, repo.id, repo.defaultBranch || "main");
                    }
                  }}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-300 hover:text-white text-xs font-mono transition-colors cursor-pointer"
                  title="Run Build / Index"
                >
                  <Play className="w-3 h-3 text-emerald-400" />
                  <span>Build</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Overview Grid (Knowledge Graph & Build History Quick Links) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
        {/* Knowledge Graph Snapshot */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs uppercase font-mono tracking-wider text-zinc-400 font-semibold">
              Software Knowledge Graph
            </h2>
            <Link
              href={`${projectBase}/graph`}
              className="text-xs text-zinc-400 hover:text-white flex items-center gap-1 transition-colors"
            >
              <span>Explore Graph</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          <div className="p-4 rounded-lg bg-[#11131a] border border-white/[0.06] space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-200 font-mono font-medium">Neo4j Codebase Graph</span>
              <span className="text-emerald-400 font-mono text-[11px] flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                Active
              </span>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Interactive vis-network canvas with Leiden community clustering, caller/callee traversals, and blast radius analysis.
            </p>
            <div className="pt-1">
              <Link
                href={`${projectBase}/graph`}
                className="inline-flex items-center gap-1.5 text-xs text-zinc-300 hover:text-white font-medium group"
              >
                <span>Open Interactive Graph</span>
                <ChevronRight className="w-3.5 h-3.5 text-zinc-500 group-hover:text-white transition-colors" />
              </Link>
            </div>
          </div>
        </section>

        {/* Build History Overview */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs uppercase font-mono tracking-wider text-zinc-400 font-semibold">
              Build Deployments
            </h2>
            <Link
              href={`${projectBase}/builds`}
              className="text-xs text-zinc-400 hover:text-white flex items-center gap-1 transition-colors"
            >
              <span>History</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          <div className="p-4 rounded-lg bg-[#11131a] border border-white/[0.06] space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-200 font-mono font-medium">Autonomous Pipeline</span>
              <span className="text-zinc-500 font-mono text-[11px]">Tree-sitter + FastMCP</span>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Real-time pipeline tracking AST parsing, symbol extraction, Neo4j graph construction, and vector embeddings.
            </p>
            <div className="pt-1">
              <Link
                href={`${projectBase}/builds`}
                className="inline-flex items-center gap-1.5 text-xs text-zinc-300 hover:text-white font-medium group"
              >
                <span>View All Builds</span>
                <ChevronRight className="w-3.5 h-3.5 text-zinc-500 group-hover:text-white transition-colors" />
              </Link>
            </div>
          </div>
        </section>
      </div>

      {activeProject && (
        <>
          <ConnectRepositoryModal
            isOpen={isConnectModalOpen}
            onClose={() => setIsConnectModalOpen(false)}
            teamSlug={teamSlug}
            projectSlug={projectSlug}
            projectId={activeProject.id}
            onSuccess={() => {
              if (token) fetchProjectDetails(token, projectSlug, true);
            }}
          />
          <EditProjectModal
            isOpen={isEditModalOpen}
            onClose={() => setIsEditModalOpen(false)}
            project={activeProject}
            onSuccess={(updated) => {
              if (updated.slug && updated.slug !== projectSlug) {
                router.push(`/${teamSlug}/${updated.slug}`);
              } else if (token) {
                fetchProjectDetails(token, updated.slug || projectSlug, true);
              }
            }}
          />
          <DeleteProjectModal
            isOpen={isDeleteModalOpen}
            onClose={() => setIsDeleteModalOpen(false)}
            project={activeProject}
            onSuccess={() => {
              router.push(`/${teamSlug}`);
            }}
          />
        </>
      )}
    </div>
  );
}
