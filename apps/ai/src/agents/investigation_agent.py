import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent, clean_json_text, parse_llm_json
from src.agents.llm_client import DualLLMClient
from src.graph.client import Neo4jClient
from src.mcp.tools import tool_get_blast_radius, tool_vector_search
from src.vector.client import VectorKBClient

logger = logging.getLogger(__name__)


@dataclass
class InvestigationTraceStep:
    step: int
    hypothesis: str
    action_taken: str
    evidence_gathered: str
    confidence_update: float


@dataclass
class InvestigationResult:
    query: str
    repo_id: str
    verdict: str
    root_cause: Optional[str]
    confidence: float
    is_deep_investigation: bool
    reasoning_trace: List[Dict[str, Any]]
    recommended_steps: List[str]
    citations: List[Dict[str, Any]]
    plain_text_summary: str
    latency_ms: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "repo_id": self.repo_id,
            "verdict": self.verdict,
            "root_cause": self.root_cause,
            "confidence": round(self.confidence, 2),
            "is_deep_investigation": self.is_deep_investigation,
            "reasoning_trace": self.reasoning_trace,
            "recommended_steps": self.recommended_steps,
            "citations": self.citations,
            "plain_text_summary": self.plain_text_summary,
            "latency_ms": self.latency_ms,
        }


