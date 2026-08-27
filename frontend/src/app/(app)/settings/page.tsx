"use client";

import React, { useEffect } from "react";
import { useAuthStore } from "../../../store/authStore";
import { useRepoStore } from "../../../store/repoStore";
import { formatTimeAgo } from "../../../lib/utils";
import {
  Settings,
  Github,
  LogOut,
  FolderGit2,
  Database,
  ExternalLink,
} from "lucide-react";

function SettingsContent() {
  const { user, token, logout } = useAuthStore();
  const {
    connectedRepos,
    installations,
    indexedRepos,
    fetchConnectedRepos,
    fetchInstallations,
    fetchIndexedRepos,
  } = useRepoStore();

  useEffect(() => {
    if (token) {
      fetchConnectedRepos(token);
      fetchInstallations(token);
      fetchIndexedRepos(token);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <div className="flex-1 flex flex-col">
      <header className="h-14 border-b border-zinc-800/80 px-6 flex items-center gap-2 bg-[#0a0a0a]/50 backdrop-blur-md sticky top-0 z-20">
        <Settings className="w-4 h-4 text-blue-400" />
        <h1 className="text-sm font-semibold text-white">Settings</h1>
      </header>

      <div className="flex-1 p-6 md:p-8 max-w-2xl w-full mx-auto space-y-6">
        {/* Account */}
        <section className="bg-[#0a0a0a] border border-zinc-800/80 rounded-xl p-6 space-y-4">
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Account</h2>
          <div className="flex items-center gap-3.5">
            {user?.avatarUrl ? (
              <img
                src={user.avatarUrl}
                alt={user.username}
                className="w-12 h-12 rounded-full border border-zinc-700 object-cover"
              />
            ) : (
              <div className="w-12 h-12 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-sm font-bold text-zinc-200">
                {(user?.username || "?").slice(0, 2).toUpperCase()}
              </div>
            )}
            <div>
              <p className="text-sm font-semibold text-white">{user?.name || user?.username}</p>
              <p className="text-xs text-zinc-500 font-mono">{user?.email || "No email on file"}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 pt-2 text-xs">
            <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800">
              <p className="text-[10px] text-zinc-500 uppercase">GitHub Username</p>
              <p className="text-zinc-200 font-mono mt-0.5">{user?.username || "—"}</p>
            </div>
            <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800">
              <p className="text-[10px] text-zinc-500 uppercase">Member Since</p>
              <p className="text-zinc-200 font-mono mt-0.5">
                {user?.createdAt ? formatTimeAgo(user.createdAt) : "—"}
              </p>
            </div>
          </div>
          <button
            onClick={() => logout()}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-red-500/10 border border-red-500/25 text-red-400 hover:bg-red-500/15 text-xs font-medium transition-colors cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign out</span>
          </button>
        </section>

        {/* Workspace stats */}
        <section className="bg-[#0a0a0a] border border-zinc-800/80 rounded-xl p-6 space-y-4">
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Workspace</h2>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800 flex items-center gap-2.5">
              <FolderGit2 className="w-4 h-4 text-blue-400 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-500 uppercase">Connected Repos</p>
                <p className="text-zinc-200 font-semibold mt-0.5">{connectedRepos.length}</p>
              </div>
            </div>
            <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800 flex items-center gap-2.5">
              <Database className="w-4 h-4 text-emerald-400 shrink-0" />
              <div>
                <p className="text-[10px] text-zinc-500 uppercase">Indexed Repos</p>
                <p className="text-zinc-200 font-semibold mt-0.5">{indexedRepos.length}</p>
              </div>
            </div>
          </div>
        </section>

        {/* GitHub App installations */}
        <section className="bg-[#0a0a0a] border border-zinc-800/80 rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
              GitHub App Installations
            </h2>
            <a
              href="https://github.com/settings/installations"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300"
            >
              Manage on GitHub <ExternalLink className="w-3 h-3" />
            </a>
          </div>

          {installations.length === 0 ? (
            <p className="text-xs text-zinc-500">No GitHub App installations found for this account.</p>
          ) : (
            <div className="space-y-2">
              {installations.map((inst) => (
                <div
                  key={inst.id}
                  className="flex items-center gap-3 p-3 rounded-lg bg-zinc-900/60 border border-zinc-800"
                >
                  <Github className="w-4 h-4 text-white shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-zinc-200 truncate">{inst.accountLogin}</p>
                    <p className="text-[10px] text-zinc-500 font-mono">{inst.accountType}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return <SettingsContent />;
}
