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
class IssueTriageResult:
    issue_number: int
    repo_id: str
    is_spam: bool
    is_duplicate: bool
    duplicate_of: Optional[int]
    criticality: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    criticality_score: int  # 1 - 10
    ai_code_suspected: bool
    ai_code_reason: Optional[str]
    domain_tags: List[str]
    suggested_labels: List[str]
    recommended_action: str
    summary: str
    latency_ms: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_number": self.issue_number,
            "repo_id": self.repo_id,
            "is_spam": self.is_spam,
            "is_duplicate": self.is_duplicate,
            "duplicate_of": self.duplicate_of,
            "criticality": self.criticality,
            "criticality_score": self.criticality_score,
            "ai_code_suspected": self.ai_code_suspected,
            "ai_code_reason": self.ai_code_reason,
            "domain_tags": self.domain_tags,
            "suggested_labels": self.suggested_labels,
            "recommended_action": self.recommended_action,
            "summary": self.summary,
            "latency_ms": self.latency_ms,
        }


class IssueAgent(BaseAgent):
    """
    Curated Issue Agent.
    Evaluates newly filed or updated issues for spam, duplicates across open/closed issues,
    criticality score, domain classification, and AI-code suspicion flags.
    """

    AI_CODE_PATTERNS = [
        r"as an ai",
        r"i apologize for the confusion",
        r"here is the updated code",
        r"todo:\s*implement this",
        r"insert code here",
        r"//\s*rest of the code remains the same",
        r"#\s*rest of the code remains the same",
    ]

    def _check_ai_code_heuristic(self, text: str) -> tuple[bool, Optional[str]]:
        lower = text.lower()
        for pat in self.AI_CODE_PATTERNS:
            if re.search(pat, lower):
                return True, f"Matched characteristic LLM generation pattern: '{pat}'"
        return False, None

    async def run(
        self,
        repo_id: str,
        issue_number: int,
        title: str,
        body: str,
        author: str = "unknown",
        existing_labels: Optional[List[str]] = None,
        existing_issues: Optional[List[Dict[str, Any]]] = None,
    ) -> IssueTriageResult:
        start_time = time.perf_counter()
        combined_text = f"{title}\n\n{body}"

        # 1. AI Code Suspected heuristic + LLM inspection
        ai_suspected, ai_reason = self._check_ai_code_heuristic(combined_text)

        # 2. Check duplicates via Vector KB / issue list
        is_duplicate = False
        duplicate_of = None
        if existing_issues:
            # Check title similarity across provided issues
            lower_title = title.lower().strip()
            for ex in existing_issues:
                ex_num = ex.get("number")
                if ex_num and ex_num != issue_number:
                    ex_title = ex.get("title", "").lower().strip()
                    if ex_title == lower_title or (len(lower_title) > 10 and lower_title in ex_title):
                        is_duplicate = True
                        duplicate_of = ex_num
                        break

        # 3. Retrieve relevant codebase context for criticality and domain assessment
        governed_context = await self.fetch_governed_context(
            repo_id=repo_id,
            query=f"{title} {body[:200]}",
            max_items=3,
            max_tokens=1500,
        )
        context_str = "\n".join(
            f"[{c['type']}] {c['title']} ({c.get('file_path', '')})"
            for c in governed_context
        )

        # 4. Invoke LLM for structured triage
        triage_prompt = (
            f"Repository: {repo_id}\n"
            f"Issue #{issue_number} by @{author}\n"
            f"Title: {title}\n"
            f"Body:\n{body[:3000]}\n\n"
            f"Codebase Context Clues:\n{context_str}\n\n"
            "Analyze this GitHub issue and return valid JSON with:\n"
            "{\n"
            '  "is_spam": false,\n'
            '  "criticality_score": 7,\n'
            '  "criticality": "HIGH",\n'
            '  "ai_code_suspected": false,\n'
            '  "ai_code_reason": null,\n'
            '  "domain_tags": ["api", "auth"],\n'
            '  "suggested_labels": ["bug", "severity:high", "domain:auth"],\n'
            '  "recommended_action": "Run Investigation Agent to diagnose auth boundary failure.",\n'
            '  "summary": "Clear description of what this issue addresses."\n'
            "}\n"
            "Scoring Guidelines for criticality:\n"
            "- 9-10 (CRITICAL): Security flaw, crash, data loss, build/deploy blockage.\n"
            "- 7-8 (HIGH): Major functional breakdown in core business logic.\n"
            "- 4-6 (MEDIUM): Secondary feature bug or performance lag.\n"
            "- 1-3 (LOW): Cosmetic styling, typo, documentation."
        )

        system_prompt = (
            "You are the Gitami Issue Agent. Provide rigorous, objective triage for developer issues. "
            "Output valid JSON only."
        )

        raw_llm = await self.llm_client.run_orchestrator(triage_prompt, system_prompt)
        parsed = parse_llm_json(raw_llm)

        # Merge heuristic findings
        llm_ai_suspected = parsed.get("ai_code_suspected", False)
        final_ai_suspected = ai_suspected or bool(llm_ai_suspected)
        final_ai_reason = ai_reason or parsed.get("ai_code_reason")

        score = int(parsed.get("criticality_score", 5))
        if score >= 9:
            crit = "CRITICAL"
        elif score >= 7:
            crit = "HIGH"
        elif score >= 4:
            crit = "MEDIUM"
        else:
            crit = "LOW"

        domains = parsed.get("domain_tags", ["general"])
        labels = list(set(parsed.get("suggested_labels", [])))
        if final_ai_suspected and "ai-code-suspected" not in labels:
            labels.append("ai-code-suspected")
        if f"severity:{crit.lower()}" not in labels:
            labels.append(f"severity:{crit.lower()}")

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return IssueTriageResult(
            issue_number=issue_number,
            repo_id=repo_id,
            is_spam=bool(parsed.get("is_spam", False)),
            is_duplicate=is_duplicate or bool(parsed.get("is_duplicate", False)),
            duplicate_of=duplicate_of or parsed.get("duplicate_of"),
            criticality=crit,
            criticality_score=score,
            ai_code_suspected=final_ai_suspected,
            ai_code_reason=final_ai_reason,
            domain_tags=domains,
            suggested_labels=labels,
            recommended_action=parsed.get(
                "recommended_action",
                "Assign to maintainer and run Investigation Agent if root cause is unknown."
            ),
            summary=parsed.get("summary", f"Triage complete for issue #{issue_number}: {title}"),
            latency_ms=elapsed_ms,
        )
