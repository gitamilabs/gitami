"use client";

import React, { useState } from "react";
import { Citation } from "../../lib/types";
import { Database, Share2, Copy, Check, ChevronDown, ChevronRight, FileCode } from "lucide-react";

interface CitationCardProps {
  citation: Citation;
}

export const CitationCard: React.FC<CitationCardProps> = ({ citation }) => {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(citation.snippet || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3.5 hover:border-slate-700 transition-all text-xs shadow-sm">
      <div
        className="flex items-center justify-between cursor-pointer select-none"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="w-5 h-5 rounded-lg bg-indigo-600/20 border border-indigo-500/40 text-indigo-300 flex items-center justify-center font-mono font-bold text-[10px] shrink-0 shadow-sm">
            {citation.id}
          </span>
          <div className="flex items-center gap-1.5 min-w-0">
            {citation.source_type === "vector" ? (
              <Database className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
            ) : (
              <Share2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
            )}
            <span className="font-mono text-slate-200 font-semibold truncate">
              {citation.file_path}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {citation.lines && (
            <span className="text-[10px] font-mono text-slate-400 bg-slate-800/90 border border-slate-700/60 px-2 py-0.5 rounded-md">
              L{citation.lines}
            </span>
          )}
          {citation.symbol && (
            <span className="text-[10px] font-mono text-indigo-300 bg-indigo-950/60 border border-indigo-800/50 px-2 py-0.5 rounded-md truncate max-w-[140px] font-semibold">
              {citation.symbol}
            </span>
          )}
          <button
            onClick={handleCopy}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Copy snippet"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
          )}
        </div>
      </div>

      {citation.snippet && (
        <div className={`mt-2.5 ${expanded ? "block animate-fade-in" : "line-clamp-2 opacity-80"}`}>
          <pre className="p-3 rounded-xl bg-slate-950/90 border border-slate-800 font-mono text-[11px] text-slate-300 overflow-x-auto whitespace-pre-wrap leading-relaxed">
            {citation.snippet}
          </pre>
        </div>
      )}
    </div>
  );
};

