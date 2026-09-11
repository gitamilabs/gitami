import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

from ai_service.graph.client import Neo4jClient
from ai_service.vector.client import VectorKBClient
from ai_service.mcp.tools import (
    tool_get_blast_radius,
    tool_get_file_dependencies,
    tool_vector_search,
    tool_cpg_reachable_guards,
    tool_cpg_callers_with_args,
)
from ai_service.analysis.blast_radius import compute_blast_radius
from ai_service.analysis.conventions import check_conventions, check_diff_conventions, ConventionViolation
from ai_service.analysis.decision import DecisionResult, Verdict, Suggestion
from ai_service.agent.diff_parser import parse_git_diff, extract_changed_symbols, DiffHunk
from ai_service.agent.llm_client import DualLLMClient
from ai_service.prompts import get_prompt
from ai_service.agent.prompts import build_orchestrator_prompt

logger = logging.getLogger(__name__)


@dataclass
class AgentReviewResult:
    decision: DecisionResult
    agent_rationale: str
    diff_hunks_count: int
    llm_orchestrator_used: bool
    issues: List[Dict[str, Any]] = field(default_factory=list)


async def _run_cpg_analysis(repo_id: str, syms: List[str]) -> str:
    """Retrieve Joern CPG control-flow guards and callers for changed symbols concurrently."""
    if not syms:
        return "No changed symbols identified for CPG analysis."

    target_syms = syms[:5]

    async def _safe_guard(sym: str) -> Dict[str, Any]:
        try:
            res = await tool_cpg_reachable_guards(repo_id=repo_id, symbol_name=sym)
            return json.loads(res) if isinstance(res, str) and res.strip().startswith("{") else {"raw": res}
        except Exception as e:
            return {"symbol": sym, "error": str(e)}

    async def _safe_callers(sym: str) -> Dict[str, Any]:
        try:
            res = await tool_cpg_callers_with_args(repo_id=repo_id, symbol_name=sym)
            return json.loads(res) if isinstance(res, str) and res.strip().startswith("{") else {"raw": res}
        except Exception as e:
            return {"symbol": sym, "error": str(e)}

    guard_tasks = [_safe_guard(s) for s in target_syms]
    caller_tasks = [_safe_callers(s) for s in target_syms]

    all_cpg = await asyncio.gather(*guard_tasks, *caller_tasks, return_exceptions=True)
    guards_res = all_cpg[: len(target_syms)]
    callers_res = all_cpg[len(target_syms) :]

    cpg_entries = []
    for i, s in enumerate(target_syms):
        g = guards_res[i] if not isinstance(guards_res[i], Exception) else str(guards_res[i])
        c = callers_res[i] if not isinstance(callers_res[i], Exception) else str(callers_res[i])
        cpg_entries.append({"symbol": s, "reachable_guards": g, "callers_with_args": c})

    return json.dumps(cpg_entries, indent=2)


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

    # 2. Static convention and diff checks
    ast_violations = check_conventions(symbols)
    diff_violations = check_diff_conventions(raw_diff_text)
    all_violations = ast_violations + diff_violations

    violations_dicts = [
        {"rule": v.rule_id, "file": v.file_path, "line": v.line, "msg": v.message, "severity": v.severity}
        for v in all_violations
    ]

    # 3. Formulate prompts and queries
    diff_query = raw_diff_text[:2000] if raw_diff_text else repo_id
    worker_system = get_prompt("pr_reviewer_worker")
    worker_prompt = (
        f"Target Repo: '{repo_id}' (branch: '{branch}')\n"
        f"Changed Files: {changed_files}\n"
        f"Modified Symbols: {changed_symbols}\n"
        f"Systematically inspect EVERY file listed in Changed Files ({changed_files}) for runtime bugs, unhandled promise rejections, missing try-catch error handling around dynamic imports or API calls, and logic flaws:\n\n{raw_diff_text[:12000]}"
    )

    # 4. Concurrent execution of Neo4j Blast Radius, Vector Search, Joern CPG, and Groq Worker
    blast_task = tool_get_blast_radius(client, repo_id=repo_id, changed_symbols=changed_symbols, branch=branch)
    vector_task = tool_vector_search(vector_client, query_text=diff_query, repo_id=repo_id, n_results=3)
    cpg_task = _run_cpg_analysis(repo_id=repo_id, syms=changed_symbols)
    worker_task = llm_client.run_worker(worker_prompt, worker_system)

    results = await asyncio.gather(blast_task, vector_task, cpg_task, worker_task, return_exceptions=True)

    blast_json = results[0] if isinstance(results[0], str) else json.dumps({"risk_score": 0.0, "total_affected": 0})
    semantic_json = results[1] if isinstance(results[1], str) else "[]"
    cpg_context = results[2] if isinstance(results[2], str) else "CPG analysis unavailable."
    worker_raw = results[3] if isinstance(results[3], str) else "{}"

    try:
        blast_data = json.loads(blast_json)
    except Exception:
        blast_data = {"risk_score": 0.0, "total_affected": 0}

    # 5. Parse candidate issues from worker node
    candidate_issues: List[Dict[str, Any]] = []
    try:
        clean_json = re.sub(r"<think>.*?</think>", "", worker_raw, flags=re.DOTALL).strip()
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_json, re.DOTALL)
        if not json_match:
            json_match = re.search(r"(\{\s*\"issues\"\s*:\s*\[.*?\]\s*\})", clean_json, re.DOTALL)
        raw_to_parse = json_match.group(1) if json_match else clean_json
        worker_parsed = json.loads(raw_to_parse.strip())
        w_issues = worker_parsed.get("issues", [])
        if isinstance(w_issues, list):
            for item in w_issues:
                candidate_issues.append({
                    "id": str(uuid.uuid4()),
                    "title": item.get("title", "Code Issue Detected"),
                    "description": item.get("description", "Potential flaw found during deep diff analysis."),
                    "category": item.get("category", "bug"),
                    "severity": item.get("severity", "warning"),
                    "file_path": item.get("file_path", changed_files[0] if changed_files else "codebase"),
                    "line": item.get("line", 1),
                    "suggested_fix": item.get("suggested_fix", ""),
                })
    except Exception as e:
        logger.warning(f"Worker JSON parse notice: {e}")

    # 5b. Fallback: If candidate_issues is empty, run direct inspection via active LLM (Ollama/Groq/Gemini)
    if not candidate_issues:
        try:
            worker_fallback_raw = await llm_client.call_json(
                worker_prompt, worker_system, temperature=0.2
            )
            if worker_fallback_raw:
                gem_clean = re.sub(r"<think>.*?</think>", "", worker_fallback_raw, flags=re.DOTALL).strip()
                json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", gem_clean, re.DOTALL)
                if not json_match:
                    json_match = re.search(r"(\{\s*\"issues\"\s*:\s*\[.*?\]\s*\})", gem_clean, re.DOTALL)
                raw_to_parse = json_match.group(1) if json_match else gem_clean
                gem_parsed = json.loads(raw_to_parse.strip())
                g_issues = gem_parsed.get("issues", [])
                if isinstance(g_issues, list):
                    for item in g_issues:
                        candidate_issues.append({
                            "id": str(uuid.uuid4()),
                            "title": item.get("title", "Code Issue Detected"),
                            "description": item.get("description", "Potential flaw found during deep diff analysis."),
                            "category": item.get("category", "bug"),
                            "severity": item.get("severity", "warning"),
                            "file_path": item.get("file_path", changed_files[0] if changed_files else "codebase"),
                            "line": item.get("line", 1),
                            "suggested_fix": item.get("suggested_fix", ""),
                        })
        except Exception as ge:
            logger.warning(f"Fallback worker inspection notice: {ge}")

    # 6. Invoke Primary Orchestrator (Ollama / Dual-LLM) for RAG synthesis & 5-Step Falsification
    orch_prompt = build_orchestrator_prompt(
        repo_id=repo_id,
        branch=branch,
        changed_files=changed_files,
        changed_symbols=changed_symbols,
        blast_radius_json=blast_json,
        diff_text=raw_diff_text[:16000],
        convention_violations=violations_dicts,
        semantic_context=semantic_json,
        cpg_context=cpg_context,
        candidate_issues=candidate_issues,
    )
    orchestrator_response = await llm_client.run_orchestrator(orch_prompt, get_prompt("pr_orchestrator"))

    # 7. Extract confirmed issues surviving falsification & merge candidate issues
    structured_issues: List[Dict[str, Any]] = []
    seen_issue_keys = set()
    orchestrator_confirmed = None

    try:
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", orchestrator_response, re.DOTALL)
        if not json_match:
            json_match = re.search(r"(\{\s*\"confirmed_issues\"\s*:\s*\[.*?\]\s*\})", orchestrator_response, re.DOTALL)
        if json_match:
            parsed_orch = json.loads(json_match.group(1))
            if "confirmed_issues" in parsed_orch and isinstance(parsed_orch["confirmed_issues"], list):
                orchestrator_confirmed = parsed_orch["confirmed_issues"]
    except Exception as e:
        logger.debug(f"Orchestrator confirmed issues parse notice: {e}")

    # Add candidate issues from worker node
    for item in candidate_issues:
        key = (item.get("file_path", ""), item.get("line", 0), item.get("title", ""))
        if key not in seen_issue_keys:
            seen_issue_keys.add(key)
            structured_issues.append(item)

    # Merge any confirmed issues uniquely identified by orchestrator
    if orchestrator_confirmed and len(orchestrator_confirmed) > 0:
        for item in orchestrator_confirmed:
            f = item.get("file_path", changed_files[0] if changed_files else "codebase")
            l = item.get("line", 1)
            t = item.get("title", "Code Issue Detected")
            key = (f, l, t)
            if key not in seen_issue_keys:
                seen_issue_keys.add(key)
                structured_issues.append({
                    "id": str(uuid.uuid4()),
                    "title": t,
                    "description": item.get("description", "Issue verified by orchestrator."),
                    "category": item.get("category", "bug"),
                    "severity": item.get("severity", "warning"),
                    "file_path": f,
                    "line": l,
                    "suggested_fix": item.get("suggested_fix", ""),
                })

    # Add critical convention violations to structured_issues (style suggestions stay in suggestions)
    for v in all_violations:
        if v.severity == "error":
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

    # Suggestions list for non-blocking code quality feedback
    suggestions: List[Suggestion] = []
    for v in all_violations:
        suggestions.append(
            Suggestion(
                file_path=v.file_path,
                line=v.line,
                description=f"[{v.rule_id}] {v.message}",
                category="convention",
                severity=v.severity,
            )
        )

    # 8. Composite risk score and final verdict
    base_blast_risk = blast_data.get("risk_score", 0.0) if isinstance(blast_data, dict) else 0.0
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

    has_errors = any(i.get("severity") == "error" for i in structured_issues)
    has_actionable_issues = any(i.get("severity") in ("error", "warning") for i in structured_issues)
    is_high_risk = composite_risk_score > 5.0

    verdict: Verdict = "SUGGEST" if (is_high_risk or has_errors or has_actionable_issues) else "ACCEPT"
    if "verdict: accept" in orchestrator_response.lower() and not has_errors and composite_risk_score <= 5.0 and len(structured_issues) == 0:
        verdict = "ACCEPT"

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

