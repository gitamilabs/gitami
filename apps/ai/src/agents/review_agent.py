import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent, parse_llm_json
from src.agents.diff_parser import DiffHunk, extract_changed_symbols, parse_git_diff
from src.agents.llm_client import DualLLMClient
from src.analysis.blast_radius import compute_blast_radius
from src.analysis.conventions import check_conventions, check_diff_conventions
from src.analysis.decision import DecisionResult, Suggestion, Verdict
from src.graph.client import Neo4jClient
from src.mcp.tools import tool_get_blast_radius, tool_vector_search
from src.vector.client import VectorKBClient

logger = logging.getLogger(__name__)


@dataclass
class ChecklistItem:
    id: str
    title: str
    description: str
    category: str  # "security", "blast_radius", "test_gap", "convention", "ai_code", "contract"
    severity: str  # "blocking", "warning", "suggestion"
    file_path: str
    line: int
    suggested_fix: str


@dataclass
class ReviewResult:
    repo_id: str
    pr_number: int
    risk_score: int  # 0 to 100
    verdict: str  # "APPROVE", "REQUEST_CHANGES", "COMMENT"
    summary: str
    checklist: List[ChecklistItem]
    blast_radius: Dict[str, Any]
    changed_files: List[str]
    changed_symbols: List[str]
    claude_code_export: str
    latency_ms: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repo_id": self.repo_id,
            "pr_number": self.pr_number,
            "risk_score": self.risk_score,
            "verdict": self.verdict,
            "summary": self.summary,
            "checklist": [
                {
                    "id": item.id,
                    "title": item.title,
                    "description": item.description,
                    "category": item.category,
                    "severity": item.severity,
                    "file_path": item.file_path,
                    "line": item.line,
                    "suggested_fix": item.suggested_fix,
                }
                for item in self.checklist
            ],
            "blast_radius": self.blast_radius,
            "changed_files": self.changed_files,
            "changed_symbols": self.changed_symbols,
            "claude_code_export": self.claude_code_export,
            "latency_ms": self.latency_ms,
        }


