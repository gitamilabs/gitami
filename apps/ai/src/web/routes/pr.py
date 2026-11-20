from fastapi import APIRouter, Depends

from src.agents import CodeAgent, ReviewAgent
from src.agents.llm_client import DualLLMClient
from src.graph.client import Neo4jClient
from src.vector.client import VectorKBClient
from src.web.deps import get_shared_graph_client, get_shared_vector_client
from src.web.schemas import PRFixRequest, PRReviewRequest

router = APIRouter(tags=["pr"])


@router.post("/api/pr/review")
async def review_pull_request(
    req: PRReviewRequest,
    graph_client: Neo4jClient = Depends(get_shared_graph_client),
    vector_client: VectorKBClient = Depends(get_shared_vector_client),
):
    """
    Execute Curated Agent PR review:
    Evaluates blast radius (Neo4j), AST conventions, security anti-patterns,
    test coverage gaps, and generates actionable Claude Code checklists.
    """
    # Guardrail: Skip AI fix branches to prevent recursive review loops
    if req.head_branch.startswith("ai-fix/") or req.title.lower().startswith("[ai fix]"):
        return {
            "verdict": "ACCEPT",
            "risk_score": 0.0,
            "summary": "Skipped review for AI Fix Agent PR (ai-fix/* branch).",
            "agent_rationale": "Self-review skipped to prevent loop.",
            "issues": [],
            "status": "skipped_ai_fix",
        }

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

    agent = ReviewAgent(
        llm_client=llm_client,
        graph_client=graph_client,
        vector_client=vector_client,
    )

    result = await agent.run(
        repo_id=req.repo_id,
        pr_number=req.pr_number,
        base_branch=req.base_branch,
        head_branch=req.head_branch,
        title=req.title,
        body=req.body or "",
        diff_text=raw_diff,
        symbols=[],
        changed_symbols=[],
    )

    # Standard backward-compatible issue format for control plane
    issues = [
        {
            "id": item.id,
            "rule": item.category,
            "title": item.title,
            "file": item.file_path,
            "file_path": item.file_path,
            "line": item.line,
            "description": item.description,
            "suggestion": item.suggested_fix,
            "suggested_fix": item.suggested_fix,
            "category": item.category,
            "severity": item.severity,
        }
        for item in result.checklist
    ]

    return {
        # Control plane backward-compatible contract fields
        "verdict": result.verdict,
        "risk_score": result.risk_score,
        "summary": result.summary,
        "agent_rationale": f"Analyzed {len(result.changed_files)} files, blast radius risk: {result.blast_radius.get('risk_level', 'LOW')}",
        "issues": issues,
        "diff_hunks_count": len(result.changed_files),
        "llm_orchestrator_used": "Gemini + Curated ReviewAgent",
        # Enriched analysis fields
        "checklist": [
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "category": item.category,
                "severity": item.severity,
                "file_path": item.file_path,
                "line": item.line,
                "suggested_fix": item.suggested_fix,
            }
            for item in result.checklist
        ],
        "blast_radius": result.blast_radius,
        "changed_files": result.changed_files,
        "changed_symbols": result.changed_symbols,
        "claude_code_export": result.claude_code_export,
    }


@router.post("/api/pr/fix")
async def fix_pull_request_issues(
    req: PRFixRequest,
    graph_client: Neo4jClient = Depends(get_shared_graph_client),
    vector_client: VectorKBClient = Depends(get_shared_vector_client),
):
    """
    Curated Code Agent (Surgical Remediation Mode):
    Uses two-stage fix planning and line-level patching to produce verified file fixes.
    """
    llm_client = DualLLMClient()

    agent = CodeAgent(
        llm_client=llm_client,
        graph_client=graph_client,
        vector_client=vector_client,
    )

    fix_res = await agent.generate_file_fixes(
        repo_id=req.repo_id,
        issues=req.issues,
        existing_file_contents=req.existing_file_contents or {},
        base_branch=req.base_branch,
        pr_number=req.pr_number,
    )

    return {
        "success": fix_res["success"],
        "plan_rationale": fix_res["plan_rationale"],
        "file_fixes": fix_res["file_fixes"],
        "error": fix_res["error"],
    }
