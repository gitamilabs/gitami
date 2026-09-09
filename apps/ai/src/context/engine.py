from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.context.authorization import AuthorizationError, ContextAuthorizer, StaticAuthResolver
from src.context.budgeting import ContextBudget, ContextBudgeter
from src.context.contracts import (
    AuthorizedScope,
    ContextItem,
    ContextItemType,
    ContextRequest,
    ContextResult,
    ContextSource,
    ProviderError,
    RetrievalMetadata,
)
from src.context.deduplication import ProviderAwareDeduplicator
from src.context.github_retriever import GitHubRetriever
from src.context.graph_retriever import GraphRetriever
from src.context.provenance import validate_provenance
from src.context.ranking import DeterministicRanker, ScoringConfig
from src.context.semantic_retriever import SemanticRetriever
from src.context.source_retriever import SourceRetriever
from src.graph.client import Neo4jClient
from src.vector.client import VectorKBClient

logger = logging.getLogger(__name__)


def classify_query_intent(query: str) -> str:
    """
    Deterministic lightweight intent classification without an LLM.
    Identifies if query is focused on calls, tests, imports, symbol lookup, or general semantic search.
    """
    q_lower = query.lower()
    if any(k in q_lower for k in ("who calls", "where is called", "callers", "invokes", "call graph", "callees")):
        return "call_graph"
    if any(k in q_lower for k in ("test", "tests", "tested by", "coverage", "spec")):
        return "test"
    if any(k in q_lower for k in ("import", "imports", "depends on", "dependency", "extends", "implements")):
        return "dependency"
    if any(k in q_lower for k in ("def ", "function ", "class ", "interface ", "type ", "signature")):
        return "symbol_lookup"
    return "semantic_search"


