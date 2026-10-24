from fastapi import APIRouter

from src.agents import CodeAgent, DocAgent, FixPlan, InvestigationAgent, IssueAgent
from src.agents.llm_client import DualLLMClient
from src.web.deps import get_shared_graph_client, get_shared_vector_client
from src.web.schemas import (
    CodeExecuteRequest,
    CodePlanRequest,
    DocGenerateRequest,
    InvestigationRequest,
    IssueAnalyzeRequest,
)

router = APIRouter(tags=["agents"])


@router.post("/api/investigate")
async def investigate_codebase(req: InvestigationRequest):
    """
    Executes the Curated Investigation Agent:
    - Fast single-shot path for informational questions
    - Up to 8-step iterative hypothesis testing loop for root cause debugging & incidents
    """
    agent = InvestigationAgent(
        llm_client=DualLLMClient(),
        graph_client=await get_shared_graph_client(),
        vector_client=get_shared_vector_client(),
    )
    result = await agent.run(
        query=req.query,
        repo_id=req.repo_id,
        branch=req.branch or "main",
        is_incident=req.is_incident,
        incident_context=req.incident_context,
        max_steps=req.max_steps or 8,
    )
    return result.to_dict()


@router.post("/api/issue/analyze")
async def analyze_github_issue(req: IssueAnalyzeRequest):
    """
    Executes the Curated Issue Agent:
    - Spam detection
    - Duplicate detection across open/closed issues
    - Criticality scoring (1-10)
    - Domain tagging
    - AI Code Suspected flag
    """
    agent = IssueAgent(
        llm_client=DualLLMClient(),
        graph_client=await get_shared_graph_client(),
        vector_client=get_shared_vector_client(),
    )
    result = await agent.run(
        repo_id=req.repo_id,
        issue_number=req.issue_number,
        title=req.title,
        body=req.body or "",
        author=req.author or "unknown",
        existing_labels=req.labels,
        existing_issues=req.existing_issues,
    )
    return result.to_dict()


@router.post("/api/doc/generate")
async def generate_documentation(req: DocGenerateRequest):
    """
    Executes the Curated Doc Agent:
    - Generates workflow guides, onboarding docs per domain, or weekly changelogs
    - Automatically feeds generated docs back into the Vector KB
    """
    agent = DocAgent(
        llm_client=DualLLMClient(),
        graph_client=await get_shared_graph_client(),
        vector_client=get_shared_vector_client(),
    )
    if req.doc_type == "onboarding_doc":
        res = await agent.generate_onboarding_doc(
            repo_id=req.repo_id,
            domain=req.topic,
            branch=req.branch or "main",
            feed_to_kb=req.feed_to_kb,
        )
    elif req.doc_type == "weekly_changelog":
        res = await agent.generate_weekly_changelog(
            repo_id=req.repo_id,
            merged_prs=req.merged_prs or [],
            week_label=req.topic or "This Week",
        )
    else:
        res = await agent.generate_workflow_guide(
            repo_id=req.repo_id,
            feature_name=req.topic,
            branch=req.branch or "main",
            feed_to_kb=req.feed_to_kb,
        )
    return res.to_dict()


@router.post("/api/code/plan")
async def plan_code_fix(req: CodePlanRequest):
    """
    Executes Code Agent Stage 1:
    - Generates a surgical fix plan (files to touch, approach, test strategy)
    - Waits for maintainer approval before executing
    """
    agent = CodeAgent(
        llm_client=DualLLMClient(),
        graph_client=await get_shared_graph_client(),
        vector_client=get_shared_vector_client(),
    )
    plan = await agent.generate_fix_plan(
        repo_id=req.repo_id,
        issue_title=req.issue_title,
        issue_description=req.issue_description,
        trigger_source=req.trigger_source,
        affected_files=req.affected_files,
        branch=req.branch or "main",
    )
    return plan.to_dict()


@router.post("/api/code/execute")
async def execute_code_fix(req: CodeExecuteRequest):
    """
    Executes Code Agent Stage 2:
    - Synthesizes reproduction test and verified implementation patch for an approved plan
    """
    agent = CodeAgent(
        llm_client=DualLLMClient(),
        graph_client=await get_shared_graph_client(),
        vector_client=get_shared_vector_client(),
    )
    p = req.plan
    plan_obj = FixPlan(
        plan_id=p.get("plan_id", "plan_1"),
        repo_id=p.get("repo_id", ""),
        trigger_source=p.get("trigger_source", "review"),
        summary=p.get("summary", ""),
        files_to_touch=p.get("files_to_touch", []),
        approach=p.get("approach", ""),
        test_strategy=p.get("test_strategy", ""),
        risk_assessment=p.get("risk_assessment", "medium"),
        needs_approval=False,
        approved=True,
    )
    result = await agent.execute_approved_plan(
        plan=plan_obj,
        existing_file_contents=req.existing_file_contents,
        maintainer_notes=req.maintainer_notes,
    )
    return result.to_dict()
