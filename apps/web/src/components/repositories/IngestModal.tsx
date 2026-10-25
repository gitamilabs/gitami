"use client";

import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { ConnectedRepository } from "../../lib/types";
import { Button } from "../ui/Button";
import { useAuthStore } from "../../store/authStore";
import { useBuildStore } from "../../store/buildStore";
import { useProjectStore } from "../../store/projectStore";
import {
  Database,
  GitBranch,
  Lock,
  Globe,
  X,
  Hammer,
  Zap,
  CheckCircle2,
} from "lucide-react";

interface IngestModalProps {
  isOpen: boolean;
  repo: ConnectedRepository | null;
  onClose: () => void;
  onSuccess?: () => void;
}

export const IngestModal: React.FC<IngestModalProps> = ({
  isOpen,
  repo,
  onClose,
  onSuccess,
}) => {
  const { token } = useAuthStore();
  const { startBuild } = useBuildStore();
  const { getActiveProject } = useProjectStore();

  const [branch, setBranch] = useState<string>("main");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (repo) {
      setBranch(repo.defaultBranch || "main");
    }
  }, [repo, isOpen]);

  if (!isOpen || !repo || !mounted) return null;

  const handleStartIngestion = () => {
    if (!token) return;
    const activeProject = getActiveProject();
    if (!activeProject) return;

    // Trigger non-blocking build immediately
    startBuild(
      token,
      activeProject.id,
      repo.id,
      branch.trim() || repo.defaultBranch || "main"
    );

    // Close modal immediately so user is NOT blocked!
    onClose();
    if (onSuccess) onSuccess();
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs animate-fade-in"
      onClick={onClose}
    >
      <div
        className="bg-[#11131a] border border-white/[0.08] rounded-xl w-full max-w-lg shadow-2xl overflow-hidden relative flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-white/[0.06] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Hammer className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Index Repository Intelligence</h3>
              <p className="text-[11px] text-zinc-400">Trigger background knowledge graph & symbol parsing</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-4 text-xs">
          {/* Target Repo Info */}
          <div className="p-3 rounded-lg bg-[#0c0d12] border border-white/[0.06] space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-white text-sm">{repo.fullName}</span>
              <span className="flex items-center gap-1 text-[11px] text-zinc-400 font-mono">
                {repo.isPrivate ? <Lock className="w-3 h-3 text-amber-400" /> : <Globe className="w-3 h-3 text-zinc-400" />}
                {repo.isPrivate ? "Private" : "Public"}
              </span>
            </div>
            <p className="text-[11px] text-zinc-400">
              Extracts functions, classes, cross-file imports, and generates vector embeddings.
            </p>
          </div>

          {/* Branch input */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-medium text-zinc-300 flex items-center gap-1.5 font-mono">
              <GitBranch className="w-3 h-3 text-zinc-400" /> Target Git Branch
            </label>
            <input
              type="text"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              placeholder="main"
              className="w-full px-3 py-2 bg-white/[0.03] border border-white/[0.08] rounded-lg text-xs font-mono text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-white/20"
            />
          </div>

          {/* Non-blocking guarantee callout */}
          <div className="p-3 rounded-lg bg-indigo-950/20 border border-indigo-500/20 text-indigo-300 space-y-1">
            <div className="flex items-center gap-2 font-semibold text-[11px]">
              <Zap className="w-3.5 h-3.5 text-indigo-400" />
              <span>Non-blocking Background Processing</span>
            </div>
            <p className="text-[11px] text-indigo-200/80 leading-relaxed">
              Indexing runs entirely in the background. You do not need to wait here—you can continue navigating freely across GitAmi while the build processes.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-white/[0.06] flex items-center justify-end gap-2 bg-[#0c0d12]">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" onClick={handleStartIngestion} className="gap-1.5">
            <Hammer className="w-3.5 h-3.5" />
            <span>Start Indexing Build</span>
          </Button>
        </div>
      </div>
    </div>,
    document.body
  );
};
