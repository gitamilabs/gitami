"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  Layers,
  FolderGit2,
  Trash2,
  Plus,
  Loader2,
  Check,
  AlertTriangle,
  ExternalLink,
  ChevronDown,
  GitBranch,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { useTeamStore } from "@/store/teamStore";
import { useProjectStore } from "@/store/projectStore";
import { Project } from "@/lib/types";
import { CreateProjectModal } from "@/components/projects/CreateProjectModal";
import { ConnectRepositoryModal } from "@/components/repositories/ConnectRepositoryModal";

export const ProjectSettings: React.FC = () => {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();

  const teamSlug = (params?.teamSlug as string) || "";
  const requestedProjectSlug = searchParams.get("project") || "";

  const { token } = useAuthStore();
  const { teams, activeTeam } = useTeamStore();
  const {
    projects,
    activeProject,
    fetchTeamProjects,
    fetchProjectDetails,
    updateProject,
    deleteProject,
    detachRepository,
    setActiveProject,
  } = useProjectStore();

  const currentTeam = teams.find((t) => t.slug === teamSlug) || activeTeam;

  // Selected project state
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [isProjectDropdownOpen, setIsProjectDropdownOpen] = useState(false);

  // Form edit state
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Modals & Actions
  const [isCreateProjectOpen, setIsCreateProjectOpen] = useState(false);
  const [isConnectRepoOpen, setIsConnectRepoOpen] = useState(false);
  const [detachingRepoId, setDetachingRepoId] = useState<string | null>(null);

  // Delete modal state
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Ensure projects for current team are loaded
  useEffect(() => {
    if (token && teamSlug) {
      fetchTeamProjects(token, teamSlug);
    }
  }, [token, teamSlug, fetchTeamProjects]);

  // Determine active target project
  const currentProject =
    projects.find((p) => p.id === selectedProjectId) ||
    projects.find((p) => p.slug === requestedProjectSlug) ||
    activeProject ||
    projects[0] ||
    null;

  // Sync selected project id when projects load or change
  useEffect(() => {
    if (currentProject && currentProject.id !== selectedProjectId) {
      setSelectedProjectId(currentProject.id);
    }
  }, [currentProject?.id]);

  // Populate form fields whenever current project changes
  useEffect(() => {
    if (currentProject) {
      setName(currentProject.name || "");
      setSlug(currentProject.slug || "");
      setDescription(currentProject.description || "");
      setError(null);
      setSaveSuccess(false);
      setDeleteConfirmText("");
      setDeleteError(null);
    }
  }, [currentProject?.id, currentProject?.slug, currentProject?.name, currentProject?.description]);

  // Load project details (e.g. connected repositories) when selected
  useEffect(() => {
    if (token && currentProject?.slug) {
      fetchProjectDetails(token, currentProject.slug);
    }
  }, [token, currentProject?.slug, fetchProjectDetails]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !currentProject) return;
    if (!name.trim()) {
      setError("Project name cannot be empty");
      return;
    }

    setIsSaving(true);
    setError(null);
    setSaveSuccess(false);

    try {
      const updated = await updateProject(token, currentProject.id, {
        name: name.trim(),
        description: description.trim(),
        slug: slug.trim() || undefined,
      });

      setIsSaving(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);

      // If slug changed, update URL query param
      if (updated.slug && updated.slug !== currentProject.slug) {
        router.replace(`/${teamSlug}/settings?tab=project&project=${updated.slug}`);
      }
    } catch (err: any) {
      setError(err.message || "Failed to update project");
      setIsSaving(false);
    }
  };

  const handleDetachRepo = async (repoId: string) => {
    if (!token || !currentProject) return;
    if (!confirm("Are you sure you want to detach this repository from the project?")) return;

    setDetachingRepoId(repoId);
    try {
      await detachRepository(token, currentProject.slug, repoId);
      await fetchProjectDetails(token, currentProject.slug, true);
    } catch (err: any) {
      alert(err.message || "Failed to detach repository");
    } finally {
      setDetachingRepoId(null);
    }
  };

  const handleDeleteProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !currentProject) return;
    if (deleteConfirmText !== currentProject.name) {
      setDeleteError(`Please type "${currentProject.name}" to confirm.`);
      return;
    }

    setIsDeleting(true);
    setDeleteError(null);

    try {
      await deleteProject(token, currentProject.id);
      setIsDeleting(false);
      setShowDeleteModal(false);
      await fetchTeamProjects(token, teamSlug, true);
      router.replace(`/${teamSlug}/settings?tab=project`);
    } catch (err: any) {
      setDeleteError(err.message || "Failed to delete project");
      setIsDeleting(false);
    }
  };

  if (projects.length === 0) {
    return (
      <div className="space-y-6 animate-fade-in">
        <section className="bg-[#11131a] border border-white/[0.06] rounded-xl p-8 text-center space-y-4">
          <div className="w-12 h-12 rounded-xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-center mx-auto text-zinc-400">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-white">No Projects in {currentTeam?.name || teamSlug}</h3>
            <p className="text-xs text-zinc-400 mt-1 max-w-md mx-auto">
              This workspace does not have any active projects yet. Create a project to connect repositories and run autonomous builds.
            </p>
          </div>
          <button
            onClick={() => setIsCreateProjectOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white hover:bg-zinc-200 text-black rounded-lg text-xs font-semibold transition-colors cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Create First Project</span>
          </button>
        </section>

        <CreateProjectModal
          isOpen={isCreateProjectOpen}
          onClose={() => setIsCreateProjectOpen(false)}
          teamSlug={teamSlug}
          onSuccess={async (newSlug) => {
            if (token) {
              const projs = await fetchTeamProjects(token, teamSlug, true);
              const created = projs.find((p) => p.slug === newSlug);
              if (created) {
                setActiveProject(created);
                setSelectedProjectId(created.id);
              }
            }
            router.replace(`/${teamSlug}/settings?tab=project&project=${newSlug}`);
          }}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Project Selector Banner */}
      <div className="p-4 rounded-xl bg-indigo-500/[0.04] border border-indigo-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="relative">
          <label className="block text-[10px] uppercase font-mono tracking-wider text-indigo-300 font-semibold mb-1">
            Target Project to Configure
          </label>
          <button
            type="button"
            onClick={() => setIsProjectDropdownOpen(!isProjectDropdownOpen)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.1] text-xs font-semibold text-white transition-colors cursor-pointer group"
          >
            <Layers className="w-3.5 h-3.5 text-indigo-400" />
            <span>{currentProject?.name}</span>
            <span className="text-[10px] text-zinc-500 font-normal">({currentProject?.slug})</span>
            <ChevronDown
              className={`w-3.5 h-3.5 text-zinc-400 transition-transform ${
                isProjectDropdownOpen ? "rotate-180" : ""
              }`}
            />
          </button>

          {isProjectDropdownOpen && (
            <div className="absolute left-0 top-full mt-1.5 w-64 bg-[#13151f] border border-white/[0.08] rounded-lg shadow-2xl py-1.5 z-40 animate-fade-in text-xs">
              <div className="px-3 py-1 text-[10px] font-mono uppercase text-zinc-500 tracking-wider font-semibold">
                Select Project
              </div>
              <div className="max-h-56 overflow-y-auto py-1 space-y-0.5">
                {projects.map((p) => {
                  const isSelected = p.id === currentProject?.id;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => {
                        setIsProjectDropdownOpen(false);
                        setSelectedProjectId(p.id);
                        setActiveProject(p);
                        router.replace(`/${teamSlug}/settings?tab=project&project=${p.slug}`);
                      }}
                      className={`w-full px-3 py-1.5 text-left flex items-center justify-between hover:bg-white/[0.06] transition-colors cursor-pointer ${
                        isSelected ? "text-white font-semibold bg-white/[0.04]" : "text-zinc-300"
                      }`}
                    >
                      <span className="truncate">{p.name}</span>
                      {isSelected && <Check className="w-3.5 h-3.5 text-indigo-400 shrink-0" />}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => router.push(`/${teamSlug}/${currentProject?.slug}`)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-300 hover:text-white rounded-md text-xs font-medium transition-colors cursor-pointer"
          >
            <span>Go to Project</span>
            <ExternalLink className="w-3 h-3 text-zinc-500" />
          </button>
          <button
            type="button"
            onClick={() => setIsCreateProjectOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-zinc-200 text-black rounded-md text-xs font-semibold transition-colors cursor-pointer shrink-0"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Create New Project</span>
          </button>
        </div>
      </div>

      {/* Project Metadata Settings */}
      {currentProject && (
        <section className="bg-[#11131a] border border-white/[0.06] rounded-xl p-6 space-y-5 shadow-sm">
          <div className="border-b border-white/[0.06] pb-4">
            <h2 className="text-sm font-bold text-white tracking-tight">
              General Project Details
            </h2>
            <p className="text-xs text-zinc-400 mt-1">
              Update project name, URL slug identifier, and overview description.
            </p>
          </div>

          <form onSubmit={handleSave} className="space-y-4 max-w-xl">
            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                Project Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 bg-white/[0.03] border border-white/[0.08] rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/20 focus:bg-white/[0.05] transition-colors"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                Project Slug <span className="text-zinc-500 font-mono font-normal">(URL path)</span>
              </label>
              <input
                type="text"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                className="w-full px-3 py-2 bg-white/[0.03] border border-white/[0.08] rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/20 focus:bg-white/[0.05] font-mono transition-colors"
              />
              <p className="text-[11px] text-zinc-500 mt-1 font-mono">
                Access project at: /{teamSlug}/{slug || currentProject.slug}
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                Description <span className="text-zinc-500 font-normal">(optional)</span>
              </label>
              <textarea
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief summary of the project architecture and services"
                className="w-full px-3 py-2 bg-white/[0.03] border border-white/[0.08] rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/20 focus:bg-white/[0.05] transition-colors resize-none"
              />
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
                {error}
              </div>
            )}

            {saveSuccess && (
              <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
                <Check className="w-4 h-4" />
                <span>Project details updated successfully.</span>
              </div>
            )}

            <div className="pt-2">
              <button
                type="submit"
                disabled={isSaving || !name.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-white hover:bg-zinc-200 text-black rounded-lg text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
              >
                {isSaving ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Saving...</span>
                  </>
                ) : (
                  <>
                    <Check className="w-3.5 h-3.5" />
                    <span>Save Project Details</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </section>
      )}

      {/* Connected Repositories Section */}
      {currentProject && (
        <section className="bg-[#11131a] border border-white/[0.06] rounded-xl p-6 space-y-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-white/[0.06] pb-4">
            <div>
              <h2 className="text-sm font-bold text-white tracking-tight">
                Attached Repositories
              </h2>
              <p className="text-xs text-zinc-400 mt-1">
                Repositories linked to this project for graph indexing, symbol analysis, and PR reviews.
              </p>
            </div>
            <button
              onClick={() => setIsConnectRepoOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-white rounded-md text-xs font-medium transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5 text-zinc-400" />
              <span>Connect Repository</span>
            </button>
          </div>

          {(!currentProject.repositories || currentProject.repositories.length === 0) ? (
            <div className="p-6 text-center rounded-xl bg-[#0c0d12] border border-white/[0.06] space-y-2">
              <FolderGit2 className="w-6 h-6 text-zinc-600 mx-auto" />
              <p className="text-xs text-zinc-400">No repositories attached to this project yet.</p>
              <button
                onClick={() => setIsConnectRepoOpen(true)}
                className="text-xs text-indigo-400 hover:text-indigo-300 font-medium cursor-pointer"
              >
                + Connect an existing repository
              </button>
            </div>
          ) : (
            <div className="space-y-2.5">
              {currentProject.repositories.map((repo) => (
                <div
                  key={repo.id}
                  className="flex items-center justify-between p-3.5 rounded-xl bg-[#0c0d12] border border-white/[0.06]"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-zinc-300 shrink-0">
                      <FolderGit2 className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-white truncate">{repo.name}</p>
                      <p className="text-[11px] text-zinc-400 font-mono truncate">
                        {repo.fullName || repo.name}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    <span className="flex items-center gap-1 text-[11px] font-mono text-zinc-400">
                      <GitBranch className="w-3 h-3 text-zinc-500" />
                      {repo.defaultBranch || "main"}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleDetachRepo(repo.id)}
                      disabled={detachingRepoId === repo.id}
                      className="px-2.5 py-1 text-xs text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 rounded transition-colors cursor-pointer disabled:opacity-50"
                      title="Detach repository from this project"
                    >
                      {detachingRepoId === repo.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <span>Detach</span>
                      )}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Danger Zone: Delete Project */}
      {currentProject && (
        <section className="bg-[#11131a] border border-rose-500/20 rounded-xl p-6 space-y-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-rose-400">Danger Zone: Delete Project</h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                Permanently deletes <span className="text-white font-semibold">{currentProject.name}</span> and unbinds associated build indexes.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowDeleteModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-500/10 border border-rose-500/20 hover:bg-rose-500/20 text-rose-300 rounded-lg text-xs font-semibold transition-colors cursor-pointer shrink-0"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Delete Project</span>
            </button>
          </div>
        </section>
      )}

      {/* Delete Project Confirmation Modal */}
      {showDeleteModal && currentProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs animate-fade-in">
          <div className="bg-[#11131a] border border-rose-500/30 rounded-xl w-full max-w-md p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-400">
              <div className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/20">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white">Delete Project</h3>
            </div>
            <p className="text-xs text-zinc-300 leading-relaxed">
              This action cannot be undone. To permanently delete the project{" "}
              <strong className="text-white font-mono">{currentProject.name}</strong>, please type the project name below:
            </p>
            <input
              type="text"
              value={deleteConfirmText}
              onChange={(e) => setDeleteConfirmText(e.target.value)}
              placeholder={currentProject.name}
              className="w-full px-3 py-2 bg-white/[0.04] border border-rose-500/30 rounded-lg text-xs text-white placeholder-zinc-500 font-mono focus:outline-none focus:border-rose-500 transition-colors"
            />
            {deleteError && (
              <p className="text-xs text-rose-400 bg-rose-500/10 p-2.5 rounded-lg border border-rose-500/20">
                {deleteError}
              </p>
            )}
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/[0.06]">
              <button
                type="button"
                onClick={() => {
                  setShowDeleteModal(false);
                  setDeleteError(null);
                  setDeleteConfirmText("");
                }}
                className="px-3.5 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-white transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteProject}
                disabled={deleteConfirmText !== currentProject.name || isDeleting}
                className="flex items-center gap-1.5 px-4 py-1.5 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-40 cursor-pointer"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <span>I understand, delete this project</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Project Modal */}
      <CreateProjectModal
        isOpen={isCreateProjectOpen}
        onClose={() => setIsCreateProjectOpen(false)}
        teamSlug={teamSlug}
        onSuccess={async (newSlug) => {
          if (token) {
            const projs = await fetchTeamProjects(token, teamSlug, true);
            const created = projs.find((p) => p.slug === newSlug);
            if (created) {
              setActiveProject(created);
              setSelectedProjectId(created.id);
            }
          }
          router.replace(`/${teamSlug}/settings?tab=project&project=${newSlug}`);
        }}
      />

      {/* Connect Repository Modal */}
      {currentProject && (
        <ConnectRepositoryModal
          isOpen={isConnectRepoOpen}
          onClose={() => setIsConnectRepoOpen(false)}
          teamSlug={teamSlug}
          projectSlug={currentProject.slug}
          projectId={currentProject.id}
          onSuccess={() => {
            if (token) fetchProjectDetails(token, currentProject.slug, true);
          }}
        />
      )}
    </div>
  );
};