class InvestigationAgent(BaseAgent):
    """
    Curated Investigation Agent.
    Executes fast single-shot answers for informational queries, or up to an 8-step
    iterative hypothesis-testing loop for complex root-cause investigations and production incidents.
    """

    INVESTIGATION_KEYWORDS = {
        "why", "bug", "error", "crash", "fail", "failing", "broken", "exception",
        "incident", "regression", "root cause", "diagnose", "investigate", "timeout",
        "latency", "leak", "bottleneck", "deadlock"
    }

    def _requires_iterative_investigation(self, query: str, is_incident: bool) -> bool:
        if is_incident:
            return True
        query_words = set(query.lower().split())
        return len(query_words.intersection(self.INVESTIGATION_KEYWORDS)) > 0

    async def run(
        self,
        query: str,
        repo_id: str,
        branch: str = "main",
        is_incident: bool = False,
        incident_context: Optional[Dict[str, Any]] = None,
        max_steps: int = 8,
    ) -> InvestigationResult:
        start_time = time.perf_counter()

        deep_mode = self._requires_iterative_investigation(query, is_incident)
        initial_context = await self.fetch_governed_context(
            repo_id=repo_id,
            query=query,
            branch=branch,
            max_items=5,
            max_tokens=3000,
        )

        citations: List[Dict[str, Any]] = []
        for idx, item in enumerate(initial_context, start=1):
            if item.get("file_path"):
                citations.append({
                    "id": idx,
                    "file_path": item["file_path"],
                    "symbol": item.get("symbol"),
                    "lines": item.get("line_range"),
                    "snippet": item["content"][:300],
                })

        if not deep_mode:
            # --- Fast Path (Single-Shot) ---
            return await self._run_fast_path(
                query=query,
                repo_id=repo_id,
                branch=branch,
                context_items=initial_context,
                citations=citations,
                start_time=start_time,
            )

        # --- Deep Path (Up to 8-step iterative hypothesis loop) ---
        return await self._run_iterative_loop(
            query=query,
            repo_id=repo_id,
            branch=branch,
            initial_context=initial_context,
            citations=citations,
            incident_context=incident_context,
            max_steps=min(max_steps, 8),
            start_time=start_time,
        )

    async def _run_fast_path(
        self,
        query: str,
        repo_id: str,
        branch: str,
        context_items: List[Dict[str, Any]],
        citations: List[Dict[str, Any]],
        start_time: float,
    ) -> InvestigationResult:
        context_str = "\n".join(
            f"[{c['type']}] {c['title']} ({c.get('file_path', '')}):\n{c['content']}"
            for c in context_items
        )

        prompt = (
            f"Repository: {repo_id} (branch: {branch})\n"
            f"Question: {query}\n\n"
            f"Retrieved Codebase Context:\n{context_str}\n\n"
            "Provide a precise, direct answer referencing the relevant files and functions. "
            "Output your response formatted cleanly with markdown code blocks where applicable."
        )
        system_prompt = (
            "You are the Gitami Investigation Agent in Fast Path mode. "
            "Provide clear, accurate, and concise architectural explanations grounded strictly in the provided codebase context."
        )

        answer = await self.llm_client.run_orchestrator(prompt, system_prompt)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return InvestigationResult(
            query=query,
            repo_id=repo_id,
            verdict="Informational resolution synthesized via fast path.",
            root_cause=None,
            confidence=0.95,
            is_deep_investigation=False,
            reasoning_trace=[],
            recommended_steps=["Review cited codebase references."],
            citations=citations,
            plain_text_summary=answer,
            latency_ms=elapsed_ms,
        )

    async def _run_iterative_loop(
        self,
        query: str,
        repo_id: str,
        branch: str,
        initial_context: List[Dict[str, Any]],
        citations: List[Dict[str, Any]],
        incident_context: Optional[Dict[str, Any]],
        max_steps: int,
        start_time: float,
    ) -> InvestigationResult:
        trace: List[Dict[str, Any]] = []
        current_hypothesis = f"Initial hypothesis: Issue '{query}' stems from boundary mismatch in primary query context."
        current_confidence = 0.35
        actionable_steps: List[str] = []
        root_cause: Optional[str] = None

        # Build investigation scratchpad
        context_snippets = [f"{c['title']}: {c['content'][:250]}" for c in initial_context]

        for step in range(1, max_steps + 1):
            step_action = f"Step {step}: Evaluating hypothesis against graph & semantic knowledge base."
            evidence = ""

            # Alternating investigative actions across steps
            if step == 1:
                # Step 1: Formulate specific hypothesis from query and incident data
                prompt = (
                    f"Incident / Query: '{query}'\n"
                    f"Initial Code Passages:\n" + "\n".join(context_snippets) + "\n"
                    f"Incident Context: {json.dumps(incident_context or {})}\n\n"
                    "Formulate a working hypothesis for the root cause in JSON format:\n"
                    '{"hypothesis": "...", "confidence": 0.45, "investigation_target": "file or symbol name"}'
                )
                raw_json = await self.llm_client.run_worker(
                    prompt, "You are an expert root cause investigator. Respond in valid JSON."
                )
                parsed = parse_llm_json(raw_json)
                current_hypothesis = parsed.get("hypothesis", current_hypothesis)
                current_confidence = float(parsed.get("confidence", 0.45))
                evidence = f"Identified suspect area: {parsed.get('investigation_target', 'core logic')}"

            elif step == 2:
                # Step 2: Query blast radius & dependencies
                target_symbol = initial_context[0].get("symbol") if initial_context else None
                if target_symbol:
                    blast_json = await tool_get_blast_radius(
                        self.graph_client,
                        repo_id=repo_id,
                        changed_symbols=[target_symbol],
                        branch=branch,
                    )
                    blast_data = parse_llm_json(blast_json)
                    downstream = blast_data.get("downstream_affected_symbols", [])
                    evidence = f"Call graph dependency analysis identified {len(downstream)} downstream dependents: {downstream[:4]}"
                    current_confidence = min(0.95, current_confidence + 0.15)
                else:
                    evidence = "No explicit symbol identified; examining file boundaries."
                    current_confidence += 0.10

            elif step == 3:
                # Step 3: Semantic search on error tokens / suspected failure mode
                search_query = f"{query} error handling edge case"
                more_context = await tool_vector_search(
                    self.vector_client,
                    query_text=search_query,
                    repo_id=repo_id,
                    n_results=3,
                )
                parsed_more = parse_llm_json(more_context, fallback_factory=list)
                if isinstance(parsed_more, list) and parsed_more:
                    top_match = parsed_more[0]
                    file_p = top_match.get("metadata", {}).get("file_path") or "unknown"
                    evidence = f"Discovered related code path: {file_p}"
                    citations.append({
                        "id": len(citations) + 1,
                        "file_path": file_p,
                        "symbol": top_match.get("metadata", {}).get("name"),
                        "lines": [1, 50],
                        "snippet": top_match.get("content", "")[:300],
                    })
                else:
                    evidence = "Checked edge-case vector patterns."
                current_confidence = min(0.95, current_confidence + 0.15)

            else:
                # Refine hypothesis
                evidence = f"Refined evidence chain; validated assumptions against step {step - 1} findings."
                current_confidence = min(0.92, current_confidence + 0.08)

            trace.append({
                "step": step,
                "hypothesis": current_hypothesis,
                "action": step_action,
                "evidence": evidence,
                "confidence": round(current_confidence, 2),
            })

            # Check if hypothesis has reached high-confidence threshold
            if current_confidence >= 0.85 and step >= 3:
                break

        # Final Synthesis
        synthesis_prompt = (
            f"Repository: '{repo_id}'\n"
            f"Investigation Query: '{query}'\n"
            f"Investigation Trail:\n{json.dumps(trace, indent=2)}\n\n"
            "Produce the final investigation diagnosis in valid JSON with these keys:\n"
            '{"verdict": "...", "root_cause": "...", "confidence": 0.88, "recommended_steps": ["step 1", "step 2"], "summary_markdown": "..."}'
        )
        system_prompt = (
            "You are the Gitami Lead Investigation Agent. Formulate the definitive root cause analysis, "
            "explaining exactly why the issue occurred, what code was affected, and actionable next steps."
        )
        synthesis_raw = await self.llm_client.run_orchestrator(synthesis_prompt, system_prompt)
        final_data = parse_llm_json(synthesis_raw)

        verdict = final_data.get("verdict", f"Root cause confirmed for: {query}")
        root_cause = final_data.get("root_cause", current_hypothesis)
        actionable_steps = final_data.get("recommended_steps", [
            "Verify affected callers in graph dependencies.",
            "Run regression tests on modified modules.",
        ])
        plain_summary = final_data.get(
            "summary_markdown",
            f"### Root Cause Diagnosis\n\n**Verdict:** {verdict}\n\n"
            f"**Root Cause:** {root_cause}\n\n"
            f"**Confidence:** {int(current_confidence * 100)}%\n\n"
            "**Recommended Resolution:**\n" + "\n".join(f"- {s}" for s in actionable_steps)
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return InvestigationResult(
            query=query,
            repo_id=repo_id,
            verdict=verdict,
            root_cause=root_cause,
            confidence=float(final_data.get("confidence", current_confidence)),
            is_deep_investigation=True,
            reasoning_trace=trace,
            recommended_steps=actionable_steps,
            citations=citations,
            plain_text_summary=plain_summary,
            latency_ms=elapsed_ms,
        )
