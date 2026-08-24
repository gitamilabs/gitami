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
    <div className="glass-card glass-card-hover rounded-2xl p-5 border border-slate-800 flex flex-col justify-between relative overflow-hidden group">
      <div>
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 shrink-0">
              <FolderGit2 className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-bold text-slate-100 truncate flex items-center gap-2">
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
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
            title="Open on GitHub"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400 my-4">
          <span className="flex items-center gap-1 bg-slate-900 px-2.5 py-1 rounded-lg border border-slate-800 font-mono">
            <GitBranch className="w-3.5 h-3.5 text-cyan-400" />
            {repo.defaultBranch}
          </span>

          {isIngested ? (
            <span className="flex items-center gap-1 bg-emerald-950/40 text-emerald-300 border border-emerald-500/30 px-2.5 py-1 rounded-lg font-mono text-[11px]">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              Ingested & Ready
            </span>
          ) : (
            <span className="flex items-center gap-1 bg-amber-950/40 text-amber-300 border border-amber-500/30 px-2.5 py-1 rounded-lg font-mono text-[11px]">
              <Sparkles className="w-3 h-3 text-amber-400" />
              Not Ingested
            </span>
          )}

          <span className="text-[11px] text-slate-500">
            Connected {formatTimeAgo(repo.createdAt)}
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between gap-2 pt-4 border-t border-slate-800/80">
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

