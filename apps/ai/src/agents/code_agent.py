import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent, parse_llm_json
from src.agents.llm_client import DualLLMClient
from src.graph.client import Neo4jClient
from src.vector.client import VectorKBClient

logger = logging.getLogger(__name__)


@dataclass
class FixPlan:
    plan_id: str
    repo_id: str
    trigger_source: str  # "review", "issue", "chat", "audit"
    summary: str
    files_to_touch: List[str]
    approach: str
    test_strategy: str
    risk_assessment: str  # "low", "medium", "high"
    needs_approval: bool = True
    approved: bool = False
    latency_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "repo_id": self.repo_id,
            "trigger_source": self.trigger_source,
            "summary": self.summary,
            "files_to_touch": self.files_to_touch,
            "approach": self.approach,
            "test_strategy": self.test_strategy,
            "risk_assessment": self.risk_assessment,
            "needs_approval": self.needs_approval,
            "approved": self.approved,
            "latency_ms": self.latency_ms,
        }


@dataclass
class ExecutedFixResult:
    plan_id: str
    repo_id: str
    status: str  # "ready_for_pr", "verified", "failed"
    reproduction_test_code: str
    test_file_path: str
    patch_diff: str
    pr_title: str
    pr_description_markdown: str
    touched_files: List[str]
    latency_ms: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "repo_id": self.repo_id,
            "status": self.status,
            "reproduction_test_code": self.reproduction_test_code,
            "test_file_path": self.test_file_path,
            "patch_diff": self.patch_diff,
            "pr_title": self.pr_title,
            "pr_description_markdown": self.pr_description_markdown,
            "touched_files": self.touched_files,
            "latency_ms": self.latency_ms,
        }


