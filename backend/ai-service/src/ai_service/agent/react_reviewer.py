"""Autonomous ReAct Agent for Pull Request Review and Vulnerability Detection."""

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from ai_service.graph.client import Neo4jClient
from ai_service.vector.client import VectorKBClient
from ai_service.mcp.tools import execute_tool_by_name
from ai_service.analysis.conventions import check_conventions, check_diff_conventions
from ai_service.analysis.decision import DecisionResult, Verdict, Suggestion
from ai_service.agent.diff_parser import parse_git_diff, extract_changed_symbols
from ai_service.agent.llm_client import DualLLMClient
from ai_service.agent.prompts import get_react_pr_reviewer_prompt

logger = logging.getLogger(__name__)


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
        max_steps: int = 4,
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

        violations_dicts = [
            {"rule": v.rule_id, "file": v.file_path, "line": v.line, "msg": v.message, "severity": v.severity}
            for v in all_violations
        ]

        # 3. ReAct reasoning loop
        observations: List[Dict[str, Any]] = []
        final_decision_data: Optional[Dict[str, Any]] = None
        system_prompt = get_react_pr_reviewer_prompt()

        diff_snippet = raw_diff_text[:4000] if raw_diff_text else "# Empty diff"

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

            prompt = (
                f"Target Repository: '{repo_id}' (branch: '{branch}')\n"
                f"Changed Files: {changed_files}\n"
                f"Changed Symbols: {changed_symbols}\n"
                f"Static Convention Violations: {json.dumps(violations_dicts)}\n\n"
                f"Pull Request Diff:\n{diff_snippet}\n"
                f"{history_str}\n"
                f"Current Reasoning Step #{step_idx} of {max_steps}.\n"
                f"Decide your next action: choose 'call_tool' to inspect further, or 'final_review' to submit findings."
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

            # Small pause between reasoning turns to protect free-tier API quotas
            time.sleep(0.5)

        # 4. Fallback synthesis if final_review was not cleanly provided
        if not final_decision_data or final_decision_data.get("action") != "final_review":
            synth_prompt = (
                f"Target Repository: '{repo_id}' (branch: '{branch}')\n"
                f"Changed Files: {changed_files}\n"
                f"Diff:\n{diff_snippet}\n"
                f"Observations:\n{json.dumps([o['raw'] for o in observations], indent=2)[:3000]}\n\n"
                f"Formulate final review JSON with verdict, risk_score, summary, and issues."
            )
            synth_res = await self._call_llm(prompt=synth_prompt, system_prompt=system_prompt)
            final_decision_data = self._parse_json(synth_res)

        # 5. Extract structured issues & build AgentReviewResult
        structured_issues: List[Dict[str, Any]] = []
        raw_issues = final_decision_data.get("issues", [])
        if isinstance(raw_issues, list):
            for item in raw_issues:
                if isinstance(item, dict):
                    structured_issues.append({
                        "id": str(uuid.uuid4()),
                        "title": item.get("title", "Code Defect Detected"),
                        "description": item.get("description", "Potential defect identified in PR analysis."),
                        "category": str(item.get("category", "bug")).lower(),
                        "severity": str(item.get("severity", "warning")).lower(),
                        "file_path": item.get("file_path", changed_files[0] if changed_files else "codebase"),
                        "line": int(item.get("line", 1) or 1),
                        "suggested_fix": item.get("suggested_fix", ""),
                    })

        # Append static convention violations as issues and suggestions
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
                "suggested_fix": f"Adhere to project convention {v.rule_id}",
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

        # Convert issues to suggestions list
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

        raw_verdict = str(final_decision_data.get("verdict", "")).upper()
        risk_score = float(final_decision_data.get("risk_score", 0.0) or 0.0)

        # Determine verdict: SUGGEST if actionable issues or high risk, else ACCEPT
        has_errors = any(i.get("severity") == "error" for i in structured_issues)
        has_warnings = any(i.get("severity") == "warning" for i in structured_issues)

        if raw_verdict in ("ACCEPT", "SUGGEST"):
            verdict: Verdict = raw_verdict
        else:
            verdict = "SUGGEST" if (has_errors or has_warnings or risk_score > 5.0) else "ACCEPT"

        summary = final_decision_data.get(
            "summary",
            f"ReAct PR Review Verdict: {verdict}. Evaluated {len(structured_issues)} issue(s) across {len(changed_files)} changed file(s)."
        )
        agent_rationale = final_decision_data.get(
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
        logger.info(f"ReAct PR review finished in {total_latency}s | Verdict: {verdict} | Issues: {len(structured_issues)}")

        return AgentReviewResult(
            decision=decision,
            agent_rationale=agent_rationale,
            diff_hunks_count=len(hunks),
            llm_orchestrator_used=self.llm_client.has_gemini,
            issues=structured_issues,
        )

    async def _call_llm(self, prompt: str, system_prompt: str) -> str:
        """Call LLM with preference for Gemini free tier, failing over to Groq."""
        if self.llm_client.has_gemini:
            res = await self.llm_client._call_gemini(prompt, system_prompt)
            if res:
                return res

        if self.llm_client.has_groq:
            res = await self.llm_client._call_groq(prompt, system_prompt, temperature=0.1, json_mode=True)
            if res:
                return res

        return ""

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Robustly extract and parse JSON object from LLM response."""
        if not text:
            return {"action": "final_review", "verdict": "ACCEPT", "issues": [], "risk_score": 0.0}

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
            logger.warning(f"Failed to parse ReAct PR reviewer JSON ({e}): {text[:200]}")
            return {"action": "final_review", "verdict": "SUGGEST", "issues": [], "risk_score": 2.0}
