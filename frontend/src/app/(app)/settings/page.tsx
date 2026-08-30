"use client";

import React, { useEffect, useState } from "react";
import { useAuthStore } from "../../../store/authStore";
import { useRepoStore } from "../../../store/repoStore";
import { formatTimeAgo } from "../../../lib/utils";
import { aiApi } from "../../../lib/api";
import { PromptInfo, AIServiceConfig } from "../../../lib/types";
import {
  Settings,
  Github,
  LogOut,
  FolderGit2,
  Database,
  ExternalLink,
  Bot,
  Sliders,
  Cpu,
  Layers,
  Save,
  RotateCcw,
  Search,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Info,
  KeyRound,
  FileCode,
} from "lucide-react";

export default function SettingsPage() {
  const { user, token, logout } = useAuthStore();
  const {
    connectedRepos,
    installations,
    indexedRepos,
    fetchConnectedRepos,
    fetchInstallations,
    fetchIndexedRepos,
  } = useRepoStore();

  const [activeTab, setActiveTab] = useState<"general" | "prompts" | "engine">("prompts");

  // System Prompts State
  const [prompts, setPrompts] = useState<PromptInfo[]>([]);
  const [promptSearch, setPromptSearch] = useState("");
  const [expandedKeys, setExpandedKeys] = useState<Record<string, boolean>>({});
  const [editedTexts, setEditedTexts] = useState<Record<string, string>>({});
  const [loadingPrompts, setLoadingPrompts] = useState(false);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [resettingKey, setResettingKey] = useState<string | null>(null);
  const [promptMessage, setPromptMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Engine Config State
  const [aiConfig, setAiConfig] = useState<AIServiceConfig | null>(null);
  const [loadingConfig, setLoadingConfig] = useState(false);

  useEffect(() => {
    if (token) {
      fetchConnectedRepos(token);
      fetchInstallations(token);
      fetchIndexedRepos(token);
    }
  }, [token, fetchConnectedRepos, fetchInstallations, fetchIndexedRepos]);

  const loadPrompts = async () => {
    setLoadingPrompts(true);
    try {
      const res = await aiApi.listPrompts();
      setPrompts(res.prompts);
      const textMap: Record<string, string> = {};
      const expMap: Record<string, boolean> = {};
      res.prompts.forEach((p, idx) => {
        textMap[p.key] = p.prompt;
        // Expand first prompt by default
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

  const loadConfig = async () => {
    setLoadingConfig(true);
    try {
      const cfg = await aiApi.getConfig();
      setAiConfig(cfg);
    } catch (e: any) {
      console.warn("Could not load AI config:", e);
    } finally {
      setLoadingConfig(false);
    }
  };

  useEffect(() => {
    loadPrompts();
    loadConfig();
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
    <div className="flex-1 flex flex-col min-h-screen bg-[#070709] text-zinc-100">
      {/* Header */}
      <header className="h-16 border-b border-zinc-800/80 px-6 sm:px-8 flex items-center justify-between bg-[#0a0a0d]/70 backdrop-blur-md sticky top-0 z-20">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
            <Settings className="w-4 h-4 text-blue-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-tight">System & AI Settings</h1>
            <p className="text-[11px] text-zinc-500">Configure AI system prompts, vector stores, and integrations</p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-1 bg-zinc-900/90 border border-zinc-800 p-1 rounded-lg text-xs font-medium">
          <button
            onClick={() => setActiveTab("prompts")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md transition-all ${
              activeTab === "prompts"
                ? "bg-blue-600/20 text-blue-300 border border-blue-500/30 font-semibold shadow-xs"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>AI Prompts</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-zinc-800 text-zinc-400">
              {prompts.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("engine")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md transition-all ${
              activeTab === "engine"
                ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 font-semibold shadow-xs"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>AI Engine</span>
            {aiConfig?.vector_db && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                {aiConfig.vector_db}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab("general")}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md transition-all ${
              activeTab === "general"
                ? "bg-zinc-800 text-white font-semibold shadow-xs"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <FolderGit2 className="w-3.5 h-3.5" />
            <span>Workspace</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 p-6 sm:p-8 max-w-5xl w-full mx-auto space-y-6">
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
              className="text-[11px] hover:underline text-zinc-400 ml-4"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* TAB 1: SYSTEM PROMPTS */}
        {activeTab === "prompts" && (
          <div className="space-y-6 animate-fade-in">
            {/* Header info & search */}
            <div className="bg-[#0c0c10] border border-zinc-800/90 rounded-2xl p-6 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <h2 className="text-base font-bold text-white tracking-tight">
                      Modular AI System Prompts
                    </h2>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                      Live Editable
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 max-w-2xl leading-relaxed">
                    Customize system instructions for the autonomous ReAct reasoning loop, code reviewers, AST fixer agent, context compressor, and RAG synthesis. Edits persist directly to backend files.
                  </p>
                </div>

                <div className="relative w-full sm:w-64">
                  <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={promptSearch}
                    onChange={(e) => setPromptSearch(e.target.value)}
                    placeholder="Search prompts..."
                    className="w-full pl-9 pr-3 py-2 bg-zinc-900/90 border border-zinc-800 focus:border-blue-500/60 rounded-xl text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none transition-all"
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
              <div className="p-12 text-center text-xs text-zinc-500 bg-[#0c0c10] border border-zinc-800 rounded-2xl">
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
                      className={`bg-[#0c0c10] border rounded-2xl transition-all overflow-hidden shadow-xs ${
                        p.is_customized
                          ? "border-blue-500/40 bg-blue-950/[0.04]"
                          : "border-zinc-800/90 hover:border-zinc-700/80"
                      }`}
                    >
                      {/* Card Header Accordion */}
                      <div
                        onClick={() => toggleExpand(p.key)}
                        className="p-5 flex items-start justify-between gap-4 cursor-pointer select-none hover:bg-zinc-900/40 transition-colors"
                      >
                        <div className="space-y-1.5 min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-sm text-zinc-100">{p.title}</span>
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                              src/ai_service/prompts/{p.key}.py
                            </span>
                            {p.is_customized ? (
                              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/30">
                                Customized
                              </span>
                            ) : (
                              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400">
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
                          <div className="w-7 h-7 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-400">
                            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </div>
                        </div>
                      </div>

                      {/* Card Body - Editor */}
                      {isExpanded && (
                        <div className="px-5 pb-5 pt-1 space-y-4 border-t border-zinc-800/60 bg-[#08080a]/90">
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
                              className="w-full p-3.5 rounded-xl bg-zinc-950/90 border border-zinc-800/90 focus:border-blue-500/70 focus:ring-1 focus:ring-blue-500/30 text-xs font-mono text-zinc-200 placeholder-zinc-600 focus:outline-none transition-all leading-relaxed"
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
                                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white hover:bg-zinc-800 text-xs font-medium transition-all disabled:opacity-50 cursor-pointer"
                                  title="Restore original hardcoded default"
                                >
                                  <RotateCcw className={`w-3.5 h-3.5 ${resettingKey === p.key ? "animate-spin" : ""}`} />
                                  <span>Reset Default</span>
                                </button>
                              )}

                              <button
                                type="button"
                                onClick={() => handleSavePrompt(p.key)}
                                disabled={savingKey === p.key}
                                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition-all shadow-xs disabled:opacity-50 cursor-pointer"
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
        )}

        {/* TAB 2: AI ENGINE CONFIG */}
        {activeTab === "engine" && (
          <div className="space-y-6 animate-fade-in">
            <div className="bg-[#0c0c10] border border-zinc-800/90 rounded-2xl p-6 shadow-sm space-y-4">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-indigo-400" />
                <h2 className="text-base font-bold text-white tracking-tight">
                  AI Orchestrator & Vector Engine Architecture
                </h2>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Live runtime inspection of active vector databases, embedder models, and dual-LLM configurations loaded from <code className="text-zinc-300 font-mono">backend/ai-service/.env</code>.
              </p>

              {loadingConfig ? (
                <div className="p-8 text-center text-xs font-mono text-zinc-500">Loading AI config...</div>
              ) : aiConfig ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                  {/* Vector DB Card */}
                  <div className="p-4 rounded-xl bg-zinc-950/70 border border-zinc-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-xs font-bold text-emerald-400">
                        <Database className="w-4 h-4" />
                        <span>Active Vector Database</span>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                        Active
                      </span>
                    </div>
                    <p className="text-lg font-mono font-extrabold text-white">
                      {aiConfig.vector_db.toUpperCase()}
                    </p>
                    <p className="text-[11px] text-zinc-500">
                      Embedder Model: <span className="font-mono text-zinc-300">{aiConfig.embedder}</span>
                    </p>
                    {aiConfig.storage.pinecone_index && (
                      <p className="text-[11px] text-zinc-500">
                        Pinecone Index: <span className="font-mono text-zinc-300">{aiConfig.storage.pinecone_index}</span>
                      </p>
                    )}
                    {aiConfig.storage.qdrant_collection && (
                      <p className="text-[11px] text-zinc-500">
                        Qdrant Collection: <span className="font-mono text-zinc-300">{aiConfig.storage.qdrant_collection}</span>
                      </p>
                    )}
                  </div>

                  {/* Primary LLM Orchestrator Card */}
                  <div className="p-4 rounded-xl bg-zinc-950/70 border border-zinc-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-xs font-bold text-indigo-400">
                        <Bot className="w-4 h-4" />
                        <span>Primary LLM Orchestrator</span>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                        Google GenAI
                      </span>
                    </div>
                    <p className="text-base font-mono font-bold text-white truncate">
                      {aiConfig.models.primary_orchestrator}
                    </p>
                    <div className="text-[11px] text-zinc-500 space-y-1">
                      <p>Fallback Candidate Models:</p>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {aiConfig.models.gemini_models.slice(0, 4).map((m) => (
                          <span key={m} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-900 text-zinc-300 border border-zinc-800">
                            {m}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Groq Worker Node Card */}
                  <div className="p-4 rounded-xl bg-zinc-950/70 border border-zinc-800 space-y-2 md:col-span-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-xs font-bold text-cyan-400">
                        <Cpu className="w-4 h-4" />
                        <span>Groq Parallel Sub-task & Diff Hunk Worker</span>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                        Groq Fast Inference
                      </span>
                    </div>
                    <p className="text-base font-mono font-bold text-white">
                      {aiConfig.models.worker_model}
                    </p>
                    <div className="flex flex-wrap gap-1 pt-1">
                      {aiConfig.models.groq_models.map((m) => (
                        <span key={m} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-900 text-zinc-300 border border-zinc-800">
                          {m}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-zinc-500">AI Service is currently offline or unreachable.</p>
              )}
            </div>
          </div>
        )}

        {/* TAB 3: WORKSPACE & ACCOUNT */}
        {activeTab === "general" && (
          <div className="space-y-6 animate-fade-in">
            {/* Account */}
            <section className="bg-[#0c0c10] border border-zinc-800/80 rounded-2xl p-6 space-y-4 shadow-sm">
              <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Account</h2>
              <div className="flex items-center gap-3.5">
                {user?.avatarUrl ? (
                  <img
                    src={user.avatarUrl}
                    alt={user.username}
                    className="w-12 h-12 rounded-full border border-zinc-700 object-cover"
                  />
                ) : (
                  <div className="w-12 h-12 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-sm font-bold text-zinc-200">
                    {(user?.username || "?").slice(0, 2).toUpperCase()}
                  </div>
                )}
                <div>
                  <p className="text-sm font-semibold text-white">{user?.name || user?.username}</p>
                  <p className="text-xs text-zinc-500 font-mono">{user?.email || "No email on file"}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 pt-2 text-xs">
                <div className="p-3 rounded-xl bg-zinc-950/70 border border-zinc-800">
                  <p className="text-[10px] text-zinc-500 uppercase font-mono">GitHub Username</p>
                  <p className="text-zinc-200 font-mono font-semibold mt-0.5">{user?.username || "—"}</p>
                </div>
                <div className="p-3 rounded-xl bg-zinc-950/70 border border-zinc-800">
                  <p className="text-[10px] text-zinc-500 uppercase font-mono">Member Since</p>
                  <p className="text-zinc-200 font-mono font-semibold mt-0.5">
                    {user?.createdAt ? formatTimeAgo(user.createdAt) : "—"}
                  </p>
                </div>
              </div>
              <button
                onClick={() => logout()}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-500/10 border border-red-500/25 text-red-400 hover:bg-red-500/15 text-xs font-medium transition-colors cursor-pointer"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>Sign out</span>
              </button>
            </section>

            {/* Workspace stats */}
            <section className="bg-[#0c0c10] border border-zinc-800/80 rounded-2xl p-6 space-y-4 shadow-sm">
              <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Knowledge Base Stats</h2>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3.5 rounded-xl bg-zinc-950/70 border border-zinc-800 flex items-center gap-3">
                  <FolderGit2 className="w-4 h-4 text-blue-400 shrink-0" />
                  <div>
                    <p className="text-[10px] text-zinc-500 uppercase font-mono">Connected Repos</p>
                    <p className="text-zinc-200 font-bold text-sm mt-0.5">{connectedRepos.length}</p>
                  </div>
                </div>
                <div className="p-3.5 rounded-xl bg-zinc-950/70 border border-zinc-800 flex items-center gap-3">
                  <Database className="w-4 h-4 text-emerald-400 shrink-0" />
                  <div>
                    <p className="text-[10px] text-zinc-500 uppercase font-mono">Indexed Repos</p>
                    <p className="text-zinc-200 font-bold text-sm mt-0.5">{indexedRepos.length}</p>
                  </div>
                </div>
              </div>
            </section>

            {/* GitHub App installations */}
            <section className="bg-[#0c0c10] border border-zinc-800/80 rounded-2xl p-6 space-y-4 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                  GitHub App Installations
                </h2>
                <a
                  href="https://github.com/settings/installations"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 font-medium"
                >
                  Manage on GitHub <ExternalLink className="w-3 h-3" />
                </a>
              </div>

              {installations.length === 0 ? (
                <p className="text-xs text-zinc-500">No GitHub App installations found for this account.</p>
              ) : (
                <div className="space-y-2">
                  {installations.map((inst) => (
                    <div
                      key={inst.id}
                      className="flex items-center gap-3 p-3 rounded-xl bg-zinc-950/70 border border-zinc-800"
                    >
                      <Github className="w-4 h-4 text-white shrink-0" />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-medium text-zinc-200 truncate">{inst.accountLogin}</p>
                        <p className="text-[10px] text-zinc-500 font-mono">{inst.accountType}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
