"use client";

import React from "react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import {
  FolderGit2,
  Layers,
  Share2,
  Bot,
  GitPullRequest,
  Activity,
  Settings,
  LogOut,
  Hammer,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { useTeamStore } from "../../store/teamStore";
import { useProjectStore } from "../../store/projectStore";
import { useBuildStore } from "../../store/buildStore";
import { GitamiLogo } from "./GitamiLogo";

interface SidebarProps {
  onOpenSearch?: () => void;
  onOpenAddProject?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ onOpenAddProject }) => {
  const params = useParams();
  const pathname = usePathname();

  const teamSlug = (params?.teamSlug as string) || "";
  const projectSlug = (params?.projectSlug as string) || "";

  const { user, logout } = useAuthStore();
  const { teams, activeTeam } = useTeamStore();
  const { projects, activeProject } = useProjectStore();
  const { getActiveBuilds } = useBuildStore();

  const activeBuilds = getActiveBuilds();
  const runningBuildCount = activeBuilds.length;

  const currentTeam = teams.find((t) => t.slug === teamSlug) || activeTeam || teams[0];
  const currentTeamSlug = teamSlug || currentTeam?.slug || "";
  const effectiveProjectSlug = projectSlug || activeProject?.slug || (projects[0]?.slug ?? "");
  const hasProject = Boolean(currentTeamSlug && effectiveProjectSlug);
  const projectBase = hasProject ? `/${currentTeamSlug}/${effectiveProjectSlug}` : `/${currentTeamSlug}`;

  const projectNavItems = [
    {
      name: "Overview",
      href: projectBase,
      icon: Layers,
      isActive: pathname === projectBase,
    },
    {
      name: "Repositories",
      href: `${projectBase}/repositories`,
      icon: FolderGit2,
      isActive: pathname.startsWith(`${projectBase}/repositories`),
    },
    {
      name: "Knowledge Sync",
      href: `${projectBase}/builds`,
      icon: Hammer,
      isActive: pathname.startsWith(`${projectBase}/builds`),
      badge: runningBuildCount > 0 ? `${runningBuildCount} active` : undefined,
      isPulsing: runningBuildCount > 0,
    },
    {
      name: "Knowledge Map",
      href: `${projectBase}/graph`,
      icon: Share2,
      isActive: pathname.startsWith(`${projectBase}/graph`),
    },
    {
      name: "Intelligence Chat",
      href: `${projectBase}/chat`,
      icon: Bot,
      isActive: pathname.startsWith(`${projectBase}/chat`),
    },
    {
      name: "PR Audits",
      href: `${projectBase}/prs`,
      icon: GitPullRequest,
      isActive: pathname.startsWith(`${projectBase}/prs`),
    },
  ];

  const workspaceNavItems = [
    {
      name: "Projects",
      href: `/${teamSlug}`,
      icon: Layers,
      isActive: pathname === `/${teamSlug}`,
    },
    {
      name: "Activity",
      href: `/${teamSlug}/activity`,
      icon: Activity,
      isActive: pathname.startsWith(`/${teamSlug}/activity`),
    },
  ];

  return (
    <aside className="w-56 bg-[#0e1017] border-r border-white/[0.06] flex flex-col h-screen select-none z-30 shrink-0 text-zinc-300">
        {/* 1. Header: GitAmi */}
        <div className="h-14 px-4 border-b border-white/[0.06] flex items-center justify-between">
          <GitamiLogo href={`/${teamSlug || ""}`} size="sm" />
          <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 bg-white/[0.04] px-1.5 py-0.5 rounded border border-white/[0.06]">
            v1
          </span>
        </div>

        {/* 2. Navigation Sections: PROJECT, WORKSPACE, Settings */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
          {/* PROJECT Navigation */}
          {hasProject ? (
            <div>
              <div className="px-2.5 mb-1.5 text-[10px] font-mono uppercase tracking-wider text-zinc-500 font-semibold">
                Project
              </div>
              <nav className="space-y-0.5">
                {projectNavItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.name}
                      href={item.href}
                      className={`flex items-center justify-between px-2.5 py-1.5 rounded-md text-xs transition-colors ${
                        item.isActive
                          ? "bg-white/[0.08] text-white font-medium"
                          : "text-zinc-400 hover:text-zinc-100 hover:bg-white/[0.04]"
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <Icon className="w-3.5 h-3.5 text-zinc-400" />
                        <span>{item.name}</span>
                      </div>
                      {item.badge && (
                        <span
                          className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                            item.isPulsing
                              ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 animate-pulse"
                              : "bg-white/[0.05] text-zinc-400"
                          }`}
                        >
                          {item.badge}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </nav>
            </div>
          ) : (
            <div className="px-2.5 py-3 rounded-lg bg-white/[0.02] border border-white/[0.05] text-center">
              <p className="text-[11px] text-zinc-400 mb-2">No project selected</p>
              {onOpenAddProject && (
                <button
                  onClick={onOpenAddProject}
                  className="w-full text-xs font-medium text-white bg-white/[0.08] hover:bg-white/[0.12] py-1 px-2 rounded transition-colors cursor-pointer"
                >
                  + Add Project
                </button>
              )}
            </div>
          )}

          {/* WORKSPACE Navigation */}
          <div>
            <div className="px-2.5 mb-1.5 text-[10px] font-mono uppercase tracking-wider text-zinc-500 font-semibold">
              Workspace
            </div>
            <nav className="space-y-0.5">
              {workspaceNavItems.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`flex items-center justify-between px-2.5 py-1.5 rounded-md text-xs transition-colors ${
                      item.isActive
                        ? "bg-white/[0.08] text-white font-medium"
                        : "text-zinc-400 hover:text-zinc-100 hover:bg-white/[0.04]"
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon className="w-3.5 h-3.5 text-zinc-400" />
                      <span>{item.name}</span>
                    </div>
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Settings */}
          <div>
            <nav className="space-y-0.5">
              <Link
                href={`/${teamSlug}/settings`}
                className={`flex items-center justify-between px-2.5 py-1.5 rounded-md text-xs transition-colors ${
                  pathname.startsWith(`/${teamSlug}/settings`)
                    ? "bg-white/[0.08] text-white font-medium"
                    : "text-zinc-400 hover:text-zinc-100 hover:bg-white/[0.04]"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Settings className="w-3.5 h-3.5 text-zinc-400" />
                  <span>Settings</span>
                </div>
              </Link>
            </nav>
          </div>
        </div>

        {/* 4. Bottom User Profile */}
        <div className="p-3 border-t border-white/[0.06] flex items-center justify-between">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-7 h-7 rounded-full bg-white/[0.06] border border-white/[0.08] flex items-center justify-center text-xs font-bold text-zinc-300 shrink-0">
              {(user?.username || "U").charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0">
              <div className="text-xs font-medium text-white truncate">
                {user?.name || user?.username || "Developer"}
              </div>
              <div className="text-[10px] text-zinc-500 truncate font-mono">
                {user?.email || "Personal"}
              </div>
            </div>
          </div>

          <button
            onClick={() => logout()}
            className="p-1.5 text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.05] rounded transition-colors cursor-pointer"
            title="Sign out"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </aside>
  );
};
