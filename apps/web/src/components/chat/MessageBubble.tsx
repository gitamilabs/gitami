"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { DisplayMessage } from "../../store/chatStore";
import { ThinkingProcess } from "./ThinkingProcess";
import { CitationCard } from "./CitationCard";
import { formatLatency } from "../../lib/utils";
import {
  User,
  Bot,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Clock,
  Check,
  Copy,
  BookOpen,
} from "lucide-react";

interface MessageBubbleProps {
  message: DisplayMessage;
  teamSlug?: string;
  projectSlug?: string;
  repoId?: string;
}

const CodeBlock: React.FC<{ language: string; code: string }> = ({ language, code }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-xl border border-white/[0.08] bg-[#090a0f] overflow-hidden text-xs font-mono shadow-sm">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-white/[0.03] border-b border-white/[0.06] text-zinc-400 select-none">
        <span className="text-[11px] font-medium text-zinc-400 lowercase">{language || "code"}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 text-[11px] hover:text-zinc-200 transition-colors cursor-pointer py-0.5 px-1 rounded hover:bg-white/[0.04]"
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
      <div className="p-3.5 overflow-x-auto leading-relaxed text-zinc-200 font-mono text-[12px]">
        <pre>{code}</pre>
      </div>
    </div>
  );
};

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  teamSlug,
  projectSlug,
  repoId,
}) => {
  const isUser = message.role === "user";
  const [citationsOpen, setCitationsOpen] = useState(false);
  const [copiedAnswer, setCopiedAnswer] = useState(false);

  const handleCopyAnswer = () => {
    navigator.clipboard.writeText(message.content);
    setCopiedAnswer(true);
    setTimeout(() => setCopiedAnswer(false), 2000);
  };

  return (
    <div
      className={`flex gap-3.5 my-5 ${
        isUser ? "justify-end" : "justify-start"
      } animate-fade-in`}
    >
      {!isUser && (
        <div className="w-7 h-7 rounded-lg bg-white/[0.04] border border-white/[0.08] shrink-0 flex items-center justify-center mt-0.5 text-zinc-300">
          <Sparkles className="w-3.5 h-3.5 text-zinc-400" />
        </div>
      )}

      <div
        className={`max-w-3xl w-full ${
          isUser
            ? "bg-white/[0.08] text-white rounded-2xl rounded-tr-sm border border-white/[0.1] px-4 py-3 ml-auto max-w-xl"
            : "text-zinc-200 space-y-3"
        }`}
      >
        {isUser ? (
          <p className="text-xs sm:text-sm font-normal whitespace-pre-wrap leading-relaxed">
            {message.content}
          </p>
        ) : (
          <div className="space-y-3">
            {/* Sequential single-line connected dots thinking & tool pipeline */}
            {(message.reasoningTimeline?.length || message.thoughts?.length || message.toolSteps?.length || message.isStreaming) ? (
              <ThinkingProcess
                thoughts={message.thoughts}
                toolSteps={message.toolSteps}
                reasoningTimeline={message.reasoningTimeline}
                isStreaming={message.isStreaming}
                latencyMs={message.latencyMs}
              />
            ) : null}

            {/* Synthesized Answer Body with Markdown & Interactive Code Blocks */}
            {message.content ? (
              <div className="prose-custom text-xs sm:text-sm leading-relaxed text-zinc-200">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    code({ node, className, children, ...props }: any) {
                      const match = /language-(\w+)/.exec(className || "");
                      const codeString = String(children).replace(/\n$/, "");
                      const isMulti = codeString.includes("\n") || Boolean(match);

                      if (isMulti) {
                        return <CodeBlock language={match ? match[1] : ""} code={codeString} />;
                      }
                      return (
                        <code
                          className="px-1.5 py-0.5 rounded bg-white/[0.06] border border-white/[0.08] font-mono text-[11px] text-zinc-200"
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    },
                    p({ children }: any) {
                      return <p className="mb-2.5 last:mb-0 leading-relaxed">{children}</p>;
                    },
                    ul({ children }: any) {
                      return <ul className="list-disc pl-5 mb-2.5 space-y-1">{children}</ul>;
                    },
                    ol({ children }: any) {
                      return <ol className="list-decimal pl-5 mb-2.5 space-y-1">{children}</ol>;
                    },
                    li({ children }: any) {
                      return <li className="leading-relaxed">{children}</li>;
                    },
                    h1({ children }: any) {
                      return <h1 className="text-base font-semibold text-white mt-4 mb-2">{children}</h1>;
                    },
                    h2({ children }: any) {
                      return <h2 className="text-sm font-semibold text-white mt-3 mb-1.5">{children}</h2>;
                    },
                    h3({ children }: any) {
                      return <h3 className="text-xs font-semibold text-zinc-200 mt-2.5 mb-1">{children}</h3>;
                    },
                    blockquote({ children }: any) {
                      return (
                        <blockquote className="border-l-2 border-white/20 pl-3 my-2 text-zinc-400 italic">
                          {children}
                        </blockquote>
                      );
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            ) : message.isStreaming ? (
              <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono py-1">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                <span>Generating response...</span>
              </div>
            ) : null}

            {/* Proof & Evidence Citations (APPEAR ONLY ON CLICK) */}
            {message.citations && message.citations.length > 0 && (
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => setCitationsOpen(!citationsOpen)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/[0.03] hover:bg-white/[0.06] text-zinc-400 hover:text-zinc-200 border border-white/[0.06] transition-colors cursor-pointer select-none"
                >
                  <BookOpen className="w-3.5 h-3.5 text-zinc-400" />
                  <span>{message.citations.length} sources & proof</span>
                  {citationsOpen ? (
                    <ChevronUp className="w-3 h-3 text-zinc-500" />
                  ) : (
                    <ChevronDown className="w-3 h-3 text-zinc-500" />
                  )}
                </button>

                {citationsOpen && (
                  <div className="grid grid-cols-1 gap-2 pt-3 animate-fade-in">
                    {message.citations.map((citation) => (
                      <CitationCard
                        key={citation.id}
                        citation={citation}
                        teamSlug={teamSlug}
                        projectSlug={projectSlug}
                        repoId={repoId}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Message Action Footer */}
            {!message.isStreaming && message.content && (
              <div className="flex items-center justify-between text-[11px] text-zinc-500 pt-1 font-mono">
                <div className="flex items-center gap-2">
                  {message.latencyMs && message.latencyMs > 0 ? (
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      <span>{formatLatency(message.latencyMs)}</span>
                    </span>
                  ) : null}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleCopyAnswer}
                    className="flex items-center gap-1 px-2 py-0.5 rounded text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04] transition-colors cursor-pointer"
                    title="Copy response"
                  >
                    {copiedAnswer ? (
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
              </div>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-7 h-7 rounded-lg bg-white/[0.06] border border-white/[0.08] shrink-0 flex items-center justify-center mt-0.5 text-zinc-300">
          <User className="w-3.5 h-3.5" />
        </div>
      )}
    </div>
  );
};