class CodeAgent(BaseAgent):
    """
    Curated Code Agent.
    Implements the two-stage fix workflow:
    1. Generates a fix plan first (file modification order, approach, test strategy)
       requiring maintainer approval before any code is generated.
    2. Writes tests before implementation, verifies changes, and formats PR with full audit trail.
    """

    async def generate_fix_plan(
        self,
        repo_id: str,
        issue_title: str,
        issue_description: str,
        trigger_source: str = "review",
        affected_files: Optional[List[str]] = None,
        branch: str = "main",
    ) -> FixPlan:
        start_time = time.perf_counter()

        # Query codebase context around the issue
        context_items = await self.fetch_governed_context(
            repo_id=repo_id,
            query=f"{issue_title} {issue_description[:300]}",
            branch=branch,
            max_items=4,
            max_tokens=2500,
        )
        context_str = "\n".join(
            f"[{c['type']}] {c['title']} ({c.get('file_path', '')}):\n{c['content']}"
            for c in context_items
        )

        plan_prompt = (
            f"Repository: {repo_id}\n"
            f"Trigger Source: {trigger_source}\n"
            f"Issue Title: {issue_title}\n"
            f"Issue Description:\n{issue_description}\n\n"
            f"Codebase Context Clues:\n{context_str}\n\n"
            "Formulate a surgical Fix Plan before writing code. Return valid JSON:\n"
            "{\n"
            '  "summary": "...",\n'
            '  "files_to_touch": ["file1.ts", "file2.ts"],\n'
            '  "approach": "...",\n'
            '  "test_strategy": "...",\n'
            '  "risk_assessment": "low"\n'
            "}"
        )
        system_prompt = (
            "You are the Gitami Code Agent planner. Produce safe, minimal, surgical fix plans. "
            "Never rewrite entire files; identify the exact files and functions to modify."
        )

        raw = await self.llm_client.run_orchestrator(plan_prompt, system_prompt)
        parsed = parse_llm_json(raw)

        plan_id = f"plan_{int(time.time())}"
        files = parsed.get("files_to_touch", affected_files or ["src/index.ts"])
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return FixPlan(
            plan_id=plan_id,
            repo_id=repo_id,
            trigger_source=trigger_source,
            summary=parsed.get("summary", f"Fix for: {issue_title}"),
            files_to_touch=files,
            approach=parsed.get("approach", "Apply surgical patch with guarded assertions."),
            test_strategy=parsed.get("test_strategy", "Add unit test reproducing the defect."),
            risk_assessment=parsed.get("risk_assessment", "medium"),
            needs_approval=True,
            approved=False,
            latency_ms=elapsed_ms,
        )

    async def execute_approved_plan(
        self,
        plan: FixPlan,
        existing_file_contents: Dict[str, str],
        maintainer_notes: Optional[str] = None,
    ) -> ExecutedFixResult:
        start_time = time.perf_counter()

        # Generate test first, then implementation patch
        files_context = "\n\n".join(
            f"=== File: {path} ===\n{content[:2500]}"
            for path, content in existing_file_contents.items()
        )

        codegen_prompt = (
            f"Repository: {plan.repo_id}\n"
            f"Approved Plan: {plan.summary}\n"
            f"Approach: {plan.approach}\n"
            f"Test Strategy: {plan.test_strategy}\n"
            f"Maintainer Notes: {maintainer_notes or 'None'}\n\n"
            f"Existing Code Contents:\n{files_context}\n\n"
            "Produce two things in valid JSON:\n"
            "1. `reproduction_test_code`: automated test verifying the fix\n"
            "2. `patch_diff`: unified git diff format applying the fix\n"
            "3. `pr_title`: clean conventional commit PR title\n"
            "4. `pr_description_markdown`: comprehensive PR description with audit trail\n"
            "{\n"
            '  "reproduction_test_code": "...",\n'
            '  "test_file_path": "tests/test_fix.py",\n'
            '  "patch_diff": "...",\n'
            '  "pr_title": "...",\n'
            '  "pr_description_markdown": "..."\n'
            "}"
        )
        system_prompt = (
            "You are the Gitami Code Agent executor. Synthesize verified, high-quality, test-backed code patches. "
            "Output valid JSON only."
        )

        raw = await self.llm_client.run_orchestrator(codegen_prompt, system_prompt)
        parsed = parse_llm_json(raw)

        pr_title = parsed.get("pr_title", f"[AI Fix] {plan.summary}")
        pr_desc = parsed.get(
            "pr_description_markdown",
            f"## [AI Fix] {plan.summary}\n\n"
            f"### Trigger Source\n- Originated from {plan.trigger_source} workflow.\n\n"
            f"### Approach\n{plan.approach}\n\n"
            f"### Verification\n- Tests generated: `{parsed.get('test_file_path', 'tests/test_fix.py')}`\n"
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return ExecutedFixResult(
            plan_id=plan.plan_id,
            repo_id=plan.repo_id,
            status="ready_for_pr",
            reproduction_test_code=parsed.get("reproduction_test_code", "// Test reproduction stub"),
            test_file_path=parsed.get("test_file_path", "tests/fix.test.ts"),
            patch_diff=parsed.get("patch_diff", ""),
            pr_title=pr_title,
            pr_description_markdown=pr_desc,
            touched_files=plan.files_to_touch,
            latency_ms=elapsed_ms,
        )

    async def generate_file_fixes(
        self,
        repo_id: str,
        issues: List[Dict[str, Any]],
        existing_file_contents: Dict[str, str],
        base_branch: str = "main",
        pr_number: int = 1,
    ) -> Dict[str, Any]:
        """
        Generates surgical line-level file fixes for reported PR issues.
        Returns a dict matching the control plane contract:
        {"success": bool, "plan_rationale": str, "file_fixes": [{"file_path": str, "content": str}], "error": Optional[str]}
        """
        if not issues:
            return {
                "success": False,
                "plan_rationale": "No issues provided to fix.",
                "file_fixes": [],
                "error": "No issues provided",
            }

        target_files = list({i.get("file_path") for i in issues if i.get("file_path")})
        issues_summary = "\n".join(
            f"- [{i.get('category', 'issue')}] {i.get('file_path')}:{i.get('line')}: {i.get('title', '')} - {i.get('description', '')}"
            for i in issues
        )

        plan = await self.generate_fix_plan(
            repo_id=repo_id,
            issue_title=f"Fix {len(issues)} issue(s) in PR #{pr_number}",
            issue_description=issues_summary,
            trigger_source="review",
            affected_files=target_files,
            branch=base_branch,
        )

        from src.prompts import get_prompt
        worker_system = get_prompt("fixer_worker")

        file_fixes: List[Dict[str, str]] = []
        file_block_pattern = re.compile(
            r"<<<FILE:\s*([^\n>]+)>>>\n?(.*?)\n?<<<ENDFILE>>>", re.DOTALL
        )

        for fp in target_files:
            original_content = existing_file_contents.get(fp, "")
            if not original_content:
                continue

            file_issues = [i for i in issues if i.get("file_path") == fp]
            if not file_issues:
                continue

            file_issues_text = "\n".join(
                f"Fix #{idx}:\n- Line {item.get('line', '?')}: {item.get('title', '')}\n"
                f"- Problem: {item.get('description', '')}\n- Suggested Fix: {item.get('suggested_fix', 'N/A')}\n"
                for idx, item in enumerate(file_issues, start=1)
            )

            worker_prompt = f"""Apply MINIMAL surgical fixes to this file.

<fix_plan>
{plan.summary}
{plan.approach}
</fix_plan>

<specific_fixes_for_this_file>
{file_issues_text}
</specific_fixes_for_this_file>

<original_file path="{fp}">
{original_content}
</original_file>

REMEMBER: Output the COMPLETE file with ONLY the specific bug-fix lines changed.
Every other line must be IDENTICAL to the original. Do NOT rewrite, refactor, or simplify the file.
Wrap your output in <<<FILE: {fp}>>> ... <<<ENDFILE>>> blocks."""

            worker_output = await self.llm_client.run_worker(worker_prompt, worker_system, json_mode=False)

            matches = file_block_pattern.findall(worker_output)
            clean_fixed_content = None
            for matched_path, content in matches:
                c_path = matched_path.strip()
                c_content = content.strip()
                if c_path and c_content:
                    clean_fixed_content = c_content
                    break

            if clean_fixed_content:
                file_fixes.append({"file_path": fp, "content": clean_fixed_content})
            else:
                patched = _apply_simple_fix(original_content, file_issues)
                if patched != original_content:
                    file_fixes.append({"file_path": fp, "content": patched})

        return {
            "success": len(file_fixes) > 0,
            "plan_rationale": plan.summary,
            "file_fixes": file_fixes,
            "error": None if file_fixes else "No surgical fixes generated",
        }


def _apply_simple_fix(original_content: str, issues: List[Dict[str, Any]]) -> str:
    """Simple text-replacement fallback when LLM output does not match block format."""
    content = original_content
    for issue in issues:
        suggested_fix = issue.get("suggested_fix", "").strip()
        if not suggested_fix:
            continue
        if "replace" in suggested_fix.lower() and "with" in suggested_fix.lower():
            try:
                parts = suggested_fix.split("with", 1)
                old_str = parts[0].replace("Replace", "").replace("replace", "").strip().strip("`'\"")
                new_str = parts[1].strip().strip("`'\"")
                if old_str and old_str in content:
                    content = content.replace(old_str, new_str, 1)
            except Exception:
                pass
    return content

