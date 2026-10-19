"use client";

import React, { useState, useEffect } from "react";
import { X, Settings2, Loader2, Check } from "lucide-react";
import { useProjectStore } from "../../store/projectStore";
import { useAuthStore } from "../../store/authStore";
import { Project } from "../../lib/types";

interface EditProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  project: Project;
  onSuccess?: (updated: Project) => void;
}

export const EditProjectModal: React.FC<EditProjectModalProps> = ({
  isOpen,
  onClose,
  project,
  onSuccess,
}) => {
  const { token } = useAuthStore();
  const { updateProject } = useProjectStore();

  const [name, setName] = useState(project.name || "");
  const [description, setDescription] = useState(project.description || "");
  const [slug, setSlug] = useState(project.slug || "");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (project) {
      setName(project.name || "");
      setDescription(project.description || "");
      setSlug(project.slug || "");
      setError(null);
    }
  }, [project, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Please enter a project name");
      return;
    }
    if (!token) {
      setError("You must be authenticated to update this project");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const updated = await updateProject(token, project.id, {
        name: name.trim(),
        description: description.trim(),
        slug: slug.trim() || undefined,
      });
      setIsLoading(false);
      onClose();
      if (onSuccess) {
        onSuccess(updated);
      }
    } catch (err: any) {
      setError(err.message || "Failed to update project");
      setIsLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs animate-fade-in"
      onClick={onClose}
    >
      <div
        className="bg-[#11131a] border border-white/[0.08] rounded-xl w-full max-w-md shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-white/[0.04] border border-white/[0.06] rounded-lg text-white">
              <Settings2 className="w-4 h-4 text-indigo-400" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Edit Project Settings</h3>
              <p className="text-[11px] text-zinc-400 font-mono">Update metadata for {project.name}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-white p-1 rounded-md hover:bg-white/[0.06] transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
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
              Project Slug <span className="text-zinc-500 font-normal font-mono">(URL path)</span>
            </label>
            <input
              type="text"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              className="w-full px-3 py-2 bg-white/[0.03] border border-white/[0.08] rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/20 focus:bg-white/[0.05] font-mono transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">
              Description <span className="text-zinc-500 font-normal">(optional)</span>
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Core intelligence services and call graph indexing"
              className="w-full px-3 py-2 bg-white/[0.03] border border-white/[0.08] rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/20 focus:bg-white/[0.05] transition-colors resize-none"
            />
          </div>

          {error && (
            <div className="p-2.5 rounded-lg bg-red-950/40 border border-red-500/30 text-red-300 text-xs">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-white/[0.06]">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-2 rounded-lg text-xs font-medium text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading || !name.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-white hover:bg-zinc-200 text-black rounded-lg text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span>Save Changes</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
