"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import {
  FolderGit2,
  Layers,
  Share2,
  Bot,
  GitPullRequest,
  Activity,
  Settings,
  ChevronDown,
  Check,
  Plus,
  LogOut,
  Hammer,
  Users,
  Search,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { useTeamStore } from "../../store/teamStore";
import { useProjectStore } from "../../store/projectStore";
import { useBuildStore } from "../../store/buildStore";
import { GitamiLogo } from "./GitamiLogo";
import { CreateTeamModal } from "../teams/CreateTeamModal";

interface SidebarProps {
  onOpenSearch?: () => void;
  onOpenAddProject?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ onOpenSearch, onOpenAddProject }) => {
  const params = useParams();
  const pathname = usePathname();
  const router = useRouter();

  const teamSlug = (params?.teamSlug as string) || "";
  const projectSlug = (params?.projectSlug as string) || "";

  const { token, user, logout } = useAuthStore();
  const { teams, activeTeam, setActiveTeam, fetchTeams } = useTeamStore();
  const { projects, activeProject } = useProjectStore();
  const { getActiveBuilds } = useBuildStore();

  const [isTeamSwitcherOpen, setIsTeamSwitcherOpen] = useState(false);
  const [isCreateTeamOpen, setIsCreateTeamOpen] = useState(false);

  const teamSwitcherRef = useRef<HTMLDivElement>(null);

  const activeBuilds = getActiveBuilds();
  const runningBuildCount = activeBuilds.length;

  const currentTeam = teams.find((t) => t.slug === teamSlug) || activeTeam || teams[0];

  // Fetch teams on mount if not yet loaded
  useEffect(() => {
    if (token && teams.length === 0) {
      fetchTeams(token);
    }
  }, [token, teams.length, fetchTeams]);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (teamSwitcherRef.current && !teamSwitcherRef.current.contains(e.target as Node)) {
        setIsTeamSwitcherOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

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
    <>
      <aside className="w-56 bg-[#0e1017] border-r border-white/[0.06] flex flex-col h-screen select-none z-30 shrink-0 text-zinc-300">
        {/* 1. Header: GitAmi */}
        <div className="h-14 px-4 border-b border-white/[0.06] flex items-center justify-between">
          <GitamiLogo href={`/${teamSlug || ""}`} size="sm" />
          <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 bg-white/[0.04] px-1.5 py-0.5 rounded border border-white/[0.06]">
            v1
          </span>
        </div>

        {/* 2. Team Switcher */}
        <div className="p-3 border-b border-white/[0.06]">
          <div className="relative" ref={teamSwitcherRef}>
            <button
              onClick={() => setIsTeamSwitcherOpen(!isTeamSwitcherOpen)}
              className="w-full flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-md bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] transition-colors text-left cursor-pointer"
            >
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-4 h-4 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center text-[10px] font-bold shrink-0">
                  <Users className="w-2.5 h-2.5" />
                </div>
                <span className="text-xs font-medium text-zinc-200 truncate">
                  {currentTeam?.name || "Select Team"}
                </span>
              </div>
              <ChevronDown
                className={`w-3.5 h-3.5 text-zinc-400 transition-transform ${
                  isTeamSwitcherOpen ? "rotate-180" : ""
                }`}
              />
            </button>

            {isTeamSwitcherOpen && (
              <div className="absolute left-0 right-0 top-full mt-1 bg-[#13151f] border border-white/[0.08] rounded-lg shadow-2xl py-1 z-50 animate-fade-in text-xs">
                <div className="px-2.5 py-1 text-[10px] uppercase font-mono text-zinc-500 font-semibold tracking-wider">
                  Teams
                </div>
                <div className="max-h-40 overflow-y-auto py-0.5">
                  {teams.map((t) => {
                    const isSelected = t.slug === currentTeam?.slug;
                    return (
                      <button
                        key={t.id}
                        onClick={() => {
                          setIsTeamSwitcherOpen(false);
                          setActiveTeam(t);
                          if (pathname.includes("/settings")) {
                            router.push(`/${t.slug}/settings`);
                          } else if (pathname.includes("/activity")) {
                            router.push(`/${t.slug}/activity`);
                          } else {
                            router.push(`/${t.slug}`);
                          }
                        }}
                        className={`w-full flex items-center justify-between px-2.5 py-1.5 hover:bg-white/[0.05] text-left transition-colors cursor-pointer ${
                          isSelected ? "text-white font-medium bg-white/[0.06]" : "text-zinc-400"
                        }`}
                      >
                        <span className="truncate pr-2">{t.name}</span>
                        {isSelected && <Check className="w-3 h-3 text-indigo-400 shrink-0" />}
                      </button>
                    );
                  })}
                </div>
                <div className="border-t border-white/[0.06] mt-1 pt-1 px-1">
                  <button
                    onClick={() => {
                      setIsTeamSwitcherOpen(false);
                      setIsCreateTeamOpen(true);
                    }}
                    className="w-full flex items-center gap-1.5 px-2 py-1 text-xs text-zinc-400 hover:text-white hover:bg-white/[0.05] rounded transition-colors cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Create Team</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Search Trigger */}
          <div className="mt-2">
            <button
              onClick={onOpenSearch}
              className="w-full flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-md bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] text-xs text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <Search className="w-3.5 h-3.5 text-zinc-500" />
                <span>Search...</span>
              </div>
              <kbd className="px-1 py-0.2 text-[9px] font-mono bg-white/[0.04] text-zinc-500 rounded border border-white/[0.06]">
                ⌘K
              </kbd>
            </button>
          </div>
        </div>

        {/* 3. Navigation Sections: PROJECT, WORKSPACE, Settings */}
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

      {/* Modals */}
      <CreateTeamModal
        isOpen={isCreateTeamOpen}
        onClose={() => setIsCreateTeamOpen(false)}
        onSuccess={(newSlug) => {
          router.push(`/${newSlug}`);
        }}
      />
    </>
  );
};
