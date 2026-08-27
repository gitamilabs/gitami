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
  Copy,
  Check,
} from "lucide-react";

interface ToolStepAccordionProps {
  step: ToolStep;
}

export const ToolStepAccordion: React.FC<ToolStepAccordionProps> = ({ step }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [copiedArgs, setCopiedArgs] = useState(false);
  const [copiedOutput, setCopiedOutput] = useState(false);
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

  const handleCopyArgs = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(JSON.stringify(step.args, null, 2));
    setCopiedArgs(true);
    setTimeout(() => setCopiedArgs(false), 2000);
  };

  const handleCopyOutput = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(
      typeof step.raw_output === "string"
        ? step.raw_output
        : JSON.stringify(step.raw_output, null, 2)
    );
    setCopiedOutput(true);
    setTimeout(() => setCopiedOutput(false), 2000);
  };

  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 overflow-hidden transition-all my-1.5 shadow-sm">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-3 text-left hover:bg-slate-800/50 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="p-1.5 rounded-xl bg-slate-800/90 border border-slate-700/60 shrink-0 shadow-inner">
            {getToolIcon(step.tool_name)}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-200 truncate">
                {step.title || step.tool_name}
              </span>
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-semibold border ${badgeStyle.bg} ${badgeStyle.text} ${badgeStyle.border}`}
              >
                {step.tool_name}
              </span>
            </div>
            {step.summary && (
              <p className="text-[11px] text-slate-400 truncate mt-0.5 max-w-md font-mono">
                {step.summary}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2.5 shrink-0 ml-2">
          {step.status === "running" ? (
            <div className="flex items-center gap-1.5 text-[11px] text-indigo-400 font-mono">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>executing</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-[11px] text-slate-400 font-mono">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span className="flex items-center gap-1 text-slate-400">
                <Clock className="w-2.5 h-2.5 text-amber-400" />
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
        <div className="p-3.5 border-t border-slate-800 bg-slate-950/90 text-xs space-y-3 font-mono animate-fade-in">
          {step.args && Object.keys(step.args).length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <p className="text-[10px] font-bold uppercase text-slate-400">
                  Input Parameters
                </p>
                <button
                  onClick={handleCopyArgs}
                  className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-slate-200"
                >
                  {copiedArgs ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedArgs ? "Copied" : "Copy"}</span>
                </button>
              </div>
              <pre className="p-2.5 rounded-xl bg-slate-900/90 border border-slate-800 font-mono text-[11px] text-indigo-300 overflow-x-auto">
                {JSON.stringify(step.args, null, 2)}
              </pre>
            </div>
          )}

          {step.raw_output && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <p className="text-[10px] font-bold uppercase text-slate-400">
                  Knowledge Base Tool Output
                </p>
                <button
                  onClick={handleCopyOutput}
                  className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-slate-200"
                >
                  {copiedOutput ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedOutput ? "Copied" : "Copy"}</span>
                </button>
              </div>
              <pre className="p-2.5 rounded-xl bg-slate-900/90 border border-slate-800 font-mono text-[11px] text-slate-300 overflow-x-auto max-h-60">
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

