"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  FolderGit2,
  ArrowRight,
  Loader2,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Laptop,
  Github,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { useRepoStore } from "../../store/repoStore";
import { githubApi } from "../../lib/api";

interface AddProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export const AddProjectModal: React.FC<AddProjectModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { token } = useAuthStore();
  const { getInstallUrl, fetchIndexedRepos } = useRepoStore();

  const [tab, setTab] = useState<"github" | "local">("github");
  const [repoId, setRepoId] = useState("");
  const [repoDir, setRepoDir] = useState("");
  const [branch, setBranch] = useState("main");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [installUrl, setInstallUrl] = useState<string | null>(null);
  const [isFetchingUrl, setIsFetchingUrl] = useState(false);

  useEffect(() => {
    if (isOpen && tab === "github" && token) {
      setIsFetchingUrl(true);
      getInstallUrl(token)
        .then((url) => setInstallUrl(url))
        .catch((e) => console.warn("Could not fetch GitHub install URL:", e))
        .finally(() => setIsFetchingUrl(false));
    }
  }, [isOpen, tab, token, getInstallUrl]);

  // Reset transient state whenever the modal is (re)opened.
  useEffect(() => {
    if (isOpen) {
      setError(null);
      setSuccessMsg(null);
      setRepoId("");
      setRepoDir("");
      setBranch("main");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleLocalIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoId.trim() || !repoDir.trim()) {
      setError("Please provide both a Project ID and a local repository directory path.");
      return;
    }
    if (!token) {
      setError("You must be signed in to ingest a repository.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      await githubApi.ingestLocal(token, {
        repo_id: repoId.trim(),
        repo_dir: repoDir.trim(),
        branch: branch.trim() || "main",
      });
      await fetchIndexedRepos(token, true);
      setSuccessMsg(`Project "${repoId.trim()}" ingested successfully!`);
      setTimeout(() => {
        onSuccess?.();
        onClose();
      }, 900);
    } catch (err: any) {
      setError(err.message || "Failed to ingest repository. Ensure the directory exists and the AI service is running.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGitHubConnect = () => {
    if (installUrl) {
      window.location.href = installUrl;
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xs animate-fade-in"
      onClick={onClose}
    >
      <div
        className="bg-[#0f0f0f] border border-zinc-800 rounded-xl w-full max-w-lg shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-zinc-800 rounded-lg text-white">
              <FolderGit2 className="w-4 h-4 text-blue-400" />
            </div>
            <h3 className="text-sm font-semibold text-white">Add New Project</h3>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-white p-1 rounded-md hover:bg-zinc-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Selection */}
        <div className="flex border-b border-zinc-800 px-5 bg-zinc-950/60">
          <button
            onClick={() => setTab("github")}
            className={`py-3 px-3 text-xs font-semibold border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              tab === "github"
                ? "border-white text-white"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Github className="w-3.5 h-3.5" />
            <span>GitHub App (Recommended)</span>
          </button>
          <button
            onClick={() => setTab("local")}
            className={`py-3 px-3 text-xs font-semibold border-b-2 transition-colors flex items-center gap-2 cursor-pointer ${
              tab === "local"
                ? "border-white text-white"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Laptop className="w-3.5 h-3.5" />
            <span>Local Directory</span>
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-4">
          {tab === "github" ? (
            <div className="space-y-4">
              <div className="rounded-lg bg-zinc-900/60 border border-zinc-800 p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-black border border-zinc-700 flex items-center justify-center text-white shrink-0">
                    <Github className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-white">Install the Sentinel GitHub App</h4>
                    <p className="text-[11px] text-zinc-400 leading-relaxed">
                      Authorizes automated PR evaluations, webhooks, and one-click fix patches directly on your GitHub repositories.
                    </p>
                  </div>
                </div>

                <div className="space-y-2 pt-1 text-[11px] text-zinc-400">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span>Automatic webhook synchronization on pull requests</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span>Choose all repositories or only specific ones</span>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={handleGitHubConnect}
                disabled={isFetchingUrl || !installUrl}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-white hover:bg-zinc-200 text-black font-semibold text-xs transition-all cursor-pointer disabled:opacity-50"
              >
                {isFetchingUrl ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Loading GitHub App...</span>
                  </>
                ) : (
                  <>
                    <Github className="w-4 h-4" />
                    <span>Install / Configure on GitHub</span>
                    <ExternalLink className="w-3.5 h-3.5 ml-1 text-zinc-600" />
                  </>
                )}
              </button>
            </div>
          ) : (
            <form onSubmit={handleLocalIngest} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                  Project Identifier
                </label>
                <input
                  type="text"
                  placeholder="e.g. my-service"
                  value={repoId}
                  onChange={(e) => setRepoId(e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600 transition-colors"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                  Repository Directory Path
                </label>
                <input
                  type="text"
                  placeholder="e.g. /home/you/projects/my-service"
                  value={repoDir}
                  onChange={(e) => setRepoDir(e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600 transition-colors"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1.5">
                  Default Branch
                </label>
                <input
                  type="text"
                  placeholder="main"
                  value={branch}
                  onChange={(e) => setBranch(e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-600 transition-colors"
                />
              </div>

              {error && (
                <div className="flex items-start gap-2 p-3 rounded-lg bg-red-950/40 border border-red-800/60 text-red-300 text-xs">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-400" />
                  <span>{error}</span>
                </div>
              )}

              {successMsg && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-950/40 border border-emerald-800/60 text-emerald-300 text-xs">
                  <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
                  <span>{successMsg}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-zinc-800">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-3.5 py-2 rounded-lg text-xs font-medium text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="flex items-center gap-2 px-4 py-2 bg-white hover:bg-zinc-200 text-black rounded-lg text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Ingesting Codebase...</span>
                    </>
                  ) : (
                    <>
                      <span>Import Repository</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
