"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Shield,
  Bot,
  GitFork,
  Database,
  Share2,
  Terminal,
  Activity,
  Layers,
  Sparkles,
  Plus,
  ArrowUpRight,
} from "lucide-react";
import { useRepoStore } from "../../store/repoStore";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";

export const Sidebar: React.FC = () => {
  const pathname = usePathname();
  const { connectedRepos, indexedRepos } = useRepoStore();

  const coreNav = [
    { href: "/dashboard", label: "Overview", icon: <Layers className="w-4 h-4" /> },
    {
      href: "/chat",
      label: "Agentic RAG Chat",
      icon: <Bot className="w-4 h-4" />,
      badge: "ReAct",
    },
    {
      href: "/repositories",
      label: "Connected Repos",
      icon: <GitFork className="w-4 h-4" />,
      count: connectedRepos.length,
    },
  ];

  const intelligenceNav = [
    {
      href: "/graph",
      label: "Code Graph & AST",
      icon: <Share2 className="w-4 h-4" />,
      badge: "Neo4j",
    },
    {
      href: "/ingest",
      label: "Ingest Knowledge Base",
      icon: <Database className="w-4 h-4" />,
    },
  ];

  return (
    <aside className="w-64 glass-panel rounded-3xl border border-slate-800/80 p-4 flex flex-col justify-between hidden lg:flex shrink-0 min-h-[calc(100vh-5.5rem)] shadow-lg shadow-black/20">
      <div className="space-y-6">
        {/* Core Section */}
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-3 mb-2 font-mono">
            Core Platform
          </p>
          <nav className="space-y-1">
            {coreNav.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-2xl text-xs font-semibold transition-all duration-150 ${
                    isActive
                      ? "bg-indigo-600/20 text-indigo-200 border border-indigo-500/40 shadow-sm shadow-indigo-600/10"
                      : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className={isActive ? "text-indigo-400" : "text-slate-500"}>
                      {item.icon}
                    </span>
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <Badge variant="primary" size="sm" className="text-[9px] py-0 px-1.5 font-mono">
                      {item.badge}
                    </Badge>
                  )}
                  {item.count !== undefined && (
                    <span className="text-[10px] bg-slate-800/90 text-slate-300 border border-slate-700/60 px-1.5 py-0.2 rounded-md font-mono font-semibold">
                      {item.count}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Intelligence & KB Section */}
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-3 mb-2 font-mono">
            Intelligence & Graph
          </p>
          <nav className="space-y-1">
            {intelligenceNav.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-2xl text-xs font-semibold transition-all duration-150 ${
                    isActive
                      ? "bg-indigo-600/20 text-indigo-200 border border-indigo-500/40 shadow-sm shadow-indigo-600/10"
                      : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className={isActive ? "text-cyan-400" : "text-slate-500"}>
                      {item.icon}
                    </span>
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <Badge variant="info" size="sm" className="text-[9px] py-0 px-1.5 font-mono">
                      {item.badge}
                    </Badge>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Active Knowledge Bases Quick Launcher */}
        <div>
          <div className="flex items-center justify-between px-3 mb-2">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
              Active Indexes
            </p>
            <span className="text-[10px] font-mono font-semibold text-cyan-400">
              {indexedRepos.length} Spaces
            </span>
          </div>
          <div className="space-y-1">
            {indexedRepos.length > 0 ? (
              indexedRepos.slice(0, 4).map((repo) => (
                <Link
                  key={repo}
                  href={`/chat?repo=${encodeURIComponent(repo)}`}
                  className="flex items-center justify-between px-3 py-1.5 rounded-xl text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 truncate font-mono transition-colors group"
                  title={repo}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0" />
                    <span className="truncate">{repo}</span>
                  </div>
                  <ArrowUpRight className="w-3 h-3 text-slate-600 group-hover:text-cyan-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                </Link>
              ))
            ) : (
              <p className="text-[11px] text-slate-500 italic px-3 py-1">
                No active indexes yet
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Footer Info Box + Quick Ingest Button */}
      <div className="space-y-2 pt-4 border-t border-slate-800/80">
        <Link href="/ingest" className="block">
          <Button
            variant="outline"
            size="sm"
            leftIcon={<Plus className="w-3.5 h-3.5 text-indigo-400" />}
            className="w-full text-xs py-2 bg-indigo-950/20 border-indigo-900/50 hover:bg-indigo-950/50 text-indigo-300"
          >
            Ingest New Codebase
          </Button>
        </Link>

        <div className="p-3 rounded-2xl bg-gradient-to-br from-indigo-950/60 via-slate-900 to-slate-950 border border-indigo-900/40 relative overflow-hidden">
          <div className="flex items-center gap-1.5 mb-1">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-[11px] font-bold text-indigo-200">Dual-KB Engine</span>
          </div>
          <p className="text-[10px] text-slate-400 leading-relaxed">
            Neo4j AST graph + ChromaDB vector embeddings with Gemini & Groq.
          </p>
        </div>
      </div>
    </aside>
  );
};

