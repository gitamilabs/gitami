"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Badge } from "../../../components/ui/Badge";
import { Button } from "../../../components/ui/Button";
import { PRReviewCard } from "../../../components/pr/PRReviewCard";
import { PRIssueChecklist } from "../../../components/pr/PRIssueChecklist";
import { PRData } from "../../../lib/types";
import { prApi } from "../../../lib/api";
import { useAuthStore } from "../../../store/authStore";
import { useRepoStore } from "../../../store/repoStore";
import {
  GitPullRequest,
  RefreshCw,
  AlertCircle,
} from "lucide-react";
import Link from "next/link";

function PRReviewContent() {
  const searchParams = useSearchParams();
  const { token } = useAuthStore();
  const {
    connectedRepos,
    indexedRepos,
    fetchConnectedRepos,
    fetchIndexedRepos,
  } = useRepoStore();
  const [pullRequestsList, setPullRequestsList] = useState<PRData[]>([]);
  const [selectedPR, setSelectedPR] = useState<PRData | null>(null);
  const [selectedRepoFilter, setSelectedRepoFilter] = useState<string>(
    searchParams.get("repoFullName") || "all"
  );
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isEvaluatingPR, setIsEvaluatingPR] = useState<boolean>(false);
  const [isFixingPR, setIsFixingPR] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (token) {
      fetchConnectedRepos(token);
      fetchIndexedRepos(token);
    }
  }, [token, fetchConnectedRepos, fetchIndexedRepos]);

  // Combine connected repos and ingested (indexed) repos
  const availableRepos = React.useMemo(() => {
    const repoMap = new Map<string, { id: string; name: string; fullName: string; isIngested: boolean }>();

    for (const r of connectedRepos) {
      const isIngested =
        indexedRepos.includes(r.name) ||
        indexedRepos.includes(r.fullName) ||
        indexedRepos.some((idx) => r.fullName.endsWith(`/${idx}`) || idx.endsWith(`/${r.name}`));

      repoMap.set(r.name, {
        id: r.id,
        name: r.name,
        fullName: r.fullName,
        isIngested,
      });
    }

    for (const name of indexedRepos) {
      const shortName = name.includes("/") ? name.split("/")[1] : name;
      if (!repoMap.has(shortName) && !repoMap.has(name)) {
        repoMap.set(shortName, {
          id: name,
          name: shortName,
          fullName: name,
          isIngested: true,
        });
      }
    }

    return Array.from(repoMap.values());
  }, [connectedRepos, indexedRepos]);

  const fetchPullRequests = async (forceSync = false) => {
    setIsLoading(true);
    setActionError(null);
    try {
      const repoParam = selectedRepoFilter === "all" ? undefined : selectedRepoFilter;
      let prs: PRData[] = [];

      if (forceSync) {
        const syncData = await prApi.syncPullRequests(token || undefined, repoParam);
        prs = syncData.pullRequests || [];
      } else {
        const data = await prApi.listPullRequests(repoParam, token || undefined);
        prs = data.pullRequests || [];
      }

      setPullRequestsList(prs);
      if (prs.length > 0) {
        if (!selectedPR || !prs.some((p) => p.id === selectedPR.id)) {
          setSelectedPR(prs[0]);
        } else {
          const current = prs.find((p) => p.id === selectedPR.id);
          if (current) setSelectedPR(current);
        }
      } else {
        setSelectedPR(null);
      }
    } catch (err: any) {
      console.warn("API Service PR fetch notice:", err);
      setActionError(err.message || "Failed to fetch pull requests from GitHub");
      setPullRequestsList([]);
      setSelectedPR(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchPullRequests();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRepoFilter, token]);

  const handleRunPRReview = async (prId: string) => {
    setIsEvaluatingPR(true);
    setActionError(null);
    try {
      const data = await prApi.reviewPullRequest(prId, token || undefined);
      if (data.pullRequest) {
        setSelectedPR(data.pullRequest);
        await fetchPullRequests();
      }
    } catch (e: any) {
      setActionError(`PR review request failed: ${e.message}`);
    } finally {
      setIsEvaluatingPR(false);
    }
  };

  const handleFixSelectedIssues = async (selectedIssueIds: string[]) => {
    if (!selectedPR) return;
    setIsFixingPR(true);
    setActionError(null);
    try {
      const data = await prApi.fixSelectedIssues(selectedPR.id, selectedIssueIds, token || undefined);
      await fetchPullRequests();
      return { fixPrUrl: data.fixPrUrl };
    } catch (e: any) {
      setActionError(`AI Fix Agent failed: ${e.message}`);
      throw e;
    } finally {
      setIsFixingPR(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col">
      <header className="h-14 border-b border-zinc-800/80 px-6 flex items-center justify-between bg-[#0a0a0a]/50 backdrop-blur-md sticky top-0 z-20">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-semibold text-white flex items-center gap-2">
            <GitPullRequest className="w-4 h-4 text-purple-400" />
            PR Reviews
          </h1>
          <Badge variant="purple" size="sm" className="font-mono text-[10px]">
            Agent
          </Badge>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => fetchPullRequests(true)}
          disabled={isLoading}
          leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
        >
          Sync with GitHub
        </Button>
      </header>

      <div className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto space-y-6">
        {actionError && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/25 text-red-300 text-xs flex items-center gap-2 animate-fade-in">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{actionError}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[600px]">
          {/* Left Column: PR List */}
          <div className="lg:col-span-4 flex flex-col bg-[#0a0a0a] rounded-xl border border-zinc-800/80 overflow-hidden">
            <div className="p-4 border-b border-zinc-800/80 bg-zinc-900/40 flex flex-col gap-2.5">
              <div className="flex items-center gap-2 shrink-0">
                <GitPullRequest className="w-4 h-4 text-blue-400" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-200 font-mono">
                  Pull Requests ({pullRequestsList.length})
                </h3>
              </div>

              {availableRepos.length > 0 && (
                <select
                  value={selectedRepoFilter}
                  onChange={(e) => setSelectedRepoFilter(e.target.value)}
                  className="w-full min-w-0 bg-zinc-950 text-zinc-300 text-[11px] font-mono rounded-lg border border-zinc-800 px-2 py-1.5 focus:outline-none focus:border-zinc-600"
                >
                  <option value="all">All Repositories ({availableRepos.length})</option>
                  {availableRepos.map((r) => (
                    <option key={r.id} value={r.fullName || r.name}>
                      {r.name} {r.isIngested ? "⚡ (Ingested)" : ""}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-2.5 custom-scrollbar max-h-[750px]">
              {pullRequestsList.length === 0 ? (
                <div className="p-6 text-center space-y-4">
                  <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 mx-auto">
                    <GitPullRequest className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-zinc-200">
                      {isLoading ? "Fetching Pull Requests..." : "No Pull Requests Found"}
                    </p>
                    <p className="text-[11px] text-zinc-500 mt-1 leading-relaxed">
                      {isLoading
                        ? "Syncing latest active PRs with GitHub..."
                        : selectedRepoFilter !== "all"
                        ? `No active pull requests were found on GitHub for '${selectedRepoFilter}'.`
                        : "No active pull requests were found for any connected or ingested repositories."}
                    </p>
                  </div>
                  <div className="flex flex-col gap-2 pt-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => fetchPullRequests(true)}
                      disabled={isLoading}
                      leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
                      className="text-xs font-mono w-full justify-center"
                    >
                      {selectedRepoFilter !== "all" ? `Sync ${selectedRepoFilter} with GitHub` : "Sync All GitHub PRs"}
                    </Button>
                    <Link href="/dashboard">
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-xs font-mono w-full justify-center text-zinc-300"
                      >
                        Manage Projects
                      </Button>
                    </Link>
                  </div>
                </div>
              ) : (
                pullRequestsList.map((pr) => {
                  const isSelected = selectedPR?.id === pr.id;
                  const isSkipped = pr.status === "skipped_ai_fix" || pr.headBranch.startsWith("ai-fix/");

                  return (
                    <div
                      key={pr.id}
                      onClick={() => setSelectedPR(pr)}
                      className={`p-3.5 rounded-xl border transition-all duration-200 cursor-pointer ${
                        isSelected
                          ? "bg-blue-950/40 border-blue-500/70 ring-1 ring-blue-500/30"
                          : "bg-zinc-950/40 border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-900/60"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-1.5">
                        <span className="text-[11px] font-mono font-bold text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-md border border-blue-500/20">
                          #{pr.prNumber}
                        </span>

                        {isSkipped ? (
                          <span className="text-[10px] font-bold text-purple-300 bg-purple-500/20 px-2 py-0.5 rounded-md border border-purple-500/30">
                            AI Fix PR
                          </span>
                        ) : pr.review ? (
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${
                              pr.review.verdict === "ACCEPT"
                                ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                                : "bg-amber-500/20 text-amber-300 border-amber-500/30"
                            }`}
                          >
                            {pr.review.verdict}
                          </span>
                        ) : (
                          <span className="text-[10px] font-medium text-zinc-400 bg-zinc-800/80 px-2 py-0.5 rounded-md border border-zinc-700/50">
                            Pending Review
                          </span>
                        )}
                      </div>

                      <h4 className="text-xs font-bold text-zinc-100 line-clamp-2 leading-snug">
                        {pr.title}
                      </h4>

                      <p className="text-[10px] text-zinc-500 font-mono mt-2 flex items-center gap-1.5 truncate">
                        <span className="text-zinc-300">{pr.headBranch}</span>
                        <span className="text-zinc-600">→</span>
                        <span>{pr.baseBranch}</span>
                      </p>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Right Column: Review Details & Issue Checklist */}
          <div className="lg:col-span-8 flex flex-col space-y-6">
            {selectedPR ? (
              <div>
                <PRReviewCard
                  review={selectedPR.review || null}
                  prNumber={selectedPR.prNumber}
                  title={selectedPR.title}
                  author={selectedPR.authorLogin}
                  headBranch={selectedPR.headBranch}
                  baseBranch={selectedPR.baseBranch}
                  htmlUrl={selectedPR.htmlUrl}
                  onEvaluateNow={() => handleRunPRReview(selectedPR.id)}
                  isEvaluating={isEvaluatingPR}
                />

                <PRIssueChecklist
                  issues={selectedPR.issues || []}
                  onFixSelected={handleFixSelectedIssues}
                  isFixing={isFixingPR}
                />
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-12 bg-[#0a0a0a] rounded-xl border border-zinc-800/80 text-center min-h-[400px]">
                <div className="w-16 h-16 rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-blue-400 mb-4">
                  <GitPullRequest className="w-8 h-8" />
                </div>
                <h3 className="text-lg font-bold text-white tracking-tight">
                  Select a Pull Request to Review
                </h3>
                <p className="text-xs text-zinc-500 mt-1.5 max-w-md leading-relaxed">
                  Choose a PR from the left sidebar to inspect AST blast radius, review automated agent verdicts, and trigger surgical AI auto-fixes.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PRReviewPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center font-mono text-xs text-zinc-500">Loading PR Reviews...</div>}>
      <PRReviewContent />
    </Suspense>
  );
}
