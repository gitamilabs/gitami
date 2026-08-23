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
        <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 p-0.5 shrink-0 shadow-md shadow-indigo-500/20 mt-1">
          <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
            <Bot className="w-4 h-4 text-indigo-400" />
          </div>
        </div>
      )}

      <div
        className={`max-w-3xl rounded-2xl p-4.5 ${
          isUser
            ? "bg-indigo-600 text-white rounded-br-sm shadow-md shadow-indigo-600/20"
            : "glass-card rounded-bl-sm border border-slate-800 text-slate-100"
        }`}
      >
        {isUser ? (
          <p className="text-sm font-medium whitespace-pre-wrap leading-relaxed">
            {message.content}
          </p>
        ) : (
          <div className="space-y-3.5">
            {/* Autonomous ReAct Thoughts (Collapsible) */}
            {message.thoughts && message.thoughts.length > 0 && (
              <div className="rounded-xl border border-indigo-900/40 bg-indigo-950/20 p-2.5">
                <button
                  onClick={() => setThoughtsOpen(!thoughtsOpen)}
                  className="w-full flex items-center justify-between text-left text-xs font-semibold text-indigo-300 hover:text-indigo-200"
                >
                  <div className="flex items-center gap-1.5">
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
                  <div className="mt-2 space-y-1.5 text-xs text-indigo-200/90 font-mono border-t border-indigo-900/40 pt-2">
                    {message.thoughts.map((thought, idx) => (
                      <div key={idx} className="flex gap-2">
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
              <div className="space-y-1">
                <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400 px-1">
                  <Layers className="w-3 h-3 text-cyan-400" />
                  <span>Knowledge Base & Graph Tool Execution</span>
                </div>
                {message.toolSteps.map((step) => (
                  <ToolStepAccordion key={step.id} step={step} />
                ))}
              </div>
            )}

            {/* Synthesized Answer Body */}
            {message.content ? (
              <div className="prose-custom text-sm leading-relaxed text-slate-200 relative pt-1">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              </div>
            ) : message.isStreaming ? (
              <div className="flex items-center gap-2 text-xs text-indigo-400 font-mono py-1">
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping" />
                Synthesizing response from Knowledge Base tools...
              </div>
            ) : null}

            {/* Cited Sources List */}
            {message.citations && message.citations.length > 0 && (
              <div className="border-t border-slate-800/80 pt-3 space-y-2">
                <button
                  onClick={() => setCitationsOpen(!citationsOpen)}
                  className="w-full flex items-center justify-between text-left text-xs font-semibold text-slate-300 hover:text-white"
                >
                  <div className="flex items-center gap-1.5">
                    <BookOpen className="w-3.5 h-3.5 text-cyan-400" />
                    <span>
                      Cited Source Passages ({message.citations.length})
                    </span>
                  </div>
                  {citationsOpen ? (
                    <ChevronDown className="w-3.5 h-3.5" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5" />
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
              <div className="flex items-center justify-between text-[11px] text-slate-400 pt-2 border-t border-slate-800/60 font-mono">
                <div className="flex items-center gap-2">
                  {message.latencyMs && message.latencyMs > 0 && (
                    <span className="flex items-center gap-1 text-slate-400">
                      <Clock className="w-3 h-3 text-slate-400" />
                      {formatLatency(message.latencyMs)}
                    </span>
                  )}
                  <span>Dual-LLM (Gemini + Groq)</span>
                </div>
                <button
                  onClick={handleCopyAnswer}
                  className="flex items-center gap-1 px-2 py-0.5 rounded text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                >
                  {copied ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
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
        <div className="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 p-0.5 shrink-0 flex items-center justify-center text-slate-300 mt-1">
          <User className="w-4 h-4" />
        </div>
      )}
    </div>
  );
};
