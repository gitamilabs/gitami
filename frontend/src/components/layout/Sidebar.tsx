"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  FolderGit2,
  GitPullRequest,
  Bot,
  Activity,
  Settings,
  Search,
  ChevronDown,
  LogOut,
  Plus,
  ExternalLink,
  ShieldCheck,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { AddProjectModal } from "../repositories/AddProjectModal";
import { useRepoStore } from "../../store/repoStore";

const navItems = [
  { name: "Projects", href: "/dashboard", icon: FolderGit2, exact: true },
  { name: "PR Reviews", href: "/prs", icon: GitPullRequest, badge: "Agent" },
  { name: "Codebase Chat", href: "/chat", icon: Bot, badge: "ReAct" },
  { name: "VulAgent Benchmark", href: "/benchmark", icon: ShieldCheck, badge: "VulAgentRL" },
  { name: "Activity Logs", href: "/activity", icon: Activity },
  { name: "Settings", href: "/settings", icon: Settings },
];

export const Sidebar: React.FC = () => {
  const pathname = usePathname();
  const { user, token, logout } = useAuthStore();
  const { fetchConnectedRepos, fetchIndexedRepos } = useRepoStore();
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  const displayName = user?.name || user?.username || "Developer Workspace";
  const displayAvatar = user?.avatarUrl;

  return (
    <aside className="w-64 bg-[#0a0a0a] border-r border-zinc-800/80 flex flex-col h-screen sticky top-0 select-none z-30 shrink-0">
      {/* Workspace Identifier */}
      <div className="p-3 border-b border-zinc-800/60">
        <div className="flex items-center justify-between px-2 py-1.5 rounded-lg">
          <div className="flex items-center gap-2.5 min-w-0">
            {displayAvatar ? (
              <img
                src={displayAvatar}
                alt={displayName}
                className="w-6 h-6 rounded-full border border-zinc-700 object-cover shrink-0"
              />
            ) : (
              <div className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center text-xs font-bold shrink-0">
                {displayName.charAt(0).toUpperCase()}
              </div>
            )}
            <span className="text-xs font-semibold text-zinc-200 truncate">
              {displayName}
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-zinc-800 text-zinc-400 border border-zinc-700/60 shrink-0">
              Personal
            </span>
          </div>
        </div>

        {/* Search (jumps to Projects, where the real search box lives) */}
        <Link
          href="/dashboard"
          className="mt-2.5 flex items-center justify-between w-full px-2.5 py-1.5 bg-zinc-900/90 border border-zinc-800/80 rounded-md text-xs text-zinc-400 hover:border-zinc-700 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Search className="w-3.5 h-3.5 text-zinc-500" />
            <span>Find...</span>
          </div>
          <kbd className="px-1.5 py-0.5 text-[10px] font-mono bg-zinc-800 text-zinc-400 rounded border border-zinc-700/60">
            F
          </kbd>
        </Link>
      </div>

      {/* Navigation Items */}
      <div className="flex-1 px-2 py-3 space-y-1 overflow-y-auto">
        <div className="px-2 pb-1.5 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
          Features & Agents
        </div>

        {navItems.map((item) => {
          const isActive = item.exact
            ? pathname === item.href
            : pathname === item.href || pathname.startsWith(item.href + "/");
          const Icon = item.icon;

          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center justify-between px-2.5 py-2 rounded-md text-xs font-medium transition-all group ${
                isActive
                  ? "bg-zinc-800/90 text-white font-semibold"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Icon
                  className={`w-4 h-4 transition-colors ${
                    isActive ? "text-white" : "text-zinc-400 group-hover:text-zinc-200"
                  }`}
                />
                <span>{item.name}</span>
              </div>
              {item.badge && (
                <span
                  className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${
                    isActive
                      ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                      : "bg-zinc-800 text-zinc-400"
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </div>

      {/* Action Button */}
      <div className="px-3 pb-3">
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-md bg-white hover:bg-zinc-200 text-black font-medium text-xs transition-colors shadow-xs cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Add New Project</span>
        </button>
      </div>

      {/* Footer User Info */}
      <div className="p-3 border-t border-zinc-800/60 relative">
        <div
          onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
          className="flex items-center justify-between p-1.5 rounded-lg hover:bg-zinc-900 transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2.5 min-w-0">
            {displayAvatar ? (
              <img
                src={displayAvatar}
                alt={displayName}
                className="w-7 h-7 rounded-full border border-zinc-700 object-cover shrink-0"
              />
            ) : (
              <div className="w-7 h-7 rounded-full bg-zinc-800 text-zinc-300 border border-zinc-700 flex items-center justify-center text-xs font-bold shrink-0">
                {displayName.charAt(0).toUpperCase()}
              </div>
            )}
            <div className="min-w-0">
              <div className="text-xs font-medium text-zinc-200 truncate">
                {displayName}
              </div>
              <div className="text-[10px] text-zinc-500 truncate">
                {user?.email || "Connected"}
              </div>
            </div>
          </div>
          <ChevronDown className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
        </div>

        {isUserMenuOpen && (
          <div className="absolute bottom-full left-3 right-3 mb-2 bg-[#121212] border border-zinc-800 rounded-lg shadow-xl p-1.5 space-y-0.5 z-50">
            <Link
              href="/settings"
              onClick={() => setIsUserMenuOpen(false)}
              className="flex items-center gap-2 w-full px-2.5 py-1.5 text-xs text-zinc-300 hover:text-white hover:bg-zinc-800 rounded-md transition-colors"
            >
              <Settings className="w-3.5 h-3.5 text-zinc-400" />
              <span>Settings</span>
            </Link>
            <a
              href="https://github.com/settings/installations"
              target="_blank"
              rel="noreferrer"
              onClick={() => setIsUserMenuOpen(false)}
              className="flex items-center justify-between w-full px-2.5 py-1.5 text-xs text-zinc-300 hover:text-white hover:bg-zinc-800 rounded-md transition-colors"
            >
              <span className="flex items-center gap-2">
                <ExternalLink className="w-3.5 h-3.5 text-zinc-400" />
                <span>GitHub App Settings</span>
              </span>
            </a>
            <div className="h-[1px] bg-zinc-800 my-1" />
            <button
              onClick={() => {
                setIsUserMenuOpen(false);
                logout();
              }}
              className="flex items-center gap-2 w-full px-2.5 py-1.5 text-xs text-red-400 hover:text-red-300 hover:bg-red-950/40 rounded-md transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Log out</span>
            </button>
          </div>
        )}
      </div>

      <AddProjectModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSuccess={() => {
          if (token) {
            fetchConnectedRepos(token, true);
            fetchIndexedRepos(token, true);
          }
        }}
      />
    </aside>
  );
};
