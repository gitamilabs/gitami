"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "../../../store/authStore";
import { useTeamStore } from "../../../store/teamStore";

export default function DashboardPage() {
  const router = useRouter();
  const { token, isInitialized } = useAuthStore();
  const { activeTeam, fetchTeams } = useTeamStore();

  useEffect(() => {
    if (!isInitialized) return;
    if (!token) {
      router.replace("/");
      return;
    }
    if (activeTeam) {
      router.replace(`/${activeTeam.slug}`);
    } else {
      fetchTeams(token)
        .then((teams) => {
          if (teams.length > 0) {
            router.replace(`/${teams[0].slug}`);
          } else {
            router.replace("/onboarding");
          }
        })
        .catch(() => {
          router.replace("/onboarding");
        });
    }
  }, [token, isInitialized, activeTeam, router, fetchTeams]);

  return (
    <div className="flex-1 flex items-center justify-center min-h-[400px]">
      <div className="flex flex-col items-center gap-3">
        <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-xs font-mono text-zinc-500">Redirecting to workspace...</span>
      </div>
    </div>
  );
}
