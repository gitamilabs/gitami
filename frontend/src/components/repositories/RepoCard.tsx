import React, { useState } from "react";
import { ConnectedRepository } from "../../lib/types";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { formatTimeAgo } from "../../lib/utils";
import {
  FolderGit2,
  GitBranch,
  Lock,
  Globe,
  Trash2,
  ExternalLink,
  Bot,
  Sparkles,
  CheckCircle2,
  RefreshCw,
  Database,
} from "lucide-react";
import Link from "next/link";

interface RepoCardProps {
  repo: ConnectedRepository;
  isIngested?: boolean;
  onDisconnect: (id: string) => Promise<void>;
  onIngest?: (repo: ConnectedRepository) => void;
}

export const RepoCard: React.FC<RepoCardProps> = ({
  repo,
  isIngested = false,
  onDisconnect,
  onIngest,
}) => {
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    if (!confirm(`Are you sure you want to disconnect ${repo.fullName}?`)) return;
    setIsDeleting(true);
    try {
      await onDisconnect(repo.id);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="glass-card glass-card-hover rounded-3xl p-5 sm:p-6 border border-slate-800 flex flex-col justify-between relative overflow-hidden group shadow-lg shadow-black/20">
      <div>
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="p-2.5 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 shrink-0 shadow-inner">
              <FolderGit2 className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-bold text-white truncate flex items-center gap-2">
                {repo.name}
                {repo.isPrivate ? (
                  <Badge variant="warning" size="sm" className="text-[10px]">
                    <Lock className="w-2.5 h-2.5" /> Private
                  </Badge>
                ) : (
                  <Badge variant="info" size="sm" className="text-[10px]">
                    <Globe className="w-2.5 h-2.5" /> Public
                  </Badge>
                )}
              </h3>
              <p className="text-xs text-slate-400 font-mono truncate">{repo.fullName}</p>
            </div>
          </div>

          <a
            href={repo.htmlUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Open on GitHub"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400 my-4">
          <span className="flex items-center gap-1.5 bg-slate-900/90 px-3 py-1 rounded-xl border border-slate-800 font-mono text-[11px] font-semibold text-slate-300">
            <GitBranch className="w-3.5 h-3.5 text-cyan-400" />
            {repo.defaultBranch}
          </span>

          {isIngested ? (
            <Badge variant="success" size="sm" dot className="font-mono text-[11px]">
              Ingested & Ready
            </Badge>
          ) : (
            <Badge variant="warning" size="sm" className="font-mono text-[11px]">
              Not Ingested
            </Badge>
          )}

          <span className="text-[11px] text-slate-500 font-mono">
            Connected {formatTimeAgo(repo.createdAt)}
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between gap-2.5 pt-4 border-t border-slate-800/80">
        {isIngested ? (
          <>
            <Link
              href={`/chat?repo=${encodeURIComponent(repo.name)}&branch=${encodeURIComponent(
                repo.defaultBranch
              )}`}
              className="flex-1"
            >
              <Button
                variant="glow"
                size="sm"
                leftIcon={<Bot className="w-3.5 h-3.5" />}
                className="w-full text-xs"
              >
                Chat with Codebase
              </Button>
            </Link>

            {onIngest && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onIngest(repo)}
                className="text-xs"
                title="Re-index Knowledge Base"
              >
                <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
              </Button>
            )}
          </>
        ) : (
          <Button
            variant="glow"
            size="sm"
            onClick={() => onIngest && onIngest(repo)}
            leftIcon={<Sparkles className="w-3.5 h-3.5" />}
            className="flex-1 text-xs"
          >
            Ingest Knowledge Base
          </Button>
        )}

        <Button
          variant="danger"
          size="sm"
          onClick={handleDelete}
          isLoading={isDeleting}
          className="text-xs"
          title="Disconnect Repository"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
};


