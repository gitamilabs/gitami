import React from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { useRepoStore } from "@/store/repoStore";
import { useTeamStore } from "@/store/teamStore";
import { formatTimeAgo } from "@/lib/utils";
import { FolderGit2, Database, LogOut, User, Mail, Calendar, Users, ArrowRight } from "lucide-react";

export const GeneralSettings: React.FC = () => {
  const params = useParams();
  const router = useRouter();
  const teamSlug = (params?.teamSlug as string) || "";

  const { user, logout } = useAuthStore();
  const { connectedRepos, indexedRepos } = useRepoStore();
  const { teams, activeTeam } = useTeamStore();

  const currentTeam = teams.find((t) => t.slug === teamSlug) || activeTeam;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Account Profile Card */}
      <section className="bg-[#11131a] border border-white/[0.06] rounded-xl p-6 space-y-5 shadow-sm">
        <div className="flex items-center justify-between border-b border-white/[0.06] pb-4">
          <div>
            <h2 className="text-sm font-bold text-white tracking-tight">User Profile</h2>
            <p className="text-xs text-zinc-400">Authenticated GitAmi session details</p>
          </div>
          <span className="px-2.5 py-1 rounded-full text-[10px] font-mono font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Active Session
          </span>
        </div>

        <div className="flex items-center gap-4">
          {user?.avatarUrl ? (
            <img
              src={user.avatarUrl}
              alt={user.username}
              className="w-14 h-14 rounded-full border border-white/[0.1] object-cover shadow-sm"
            />
          ) : (
            <div className="w-14 h-14 rounded-full bg-white/[0.04] border border-white/[0.1] flex items-center justify-center text-base font-bold text-zinc-200">
              {(user?.username || "?").slice(0, 2).toUpperCase()}
            </div>
          )}
          <div className="space-y-1">
            <p className="text-base font-semibold text-white">{user?.name || user?.username}</p>
            <p className="text-xs text-zinc-400 font-mono flex items-center gap-1.5">
              <Mail className="w-3.5 h-3.5 text-zinc-500" />
              {user?.email || "No email on file"}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-xs">
          <div className="p-3.5 rounded-xl bg-[#0c0d12] border border-white/[0.06]">
            <div className="flex items-center gap-2 text-zinc-400 mb-1">
              <User className="w-3.5 h-3.5 text-indigo-400" />
              <p className="text-[10px] text-zinc-500 uppercase font-mono tracking-wider">GitHub Username</p>
            </div>
            <p className="text-zinc-200 font-mono font-semibold text-sm">{user?.username || "—"}</p>
          </div>
          <div className="p-3.5 rounded-xl bg-[#0c0d12] border border-white/[0.06]">
            <div className="flex items-center gap-2 text-zinc-400 mb-1">
              <Calendar className="w-3.5 h-3.5 text-indigo-400" />
              <p className="text-[10px] text-zinc-500 uppercase font-mono tracking-wider">Member Since</p>
            </div>
            <p className="text-zinc-200 font-mono font-semibold text-sm">
              {user?.createdAt ? formatTimeAgo(user.createdAt) : "—"}
            </p>
          </div>
        </div>

        <div className="pt-2">
          <button
            onClick={() => logout()}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 hover:bg-rose-500/15 text-xs font-semibold transition-all cursor-pointer shadow-xs"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign out of GitAmi</span>
          </button>
        </div>
      </section>

      {/* Active Team Workspace Section */}
      <section className="bg-[#11131a] border border-white/[0.06] rounded-xl p-6 space-y-4 shadow-sm">
        <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
          <div>
            <h2 className="text-sm font-bold text-white tracking-tight">Active Team Workspace</h2>
            <p className="text-xs text-zinc-400">Current workspace context for projects, builds, and repositories</p>
          </div>
          <button
            onClick={() => router.push(`/${teamSlug}/settings?tab=team`)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-medium text-zinc-200 hover:text-white transition-colors cursor-pointer"
          >
            <span>Team Settings</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="p-4 rounded-xl bg-[#0c0d12] border border-white/[0.06] flex items-center justify-between">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 font-bold shrink-0">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">{currentTeam?.name || teamSlug}</p>
              <p className="text-xs text-zinc-400 font-mono mt-0.5">
                Slug: <span className="text-zinc-300">/{currentTeam?.slug || teamSlug}</span>
              </p>
            </div>
          </div>
          <span className="px-2.5 py-1 rounded-full text-[10px] font-mono font-semibold bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
            Current Workspace
          </span>
        </div>
      </section>

      {/* Workspace Intelligence Stats */}
      <section className="bg-[#11131a] border border-white/[0.06] rounded-xl p-6 space-y-4 shadow-sm">
        <div className="border-b border-white/[0.06] pb-3">
          <h2 className="text-sm font-bold text-white tracking-tight">Workspace Knowledge Base</h2>
          <p className="text-xs text-zinc-400">Current indexing & repository boundaries</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <div className="p-4 rounded-xl bg-[#0c0d12] border border-white/[0.06] flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shrink-0">
              <FolderGit2 className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <p className="text-[10px] text-zinc-500 uppercase font-mono tracking-wider">Connected Repositories</p>
              <p className="text-zinc-100 font-extrabold text-xl mt-0.5">{connectedRepos.length}</p>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-[#0c0d12] border border-white/[0.06] flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0">
              <Database className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-[10px] text-zinc-500 uppercase font-mono tracking-wider">Indexed Knowledge Bases</p>
              <p className="text-zinc-100 font-extrabold text-xl mt-0.5">{indexedRepos.length}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
