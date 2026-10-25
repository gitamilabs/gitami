"use client";

import React, { useState, useEffect, useMemo } from "react";
import { createPortal } from "react-dom";
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
  ChevronRight,
  ArrowLeft,
  ArrowRight,
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

interface DirectoryNode {
  name: string;
  fullPath: string;
  children: DirectoryNode[];
}

/**
 * Transforms a flat list of directory paths (e.g. ["apps", "apps/web", "apps/api"])
 * into a hierarchical tree structure for nested Vercel-style browsing.
 */
function buildDirectoryTree(paths: string[]): DirectoryNode[] {
  const rootNodes: DirectoryNode[] = [];

  for (const pathStr of paths) {
    const segments = pathStr.split("/").filter(Boolean);
    let currentLevel = rootNodes;
    let accumulatedPath = "";

    for (let i = 0; i < segments.length; i++) {
      const segment = segments[i];
      accumulatedPath = accumulatedPath ? `${accumulatedPath}/${segment}` : segment;

      let existingNode = currentLevel.find((n) => n.name === segment);
      if (!existingNode) {
        existingNode = {
          name: segment,
          fullPath: accumulatedPath,
          children: [],
        };
        currentLevel.push(existingNode);
      }
      currentLevel = existingNode.children;
    }
  }

  const sortNodes = (nodes: DirectoryNode[]) => {
    nodes.sort((a, b) => a.name.localeCompare(b.name));
    for (const node of nodes) {
      sortNodes(node.children);
    }
  };
  sortNodes(rootNodes);

  return rootNodes;
}

/**
 * Checks if a node or any of its descendant nodes matches the search query.
 */
function nodeMatchesQuery(node: DirectoryNode, query: string): boolean {
  if (!query) return true;
  const q = query.toLowerCase();
  if (node.name.toLowerCase().includes(q) || node.fullPath.toLowerCase().includes(q)) {
    return true;
  }
  return node.children.some((child) => nodeMatchesQuery(child, query));
}


/**
 * Recursive Tree Node Component for hierarchical directory explorer.
 */
interface DirectoryTreeItemProps {
  node: DirectoryNode;
  depth: number;
  selectedPath: string;
  onSelect: (path: string) => void;
  expandedPaths: Set<string>;
  toggleExpand: (path: string) => void;
  filterQuery: string;
}

