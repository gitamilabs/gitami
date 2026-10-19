"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "../../../store/authStore";
import { useRepoStore } from "../../../store/repoStore";
import { useTeamStore } from "../../../store/teamStore";
import { useProjectStore } from "../../../store/projectStore";
import { GeneralSettings } from "../../../features/settings/GeneralSettings";
import { ProjectSettings } from "../../../features/settings/ProjectSettings";
import { TeamSettings } from "../../../features/settings/TeamSettings";
import { GitHubSettings } from "../../../features/settings/GitHubSettings";
import { AISettings } from "../../../features/settings/AISettings";
import { AdvancedSettings } from "../../../features/settings/AdvancedSettings";
import { Sidebar } from "../../../components/layout/Sidebar";
import { TopBar } from "../../../components/layout/TopBar";
import { ProtectedRoute } from "../../../components/auth/ProtectedRoute";
import {
  Settings,
  Sliders,
  Cpu,
  FolderGit2,
  Github,
  Users,
  Layers,
} from "lucide-react";

type SettingsTab = "general" | "project" | "team" | "github" | "ai" | "advanced";

export default function WorkspaceSettingsPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();

  const teamSlug = (params?.teamSlug as string) || "";
  const tabParam = searchParams.get("tab") as SettingsTab | null;

  const { token } = useAuthStore();
  const { teams, activeTeam, fetchTeams, setActiveTeam } = useTeamStore();
  const { fetchTeamProjects } = useProjectStore();
  const {
    fetchConnectedRepos,
    fetchInstallations,
    fetchIndexedRepos,
  } = useRepoStore();

  const [activeTab, setActiveTab] = useState<SettingsTab>(tabParam || "general");

  // Keep activeTab synchronized with searchParams
  useEffect(() => {
    if (tabParam && tabParam !== activeTab) {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

  // Synchronize team and project stores with current route's teamSlug
  useEffect(() => {
    if (token && teamSlug) {
      if (teams.length === 0) {
        fetchTeams(token);
      }
      setActiveTeam(teamSlug);
      fetchTeamProjects(token, teamSlug);
    }
  }, [token, teamSlug, teams.length, fetchTeams, setActiveTeam, fetchTeamProjects]);

  // Fetch repositories and installations
  useEffect(() => {
    if (token) {
      fetchConnectedRepos(token);
      fetchInstallations(token);
      fetchIndexedRepos(token);
    }
  }, [token, fetchConnectedRepos, fetchInstallations, fetchIndexedRepos]);

  const currentTeam = teams.find((t) => t.slug === teamSlug) || (activeTeam?.slug === teamSlug ? activeTeam : null) || teams[0];

  const handleTabChange = (tabId: SettingsTab) => {
    setActiveTab(tabId);
    router.replace(`/${teamSlug}/settings?tab=${tabId}`);
  };

  const tabs: { id: SettingsTab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { id: "general", label: "General", icon: FolderGit2 },
    { id: "project", label: "Project Details", icon: Layers },
    { id: "team", label: "Team & Members", icon: Users },
    { id: "github", label: "GitHub App", icon: Github },
    { id: "ai", label: "AI & Vector Engine", icon: Cpu },
    { id: "advanced", label: "Advanced Prompts", icon: Sliders },
  ];

  return (
    <ProtectedRoute>
      <div className="flex h-screen bg-[#0c0d12] text-zinc-100 overflow-hidden select-none">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
          <TopBar />
          <main className="flex-1 overflow-y-auto p-8 max-w-5xl w-full mx-auto space-y-6">
            <div className="pb-6 border-b border-white/[0.06] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h1 className="text-xl font-bold text-white tracking-tight font-mono">
                  Workspace Settings
                </h1>
                <p className="text-xs text-zinc-400 mt-1">
                  Team permissions, project configurations, GitHub App, and AI runtime.
                </p>
              </div>

              {/* Synchronized Workspace Badge */}
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.08]">
                <Users className="w-3.5 h-3.5 text-indigo-400" />
                <span className="text-xs font-semibold text-white">
                  {currentTeam?.name || teamSlug}
                </span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-white/[0.04] text-zinc-400 border border-white/[0.06]">
                  /{currentTeam?.slug || teamSlug}
                </span>
              </div>
            </div>

            {/* Tab navigation */}
            <div className="flex items-center gap-1.5 border-b border-white/[0.06] pb-2 overflow-x-auto">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => handleTabChange(tab.id)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer shrink-0 ${
                      isActive
                        ? "bg-white/[0.08] text-white font-semibold"
                        : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]"
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Tab Content */}
            <div className="pt-2">
              {activeTab === "general" && <GeneralSettings />}
              {activeTab === "project" && <ProjectSettings />}
              {activeTab === "team" && <TeamSettings />}
              {activeTab === "github" && <GitHubSettings />}
              {activeTab === "ai" && <AISettings />}
              {activeTab === "advanced" && <AdvancedSettings />}
            </div>
          </main>
        </div>
      </div>
    </ProtectedRoute>
  );
}
