"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { DisplayMessage } from "../../store/chatStore";
import { ToolStepAccordion } from "./ToolStepAccordion";
import { CitationCard } from "./CitationCard";
import { formatLatency } from "../../lib/utils";
import {
  User,
  Bot,
  Sparkles,
  ChevronDown,
  ChevronRight,
  Clock,
  Check,
  Copy,
  Layers,
  BookOpen,
  Cpu,
} from "lucide-react";

interface MessageBubbleProps {
  message: DisplayMessage;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === "user";
  const [thoughtsOpen, setThoughtsOpen] = useState(false);
  const [citationsOpen, setCitationsOpen] = useState(true);
  const [copied, setCopied] = useState(false);

  const handleCopyAnswer = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`flex gap-3.5 my-4 ${
        isUser ? "justify-end" : "justify-start"
      } animate-fade-in`}
    >
      {!isUser && (
        <div className="w-8 h-8 rounded-xl bg-zinc-900 border border-zinc-800 shrink-0 flex items-center justify-center mt-1">
          <Bot className="w-4 h-4 text-blue-400" />
        </div>
      )}

      <div
        className={`max-w-3xl rounded-2xl p-5 ${
          isUser
            ? "bg-blue-600 text-white rounded-br-md border border-blue-500/40"
            : "glass-panel rounded-bl-md border border-slate-800 text-slate-100"
        }`}
      >
        {isUser ? (
          <p className="text-xs sm:text-sm font-medium whitespace-pre-wrap leading-relaxed">
            {message.content}
          </p>
        ) : (
          <div className="space-y-4">
            {/* Autonomous ReAct Thoughts (Collapsible) */}
            {message.thoughts && message.thoughts.length > 0 && (
              <div className="rounded-xl border border-indigo-900/50 bg-indigo-950/30 p-3 shadow-inner">
                <button
                  onClick={() => setThoughtsOpen(!thoughtsOpen)}
                  className="w-full flex items-center justify-between text-left text-xs font-semibold text-indigo-300 hover:text-indigo-200 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                    <span>
                      Autonomous Reasoning Thoughts ({message.thoughts.length}{" "}
                      steps)
                    </span>
                  </div>
                  {thoughtsOpen ? (
                    <ChevronDown className="w-3.5 h-3.5" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5" />
                  )}
                </button>

                {thoughtsOpen && (
                  <div className="mt-2.5 space-y-2 text-xs text-indigo-200/90 font-mono border-t border-indigo-900/40 pt-2.5">
                    {message.thoughts.map((thought, idx) => (
                      <div key={idx} className="flex gap-2 bg-indigo-950/40 p-2 rounded-xl border border-indigo-900/30">
                        <span className="text-indigo-400 font-bold shrink-0">
                          #{idx + 1}
                        </span>
                        <p className="leading-relaxed">{thought}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Executed Knowledge Base Tool Steps */}
            {message.toolSteps && message.toolSteps.length > 0 && (
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 px-1 font-mono">
                  <Layers className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Knowledge Base & Graph Tool Execution</span>
                </div>
                {message.toolSteps.map((step) => (
                  <ToolStepAccordion key={step.id} step={step} />
                ))}
              </div>
            )}

            {/* Synthesized Answer Body */}
            {message.content ? (
              <div className="prose-custom text-xs sm:text-sm leading-relaxed text-slate-200 relative pt-1">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              </div>
            ) : message.isStreaming ? (
              <div className="flex items-center gap-2.5 text-xs text-indigo-400 font-mono py-2">
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping shrink-0" />
                <span>Synthesizing response from Knowledge Base tools...</span>
              </div>
            ) : null}

            {/* Cited Sources List */}
            {message.citations && message.citations.length > 0 && (
              <div className="border-t border-slate-800/80 pt-3.5 space-y-2.5">
                <button
                  onClick={() => setCitationsOpen(!citationsOpen)}
                  className="w-full flex items-center justify-between text-left text-xs font-semibold text-slate-300 hover:text-white transition-colors"
                >
                  <div className="flex items-center gap-1.5">
                    <BookOpen className="w-3.5 h-3.5 text-cyan-400" />
                    <span>
                      Cited Source Passages ({message.citations.length})
                    </span>
                  </div>
                  {citationsOpen ? (
                    <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                  )}
                </button>

                {citationsOpen && (
                  <div className="grid grid-cols-1 gap-2 pt-1">
                    {message.citations.map((citation) => (
                      <CitationCard key={citation.id} citation={citation} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Footer Metadata & Copy */}
            {!message.isStreaming && message.content && (
              <div className="flex items-center justify-between text-[11px] text-slate-400 pt-3 border-t border-slate-800/80 font-mono">
                <div className="flex items-center gap-3">
                  {message.latencyMs && message.latencyMs > 0 && (
                    <span className="flex items-center gap-1 text-slate-400">
                      <Clock className="w-3 h-3 text-amber-400" />
                      {formatLatency(message.latencyMs)}
                    </span>
                  )}
                  <span className="text-slate-500 hidden sm:inline-block">Dual-LLM (Gemini + Groq)</span>
                </div>
                <button
                  onClick={handleCopyAnswer}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors border border-transparent hover:border-slate-700"
                >
                  {copied ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-400" />
                      <span className="text-emerald-400 font-semibold">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 p-0.5 shrink-0 flex items-center justify-center text-slate-300 mt-1 shadow-sm">
          <User className="w-4 h-4" />
        </div>
      )}
    </div>
  );
};

