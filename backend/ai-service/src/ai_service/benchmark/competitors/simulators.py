"""Competitor & ablation review pipeline simulators.

Each simulator strictly implements the designated strategy without borrowing GitAmi's
full ReAct autonomous agent loop or unauthorized cross-subsystems:
- B1: Pure Zero-Shot LLM (Gemini 2.0 Flash) on Raw Diff only (No KB, No Conv Gate)
- B2: Chroma Vector RAG Only + Conv Gate + Dual-LLM (Groq Worker + Gemini Orchestrator)
- A1: Neo4j Graph Only (No Vector) + Conv Gate + Dual-LLM (Groq Worker + Gemini Orchestrator)
- A2: Dual KB (Neo4j + Chroma) + Conv Gate + Worker Only (Groq Llama-3.3-70B)
- A3: Dual KB (Neo4j + Chroma) + Conv Gate + Orchestrator Only (Gemini 2.0 Flash)
"""

import asyncio
import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ai_service.agent.diff_parser import parse_git_diff, extract_changed_symbols
from ai_service.agent.llm_client import is_rate_limit_error
from ai_service.analysis.blast_radius import compute_blast_radius
from ai_service.analysis.conventions import check_conventions, check_diff_conventions
from ai_service.benchmark.competitors.config import CompetitorConfig
from ai_service.benchmark.competitors.key_rotator import APIKeyRotator
from ai_service.benchmark.datasets.base import BenchmarkTestCase
from ai_service.graph.client import Neo4jClient
from ai_service.vector.client import VectorKBClient

logger = logging.getLogger(__name__)

GEMINI_BENCHMARK_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

GROQ_BENCHMARK_MODELS = [
    "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
]


def extract_json_from_text(text: str) -> Dict[str, Any]:
    """Robustly extract and parse a JSON dictionary from an LLM response string."""
    if not text:
        return {"verdict": "ACCEPT", "issues": [], "summary": "Empty response"}

    clean = text.strip()
    if "```json" in clean:
        clean = clean.split("```json")[1].split("```")[0]
    elif "```" in clean:
        clean = clean.split("```")[1].split("```")[0]

    first_brace = clean.find("{")
    last_brace = clean.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        clean = clean[first_brace : last_brace + 1]

    try:
        return json.loads(clean.strip())
    except Exception as e:
        logger.warning(f"Failed to parse LLM JSON output ({e}). Falling back to regex extraction.")

    # Fallback: extract list of issues if enclosed in "issues": [...]
    try:
        match = re.search(r'"issues"\s*:\s*(\[[^\]]*\])', text, re.DOTALL)
        if match:
            issues = json.loads(match.group(1))
            return {"verdict": "SUGGEST" if issues else "ACCEPT", "issues": issues}
    except Exception:
        pass

    return {"verdict": "ACCEPT", "issues": [], "summary": "Failed JSON parse"}


def normalize_issues(
    raw_issues: List[Any], changed_files: List[str], default_category: str = "bug"
) -> List[Dict[str, Any]]:
    """Normalize extracted issues into BenchmarkScorer format."""
    normalized: List[Dict[str, Any]] = []
    primary_file = changed_files[0] if changed_files else "codebase"

    for item in raw_issues:
        if not isinstance(item, dict):
            continue

        raw_sev = str(item.get("severity", "warning")).lower()
        if raw_sev in ("error", "critical"):
            sev = "error"
        elif raw_sev in ("info", "low"):
            sev = "info"
        else:
            sev = "warning"

        raw_cat = str(item.get("category", default_category)).lower()
        if "sec" in raw_cat or "vuln" in raw_cat:
            cat = "security"
        elif "perf" in raw_cat:
            cat = "performance"
        elif "style" in raw_cat or "conv" in raw_cat or "doc" in raw_cat:
            cat = "convention"
        else:
            cat = "bug"

        line_val = item.get("line") or item.get("line_start") or 1
        try:
            line_int = int(line_val)
        except (ValueError, TypeError):
            line_int = 1

        file_path = item.get("file_path") or item.get("file") or primary_file

        normalized.append({
            "id": str(uuid.uuid4()),
            "title": str(item.get("title", "Identified Code Defect"))[:100],
            "description": str(item.get("description", "Potential defect identified during review.")),
            "category": cat,
            "severity": sev,
            "file_path": file_path,
            "line": line_int,
            "suggested_fix": str(item.get("suggested_fix", "")),
        })

    return normalized


