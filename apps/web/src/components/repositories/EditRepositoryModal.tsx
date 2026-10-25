"use client";

import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { X, GitBranch, Loader2, Check } from "lucide-react";
import { useRepoStore } from "../../store/repoStore";
import { useAuthStore } from "../../store/authStore";
import { ConnectedRepository } from "../../lib/types";

interface EditRepositoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  repository: ConnectedRepository;
  onSuccess?: (updated: ConnectedRepository) => void;
}

export const EditRepositoryModal: React.FC<EditRepositoryModalProps> = ({
  isOpen,
  onClose,
  repository,
  onSuccess,
}) => {
  const { token } = useAuthStore();
  const { updateRepo } = useRepoStore();

  const [defaultBranch, setDefaultBranch] = useState(repository.defaultBranch || "main");
  const [isActive, setIsActive] = useState(repository.isActive ?? true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (repository) {
      setDefaultBranch(repository.defaultBranch || "main");
      setIsActive(repository.isActive ?? true);
      setError(null);
    }
  }, [repository, isOpen]);

  if (!isOpen || !mounted) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!defaultBranch.trim()) {
      setError("Please specify a default branch");
      return;
    }
    if (!token) {
      setError("Authentication required");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const updated = await updateRepo(token, repository.id, {
        defaultBranch: defaultBranch.trim(),
        isActive,
      });
      setIsLoading(false);
      onClose();
      if (updated && onSuccess) {
        onSuccess(updated);
      }
    } catch (err: any) {
      setError(err.message || "Failed to update repository");
      setIsLoading(false);
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs animate-fade-in"
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
              <GitBranch className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Repository Settings</h3>
              <p className="text-[11px] text-zinc-400 font-mono truncate max-w-[280px]">
                {repository.fullName}
              </p>
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
              Default Target Branch
            </label>
            <input
              type="text"
              value={defaultBranch}
              onChange={(e) => setDefaultBranch(e.target.value)}
              placeholder="main"
              className="w-full px-3 py-2 bg-white/[0.03] border border-white/[0.08] rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/20 focus:bg-white/[0.05] font-mono transition-colors"
              required
            />
            <p className="text-[11px] text-zinc-500 mt-1">
              Used for automated indexing, AST call-graph tracing, and default PR base comparisons.
            </p>
          </div>

          <div className="pt-2">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="w-4 h-4 rounded bg-[#0c0d12] border-white/[0.1] text-indigo-500 focus:ring-0 focus:ring-offset-0 cursor-pointer"
              />
              <div>
                <p className="text-xs font-medium text-white">Active in Knowledge Base</p>
                <p className="text-[11px] text-zinc-500">
                  Allow automated PR evaluation and interactive knowledge graph exploration.
                </p>
              </div>
            </label>
          </div>

          {error && (
            <div className="p-2.5 rounded-lg bg-red-950/40 border border-red-500/30 text-red-300 text-xs">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-white/[0.06]">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-2 rounded-lg text-xs font-medium text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading || !defaultBranch.trim()}
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
                  <span>Save Settings</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
};
