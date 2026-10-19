"use client";

import React, { useEffect, useState } from "react";
import { aiApi } from "@/lib/api";
import { PromptInfo } from "@/lib/types";
import {
  Sliders,
  Search,
  ChevronDown,
  ChevronUp,
  Save,
  RotateCcw,
  Info,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

export const AdvancedSettings: React.FC = () => {
  const [prompts, setPrompts] = useState<PromptInfo[]>([]);
  const [promptSearch, setPromptSearch] = useState("");
  const [expandedKeys, setExpandedKeys] = useState<Record<string, boolean>>({});
  const [editedTexts, setEditedTexts] = useState<Record<string, string>>({});
  const [loadingPrompts, setLoadingPrompts] = useState(false);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [resettingKey, setResettingKey] = useState<string | null>(null);
  const [promptMessage, setPromptMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const loadPrompts = async () => {
    setLoadingPrompts(true);
    try {
      const res = await aiApi.listPrompts();
      setPrompts(res.prompts);
      const textMap: Record<string, string> = {};
      const expMap: Record<string, boolean> = {};
      res.prompts.forEach((p: any, idx: number) => {
        textMap[p.key] = p.prompt;
        if (idx === 0) expMap[p.key] = true;
      });
      setEditedTexts(textMap);
      setExpandedKeys((prev) => ({ ...expMap, ...prev }));
    } catch (e: any) {
      setPromptMessage({ type: "error", text: e.message || "Failed to load system prompts." });
    } finally {
      setLoadingPrompts(false);
    }
  };

  useEffect(() => {
    loadPrompts();
  }, []);

  const handleSavePrompt = async (key: string) => {
    const text = editedTexts[key];
    if (!text || !text.trim()) {
      setPromptMessage({ type: "error", text: "Prompt text cannot be empty." });
      return;
    }
    setSavingKey(key);
    setPromptMessage(null);
    try {
      const res = await aiApi.updatePrompt(key, text);
      setPrompts((prev) =>
        prev.map((p) => (p.key === key ? res.prompt : p))
      );
      setPromptMessage({ type: "success", text: `Prompt "${res.prompt.title}" saved successfully.` });
    } catch (e: any) {
      setPromptMessage({ type: "error", text: e.message || "Failed to save prompt." });
    } finally {
      setSavingKey(null);
    }
  };

  const handleResetPrompt = async (key: string) => {
    setResettingKey(key);
    setPromptMessage(null);
    try {
      const res = await aiApi.resetPrompt(key);
      setPrompts((prev) =>
        prev.map((p) => (p.key === key ? res.prompt : p))
      );
      setEditedTexts((prev) => ({ ...prev, [key]: res.prompt.prompt }));
      setPromptMessage({ type: "success", text: `Prompt "${res.prompt.title}" reset to default.` });
    } catch (e: any) {
      setPromptMessage({ type: "error", text: e.message || "Failed to reset prompt." });
    } finally {
      setResettingKey(null);
    }
  };

  const toggleExpand = (key: string) => {
    setExpandedKeys((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const filteredPrompts = prompts.filter((p) =>
    p.title.toLowerCase().includes(promptSearch.toLowerCase()) ||
    p.description.toLowerCase().includes(promptSearch.toLowerCase()) ||
    p.key.toLowerCase().includes(promptSearch.toLowerCase())
  );

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Toast Feedback */}
      {promptMessage && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between text-xs transition-all animate-fade-in ${
            promptMessage.type === "success"
              ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300"
              : "bg-rose-950/40 border-rose-500/30 text-rose-300"
          }`}
        >
          <div className="flex items-center gap-2.5">
            {promptMessage.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            )}
            <span>{promptMessage.text}</span>
          </div>
          <button
            onClick={() => setPromptMessage(null)}
            className="text-[11px] hover:underline text-zinc-400 ml-4 cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Header info & search */}
      <div className="bg-[#11131a] border border-white/[0.06] rounded-xl p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-blue-400" />
              <h2 className="text-sm font-bold text-white tracking-tight">
                Modular AI System Prompts
              </h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                Live Editable
              </span>
            </div>
            <p className="text-xs text-zinc-400 max-w-2xl leading-relaxed">
              Fine-tune runtime instructions for codebase chat, PR reviews, and AST traversals. Edits persist to Python prompt definitions.
            </p>
          </div>

          <div className="relative w-full sm:w-64">
            <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={promptSearch}
              onChange={(e) => setPromptSearch(e.target.value)}
              placeholder="Search prompts..."
              className="w-full pl-9 pr-3 py-2 bg-white/[0.03] border border-white/[0.08] focus:border-white/20 rounded-lg text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none transition-all"
            />
          </div>
        </div>
      </div>

      {/* Prompt Cards List */}
      {loadingPrompts ? (
        <div className="p-12 text-center text-xs font-mono text-zinc-500 space-y-2">
          <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p>Loading modular system prompts from AI service...</p>
        </div>
      ) : filteredPrompts.length === 0 ? (
        <div className="p-12 text-center text-xs text-zinc-500 bg-[#0c0d12] border border-white/[0.06] rounded-xl">
          No system prompts match "{promptSearch}".
        </div>
      ) : (
        <div className="space-y-4">
          {filteredPrompts.map((p) => {
            const isExpanded = !!expandedKeys[p.key];
            const currentText = editedTexts[p.key] ?? p.prompt;
            const isModifiedLocally = currentText !== p.prompt;
            const lineCount = (currentText || "").split("\n").length;
            const charCount = (currentText || "").length;

            return (
              <div
                key={p.key}
                className={`bg-[#11131a] border rounded-xl transition-all overflow-hidden shadow-xs ${
                  p.is_customized
                    ? "border-blue-500/40 bg-blue-950/[0.04]"
                    : "border-white/[0.06] hover:border-white/[0.12]"
                }`}
              >
                {/* Card Header Accordion */}
                <div
                  onClick={() => toggleExpand(p.key)}
                  className="p-5 flex items-start justify-between gap-4 cursor-pointer select-none hover:bg-white/[0.02] transition-colors"
                >
                  <div className="space-y-1.5 min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-sm text-zinc-100">{p.title}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.04] border border-white/[0.06] text-zinc-400">
                        src/ai_service/prompts/{p.key}.py
                      </span>
                      {p.is_customized ? (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/30">
                          Customized
                        </span>
                      ) : (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-white/[0.06] text-zinc-400">
                          Default
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-zinc-400 leading-relaxed">{p.description}</p>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 pt-0.5">
                    <span className="text-[11px] font-mono text-zinc-500 hidden sm:inline-block">
                      {lineCount} lines • {charCount} chars
                    </span>
                    <div className="w-7 h-7 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center text-zinc-400">
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </div>
                  </div>
                </div>

                {/* Card Body - Editor */}
                {isExpanded && (
                  <div className="px-5 pb-5 pt-1 space-y-4 border-t border-white/[0.06] bg-[#0c0d12]">
                    <div className="relative">
                      <textarea
                        rows={Math.min(18, Math.max(7, lineCount + 1))}
                        value={currentText}
                        onChange={(e) =>
                          setEditedTexts((prev) => ({
                            ...prev,
                            [p.key]: e.target.value,
                          }))
                        }
                        placeholder="Enter system prompt instructions..."
                        className="w-full p-3.5 rounded-xl bg-[#11131a] border border-white/[0.08] focus:border-blue-500/70 focus:ring-1 focus:ring-blue-500/30 text-xs font-mono text-zinc-200 placeholder-zinc-600 focus:outline-none transition-all leading-relaxed"
                      />
                      {isModifiedLocally && (
                        <div className="absolute right-3 top-3 text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                          Unsaved Changes
                        </div>
                      )}
                    </div>

                    {/* Action Buttons */}
                    <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                      <div className="text-[11px] text-zinc-500 flex items-center gap-1.5">
                        <Info className="w-3.5 h-3.5 text-zinc-500" />
                        <span>Stored in modular Python files. Reloaded on demand without restart.</span>
                      </div>

                      <div className="flex items-center gap-2">
                        {p.is_customized && (
                          <button
                            type="button"
                            onClick={() => handleResetPrompt(p.key)}
                            disabled={resettingKey === p.key}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.08] text-zinc-300 hover:text-white hover:bg-white/[0.06] text-xs font-medium transition-all disabled:opacity-50 cursor-pointer"
                            title="Restore original default"
                          >
                            <RotateCcw className={`w-3.5 h-3.5 ${resettingKey === p.key ? "animate-spin" : ""}`} />
                            <span>Reset Default</span>
                          </button>
                        )}

                        <button
                          type="button"
                          onClick={() => handleSavePrompt(p.key)}
                          disabled={savingKey === p.key}
                          className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-white hover:bg-zinc-200 text-black font-semibold text-xs transition-all shadow-xs disabled:opacity-50 cursor-pointer"
                        >
                          <Save className="w-3.5 h-3.5" />
                          <span>{savingKey === p.key ? "Saving..." : "Save Prompt"}</span>
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
