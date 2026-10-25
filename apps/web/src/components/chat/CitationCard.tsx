"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Citation } from "../../lib/types";
import { Database, Share2, Copy, Check, ChevronDown, ChevronRight, ArrowUpRight } from "lucide-react";

interface CitationCardProps {
  citation: Citation;
  teamSlug?: string;
  projectSlug?: string;
  repoId?: string;
}

export const CitationCard: React.FC<CitationCardProps> = ({
  citation,
  teamSlug,
  projectSlug,
  repoId,
}) => {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(citation.snippet || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const graphUrl =
    teamSlug && projectSlug
      ? `/${teamSlug}/${projectSlug}/graph?repo=${encodeURIComponent(
          repoId || ""
        )}&file=${encodeURIComponent(citation.file_path)}`
      : null;

  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#0c0d12] p-3 hover:border-white/[0.12] transition-all text-xs shadow-sm">
      <div
        className="flex items-center justify-between cursor-pointer select-none"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="w-5 h-5 rounded-md bg-white/[0.06] border border-white/[0.08] text-zinc-300 flex items-center justify-center font-mono font-semibold text-[10px] shrink-0">
            {citation.id}
          </span>
          <div className="flex items-center gap-1.5 min-w-0">
            {citation.source_type === "vector" ? (
              <Database className="w-3.5 h-3.5 text-blue-400 shrink-0" />
            ) : (
              <Share2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
            )}
            <span className="font-mono text-zinc-200 font-medium truncate">
              {citation.file_path}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {citation.lines && (
            <span className="text-[10px] font-mono text-zinc-400 bg-white/[0.04] border border-white/[0.06] px-1.5 py-0.5 rounded">
              L{citation.lines}
            </span>
          )}
          {citation.symbol && (
            <span className="text-[10px] font-mono text-zinc-300 bg-white/[0.04] border border-white/[0.06] px-1.5 py-0.5 rounded truncate max-w-[130px]">
              {citation.symbol}
            </span>
          )}
          {graphUrl && (
            <Link
              href={graphUrl}
              onClick={(e) => e.stopPropagation()}
              className="p-1 rounded text-zinc-500 hover:text-white hover:bg-white/[0.06] transition-colors"
              title="Locate in Knowledge Graph"
            >
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          )}
          <button
            type="button"
            onClick={handleCopy}
            className="p-1 rounded text-zinc-500 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
            title="Copy snippet"
          >
            {copied ? (
              <Check className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <Copy className="w-3.5 h-3.5" />
            )}
          </button>
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />
          )}
        </div>
      </div>

      {citation.snippet && (
        <div className={`mt-2.5 ${expanded ? "block animate-fade-in" : "line-clamp-2 opacity-80"}`}>
          <pre className="p-2.5 rounded-lg bg-black/40 border border-white/[0.04] font-mono text-[11px] text-zinc-300 overflow-x-auto whitespace-pre-wrap leading-relaxed">
            {citation.snippet}
          </pre>
        </div>
      )}
    </div>
  );
};
