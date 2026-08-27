"use client";

import React, { useState, useEffect } from "react";
import { ProtectedRoute } from "../../components/auth/ProtectedRoute";
import { Sidebar } from "../../components/layout/Sidebar";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { PRReviewCard } from "../../components/pr/PRReviewCard";
import { PRIssueChecklist } from "../../components/pr/PRIssueChecklist";
import { PRData } from "../../lib/types";
import { prApi } from "../../lib/api";
import { useAuthStore } from "../../store/authStore";
import { useRepoStore } from "../../store/repoStore";
import {
  GitPullRequest,
  RefreshCw,
  Sparkles,
  Bot,
  AlertCircle,
  Filter,
  CheckCircle2,
  Cpu,
  Layers,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";

function PRReviewContent() {
  const { user, token } = useAuthStore();
  const {
    connectedRepos,
    indexedRepos,
    fetchConnectedRepos,
    fetchIndexedRepos,
  } = useRepoStore();
  const [pullRequestsList, setPullRequestsList] = useState<PRData[]>([]);
  const [selectedPR, setSelectedPR] = useState<PRData | null>(null);
  const [selectedRepoFilter, setSelectedRepoFilter] = useState<string>("all");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isEvaluatingPR, setIsEvaluatingPR] = useState<boolean>(false);
  const [isFixingPR, setIsFixingPR] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Auto-fetch connected repos and indexed repos on mount
  useEffect(() => {
    if (token) {
      fetchConnectedRepos(token);
    }
    fetchIndexedRepos();
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
          // Refresh current selection
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

  const createMockPRsIfEmpty = () => {
    const activeRepoName = selectedRepoFilter === "all" ? "demo-codebase" : selectedRepoFilter;
    const mockPRs: PRData[] = [
      {
        id: `demo-pr-${Date.now()}`,
        repoFullName: activeRepoName,
        prNumber: 42,
        title: "feat(auth): add JWT token refresh and role RBAC middleware",
        body: "Refactors auth flow, adds JWT token rotation, and adds RBAC middleware.",
        state: "open",
        status: "reviewed",
        baseBranch: "main",
        headBranch: "feature/jwt-rbac-auth",
        authorLogin: "dev-lead",
        htmlUrl: `https://github.com/${activeRepoName}/pull/42`,
        review: {
          id: "rev-1",
          verdict: "SUGGEST",
          riskScore: 6.4,
          summary: "ReAct Agent Review: Found 3 critical security & logical issues. Downstream blast radius ripple affects user session handlers.",
          agentRationale:
            "Orchestrator called FastMCP tool `get_blast_radius`. Downstream symbols `getUserByGithubId` and `authMiddleware` are affected. Groq Llama worker identified potential unhandled token null dereference.",
        },
        issues: [
          {
            id: "issue-1",
            title: "Potential Null Pointer Exception in Auth Middleware",
            description: "Token string dereference lacks validation when Bearer header is empty or undefined.",
            category: "security",
            severity: "error",
            filePath: "backend/api-service/src/middlewares/auth.middleware.ts",
            line: 28,
            suggestedFix: "Add `if (!token) return c.json({ error: 'Unauthorized' }, 401);` check.",
            isFixed: false,
          },
          {
            id: "issue-2",
            title: "Downstream Blast Radius Ripple Risk on User Session",
            description: "Modifying authorization header format will break existing frontend session context getters.",
            category: "blast_radius",
            severity: "warning",
            filePath: "frontend/src/store/authStore.ts",
            line: 45,
            suggestedFix: "Ensure backward compatibility for legacy token bearer format.",
            isFixed: false,
          },
          {
            id: "issue-3",
            title: "Missing Error Catching in Async Handler",
            description: "Async database query lacks try-catch wrapper causing potential 500 server crashes.",
            category: "bug",
            severity: "warning",
            filePath: "backend/api-service/src/modules/auth/auth.service.ts",
            line: 62,
            suggestedFix: "Wrap DB query in try-catch and return structured error response.",
            isFixed: false,
          },
        ],
      },
    ];
    setPullRequestsList(mockPRs);
    setSelectedPR(mockPRs[0]);
  };

  useEffect(() => {
    fetchPullRequests();
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
    <div className="flex max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 gap-6 min-h-[calc(100vh-5.5rem)]">
      <Sidebar />

      <div className="flex-1 flex flex-col space-y-6 min-w-0">
        {/* Header Banner */}
        <div className="glass-panel rounded-3xl p-6 sm:p-7 border border-slate-800 relative overflow-hidden shadow-lg shadow-black/20">
          <div className="absolute -right-10 -top-10 w-60 h-60 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 relative z-10">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <Badge variant="primary" size="sm" className="font-mono text-[10px]" dot>
                  Autonomous Code Agent
                </Badge>
                <Badge variant="info" size="sm" className="font-mono text-[10px]">
                  GitHub Live Sync
                </Badge>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
                <GitPullRequest className="w-7 h-7 text-indigo-400" />
                PR Review & Auto-Fix Studio
              </h1>
              <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-2xl leading-relaxed">
                Analyze PR blast radius, detect security vulnerabilities and logic defects using Gemini ReAct orchestrators, and launch autonomous fix PRs directly to GitHub.
              </p>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => fetchPullRequests(true)}
                disabled={isLoading}
                leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
              >
                Sync with GitHub
              </Button>
            </div>
          </div>
        </div>

        {/* Global Action Error Alert */}
        {actionError && (
          <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2 animate-fade-in">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{actionError}</span>
          </div>
        )}

        {/* Main Work Area: 2-Column Split */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[600px]">
          {/* Left Column: PR List (4 cols) */}
          <div className="lg:col-span-4 flex flex-col glass-panel rounded-3xl border border-slate-800/80 overflow-hidden shadow-xl">
            <div className="p-4 border-b border-slate-800/80 bg-slate-900/40 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 shrink-0">
                <GitPullRequest className="w-4 h-4 text-indigo-400" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 font-mono">
                  Pull Requests ({pullRequestsList.length})
                </h3>
              </div>

              {availableRepos.length > 0 && (
                <select
                  value={selectedRepoFilter}
                  onChange={(e) => setSelectedRepoFilter(e.target.value)}
                  className="bg-slate-950 text-slate-300 text-[11px] font-mono rounded-lg border border-slate-800 px-2 py-1 focus:outline-none focus:border-indigo-500 max-w-[170px] truncate"
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
                  <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mx-auto">
                    <GitPullRequest className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-slate-200">
                      {isLoading ? "Fetching Pull Requests..." : "No Pull Requests Found"}
                    </p>
                    <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
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
                    <Link href="/repositories">
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-xs font-mono w-full justify-center text-slate-300"
                      >
                        Manage Connected Repos
                      </Button>
                    </Link>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={createMockPRsIfEmpty}
                      className="text-[11px] font-mono text-indigo-400 hover:text-indigo-300"
                    >
                      Load Interactive Demo PR
                    </Button>
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
                      className={`p-3.5 rounded-2xl border transition-all duration-200 cursor-pointer ${
                        isSelected
                          ? "bg-indigo-950/40 border-indigo-500/70 shadow-lg shadow-indigo-500/10 ring-1 ring-indigo-500/30"
                          : "bg-slate-950/40 border-slate-800/80 hover:border-slate-700 hover:bg-slate-900/60"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-1.5">
                        <span className="text-[11px] font-mono font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-md border border-indigo-500/20">
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
                          <span className="text-[10px] font-medium text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded-md border border-slate-700/50">
                            Pending Review
                          </span>
                        )}
                      </div>

                      <h4 className="text-xs font-bold text-slate-100 line-clamp-2 leading-snug">
                        {pr.title}
                      </h4>

                      <p className="text-[10px] text-slate-400 font-mono mt-2 flex items-center gap-1.5 truncate">
                        <span className="text-slate-300">{pr.headBranch}</span>
                        <span className="text-slate-500">→</span>
                        <span>{pr.baseBranch}</span>
                      </p>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Right Column: Review Details & Issue Checklist (8 cols) */}
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
              <div className="flex-1 flex flex-col items-center justify-center p-12 glass-panel rounded-3xl border border-slate-800/80 text-center min-h-[400px]">
                <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-indigo-400 mb-4 shadow-xl">
                  <GitPullRequest className="w-8 h-8" />
                </div>
                <h3 className="text-lg font-bold text-white tracking-tight">
                  Select a Pull Request to Review
                </h3>
                <p className="text-xs text-slate-400 mt-1.5 max-w-md leading-relaxed">
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
    <ProtectedRoute>
      <PRReviewContent />
    </ProtectedRoute>
  );
}
