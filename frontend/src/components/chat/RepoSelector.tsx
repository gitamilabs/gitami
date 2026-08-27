"use client";

import React, { useEffect } from "react";
import { useRepoStore } from "../../store/repoStore";
import { useChatStore } from "../../store/chatStore";
import { useAuthStore } from "../../store/authStore";
import { GitBranch, FolderGit2, ChevronDown } from "lucide-react";

export const RepoSelector: React.FC = () => {
  const { token } = useAuthStore();
  const { indexedRepos, fetchIndexedRepos } = useRepoStore();
  const { selectedRepo, selectedBranch, setSelectedRepo, setSelectedBranch } = useChatStore();

  useEffect(() => {
    if (token) fetchIndexedRepos(token);
  }, [token, fetchIndexedRepos]);

  // Auto-select the first available indexed repo once the list loads, if
  // nothing (or a stale/no-longer-indexed repo) is currently selected.
  useEffect(() => {
    if (indexedRepos.length === 0) return;
    if (!selectedRepo || !indexedRepos.includes(selectedRepo)) {
      setSelectedRepo(indexedRepos[0]);
    }
  }, [indexedRepos, selectedRepo, setSelectedRepo]);

  if (indexedRepos.length === 0) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-900/90 border border-zinc-800 text-xs text-zinc-500">
        <FolderGit2 className="w-3.5 h-3.5 shrink-0" />
        <span>No repositories indexed yet — ingest one from Projects</span>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-900/90 border border-zinc-800 focus-within:border-zinc-600">
        <FolderGit2 className="w-3.5 h-3.5 text-blue-400 shrink-0" />
        <span className="text-zinc-500 font-medium font-mono text-[11px]">KB Space:</span>
        <div className="relative flex items-center">
          <select
            value={selectedRepo}
            onChange={(e) => setSelectedRepo(e.target.value)}
            aria-label="Target Repo"
            className="bg-transparent text-zinc-100 font-mono font-semibold focus:outline-none cursor-pointer pr-4 appearance-none text-xs"
          >
            {indexedRepos.map((repo) => (
              <option key={repo} value={repo} className="bg-zinc-900 text-zinc-200">
                {repo}
              </option>
            ))}
          </select>
          <ChevronDown className="w-3 h-3 text-zinc-500 absolute right-0 pointer-events-none" />
        </div>
      </div>

      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-900/90 border border-zinc-800 focus-within:border-zinc-600">
        <GitBranch className="w-3.5 h-3.5 text-blue-400 shrink-0" />
        <span className="text-zinc-500 font-medium font-mono text-[11px]">Branch:</span>
        <input
          type="text"
          value={selectedBranch}
          onChange={(e) => setSelectedBranch(e.target.value)}
          placeholder="main"
          aria-label="Branch"
          className="w-20 bg-transparent text-zinc-100 font-mono font-semibold focus:outline-none text-xs placeholder-zinc-600"
        />
      </div>
    </div>
  );
};
