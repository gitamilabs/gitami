"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  X,
  Github,
  Search,
  Lock,
  Globe,
  Loader2,
  ExternalLink,
  GitBranch,
  ChevronDown,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { useRepoStore } from "../../store/repoStore";
import { useProjectStore } from "../../store/projectStore";
import { useBuildStore } from "../../store/buildStore";
import { githubApi } from "../../lib/api";
import { ConnectedRepository } from "../../lib/types";

interface ConnectRepositoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  teamSlug: string;
  projectSlug: string;
  projectId: string;
  onSuccess?: () => void;
}

export const ConnectRepositoryModal: React.FC<ConnectRepositoryModalProps> = ({
  isOpen,
  onClose,
  teamSlug,
  projectSlug,
  projectId,
  onSuccess,
}) => {
  const router = useRouter();
  const { token } = useAuthStore();
  const { connectedRepos, fetchConnectedRepos } = useRepoStore();
  const { activeProject, attachRepository } = useProjectStore();
  const { startBuild } = useBuildStore();

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedOwner, setSelectedOwner] = useState<string>("all");
  const [installUrl, setInstallUrl] = useState<string | null>(null);
  const [isFetchingUrl, setIsFetchingUrl] = useState(false);
  const [connectingRepoId, setConnectingRepoId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && token) {
      fetchConnectedRepos(token, true);

      // Fetch GitHub App URL with encoded teamSlug and projectSlug state
      setIsFetchingUrl(true);
      githubApi
        .getInstallUrl(token, teamSlug, projectSlug)
        .then((res) => setInstallUrl(res.installUrl))
        .catch((err) => console.warn("Failed to get install URL:", err))
        .finally(() => setIsFetchingUrl(false));
    }
  }, [isOpen, token, teamSlug, projectSlug, fetchConnectedRepos]);

  if (!isOpen) return null;

  // Extract distinct owners/organizations
  const owners = Array.from(
    new Set(
      connectedRepos
        .map((repo) => repo.fullName.split("/")[0])
        .filter(Boolean)
    )
  );

  // Filter available GitHub repositories
  const filteredRepos = connectedRepos.filter((repo) => {
    const [owner] = repo.fullName.split("/");
    if (selectedOwner !== "all" && owner !== selectedOwner) {
      return false;
    }
    const query = searchQuery.toLowerCase().trim();
    return (
      !query ||
      repo.name.toLowerCase().includes(query) ||
      repo.fullName.toLowerCase().includes(query)
    );
  });

  const handleImportGitHubRepo = async (repo: ConnectedRepository) => {
    if (!token) return;
    setConnectingRepoId(repo.id);
    setError(null);

    try {
      // 1. Attach repository specifically to current project
      await attachRepository(token, projectId, repo.id);

      // 2. Start build in background
      await startBuild(token, projectId, repo.id, repo.defaultBranch || "main");

      setConnectingRepoId(null);
      onSuccess?.();
      onClose();

      // 3. Immediately redirect to live builds page
      router.push(`/${teamSlug}/${projectSlug}/builds`);
    } catch (err: any) {
      setError(err.message || "Failed to connect repository");
      setConnectingRepoId(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs animate-fade-in"
      onClick={onClose}
    >
      <div
        className="bg-[#11131a] border border-white/[0.08] rounded-xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06] shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-white/[0.04] border border-white/[0.06] rounded-lg text-white">
              <Github className="w-4 h-4 text-white" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Connect GitHub Repository</h3>
              <p className="text-[11px] text-zinc-400">Select a repository installed via the GitAmi GitHub App</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-white p-1 rounded hover:bg-white/[0.05] transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 overflow-y-auto flex-1 space-y-4">
          {error && (
            <div className="p-2.5 rounded-lg bg-red-950/40 border border-red-800/60 text-red-300 text-xs">
              {error}
            </div>
          )}

          <div className="space-y-4">
            {/* Search & GitHub App Config */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
              {owners.length > 1 && (
                <div className="relative shrink-0">
                  <select
                    value={selectedOwner}
                    onChange={(e) => setSelectedOwner(e.target.value)}
                    className="w-full sm:w-auto appearance-none pl-3 pr-8 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-xs text-white focus:outline-none focus:border-white/[0.2] transition-colors cursor-pointer"
                  >
                    <option value="all" className="bg-[#13151f] text-white">All Organizations</option>
                    {owners.map((owner) => (
                      <option key={owner} value={owner} className="bg-[#13151f] text-white">
                        {owner}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="w-3.5 h-3.5 text-zinc-400 absolute right-2.5 top-3 pointer-events-none" />
                </div>
              )}

              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-2.5 pointer-events-none" />
                <input
                  type="text"
                  placeholder="Search repositories..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 bg-white/[0.03] border border-white/[0.08] rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/[0.2] transition-colors"
                />
              </div>

              {installUrl && (
                <a
                  href={installUrl}
                  className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-300 hover:text-white text-xs font-medium transition-colors shrink-0"
                >
                  {isFetchingUrl ? (
                    <Loader2 className="w-3 h-3 animate-spin text-zinc-400" />
                  ) : (
                    <>
                      <span>Configure GitHub App</span>
                      <ExternalLink className="w-3 h-3 text-zinc-500" />
                    </>
                  )}
                </a>
              )}
            </div>

            {/* Repositories List */}
            <div className="border border-white/[0.06] rounded-xl overflow-hidden divide-y divide-white/[0.06] bg-[#0c0d12]">
              {filteredRepos.length === 0 ? (
                <div className="p-8 text-center space-y-3">
                  <p className="text-xs text-zinc-400">
                    No repositories found{searchQuery ? " matching your search" : ""}.
                  </p>
                  {installUrl && (
                    <a
                      href={installUrl}
                      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white text-black text-xs font-semibold hover:bg-zinc-200 transition-colors"
                    >
                      <Github className="w-3.5 h-3.5" />
                      <span>Install GitAmi on GitHub</span>
                    </a>
                  )}
                </div>
              ) : (
                filteredRepos.map((repo) => {
                  const isConnecting = connectingRepoId === repo.id;
                  const isAlreadyConnected = activeProject?.repositories?.some(
                    (r) => r.id === repo.id || r.fullName.toLowerCase() === repo.fullName.toLowerCase()
                  );

                  return (
                    <div
                      key={repo.id}
                      className="p-3.5 flex items-center justify-between hover:bg-white/[0.02] transition-colors"
                    >
                      <div className="flex items-center gap-3 min-w-0 pr-4">
                        <div className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center text-zinc-400 shrink-0">
                          {repo.isPrivate ? (
                            <Lock className="w-3.5 h-3.5 text-zinc-500" />
                          ) : (
                            <Globe className="w-3.5 h-3.5 text-zinc-500" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs font-semibold text-white truncate font-mono">
                            {repo.fullName}
                          </div>
                          <div className="flex items-center gap-2 text-[11px] text-zinc-500 font-mono mt-0.5">
                            <span className="flex items-center gap-1">
                              <GitBranch className="w-3 h-3 text-zinc-600" />
                              {repo.defaultBranch || "main"}
                            </span>
                          </div>
                        </div>
                      </div>

                      {isAlreadyConnected ? (
                        <span className="px-3 py-1.5 rounded-md bg-white/[0.03] border border-white/[0.06] text-zinc-500 text-xs font-medium shrink-0">
                          Connected
                        </span>
                      ) : (
                        <button
                          onClick={() => handleImportGitHubRepo(repo)}
                          disabled={isConnecting}
                          className="px-3.5 py-1.5 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold transition-colors disabled:opacity-50 shrink-0 cursor-pointer flex items-center gap-1.5"
                        >
                          {isConnecting ? (
                            <>
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              <span>Importing...</span>
                            </>
                          ) : (
                            <span>Import</span>
                          )}
                        </button>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
