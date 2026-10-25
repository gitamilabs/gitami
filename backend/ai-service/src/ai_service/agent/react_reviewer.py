"""Autonomous ReAct Agent for Pull Request Review and Vulnerability Detection."""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ai_service.graph.client import Neo4jClient
from ai_service.vector.client import VectorKBClient
from ai_service.mcp.tools import execute_tool_by_name
from ai_service.analysis.conventions import check_conventions, check_diff_conventions
from ai_service.analysis.decision import DecisionResult, Verdict, Suggestion
from ai_service.agent.diff_parser import parse_git_diff, extract_changed_symbols, chunk_diff_by_files, format_annotated_diff
from ai_service.agent.llm_client import DualLLMClient
from ai_service.prompts import get_prompt
from ai_service.agent.prompts import get_react_pr_reviewer_prompt

logger = logging.getLogger(__name__)


def normalize_issues(
    raw_issues: List[Any],
    changed_files: List[str],
    default_category: str = "bug",
) -> List[Dict[str, Any]]:
    """Normalize extracted issues into standard BenchmarkScorer format."""
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
        if "sec" in raw_cat or "vuln" in raw_cat or "auth" in raw_cat:
            cat = "security"
        elif "perf" in raw_cat or "leak" in raw_cat:
            cat = "performance"
        elif "style" in raw_cat or "conv" in raw_cat or "doc" in raw_cat or "nam" in raw_cat:
            cat = "convention"
        else:
            cat = "bug"

        line_val = item.get("line") or item.get("line_start") or 1
        try:
            line_int = int(line_val)
        except (ValueError, TypeError):
            line_int = 1

        file_path = str(item.get("file_path") or item.get("file") or primary_file).strip()
        if file_path.startswith("a/") or file_path.startswith("b/"):
            file_path = file_path[2:]

        # Map file_path accurately against changed_files list
        if changed_files and file_path not in changed_files:
            matched_cf = None
            for cf in changed_files:
                if file_path.endswith(cf) or cf.endswith(file_path):
                    matched_cf = cf
                    break
                if os.path.basename(file_path) == os.path.basename(cf):
                    matched_cf = cf
                    break
            if matched_cf:
                file_path = matched_cf

        normalized.append({
            "id": str(uuid.uuid4()),
            "title": str(item.get("title", "Identified Code Defect"))[:120],
            "description": str(item.get("description", "Potential defect identified during review.")),
            "category": cat,
            "severity": sev,
            "file_path": file_path,
            "line": line_int,
            "suggested_fix": str(item.get("suggested_fix", "")),
        })

    return normalized


def _text_overlap(t1: str, t2: str) -> float:
    w1 = set(re.findall(r"[a-zA-Z0-9_]{3,}", t1.lower()))
    w2 = set(re.findall(r"[a-zA-Z0-9_]{3,}", t2.lower()))
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / len(w1 | w2)