# ─── Free-Tier LLM Dispatchers with Key Rotation ──────────────────────────────

async def call_gemini_with_rotation(
    prompt: str,
    system_prompt: str,
    rotator: APIKeyRotator,
    max_retries: int = 3,
) -> str:
    """Call Google Gemini with automatic API key rotation on 429 quota exhaustion."""
    if not rotator.has_keys:
        logger.warning("[Gemini] No Gemini API keys configured. Running in offline fallback mode.")
        return ""

    for attempt in range(1, max_retries + 1):
        key = rotator.get_current_key()
        try:
            from google import genai
            client = genai.Client(api_key=key)

            for model_name in GEMINI_BENCHMARK_MODELS:
                try:
                    res = client.models.generate_content(
                        model=model_name,
                        contents=f"{system_prompt}\n\n{prompt}",
                    )
                    if res and res.text:
                        return res.text
                except Exception as me:
                    if is_rate_limit_error(me):
                        raise me
                    logger.debug(f"[Gemini] Model '{model_name}' try failed: {me}")
            return ""

        except Exception as e:
            if is_rate_limit_error(e):
                logger.warning(f"[Gemini 429] Rate limit / quota hit on key (attempt {attempt}/{max_retries}): {e}")
                if rotator.key_count > 1:
                    await rotator.rotate(reason=f"HTTP 429 on attempt {attempt}")
                else:
                    backoff = 15 * attempt
                    logger.info(f"[Gemini] Single key configured; sleeping {backoff}s before retrying...")
                    await asyncio.sleep(backoff)
            else:
                logger.error(f"[Gemini] Execution error: {e}")
                break

    return ""


async def call_groq_with_rotation(
    prompt: str,
    system_prompt: str,
    rotator: APIKeyRotator,
    json_mode: bool = True,
    max_retries: int = 3,
) -> str:
    """Call Groq Llama with automatic API key rotation on 429 rate limit."""
    if not rotator.has_keys:
        logger.warning("[Groq] No Groq API keys configured. Running in offline fallback mode.")
        return ""

    for attempt in range(1, max_retries + 1):
        key = rotator.get_current_key()
        try:
            from groq import Groq
            client = Groq(api_key=key)

            for model_name in GROQ_BENCHMARK_MODELS:
                try:
                    kwargs: Dict[str, Any] = {
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.1,
                    }
                    if json_mode:
                        kwargs["response_format"] = {"type": "json_object"}

                    completion = client.chat.completions.create(**kwargs)
                    if completion.choices and completion.choices[0].message.content:
                        return completion.choices[0].message.content
                except Exception as me:
                    if is_rate_limit_error(me):
                        raise me
                    logger.debug(f"[Groq] Model '{model_name}' try failed: {me}")
            return ""

        except Exception as e:
            if is_rate_limit_error(e):
                logger.warning(f"[Groq 429] Rate limit hit on key (attempt {attempt}/{max_retries}): {e}")
                if rotator.key_count > 1:
                    await rotator.rotate(reason=f"HTTP 429 on attempt {attempt}")
                else:
                    backoff = 10 * attempt
                    logger.info(f"[Groq] Single key configured; sleeping {backoff}s before retrying...")
                    await asyncio.sleep(backoff)
            else:
                logger.error(f"[Groq] Execution error: {e}")
                break

    return ""


# ─── Competitor Simulator Implementations ────────────────────────────────────

