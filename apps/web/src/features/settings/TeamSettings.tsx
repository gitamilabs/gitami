import React, { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Users,
  Shield,
  Trash2,
  UserPlus,
  Loader2,
  Check,
  AlertTriangle,
  Mail,
  User,
  Crown,
  Plus,
  ChevronDown,
} from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { useTeamStore } from "@/store/teamStore";
import { teamsApi } from "@/lib/api";
import { TeamMember } from "@/lib/types";
import { CreateTeamModal } from "@/components/teams/CreateTeamModal";

export const TeamSettings: React.FC = () => {
  const params = useParams();
  const router = useRouter();
  const teamSlug = (params?.teamSlug as string) || "";

  const { token, user: currentUser } = useAuthStore();
  const { teams, activeTeam, updateTeam, deleteTeam, setActiveTeam, fetchTeams } = useTeamStore();

  const currentTeam = teams.find((t) => t.slug === teamSlug) || activeTeam;

  useEffect(() => {
    if (token && teams.length === 0) {
      fetchTeams(token);
    }
  }, [token, teams.length, fetchTeams]);

  // Team Edit State
  const [teamName, setTeamName] = useState(currentTeam?.name || "");
  const [teamSlugInput, setTeamSlugInput] = useState(currentTeam?.slug || "");
  const [isSavingTeam, setIsSavingTeam] = useState(false);
  const [teamSaveSuccess, setTeamSaveSuccess] = useState(false);
  const [teamError, setTeamError] = useState<string | null>(null);

  // Members State
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [isLoadingMembers, setIsLoadingMembers] = useState(false);
  const [newMemberInput, setNewMemberInput] = useState("");
  const [newMemberRole, setNewMemberRole] = useState("MEMBER");
  const [isAddingMember, setIsAddingMember] = useState(false);
  const [memberError, setMemberError] = useState<string | null>(null);
  const [memberSuccess, setMemberSuccess] = useState<string | null>(null);

  // Delete Team State
  const [isDeletingTeam, setIsDeletingTeam] = useState(false);
  const [deleteConfirmInput, setDeleteConfirmInput] = useState("");
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Create Team Modal & Team Switcher State
  const [isCreateTeamModalOpen, setIsCreateTeamModalOpen] = useState(false);
  const [isTeamDropdownOpen, setIsTeamDropdownOpen] = useState(false);
  const teamDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (teamDropdownRef.current && !teamDropdownRef.current.contains(e.target as Node)) {
        setIsTeamDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    const matchingTeam = teams.find((t) => t.slug === teamSlug) || (activeTeam?.slug === teamSlug ? activeTeam : null) || teams[0];
    if (matchingTeam) {
      setTeamName(matchingTeam.name);
      setTeamSlugInput(matchingTeam.slug);
      setTeamError(null);
      setTeamSaveSuccess(false);
      setMemberError(null);
      setMemberSuccess(null);
      setDeleteConfirmInput("");
      setDeleteError(null);
    }
  }, [teams, teamSlug, activeTeam]);

  const loadMembers = useCallback(async () => {
    if (!token || !teamSlug) return;
    setIsLoadingMembers(true);
    try {
      const data = await teamsApi.getTeamMembers(token, teamSlug);
      setMembers(data.members || []);
    } catch (err: any) {
      console.warn("Failed to load members:", err);
    } finally {
      setIsLoadingMembers(false);
    }
  }, [token, teamSlug]);

  useEffect(() => {
    loadMembers();
  }, [loadMembers]);

  const handleUpdateTeam = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !teamSlug) return;
    setIsSavingTeam(true);
    setTeamError(null);
    setTeamSaveSuccess(false);

    try {
      const updated = await updateTeam(token, teamSlug, {
        name: teamName.trim(),
        slug: teamSlugInput.trim() || undefined,
      });
      setIsSavingTeam(false);
      setTeamSaveSuccess(true);
      setTimeout(() => setTeamSaveSuccess(false), 3000);
      if (updated.slug !== teamSlug) {
        router.push(`/${updated.slug}/settings`);
      }
    } catch (err: any) {
      setTeamError(err.message || "Failed to update team");
      setIsSavingTeam(false);
    }
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !teamSlug || !newMemberInput.trim()) return;

    setIsAddingMember(true);
    setMemberError(null);
    setMemberSuccess(null);

    try {
      const res = await teamsApi.addTeamMember(token, teamSlug, newMemberInput.trim(), newMemberRole);
      setMembers((prev) => [...prev, res.member]);
      setNewMemberInput("");
      setMemberSuccess(`Added ${res.member.user?.username || newMemberInput} to team`);
      setTimeout(() => setMemberSuccess(null), 3500);
    } catch (err: any) {
      setMemberError(err.message || "Failed to add member");
    } finally {
      setIsAddingMember(false);
    }
  };

  const handleUpdateRole = async (memberId: string, role: string) => {
    if (!token || !teamSlug) return;
    try {
      await teamsApi.updateTeamMemberRole(token, teamSlug, memberId, role);
      setMembers((prev) =>
        prev.map((m) => (m.id === memberId ? { ...m, role } : m))
      );
    } catch (err: any) {
      setMemberError(err.message || "Failed to update member role");
    }
  };

  const handleRemoveMember = async (memberId: string, username: string) => {
    if (!token || !teamSlug) return;
    if (!confirm(`Are you sure you want to remove ${username} from the team?`)) return;

    try {
      await teamsApi.removeTeamMember(token, teamSlug, memberId);
      setMembers((prev) => prev.filter((m) => m.id !== memberId));
    } catch (err: any) {
      setMemberError(err.message || "Failed to remove member");
    }
  };

  const handleDeleteTeam = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !teamSlug) return;
    if (deleteConfirmInput.trim().toLowerCase() !== teamSlug.toLowerCase()) {
      setDeleteError("Please enter the team slug exactly to confirm");
      return;
    }

    setIsDeletingTeam(true);
    setDeleteError(null);

    try {
      await deleteTeam(token, teamSlug);
      setIsDeletingTeam(false);
      setShowDeleteModal(false);
      router.push("/");
    } catch (err: any) {
      setDeleteError(err.message || "Failed to delete team");
      setIsDeletingTeam(false);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in text-zinc-200">
      {/* Current Team Banner & Team Switcher + Create Team Action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-[#11131a] border border-white/[0.06]">
        <div className="relative" ref={teamDropdownRef}>
          <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-400 font-semibold block mb-1">
            Currently Configuring Team
          </span>
          <button
            type="button"
            onClick={() => setIsTeamDropdownOpen(!isTeamDropdownOpen)}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-white text-xs font-semibold font-mono transition-colors cursor-pointer group"
            title="Switch Active Team"
          >
            <div className="w-4 h-4 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center text-[10px] font-bold shrink-0">
              <Users className="w-2.5 h-2.5" />
            </div>
            <span>{currentTeam?.name || teamSlug}</span>
            <span className="text-[10px] text-zinc-500 font-normal">({teamSlug})</span>
            <ChevronDown className={`w-3.5 h-3.5 text-zinc-400 group-hover:text-white transition-transform ${isTeamDropdownOpen ? "rotate-180" : ""}`} />
          </button>

          {isTeamDropdownOpen && (
            <div className="absolute left-0 top-full mt-1.5 w-60 bg-[#13151f] border border-white/[0.08] rounded-lg shadow-2xl py-1.5 z-50 animate-fade-in text-xs">
              <div className="px-3 py-1 text-[10px] font-mono uppercase text-zinc-500 tracking-wider font-semibold">
                Switch Team Settings
              </div>
              <div className="max-h-56 overflow-y-auto py-1 space-y-0.5">
                {teams.map((t) => {
                  const isSelected = t.slug === currentTeam?.slug;
                  return (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => {
                        setIsTeamDropdownOpen(false);
                        setActiveTeam(t);
                        router.push(`/${t.slug}/settings?tab=team`);
                      }}
                      className={`w-full px-3 py-1.5 text-left flex items-center justify-between hover:bg-white/[0.06] transition-colors cursor-pointer ${
                        isSelected ? "text-white font-semibold bg-white/[0.04]" : "text-zinc-300"
                      }`}
                    >
                      <span className="truncate">{t.name}</span>
                      {isSelected && (
                        <Check className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={() => setIsCreateTeamModalOpen(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-zinc-200 text-black rounded-md text-xs font-semibold transition-colors cursor-pointer shrink-0"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Create New Team</span>
        </button>
      </div>

      {/* Team General Preferences */}
      <section className="bg-[#11131a] border border-white/[0.06] rounded-xl p-6 space-y-5 shadow-sm">
        <div className="border-b border-white/[0.06] pb-4">
          <h2 className="text-sm font-bold text-white tracking-tight">
            Rename Team ({currentTeam?.name || teamSlug})
          </h2>
          <p className="text-xs text-zinc-400 mt-1">
            Modify the name or URL identifier of this specific team. To add a brand new team instead, use the &quot;Create New Team&quot; button above.
          </p>
        </div>

        <form onSubmit={handleUpdateTeam} className="space-y-4 max-w-lg">
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">
              Team Display Name
            </label>
            <input
              type="text"
              value={teamName}
              onChange={(e) => setTeamName(e.target.value)}
              className="w-full px-3 py-2 bg-[#0c0d12] border border-white/[0.08] rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/20 transition-colors"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">
              Team Slug <span className="text-zinc-500 font-mono font-normal">(Workspace URL path)</span>
            </label>
            <input
              type="text"
              value={teamSlugInput}
              onChange={(e) => setTeamSlugInput(e.target.value)}
              className="w-full px-3 py-2 bg-[#0c0d12] border border-white/[0.08] rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/20 font-mono transition-colors"
              required
            />
          </div>

          {teamError && (
            <div className="p-2.5 rounded-lg bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs">
              {teamError}
            </div>
          )}

          {teamSaveSuccess && (
            <div className="flex items-center gap-2 p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 text-xs font-mono">
              <Check className="w-3.5 h-3.5" />
              <span>Team renamed successfully!</span>
            </div>
          )}

          <div>
            <button
              type="submit"
              disabled={isSavingTeam || !teamName.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-white hover:bg-zinc-200 text-black rounded-lg text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
            >
              {isSavingTeam ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span>Save Team Name</span>
                </>
              )}
            </button>
          </div>
        </form>
      </section>

      {/* Team Members Management */}
      <section className="bg-[#11131a] border border-white/[0.06] rounded-xl p-6 space-y-6 shadow-sm">
        <div className="border-b border-white/[0.06] pb-4 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
              <Users className="w-4 h-4 text-indigo-400" />
              <span>Team Members ({members.length})</span>
            </h2>
            <p className="text-xs text-zinc-400 mt-0.5">
              Manage member roles, permissions, and workspace access.
            </p>
          </div>
        </div>

        {/* Add Member Form */}
        <form onSubmit={handleAddMember} className="p-4 rounded-xl bg-[#0c0d12] border border-white/[0.06] space-y-3">
          <p className="text-xs font-semibold text-white">Invite / Add Member</p>
          <div className="flex flex-col sm:flex-row gap-2.5">
            <div className="relative flex-1">
              <User className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-2.5 pointer-events-none" />
              <input
                type="text"
                value={newMemberInput}
                onChange={(e) => setNewMemberInput(e.target.value)}
                placeholder="GitHub username or registered email"
                className="w-full pl-9 pr-3 py-2 bg-white/[0.03] border border-white/[0.08] rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/20 font-mono transition-colors"
                required
              />
            </div>
            <select
              value={newMemberRole}
              onChange={(e) => setNewMemberRole(e.target.value)}
              className="px-3 py-2 bg-white/[0.03] border border-white/[0.08] rounded-lg text-xs text-zinc-200 font-mono focus:outline-none shrink-0"
            >
              <option value="MEMBER" className="bg-[#11131a]">MEMBER</option>
              <option value="OWNER" className="bg-[#11131a]">OWNER</option>
              <option value="VIEWER" className="bg-[#11131a]">VIEWER</option>
            </select>
            <button
              type="submit"
              disabled={isAddingMember || !newMemberInput.trim()}
              className="flex items-center justify-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer shrink-0"
            >
              {isAddingMember ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <UserPlus className="w-3.5 h-3.5" />
              )}
              <span>Add Member</span>
            </button>
          </div>

          {memberError && (
            <div className="p-2.5 rounded-lg bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs">
              {memberError}
            </div>
          )}

          {memberSuccess && (
            <div className="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 text-xs font-mono">
              {memberSuccess}
            </div>
          )}
        </form>

        {/* Member List */}
        <div className="divide-y divide-white/[0.06] border-t border-b border-white/[0.06]">
          {isLoadingMembers ? (
            <div className="py-8 flex items-center justify-center gap-2 text-xs text-zinc-500 font-mono">
              <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
              <span>Loading members...</span>
            </div>
          ) : members.length === 0 ? (
            <div className="py-6 text-center text-xs text-zinc-500 font-mono">
              No members recorded.
            </div>
          ) : (
            members.map((member) => {
              const isOwner = member.role === "OWNER";
              const isSelf = member.userId === currentUser?.id;

              return (
                <div key={member.id} className="py-3.5 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 min-w-0">
                    {member.user?.avatarUrl ? (
                      <img
                        src={member.user.avatarUrl}
                        alt={member.user.username}
                        className="w-8 h-8 rounded-full border border-white/[0.1] object-cover shrink-0"
                      />
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-white/[0.06] border border-white/[0.1] flex items-center justify-center text-xs font-bold text-zinc-300 shrink-0">
                        {(member.user?.username || "?").slice(0, 2).toUpperCase()}
                      </div>
                    )}
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-white font-mono truncate">
                          {member.user?.username || "Unknown"}
                        </span>
                        {isSelf && (
                          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-white/[0.06] text-zinc-400">
                            You
                          </span>
                        )}
                        {isOwner && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                            <Crown className="w-2.5 h-2.5 text-amber-400" />
                            Owner
                          </span>
                        )}
                      </div>
                      {member.user?.email && (
                        <p className="text-[11px] text-zinc-500 font-mono truncate">
                          {member.user.email}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    <select
                      value={member.role}
                      onChange={(e) => handleUpdateRole(member.id, e.target.value)}
                      className="px-2 py-1 bg-[#0c0d12] border border-white/[0.08] rounded text-xs text-zinc-300 font-mono focus:outline-none cursor-pointer"
                    >
                      <option value="OWNER" className="bg-[#11131a]">OWNER</option>
                      <option value="MEMBER" className="bg-[#11131a]">MEMBER</option>
                      <option value="VIEWER" className="bg-[#11131a]">VIEWER</option>
                    </select>

                    <button
                      onClick={() => handleRemoveMember(member.id, member.user?.username || "member")}
                      className="p-1.5 text-zinc-500 hover:text-rose-400 rounded hover:bg-rose-500/10 transition-colors cursor-pointer"
                      title="Remove Member"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </section>

      {/* Danger Zone */}
      <section className="bg-rose-950/10 border border-rose-500/20 rounded-xl p-6 space-y-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-rose-400 tracking-tight flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              <span>Danger Zone</span>
            </h2>
            <p className="text-xs text-zinc-400 mt-1">
              Irreversible actions that delete team resources and project metadata.
            </p>
          </div>

          <button
            onClick={() => setShowDeleteModal(true)}
            className="flex items-center gap-2 px-3.5 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-300 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Delete Team</span>
          </button>
        </div>
      </section>

      {/* Delete Team Modal */}
      {showDeleteModal && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs animate-fade-in"
          onClick={() => setShowDeleteModal(false)}
        >
          <div
            className="bg-[#11131a] border border-rose-500/20 rounded-xl w-full max-w-md shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 p-5 border-b border-white/[0.06] bg-rose-500/5">
              <div className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Delete Entire Team</h3>
                <p className="text-xs text-rose-300/80">This action is irreversible.</p>
              </div>
            </div>

            <form onSubmit={handleDeleteTeam} className="p-5 space-y-4">
              <p className="text-xs text-zinc-300 leading-relaxed">
                Deleting this team will permanently remove all associated project scopes, builds, and settings.
              </p>

              <div>
                <label className="block text-[11px] text-zinc-400 mb-1.5">
                  Type <span className="font-mono text-white font-semibold">{teamSlug}</span> to confirm:
                </label>
                <input
                  type="text"
                  value={deleteConfirmInput}
                  onChange={(e) => setDeleteConfirmInput(e.target.value)}
                  placeholder={teamSlug}
                  className="w-full px-3 py-2 bg-[#0c0d12] border border-white/[0.08] rounded-lg text-xs text-white placeholder-zinc-600 focus:outline-none focus:border-rose-500/40 font-mono transition-colors"
                  autoFocus
                />
              </div>

              {deleteError && (
                <div className="p-2.5 rounded-lg bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs">
                  {deleteError}
                </div>
              )}

              <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-white/[0.06]">
                <button
                  type="button"
                  onClick={() => setShowDeleteModal(false)}
                  className="px-3.5 py-2 rounded-lg text-xs font-medium text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={deleteConfirmInput.trim().toLowerCase() !== teamSlug.toLowerCase() || isDeletingTeam}
                  className="flex items-center gap-2 px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-30 cursor-pointer"
                >
                  {isDeletingTeam ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="w-3.5 h-3.5" />
                  )}
                  <span>Delete Team</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <CreateTeamModal
        isOpen={isCreateTeamModalOpen}
        onClose={() => setIsCreateTeamModalOpen(false)}
        onSuccess={(newSlug) => {
          setIsCreateTeamModalOpen(false);
          router.push(`/${newSlug}/settings`);
        }}
      />
    </div>
  );
};
