"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  FolderGit2,
  Plus,
  Search,
  ArrowRight,
  Hammer,
  CheckCircle2,
  GitBranch,
  Pencil,
  Trash2,
  Settings,
  ChevronDown,
  Check,
  Users,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { useTeamStore } from "../../store/teamStore";
import { useProjectStore } from "../../store/projectStore";
import { ProtectedRoute } from "../../components/auth/ProtectedRoute";
import { CreateProjectModal } from "../../components/projects/CreateProjectModal";
import { CreateTeamModal } from "../../components/teams/CreateTeamModal";
import { EditProjectModal } from "../../components/projects/EditProjectModal";
import { DeleteProjectModal } from "../../components/projects/DeleteProjectModal";
import { GitamiLogo } from "../../components/layout/GitamiLogo";
import { Project } from "../../lib/types";

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

function TeamOverviewContent() {
  const params = useParams();
  const router = useRouter();
  const teamSlug = (params?.teamSlug as string) || "";

  const { token, user } = useAuthStore();
  const { teams, activeTeam, fetchTeams, setActiveTeam } = useTeamStore();
  const { projects, fetchTeamProjects } = useProjectStore();

  const [searchQuery, setSearchQuery] = useState("");
  const [isTeamMenuOpen, setIsTeamMenuOpen] = useState(false);
  const [isCreateProjectOpen, setIsCreateProjectOpen] = useState(false);
  const [isCreateTeamOpen, setIsCreateTeamOpen] = useState(false);
  const [projectToEdit, setProjectToEdit] = useState<Project | null>(null);
  const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);

  const teamMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (teamMenuRef.current && !teamMenuRef.current.contains(e.target as Node)) {
        setIsTeamMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (token && teams.length === 0) {
      fetchTeams(token);
    }
  }, [token, teams.length, fetchTeams]);

  useEffect(() => {
    if (token && teamSlug) {
      fetchTeamProjects(token, teamSlug);
    }
  }, [token, teamSlug, fetchTeamProjects]);

  const currentTeam = teams.find((t) => t.slug === teamSlug) || activeTeam;

  const filteredProjects = projects.filter((p) => {
    const q = searchQuery.toLowerCase().trim();
    return !q || p.name.toLowerCase().includes(q) || p.slug.toLowerCase().includes(q);
  });

  return (
    <div className="min-h-screen bg-[#0c0d12] text-zinc-200 flex flex-col">
      {/* Vercel-style Clean Top Header */}
      <header className="h-14 border-b border-white/[0.06] bg-[#0c0d12]/85 backdrop-blur-md px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <GitamiLogo href={`/${teamSlug}`} size="sm" />
          <span className="text-zinc-700 font-light">/</span>

          {/* Team Switcher Dropdown */}
          <div className="relative" ref={teamMenuRef}>
            <button
              onClick={() => setIsTeamMenuOpen(!isTeamMenuOpen)}
              className="flex items-center gap-2 px-2.5 py-1 rounded-md hover:bg-white/[0.05] border border-transparent hover:border-white/[0.08] text-white font-medium transition-colors cursor-pointer group"
              title="Toggle Team Workspace"
            >
              <div className="w-5 h-5 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center text-[10px] font-bold shrink-0">
                <Users className="w-3 h-3" />
              </div>
              <span className="text-xs font-semibold text-white truncate max-w-[150px]">
                {currentTeam?.name || teamSlug}
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-white/[0.04] text-zinc-400 border border-white/[0.06]">
                Team
              </span>
              <ChevronDown
                className={`w-3.5 h-3.5 text-zinc-500 group-hover:text-zinc-300 transition-transform ${
                  isTeamMenuOpen ? "rotate-180" : ""
                }`}
              />
            </button>

            {isTeamMenuOpen && (
              <div className="absolute left-0 top-full mt-1.5 w-60 bg-[#13151f] border border-white/[0.08] rounded-lg shadow-2xl py-1.5 z-50 animate-fade-in text-xs">
                <div className="px-3 py-1 text-[10px] font-mono uppercase text-zinc-500 tracking-wider font-semibold">
                  Switch Team Workspace
                </div>
                <div className="max-h-56 overflow-y-auto py-1 space-y-0.5">
                  {teams.map((t) => {
                    const isSelected = t.slug === currentTeam?.slug;
                    return (
                      <button
                        key={t.id}
                        onClick={() => {
                          setIsTeamMenuOpen(false);
                          setActiveTeam(t);
                          router.push(`/${t.slug}`);
                        }}
                        className={`w-full px-3 py-1.5 text-left flex items-center justify-between hover:bg-white/[0.06] transition-colors cursor-pointer ${
                          isSelected ? "text-white font-semibold bg-white/[0.04]" : "text-zinc-300"
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0 pr-2">
                          <div
                            className={`w-4 h-4 rounded flex items-center justify-center text-[10px] font-bold ${
                              isSelected
                                ? "bg-indigo-500/30 text-indigo-300 border border-indigo-500/40"
                                : "bg-white/[0.04] text-zinc-400"
                            }`}
                          >
                            {t.name.charAt(0).toUpperCase()}
                          </div>
                          <span className="truncate">{t.name}</span>
                        </div>
                        {isSelected && (
                          <Check className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                        )}
                      </button>
                    );
                  })}
                </div>
                <div className="border-t border-white/[0.06] my-1" />
                <button
                  onClick={() => {
                    setIsTeamMenuOpen(false);
                    setIsCreateTeamOpen(true);
                  }}
                  className="w-full px-3 py-1.5 text-left flex items-center gap-2 text-zinc-300 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5 text-zinc-400" />
                  <span className="font-medium">Create New Team</span>
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href={`/${teamSlug}/settings`}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-zinc-400 hover:text-white rounded hover:bg-white/[0.05] transition-colors"
          >
            <Settings className="w-3.5 h-3.5" />
            <span>Settings</span>
          </Link>
          <div className="w-px h-4 bg-white/[0.06]" />
          <button
            onClick={() => setIsCreateTeamOpen(true)}
            className="px-2.5 py-1 text-xs text-zinc-400 hover:text-white rounded hover:bg-white/[0.05] transition-colors cursor-pointer"
          >
            + Create Team
          </button>
          <div className="w-px h-4 bg-white/[0.06]" />
          <div className="w-7 h-7 rounded-full bg-white/[0.06] border border-white/[0.08] flex items-center justify-center text-xs font-bold text-zinc-300">
            {(user?.username || "U").charAt(0).toUpperCase()}
          </div>
        </div>
      </header>

      {/* Main Workspace Directory Container */}
      <main className="flex-1 max-w-5xl w-full mx-auto px-6 py-10 space-y-8">
        {/* Section Heading & Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/[0.06]">
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">Projects</h1>
            <p className="text-xs text-zinc-400 mt-1">
              Select a project to explore code knowledge graphs, PR reviews, and intelligence.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Search */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-2.5 pointer-events-none" />
              <input
                type="text"
                placeholder="Search projects..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-3 py-1.5 bg-white/[0.03] border border-white/[0.08] rounded-md text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-500 w-56 font-mono transition-colors"
              />
            </div>

            {/* New Project Button */}
            <button
              onClick={() => setIsCreateProjectOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold transition-colors cursor-pointer shrink-0"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New Project</span>
            </button>
          </div>
        </div>

        {/* Projects Rows with subtle 1px dividers, no heavy card boxes */}
        {filteredProjects.length === 0 ? (
          <div className="rounded-lg border border-white/[0.06] bg-[#11131a] p-12 text-center space-y-4 max-w-md mx-auto my-12">
            <div className="w-10 h-10 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center mx-auto text-zinc-400">
              <FolderGit2 className="w-5 h-5 text-zinc-400" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">No projects found</h3>
              <p className="text-xs text-zinc-500 mt-1">
                {searchQuery
                  ? "No projects match your search query."
                  : "Get started by creating your first project in this workspace."}
              </p>
            </div>
            <button
              onClick={() => setIsCreateProjectOpen(true)}
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create Project</span>
            </button>
          </div>
        ) : (
          <div className="border-t border-b border-white/[0.06] divide-y divide-white/[0.06]">
            {filteredProjects.map((project) => {
              const repoCount = project.repositoryCount || (project.repositories || []).length || 0;
              const isBuilding = project.status === "BUILDING";
              const isReady = project.status === "READY";

              return (
                <div
                  key={project.id}
                  className="group py-4 px-3 flex items-center justify-between hover:bg-white/[0.02] transition-colors"
                >
                  <Link
                    href={`/${teamSlug}/${project.slug}`}
                    className="min-w-0 pr-4 flex-1 cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-white group-hover:text-indigo-300 font-mono transition-colors">
                        {project.name}
                      </span>
                      <span className="text-[10px] font-mono text-zinc-500">
                        {project.slug}
                      </span>
                    </div>

                    {project.description && (
                      <p className="text-xs text-zinc-400 truncate mt-1 max-w-xl">
                        {project.description}
                      </p>
                    )}

                    <div className="flex items-center gap-3 text-[11px] font-mono text-zinc-500 mt-2">
                      <span className="flex items-center gap-1.5">
                        <FolderGit2 className="w-3 h-3 text-zinc-600" />
                        <span>{repoCount} {repoCount === 1 ? "repo" : "repos"}</span>
                      </span>
                      <span>•</span>
                      <span>Updated {formatRelativeTime(project.updatedAt)}</span>
                    </div>
                  </Link>

                  <div className="flex items-center gap-4 shrink-0">
                    <div>
                      {isBuilding ? (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
                          Building
                        </span>
                      ) : isReady ? (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                          Ready
                        </span>
                      ) : null}
                    </div>

                    {/* Action buttons: Edit & Delete */}
                    <div className="flex items-center gap-1 opacity-60 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setProjectToEdit(project);
                        }}
                        className="p-1.5 text-zinc-400 hover:text-white rounded hover:bg-white/[0.08] transition-colors cursor-pointer"
                        title="Edit Project"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setProjectToDelete(project);
                        }}
                        className="p-1.5 text-zinc-400 hover:text-rose-400 rounded hover:bg-rose-500/10 transition-colors cursor-pointer"
                        title="Delete Project"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <Link
                      href={`/${teamSlug}/${project.slug}`}
                      className="text-zinc-600 group-hover:text-white group-hover:translate-x-0.5 transition-all"
                    >
                      <ArrowRight className="w-4 h-4" />
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Modals */}
      <CreateProjectModal
        isOpen={isCreateProjectOpen}
        onClose={() => setIsCreateProjectOpen(false)}
        teamSlug={teamSlug}
        onSuccess={(newSlug) => router.push(`/${teamSlug}/${newSlug}`)}
      />

      <CreateTeamModal
        isOpen={isCreateTeamOpen}
        onClose={() => setIsCreateTeamOpen(false)}
        onSuccess={(newSlug) => router.push(`/${newSlug}`)}
      />

      {projectToEdit && (
        <EditProjectModal
          isOpen={!!projectToEdit}
          onClose={() => setProjectToEdit(null)}
          project={projectToEdit}
          onSuccess={() => {
            if (token) fetchTeamProjects(token, teamSlug, true);
          }}
        />
      )}

      {projectToDelete && (
        <DeleteProjectModal
          isOpen={!!projectToDelete}
          onClose={() => setProjectToDelete(null)}
          project={projectToDelete}
          onSuccess={() => {
            if (token) fetchTeamProjects(token, teamSlug, true);
          }}
        />
      )}
    </div>
  );
}

export default function TeamOverviewPage() {
  return (
    <ProtectedRoute>
      <TeamOverviewContent />
    </ProtectedRoute>
  );
}