async def run_simulator_B1(
    case: BenchmarkTestCase,
    config: CompetitorConfig,
    gemini_rotator: APIKeyRotator,
    groq_rotator: APIKeyRotator,
    graph_client: Optional[Neo4jClient] = None,
    vector_client: Optional[VectorKBClient] = None,
) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
    """
    Configuration B1: Standard LLM (Gemini 2.0 Flash) on Raw Diff Only.
    - Knowledge Base: None (Raw Diff Only)
    - LLM Architecture: Single (Gemini 2.0 Flash)
    - Conv. Gate: Disabled
    """
    diff_text = case.diff_text or "# Empty Diff"
    diff_snippet = diff_text[:6000]

    hunks = parse_git_diff(diff_text)
    changed_files = list({h.file_path for h in hunks if h.file_path}) or ["codebase"]

    system_prompt = (
        "You are an expert automated code review assistant. "
        "Analyze the provided git diff for software bugs, security vulnerabilities, and logic flaws. "
        "Output ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "verdict": "ACCEPT" | "SUGGEST",\n'
        '  "summary": "Brief analysis summary",\n'
        '  "issues": [\n'
        '    {\n'
        '      "title": "Concise defect title",\n'
        '      "description": "Explanation of the defect",\n'
        '      "category": "bug" | "security" | "performance" | "convention",\n'
        '      "severity": "error" | "warning" | "info",\n'
        '      "file_path": "path/to/file",\n'
        '      "line": 123,\n'
        '      "suggested_fix": "Remediation recommendation"\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    user_prompt = (
        f"Target Repository: '{case.repo_name}' (Language: {case.language})\n"
        f"Changed Files: {changed_files}\n\n"
        f"Git Diff:\n{diff_snippet}\n\n"
        "Perform a thorough review and return the JSON findings."
    )

    resp_text = await call_gemini_with_rotation(user_prompt, system_prompt, gemini_rotator)
    parsed = extract_json_from_text(resp_text)

    raw_issues = parsed.get("issues", [])
    issues = normalize_issues(raw_issues, changed_files)
    verdict = parsed.get("verdict", "SUGGEST" if issues else "ACCEPT").upper()

    meta = {"llm_calls_gemini": 1, "llm_calls_groq": 0, "kb_hits": 0, "conv_violations": 0}
    return issues, verdict, meta


