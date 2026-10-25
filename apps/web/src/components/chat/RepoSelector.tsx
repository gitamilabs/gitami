"use client";

import React, { useEffect, useMemo } from "react";
import { useRepoStore } from "../../store/repoStore";
import { useChatStore } from "../../store/chatStore";
import { useProjectStore } from "../../store/projectStore";
import { useAuthStore } from "../../store/authStore";
import { FolderGit2, ChevronDown, Folder } from "lucide-react";

export const RepoSelector: React.FC = () => {
  const { token } = useAuthStore();
  const { indexedRepos, fetchIndexedRepos } = useRepoStore();
  const { getActiveProject } = useProjectStore();
  const activeProject = getActiveProject();

  const {
    selectedRepo,
    selectedBranch,
    rootDirectory,
    setSelectedRepo,
    setSelectedBranch,
    setRootDirectory,
  } = useChatStore();

  useEffect(() => {
    if (token) fetchIndexedRepos(token);
  }, [token, fetchIndexedRepos]);

  const projectRepos = useMemo(() => {
    return activeProject?.repositories || [];
  }, [activeProject]);

  // Auto-bind to the active project's repositories if available
  useEffect(() => {
    if (projectRepos.length > 0) {
      const match = projectRepos.find(
        (r) => r.fullName === selectedRepo || r.name === selectedRepo || r.id === selectedRepo
      );
      if (!match) {
        const first = projectRepos[0];
        const repoName = first.fullName || first.name;
        setSelectedRepo(repoName);
        setSelectedBranch(first.defaultBranch || "main");
        setRootDirectory(first.rootDirectory || null);
      } else if (match.rootDirectory !== rootDirectory) {
        setRootDirectory(match.rootDirectory || null);
      }
    } else if (indexedRepos.length > 0 && !selectedRepo) {
      setSelectedRepo(indexedRepos[0]);
    }
  }, [projectRepos, indexedRepos, selectedRepo, rootDirectory, setSelectedRepo, setSelectedBranch, setRootDirectory]);

  const handleRepoChange = (val: string) => {
    setSelectedRepo(val);
    const match = projectRepos.find((r) => r.fullName === val || r.name === val || r.id === val);
    if (match) {
      setSelectedBranch(match.defaultBranch || "main");
      setRootDirectory(match.rootDirectory || null);
    }
  };

  const hasRepos = projectRepos.length > 0 || indexedRepos.length > 0;

  if (!hasRepos) {
    return (
      <div className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-white/[0.03] border border-white/[0.06] text-xs text-zinc-500">
        <FolderGit2 className="w-3.5 h-3.5 shrink-0" />
        <span>No repositories connected</span>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      {/* Repository Selector */}
      <div className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-white/[0.03] border border-white/[0.06] hover:border-white/10 transition-colors">
        <FolderGit2 className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
        <div className="relative flex items-center">
          <select
            value={selectedRepo}
            onChange={(e) => handleRepoChange(e.target.value)}
            aria-label="Target Repository"
            className="bg-transparent text-zinc-200 font-medium focus:outline-none cursor-pointer pr-4 appearance-none text-xs"
          >
            {projectRepos.length > 0
              ? projectRepos.map((repo) => {
                  const key = repo.fullName || repo.name;
                  return (
                    <option key={repo.id} value={key} className="bg-[#12131a] text-zinc-200">
                      {repo.name || repo.fullName}
                      {repo.rootDirectory ? ` (${repo.rootDirectory})` : ""}
                    </option>
                  );
                })
              : indexedRepos.map((repo) => (
                  <option key={repo} value={repo} className="bg-[#12131a] text-zinc-200">
                    {repo}
                  </option>
                ))}
          </select>
          <ChevronDown className="w-3 h-3 text-zinc-500 absolute right-0 pointer-events-none" />
        </div>
      </div>

      {/* Scoped Subfolder Badge (if configured) */}
      {rootDirectory && (
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-white/[0.03] border border-white/[0.06] text-zinc-400 text-[11px] font-mono">
          <Folder className="w-3 h-3 text-zinc-500 shrink-0" />
          <span>{rootDirectory}</span>
        </div>
      )}
    </div>
  );
};
