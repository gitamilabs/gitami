"use client";

import React, { useState, useRef, useEffect, useMemo } from "react";
import { useParams } from "next/navigation";
import { useChatStore } from "../../store/chatStore";
import { useProjectStore } from "../../store/projectStore";
import { useAuthStore } from "../../store/authStore";
import { MessageBubble } from "./MessageBubble";
import { RepoSelector } from "./RepoSelector";
import {
  Send,
  Square,
  Trash2,
  Sparkles,
  AlertCircle,
  Zap,
  Share2,
  Database,
  FileCode,
  Plus,
  MessageSquare,
  ChevronDown,
  History,
} from "lucide-react";

export const ChatWindow: React.FC = () => {
  const params = useParams();
  const teamSlug = (params?.teamSlug as string) || "";
  const projectSlug = (params?.projectSlug as string) || "";

  const { token } = useAuthStore();
  const { getActiveProject, fetchProjectDetails } = useProjectStore();
  const activeProject = getActiveProject();

  const {
    messages,
    isStreaming,
    sendMessage,
    stopStreaming,
    clearMessages,
    error,
    fetchAIConfig,
    selectedRepo,
    selectedBranch,
    rootDirectory,
    threads,
    activeThreadId,
    initProject,
    createNewThread,
    switchThread,
    deleteThread,
  } = useChatStore();

  const [input, setInput] = useState("");
  const [isThreadsOpen, setIsThreadsOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const threadsDropdownRef = useRef<HTMLDivElement>(null);

  // Initialize project chat tenancy
  useEffect(() => {
    if (token && projectSlug) {
      fetchProjectDetails(token, projectSlug);
    }
  }, [token, projectSlug, fetchProjectDetails]);

  useEffect(() => {
    if (activeProject) {
      const primaryRepo = activeProject.repositories?.[0];
      initProject(
        activeProject.id,
        primaryRepo?.fullName || primaryRepo?.name || "",
        primaryRepo?.defaultBranch || "main",
        primaryRepo?.rootDirectory || null
      );
    }
  }, [activeProject, initProject]);

  useEffect(() => {
    fetchAIConfig();
  }, [fetchAIConfig]);

  // Close threads dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        threadsDropdownRef.current &&
        !threadsDropdownRef.current.contains(e.target as Node)
      ) {
        setIsThreadsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;
    const userQuery = input.trim();
    sendMessage(userQuery);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const currentThread = useMemo(() => {
    return threads.find((t) => t.id === activeThreadId);
  }, [threads, activeThreadId]);

  const starterPrompts = [
    {
      label: "Trace authentication flow",
      query: "Trace the authentication and authorization flow from incoming request to route handler.",
      icon: <Zap className="w-3.5 h-3.5 text-zinc-400" />,
    },
    {
      label: "Find cross-file dependencies",
      query: "Which files and modules are most heavily depended upon across this codebase?",
      icon: <Share2 className="w-3.5 h-3.5 text-zinc-400" />,
    },
    {
      label: "Calculate ripple blast radius",
      query: "What is the downstream blast radius if I refactor the core database connection or model schemas?",
      icon: <Database className="w-3.5 h-3.5 text-zinc-400" />,
    },
    {
      label: "Identify key API endpoints",
      query: "List all main API routes and controllers, including their middleware dependencies.",
      icon: <FileCode className="w-3.5 h-3.5 text-zinc-400" />,
    },
  ];

  return (
    <div className="flex-1 flex flex-col h-full w-full bg-[#0c0d12] relative overflow-hidden">
      {/* Sleek Minimalist Top Header */}
      <div className="px-4 sm:px-6 py-2.5 border-b border-white/[0.05] bg-[#0c0d12]/90 backdrop-blur-md flex items-center justify-between gap-3 shrink-0 z-20">
        <div className="flex items-center gap-2.5 min-w-0">
          <RepoSelector />

          {/* Thread Switcher Dropdown */}
          <div className="relative" ref={threadsDropdownRef}>
            <button
              type="button"
              onClick={() => setIsThreadsOpen(!isThreadsOpen)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.08] text-xs font-medium text-zinc-300 transition-colors cursor-pointer max-w-[200px] sm:max-w-[240px]"
            >
              <History className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
              <span className="truncate">{currentThread?.title || "Conversations"}</span>
              <ChevronDown className="w-3 h-3 text-zinc-500 shrink-0 ml-0.5" />
            </button>

            {isThreadsOpen && (
              <div className="absolute left-0 top-full mt-2 w-72 rounded-xl border border-white/15 bg-[#141622] shadow-[0_20px_50px_rgba(0,0,0,0.9),0_0_1px_rgba(255,255,255,0.2)] z-50 overflow-hidden text-xs animate-fade-in divide-y divide-white/[0.06] ring-1 ring-black/50">
                <div className="px-3 py-2 flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-zinc-400 font-semibold bg-white/[0.02]">
                  <span>Chat History</span>
                  <span className="text-zinc-500">{threads.length} threads</span>
                </div>

                <div className="max-h-64 overflow-y-auto p-1.5 space-y-1">
                  {threads.map((t) => {
                    const isSelected = t.id === activeThreadId;
                    return (
                      <div
                        key={t.id}
                        className={`flex items-center justify-between gap-1.5 rounded-lg px-2.5 py-1.5 transition-colors cursor-pointer ${
                          isSelected
                            ? "bg-white/[0.1] text-white font-medium shadow-sm"
                            : "hover:bg-white/[0.04] text-zinc-400"
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() => {
                            switchThread(t.id);
                            setIsThreadsOpen(false);
                          }}
                          className="flex items-center gap-2 truncate flex-1 text-left cursor-pointer min-w-0 py-0.5"
                        >
                          <MessageSquare className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                          <span className="truncate">{t.title}</span>
                        </button>

                        {threads.length > 1 && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteThread(t.id);
                            }}
                            className="p-1 rounded text-zinc-500 hover:text-rose-400 hover:bg-rose-500/15 transition-all cursor-pointer shrink-0"
                            title="Delete conversation"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={createNewThread}
            className="p-1.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.08] text-zinc-400 hover:text-white transition-colors cursor-pointer"
            title="Start New Chat"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={clearMessages}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] transition-colors cursor-pointer"
            title="Clear Chat History"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Clear</span>
          </button>
        </div>
      </div>

      {/* Messages Canvas */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-6 pt-6 pb-28 scroll-smooth">
        <div className="max-w-2xl mx-auto w-full space-y-6">
          {messages.length <= 1 ? (
            <div className="flex flex-col items-center justify-center text-center max-w-lg mx-auto py-12 space-y-6 animate-fade-in">
              <div className="w-11 h-11 rounded-2xl bg-white/[0.03] border border-white/[0.08] flex items-center justify-center mx-auto text-zinc-400 shadow-sm">
                <Sparkles className="w-5 h-5 text-zinc-300" />
              </div>

              <div>
                <h2 className="text-base font-semibold text-white tracking-tight">
                  GitAmi Codebase Intelligence
                </h2>
                <p className="text-xs text-zinc-400 mt-1.5 max-w-sm mx-auto leading-relaxed">
                  Query symbols, inspect call graphs, compute ripple blast radius, and explore architectural dependencies.
                </p>
              </div>

              {/* Starter Prompts Grid */}
              <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-2 text-left pt-2">
                {starterPrompts.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setInput(item.query);
                      if (textareaRef.current) textareaRef.current.focus();
                    }}
                    className="p-3 rounded-xl bg-white/[0.02] hover:bg-white/[0.05] border border-white/[0.06] hover:border-white/12 text-left transition-all group cursor-pointer"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      {item.icon}
                      <span className="text-xs font-medium text-zinc-200 group-hover:text-white transition-colors">
                        {item.label}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-500 line-clamp-2 leading-relaxed">
                      {item.query}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                teamSlug={teamSlug}
                projectSlug={projectSlug}
                repoId={selectedRepo}
              />
            ))
          )}

          {error && (
            <div className="p-3.5 rounded-xl bg-rose-950/20 border border-rose-800/30 flex items-start gap-2.5 text-rose-300 text-xs animate-fade-in">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
              <div>
                <p className="font-semibold text-rose-200">AI Service Error</p>
                <p className="font-mono mt-0.5 text-rose-300/80">{error}</p>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Slim Modern Floating Input Island */}
      <div className="absolute inset-x-0 bottom-0 pointer-events-none pb-5 pt-8 bg-gradient-to-t from-[#0c0d12] via-[#0c0d12]/90 to-transparent z-30 flex justify-center">
        <div className="w-full max-w-2xl px-4 pointer-events-auto">
          <div className="relative flex items-center gap-2 rounded-2xl bg-[#13151f]/90 backdrop-blur-2xl border border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.6)] focus-within:border-white/20 focus-within:shadow-[0_12px_40px_rgba(0,0,0,0.8)] transition-all px-3 py-1.5">
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
              }}
              onKeyDown={handleKeyDown}
              placeholder={
                selectedRepo
                  ? `Ask about ${selectedRepo}${rootDirectory ? `/${rootDirectory}` : ""}...`
                  : "Select a repository to query..."
              }
              className="flex-1 min-h-[36px] max-h-36 bg-transparent text-xs sm:text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none resize-none py-2 px-1 leading-relaxed font-sans"
            />

            <div className="flex items-center gap-1 shrink-0 self-end mb-1">
              {isStreaming ? (
                <button
                  type="button"
                  onClick={stopStreaming}
                  className="flex items-center justify-center w-7 h-7 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 transition-all cursor-pointer shadow-sm"
                  title="Stop generation"
                >
                  <Square className="w-3 h-3 fill-current" />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleSend}
                  disabled={!input.trim() || !selectedRepo}
                  className="flex items-center justify-center w-7 h-7 rounded-lg bg-white hover:bg-zinc-200 text-black transition-all cursor-pointer disabled:opacity-20 disabled:cursor-not-allowed shadow-sm"
                  title="Send message"
                >
                  <Send className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