async def run_simulator_B2(
    case: BenchmarkTestCase,
    config: CompetitorConfig,
    gemini_rotator: APIKeyRotator,
    groq_rotator: APIKeyRotator,
    graph_client: Optional[Neo4jClient] = None,
    vector_client: Optional[VectorKBClient] = None,
) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
    """
    Configuration B2: Vector RAG Only (Chroma) + Dual-LLM + Conv. Gate Enabled.
    - Knowledge Base: Chroma (Only)
    - LLM Architecture: Dual-LLM (Groq Worker + Gemini Orchestrator)
    - Conv. Gate: Enabled
    """
    diff_text = case.diff_text or "# Empty Diff"
    diff_snippet = diff_text[:5000]

    hunks = parse_git_diff(diff_text)
    changed_files = list({h.file_path for h in hunks if h.file_path}) or ["codebase"]

    # 1. Retrieve Chroma Vector context (No Neo4j)
    vector_context = ""
    kb_hits = 0
    if vector_client:
        try:
            query = diff_text[:300] if diff_text else case.repo_name
            results = vector_client.search(
                query_text=query,
                repo_id=f"{config.repo_id_prefix}{case.case_id}",
                n_results=3,
            )
            chunks = results.get("documents", [[]])[0]
            if chunks:
                vector_context = "\n---\n".join(chunks[:3])
                kb_hits = len(chunks)
        except Exception as e:
            logger.debug(f"[B2] Chroma vector search error: {e}")

    # 2. Convention Gate
    ast_violations = check_conventions([])
    diff_violations = check_diff_conventions(diff_text)
    all_violations = ast_violations + diff_violations

    conv_issues: List[Dict[str, Any]] = []
    for v in all_violations:
        conv_issues.append({
            "id": str(uuid.uuid4()),
            "title": f"[{v.rule_id}] Convention Violation",
            "description": v.message,
            "category": "convention",
            "severity": v.severity,
            "file_path": v.file_path,
            "line": v.line,
            "suggested_fix": f"Adhere to convention rule {v.rule_id}",
        })

    # 3. Dual-LLM: Step 1 - Groq Worker Node diff inspection
    worker_system = (
        "You are a code inspection worker. Analyze this pull request diff along with "
        "semantic vector context to detect bugs, security flaws, and defects. "
        "Output ONLY valid JSON with format: {'issues': [{'title': '...', 'description': '...', 'category': '...', 'severity': '...', 'file_path': '...', 'line': 123}]}"
    )
    worker_prompt = (
        f"Repository: '{case.repo_name}'\n"
        f"Semantic Vector Context:\n{vector_context[:1500] if vector_context else 'None'}\n\n"
        f"Diff:\n{diff_snippet}"
    )
    worker_raw = await call_groq_with_rotation(worker_prompt, worker_system, groq_rotator)
    worker_parsed = extract_json_from_text(worker_raw)
    worker_issues = worker_parsed.get("issues", [])

    # 4. Dual-LLM: Step 2 - Gemini Orchestrator review synthesis
    orch_system = (
        "You are an architectural code review orchestrator. Synthesize worker findings, "
        "semantic vector context, and convention violations into a final review JSON matching:\n"
        "{\n"
        '  "verdict": "ACCEPT" | "SUGGEST",\n'
        '  "summary": "...",\n'
        '  "issues": [{"title": "...", "description": "...", "category": "...", "severity": "...", "file_path": "...", "line": 123}]\n'
        "}"
    )
    orch_prompt = (
        f"Target Repo: '{case.repo_name}'\n"
        f"Changed Files: {changed_files}\n"
        f"Convention Violations: {len(conv_issues)}\n"
        f"Worker Preliminary Issues: {json.dumps(worker_issues[:5])}\n"
        f"Semantic Context:\n{vector_context[:1200] if vector_context else 'None'}\n\n"
        f"Diff:\n{diff_snippet[:3500]}"
    )
    orch_raw = await call_gemini_with_rotation(orch_prompt, orch_system, gemini_rotator)
    orch_parsed = extract_json_from_text(orch_raw)

    final_issues = normalize_issues(orch_parsed.get("issues", []) or worker_issues, changed_files)
    final_issues.extend(conv_issues)

    verdict = orch_parsed.get("verdict", "SUGGEST" if final_issues else "ACCEPT").upper()
    meta = {
        "llm_calls_gemini": 1,
        "llm_calls_groq": 1,
        "kb_hits": kb_hits,
        "conv_violations": len(all_violations),
    }
    return final_issues, verdict, meta


