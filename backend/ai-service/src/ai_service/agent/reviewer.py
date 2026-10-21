import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Set

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


def format_cpg_security_summary(
    target_syms: List[str],
    guards_res: List[Any],
    callers_res: List[Any],
) -> str:
    """
    Format Joern CPG control-flow and caller analysis into a structured security briefing.
    Classifies guards into strong sanitizers vs weak/presence checks and enforces a
    zero-false-negative defensive posture for LLM orchestrator reasoning.
    """
    if not target_syms:
        return "No changed symbols identified for CPG analysis."

    SANITIZER_KEYWORDS = (
        "sanitize", "sanitise", "escape", "clean", "param", "prepared",
        "dompurify", "basename", "int(", "float(", "number(", "typeof",
        "isinstance", "zod", "joi", "yup", "validator", "bind"
    )

    sections = [
        "### Joern CPG Structural Control-Flow & Taint Analysis Briefing:",
        "DEFENSIVE SECURITY POLICY (Zero False Negatives): Presence checks (if x) and auth checks (@login_required) do NOT neutralize injection payloads.",
        ""
    ]

    for i, sym in enumerate(target_syms):
        g = guards_res[i] if i < len(guards_res) and not isinstance(guards_res[i], Exception) else {}
        c = callers_res[i] if i < len(callers_res) and not isinstance(callers_res[i], Exception) else {}

        if isinstance(g, str):
            try:
                g = json.loads(g)
            except Exception:
                g = {"guards": [g]} if g else {}

        if isinstance(c, str):
            try:
                c = json.loads(c)
            except Exception:
                c = {"callers_with_args": [c]} if c else {}

        raw_guards = g.get("guards", []) if isinstance(g, dict) else []
        if isinstance(raw_guards, str):
            raw_guards = [raw_guards]

        strong_sanitizers = []
        weak_checks = []

        for guard in raw_guards:
            guard_str = str(guard).strip()
            if not guard_str:
                continue
            if any(k in guard_str.lower() for k in SANITIZER_KEYWORDS):
                strong_sanitizers.append(guard_str)
            else:
                weak_checks.append(guard_str)

        sections.append(f"- **Symbol: `{sym}`**")

        # Report Guard Classification
        if strong_sanitizers:
            sections.append(f"  - Verified Sanitizers/Neutralizers: {', '.join(strong_sanitizers)}")
            sections.append("  - Taint Status: POTENTIALLY SANITIZED (Verify parameter binding in diff)")
        elif weak_checks:
            sections.append(f"  - Non-Sanitizing Guards: {', '.join(weak_checks)}")
            sections.append("  - Taint Status: [WARNING: INSUFFICIENT SANITIZATION — Presence/Auth check only, does NOT neutralize injection]")
        else:
            sections.append("  - Verified Sanitizers: NONE (Unshielded sink)")
            sections.append("  - Taint Status: [CRITICAL: NO SANITIZER DETECTED — High injection exposure if reached by untrusted input]")

        # Report Callers & Args
        raw_callers = c.get("callers_with_args", []) if isinstance(c, dict) else []
        if isinstance(raw_callers, str):
            raw_callers = [line.strip() for line in raw_callers.splitlines() if line.strip()]

        if raw_callers:
            clean_callers = [str(call).strip() for call in raw_callers[:3] if str(call).strip()]
            if clean_callers:
                sections.append(f"  - Observed Call Sites: {'; '.join(clean_callers)}")
            else:
                sections.append("  - Observed Call Sites: Internal or unreferenced in CPG call graph")
        else:
            sections.append("  - Observed Call Sites: None detected in current graph")

        sections.append("")

    return "\n".join(sections).strip()


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

    return format_cpg_security_summary(target_syms, guards_res, callers_res)


def _extract_concept_tokens(text: str) -> Set[str]:
    """Tokenize issue text into keywords including camelCase and snake_case subwords."""
    tokens = set(re.findall(r"[a-zA-Z0-9_]{3,}", text.lower()))
    subwords = re.findall(r"[a-zA-Z][a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)", text)
    for sw in subwords:
        if len(sw) >= 3:
            tokens.add(sw.lower())
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "should", "have",
        "not", "code", "file", "line", "issue", "detected", "potential", "during",
        "analysis", "found", "verified", "orchestrator", "flaw", "possible",
        "does", "will", "without", "into", "been", "being"
    }
    return {t for t in tokens if t not in stopwords}


