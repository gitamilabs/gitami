"use client";

import React, { useState, useRef, useEffect } from "react";
import { useChatStore } from "../../store/chatStore";
import { MessageBubble } from "./MessageBubble";
import { RepoSelector } from "./RepoSelector";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import {
  Send,
  Square,
  Trash2,
  Sparkles,
  AlertCircle,
  CornerDownLeft,
  Bot,
  Zap,
  Share2,
  Database,
  Terminal,
  FileText,
  Loader2,
} from "lucide-react";
import { aiApi } from "../../lib/api";

export const ChatWindow: React.FC = () => {
  const {
    messages,
    isStreaming,
    sendMessage,
    stopStreaming,
    clearMessages,
    error,
    aiConfig,
    fetchAIConfig,
    selectedRepo,
    selectedBranch,
    addAssistantMessage,
  } = useChatStore();

  const [isGeneratingReport, setIsGeneratingReport] = useState(false);

  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    fetchAIConfig();
  }, [fetchAIConfig]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;
    sendMessage(input);
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

  const [chatMode, setChatMode] = useState<"ask" | "investigate">("ask");

  const handleGenerateReport = async () => {
    if (!selectedRepo) return;
    setIsGeneratingReport(true);
    try {
      addAssistantMessage("Generating GitAmi Architecture Report...");
      const res = await aiApi.getGraphReport(selectedRepo, selectedBranch);
      addAssistantMessage(res.report_markdown);
    } catch (err: any) {
      addAssistantMessage(`Error generating report: ${err.message}`);
    } finally {
      setIsGeneratingReport(false);
    }
  };

  const modelLabel = "GitAmi Intelligence Engine";
  const vectorDbLabel = "Knowledge Base";

  const starterCategories = [
    {
      category: "Blast Radius & Ripple Risk",
      icon: <Zap className="w-3.5 h-3.5 text-rose-400" />,
      prompts: [
        "What is the ripple blast radius if I modify session authentication token signing?",
        "Which downstream files and callers will break if user payload schema changes?",
      ],
    },
    {
      category: "AST Topology & Call Graphs",
      icon: <Share2 className="w-3.5 h-3.5 text-indigo-400" />,
      prompts: [
        "Show the complete caller hierarchy and dependencies for auth callback service",
        "Find all exported classes and methods across backend services",
      ],
    },
    {
      category: "Knowledge Base & Architecture",
      icon: <Database className="w-3.5 h-3.5 text-cyan-400" />,
      prompts: [
        `How does the dual-KB (Neo4j AST + ${vectorDbLabel} vector embeddings) architecture work?`,
        "Explain how codebase intelligence retrieval works across AST and vector indices",
      ],
    },
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)] sm:h-[calc(100vh-3rem)] bg-[#0c0d12] rounded-xl border border-white/[0.06] overflow-hidden relative">
      {/* Header bar */}
      <div className="p-3 sm:p-4 border-b border-white/[0.06] bg-[#0c0d12]/90 backdrop-blur-md flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <RepoSelector />

          {/* Ask / Investigate Segmented Toggle */}
          <div className="flex items-center p-0.5 bg-white/[0.03] border border-white/[0.06] rounded-lg text-xs font-medium">
            <button
              type="button"
              onClick={() => setChatMode("ask")}
              className={`px-3 py-1 rounded-md transition-colors cursor-pointer ${
                chatMode === "ask"
                  ? "bg-white/[0.08] text-white font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Ask
            </button>
            <button
              type="button"
              onClick={() => setChatMode("investigate")}
              className={`px-3 py-1 rounded-md transition-colors flex items-center gap-1.5 cursor-pointer ${
                chatMode === "investigate"
                  ? "bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 font-semibold"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <Sparkles className="w-3 h-3 text-indigo-400" />
              <span>Investigate</span>
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="ghost"
            size="sm"
            onClick={clearMessages}
            leftIcon={<Trash2 className="w-3.5 h-3.5 text-zinc-500" />}
            className="text-xs text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg"
            title="Clear Chat History"
          >
            Clear
          </Button>

          <Button
            variant="secondary"
            size="sm"
            onClick={handleGenerateReport}
            disabled={!selectedRepo || isGeneratingReport}
            leftIcon={
              isGeneratingReport ? (
                <Loader2 className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
              ) : (
                <FileText className="w-3.5 h-3.5 text-indigo-400" />
              )
            }
            className="text-xs text-zinc-300 hover:text-white rounded-lg border border-white/[0.08] bg-white/[0.04]"
            title="Generate Architecture Report"
          >
            Graph Report
          </Button>
        </div>
      </div>

      {/* Message List */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-2xl mx-auto py-10 space-y-6">
            <div className="w-14 h-14 rounded-xl bg-white/[0.04] border border-white/[0.06] flex items-center justify-center">
              <Bot className="w-7 h-7 text-blue-400" />
            </div>

            <div className="space-y-2">
              <h3 className="text-xl sm:text-2xl font-extrabold text-white tracking-tight">
                Ask GitAmi Codebase Agent
              </h3>
              <p className="text-xs sm:text-sm text-zinc-400 max-w-md mx-auto leading-relaxed">
                Inspect call graphs, compute transitive blast radius, or search semantic vector passages across your repository.
              </p>
            </div>

            {/* Categorized Starter Prompts */}
            <div className="w-full space-y-3 pt-2 text-left">
              {starterCategories.map((cat, idx) => (
                <div key={idx} className="space-y-1.5">
                  <p className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider font-mono flex items-center gap-1.5 px-1">
                    {cat.icon}
                    <span>{cat.category}</span>
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {cat.prompts.map((prompt, pIdx) => (
                      <button
                        key={pIdx}
                        onClick={() => {
                          setInput(prompt);
                          if (textareaRef.current) textareaRef.current.focus();
                        }}
                        className="text-left text-xs p-3 rounded-xl bg-[#11131a] hover:bg-white/[0.04] border border-white/[0.06] hover:border-white/[0.12] text-zinc-300 transition-all leading-relaxed truncate group shadow-sm"
                      >
                        <span className="group-hover:text-indigo-200 transition-colors">
                          {prompt}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
          </>
        )}

        {error && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-3 text-rose-300 text-xs animate-fade-in">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold">AI Service Error:</p>
              <p className="font-mono mt-0.5 text-rose-200">{error}</p>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Composer area */}
      <div className="p-3 sm:p-4 border-t border-white/[0.06] bg-[#0c0d12]">
        <div className="relative flex items-end gap-2 bg-[#11131a] border border-white/[0.08] focus-within:border-white/[0.16] rounded-xl p-2 transition-all">
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
              chatMode === "investigate"
                ? "Investigate architectural impact, blast radius, or cross-file caller dependencies..."
                : "Ask GitAmi about your codebase..."
            }
            className="flex-1 max-h-36 bg-transparent text-xs sm:text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none resize-none px-2.5 py-1.5 leading-relaxed font-sans"
          />

          <div className="flex items-center gap-1.5 shrink-0">
            {isStreaming ? (
              <Button
                variant="danger"
                size="sm"
                onClick={stopStreaming}
                leftIcon={<Square className="w-3.5 h-3.5 fill-current" />}
              >
                Stop
              </Button>
            ) : (
              <button
                type="button"
                onClick={handleSend}
                disabled={!input.trim()}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer disabled:opacity-40 ${
                  chatMode === "investigate"
                    ? "bg-indigo-600 hover:bg-indigo-500 text-white shadow-xs"
                    : "bg-white hover:bg-zinc-200 text-black shadow-xs"
                }`}
              >
                <span>{chatMode === "investigate" ? "Investigate" : "Ask"}</span>
                <Send className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between text-[11px] text-zinc-500 mt-2 px-1 font-mono">
          <span className="flex items-center gap-1">
            <CornerDownLeft className="w-3 h-3 text-zinc-500" />
            <kbd className="bg-zinc-800/80 px-1.5 py-0.5 rounded text-[10px] text-zinc-400">Enter</kbd> to send,{" "}
            <kbd className="bg-zinc-800/80 px-1.5 py-0.5 rounded text-[10px] text-zinc-400">Shift+Enter</kbd> for newline
          </span>
          <span className="hidden sm:inline-block text-zinc-500">
            GitAmi Context Engine V1 • AST Software Graph &amp; Vector KB
          </span>
        </div>
      </div>
    </div>
  );
};