async def run_simulator_A1(
    case: BenchmarkTestCase,
    config: CompetitorConfig,
    gemini_rotator: APIKeyRotator,
    groq_rotator: APIKeyRotator,
    graph_client: Optional[Neo4jClient] = None,
    vector_client: Optional[VectorKBClient] = None,
) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
    """
    Configuration A1: Neo4j Graph Only (No Vector) + Dual-LLM + Conv. Gate Enabled.
    - Knowledge Base: Neo4j Only (No Vector)
    - LLM Architecture: Dual-LLM (Groq Worker + Gemini Orchestrator)
    - Conv. Gate: Enabled
    """
    diff_text = case.diff_text or "# Empty Diff"
    diff_snippet = diff_text[:5000]

    hunks = parse_git_diff(diff_text)
    changed_files = list({h.file_path for h in hunks if h.file_path}) or ["codebase"]
    changed_symbols = extract_changed_symbols(hunks, diff_text)

    # 1. Retrieve Graph Blast Radius from Neo4j (No Vector DB)
    blast_info = ""
    risk_score = 0.0
    if graph_client and graph_client._driver:
        try:
            repo_id = f"{config.repo_id_prefix}{case.case_id}"
            blast_res = await compute_blast_radius(
                client=graph_client,
                repo_id=repo_id,
                changed_symbols=changed_symbols,
                branch=config.branch,
            )
            risk_score = blast_res.risk_score
            affected_names = [a.qualified_name for a in blast_res.affected_symbols[:5]]
            blast_info = (
                f"Blast Radius Risk Score: {blast_res.risk_score:.2f}, "
                f"Total Affected Downstream: {blast_res.total_affected}, "
                f"Key Affected: {', '.join(affected_names)}"
            )
        except Exception as e:
            logger.debug(f"[A1] Neo4j blast radius query error: {e}")

    # 2. Convention Gate
    ast_violations = check_conventions([])
    diff_violations = check_diff_conventions(diff_text)
    all_violations = ast_violations + diff_violations

    conv_issues: List[Dict[str, Any]] = []
    for v in all_violations:
        conv_issues.append({
            "id": str(uuid.uuid4()),
            "title": f"[{v.rule_id}] Convention Violation",
            "description": v.message,
            "category": "convention",
            "severity": v.severity,
            "file_path": v.file_path,
            "line": v.line,
            "suggested_fix": f"Adhere to convention rule {v.rule_id}",
        })

    # 3. Dual-LLM: Step 1 - Groq Worker Node
    worker_system = (
        "You are a code inspection worker. Analyze this pull request diff along with "
        "structural call-graph blast radius information to detect bugs and vulnerabilities. "
        "Output ONLY valid JSON with format: {'issues': [{'title': '...', 'description': '...', 'category': '...', 'severity': '...', 'file_path': '...', 'line': 123}]}"
    )
    worker_prompt = (
        f"Repository: '{case.repo_name}'\n"
        f"Call-Graph Blast Radius:\n{blast_info or 'No ripple callers detected'}\n\n"
        f"Diff:\n{diff_snippet}"
    )
    worker_raw = await call_groq_with_rotation(worker_prompt, worker_system, groq_rotator)
    worker_parsed = extract_json_from_text(worker_raw)
    worker_issues = worker_parsed.get("issues", [])

    # 4. Dual-LLM: Step 2 - Gemini Orchestrator
    orch_system = (
        "You are an architectural code review orchestrator. Synthesize worker findings, "
        "graph dependency blast radius, and convention violations into a final review JSON matching:\n"
        "{\n"
        '  "verdict": "ACCEPT" | "SUGGEST",\n'
        '  "summary": "...",\n'
        '  "issues": [{"title": "...", "description": "...", "category": "...", "severity": "...", "file_path": "...", "line": 123}]\n'
        "}"
    )
    orch_prompt = (
        f"Target Repo: '{case.repo_name}'\n"
        f"Changed Files: {changed_files}\n"
        f"Graph Blast Radius: {blast_info or 'None'}\n"
        f"Worker Preliminary Issues: {json.dumps(worker_issues[:5])}\n"
        f"Convention Violations: {len(conv_issues)}\n\n"
        f"Diff:\n{diff_snippet[:3500]}"
    )
    orch_raw = await call_gemini_with_rotation(orch_prompt, orch_system, gemini_rotator)
    orch_parsed = extract_json_from_text(orch_raw)

    final_issues = normalize_issues(orch_parsed.get("issues", []) or worker_issues, changed_files)
    final_issues.extend(conv_issues)

    verdict = orch_parsed.get("verdict", "SUGGEST" if (final_issues or risk_score > 5.0) else "ACCEPT").upper()
    meta = {
        "llm_calls_gemini": 1,
        "llm_calls_groq": 1,
        "blast_risk": risk_score,
        "conv_violations": len(all_violations),
    }
    return final_issues, verdict, meta


