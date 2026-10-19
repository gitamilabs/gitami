import React from "react";
import { ShieldAlert, ShieldCheck, AlertTriangle, Cpu, CheckCircle2, GitPullRequest, ArrowUpRight, Trash2, Loader2 } from "lucide-react";
import { PRReviewData } from "@/lib/types";

interface PRReviewCardProps {
  review: PRReviewData | null;
  prNumber: number;
  title: string;
  author?: string;
  headBranch: string;
  baseBranch: string;
  htmlUrl?: string;
  onEvaluateNow?: () => void;
  isEvaluating?: boolean;
  onDelete?: () => void;
  isDeleting?: boolean;
}

export const PRReviewCard: React.FC<PRReviewCardProps> = ({
  review,
  prNumber,
  title,
  author,
  headBranch,
  baseBranch,
  htmlUrl,
  onEvaluateNow,
  isEvaluating = false,
  onDelete,
  isDeleting = false,
}) => {
  if (!review) {
    return (
      <div className="bg-[#11131a] border border-white/[0.06] rounded-xl p-6 mb-6 shadow-sm relative overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="p-3 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold px-2 py-0.5 bg-white/[0.05] text-indigo-300 rounded border border-white/[0.08]">
                  PR #{prNumber}
                </span>
                <h3 className="text-base font-bold text-white tracking-tight">
                  {title}
                </h3>
              </div>
              <p className="text-xs text-zinc-400 font-mono mt-1">
                <span className="text-zinc-300">{headBranch}</span> → <span>{baseBranch}</span> • Author:{" "}
                <span className="text-zinc-300">{author || "contributor"}</span>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {onEvaluateNow && (
              <button
                onClick={onEvaluateNow}
                disabled={isEvaluating}
                className="px-4 py-2 bg-white hover:bg-zinc-200 disabled:opacity-50 text-black rounded-lg font-semibold text-xs flex items-center gap-2 transition-all cursor-pointer shrink-0"
              >
                {isEvaluating ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Analyzing PR with GitAmi...</span>
                  </>
                ) : (
                  <>
                    <Cpu className="w-4 h-4" />
                    <span>Run GitAmi PR Review</span>
                  </>
                )}
              </button>
            )}
            {onDelete && (
              <button
                onClick={onDelete}
                disabled={isDeleting || isEvaluating}
                className="p-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 rounded-lg text-xs transition-colors cursor-pointer shrink-0"
                title="Delete PR"
              >
                {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  const isSkipped = review.status === "skipped_ai_fix" || headBranch.startsWith("ai-fix/");
  const isAccept = review.verdict === "ACCEPT";
  const riskScore = review.riskScore || 0;
  const getRiskColor = (score: number) => {
    if (score >= 5) return "text-rose-400 bg-rose-500/10 border-rose-500/30";
    if (score >= 2.5) return "text-amber-400 bg-amber-500/10 border-amber-500/30";
    return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
  };

  return (
    <div className="bg-[#11131a] border border-white/[0.06] rounded-xl p-6 mb-6 shadow-sm relative overflow-hidden">
      {/* Header section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.06] pb-5">
        <div className="flex items-start gap-3.5">
          <div
            className={`p-3 rounded-xl border mt-0.5 ${
              isSkipped
                ? "bg-purple-500/10 text-purple-400 border-purple-500/20"
                : isAccept
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                : "bg-amber-500/10 text-amber-400 border-amber-500/20"
            }`}
          >
            <GitPullRequest className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-bold font-mono px-2 py-0.5 bg-white/[0.05] text-indigo-300 rounded border border-white/[0.08]">
                PR #{prNumber}
              </span>
              <h3 className="text-base sm:text-lg font-bold text-white tracking-tight">
                {title}
              </h3>
              {htmlUrl && (
                <a
                  href={htmlUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-indigo-400 hover:text-indigo-300 inline-flex items-center gap-1 font-mono hover:underline"
                >
                  GitHub <ArrowUpRight className="w-3 h-3" />
                </a>
              )}
            </div>
            <p className="text-xs text-zinc-400 font-mono mt-1 flex items-center gap-2">
              <span className="text-zinc-300 font-semibold">{headBranch}</span> →{" "}
              <span>{baseBranch}</span> • Author:{" "}
              <span className="text-zinc-300">{author || "contributor"}</span>
            </p>
          </div>
        </div>

        {/* Verdict Badge & Risk Score */}
        <div className="flex items-center gap-2.5 shrink-0">
          {isSkipped ? (
            <div className="px-3 py-1.5 rounded-lg text-xs font-bold bg-purple-500/15 border border-purple-500/30 text-purple-300 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4" />
              AI Fix PR (Skipped Review)
            </div>
          ) : (
            <>
              <div
                className={`px-3 py-1.5 rounded-lg text-xs font-bold border flex items-center gap-2 ${
                  isAccept
                    ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-300"
                    : "bg-amber-500/15 border-amber-500/30 text-amber-300"
                }`}
              >
                {isAccept ? (
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                ) : (
                  <ShieldAlert className="w-4 h-4 text-amber-400" />
                )}
                Verdict: {review.verdict}
              </div>

              <div className={`px-3 py-1.5 rounded-lg text-xs font-bold border ${getRiskColor(riskScore)}`}>
                Risk: {riskScore.toFixed(1)} / 10
              </div>
            </>
          )}

          {onDelete && (
            <button
              onClick={onDelete}
              disabled={isDeleting}
              className="p-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 rounded-lg text-xs transition-colors cursor-pointer shrink-0"
              title="Delete PR"
            >
              {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
            </button>
          )}
        </div>
      </div>

      {/* Summary section */}
      <div className="mt-5 space-y-3">
        <div className="bg-[#0c0d12] rounded-xl p-4 border border-white/[0.06]">
          <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5 font-mono">
            <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400" /> GitAmi Review Summary
          </h4>
          <p className="text-xs sm:text-sm text-zinc-200 leading-relaxed font-sans">
            {review.summary}
          </p>
        </div>

        {/* Agent Rationale */}
        {review.agentRationale && (
          <div className="bg-[#0c0d12] rounded-xl p-4 border border-white/[0.06]">
            <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5 font-mono">
              <Cpu className="w-3.5 h-3.5 text-indigo-400" /> Review Evidence & Rationale
            </h4>
            <div className="text-xs text-zinc-300 font-mono whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto pr-2 custom-scrollbar">
              {review.agentRationale}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