def _calc_concept_overlap(text1: str, text2: str) -> float:
    """Calculate token overlap similarity with prefix and substring matching."""
    t1 = _extract_concept_tokens(text1)
    t2 = _extract_concept_tokens(text2)
    if not t1 or not t2:
        return 0.0
    exact = t1 & t2
    matched = set(exact)
    for w1 in t1 - exact:
        for w2 in t2 - exact:
            if len(w1) >= 4 and len(w2) >= 4 and (w1 in w2 or w2 in w1 or w1.startswith(w2[:4]) or w2.startswith(w1[:4])):
                matched.add(w1)
                break
    sim_count = len(matched)
    if sim_count == 0:
        return 0.0
    jaccard = sim_count / len(t1 | t2)
    overlap = sim_count / min(len(t1), len(t2))
    return max(jaccard, overlap * 0.75)


def _issue_concept_sim(issue1: Dict[str, Any], issue2: Dict[str, Any]) -> float:
    """Compute composite concept similarity across title, description, and full text."""
    t1 = issue1.get("title", "")
    t2 = issue2.get("title", "")
    d1 = issue1.get("description", "")
    d2 = issue2.get("description", "")
    sim_title = _calc_concept_overlap(t1, t2)
    sim_desc = _calc_concept_overlap(d1, d2)
    sim_full = _calc_concept_overlap(f"{t1} {d1}", f"{t2} {d2}")
    return max(sim_title, sim_desc, sim_full)


def deduplicate_issues(
    issues: List[Dict[str, Any]],
    line_window: int = 15,
    cross_file_threshold: float = 0.48,
) -> List[Dict[str, Any]]:
    """
    Two-pass deduplication:
    Pass 1 (Intra-file):
        Deduplicate issues that target the same file and have overlapping line ranges
        (within line_window) or high concept overlap.
    Pass 2 (Cross-file Sibling Deduplication):
        For multi-file PRs, worker hunks often catch the exact same systemic bug
        (e.g., async callback inside Array.forEach, unhandled promise, missing CSRF token)
        across multiple touched files. In real PR reviews and benchmarks (like Martian),
        ground truth records one issue for a systemic defect rather than repeating it across
        every touched file. Pass 2 identifies cross-file duplicates with high concept
        similarity (>= cross_file_threshold) and suppresses subsequent sibling copies.
    """
    if not issues:
        return []

    # Pass 1: Intra-file deduplication
    pass1: List[Dict[str, Any]] = []
    for issue in issues:
        f = issue.get("file_path", "")
        try:
            l = int(issue.get("line", 0))
        except (ValueError, TypeError):
            l = 0

        is_duplicate = False
        for existing in pass1:
            ef = existing.get("file_path", "")
            if f != ef:
                continue
            try:
                el = int(existing.get("line", 0))
            except (ValueError, TypeError):
                el = 0

            line_diff = abs(l - el)
            overlap = _issue_concept_sim(issue, existing)

            if (line_diff <= line_window and overlap >= 0.25) or (line_diff == 0 and overlap >= 0.15) or (overlap >= 0.60):
                is_duplicate = True
                if issue.get("severity") in ("critical", "error") and existing.get("severity") not in ("critical", "error"):
                    existing["severity"] = issue.get("severity")
                break

        if not is_duplicate:
            pass1.append(issue)

    # Pass 2: Cross-file sibling deduplication
    pass2: List[Dict[str, Any]] = []
    for issue in pass1:
        is_cross_dup = False

        for existing in pass2:
            overlap = _issue_concept_sim(issue, existing)

            if overlap >= cross_file_threshold:
                is_cross_dup = True
                if issue.get("severity") in ("critical", "error") and existing.get("severity") not in ("critical", "error"):
                    existing["severity"] = issue.get("severity")
                break

        if not is_cross_dup:
            pass2.append(issue)

    return pass2



def _chunk_diff_by_files(raw_diff_text: str, max_chunk_chars: int = 22000) -> List[Tuple[List[str], str]]:
    """
    Split a large multi-file git diff into manageable chunks grouped by file,
    ensuring files late in the diff are not truncated.
    Returns list of (files_in_chunk, chunk_diff_text).
    """
    if not raw_diff_text:
        return [([], "")]

    # Split by git diff file headers
    file_diff_pattern = re.compile(r"(?=diff --git a/.* b/.*)")
    parts = file_diff_pattern.split(raw_diff_text)
    parts = [p.strip() for p in parts if p.strip()]

    if not parts:
        return [([], raw_diff_text[:max_chunk_chars])]

    # Extract all files across parts
    all_files: List[str] = []
    for part in parts:
        m = re.search(r"diff --git a/(\S+) b/(\S+)", part)
        if m:
            all_files.append(m.group(1))

    if len(raw_diff_text) <= max_chunk_chars:
        return [(all_files if all_files else ["modified_files"], raw_diff_text)]

    chunks: List[Tuple[List[str], str]] = []
    curr_files: List[str] = []
    curr_text: List[str] = []
    curr_len = 0

    for part in parts:
        m = re.search(r"diff --git a/(\S+) b/(\S+)", part)
        fname = m.group(1) if m else "unknown"

        part_len = len(part)
        if curr_len + part_len > max_chunk_chars and curr_text:
            chunks.append((curr_files, "\n\n".join(curr_text)))
            curr_files = [fname]
            curr_text = [part[:max_chunk_chars]]
            curr_len = min(part_len, max_chunk_chars)
        else:
            curr_files.append(fname)
            curr_text.append(part)
            curr_len += part_len

    if curr_text:
        chunks.append((curr_files, "\n\n".join(curr_text)))

    return chunks