const DirectoryTreeItem: React.FC<DirectoryTreeItemProps> = ({
  node,
  depth,
  selectedPath,
  onSelect,
  expandedPaths,
  toggleExpand,
  filterQuery,
}) => {
  const hasChildren = node.children.length > 0;
  // If user searched, auto-expand matching ancestor branches; otherwise STRICTLY check expandedPaths
  const isExpanded = filterQuery.trim() ? true : expandedPaths.has(node.fullPath);
  const isSelected = selectedPath === node.fullPath;

  const matchingChildren = useMemo(
    () => node.children.filter((child) => nodeMatchesQuery(child, filterQuery)),
    [node.children, filterQuery]
  );

  return (
    <div className="divide-y divide-white/[0.06]">
      <div
        className={`group flex items-center justify-between py-2.5 px-3 transition-colors cursor-pointer text-xs select-none ${
          isSelected
            ? "bg-white/[0.08] text-white"
            : "hover:bg-white/[0.03] text-zinc-300 hover:text-white"
        }`}
        style={{ paddingLeft: `${depth * 20 + 12}px` }}
        onClick={() => onSelect(node.fullPath)}
      >
        <div className="flex items-center gap-2 min-w-0">
          {/* Expand / Collapse Chevron */}
          {hasChildren ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                toggleExpand(node.fullPath);
              }}
              className="w-4 h-4 flex items-center justify-center text-zinc-400 hover:text-white rounded transition-transform cursor-pointer shrink-0"
            >
              <ChevronRight
                className={`w-3.5 h-3.5 transition-transform duration-150 ${
                  isExpanded ? "rotate-90 text-white" : ""
                }`}
              />
            </button>
          ) : (
            <div className="w-4 h-4 shrink-0" />
          )}

          {/* Vercel-style Radio button */}
          <div className="shrink-0 flex items-center justify-center">
            {isSelected ? (
              <div className="w-4 h-4 rounded-full border-2 border-white flex items-center justify-center bg-transparent">
                <div className="w-1.5 h-1.5 rounded-full bg-white" />
              </div>
            ) : (
              <div className="w-4 h-4 rounded-full border border-zinc-600 group-hover:border-zinc-400 transition-colors" />
            )}
          </div>

          <span className="font-mono text-xs truncate font-medium">
            {node.name}
          </span>
        </div>
      </div>


      {/* Render child folders ONLY when parent is expanded */}
      {hasChildren && isExpanded && (
        <div className="relative divide-y divide-white/[0.06] bg-black/20">
          {/* Subtle vertical indentation tree guide */}
          <div
            className="absolute top-0 bottom-0 border-l border-white/[0.06]"
            style={{ left: `${depth * 20 + 20}px` }}
          />
          {matchingChildren.map((child) => (
            <DirectoryTreeItem
              key={child.fullPath}
              node={child}
              depth={depth + 1}
              selectedPath={selectedPath}
              onSelect={onSelect}
              expandedPaths={expandedPaths}
              toggleExpand={toggleExpand}
              filterQuery={filterQuery}
            />
          ))}
        </div>
      )}
    </div>
  );
};

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

  // Wizard state: "select" -> "configure"
  const [step, setStep] = useState<"select" | "configure">("select");
  const [selectedRepo, setSelectedRepo] = useState<ConnectedRepository | null>(null);

  // Configuration options
  const [rootDirectory, setRootDirectory] = useState("");
  const [targetBranch, setTargetBranch] = useState("main");
  const [directories, setDirectories] = useState<string[]>([]);
  const [isLoadingDirs, setIsLoadingDirs] = useState(false);
  const [dirSearchQuery, setDirSearchQuery] = useState("");
  // ONLY top level folders are shown initially; sub-folders only show when opened
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [isCustomPathOpen, setIsCustomPathOpen] = useState(false);

  // Search & Filters in select step
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedOwner, setSelectedOwner] = useState<string>("all");
  const [installUrl, setInstallUrl] = useState<string | null>(null);
  const [isFetchingUrl, setIsFetchingUrl] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

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

  // Reset wizard when modal is closed
  useEffect(() => {
    if (!isOpen) {
      setStep("select");
      setSelectedRepo(null);
      setRootDirectory("");
      setDirSearchQuery("");
      setExpandedPaths(new Set());
      setIsCustomPathOpen(false);
      setError(null);
    }
  }, [isOpen]);

  // Build directory tree
  const directoryTree = useMemo(() => buildDirectoryTree(directories), [directories]);

  if (!isOpen || !mounted) return null;

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

  // Step 1 -> Step 2 transition: Select repository
  const handleSelectRepo = async (repo: ConnectedRepository) => {
    setSelectedRepo(repo);
    const branch = repo.defaultBranch || "main";
    setTargetBranch(branch);
    setRootDirectory("");
    setDirSearchQuery("");
    setExpandedPaths(new Set());
    setIsCustomPathOpen(false);
    setError(null);
    setStep("configure");

    if (token) {
      setIsLoadingDirs(true);
      try {
        const res = await githubApi.getRepositoryDirectories(token, repo.id, branch);
        setDirectories(res.directories || []);
      } catch (err) {
        console.warn("Could not load repo directories:", err);
        setDirectories([]);
      } finally {
        setIsLoadingDirs(false);
      }
    }
  };

  // Step 2: Final Connect & Build action
  const handleConnectAndBuild = async () => {
    if (!token || !selectedRepo) return;
    setIsConnecting(true);
    setError(null);

    try {
      // Attach repository specifically to current project with selected rootDirectory
      const cleanRoot =
        rootDirectory.trim() === "./" || rootDirectory.trim() === "."
          ? ""
          : rootDirectory.trim();

      await attachRepository(token, projectId, selectedRepo.id, cleanRoot);

      // Start build in background
      await startBuild(
        token,
        projectId,
        selectedRepo.id,
        targetBranch || selectedRepo.defaultBranch || "main"
      );

      setIsConnecting(false);
      onSuccess?.();
      onClose();

      // Redirect to live builds page
      router.push(`/${teamSlug}/${projectSlug}/builds`);
    } catch (err: any) {
      setError(err.message || "Failed to connect repository");
      setIsConnecting(false);
    }
  };

  const toggleExpand = (fullPath: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(fullPath)) {
        next.delete(fullPath);
      } else {
        next.add(fullPath);
      }
      return next;
    });
  };

  const filteredTree = directoryTree.filter((node) =>
    nodeMatchesQuery(node, dirSearchQuery)
  );

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs animate-fade-in"
      onClick={onClose}
    >

      <div
        className="bg-[#11131a] border border-white/[0.08] rounded-xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col max-h-[88vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06] shrink-0">
          <div className="flex items-center gap-2.5">
            {step === "configure" ? (
              <button
                onClick={() => setStep("select")}
                className="p-1.5 bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] rounded-lg text-zinc-300 hover:text-white transition-colors cursor-pointer"
                title="Back to repositories"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
            ) : (
              <div className="p-1.5 bg-white/[0.04] border border-white/[0.06] rounded-lg text-white">
                <Github className="w-4 h-4 text-white" />
              </div>
            )}
            <div>
              <h3 className="text-sm font-semibold text-white">
                {step === "configure" ? "Root Directory" : "Connect GitHub Repository"}
              </h3>
              <p className="text-[11px] text-zinc-400">
                {step === "configure"
                  ? `Select directory containing your source code`
                  : "Select a repository installed via the GitAmi GitHub App"}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-white p-1 rounded hover:bg-white/[0.05] transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Area */}
        <div className="p-5 overflow-y-auto flex-1 space-y-4">
          {error && (
            <div className="p-2.5 rounded-lg bg-red-950/40 border border-red-800/60 text-red-300 text-xs">
              {error}
            </div>
          )}

          {step === "select" ? (
            /* STEP 1: Select Repository */
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
                      <option value="all" className="bg-[#13151f] text-white">
                        All Organizations
                      </option>
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
                    const isAlreadyConnected = activeProject?.repositories?.some(
                      (r) =>
                        r.id === repo.id ||
                        r.fullName.toLowerCase() === repo.fullName.toLowerCase()
                    );

                    return (
                      <div
                        key={repo.id}
                        onClick={() => !isAlreadyConnected && handleSelectRepo(repo)}
                        className={`p-3.5 flex items-center justify-between transition-colors ${
                          isAlreadyConnected
                            ? "opacity-60 bg-transparent"
                            : "hover:bg-white/[0.03] cursor-pointer"
                        }`}
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
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSelectRepo(repo);
                            }}
                            className="px-3.5 py-1.5 rounded-md bg-white hover:bg-zinc-200 text-black text-xs font-semibold transition-colors shrink-0 cursor-pointer flex items-center gap-1.5"
                          >
                            <span>Import</span>
                            <ArrowRight className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          ) : (
            /* STEP 2: Root Directory Picker (Vercel-style) */
            selectedRepo && (
              <div className="space-y-4 animate-fade-in">
                {/* Header Info */}
                <div>
                  <h3 className="text-base font-semibold text-white">Root Directory</h3>
                  <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                    Select the directory containing your source code. For monorepos, select the subfolder containing your application.
                  </p>
                </div>

                {/* Repo Identifier row */}
                <div className="flex items-center gap-2 py-0.5 text-xs text-zinc-300 font-medium">
                  <Github className="w-4 h-4 text-white shrink-0" />
                  <span className="font-mono text-white font-semibold">{selectedRepo.name}</span>
                  {targetBranch && (
                    <span className="text-zinc-500 font-mono text-[11px] ml-auto flex items-center gap-1">
                      <GitBranch className="w-3 h-3 text-zinc-500" />
                      {targetBranch}
                    </span>
                  )}
                </div>

                {/* Optional Search bar if more than 6 directories */}
                {directories.length > 6 && (
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-2.5 pointer-events-none" />
                    <input
                      type="text"
                      placeholder="Filter directories..."
                      value={dirSearchQuery}
                      onChange={(e) => setDirSearchQuery(e.target.value)}
                      className="w-full pl-9 pr-3 py-1.5 bg-black/60 border border-white/[0.08] rounded-lg text-xs text-white placeholder-zinc-500 font-mono focus:outline-none focus:border-white/20 transition-colors"
                    />
                  </div>
                )}

                {/* Directory List Container */}
                <div className="border border-white/[0.1] rounded-xl bg-[#0c0d12] overflow-hidden divide-y divide-white/[0.06] shadow-xl">
                  {/* Root directory option: repo (root) */}
                  <div
                    onClick={() => setRootDirectory("")}
                    className={`group flex items-center justify-between py-2.5 px-3 transition-colors cursor-pointer text-xs select-none ${
                      !rootDirectory.trim()
                        ? "bg-white/[0.08] text-white"
                        : "hover:bg-white/[0.03] text-zinc-300 hover:text-white"
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      {/* Spacer aligning with chevrons */}
                      <div className="w-4 h-4 shrink-0" />
                      {/* Radio button */}
                      <div className="shrink-0 flex items-center justify-center">
                        {!rootDirectory.trim() ? (
                          <div className="w-4 h-4 rounded-full border-2 border-white flex items-center justify-center bg-transparent">
                            <div className="w-1.5 h-1.5 rounded-full bg-white" />
                          </div>
                        ) : (
                          <div className="w-4 h-4 rounded-full border border-zinc-600 group-hover:border-zinc-400 transition-colors" />
                        )}
                      </div>
                      <span className="font-mono text-xs truncate font-medium">
                        {selectedRepo.name} <span className="text-zinc-500 font-normal">(root)</span>
                      </span>
                    </div>
                  </div>


                  {/* Scrollable list of top-level folders */}
                  <div className="max-h-72 overflow-y-auto divide-y divide-white/[0.06]">
                    {isLoadingDirs ? (
                      <div className="p-8 text-center text-xs text-zinc-400 flex items-center justify-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-white" />
                        <span>Loading directories...</span>
                      </div>
                    ) : filteredTree.length === 0 ? (
                      dirSearchQuery ? (
                        <div className="p-6 text-center text-xs text-zinc-500">
                          No folders matching "{dirSearchQuery}".
                        </div>
                      ) : null
                    ) : (
                      filteredTree.map((node) => (
                        <DirectoryTreeItem
                          key={node.fullPath}
                          node={node}
                          depth={0}
                          selectedPath={rootDirectory}
                          onSelect={(path) => setRootDirectory(path)}
                          expandedPaths={expandedPaths}
                          toggleExpand={toggleExpand}
                          filterQuery={dirSearchQuery}
                        />
                      ))
                    )}
                  </div>
                </div>

                {/* Manual custom path option */}
                <div className="pt-0.5">
                  {!isCustomPathOpen ? (
                    <button
                      type="button"
                      onClick={() => setIsCustomPathOpen(true)}
                      className="text-[11px] text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer"
                    >
                      + Enter directory path manually
                    </button>
                  ) : (
                    <div className="flex items-center gap-2 animate-fade-in">
                      <div className="relative flex-1">
                        <span className="absolute left-3 top-2 text-zinc-500 text-xs font-mono">/</span>
                        <input
                          type="text"
                          placeholder="Custom directory (e.g. backend/services)"
                          value={rootDirectory}
                          onChange={(e) => setRootDirectory(e.target.value)}
                          className="w-full pl-7 pr-3 py-1.5 bg-black/60 border border-white/[0.1] rounded-lg text-xs text-white placeholder-zinc-500 font-mono focus:outline-none focus:border-white/20"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => setIsCustomPathOpen(false)}
                        className="text-xs text-zinc-500 hover:text-zinc-300 px-2 py-1 cursor-pointer"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )
          )}
        </div>

        {/* Modal Footer (for Step 2: Configure) */}
        {step === "configure" && (
          <div className="px-5 py-3.5 border-t border-white/[0.06] bg-[#0c0d12] flex items-center justify-between shrink-0">
            <button
              type="button"
              onClick={() => setStep("select")}
              className="px-4 py-2 rounded-lg text-xs font-medium text-zinc-300 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] transition-colors cursor-pointer"
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={handleConnectAndBuild}
              disabled={isConnecting}
              className="flex items-center gap-2 px-6 py-2 bg-white hover:bg-zinc-200 text-black rounded-lg text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer shadow-lg shadow-white/5"
            >
              {isConnecting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Connecting...</span>
                </>
              ) : (
                <span>Continue</span>
              )}
            </button>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
};
