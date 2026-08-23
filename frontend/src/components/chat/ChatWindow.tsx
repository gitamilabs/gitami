"use client";

import React, { useState, useRef, useEffect } from "react";
import { useChatStore } from "../../store/chatStore";
import { MessageBubble } from "./MessageBubble";
import { RepoSelector } from "./RepoSelector";
import { Button } from "../ui/Button";
import {
  Send,
  Square,
  Trash2,
  Sparkles,
  AlertCircle,
  CornerDownLeft,
} from "lucide-react";

export const ChatWindow: React.FC = () => {
  const {
    messages,
    isStreaming,
    sendMessage,
    stopStreaming,
    clearMessages,
    error,
  } = useChatStore();

  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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

  const starterPrompts = [
    "What is the ripple blast radius if I change authentication tokens?",
    "Show the call hierarchy and dependencies for user service",
    "How does the dual-KB (Neo4j AST + ChromaDB) architecture work?",
    "Find all exported functions and classes across the repository",
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)] glass-panel rounded-2xl border border-slate-800 overflow-hidden relative">
      {/* Header bar */}
      <div className="p-3.5 border-b border-slate-800/80 bg-slate-950/60 flex flex-wrap items-center justify-between gap-3">
        <RepoSelector />

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={clearMessages}
            leftIcon={<Trash2 className="w-3.5 h-3.5 text-slate-400" />}
            className="text-xs text-slate-400 hover:text-rose-400"
          >
            Clear History
          </Button>
        </div>
      </div>

      {/* Message List */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {error && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-2.5 text-rose-300 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">AI Service Error:</p>
              <p>{error}</p>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Starter Prompts */}
      {messages.length <= 1 && (
        <div className="px-4 sm:px-6 pb-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
            <Sparkles className="w-3 h-3 text-indigo-400" />
            <span>Suggested Queries</span>
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {starterPrompts.map((prompt, i) => (
              <button
                key={i}
                onClick={() => {
                  setInput(prompt);
                  if (textareaRef.current) textareaRef.current.focus();
                }}
                className="text-left text-xs p-2.5 rounded-xl bg-slate-900/80 hover:bg-indigo-950/40 border border-slate-800 hover:border-indigo-800/60 text-slate-300 transition-all truncate"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="p-3 sm:p-4 border-t border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
        <div className="relative flex items-end gap-2 bg-slate-900 border border-slate-700/80 focus-within:border-indigo-500 rounded-2xl p-2 shadow-inner transition-colors">
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
            placeholder="Ask about functions, call graphs, blast radius, or architecture..."
            className="flex-1 max-h-36 bg-transparent text-sm text-slate-100 placeholder-slate-400 focus:outline-none resize-none px-2 py-1 leading-relaxed"
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

        <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 px-1">
          <span className="flex items-center gap-1">
            <CornerDownLeft className="w-3 h-3 text-slate-400" />
            <kbd className="font-mono bg-slate-800 px-1 rounded text-[10px]">Enter</kbd> to send,{" "}
            <kbd className="font-mono bg-slate-800 px-1 rounded text-[10px]">Shift+Enter</kbd> for newline
          </span>
          <span className="hidden sm:inline-block font-mono">
            Powered by FastMCP & Tree-sitter
          </span>
        </div>
      </div>
    </div>
  );
};