async def run_simulator_A2(
    case: BenchmarkTestCase,
    config: CompetitorConfig,
    gemini_rotator: APIKeyRotator,
    groq_rotator: APIKeyRotator,
    graph_client: Optional[Neo4jClient] = None,
    vector_client: Optional[VectorKBClient] = None,
) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
    """
    Configuration A2: Dual KB (Neo4j + Chroma) + Worker Only (Llama-3.3-70B) + Conv. Gate Enabled.
    - Knowledge Base: Dual KB (Neo4j + Chroma)
    - LLM Architecture: Worker Only (Llama-70B via Groq) - ZERO Gemini calls!
    - Conv. Gate: Enabled
    """
    diff_text = case.diff_text or "# Empty Diff"
    diff_snippet = diff_text[:5000]

    hunks = parse_git_diff(diff_text)
    changed_files = list({h.file_path for h in hunks if h.file_path}) or ["codebase"]
    changed_symbols = extract_changed_symbols(hunks, diff_text)

    # 1. Graph Blast Radius
    blast_info = ""
    risk_score = 0.0
    if graph_client and graph_client._driver:
        try:
            repo_id = f"{config.repo_id_prefix}{case.case_id}"
            blast_res = await compute_blast_radius(
                client=graph_client,
                repo_id=repo_id,
                changed_symbols=changed_symbols,
                branch=config.branch,
            )
            risk_score = blast_res.risk_score
            affected_names = [a.qualified_name for a in blast_res.affected_symbols[:4]]
            blast_info = f"Blast Risk: {blast_res.risk_score:.2f}, Downstream: {', '.join(affected_names)}"
        except Exception as e:
            logger.debug(f"[A2] Blast radius query error: {e}")

    # 2. Vector Semantic Context
    vector_context = ""
    if vector_client:
        try:
            query = diff_text[:300] if diff_text else case.repo_name
            results = vector_client.search(
                query_text=query,
                repo_id=f"{config.repo_id_prefix}{case.case_id}",
                n_results=2,
            )
            chunks = results.get("documents", [[]])[0]
            if chunks:
                vector_context = "\n".join(chunks[:2])
        except Exception as e:
            logger.debug(f"[A2] Vector search error: {e}")

    # 3. Convention Gate
    ast_violations = check_conventions([])
    diff_violations = check_diff_conventions(diff_text)
    all_violations = ast_violations + diff_violations

    conv_issues: List[Dict[str, Any]] = []
    for v in all_violations:
        conv_issues.append({
            "id": str(uuid.uuid4()),
            "title": f"[{v.rule_id}] Convention Violation",
            "description": v.message,
            "category": "convention",
            "severity": v.severity,
            "file_path": v.file_path,
            "line": v.line,
            "suggested_fix": f"Adhere to convention rule {v.rule_id}",
        })

    # 4. Sole LLM: Groq Llama-3.3-70B Worker (No Gemini!)
    worker_system = (
        "You are an autonomous code auditing worker (Llama-3.3-70B). "
        "Review the pull request diff with both structural graph blast radius and semantic vector context. "
        "Identify bugs, vulnerabilities, logic errors, and security defects. "
        "Output ONLY valid JSON matching:\n"
        "{\n"
        '  "verdict": "ACCEPT" | "SUGGEST",\n'
        '  "summary": "...",\n'
        '  "issues": [{"title": "...", "description": "...", "category": "...", "severity": "...", "file_path": "...", "line": 123}]\n'
        "}"
    )
    worker_prompt = (
        f"Target Repo: '{case.repo_name}' (Language: {case.language})\n"
        f"Changed Files: {changed_files}\n"
        f"Graph Context: {blast_info or 'None'}\n"
        f"Vector Context:\n{vector_context[:1000] if vector_context else 'None'}\n\n"
        f"Diff:\n{diff_snippet}"
    )

    resp_text = await call_groq_with_rotation(worker_prompt, worker_system, groq_rotator)
    parsed = extract_json_from_text(resp_text)

    final_issues = normalize_issues(parsed.get("issues", []), changed_files)
    final_issues.extend(conv_issues)

    verdict = parsed.get("verdict", "SUGGEST" if (final_issues or risk_score > 5.0) else "ACCEPT").upper()
    meta = {
        "llm_calls_gemini": 0,
        "llm_calls_groq": 1,
        "blast_risk": risk_score,
        "conv_violations": len(all_violations),
    }
    return final_issues, verdict, meta


