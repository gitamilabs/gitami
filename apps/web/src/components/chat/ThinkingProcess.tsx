"use client";

import React, { useState, useMemo } from "react";
import { ToolStep } from "../../lib/types";
import { ReasoningItem } from "../../store/chatStore";
import {
  Sparkles,
  ChevronDown,
  ChevronRight,
  Database,
  Share2,
  AlertTriangle,
  FileCode,
  Search,
  Loader2,
  Copy,
  Check,
} from "lucide-react";

interface ThinkingProcessProps {
  thoughts?: string[];
  toolSteps?: ToolStep[];
  reasoningTimeline?: ReasoningItem[];
  isStreaming?: boolean;
  latencyMs?: number;
}

export const ThinkingProcess: React.FC<ThinkingProcessProps> = ({
  thoughts = [],
  toolSteps = [],
  reasoningTimeline = [],
  isStreaming = false,
  latencyMs = 0,
}) => {
  // During streaming, default open so user sees sequential progress; once completed, default closed
  const [isOpen, setIsOpen] = useState(isStreaming);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Build unified sequential pipeline of steps
  const sequentialItems: ReasoningItem[] = useMemo(() => {
    if (reasoningTimeline && reasoningTimeline.length > 0) {
      return reasoningTimeline;
    }

    const items: ReasoningItem[] = [];
    const maxLen = Math.max(thoughts.length, toolSteps.length);
    for (let i = 0; i < maxLen; i++) {
      if (i < thoughts.length && thoughts[i]?.trim()) {
        items.push({
          id: `thought-${i}`,
          type: "thought",
          text: thoughts[i],
          stepIndex: i + 1,
        });
      }
      if (i < toolSteps.length && toolSteps[i]) {
        items.push({
          id: toolSteps[i].id || `tool-${i}`,
          type: "tool",
          toolStep: toolSteps[i],
          status: toolSteps[i].status,
          latencyMs: toolSteps[i].latency_ms,
          stepIndex: toolSteps[i].step_index || i + 1,
        });
      }
    }
    return items;
  }, [reasoningTimeline, thoughts, toolSteps]);

  const hasContent = sequentialItems.length > 0 || isStreaming;
  if (!hasContent) return null;

  const getToolIcon = (name: string) => {
    switch (name) {
      case "hybrid_search":
        return <Sparkles className="w-3 h-3 text-indigo-400" />;
      case "vector_search":
        return <Database className="w-3 h-3 text-cyan-400" />;
      case "get_blast_radius":
        return <AlertTriangle className="w-3 h-3 text-rose-400" />;
      case "get_symbol_details":
        return <Share2 className="w-3 h-3 text-purple-400" />;
      case "get_file_dependencies":
      case "get_repo_structure":
        return <FileCode className="w-3 h-3 text-emerald-400" />;
      default:
        return <Search className="w-3 h-3 text-zinc-400" />;
    }
  };

  const handleCopy = (id: string, text: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const formatSeconds = (ms: number) => {
    if (ms <= 0) return "";
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const toggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="my-2.5 rounded-xl border border-white/[0.05] bg-white/[0.015] backdrop-blur-sm transition-all overflow-hidden">
      {/* Sleek single-line header summary */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-white/[0.02] text-left transition-colors cursor-pointer select-none"
      >
        <div className="flex items-center gap-2 min-w-0">
          {isStreaming ? (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
            </span>
          ) : (
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-500" />
          )}

          <span className="text-xs font-mono font-medium text-zinc-300">
            {isStreaming ? (
              <span className="inline-flex items-center gap-1.5 text-blue-400">
                <span>Reasoning & inspecting codebase...</span>
                <Loader2 className="w-3 h-3 animate-spin inline" />
              </span>
            ) : latencyMs > 0 ? (
              <span>Thought for {formatSeconds(latencyMs)}</span>
            ) : (
              <span>Reasoning trace</span>
            )}
          </span>

          <span className="text-[10px] text-zinc-500 font-mono">
            • {sequentialItems.length} {sequentialItems.length === 1 ? "step" : "steps"}
          </span>
        </div>

        <div className="flex items-center gap-1.5 text-zinc-500 shrink-0">
          {isOpen ? (
            <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-zinc-400" />
          )}
        </div>
      </button>

      {/* Sequential, single-line connected dots timeline */}
      {isOpen && (
        <div className="px-3 pb-3 pt-1 border-t border-white/[0.04] animate-fade-in">
          <div className="relative pl-4 ml-2 border-l border-white/10 space-y-2 py-1.5">
            {sequentialItems.map((item) => {
              const isItemExpanded = expandedId === item.id;
              const isThought = item.type === "thought";
              const tool = item.toolStep;
              const isRunning = item.status === "running" || tool?.status === "running";

              return (
                <div key={item.id} className="relative group">
                  {/* Connected Dot on vertical line */}
                  <div className="absolute -left-[21px] top-1.5 flex items-center justify-center">
                    {isRunning ? (
                      <span className="relative flex h-2.5 w-2.5">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-blue-500 ring-2 ring-blue-500/20" />
                      </span>
                    ) : isThought ? (
                      <span className="w-2 h-2 rounded-full bg-indigo-400/80 border border-indigo-300/40" />
                    ) : item.status === "failed" ? (
                      <span className="w-2 h-2 rounded-full bg-rose-400/80 border border-rose-300/40" />
                    ) : (
                      <span className="w-2 h-2 rounded-full bg-emerald-400/80 border border-emerald-300/40" />
                    )}
                  </div>

                  {/* Single Line Content */}
                  {isThought ? (
                    <div>
                      <div
                        onClick={() => toggleExpand(item.id)}
                        className="flex items-center gap-2 text-[11px] text-zinc-400 hover:text-zinc-200 cursor-pointer select-none transition-colors py-0.5"
                      >
                        <span className="text-[10px] font-mono text-zinc-500 font-semibold uppercase tracking-wider shrink-0">
                          Thought
                        </span>
                        <span className="truncate flex-1 font-sans text-zinc-300">
                          {item.text}
                        </span>
                        <span className="text-[9px] text-zinc-600 font-mono group-hover:text-zinc-400 shrink-0">
                          {isItemExpanded ? "hide" : "details"}
                        </span>
                      </div>

                      {/* Expanded thought text */}
                      {isItemExpanded && (
                        <div className="mt-1 p-2 rounded-lg bg-black/40 border border-white/[0.04] text-[11px] font-mono text-zinc-300 whitespace-pre-wrap leading-relaxed animate-fade-in">
                          {item.text}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div>
                      <div
                        onClick={() => toggleExpand(item.id)}
                        className="flex items-center justify-between gap-2 text-[11px] cursor-pointer select-none group/tool hover:text-zinc-200 transition-colors py-0.5"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="font-mono text-zinc-200 font-medium shrink-0 flex items-center gap-1.5">
                            {getToolIcon(tool?.tool_name || "")}
                            <span>{tool?.title || tool?.tool_name}</span>
                          </span>
                          {tool?.summary && (
                            <span className="text-[10px] text-zinc-500 truncate hidden sm:inline font-mono">
                              — {tool.summary}
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-2 text-[10px] font-mono text-zinc-500 shrink-0">
                          {isRunning ? (
                            <span className="text-blue-400 flex items-center gap-1">
                              <Loader2 className="w-2.5 h-2.5 animate-spin" />
                              <span>running</span>
                            </span>
                          ) : (
                            <span>{formatSeconds(item.latencyMs || tool?.latency_ms || 0)}</span>
                          )}
                          <ChevronDown
                            className={`w-3 h-3 text-zinc-600 group-hover/tool:text-zinc-400 transition-transform ${
                              isItemExpanded ? "rotate-180" : ""
                            }`}
                          />
                        </div>
                      </div>

                      {/* Expanded tool details */}
                      {isItemExpanded && tool && (
                        <div className="mt-1.5 p-2.5 rounded-lg bg-black/50 border border-white/[0.05] space-y-2 text-[11px] font-mono animate-fade-in">
                          {tool.summary && (
                            <p className="text-zinc-400 text-xs font-sans pb-1 border-b border-white/[0.04]">
                              {tool.summary}
                            </p>
                          )}

                          {tool.args && Object.keys(tool.args).length > 0 && (
                            <div>
                              <div className="flex items-center justify-between text-zinc-500 text-[10px] pb-1">
                                <span>ARGUMENTS</span>
                                <button
                                  type="button"
                                  onClick={(e) =>
                                    handleCopy(`args-${tool.id}`, JSON.stringify(tool.args, null, 2), e)
                                  }
                                  className="hover:text-zinc-300 p-0.5 cursor-pointer"
                                >
                                  {copiedId === `args-${tool.id}` ? (
                                    <Check className="w-3 h-3 text-emerald-400" />
                                  ) : (
                                    <Copy className="w-3 h-3" />
                                  )}
                                </button>
                              </div>
                              <pre className="p-2 rounded bg-black/60 border border-white/[0.04] text-zinc-400 overflow-x-auto text-[10px]">
                                {JSON.stringify(tool.args, null, 2)}
                              </pre>
                            </div>
                          )}

                          {tool.raw_output && (
                            <div>
                              <div className="flex items-center justify-between text-zinc-500 text-[10px] pb-1">
                                <span>OUTPUT</span>
                                <button
                                  type="button"
                                  onClick={(e) =>
                                    handleCopy(
                                      `raw-${tool.id}`,
                                      typeof tool.raw_output === "string"
                                        ? tool.raw_output
                                        : JSON.stringify(tool.raw_output, null, 2),
                                      e
                                    )
                                  }
                                  className="hover:text-zinc-300 p-0.5 cursor-pointer"
                                >
                                  {copiedId === `raw-${tool.id}` ? (
                                    <Check className="w-3 h-3 text-emerald-400" />
                                  ) : (
                                    <Copy className="w-3 h-3" />
                                  )}
                                </button>
                              </div>
                              <pre className="p-2 rounded bg-black/60 border border-white/[0.04] text-zinc-400 overflow-x-auto text-[10px] max-h-48 overflow-y-auto">
                                {typeof tool.raw_output === "string"
                                  ? tool.raw_output
                                  : JSON.stringify(tool.raw_output, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
