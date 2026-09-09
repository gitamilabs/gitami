"use client";

import React, { useState } from "react";
import {
  Bug,
  ShieldAlert,
  AlertTriangle,
  FileCode,
  Sparkles,
  CheckCircle2,
  ExternalLink,
  Code2,
  Layers,
  Wrench,
} from "lucide-react";
import { PRIssueItem } from "@/lib/types";

interface PRIssueChecklistProps {
  issues: PRIssueItem[];
  onFixSelected: (selectedIds: string[]) => Promise<{ fixPrUrl?: string } | void>;
  isFixing?: boolean;
}

export const PRIssueChecklist: React.FC<PRIssueChecklistProps> = ({
  issues,
  onFixSelected,
  isFixing = false,
}) => {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [fixResultUrl, setFixResultUrl] = useState<string | null>(null);
  const [fixError, setFixError] = useState<string | null>(null);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const openIssues = issues.filter((i) => !i.isFixed);
  const fixedIssues = issues.filter((i) => i.isFixed);

  const handleSelectAll = () => {
    if (selectedIds.length === openIssues.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(openIssues.map((i) => i.id));
    }
  };

  const handleFixSubmit = async () => {
    if (selectedIds.length === 0 || isFixing) return;
    setFixError(null);
    setFixResultUrl(null);
    try {
      const res = await onFixSelected(selectedIds);
      if (res && res.fixPrUrl) {
        setFixResultUrl(res.fixPrUrl);
      }
      setSelectedIds([]);
    } catch (err: any) {
      setFixError(err.message || "Failed to generate AI Fix PR");
    }
  };

  const getCategoryBadge = (cat: string) => {
    switch (cat.toLowerCase()) {
      case "security":
        return {
          icon: <ShieldAlert className="w-3.5 h-3.5" />,
          label: "Security Vulnerability",
          color: "bg-rose-500/10 text-rose-400 border-rose-500/20",
        };
      case "bug":
        return {
          icon: <Bug className="w-3.5 h-3.5" />,
          label: "Bug / Defect",
          color: "bg-amber-500/10 text-amber-400 border-amber-500/20",
        };
      case "logical_error":
        return {
          icon: <Code2 className="w-3.5 h-3.5" />,
          label: "Logical Error",
          color: "bg-purple-500/10 text-purple-400 border-purple-500/20",
        };
      case "blast_radius":
        return {
          icon: <Layers className="w-3.5 h-3.5" />,
          label: "Blast Radius Risk",
          color: "bg-red-500/10 text-red-400 border-red-500/20",
        };
      default:
        return {
          icon: <FileCode className="w-3.5 h-3.5" />,
          label: cat.toUpperCase(),
          color: "bg-blue-500/10 text-blue-400 border-blue-500/20",
        };
    }
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev.toLowerCase()) {
      case "error":
      case "critical":
        return "bg-rose-500/20 text-rose-300 font-bold border-rose-500/40";
      case "warning":
        return "bg-amber-500/20 text-amber-300 font-semibold border-amber-500/40";
      default:
        return "bg-blue-500/20 text-blue-300 font-medium border-blue-500/40";
    }
  };

  if (issues.length === 0) {
    return (
      <div className="glass-panel border border-slate-800/80 rounded-xl p-8 text-center my-6">
        <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
        <h4 className="text-lg font-bold text-white">No Issues Detected</h4>
        <p className="text-xs text-slate-400 mt-1">
          The ReAct agent analyzed this PR and found no logical errors, bugs, or convention violations.
        </p>
      </div>
    );
  }

  return (
    <div className="glass-panel border border-slate-800/80 rounded-xl p-6 my-6 shadow-xl">
      {/* Action Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5 mb-5">
        <div>
          <div className="flex items-center gap-2">
            <Wrench className="w-5 h-5 text-indigo-400" />
            <h3 className="text-lg font-bold text-white tracking-tight">
              PR Issues & Vulnerabilities Checklist
            </h3>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-800 text-slate-300 border border-slate-700">
              {openIssues.length} Open
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Select issues below and click <span className="text-indigo-300 font-semibold">Fix using AI</span> to launch autonomous agents that push a fix PR to GitHub.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {openIssues.length > 0 && (
            <button
              onClick={handleSelectAll}
              className="text-xs font-mono text-slate-400 hover:text-slate-200 px-3 py-1.5 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-950/40 transition-all cursor-pointer"
            >
              {selectedIds.length === openIssues.length ? "Deselect All" : "Select All"}
            </button>
          )}

          <button
            onClick={handleFixSubmit}
            disabled={selectedIds.length === 0 || isFixing}
            className="px-5 py-2.5 bg-white hover:bg-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed text-black rounded-lg font-semibold text-xs flex items-center gap-2.5 transition-all cursor-pointer"
          >
            {isFixing ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Launching AI Fix Agent...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-black" />
                <span>
                  Fix {selectedIds.length > 0 ? `(${selectedIds.length})` : ""} Selected Issues using AI
                </span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Success Notification Alert */}
      {fixResultUrl && (
        <div className="mb-5 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center justify-between gap-3 animate-fade-in">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            <div>
              <p className="font-bold text-emerald-200">AI Fix Pull Request Successfully Raised!</p>
              <p className="text-emerald-400/80">The AI Agent created a fix branch and opened a PR on GitHub.</p>
            </div>
          </div>
          <a
            href={fixResultUrl}
            target="_blank"
            rel="noreferrer"
            className="px-3.5 py-1.5 bg-emerald-500 text-slate-950 hover:bg-emerald-400 font-bold rounded-lg flex items-center gap-1.5 shrink-0 shadow-lg"
          >
            <span>View Fix PR</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      )}

      {/* Error Notification Alert */}
      {fixError && (
        <div className="mb-5 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>Error launching AI Fix Agent: {fixError}</span>
        </div>
      )}

      {/* Issues List */}
      <div className="space-y-3.5">
        {issues.map((item) => {
          const isSelected = selectedIds.includes(item.id);
          const cat = getCategoryBadge(item.category);

          return (
            <div
              key={item.id}
              onClick={() => {
                if (!item.isFixed) toggleSelect(item.id);
              }}
              className={`group p-4 rounded-xl border transition-all duration-200 cursor-pointer ${
                item.isFixed
                  ? "bg-slate-950/40 border-slate-800/60 opacity-60 cursor-default"
                  : isSelected
                  ? "bg-indigo-950/40 border-indigo-500/80 shadow-lg shadow-indigo-500/10 ring-1 ring-indigo-500/50"
                  : "bg-slate-950/70 border-slate-800/80 hover:border-slate-700 hover:bg-slate-950"
              }`}
            >
              <div className="flex items-start gap-3.5">
                {/* Custom Checkbox */}
                {!item.isFixed && (
                  <div
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleSelect(item.id);
                    }}
                    className={`mt-1 w-4 h-4 rounded flex items-center justify-center border transition-all cursor-pointer ${
                      isSelected
                        ? "bg-indigo-600 border-indigo-500 text-white shadow-sm"
                        : "bg-slate-900 border-slate-700 hover:border-slate-500 text-transparent"
                    }`}
                  >
                    ✓
                  </div>
                )}

                {item.isFixed && (
                  <div className="mt-1 text-emerald-400 shrink-0">
                    <CheckCircle2 className="w-4 h-4" />
                  </div>
                )}

                <div className="flex-1 min-w-0">
                  {/* Category & Severity Badges */}
                  <div className="flex items-center gap-2 flex-wrap mb-1.5">
                    <span
                      className={`px-2.5 py-0.5 rounded-md text-[11px] font-semibold border flex items-center gap-1 ${cat.color}`}
                    >
                      {cat.icon}
                      {cat.label}
                    </span>

                    <span
                      className={`px-2 py-0.5 rounded text-[10px] uppercase tracking-wider border ${getSeverityBadge(
                        item.severity
                      )}`}
                    >
                      {item.severity}
                    </span>

                    <span className="text-[11px] font-mono text-slate-400 flex items-center gap-1">
                      <FileCode className="w-3.5 h-3.5 text-slate-500" />
                      {item.filePath}:{item.line}
                    </span>

                    {item.isFixed && (
                      <span className="ml-auto text-[11px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
                        Fixed via AI PR
                      </span>
                    )}
                  </div>

                  {/* Title & Description */}
                  <h4 className="text-sm font-bold text-slate-100 group-hover:text-white transition-colors">
                    {item.title}
                  </h4>
                  <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                    {item.description}
                  </p>

                  {/* Suggested Fix snippet */}
                  {item.suggestedFix && (
                    <div className="mt-2.5 p-3 rounded-lg bg-slate-900 border border-slate-800/80">
                      <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider block mb-1">
                        Suggested Fix / Patch Strategy:
                      </span>
                      <p className="text-xs font-mono text-indigo-300 whitespace-pre-wrap leading-relaxed">
                        {item.suggestedFix}
                      </p>
                    </div>
                  )}

                  {item.fixPrUrl && (
                    <div className="mt-2">
                      <a
                        href={item.fixPrUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-mono text-emerald-400 hover:text-emerald-300 underline flex items-center gap-1"
                      >
                        View AI Fix PR on GitHub ↗
                      </a>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
