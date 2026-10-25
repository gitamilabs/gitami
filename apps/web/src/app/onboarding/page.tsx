"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Users, ArrowRight, Loader2, LogOut, Sparkles, CheckCircle2 } from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { useTeamStore } from "../../store/teamStore";
import { ProtectedRoute } from "../../components/auth/ProtectedRoute";
import { GitamiLogo } from "../../components/layout/GitamiLogo";
import { Button } from "../../components/ui/Button";

function generateSlugPreview(name: string): string {
  return (
    name
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "team-slug"
  );
}

function OnboardingContent() {
  const router = useRouter();
  const { token, user, logout } = useAuthStore();
  const { teams, fetchTeams, createTeam } = useTeamStore();

  const [teamName, setTeamName] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCheckingTeams, setIsCheckingTeams] = useState(true);

  // If user already belongs to a team, redirect to their team workspace
  useEffect(() => {
    if (token) {
      fetchTeams(token)
        .then((existingTeams) => {
          if (existingTeams && existingTeams.length > 0) {
            router.replace(`/${existingTeams[0].slug}`);
          } else {
            setIsCheckingTeams(false);
          }
        })
        .catch(() => {
          setIsCheckingTeams(false);
        });
    }
  }, [token, fetchTeams, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = teamName.trim();
    if (!trimmed) {
      setError("Please enter a name for your team");
      return;
    }
    if (!token) {
      setError("Authentication session expired. Please sign in again.");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const created = await createTeam(token, trimmed);
      router.replace(`/${created.slug}`);
    } catch (err: any) {
      setError(err.message || "Failed to create team. Please try another name.");
      setIsLoading(false);
    }
  };

  if (isCheckingTeams) {
    return (
      <div className="min-h-screen bg-[#0c0d12] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-mono text-zinc-400">Checking workspace status...</span>
        </div>
      </div>
    );
  }

  const slugPreview = generateSlugPreview(teamName);
  const quickSuggestions = ["Engineering", "Core Team", "Personal Workspace", "DevOps"];

  return (
    <div className="min-h-screen bg-[#0c0d12] text-zinc-100 flex flex-col justify-between selection:bg-indigo-500/30">
      {/* Top Header */}
      <header className="h-16 px-6 sm:px-10 border-b border-white/[0.06] flex items-center justify-between">
        <GitamiLogo href="/" size="md" />

        <div className="flex items-center gap-3">
          {user && (
            <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-full bg-white/[0.03] border border-white/[0.06]">
              {user.avatarUrl ? (
                <img
                  src={user.avatarUrl}
                  alt={user.name || user.username}
                  className="w-5 h-5 rounded-full object-cover"
                />
              ) : (
                <div className="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-[10px] font-bold">
                  {(user.name || user.username || "U")[0].toUpperCase()}
                </div>
              )}
              <span className="text-xs text-zinc-300 font-medium">
                {user.name || user.username}
              </span>
            </div>
          )}

          <button
            onClick={() => logout()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-zinc-400 hover:text-white rounded-md hover:bg-white/[0.06] transition-colors cursor-pointer"
            title="Sign Out"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-lg bg-[#11131a] border border-white/[0.08] rounded-2xl p-8 sm:p-10 shadow-2xl relative overflow-hidden">
          {/* Subtle Accent Glow */}
          <div className="absolute -top-24 -right-24 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-mono mb-6">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Workspace Setup</span>
          </div>

          <h1 className="text-2xl font-bold tracking-tight text-white mb-2">
            Create your Team
          </h1>
          <p className="text-xs sm:text-sm text-zinc-400 mb-8 leading-relaxed">
            GitAmi organizes your repositories, code knowledge graphs, and pull request intelligence under teams. Choose a name to set up your workspace.
          </p>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-2">
                Team or Organization Name
              </label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="e.g. Acme Corp or Core Team"
                  value={teamName}
                  onChange={(e) => {
                    setTeamName(e.target.value);
                    if (error) setError(null);
                  }}
                  autoFocus
                  disabled={isLoading}
                  className="w-full px-4 py-3 bg-white/[0.03] border border-white/[0.1] rounded-xl text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500/50 focus:bg-white/[0.05] transition-all"
                  required
                />
              </div>

              {/* Slug Preview */}
              <div className="mt-2.5 flex items-center gap-1.5 text-[11px] font-mono text-zinc-500">
                <span>URL:</span>
                <span className="text-zinc-400">gitami.app/</span>
                <span className="text-indigo-400 font-medium">
                  {slugPreview}
                </span>
              </div>
            </div>

            {/* Quick Suggestions */}
            <div>
              <span className="text-[11px] text-zinc-500 block mb-2">
                Suggestions:
              </span>
              <div className="flex flex-wrap gap-2">
                {quickSuggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => {
                      setTeamName(suggestion);
                      if (error) setError(null);
                    }}
                    className="px-2.5 py-1 text-xs rounded-lg bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
                {error}
              </div>
            )}

            <Button
              type="submit"
              variant="primary"
              size="lg"
              disabled={isLoading || !teamName.trim()}
              className="w-full justify-center py-3 text-sm font-semibold rounded-xl cursor-pointer"
              rightIcon={
                isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <ArrowRight className="w-4 h-4" />
                )
              }
            >
              {isLoading ? "Creating Team..." : "Create Team & Continue"}
            </Button>
          </form>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-6 text-center text-xs text-zinc-600 border-t border-white/[0.04]">
        GitAmi &copy; {new Date().getFullYear()} &mdash; Production Ready Intelligence Workspace
      </footer>
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <ProtectedRoute>
      <OnboardingContent />
    </ProtectedRoute>
  );
}