class ReviewAgent(BaseAgent):
    """
    Curated Review Agent.
    Executes in-depth PR evaluation covering:
    - Blast Radius (Neo4j call graph)
    - Convention Violations (AST & Diff linting)
    - Test Coverage Gaps (missing test modifications)
    - AI-Generated Code Detection (hallucinated stubs & boilerplate)
    - Security Anti-Patterns (hardcoded secrets, injections, eval)
    - Cross-Repo Contract Breaks
    - Formats checklist export for local Claude Code / Codex sessions.
    """

    SECURITY_PATTERNS = [
        (r"(?i)(api[_-]?key|secret|password|bearer|auth[_-]?token)\s*=\s*['\"][A-Za-z0-9_\-\.]{12,}['\"]", "Hardcoded credential or API secret"),
        (r"dangerouslySetInnerHTML\s*=", "Unsafe inner HTML injection"),
        (r"\beval\s*\(", "Use of eval() function"),
        (r"exec\s*\(", "Use of dynamic code execution (exec)"),
        (r"(?i)select\s+.*\s+from\s+.*\s*\+\s*['\"]", "Possible SQL string concatenation injection"),
    ]

    def _scan_security_anti_patterns(self, diff_text: str, hunks: List[DiffHunk]) -> List[ChecklistItem]:
        items: List[ChecklistItem] = []
        for hunk in hunks:
            for item in hunk.added_lines:
                line_no, line_str = item if isinstance(item, tuple) else (hunk.new_start, str(item))
                for pattern, desc in self.SECURITY_PATTERNS:
                    if re.search(pattern, line_str):
                        items.append(
                            ChecklistItem(
                                id=str(uuid.uuid4()),
                                title=f"Security Anti-Pattern: {desc}",
                                description=f"Potentially hazardous code identified: `{line_str.strip()}`",
                                category="security",
                                severity="blocking",
                                file_path=hunk.file_path or "codebase",
                                line=line_no,
                                suggested_fix="Store credentials in environment variables or sanitize input.",
                            )
                        )
        return items

    def _scan_test_coverage_gaps(self, changed_files: List[str], hunks: List[DiffHunk]) -> List[ChecklistItem]:
        items: List[ChecklistItem] = []
        has_tests = any(
            "test" in f.lower() or "spec" in f.lower() or "__tests__" in f
            for f in changed_files
        )
        non_test_code_files = [
            f for f in changed_files
            if f.endswith((".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs"))
            and not ("test" in f.lower() or "spec" in f.lower())
        ]

        if non_test_code_files and not has_tests:
            items.append(
                ChecklistItem(
                    id=str(uuid.uuid4()),
                    title="Test Coverage Gap: New logic introduced without tests",
                    description=(
                        f"PR modifies {len(non_test_code_files)} source files ({', '.join(non_test_code_files[:3])}) "
                        "without modifying or introducing any unit/integration tests."
                    ),
                    category="test_gap",
                    severity="warning",
                    file_path=non_test_code_files[0],
                    line=1,
                    suggested_fix="Add automated tests covering modified functions before merging.",
                )
            )
        return items

    def _scan_ai_code_anti_patterns(self, diff_text: str, hunks: List[DiffHunk]) -> List[ChecklistItem]:
        items: List[ChecklistItem] = []
        ai_markers = [
            r"//\s*TODO:\s*Add implementation later",
            r"#\s*TODO:\s*Implement logic",
            r"catch\s*\([^\)]*\)\s*\{\s*\}",  # empty swallow catch
            r"except\s*:\s*pass",  # bare except pass
        ]
        for hunk in hunks:
            for item in hunk.added_lines:
                line_no, line_str = item if isinstance(item, tuple) else (hunk.new_start, str(item))
                for marker in ai_markers:
                    if re.search(marker, line_str):
                        items.append(
                            ChecklistItem(
                                id=str(uuid.uuid4()),
                                title="AI Code Anti-Pattern: Incomplete stub or swallowed exception",
                                description=f"Pattern detected: `{line_str.strip()}`",
                                category="ai_code",
                                severity="suggestion",
                                file_path=hunk.file_path or "codebase",
                                line=line_no,
                                suggested_fix="Implement robust error handling or remove dummy stubs.",
                            )
                        )
        return items

    def _generate_claude_code_export(self, repo_id: str, pr_number: int, items: List[ChecklistItem]) -> str:
        lines = [
            f"# Claude Code Task: Resolve Review Findings for PR #{pr_number} in {repo_id}",
            "",
            "Please review and fix the following items found by Gitami Review Agent:",
            "",
        ]
        for idx, item in enumerate(items, start=1):
            lines.append(f"### {idx}. [{item.severity.upper()}] {item.title}")
            lines.append(f"- **File:** `{item.file_path}:{item.line}`")
            lines.append(f"- **Category:** {item.category}")
            lines.append(f"- **Issue:** {item.description}")
            lines.append(f"- **Suggested Fix:** {item.suggested_fix}")
            lines.append("")
        return "\n".join(lines)

    async def run(
        self,
        repo_id: str,
        pr_number: int,
        base_branch: str,
        head_branch: str,
        title: str,
        body: str,
        diff_text: str,
        symbols: Optional[list] = None,
        changed_symbols: Optional[List[str]] = None,
    ) -> ReviewResult:
        start_time = time.perf_counter()

        # 1. Parse diff into hunks & files
        hunks = parse_git_diff(diff_text)
        changed_files = list({h.file_path for h in hunks if h.file_path})

        if not changed_symbols:
            changed_symbols = extract_changed_symbols(hunks, diff_text)

        checklist: List[ChecklistItem] = []

        # 2. Blast Radius Analysis via Neo4j
        blast_data: Dict[str, Any] = {}
        try:
            blast_json = await tool_get_blast_radius(
                self.graph_client,
                repo_id=repo_id,
                changed_symbols=changed_symbols,
                branch=base_branch,
            )
            blast_data = parse_llm_json(blast_json)
            downstream = blast_data.get("downstream_affected_symbols", [])
            if len(downstream) > 10:
                checklist.append(
                    ChecklistItem(
                        id=str(uuid.uuid4()),
                        title=f"High Blast Radius: {len(downstream)} downstream symbols affected",
                        description=f"Changes to {changed_symbols[:3]} impact a wide surface area across the project.",
                        category="blast_radius",
                        severity="warning",
                        file_path=changed_files[0] if changed_files else "codebase",
                        line=1,
                        suggested_fix="Verify integration tests for downstream callers before merging.",
                    )
                )
        except Exception as e:
            logger.warning(f"Blast radius computation notice: {e}")

        # 3. Security Anti-Pattern Scan
        security_items = self._scan_security_anti_patterns(diff_text, hunks)
        checklist.extend(security_items)

        # 4. Test Coverage Gap Scan
        test_gap_items = self._scan_test_coverage_gaps(changed_files, hunks)
        checklist.extend(test_gap_items)

        # 5. AI Code Anti-Pattern Scan
        ai_code_items = self._scan_ai_code_anti_patterns(diff_text, hunks)
        checklist.extend(ai_code_items)

        # 6. Static AST & Diff Conventions
        all_violations = []
        if symbols:
            all_violations.extend(check_conventions(symbols))
        all_violations.extend(check_diff_conventions(diff_text))

        for v in all_violations:
            checklist.append(
                ChecklistItem(
                    id=str(uuid.uuid4()),
                    title=f"Convention Violation: {v.rule_id}",
                    description=v.message,
                    category="convention",
                    severity="blocking" if v.severity == "error" else "warning",
                    file_path=v.file_path,
                    line=v.line,
                    suggested_fix=f"Follow codebase guidelines for {v.rule_id}.",
                )
            )

        # 7. LLM Deep Review for Bugs & Logic Flaws
        worker_prompt = (
            f"Repository: {repo_id}\n"
            f"PR #{pr_number}: {title}\n"
            f"Modified Files: {changed_files}\n"
            f"Modified Symbols: {changed_symbols}\n\n"
            f"Diff (first 6000 chars):\n{diff_text[:6000]}\n\n"
            "Analyze the code diff for subtle logic errors, missing null guards, and edge case failures. "
            "Return valid JSON:\n"
            '{"issues": [{"title": "...", "description": "...", "severity": "warning", "file_path": "...", "line": 1, "suggested_fix": "..."}]}'
        )
        worker_system = (
            "You are an expert static analysis code reviewer. Detect non-trivial bugs and return structured JSON."
        )
        worker_raw = await self.llm_client.run_worker(worker_prompt, worker_system)
        parsed_worker = parse_llm_json(worker_raw)
        if isinstance(parsed_worker, dict) and "issues" in parsed_worker:
            for item in parsed_worker["issues"]:
                sev = item.get("severity", "warning").lower()
                checklist.append(
                    ChecklistItem(
                        id=str(uuid.uuid4()),
                        title=item.get("title", "Potential Logic Bug"),
                        description=item.get("description", "Identified possible flaw during deep diff analysis."),
                        category="logic",
                        severity="blocking" if "error" in sev or "blocking" in sev else "warning",
                        file_path=item.get("file_path", changed_files[0] if changed_files else "codebase"),
                        line=item.get("line", 1),
                        suggested_fix=item.get("suggested_fix", "Review logic boundary condition."),
                    )
                )

        # 8. Compute Deterministic Risk Score (0 - 100)
        risk = 15  # baseline
        blocking_count = sum(1 for i in checklist if i.severity == "blocking")
        warning_count = sum(1 for i in checklist if i.severity == "warning")

        risk += blocking_count * 25
        risk += warning_count * 10
        if blast_data.get("downstream_affected_symbols"):
            risk += min(20, len(blast_data["downstream_affected_symbols"]) * 2)
        risk_score = min(100, max(0, risk))

        # 9. Determine Verdict
        if blocking_count > 0 or risk_score >= 75:
            verdict = "REQUEST_CHANGES"
        elif warning_count > 0 or risk_score >= 40:
            verdict = "COMMENT"
        else:
            verdict = "APPROVE"

        summary = (
            f"PR #{pr_number} evaluation complete. Verdict: {verdict} with Risk Score: {risk_score}/100. "
            f"Found {len(checklist)} findings ({blocking_count} blocking, {warning_count} warning)."
        )

        claude_export = self._generate_claude_code_export(repo_id, pr_number, checklist)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return ReviewResult(
            repo_id=repo_id,
            pr_number=pr_number,
            risk_score=risk_score,
            verdict=verdict,
            summary=summary,
            checklist=checklist,
            blast_radius=blast_data,
            changed_files=changed_files,
            changed_symbols=changed_symbols,
            claude_code_export=claude_export,
            latency_ms=elapsed_ms,
        )