def deduplicate_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate overlapping issues while preserving distinct defects in the same file."""
    unique: List[Dict[str, Any]] = []

    for issue in issues:
        f = str(issue.get("file_path", "")).strip()
        l = int(issue.get("line", 1) or 1)
        cat = str(issue.get("category", "")).strip().lower()
        title = str(issue.get("title", "")).strip().lower()
        desc = str(issue.get("description", "")).strip().lower()
        full_text = f"{title} {desc}"

        is_dup = False
        dup_idx = -1
        for idx, existing in enumerate(unique):
            ef = str(existing.get("file_path", "")).strip()
            el = int(existing.get("line", 1) or 1)
            ecat = str(existing.get("category", "")).strip().lower()
            etitle = str(existing.get("title", "")).strip().lower()
            edesc = str(existing.get("description", "")).strip().lower()
            efull_text = f"{etitle} {edesc}"

            # If not the same file, not a duplicate
            if f != ef and not (f.endswith(ef) or ef.endswith(f)):
                continue

            line_diff = abs(l - el)
            sim = _text_overlap(full_text, efull_text)

            # Duplicate only if referring to the exact same defect:
            # 1. Extremely close lines (<= 5) in same category with semantic overlap (sim >= 0.15)
            # 2. Within line tolerance (<= 15) with substantial text similarity (sim >= 0.30)
            # 3. Identical wording / highly similar text (sim >= 0.50) anywhere in the file
            if (line_diff <= 5 and cat == ecat and sim >= 0.15) or (line_diff <= 15 and sim >= 0.30) or sim >= 0.50:
                is_dup = True
                dup_idx = idx
                break

        if not is_dup:
            unique.append(issue)
        else:
            # Upgrade existing issue if current one has higher severity (error > warning > info)
            sev_order = {"error": 3, "warning": 2, "info": 1}
            cur_sev = sev_order.get(str(issue.get("severity", "warning")).lower(), 2)
            ex_sev = sev_order.get(str(unique[dup_idx].get("severity", "warning")).lower(), 2)
            if cur_sev > ex_sev:
                unique[dup_idx] = issue

    return unique


class PrReviewReActAgent:
    """
    Autonomous ReAct (Reasoning + Action) agent for Pull Request reviews.
    Dynamically inspects blast radius, semantic context, and file contents
    through iterative tool invocations before rendering a final review verdict.
    """

    def __init__(self, llm_client: Optional[DualLLMClient] = None):
        self.llm_client = llm_client or DualLLMClient()

    async def review(
        self,
        repo_id: str,
        branch: str,
        raw_diff_text: str,
        changed_symbols: Optional[List[str]] = None,
        symbols: Optional[list] = None,
        graph_client: Optional[Neo4jClient] = None,
        vector_client: Optional[VectorKBClient] = None,
        max_steps: int = 2,
    ) -> Any:
        """
        Execute iterative ReAct PR review.
        Returns AgentReviewResult containing decision, rationale, and structured issues.
        """
        from ai_service.agent.reviewer import AgentReviewResult

        loop_start = time.perf_counter()

        # 1. Parse diff hunks & symbols
        hunks = parse_git_diff(raw_diff_text) if raw_diff_text else []
        changed_files = list({h.file_path for h in hunks if h.file_path})

        if not changed_symbols:
            changed_symbols = extract_changed_symbols(hunks, raw_diff_text or "")

        # 2. Check static AST and diff conventions
        ast_violations = check_conventions(symbols or [])
        diff_violations = check_diff_conventions(raw_diff_text or "")
        all_violations = ast_violations + diff_violations

        conv_issues: List[Dict[str, Any]] = []
        for v in all_violations:
            conv_issues.append({
                "id": str(uuid.uuid4()),
                "title": f"[{v.rule_id}] Style & Convention Violation",
                "description": v.message,
                "category": "convention",
                "severity": v.severity,
                "file_path": v.file_path,
                "line": v.line,
                "suggested_fix": f"Adhere to project convention {v.rule_id}",
            })

        # 3. High-Recall Focused Worker Diff Scanning Across All Files
        worker_issues: List[Dict[str, Any]] = []
        worker_system = get_prompt("pr_reviewer_worker")

        # Partition hunks into chunks so no file is dropped due to length
        file_chunks = chunk_diff_by_files(hunks, max_chars_per_chunk=35000) if hunks else [([], raw_diff_text or "# Empty diff")]
        # Scan up to 4 chunks covering up to 140,000 characters of diff
        for chunk_idx, (chunk_files, _) in enumerate(file_chunks[:4], start=1):
            chunk_hunks = [h for h in hunks if h.file_path in chunk_files] if chunk_files else hunks
            worker_diff = (
                format_annotated_diff(chunk_hunks, max_chars=40000)
                if chunk_hunks
                else (raw_diff_text[:40000] if raw_diff_text else "# Empty diff")
            )

            worker_prompt = (
                f"Target Repository: '{repo_id}' (branch: '{branch}')\n"
                f"Inspecting File Chunk {chunk_idx}/{min(len(file_chunks), 4)}: {chunk_files}\n"
                f"Changed Symbols: {changed_symbols}\n"
                f"Analyze the following pull request diff for bugs, concurrency flaws, logic errors, and security issues. "
                f"Always use the exact line numbers shown in the diff:\n\n"
                f"{worker_diff}"
            )
            try:
                worker_raw = await self.llm_client.run_worker(worker_prompt, worker_system)
                worker_parsed = self._parse_json(worker_raw)
                raw_w_issues = worker_parsed.get("issues", [])
                if isinstance(raw_w_issues, list):
                    worker_issues.extend(raw_w_issues)
            except Exception as we:
                logger.warning(f"Worker scan note on chunk {chunk_idx}: {we}")

        # 4. ReAct Reasoning Loop for Deep Multi-Modal Verification
        observations: List[Dict[str, Any]] = []
        final_decision_data: Optional[Dict[str, Any]] = None
        system_prompt = get_react_pr_reviewer_prompt()

        orchestrator_diff = (
            format_annotated_diff(hunks, max_chars=120000)
            if hunks
            else (raw_diff_text[:120000] if raw_diff_text else "# Empty diff")
        )

        for step_idx in range(1, max_steps + 1):
            history_str = ""
            if observations:
                history_str = "\n\n### PREVIOUS TOOL OBSERVATIONS IN THIS REVIEW LOOP:\n"
                for obs in observations:
                    history_str += (
                        f"Step {obs['step']}:\n"
                        f"- Thought: {obs['thought']}\n"
                        f"- Tool Called: {obs['tool_name']}({json.dumps(obs['args'])})\n"
                        f"- Output:\n{obs['raw'][:1500]}\n\n"
                    )

            if step_idx == max_steps:
                step_directive = (
                    f"Current Reasoning Step #{step_idx} of {max_steps} (FINAL STEP).\n"
                    f"You MUST conclude your review now: choose action: 'final_review', verify all findings, "
                    f"and output your complete list of verified defects in the 'issues' array."
                )
            else:
                step_directive = (
                    f"Current Reasoning Step #{step_idx} of {max_steps}.\n"
                    f"Decide your next action: choose 'call_tool' to inspect further, or 'final_review' to submit findings."
                )

            prompt = (
                f"Target Repository: '{repo_id}' (branch: '{branch}')\n"
                f"Changed Files: {changed_files}\n"
                f"Changed Symbols: {changed_symbols}\n"
                f"Convention Violations: {len(conv_issues)}\n"
                f"Worker Preliminary Findings ({len(worker_issues)} identified): {json.dumps(worker_issues[:12])}\n\n"
                f"Pull Request Diff (Annotated with Target Line Numbers):\n{orchestrator_diff}\n"
                f"{history_str}\n"
                f"{step_directive}"
            )

            llm_text = await self._call_llm(prompt=prompt, system_prompt=system_prompt)
            decision = self._parse_json(llm_text)

            thought = decision.get("thought", f"Evaluating PR diff context step #{step_idx}...")
            action = decision.get("action", "call_tool" if step_idx < max_steps else "final_review")

            logger.info(f"  [ReAct Step {step_idx}/{max_steps}] Thought: {thought}")

            if action == "final_review" or step_idx == max_steps:
                logger.info(f"  [ReAct Step {step_idx}] Concluding review formulation.")
                final_decision_data = decision
                break

            # Execute tool call
            tool_name = decision.get("tool_name", "get_blast_radius")
            tool_args = decision.get("tool_args", {})
            if tool_name == "get_blast_radius" and "changed_symbols" not in tool_args:
                tool_args["changed_symbols"] = changed_symbols
            elif tool_name == "vector_search" and "query" not in tool_args:
                tool_args["query"] = raw_diff_text[:300] if raw_diff_text else repo_id

            logger.info(f"  [ReAct Step {step_idx}] Tool Call: {tool_name}({json.dumps(tool_args)})")

            tool_raw = await execute_tool_by_name(
                tool_name=tool_name,
                tool_args=tool_args,
                graph_client=graph_client,
                vector_client=vector_client,
                repo_id=repo_id,
                branch=branch,
            )

            summary = tool_raw[:300] if tool_raw else "No output"
            observations.append({
                "step": step_idx,
                "thought": thought,
                "tool_name": tool_name,
                "args": tool_args,
                "raw": tool_raw,
                "summary": summary,
            })

            # Non-blocking pause between reasoning turns
            await asyncio.sleep(0.05)

        # 5. Extract structured issues & build AgentReviewResult
        react_issues = []
        if final_decision_data and isinstance(final_decision_data.get("issues"), list):
            react_issues = final_decision_data.get("issues", [])

        # Combine ReAct verified issues with all worker issues, letting deduplicate_issues merge duplicates
        combined_issues: List[Dict[str, Any]] = list(react_issues) + list(worker_issues)

        # Check observations for blast radius affected callers to capture entry-point vulnerabilities
        for obs in observations:
            if obs.get("tool_name") == "get_blast_radius":
                try:
                    b_raw = obs.get("raw", "")
                    if isinstance(b_raw, str) and b_raw.strip().startswith("{"):
                        b_data = json.loads(b_raw)
                        for aff in b_data.get("affected_symbols", []):
                            aff_file = aff.get("file_path")
                            if aff_file and aff_file not in changed_files:
                                combined_issues.append({
                                    "id": str(uuid.uuid4()),
                                    "title": f"Vulnerability Entry Point: Blast radius impact on {aff.get('qualified_name')}",
                                    "description": f"Transitively affected downstream symbol '{aff.get('qualified_name')}' in entry-point file.",
                                    "category": "security",
                                    "severity": "warning",
                                    "file_path": aff_file,
                                    "line": 1,
                                    "suggested_fix": f"Audit entry point invocation in {aff_file}",
                                })
                except Exception:
                    pass
            elif obs.get("tool_name") == "get_file_dependencies":
                try:
                    dep_raw = obs.get("raw", "")
                    if isinstance(dep_raw, str) and dep_raw.strip().startswith("{"):
                        dep_data = json.loads(dep_raw)
                        for imp_file in dep_data.get("imported_by_files", []):
                            if imp_file and imp_file not in changed_files:
                                combined_issues.append({
                                    "id": str(uuid.uuid4()),
                                    "title": f"Vulnerability Entry Point: Entry route in {imp_file}",
                                    "description": f"Inbound dependent entry point file '{imp_file}' routing into modified logic.",
                                    "category": "security",
                                    "severity": "warning",
                                    "file_path": imp_file,
                                    "line": 1,
                                    "suggested_fix": f"Sanitize input at entry point in {imp_file}",
                                })
                except Exception:
                    pass

        normalized_issues = normalize_issues(combined_issues, changed_files)
        normalized_issues.extend(conv_issues)

        # Deduplicate to eliminate overlapping predictions
        structured_issues = deduplicate_issues(normalized_issues)

        # Build suggestions list for backward compatibility
        suggestions: List[Suggestion] = []
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

        raw_verdict = str((final_decision_data or {}).get("verdict", "")).upper()
        risk_score = float((final_decision_data or {}).get("risk_score", 0.0) or 0.0)

        has_errors = any(i.get("severity") == "error" for i in structured_issues)
        has_warnings = any(i.get("severity") == "warning" for i in structured_issues)

        if raw_verdict in ("ACCEPT", "SUGGEST"):
            verdict: Verdict = raw_verdict
        else:
            verdict = "SUGGEST" if (has_errors or has_warnings or risk_score > 5.0) else "ACCEPT"

        summary = (final_decision_data or {}).get(
            "summary",
            f"GitAmi PR Review Verdict: {verdict}. Evaluated {len(structured_issues)} issue(s) across {len(changed_files)} changed file(s)."
        )
        agent_rationale = (final_decision_data or {}).get(
            "agent_rationale",
            f"Autonomous ReAct review completed in {len(observations)} tool steps."
        )

        decision = DecisionResult(
            verdict=verdict,
            risk_score=risk_score,
            suggestions=suggestions,
            summary=summary,
        )

        total_latency = round(time.perf_counter() - loop_start, 3)
        logger.info(f"GitAmi PR review finished in {total_latency}s | Verdict: {verdict} | Issues: {len(structured_issues)}")

        return AgentReviewResult(
            decision=decision,
            agent_rationale=agent_rationale,
            diff_hunks_count=len(hunks),
            llm_orchestrator_used=(
                self.llm_client.has_gemini
                or self.llm_client.has_ollama
                or self.llm_client.has_groq
            ),
            issues=structured_issues,
        )

    async def _call_llm(self, prompt: str, system_prompt: str) -> str:
        """Call LLM with preference matching configured provider, failing over across available providers."""
        if self.llm_client.orchestrator_provider == "ollama" and self.llm_client.has_ollama:
            res = await self.llm_client._call_ollama(
                prompt,
                system_prompt,
                model=self.llm_client.orchestrator_model or self.llm_client.ollama_model,
                temperature=0.1,
                json_mode=True,
            )
            if res:
                return res

        if self.llm_client.has_gemini:
            res = await self.llm_client._call_gemini(prompt, system_prompt)
            if res:
                return res

        if self.llm_client.has_groq:
            res = await self.llm_client._call_groq(prompt, system_prompt, temperature=0.1, json_mode=True)
            if res:
                return res

        if self.llm_client.has_ollama and self.llm_client.orchestrator_provider != "ollama":
            res = await self.llm_client._call_ollama(
                prompt,
                system_prompt,
                model=self.llm_client.ollama_model,
                temperature=0.1,
                json_mode=True,
            )
            if res:
                return res

        return ""

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Robustly extract and parse JSON object from LLM response."""
        if not text:
            return {"action": "final_review", "verdict": "ACCEPT", "issues": [], "risk_score": 0.0}

        clean = text.strip()

        # If wrapped in markdown code fence, strip outer fence only
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean)
        else:
            fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, re.DOTALL)
            if fence_match:
                clean = fence_match.group(1).strip()

        # Extract outermost JSON object
        first_brace = clean.find("{")
        last_brace = clean.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            clean = clean[first_brace : last_brace + 1]

        # 1. Standard JSON parse
        try:
            return json.loads(clean.strip())
        except Exception:
            pass

        # 2. Python literal dict syntax (single quotes) fallback
        try:
            import ast
            parsed = ast.literal_eval(clean.strip())
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # 3. Clean trailing commas and retry
        try:
            fixed = re.sub(r",\s*([\]}])", r"\1", clean.strip())
            return json.loads(fixed)
        except Exception:
            pass

        # 4. Regex fallback: extract list of issues if enclosed in "issues": [...]
        try:
            match = re.search(r'["\']issues["\']\s*:\s*(\[[^\]]*\])', text, re.DOTALL)
            if match:
                raw_list = match.group(1)
                try:
                    issues = json.loads(raw_list)
                except Exception:
                    import ast
                    issues = ast.literal_eval(raw_list)
                if isinstance(issues, list):
                    return {"action": "final_review", "verdict": "SUGGEST" if issues else "ACCEPT", "issues": issues}
        except Exception:
            pass

        logger.warning(f"Failed to parse ReAct PR reviewer JSON: {text[:200]}")
        return {"action": "final_review", "verdict": "SUGGEST", "issues": [], "risk_score": 2.0}
