import json
import uuid
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

from ai_service.graph.client import Neo4jClient
from ai_service.vector.client import VectorKBClient
from ai_service.mcp.tools import tool_get_blast_radius, tool_get_file_dependencies, tool_vector_search
from ai_service.analysis.blast_radius import compute_blast_radius
from ai_service.analysis.conventions import check_conventions, check_diff_conventions, ConventionViolation
from ai_service.analysis.decision import DecisionResult, Verdict, Suggestion
from ai_service.agent.diff_parser import parse_git_diff, extract_changed_symbols, chunk_diff_by_files
from ai_service.agent.llm_client import DualLLMClient
from ai_service.agent.react_reviewer import normalize_issues, deduplicate_issues
from ai_service.prompts import get_prompt
from ai_service.agent.prompts import (
    build_orchestrator_prompt,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentReviewResult:
    decision: DecisionResult
    agent_rationale: str
    diff_hunks_count: int
    llm_orchestrator_used: bool
    issues: List[Dict[str, Any]] = field(default_factory=list)


async def run_agentic_pr_review(
    client: Neo4jClient,
    repo_id: str,
    branch: str,
    changed_symbols: List[str],
    raw_diff_text: str,
    symbols: list,
    vector_client: Optional[VectorKBClient] = None,
    llm_client: Optional[DualLLMClient] = None,
) -> AgentReviewResult:
    """Execute autonomous agentic PR review using FastMCP knowledge base tools + Gemini/Groq dual LLMs."""
    if llm_client is None:
        llm_client = DualLLMClient()

    if vector_client is None:
        vector_client = VectorKBClient()

    # Delegate to autonomous ReAct PR Review Agent
    try:
        from ai_service.agent.react_reviewer import PrReviewReActAgent
        react_reviewer = PrReviewReActAgent(llm_client=llm_client)
        return await react_reviewer.review(
            repo_id=repo_id,
            branch=branch,
            raw_diff_text=raw_diff_text,
            changed_symbols=changed_symbols,
            symbols=symbols,
            graph_client=client,
            vector_client=vector_client,
            max_steps=2,
        )
    except Exception as e:
        logger.warning(f"ReAct agent review fallback notice ({e}), proceeding with standard pipeline...")

    # 1. Parse raw diff text into hunks & extract changed symbols
    hunks = parse_git_diff(raw_diff_text)
    changed_files = list({h.file_path for h in hunks if h.file_path})

    if not changed_symbols:
        changed_symbols = extract_changed_symbols(hunks, raw_diff_text)

    # 2. Query Knowledge Base via FastMCP tools
    blast_json = await tool_get_blast_radius(client, repo_id=repo_id, changed_symbols=changed_symbols, branch=branch)
    blast_data = json.loads(blast_json)

    # 2b. Retrieve semantic context from Vector KB (non-blocking)
    diff_query = raw_diff_text[:600] if raw_diff_text else repo_id
    semantic_json = await tool_vector_search(vector_client, query_text=diff_query, repo_id=repo_id, n_results=3)

    # 3. Static convention and diff checks
    ast_violations = check_conventions(symbols or [])
    diff_violations = check_diff_conventions(raw_diff_text or "")
    all_violations = ast_violations + diff_violations

    violations_dicts = [
        {"rule": v.rule_id, "file": v.file_path, "line": v.line, "msg": v.message, "severity": v.severity}
        for v in all_violations
    ]

    # 4. Invoke Groq Worker Node for focused code inspection
    worker_raw_issues: List[Dict[str, Any]] = []
    diff_snippet = raw_diff_text[:5000] if raw_diff_text else "# Empty Diff"
    worker_system = get_prompt("pr_reviewer_worker")

    worker_prompt = (
        f"Target Repo: '{repo_id}' (branch: '{branch}')\n"
        f"Changed Files: {changed_files}\n"
        f"Modified Symbols: {changed_symbols}\n"
        f"Analyze the following pull request diff for bugs, invalid method calls, logic flaws, and security errors:\n\n"
        f"{diff_snippet}"
    )
    try:
        worker_raw = await llm_client.run_worker(worker_prompt, worker_system)
        clean_json = worker_raw.strip()
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0]
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1].split("```")[0]
        first_brace = clean_json.find("{")
        last_brace = clean_json.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            clean_json = clean_json[first_brace : last_brace + 1]
        worker_parsed = json.loads(clean_json.strip())
        w_issues = worker_parsed.get("issues", [])
        if isinstance(w_issues, list):
            worker_raw_issues.extend(w_issues)
    except Exception as e:
        logger.warning(f"Worker JSON parse notice: {e}")

    # 5. Invoke Google Gemini Orchestrator for RAG synthesis & architectural evaluation
    orch_prompt = build_orchestrator_prompt(
        repo_id=repo_id,
        branch=branch,
        changed_files=changed_files,
        changed_symbols=changed_symbols,
        blast_radius_json=blast_json,
        diff_text=raw_diff_text[:5000],
        convention_violations=violations_dicts,
        semantic_context=semantic_json,
    )
    orchestrator_response = await llm_client.run_orchestrator(orch_prompt, get_prompt("pr_orchestrator"))

    # Parse any structured issues from orchestrator
    orch_issues: List[Dict[str, Any]] = []
    try:
        clean_orch = orchestrator_response.strip()
        if "```json" in clean_orch:
            clean_orch = clean_orch.split("```json")[1].split("```")[0]
        elif "```" in clean_orch:
            clean_orch = clean_orch.split("```")[1].split("```")[0]
        first_b = clean_orch.find("{")
        last_b = clean_orch.rfind("}")
        if first_b != -1 and last_b != -1 and last_b > first_b:
            clean_orch = clean_orch[first_b : last_b + 1]
            orch_parsed = json.loads(clean_orch.strip())
            o_issues = orch_parsed.get("issues", [])
            if isinstance(o_issues, list):
                orch_issues.extend(o_issues)
    except Exception:
        pass

    # Prioritize orchestrator issues if available; fallback to worker issues if empty
    if orch_issues:
        all_found = list(orch_issues)
        orch_files = {str(i.get("file_path", "")).strip() for i in orch_issues}
        for wi in worker_raw_issues:
            w_file = str(wi.get("file_path", "")).strip()
            if w_file and w_file not in orch_files:
                all_found.append(wi)
    else:
        all_found = list(worker_raw_issues)

    normalized_issues = normalize_issues(all_found, changed_files)
    structured_issues = deduplicate_issues(normalized_issues)

    # 6. Formulate final suggestions and convention violations
    suggestions: List[Suggestion] = []

    for v in all_violations:
        structured_issues.append({
            "id": str(uuid.uuid4()),
            "title": f"[{v.rule_id}] Style & Convention Violation",
            "description": v.message,
            "category": "convention",
            "severity": v.severity,
            "file_path": v.file_path,
            "line": v.line,
            "suggested_fix": f"Follow project conventions for {v.rule_id}",
        })

    structured_issues = deduplicate_issues(structured_issues)

    for issue in structured_issues:
        suggestions.append(
            Suggestion(
                file_path=issue.get("file_path", "unknown"),
                line=int(issue.get("line", 1) or 1),
                description=f"[{issue.get('category', 'bug').upper()}] {issue.get('title', '')}: {issue.get('description', '')}",
                category=issue.get("category", "bug"),
                severity=issue.get("severity", "warning"),
            )
        )

    # Calculate composite risk score (Neo4j blast radius + Issue severity score)
    base_blast_risk = blast_data.get("risk_score", 0.0)
    total_affected = blast_data.get("total_affected", 0)

    issue_severity_score = 0.0
    for issue in structured_issues:
        sev = str(issue.get("severity", "warning")).lower()
        if sev == "error":
            issue_severity_score += 2.0
        elif sev == "warning":
            issue_severity_score += 0.5
        else:
            issue_severity_score += 0.1

    composite_risk_score = round(min(10.0, max(base_blast_risk, issue_severity_score)), 2)

    # Determine verdict: SUGGEST if actionable issues/suggestions or high risk, else ACCEPT
    has_errors = any(i.get("severity") == "error" for i in structured_issues)
    has_actionable_issues = any(i.get("severity") in ("error", "warning") for i in structured_issues) or len(suggestions) > 0
    is_high_risk = composite_risk_score > 5.0

    verdict: Verdict = "SUGGEST" if (is_high_risk or has_errors or has_actionable_issues) else "ACCEPT"

    summary_text = (
        f"GitAmi Review Verdict: {verdict}. Composite Risk Score: {composite_risk_score}/10.0. "
        f"Detected {len(structured_issues)} item(s) across {len(changed_files)} changed file(s)."
    )

    decision = DecisionResult(
        verdict=verdict,
        risk_score=composite_risk_score,
        suggestions=suggestions,
        summary=summary_text,
    )

    return AgentReviewResult(
        decision=decision,
        agent_rationale=orchestrator_response,
        diff_hunks_count=len(hunks),
        llm_orchestrator_used=llm_client.has_gemini,
        issues=structured_issues,
    )