async def run_simulator_A3(
    case: BenchmarkTestCase,
    config: CompetitorConfig,
    gemini_rotator: APIKeyRotator,
    groq_rotator: APIKeyRotator,
    graph_client: Optional[Neo4jClient] = None,
    vector_client: Optional[VectorKBClient] = None,
) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
    """
    Configuration A3: Dual KB (Neo4j + Chroma) + Orchestrator Only (Gemini 2.0 Flash) + Conv. Gate Enabled.
    - Knowledge Base: Dual KB (Neo4j + Chroma)
    - LLM Architecture: Orch. Only (Gemini 2.0 Flash) - ZERO Groq calls!
    - Conv. Gate: Enabled
    """
    diff_text = case.diff_text or "# Empty Diff"
    diff_snippet = diff_text[:5500]

    hunks = parse_git_diff(diff_text)
    changed_files = list({h.file_path for h in hunks if h.file_path}) or ["codebase"]
    changed_symbols = extract_changed_symbols(hunks, diff_text)

    # 1. Graph Blast Radius
    blast_info = ""
    risk_score = 0.0
    if graph_client and graph_client._driver:
        try:
            repo_id = f"{config.repo_id_prefix}{case.case_id}"
            blast_res = await compute_blast_radius(
                client=graph_client,
                repo_id=repo_id,
                changed_symbols=changed_symbols,
                branch=config.branch,
            )
            risk_score = blast_res.risk_score
            affected_names = [a.qualified_name for a in blast_res.affected_symbols[:4]]
            blast_info = f"Blast Risk: {blast_res.risk_score:.2f}, Downstream: {', '.join(affected_names)}"
        except Exception as e:
            logger.debug(f"[A3] Blast radius query error: {e}")

    # 2. Vector Semantic Context
    vector_context = ""
    if vector_client:
        try:
            query = diff_text[:300] if diff_text else case.repo_name
            results = vector_client.search(
                query_text=query,
                repo_id=f"{config.repo_id_prefix}{case.case_id}",
                n_results=2,
            )
            chunks = results.get("documents", [[]])[0]
            if chunks:
                vector_context = "\n".join(chunks[:2])
        except Exception as e:
            logger.debug(f"[A3] Vector search error: {e}")

    # 3. Convention Gate
    ast_violations = check_conventions([])
    diff_violations = check_diff_conventions(diff_text)
    all_violations = ast_violations + diff_violations

    conv_issues: List[Dict[str, Any]] = []
    for v in all_violations:
        conv_issues.append({
            "id": str(uuid.uuid4()),
            "title": f"[{v.rule_id}] Convention Violation",
            "description": v.message,
            "category": "convention",
            "severity": v.severity,
            "file_path": v.file_path,
            "line": v.line,
            "suggested_fix": f"Adhere to convention rule {v.rule_id}",
        })

    # 4. Sole LLM: Gemini 2.0 Flash Orchestrator (No Groq!)
    orch_system = (
        "You are an architectural code review orchestrator (Gemini 2.0 Flash). "
        "Review the pull request diff with both structural graph blast radius and semantic vector context. "
        "Identify bugs, vulnerabilities, logic errors, and security defects. "
        "Output ONLY valid JSON matching:\n"
        "{\n"
        '  "verdict": "ACCEPT" | "SUGGEST",\n'
        '  "summary": "...",\n'
        '  "issues": [{"title": "...", "description": "...", "category": "...", "severity": "...", "file_path": "...", "line": 123}]\n'
        "}"
    )
    orch_prompt = (
        f"Target Repo: '{case.repo_name}' (Language: {case.language})\n"
        f"Changed Files: {changed_files}\n"
        f"Graph Context: {blast_info or 'None'}\n"
        f"Vector Context:\n{vector_context[:1000] if vector_context else 'None'}\n\n"
        f"Diff:\n{diff_snippet}"
    )

    resp_text = await call_gemini_with_rotation(orch_prompt, orch_system, gemini_rotator)
    parsed = extract_json_from_text(resp_text)

    final_issues = normalize_issues(parsed.get("issues", []), changed_files)
    final_issues.extend(conv_issues)

    verdict = parsed.get("verdict", "SUGGEST" if (final_issues or risk_score > 5.0) else "ACCEPT").upper()
    meta = {
        "llm_calls_gemini": 1,
        "llm_calls_groq": 0,
        "blast_risk": risk_score,
        "conv_violations": len(all_violations),
    }
    return final_issues, verdict, meta


SIMULATOR_DISPATCHER = {
    "B1": run_simulator_B1,
    "B2": run_simulator_B2,
    "A1": run_simulator_A1,
    "A2": run_simulator_A2,
    "A3": run_simulator_A3,
}
