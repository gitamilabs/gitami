"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { PRReviewCard } from "@/components/pr/PRReviewCard";
import { PRIssueChecklist } from "@/components/pr/PRIssueChecklist";
import { PRData } from "@/lib/types";
import { prApi } from "@/lib/api";
import { PRSkeleton } from "@/components/ui/PageSkeletons";
import { useAuthStore } from "@/store/authStore";
import { useProjectStore } from "@/store/projectStore";
import {
  GitPullRequest,
  RefreshCw,
  AlertCircle,
} from "lucide-react";

function PRReviewContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const teamSlug = (params?.teamSlug as string) || "";
  const projectSlug = (params?.projectSlug as string) || "";

  const { token } = useAuthStore();
  const { getActiveProject } = useProjectStore();
  const activeProject = getActiveProject();

  const [pullRequestsList, setPullRequestsList] = useState<PRData[]>([]);
  const [selectedPR, setSelectedPR] = useState<PRData | null>(null);
  const [selectedRepoFilter, setSelectedRepoFilter] = useState<string>(
    searchParams.get("repoFullName") || "all"
  );
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isEvaluatingPR, setIsEvaluatingPR] = useState<boolean>(false);
  const [isFixingPR, setIsFixingPR] = useState<boolean>(false);
  const [isDeletingPR, setIsDeletingPR] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const projectRepos = activeProject?.repositories || [];

  const loadPRs = useCallback(async () => {
    setIsLoading(true);
    setActionError(null);
    try {
      const repoFilter = selectedRepoFilter === "all" ? undefined : selectedRepoFilter;
      const targetProjectIdentifier = activeProject?.id || projectSlug;
      const res = await prApi.listPullRequests(repoFilter, token || undefined, targetProjectIdentifier);
      const data = res.pullRequests || [];
      setPullRequestsList(data);
      if (data.length > 0) {
        setSelectedPR((prev) => (prev ? (data.find((p) => p.id === prev.id) || data[0]) : data[0]));
      } else {
        setSelectedPR(null);
      }
    } catch (err: any) {
      console.warn("Could not load pull requests:", err);
    } finally {
      setIsLoading(false);
    }
  }, [selectedRepoFilter, token, activeProject?.id, projectSlug]);

  useEffect(() => {
    loadPRs();
  }, [loadPRs]);

  const handleEvaluate = async (prId: string) => {
    setIsEvaluatingPR(true);
    setActionError(null);
    try {
      const res = await prApi.reviewPullRequest(prId, token || undefined);
      if (res.pullRequest) {
        setSelectedPR(res.pullRequest);
        setPullRequestsList((prev) =>
          prev.map((pr) => (pr.id === prId ? res.pullRequest : pr))
        );
      }
    } catch (err: any) {
      setActionError(err.message || "Failed to trigger automated review");
    } finally {
      setIsEvaluatingPR(false);
    }
  };

  const handleFixSelected = async (prId: string, issueIds: string[]) => {
    setIsFixingPR(true);
    setActionError(null);
    try {
      const res = await prApi.fixSelectedIssues(prId, issueIds, token || undefined);
      if (res.success) {
        await loadPRs();
      }
      return { fixPrUrl: res.fixPrUrl };
    } catch (err: any) {
      setActionError(err.message || "Failed to execute auto-fix");
    } finally {
      setIsFixingPR(false);
    }
  };

  const handleDeletePR = async (prId: string) => {
    if (!token) return;
    if (!window.confirm("Are you sure you want to delete this PR and its review data?")) return;
    setIsDeletingPR(true);
    setActionError(null);
    try {
      await prApi.deletePullRequest(token, prId);
      setSelectedPR(null);
      await loadPRs();
    } catch (err: any) {
      setActionError(err.message || "Failed to delete PR");
    } finally {
      setIsDeletingPR(false);
    }
  };

  const handleToggleFixed = async (issueId: string, isFixed: boolean) => {
    if (!token) return;
    try {
      await prApi.updateIssue(token, issueId, { isFixed });
      setSelectedPR((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          issues: prev.issues?.map((i) => (i.id === issueId ? { ...i, isFixed } : i)),
        };
      });
      setPullRequestsList((prev) =>
        prev.map((pr) => {
          if (pr.id === selectedPR?.id) {
            return {
              ...pr,
              issues: pr.issues?.map((i) => (i.id === issueId ? { ...i, isFixed } : i)),
            };
          }
          return pr;
        })
      );
    } catch (err: any) {
      setActionError(err.message || "Failed to update issue status");
    }
  };

  return (
    <div className="p-8 max-w-5xl w-full mx-auto space-y-8 animate-fade-in text-zinc-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-white/[0.06]">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight font-mono">
            PR Reviews & Risk Evaluation
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Automated intelligence review scoped to repositories in {activeProject?.name || projectSlug}.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {projectRepos.length > 1 && (
            <select
              value={selectedRepoFilter}
              onChange={(e) => {
                setSelectedRepoFilter(e.target.value);
                setSelectedPR(null);
              }}
              className="bg-white/[0.03] border border-white/[0.08] rounded px-2.5 py-1 text-xs text-zinc-300 font-mono focus:outline-none"
            >
              <option value="all">All Repositories</option>
              {projectRepos.map((r) => (
                <option key={r.id} value={r.fullName} className="bg-[#11131a] text-zinc-200">
                  {r.name}
                </option>
              ))}
            </select>
          )}

          <Button
            variant="secondary"
            size="sm"
            onClick={loadPRs}
            isLoading={isLoading}
            leftIcon={<RefreshCw className="w-3 h-3 text-zinc-400" />}
            className="rounded-md text-xs font-mono"
          >
            Refresh
          </Button>
        </div>
      </div>

      {actionError && (
        <div className="p-3 rounded-md bg-rose-950/30 border border-rose-800/50 text-rose-300 text-xs flex items-center gap-2 font-mono">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          <span>{actionError}</span>
        </div>
      )}

      {isLoading ? (
        <PRSkeleton />
      ) : pullRequestsList.length === 0 ? (
        <div className="py-16 text-center space-y-4 max-w-md mx-auto">
          <div className="w-12 h-12 rounded-xl bg-[#11131a] border border-white/[0.06] flex items-center justify-center mx-auto text-zinc-400">
            <GitPullRequest className="w-6 h-6 text-zinc-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">No pull requests found</h3>
            <p className="text-xs text-zinc-400 mt-1">
              Open a pull request on GitHub or select another repository filter.
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* PR List Column */}
          <div className="lg:col-span-5 space-y-3">
            <div className="text-xs font-mono uppercase tracking-wider text-zinc-400 font-semibold px-1">
              Pull Requests ({pullRequestsList.length})
            </div>

            <div className="border-t border-b border-white/[0.06] divide-y divide-white/[0.06] max-h-[600px] overflow-y-auto">
              {pullRequestsList.map((pr) => {
                const isSelected = selectedPR?.id === pr.id;
                const isReviewed = pr.status === "reviewed" || !!pr.review;
                return (
                  <button
                    key={pr.id}
                    onClick={() => setSelectedPR(pr)}
                    className={`w-full py-3.5 px-3 text-left transition-colors flex flex-col gap-1.5 ${
                      isSelected
                        ? "bg-white/[0.08] rounded-md text-white font-medium"
                        : "hover:bg-white/[0.03] text-zinc-300"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-mono font-semibold text-white truncate">
                        #{pr.prNumber} {pr.title}
                      </span>
                      <span
                        className={`text-[10px] font-mono px-1.5 py-0.2 rounded font-semibold shrink-0 ${
                          isReviewed
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                            : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                        }`}
                      >
                        {isReviewed ? "Reviewed" : "Pending"}
                      </span>
                    </div>

                    <div className="text-[11px] font-mono text-zinc-500 truncate">
                      {pr.repoFullName} • {pr.headBranch} → {pr.baseBranch}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* PR Detail / Review Column */}
          {selectedPR && (
            <div className="lg:col-span-7 space-y-6">
              <PRReviewCard
                review={selectedPR.review || null}
                prNumber={selectedPR.prNumber}
                title={selectedPR.title}
                author={selectedPR.authorLogin}
                headBranch={selectedPR.headBranch}
                baseBranch={selectedPR.baseBranch}
                htmlUrl={selectedPR.htmlUrl}
                onEvaluateNow={() => handleEvaluate(selectedPR.id)}
                isEvaluating={isEvaluatingPR}
                onDelete={() => handleDeletePR(selectedPR.id)}
                isDeleting={isDeletingPR}
              />

              {selectedPR.review && selectedPR.issues && selectedPR.issues.length > 0 && (
                <PRIssueChecklist
                  issues={selectedPR.issues}
                  onFixSelected={(ids) => handleFixSelected(selectedPR.id, ids)}
                  isFixing={isFixingPR}
                  onToggleFixed={handleToggleFixed}
                />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function PRsPage() {
  return (
    <Suspense fallback={<PRSkeleton />}>
      <PRReviewContent />
    </Suspense>
  );
}