class ContextEngine:
    """
    Governed retrieval and context-assembly layer for Gitami.
    Sits between indexed project intelligence (Neo4j, VectorKB, Git, GitHub)
    and all future agents / chat interfaces.
    """

    def __init__(
        self,
        graph_client: Optional[Neo4jClient] = None,
        vector_client: Optional[VectorKBClient] = None,
        authorizer: Optional[ContextAuthorizer] = None,
        scoring_config: Optional[ScoringConfig] = None,
        default_repo_root: Optional[str | Path] = None,
    ):
        self.graph_client = graph_client
        self.vector_client = vector_client
        self.authorizer = authorizer or ContextAuthorizer(graph_client=graph_client)
        self.ranker = DeterministicRanker(config=scoring_config)
        self.deduplicator = ProviderAwareDeduplicator()
        self.budgeter = ContextBudgeter()

        # Initialize providers
        self.graph_retriever = GraphRetriever(client=graph_client) if graph_client else None
        self.semantic_retriever = SemanticRetriever(client=vector_client) if vector_client else None
        self.source_retriever = SourceRetriever(default_repo_root=default_repo_root)
        self.github_retriever = GitHubRetriever(
            vector_client=vector_client, default_repo_root=default_repo_root
        )

    async def retrieve(self, request: ContextRequest) -> ContextResult:
        """
        Main public interface for governed context retrieval.
        Enforces authorization, queries enabled providers in parallel,
        deduplicates, deterministically ranks, bounds by budget, and preserves provenance.
        """
        start_time = time.time()
        durations: Dict[str, float] = {}
        provider_counts: Dict[str, int] = {}
        errors: List[ProviderError] = []

        # 1. Mandatory Authorization Security Boundary
        scope = await self.authorizer.authorize(request)

        # 2. Query Intent Classification
        intent = classify_query_intent(request.query)

        # 3. Parallel Provider Retrieval
        tasks = []
        task_names = []

        # Graph retrieval task
        if request.include_graph and self.graph_retriever:
            tasks.append(
                self.graph_retriever.retrieve(
                    query=request.query,
                    scope=scope,
                    hops=request.hops,
                    limit=request.max_items,
                )
            )
            task_names.append("graph")

        # Semantic retrieval task
        if request.include_semantic and self.semantic_retriever:
            tasks.append(
                self.semantic_retriever.retrieve(
                    query=request.query,
                    scope=scope,
                    limit=request.max_items,
                )
            )
            task_names.append("semantic")

        # GitHub / Git history task
        if request.include_github and self.github_retriever:
            tasks.append(
                self.github_retriever.retrieve(
                    query=request.query,
                    scope=scope,
                    limit=min(5, request.max_items),
                )
            )
            task_names.append("github")

        # Execute providers concurrently with resilience
        all_candidates: List[ContextItem] = []
        if tasks:
            t0 = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for name, res in zip(task_names, results):
                durations[name] = round((time.time() - t0) * 1000, 2)
                if isinstance(res, Exception):
                    logger.error(f"ContextEngine provider '{name}' error: {res}")
                    errors.append(
                        ProviderError(
                            provider=name,
                            error=str(res),
                            recoverable=True,
                        )
                    )
                    provider_counts[name] = 0
                elif isinstance(res, list):
                    provider_counts[name] = len(res)
                    all_candidates.extend(res)

        # 4. Source Retrieval for top candidate symbols/files (if requested)
        if request.include_source and self.source_retriever:
            t_src = time.time()
            source_candidates: List[ContextItem] = []
            seen_source_keys: Set[str] = set()

            # Find entities from graph or semantic results that have line ranges or file paths
            for item in all_candidates[:10]:
                src = item.source
                if src.file_path and src.repository_id in scope.allowed_repo_ids:
                    key = f"{src.repository_id}:{src.file_path}:{src.start_line}"
                    if key in seen_source_keys:
                        continue
                    seen_source_keys.add(key)

                    symbol_name = item.metadata.get("name") or item.title
                    snippet_item = self.source_retriever.retrieve_snippet(
                        repo_id=src.repository_id,
                        file_path=src.file_path,
                        scope=scope,
                        commit_sha=request.commit_sha or src.commit_sha,
                        entity_uid=src.entity_uid,
                        symbol_name=symbol_name,
                        start_line=src.start_line,
                        end_line=src.end_line,
                    )
                    if snippet_item:
                        source_candidates.append(snippet_item)

            durations["source"] = round((time.time() - t_src) * 1000, 2)
            provider_counts["source"] = len(source_candidates)
            all_candidates.extend(source_candidates)

        total_candidates = len(all_candidates)

        # 5. Provider-Aware Deduplication & Complementary Merging
        deduped_candidates, dedup_count = self.deduplicator.deduplicate(all_candidates)

        # 6. Deterministic Ranking
        ranked_items = self.ranker.rank(deduped_candidates, request.query)

        # 7. Context Budgeting (max_items, max_tokens)
        budget = ContextBudget(max_items=request.max_items, max_tokens=request.max_tokens)
        final_items, truncated = self.budgeter.apply_budget(ranked_items, budget)

        # 8. Provenance Validation & Source Extraction
        valid_items: List[ContextItem] = []
        sources: List[ContextSource] = []
        for item in final_items:
            validate_provenance(item)
            valid_items.append(item)
            sources.append(item.source)

        durations["total"] = round((time.time() - start_time) * 1000, 2)

        metadata = RetrievalMetadata(
            durations_ms=durations,
            candidates_per_provider=provider_counts,
            deduplicated_count=dedup_count,
            budget_applied=truncated,
            query_intent=intent,
        )

        return ContextResult(
            query=request.query,
            project_id=request.project_id,
            items=valid_items,
            sources=sources,
            total_candidates=total_candidates,
            returned_items=len(valid_items),
            truncated=truncated,
            retrieval_metadata=metadata,
            errors=errors,
        )

    async def retrieve_for_entity(
        self,
        project_id: str,
        repo_id: str,
        entity_uid: str,
        hops: int = 1,
        max_items: int = 20,
    ) -> ContextResult:
        """Convenience method to retrieve context centered on an explicit entity UID."""
        req = ContextRequest(
            project_id=project_id,
            query=entity_uid,
            repository_ids=[repo_id],
            hops=hops,
            max_items=max_items,
            include_graph=True,
            include_semantic=False,
            include_source=True,
            include_github=False,
        )
        return await self.retrieve(req)
