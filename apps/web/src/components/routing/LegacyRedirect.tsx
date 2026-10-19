"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "../../store/authStore";
import { useTeamStore } from "../../store/teamStore";
import { useProjectStore } from "../../store/projectStore";

interface LegacyRedirectProps {
  target: "repositories" | "builds" | "graph" | "chat" | "prs" | "activity" | "settings";
}

export function LegacyRedirect({ target }: LegacyRedirectProps) {
  const router = useRouter();
  const { token, isInitialized } = useAuthStore();
  const { activeTeam, fetchTeams } = useTeamStore();
  const { activeProject, fetchTeamProjects } = useProjectStore();

  useEffect(() => {
    if (!isInitialized) return;
    if (!token) {
      router.replace("/");
      return;
    }

    const resolveAndRedirect = async () => {
      let team = activeTeam;
      if (!team) {
        const teams = await fetchTeams(token);
        team = teams[0] || null;
      }
      if (!team) {
        router.replace("/");
        return;
      }

      if (target === "activity") {
        router.replace(`/${team.slug}/activity`);
        return;
      }
      if (target === "settings") {
        router.replace(`/${team.slug}/settings`);
        return;
      }

      let proj = activeProject;
      if (!proj) {
        const projs = await fetchTeamProjects(token, team.slug);
        proj = projs[0] || null;
      }

      if (proj) {
        router.replace(`/${team.slug}/${proj.slug}/${target}`);
      } else {
        router.replace(`/${team.slug}`);
      }
    };

    resolveAndRedirect();
  }, [isInitialized, token, activeTeam, activeProject, target, router, fetchTeams, fetchTeamProjects]);

  return (
    <div className="flex-1 flex items-center justify-center min-h-[400px]">
      <div className="flex flex-col items-center gap-3">
        <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-xs font-mono text-zinc-500">Opening {target}...</span>
      </div>
    </div>
  );
}
