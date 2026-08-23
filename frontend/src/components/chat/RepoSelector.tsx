"use client";

import React, { useEffect } from "react";
import { useRepoStore } from "../../store/repoStore";
import { useChatStore } from "../../store/chatStore";
import { GitBranch, FolderGit2, Check, Sparkles } from "lucide-react";

export const RepoSelector: React.FC = () => {
  const { indexedRepos, fetchIndexedRepos } = useRepoStore();
  const { selectedRepo, selectedBranch, setSelectedRepo, setSelectedBranch } = useChatStore();

  useEffect(() => {
    fetchIndexedRepos();
  }, [fetchIndexedRepos]);

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800">
        <FolderGit2 className="w-3.5 h-3.5 text-indigo-400" />
        <span className="text-slate-400 font-medium">Target Repo:</span>
        <select
          value={selectedRepo}
          onChange={(e) => setSelectedRepo(e.target.value)}
          aria-label="Target Repo"
          className="bg-transparent text-slate-200 font-mono font-semibold focus:outline-none cursor-pointer"
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
      </div>

      <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800">
        <GitBranch className="w-3.5 h-3.5 text-cyan-400" />
        <span className="text-slate-400 font-medium">Branch:</span>
        <input
          type="text"
          value={selectedBranch}
          onChange={(e) => setSelectedBranch(e.target.value)}
          placeholder="main"
          aria-label="Branch"
          className="w-20 bg-transparent text-slate-200 font-mono font-semibold focus:outline-none"
        />
      </div>
    </div>
  );
};
