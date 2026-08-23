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
} from "lucide-react";
import { useRepoStore } from "../../store/repoStore";
import { Badge } from "../ui/Badge";

export const Sidebar: React.FC = () => {
  const pathname = usePathname();
  const { connectedRepos, indexedRepos } = useRepoStore();

  const mainNav = [
    { href: "/dashboard", label: "Overview", icon: <Layers className="w-4 h-4" /> },
    {
      href: "/chat",
      label: "Agentic RAG Chat",
      icon: <Bot className="w-4 h-4" />,
      badge: "ReAct",
    },
    {
      href: "/repositories",
      label: "GitHub Repositories",
      icon: <GitFork className="w-4 h-4" />,
      count: connectedRepos.length,
    },
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
    <aside className="w-64 glass-panel border-r border-slate-800/80 p-4 flex flex-col justify-between hidden lg:flex shrink-0 min-h-[calc(100vh-4rem)]">
      <div className="space-y-6">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 px-3 mb-2">
            Navigation
          </p>
          <nav className="space-y-1">
            {mainNav.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                    isActive
                      ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/40 shadow-sm shadow-indigo-600/10"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className={isActive ? "text-indigo-400" : "text-slate-400"}>
                      {item.icon}
                    </span>
                    {item.label}
                  </div>
                  {item.badge && (
                    <Badge variant="primary" size="sm" className="text-[10px] py-0 px-1.5 font-mono">
                      {item.badge}
                    </Badge>
                  )}
                  {item.count !== undefined && item.count > 0 && (
                    <span className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded-full font-mono">
                      {item.count}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Indexed Repos Quick View */}
        <div>
          <div className="flex items-center justify-between px-3 mb-2">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Active Indexes
            </p>
            <span className="text-[10px] font-mono text-cyan-400">
              {indexedRepos.length} KB
            </span>
          </div>
          <div className="space-y-1">
            {indexedRepos.slice(0, 4).map((repo) => (
              <Link
                key={repo}
                href={`/chat?repo=${encodeURIComponent(repo)}`}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 truncate font-mono transition-colors"
                title={repo}
              >
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0" />
                <span className="truncate">{repo}</span>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* Footer Banner */}
      <div className="p-3 rounded-2xl bg-gradient-to-br from-indigo-950/60 to-slate-900 border border-indigo-900/40 relative overflow-hidden">
        <div className="flex items-center gap-2 mb-1.5">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          <span className="text-xs font-semibold text-indigo-200">Dual-KB Engine</span>
        </div>
        <p className="text-[11px] text-slate-400 leading-relaxed">
          Neo4j AST graph + ChromaDB vector embeddings with Gemini & Groq.
        </p>
      </div>
    </aside>
  );
};
