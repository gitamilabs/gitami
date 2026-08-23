"use client";

import React, { useState } from "react";
import { ToolStep } from "../../lib/types";
import { getToolBadgeStyle, formatLatency } from "../../lib/utils";
import {
  ChevronDown,
  ChevronRight,
  Database,
  Share2,
  AlertTriangle,
  FileCode,
  Search,
  CheckCircle2,
  Loader2,
  Clock,
  Sparkles,
} from "lucide-react";

interface ToolStepAccordionProps {
  step: ToolStep;
}

export const ToolStepAccordion: React.FC<ToolStepAccordionProps> = ({ step }) => {
  const [isOpen, setIsOpen] = useState(false);
  const badgeStyle = getToolBadgeStyle(step.tool_name);

  const getToolIcon = (name: string) => {
    switch (name) {
      case "hybrid_search":
        return <Sparkles className="w-3.5 h-3.5 text-indigo-400" />;
      case "vector_search":
        return <Database className="w-3.5 h-3.5 text-cyan-400" />;
      case "get_blast_radius":
        return <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />;
      case "get_symbol_details":
        return <Share2 className="w-3.5 h-3.5 text-purple-400" />;
      case "get_file_dependencies":
        return <FileCode className="w-3.5 h-3.5 text-emerald-400" />;
      case "get_repo_structure":
        return <FileCode className="w-3.5 h-3.5 text-amber-400" />;
      default:
        return <Search className="w-3.5 h-3.5 text-slate-400" />;
    }
  };

  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 overflow-hidden transition-all my-1.5">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-2.5 text-left hover:bg-slate-800/40 transition-colors"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="p-1 rounded-lg bg-slate-800 border border-slate-700/60 shrink-0">
            {getToolIcon(step.tool_name)}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-200 truncate">
                {step.title || step.tool_name}
              </span>
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded font-mono border ${badgeStyle.bg} ${badgeStyle.text} ${badgeStyle.border}`}
              >
                {step.tool_name}
              </span>
            </div>
            {step.summary && (
              <p className="text-[11px] text-slate-400 truncate mt-0.5 max-w-md">
                {step.summary}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0 ml-2">
          {step.status === "running" ? (
            <div className="flex items-center gap-1 text-[11px] text-indigo-400 font-mono">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>executing</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-[11px] text-slate-400 font-mono">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span className="flex items-center gap-0.5 text-slate-500">
                <Clock className="w-2.5 h-2.5" />
                {formatLatency(step.latency_ms || 0)}
              </span>
            </div>
          )}
          {isOpen ? (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-slate-400" />
          )}
        </div>
      </button>

      {isOpen && (
        <div className="p-3 border-t border-slate-800 bg-slate-950/80 text-xs space-y-2.5">
          {step.args && Object.keys(step.args).length > 0 && (
            <div>
              <p className="text-[10px] font-semibold uppercase text-slate-400 font-mono mb-1">
                Input Parameters:
              </p>
              <pre className="p-2 rounded-lg bg-slate-900 border border-slate-800 font-mono text-[11px] text-indigo-300 overflow-x-auto">
                {JSON.stringify(step.args, null, 2)}
              </pre>
            </div>
          )}

          {step.raw_output && (
            <div>
              <p className="text-[10px] font-semibold uppercase text-slate-400 font-mono mb-1">
                Knowledge Base Tool Output:
              </p>
              <pre className="p-2 rounded-lg bg-slate-900 border border-slate-800 font-mono text-[11px] text-slate-300 overflow-x-auto max-h-56">
                {typeof step.raw_output === "string"
                  ? step.raw_output
                  : JSON.stringify(step.raw_output, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
