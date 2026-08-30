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
from ai_service.agent.diff_parser import parse_git_diff, extract_changed_symbols, DiffHunk
from ai_service.agent.llm_client import DualLLMClient
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

    # 1. Parse raw diff text into hunks & extract changed symbols
    hunks = parse_git_diff(raw_diff_text)
    changed_files = list({h.file_path for h in hunks if h.file_path})

    if not changed_symbols:
        changed_symbols = extract_changed_symbols(hunks, raw_diff_text)

    # 2. Query Knowledge Base via FastMCP tools
    blast_json = await tool_get_blast_radius(client, repo_id=repo_id, changed_symbols=changed_symbols, branch=branch)
    blast_data = json.loads(blast_json)

    # 2b. Retrieve semantic context from Vector KB (non-blocking)
    diff_query = raw_diff_text[:400] if raw_diff_text else repo_id
    semantic_json = await tool_vector_search(vector_client, query_text=diff_query, repo_id=repo_id, n_results=3)

    # 3. Static convention and diff checks
    ast_violations = check_conventions(symbols)
    diff_violations = check_diff_conventions(raw_diff_text)
    all_violations = ast_violations + diff_violations

    violations_dicts = [
        {"rule": v.rule_id, "file": v.file_path, "line": v.line, "msg": v.message, "severity": v.severity}
        for v in all_violations
    ]

    # 4. Invoke Groq Worker Node for parallel file diff inspection
    worker_system = get_prompt("pr_reviewer_worker")

    worker_prompt = (
        f"Target Repo: '{repo_id}' (branch: '{branch}')\n"
        f"Modified Symbols: {changed_symbols}\n"
        f"Analyze the following pull request diff for bugs, invalid method calls, and errors:\n\n{raw_diff_text[:5000]}"
    )
    worker_raw = await llm_client.run_worker(worker_prompt, worker_system)

    structured_issues: List[Dict[str, Any]] = []

    # Parse JSON from Groq worker
    try:
        clean_json = worker_raw.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.startswith("```"):
            clean_json = clean_json[3:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        worker_parsed = json.loads(clean_json.strip())
        w_issues = worker_parsed.get("issues", [])
        if isinstance(w_issues, list):
            for item in w_issues:
                structured_issues.append({
                    "id": str(uuid.uuid4()),
                    "title": item.get("title", "Code Issue Detected"),
                    "description": item.get("description", "Potential flaw found during deep diff analysis."),
                    "category": item.get("category", "bug"),
                    "severity": item.get("severity", "error" if "invalid" in item.get("title", "").lower() or "error" in item.get("title", "").lower() else "warning"),
                    "file_path": item.get("file_path", changed_files[0] if changed_files else "codebase"),
                    "line": item.get("line", 1),
                    "suggested_fix": item.get("suggested_fix", ""),
                })
    except Exception as e:
        logger.warning(f"Worker JSON parse notice: {e}")

    # 5. Invoke Google Gemini Orchestrator for RAG synthesis & architectural evaluation
    orch_prompt = build_orchestrator_prompt(
        repo_id=repo_id,
        branch=branch,
        changed_files=changed_files,
        changed_symbols=changed_symbols,
        blast_radius_json=blast_json,
        diff_text=raw_diff_text,
        convention_violations=violations_dicts,
        semantic_context=semantic_json,
    )
    orchestrator_response = await llm_client.run_orchestrator(orch_prompt, get_prompt("pr_orchestrator"))

    # 6. Formulate final suggestions and decision verdict
    suggestions: List[Suggestion] = []

    # Add convention violations to issues list
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
        suggestions.append(
            Suggestion(
                file_path=v.file_path,
                line=v.line,
                description=f"[{v.rule_id}] {v.message}",
                category="convention",
                severity=v.severity,
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

    if base_blast_risk > 5.0:
        affected_names = [a.get("qualified_name") for a in blast_data.get("affected_symbols", [])[:3]]
        primary_file = changed_files[0] if changed_files else "codebase"
        structured_issues.append({
            "id": str(uuid.uuid4()),
            "title": f"High Blast Radius Ripple Effect (Risk Score: {base_blast_risk})",
            "description": f"This change affects {total_affected} downstream symbols: {', '.join(affected_names)}",
            "category": "blast_radius",
            "severity": "error" if base_blast_risk > 7.0 else "warning",
            "file_path": primary_file,
            "line": 1,
            "suggested_fix": "Verify downstream call sites and run integration tests for affected dependencies.",
        })

    # Determine verdict: SUGGEST if actionable issues/suggestions or high risk, else ACCEPT
    has_errors = any(i.get("severity") == "error" for i in structured_issues)
    has_actionable_issues = any(i.get("severity") in ("error", "warning") for i in structured_issues) or len(suggestions) > 0
    is_high_risk = composite_risk_score > 5.0

    verdict: Verdict = "SUGGEST" if (is_high_risk or has_errors or has_actionable_issues) else "ACCEPT"

    summary_text = (
        f"Agentic Review Verdict: {verdict}. Composite Risk Score: {composite_risk_score}/10.0. "
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

