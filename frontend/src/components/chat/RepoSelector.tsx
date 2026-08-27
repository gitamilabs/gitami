"use client";

import React, { useEffect } from "react";
import { useRepoStore } from "../../store/repoStore";
import { useChatStore } from "../../store/chatStore";
import { GitBranch, FolderGit2, ChevronDown } from "lucide-react";

export const RepoSelector: React.FC = () => {
  const { indexedRepos, fetchIndexedRepos } = useRepoStore();
  const { selectedRepo, selectedBranch, setSelectedRepo, setSelectedBranch } = useChatStore();

  useEffect(() => {
    fetchIndexedRepos();
  }, [fetchIndexedRepos]);

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-800 focus-within:border-indigo-500/60 shadow-inner">
        <FolderGit2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
        <span className="text-slate-400 font-medium font-mono text-[11px]">KB Space:</span>
        <div className="relative flex items-center">
          <select
            value={selectedRepo}
            onChange={(e) => setSelectedRepo(e.target.value)}
            aria-label="Target Repo"
            className="bg-transparent text-slate-100 font-mono font-bold focus:outline-none cursor-pointer pr-4 appearance-none text-xs"
          >
            {indexedRepos.map((repo) => (
              <option key={repo} value={repo} className="bg-slate-900 text-slate-200">
                {repo}
              </option>
            ))}
            {/* Custom option fallback */}
            {!indexedRepos.includes(selectedRepo) && (
              <option value={selectedRepo} className="bg-slate-900 text-slate-200">
                {selectedRepo} (Custom)
              </option>
            )}
          </select>
          <ChevronDown className="w-3 h-3 text-slate-400 absolute right-0 pointer-events-none" />
        </div>
      </div>

      <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-800 focus-within:border-cyan-500/60 shadow-inner">
        <GitBranch className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
        <span className="text-slate-400 font-medium font-mono text-[11px]">Branch:</span>
        <input
          type="text"
          value={selectedBranch}
          onChange={(e) => setSelectedBranch(e.target.value)}
          placeholder="main"
          aria-label="Branch"
          className="w-20 bg-transparent text-slate-100 font-mono font-bold focus:outline-none text-xs placeholder-slate-600"
        />
      </div>
    </div>
  );
};

