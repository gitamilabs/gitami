"use client";

import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import {
  X,
  FolderGit2,
  Loader2,
  CheckCircle2,
  ExternalLink,
  Github,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { useRepoStore } from "../../store/repoStore";

interface AddProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export const AddProjectModal: React.FC<AddProjectModalProps> = ({
  isOpen,
  onClose,
}) => {
  const { token } = useAuthStore();
  const { getInstallUrl } = useRepoStore();

  const [installUrl, setInstallUrl] = useState<string | null>(null);
  const [isFetchingUrl, setIsFetchingUrl] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (isOpen && token) {
      setIsFetchingUrl(true);
      getInstallUrl(token)
        .then((url) => setInstallUrl(url))
        .catch((e) => console.warn("Could not fetch GitHub install URL:", e))
        .finally(() => setIsFetchingUrl(false));
    }
  }, [isOpen, token, getInstallUrl]);

  if (!isOpen || !mounted) return null;

  const handleGitHubConnect = () => {
    if (installUrl) {
      window.location.href = installUrl;
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/75 backdrop-blur-xs animate-fade-in"
      onClick={onClose}
    >
      <div
        className="bg-[#11131a] border border-white/[0.08] rounded-xl w-full max-w-lg shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-white/[0.04] border border-white/[0.06] rounded-lg text-white">
              <FolderGit2 className="w-4 h-4 text-blue-400" />
            </div>
            <h3 className="text-sm font-semibold text-white">Connect GitHub Repository</h3>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-white p-1 rounded-md hover:bg-white/[0.06] transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-4">
          <div className="rounded-lg bg-[#0c0d12] border border-white/[0.06] p-4 space-y-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-white shrink-0">
                <Github className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-white">Install the GitAmi GitHub App</h4>
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
                <span>Choose all repositories or select specific repositories</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <span>Secure access token refresh managed via GitHub App</span>
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
      </div>
    </div>,
    document.body
  );
};
