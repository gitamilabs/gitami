"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import {
  ChevronRight,
  ChevronDown,
  Plus,
  Bell,
  Search,
  Hammer,
  Check,
  FolderGit2,
  FolderPlus,
  LogOut,
  User as UserIcon,
} from "lucide-react";
import { useTeamStore } from "../../store/teamStore";
import { useProjectStore } from "../../store/projectStore";
import { useBuildStore } from "../../store/buildStore";
import { useAuthStore } from "../../store/authStore";
import { CreateTeamModal } from "../teams/CreateTeamModal";
import { CreateProjectModal } from "../projects/CreateProjectModal";
import { ConnectRepositoryModal } from "../repositories/ConnectRepositoryModal";

interface TopBarProps {
  onOpenSearch?: () => void;
  onOpenAddProject?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ onOpenSearch, onOpenAddProject }) => {
  const params = useParams();
  const pathname = usePathname();
  const router = useRouter();

  const teamSlug = (params?.teamSlug as string) || "";
  const projectSlug = (params?.projectSlug as string) || "";

  const { token, user, logout } = useAuthStore();
  const { teams, activeTeam, fetchTeams, setActiveTeam } = useTeamStore();
  const { projects, activeProject, fetchTeamProjects, setActiveProject, fetchProjectDetails } = useProjectStore();
  const { getActiveBuilds } = useBuildStore();

  const [isTeamMenuOpen, setIsTeamMenuOpen] = useState(false);
  const [isProjectMenuOpen, setIsProjectMenuOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  const [isCreateTeamOpen, setIsCreateTeamOpen] = useState(false);
  const [isCreateProjectOpen, setIsCreateProjectOpen] = useState(false);
  const [isConnectRepoOpen, setIsConnectRepoOpen] = useState(false);

  const teamMenuRef = useRef<HTMLDivElement>(null);
  const projectMenuRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  const activeBuilds = getActiveBuilds();
  const runningBuild = activeBuilds[0];

  // Fetch teams on mount only if empty
  useEffect(() => {
    if (token && teams.length === 0) {
      fetchTeams(token);
    }
  }, [token, teams.length, fetchTeams]);

  // Fetch projects when teamSlug changes
  useEffect(() => {
    if (token && teamSlug) {
      fetchTeamProjects(token, teamSlug);
    }
  }, [token, teamSlug, fetchTeamProjects]);

  // Close menus on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (teamMenuRef.current && !teamMenuRef.current.contains(e.target as Node)) {
        setIsTeamMenuOpen(false);
      }
      if (projectMenuRef.current && !projectMenuRef.current.contains(e.target as Node)) {
        setIsProjectMenuOpen(false);
      }
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setIsUserMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Determine section name
  let currentSection = "Overview";
  if (pathname.includes("/repositories")) currentSection = "Repositories";
  else if (pathname.includes("/builds")) currentSection = "Builds";
  else if (pathname.includes("/graph")) currentSection = "Graph";
  else if (pathname.includes("/chat")) currentSection = "Chat";
  else if (pathname.includes("/prs")) currentSection = "PR Reviews";
  else if (pathname.includes("/activity")) currentSection = "Activity";
  else if (pathname.includes("/settings")) currentSection = "Settings";

  const currentTeam = teams.find((t) => t.slug === teamSlug) || activeTeam || teams[0];
  const currentProject = projects.find((p) => p.slug === projectSlug) || activeProject;

  return (
    <>
      <header className="h-14 border-b border-white/[0.06] bg-[#0c0d12]/85 backdrop-blur-md px-5 flex items-center justify-between shrink-0 select-none z-20">
        {/* Left: Context Breadcrumbs: [ Team ] / [ Project ] / Current Section */}
        <div className="flex items-center gap-1.5 text-xs">
          {/* 1. Team Switcher */}
          <div className="relative" ref={teamMenuRef}>
            <button
              onClick={() => setIsTeamMenuOpen(!isTeamMenuOpen)}
              className="flex items-center gap-1.5 px-2 py-1 rounded-md hover:bg-white/[0.05] text-zinc-300 hover:text-white font-medium transition-colors cursor-pointer"
            >
              <span className="truncate max-w-[130px]">
                {currentTeam?.name || "Select Team"}
              </span>
              <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
            </button>

            {isTeamMenuOpen && (
              <div className="absolute left-0 top-full mt-1.5 w-56 bg-[#13151f] border border-white/[0.08] rounded-lg shadow-2xl py-1 z-40 animate-fade-in">
                <div className="px-3 py-1.5 text-[10px] font-mono uppercase text-zinc-500 tracking-wider">
                  Teams & Workspaces
                </div>
                {teams.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => {
                      setIsTeamMenuOpen(false);
                      setActiveTeam(t);
                      if (pathname.includes("/settings")) {
                        router.push(`/${t.slug}/settings`);
                      } else if (pathname.includes("/activity")) {
                        router.push(`/${t.slug}/activity`);
                      } else {
                        router.push(`/${t.slug}`);
                      }
                    }}
                    className="w-full px-3 py-1.5 text-left text-xs flex items-center justify-between text-zinc-300 hover:text-white hover:bg-white/[0.05] transition-colors"
                  >
                    <span className="truncate font-medium">{t.name}</span>
                    {t.slug === currentTeam?.slug && (
                      <Check className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                    )}
                  </button>
                ))}
                <div className="border-t border-white/[0.06] my-1" />
                <button
                  onClick={() => {
                    setIsTeamMenuOpen(false);
                    setIsCreateTeamOpen(true);
                  }}
                  className="w-full px-3 py-1.5 text-left text-xs flex items-center gap-2 text-zinc-400 hover:text-white hover:bg-white/[0.05] transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Create Team</span>
                </button>
              </div>
            )}
          </div>

          {/* Slash Separator */}
          {projectSlug && (
            <>
              <span className="text-zinc-600 font-light">/</span>

              {/* 2. Project Switcher */}
              <div className="relative" ref={projectMenuRef}>
                <button
                  onClick={() => setIsProjectMenuOpen(!isProjectMenuOpen)}
                  className="flex items-center gap-1.5 px-2 py-1 rounded-md hover:bg-white/[0.05] text-zinc-300 hover:text-white font-medium transition-colors cursor-pointer"
                >
                  <span className="truncate max-w-[140px]">
                    {currentProject?.name || projectSlug}
                  </span>
                  <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
                </button>

                {isProjectMenuOpen && (
                  <div className="absolute left-0 top-full mt-1.5 w-56 bg-[#13151f] border border-white/[0.08] rounded-lg shadow-2xl py-1 z-40 animate-fade-in">
                    <div className="px-3 py-1.5 text-[10px] font-mono uppercase text-zinc-500 tracking-wider">
                      Projects
                    </div>
                    {projects.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => {
                          setIsProjectMenuOpen(false);
                          setActiveProject(p);
                          router.push(`/${teamSlug}/${p.slug}`);
                        }}
                        className="w-full px-3 py-1.5 text-left text-xs flex items-center justify-between text-zinc-300 hover:text-white hover:bg-white/[0.05] transition-colors"
                      >
                        <span className="truncate font-medium">{p.name}</span>
                        {p.slug === projectSlug && (
                          <Check className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                        )}
                      </button>
                    ))}
                    <div className="border-t border-white/[0.06] my-1" />
                    <button
                      onClick={() => {
                        setIsProjectMenuOpen(false);
                        setIsCreateProjectOpen(true);
                      }}
                      className="w-full px-3 py-1.5 text-left text-xs flex items-center gap-2 text-zinc-400 hover:text-white hover:bg-white/[0.05] transition-colors"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>New Project</span>
                    </button>
                  </div>
                )}
              </div>
            </>
          )}

          {/* 3. Section Breadcrumb */}
          {projectSlug && currentSection !== "Overview" && (
            <>
              <ChevronRight className="w-3.5 h-3.5 text-zinc-650 mx-0.5" />
              <span className="text-zinc-100 font-semibold px-1">{currentSection}</span>
            </>
          )}
        </div>

        {/* Right Side: Search, Connect Repo, Notifications, User */}
        <div className="flex items-center gap-2.5">
          {/* Live Background Build Pulse */}
          {runningBuild && (
            <Link
              href={`/${teamSlug}/${projectSlug}/builds`}
              className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs hover:bg-indigo-500/15 transition-colors"
            >
              <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
              <Hammer className="w-3 h-3 text-indigo-400 animate-bounce" />
              <span className="font-mono text-[11px] truncate max-w-[150px]">
                {runningBuild.currentStage || "Indexing"}
              </span>
            </Link>
          )}

          {/* Quick Search */}
          <button
            onClick={onOpenSearch}
            className="hidden sm:flex items-center gap-2 px-2.5 py-1.5 bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] rounded-md text-xs text-zinc-400 transition-colors cursor-pointer"
          >
            <Search className="w-3.5 h-3.5 text-zinc-500" />
            <span className="text-zinc-500">Search</span>
            <kbd className="px-1.5 py-0.2 text-[9px] font-mono bg-white/[0.04] text-zinc-500 rounded border border-white/[0.06]">
              ⌘K
            </kbd>
          </button>

          {/* Connect Repository Action (when in project) */}
          {projectSlug && (
            <button
              onClick={() => setIsConnectRepoOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-zinc-200 text-black text-xs font-semibold rounded-md transition-colors cursor-pointer shrink-0"
            >
              <Plus className="w-3.5 h-3.5" />
              <span className="hidden md:inline">Connect Repository</span>
            </button>
          )}

          {/* Notifications */}
          <button
            className="p-1.5 rounded-md text-zinc-400 hover:text-white hover:bg-white/[0.05] transition-colors cursor-pointer"
            title="Notifications"
          >
            <Bell className="w-4 h-4" />
          </button>

          {/* User Menu */}
          <div className="relative" ref={userMenuRef}>
            <button
              onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
              className="flex items-center gap-2 p-1 rounded-full hover:ring-2 hover:ring-white/[0.1] transition-all cursor-pointer"
            >
              <div className="w-7 h-7 rounded-full bg-white/[0.06] border border-white/[0.08] flex items-center justify-center text-xs font-bold text-zinc-300">
                {(user?.username || "U").charAt(0).toUpperCase()}
              </div>
            </button>

            {isUserMenuOpen && (
              <div className="absolute right-0 top-full mt-1.5 w-48 bg-[#13151f] border border-white/[0.08] rounded-lg shadow-2xl py-1 z-50 animate-fade-in">
                <div className="px-3 py-2 border-b border-white/[0.06]">
                  <div className="text-xs font-semibold text-white truncate">
                    {user?.name || user?.username}
                  </div>
                  <div className="text-[11px] text-zinc-500 font-mono truncate">
                    {user?.email || "Personal"}
                  </div>
                </div>

                <Link
                  href={`/${teamSlug}/settings`}
                  onClick={() => setIsUserMenuOpen(false)}
                  className="w-full px-3 py-2 text-left text-xs flex items-center gap-2 text-zinc-300 hover:text-white hover:bg-white/[0.05] transition-colors"
                >
                  <UserIcon className="w-3.5 h-3.5 text-zinc-500" />
                  <span>Settings</span>
                </Link>

                <div className="border-t border-white/[0.06] my-1" />

                <button
                  onClick={() => {
                    setIsUserMenuOpen(false);
                    logout();
                  }}
                  className="w-full px-3 py-2 text-left text-xs flex items-center gap-2 text-rose-400 hover:text-rose-300 hover:bg-rose-950/20 transition-colors"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span>Log out</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Modals */}
      <CreateTeamModal
        isOpen={isCreateTeamOpen}
        onClose={() => setIsCreateTeamOpen(false)}
        onSuccess={(newSlug) => {
          router.push(`/${newSlug}`);
        }}
      />

      <CreateProjectModal
        isOpen={isCreateProjectOpen}
        onClose={() => setIsCreateProjectOpen(false)}
        teamSlug={teamSlug}
        onSuccess={(newSlug) => {
          router.push(`/${teamSlug}/${newSlug}`);
        }}
      />

      {currentProject && (
        <ConnectRepositoryModal
          isOpen={isConnectRepoOpen}
          onClose={() => setIsConnectRepoOpen(false)}
          teamSlug={teamSlug}
          projectSlug={projectSlug}
          projectId={currentProject.id}
          onSuccess={() => {
            if (token) fetchProjectDetails(token, projectSlug);
          }}
        />
      )}
    </>
  );
};
