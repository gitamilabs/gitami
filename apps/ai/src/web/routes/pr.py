from fastapi import APIRouter

from src.agents.fixer import run_autonomous_pr_fixer
from src.agents.llm_client import DualLLMClient
from src.agents.reviewer import run_agentic_pr_review
from src.web.deps import get_shared_graph_client, get_shared_vector_client
from src.web.schemas import PRFixRequest, PRReviewRequest

router = APIRouter(tags=["pr"])


@router.post("/api/pr/review")
async def review_pull_request(req: PRReviewRequest):
    """
    Execute autonomous agentic PR review:
    Orchestrator (Gemini) uses Knowledge Base tools + Workers (Groq Llama 3.3 70B) analyze diff hunks.
    """
    # Guardrail: Skip AI fix branches
    if req.head_branch.startswith("ai-fix/") or req.title.lower().startswith("[ai fix]"):
        return {
            "verdict": "ACCEPT",
            "risk_score": 0.0,
            "summary": "Skipped review for AI Fix Agent PR (ai-fix/* branch).",
            "agent_rationale": "Self-review skipped to prevent loop.",
            "issues": [],
            "status": "skipped_ai_fix",
        }

    graph_client = await get_shared_graph_client()
    vector_client = get_shared_vector_client()
    llm_client = DualLLMClient()

    raw_diff = req.diff_text or ""
    if not raw_diff:
        raw_diff = (
            f"PR Title: {req.title}\n"
            f"PR Description: {req.body}\n"
            f"Base Branch: {req.base_branch}\n"
            f"Head Branch: {req.head_branch}\n\n"
            f"/// PR Diff changes in {req.repo_id} for head branch {req.head_branch} ///\n"
        )

    result = await run_agentic_pr_review(
        client=graph_client,
        repo_id=req.repo_id,
        branch=req.head_branch,
        changed_symbols=[],
        raw_diff_text=raw_diff,
        symbols=[],
        vector_client=vector_client,
        llm_client=llm_client,
        root_directory=req.root_directory,
    )

    return {
        "verdict": result.decision.verdict,
        "risk_score": result.decision.risk_score,
        "summary": result.decision.summary,
        "agent_rationale": result.agent_rationale,
        "issues": result.issues,
        "diff_hunks_count": result.diff_hunks_count,
        "llm_orchestrator_used": result.llm_orchestrator_used,
    }


@router.post("/api/pr/fix")
async def fix_pull_request_issues(req: PRFixRequest):
    """
    Autonomous PR Fix Agent (Surgical Patch Mode):
    Fetches real file content, applies minimal line-level fixes, validates output.
    """
    llm_client = DualLLMClient()
    fix_res = await run_autonomous_pr_fixer(
        repo_id=req.repo_id,
        pr_number=req.pr_number,
        base_branch=req.base_branch,
        issues=req.issues,
        llm_client=llm_client,
        diff_text=req.diff_text,
        existing_file_contents=req.existing_file_contents,
    )

    return {
        "success": fix_res.success,
        "plan_rationale": fix_res.plan_rationale,
        "file_fixes": [
            {"file_path": f.file_path, "content": f.content}
            for f in fix_res.file_fixes
        ],
        "error": fix_res.error,
    }