def _parse_worker_issues(worker_raw: str, default_files: List[str]) -> List[Dict[str, Any]]:
    """Extract structured candidate issues from worker node JSON/markdown output."""
    candidate_issues: List[Dict[str, Any]] = []
    if not worker_raw:
        return candidate_issues
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
                    "file_path": item.get("file_path", default_files[0] if default_files else "codebase"),
                    "line": item.get("line", 1),
                    "suggested_fix": item.get("suggested_fix", ""),
                })
    except Exception as e:
        logger.warning(f"Worker JSON parse notice: {e}")
    return candidate_issues


async def run_agentic_pr_review(
    client: Optional[Neo4jClient] = None,
    repo_id: str = "repo",
    branch: str = "main",
    changed_symbols: Optional[List[str]] = None,
    raw_diff_text: str = "",
    symbols: Optional[list] = None,
    vector_client: Optional[VectorKBClient] = None,
    llm_client: Optional[DualLLMClient] = None,
    mode: str = "auto",
) -> AgentReviewResult:
    """Execute autonomous agentic PR review using FastMCP knowledge base tools + Gemini/Ollama dual LLMs."""
    if llm_client is None:
        llm_client = DualLLMClient()

    if vector_client is None:
        vector_client = VectorKBClient()

    if symbols is None:
        symbols = []

    if changed_symbols is None:
        changed_symbols = []

    is_text_rag = (mode == "text_rag") or (client is None)

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

    # Chunk diff by files to prevent dropping files in large PRs
    diff_chunks = _chunk_diff_by_files(raw_diff_text, max_chunk_chars=22000)

    # 4. Concurrent execution of Blast Radius, Vector Search, Joern CPG, and Worker Node(s)
    if not is_text_rag and client is not None:
        blast_task = tool_get_blast_radius(client, repo_id=repo_id, changed_symbols=changed_symbols, branch=branch)
        cpg_task = _run_cpg_analysis(repo_id=repo_id, syms=changed_symbols)
    else:
        async def _dummy_blast():
            return json.dumps({"risk_score": 0.0, "total_affected": 0, "mode": "text_rag"})
        async def _dummy_cpg():
            return "Text-RAG mode active (pure diff & vector review). AST & Graph reasoning performed directly on code diff context."
        blast_task = _dummy_blast()
        cpg_task = _dummy_cpg()

    vector_task = tool_vector_search(vector_client, query_text=diff_query, repo_id=repo_id, n_results=3)

    # Run worker inspections for each chunk
    async def _inspect_chunk(chunk_files: List[str], chunk_diff: str) -> str:
        prompt = (
            f"Target Repo: '{repo_id}' (branch: '{branch}')\n"
            f"Target Files in this patch: {chunk_files}\n"
            f"Modified Symbols: {changed_symbols}\n"
            f"Systematically inspect EVERY file listed in Target Files ({chunk_files}) for runtime bugs, unhandled promise rejections, missing try-catch error handling around dynamic imports or API calls, and logic flaws:\n\n{chunk_diff}"
        )
        return await llm_client.run_worker(prompt, worker_system)

    worker_tasks = [_inspect_chunk(c_files, c_diff) for c_files, c_diff in diff_chunks]

    all_coros = [blast_task, vector_task, cpg_task] + worker_tasks
    results = await asyncio.gather(*all_coros, return_exceptions=True)

    blast_json = results[0] if isinstance(results[0], str) else json.dumps({"risk_score": 0.0, "total_affected": 0})
    semantic_json = results[1] if isinstance(results[1], str) else "[]"
    cpg_context = results[2] if isinstance(results[2], str) else "CPG analysis unavailable."
    worker_raw_list = results[3:]

    try:
        blast_data = json.loads(blast_json)
    except Exception:
        blast_data = {"risk_score": 0.0, "total_affected": 0}

    # 5. Parse candidate issues from all worker node chunks
    candidate_issues: List[Dict[str, Any]] = []
    for idx, w_raw in enumerate(worker_raw_list):
        if isinstance(w_raw, str):
            c_files = diff_chunks[idx][0] if idx < len(diff_chunks) else changed_files
            parsed = _parse_worker_issues(w_raw, c_files)
            candidate_issues.extend(parsed)

    # 5b. Fallback: If candidate_issues is empty and Gemini is available, run direct inspection on first chunk
    if not candidate_issues and llm_client.has_gemini:
        try:
            fallback_prompt = (
                f"Target Repo: '{repo_id}' (branch: '{branch}')\n"
                f"Changed Files: {changed_files}\n"
                f"Modified Symbols: {changed_symbols}\n"
                f"Systematically inspect EVERY file listed in Changed Files ({changed_files}) for runtime bugs, unhandled promise rejections, missing try-catch error handling around dynamic imports or API calls, and logic flaws:\n\n{raw_diff_text[:25000]}"
            )
            gem_raw = await llm_client._call_gemini(
                fallback_prompt, worker_system, temperature=0.2, json_mode=True
            )
            if gem_raw:
                candidate_issues.extend(_parse_worker_issues(gem_raw, changed_files))
        except Exception as ge:
            logger.warning(f"Fallback Gemini worker inspection notice: {ge}")

    # 6. Invoke Primary Orchestrator (Qwen / Gemini) for RAG synthesis & 5-Step Falsification
    diff_limit = 35000 if getattr(llm_client, "orchestrator_provider", "") == "ollama" else 60000
    orch_prompt = build_orchestrator_prompt(
        repo_id=repo_id,
        branch=branch,
        changed_files=changed_files,
        changed_symbols=changed_symbols,
        blast_radius_json=blast_json,
        diff_text=raw_diff_text[:diff_limit],
        convention_violations=violations_dicts,
        semantic_context=semantic_json,
        cpg_context=cpg_context,
        candidate_issues=candidate_issues,
    )
    orchestrator_response = await llm_client.run_orchestrator(orch_prompt, get_prompt("pr_orchestrator"))

    # 7. Extract confirmed issues surviving falsification & merge candidate issues
    structured_issues: List[Dict[str, Any]] = []
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

    raw_issues: List[Dict[str, Any]] = []
    suggestions: List[Suggestion] = []
    generic_titles = {
        "code issue detected",
        "issue detected",
        "bug detected",
        "code issue",
        "potential flaw found",
        "potential flaw found during deep diff analysis.",
        "issue verified by orchestrator.",
    }

    # Priority 1: Add orchestrator confirmed issues
    if orchestrator_confirmed and len(orchestrator_confirmed) > 0:
        for item in orchestrator_confirmed:
            f = item.get("file_path", changed_files[0] if changed_files else "codebase")
            l = item.get("line", 1)
            t = (item.get("title") or "").strip()
            desc = (item.get("description") or "").strip()
            if not t or t.lower() in generic_titles:
                t = desc[:60] if desc else "Code Issue Detected"

            raw_issues.append({
                "id": str(uuid.uuid4()),
                "title": t,
                "description": desc or "Issue verified by orchestrator.",
                "category": item.get("category", "bug"),
                "severity": item.get("severity", "warning"),
                "file_path": f,
                "line": l,
                "suggested_fix": item.get("suggested_fix", ""),
            })

    # Priority 2: Hierarchical Vetting Gate for worker candidate issues
    # Combines orchestrator precision with worker hunk coverage
    for cand in candidate_issues:
        title = (cand.get("title") or "").strip()
        desc = (cand.get("description") or "").strip()
        sev = (cand.get("severity") or "warning").lower()
        cat = (cand.get("category") or "bug").lower()

        # Gate 1: Discard generic placeholder issues that lack actionable substance
        if not title or title.lower() in generic_titles:
            if not desc or desc.lower() in generic_titles:
                continue
            title = desc[:60]

        # Gate 2: Route low-severity/info nits to non-blocking suggestions (avoids FP inflation)
        if sev in ("low", "info") or cat in ("style", "formatting", "convention"):
            try:
                cline = int(cand.get("line", 1))
            except (ValueError, TypeError):
                cline = 1
            suggestions.append(
                Suggestion(
                    file_path=cand.get("file_path", "codebase"),
                    line=cline,
                    description=f"{title}: {desc}",
                    category=cat,
                    severity=sev,
                )
            )
            continue

        # Gate 3: Deduplicate candidate against already admitted orchestrator issues
        covered_by_orch = False
        for orch_item in raw_issues:
            if _issue_concept_sim(cand, orch_item) >= 0.45:
                covered_by_orch = True
                if sev in ("critical", "error") and orch_item.get("severity") not in ("critical", "error"):
                    orch_item["severity"] = sev
                break

        if covered_by_orch:
            continue

        # Gate 4: Admit verified high-confidence worker candidate
        raw_issues.append(cand)

    # Deduplicate issues to eliminate overlapping line reports & cross-file siblings
    structured_issues = deduplicate_issues(raw_issues, line_window=15, cross_file_threshold=0.48)

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
        else:
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

