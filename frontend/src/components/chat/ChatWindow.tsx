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
} from "lucide-react";

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
  } = useChatStore();

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

  const modelLabel = aiConfig
    ? `${aiConfig.models.primary_orchestrator} + ${aiConfig.models.worker_model}`
    : "Gemini 2.0 Flash + Groq 70B";

  const vectorDbLabel = aiConfig?.vector_db
    ? aiConfig.vector_db.replace("_", " ").toUpperCase()
    : "Vector DB";

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
      category: "Vector KB & Architecture",
      icon: <Database className="w-3.5 h-3.5 text-cyan-400" />,
      prompts: [
        `How does the dual-KB (Neo4j AST + ${vectorDbLabel} vector embeddings) architecture work?`,
        "Explain how the FastMCP server tools interface with the ReAct agent loop",
      ],
    },
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)] sm:h-[calc(100vh-3rem)] glass-panel rounded-xl border border-slate-800/80 overflow-hidden relative">
      {/* Header bar */}
      <div className="p-3.5 sm:p-4 border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-md flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <RepoSelector />
        </div>

        <div className="flex items-center gap-2.5">
          <div className="hidden xl:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-[10px] font-mono text-slate-400">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
            <span className="truncate max-w-[320px]" title={modelLabel}>{modelLabel}</span>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={clearMessages}
            leftIcon={<Trash2 className="w-3.5 h-3.5 text-slate-500" />}
            className="text-xs text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-xl"
            title="Clear Chat History"
          >
            Clear
          </Button>
        </div>
      </div>

      {/* Message List */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-2xl mx-auto py-10 space-y-6">
            <div className="w-14 h-14 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center">
              <Bot className="w-7 h-7 text-blue-400" />
            </div>

            <div className="space-y-2">
              <h3 className="text-xl sm:text-2xl font-extrabold text-white tracking-tight">
                Ask Sentinel Codebase Agent
              </h3>
              <p className="text-xs sm:text-sm text-slate-400 max-w-md mx-auto leading-relaxed">
                Inspect call graphs, compute transitive blast radius, or search semantic vector passages across your repository.
              </p>
            </div>

            {/* Categorized Starter Prompts */}
            <div className="w-full space-y-3 pt-2 text-left">
              {starterCategories.map((cat, idx) => (
                <div key={idx} className="space-y-1.5">
                  <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-mono flex items-center gap-1.5 px-1">
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
                        className="text-left text-xs p-3 rounded-xl bg-slate-900/80 hover:bg-indigo-950/40 border border-slate-800/90 hover:border-indigo-700/60 text-slate-300 transition-all leading-relaxed truncate group shadow-sm"
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
      <div className="p-3 sm:p-4 border-t border-slate-800/80 bg-slate-950/90 backdrop-blur-xl">
        <div className="relative flex items-end gap-2 bg-slate-900/90 border border-slate-700/80 focus-within:border-indigo-500 rounded-xl p-2 shadow-inner transition-all">
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
            placeholder="Ask about functions, call hierarchies, blast radius, or architecture..."
            className="flex-1 max-h-36 bg-transparent text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none resize-none px-2.5 py-1.5 leading-relaxed font-sans"
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
              <Button
                variant="glow"
                size="sm"
                onClick={handleSend}
                disabled={!input.trim()}
                rightIcon={<Send className="w-3.5 h-3.5" />}
              >
                Ask Agent
              </Button>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between text-[11px] text-slate-500 mt-2 px-1 font-mono">
          <span className="flex items-center gap-1">
            <CornerDownLeft className="w-3 h-3 text-slate-500" />
            <kbd className="bg-slate-800/80 px-1.5 py-0.5 rounded text-[10px] text-slate-400">Enter</kbd> to send,{" "}
            <kbd className="bg-slate-800/80 px-1.5 py-0.5 rounded text-[10px] text-slate-400">Shift+Enter</kbd> for newline
          </span>
          <span className="hidden sm:inline-block">
            FastMCP • Tree-sitter AST • Neo4j • {vectorDbLabel}
          </span>
        </div>
      </div>
    </div>
  );
};

