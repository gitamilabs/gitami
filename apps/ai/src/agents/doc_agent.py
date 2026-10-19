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
class GeneratedDoc:
    repo_id: str
    doc_type: str  # "workflow_guide", "onboarding_doc", "weekly_changelog", "decision_log"
    title: str
    content_markdown: str
    target_domain: Optional[str]
    covered_files: List[str]
    is_stale: bool = False
    indexed_in_kb: bool = False
    latency_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repo_id": self.repo_id,
            "doc_type": self.doc_type,
            "title": self.title,
            "content_markdown": self.content_markdown,
            "target_domain": self.target_domain,
            "covered_files": self.covered_files,
            "is_stale": self.is_stale,
            "indexed_in_kb": self.indexed_in_kb,
            "latency_ms": self.latency_ms,
        }


class DocAgent(BaseAgent):
    """
    Curated Doc Agent.
    Creates documentation about workflow, architecture, and system operation using the intelligence layer.
    Automatically indexes generated documents back into the semantic Vector KB for other agents.
    Tracks document staleness against codebase commits.
    """

    async def generate_workflow_guide(
        self,
        repo_id: str,
        feature_name: str,
        branch: str = "main",
        feed_to_kb: bool = True,
    ) -> GeneratedDoc:
        start_time = time.perf_counter()

        # Retrieve relevant codebase context
        context_items = await self.fetch_governed_context(
            repo_id=repo_id,
            query=f"{feature_name} implementation architecture flow",
            branch=branch,
            max_items=6,
            max_tokens=3500,
        )
        context_str = "\n".join(
            f"[{c['type']}] {c['title']} ({c.get('file_path', '')}):\n{c['content']}"
            for c in context_items
        )
        covered_files = list({c["file_path"] for c in context_items if c.get("file_path")})

        prompt = (
            f"Repository: {repo_id}\n"
            f"Feature / Subsystem: {feature_name}\n\n"
            f"Codebase Passages & Symbol References:\n{context_str}\n\n"
            "Generate an authoritative, end-to-end Technical Workflow Guide in Markdown:\n"
            "1. Overview & Architecture\n"
            "2. Data Flow & Execution Sequence\n"
            "3. Key Classes, Functions & Interfaces\n"
            "4. Edge Cases & Error Handling\n"
            "Use clear headings, mermaid sequence/flow charts where helpful, and exact file paths."
        )
        system_prompt = (
            "You are the Gitami Lead Technical Documentation Agent. Produce production-grade, "
            "developer-focused architecture and workflow documentation grounded strictly in source code."
        )

        content = await self.llm_client.run_orchestrator(prompt, system_prompt)
        title = f"Workflow Guide: {feature_name.title()}"

        indexed = False
        if feed_to_kb:
            indexed = await self._index_doc_in_kb(repo_id, title, content, covered_files)

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return GeneratedDoc(
            repo_id=repo_id,
            doc_type="workflow_guide",
            title=title,
            content_markdown=content,
            target_domain=feature_name,
            covered_files=covered_files,
            is_stale=False,
            indexed_in_kb=indexed,
            latency_ms=elapsed_ms,
        )

    async def generate_onboarding_doc(
        self,
        repo_id: str,
        domain: str,
        branch: str = "main",
        feed_to_kb: bool = True,
    ) -> GeneratedDoc:
        start_time = time.perf_counter()

        context_items = await self.fetch_governed_context(
            repo_id=repo_id,
            query=f"{domain} domain setup entrypoint configuration",
            branch=branch,
            max_items=6,
            max_tokens=3500,
        )
        context_str = "\n".join(
            f"[{c['type']}] {c['title']} ({c.get('file_path', '')}):\n{c['content']}"
            for c in context_items
        )
        covered_files = list({c["file_path"] for c in context_items if c.get("file_path")})

        prompt = (
            f"Repository: {repo_id}\n"
            f"Domain: {domain}\n\n"
            f"Relevant Code Passages:\n{context_str}\n\n"
            "Generate an Onboarding Guide for a new engineer joining this domain in Markdown:\n"
            "1. Domain Mission & Core Responsibilities\n"
            "2. Directory Structure & Entry Points\n"
            "3. Key Conventions & Invariants\n"
            "4. How to Test & Debug Locally\n"
            "Reference real files and function signatures from the context."
        )
        system_prompt = (
            "You are the Gitami Documentation Agent. Write clear, high-signal onboarding guides for new team members."
        )

        content = await self.llm_client.run_orchestrator(prompt, system_prompt)
        title = f"Onboarding Guide: {domain.title()} Domain"

        indexed = False
        if feed_to_kb:
            indexed = await self._index_doc_in_kb(repo_id, title, content, covered_files)

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return GeneratedDoc(
            repo_id=repo_id,
            doc_type="onboarding_doc",
            title=title,
            content_markdown=content,
            target_domain=domain,
            covered_files=covered_files,
            is_stale=False,
            indexed_in_kb=indexed,
            latency_ms=elapsed_ms,
        )

    async def generate_weekly_changelog(
        self,
        repo_id: str,
        merged_prs: List[Dict[str, Any]],
        week_label: str = "This Week",
    ) -> GeneratedDoc:
        start_time = time.perf_counter()

        pr_summaries = []
        covered_files = []
        for pr in merged_prs:
            pr_summaries.append(
                f"- PR #{pr.get('number', '?')}: {pr.get('title', 'Update')} (by @{pr.get('author', 'user')})\n"
                f"  Summary: {pr.get('body', '')[:150]}"
            )

        prompt = (
            f"Repository: {repo_id}\n"
            f"Timeframe: {week_label}\n"
            f"Merged PRs:\n" + "\n".join(pr_summaries) + "\n\n"
            "Generate a structured Weekly Engineering Changelog in Markdown:\n"
            "1. Executive Summary\n"
            "2. Breaking Changes & Deprecations (if any)\n"
            "3. Key Improvements & Features\n"
            "4. Bug Fixes & Stability Enhancements\n"
            "Format cleanly for an engineering team update."
        )
        system_prompt = "You are the Gitami Documentation Agent generating an engineering changelog."

        content = await self.llm_client.run_orchestrator(prompt, system_prompt)
        title = f"Changelog: {week_label} ({repo_id})"
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return GeneratedDoc(
            repo_id=repo_id,
            doc_type="weekly_changelog",
            title=title,
            content_markdown=content,
            target_domain="changelog",
            covered_files=covered_files,
            is_stale=False,
            indexed_in_kb=False,
            latency_ms=elapsed_ms,
        )

    async def _index_doc_in_kb(
        self,
        repo_id: str,
        title: str,
        content: str,
        covered_files: List[str],
    ) -> bool:
        """Embeds and saves the generated doc into VectorKBClient so other agents have immediate context."""
        try:
            chunks = [content[:1000]]
            if len(content) > 1000:
                chunks.append(content[1000:2500])

            records = [
                {
                    "content": f"Document: {title}\n\n{chunk}",
                    "file_path": f"docs/generated/{title.lower().replace(' ', '_')}.md",
                    "repo_id": repo_id,
                    "kind": "documentation",
                    "name": title,
                }
                for chunk in chunks
            ]
            await self.vector_client.batch_upsert(repo_id, records)
            return True
        except Exception as e:
            logger.warning(f"Could not index generated doc into Vector KB: {e}")
            return False
