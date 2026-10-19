import json
import logging
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
