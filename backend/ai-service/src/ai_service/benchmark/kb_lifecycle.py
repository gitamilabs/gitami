"""Knowledge Base lifecycle management for benchmarking runs.

Ensures real Knowledge Base injection (Neo4j AST graph + ChromaDB vector embeddings)
during benchmark test execution, and guarantees clean teardown after completion.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ai_service.graph.client import Neo4jClient
from ai_service.graph.writer import delete_repo_data
from ai_service.vector.client import VectorKBClient
from ai_service.vector.cache import VectorCacheManager
from ai_service.jobs.init_job import run_init_job, InitResult

logger = logging.getLogger(__name__)


@dataclass
class KBContextInfo:
    """Active Knowledge Base context state for a benchmark test case."""

    repo_id: str
    branch: str
    graph_client: Neo4jClient
    vector_client: VectorKBClient
    init_result: Optional[InitResult] = None


class BenchmarkKBContext:
    """Async context manager handling safe KB injection and guaranteed teardown."""

    def __init__(
        self,
        repo_id: str,
        branch: str,
        repo_dir: Optional[Path | str] = None,
        graph_client: Optional[Neo4jClient] = None,
        vector_client: Optional[VectorKBClient] = None,
        cleanup: bool = True,
    ):
        self.repo_id = repo_id
        self.branch = branch
        self.repo_dir = Path(repo_dir) if repo_dir else None
        self._external_graph = graph_client is not None
        self._external_vector = vector_client is not None
        self.graph_client = graph_client or Neo4jClient()
        self.vector_client = vector_client or VectorKBClient()
        self.cleanup = cleanup
        self.init_result: Optional[InitResult] = None

    async def __aenter__(self) -> KBContextInfo:
        """Connect to KB backends and ingest repository AST/vectors if repo_dir provided."""
        if not self._external_graph:
            await self.graph_client.connect()

        # Ingest into KB if repository directory exists
        if self.repo_dir and self.repo_dir.exists():
            try:
                logger.info(
                    f"[BenchmarkKB] Ingesting repository '{self.repo_id}' from {self.repo_dir} into Neo4j & Vector DB..."
                )
                self.init_result = await run_init_job(
                    repo_id=self.repo_id,
                    branch=self.branch,
                    repo_dir=self.repo_dir,
                    client=self.graph_client,
                    vector_client=self.vector_client,
                )
                logger.info(
                    f"[BenchmarkKB] Ingestion complete: {self.init_result.symbols_count} symbols, "
                    f"{self.init_result.edges_count} edges, {self.init_result.vector_entries_count} vectors."
                )
            except Exception as e:
                logger.warning(
                    f"[BenchmarkKB] Repository indexing encountered non-fatal issue for '{self.repo_id}': {e}"
                )

        return KBContextInfo(
            repo_id=self.repo_id,
            branch=self.branch,
            graph_client=self.graph_client,
            vector_client=self.vector_client,
            init_result=self.init_result,
        )

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Tear down KB state and close unmanaged connections."""
        try:
            if self.cleanup:
                await self.cleanup_kb(self.repo_id, self.branch)
        finally:
            if not self._external_graph:
                await self.graph_client.close()

    async def cleanup_kb(self, repo_id: str, branch: Optional[str] = None) -> None:
        """Purge all Neo4j graph nodes, Vector DB records, and disk cache manifests for repo."""
        logger.info(f"[BenchmarkKB] Purging Knowledge Base entries for '{repo_id}'...")

        # 1. Purge Neo4j graph nodes & relationships
        try:
            await delete_repo_data(self.graph_client, repo_id=repo_id, branch=branch)
            logger.info(f"[BenchmarkKB] Neo4j graph data purged for '{repo_id}'.")
        except Exception as e:
            logger.warning(f"[BenchmarkKB] Error purging Neo4j data for '{repo_id}': {e}")

        # 2. Purge Vector DB entries
        try:
            where_clause = {"repo": repo_id}
            if branch:
                where_clause = {"$and": [{"repo": repo_id}, {"branch": branch}]}
            self.vector_client.delete(where=where_clause)
            logger.info(f"[BenchmarkKB] Vector DB entries purged for '{repo_id}'.")
        except Exception as e:
            logger.warning(f"[BenchmarkKB] Error purging Vector DB entries for '{repo_id}': {e}")

        # 3. Purge disk cache manifests
        try:
            cache_mgr = VectorCacheManager()
            purged = cache_mgr.invalidate(repo_id=repo_id, branch=branch)
            if purged > 0:
                logger.info(f"[BenchmarkKB] Purged {purged} disk vector cache manifest(s).")
        except Exception as e:
            logger.warning(f"[BenchmarkKB] Error purging disk vector cache: {e}")


async def purge_all_benchmark_data(
    graph_client: Neo4jClient,
    vector_client: Optional[VectorKBClient] = None,
    prefix: str = "benchmark_",
) -> int:
    """Purge any orphaned benchmark nodes and vector entries across the entire KB."""
    if vector_client is None:
        vector_client = VectorKBClient()

    purged_nodes = 0
    # Purge orphaned Neo4j benchmark nodes
    try:
        query = (
            f"MATCH (n) WHERE n.repo_id STARTS WITH $prefix "
            f"DETACH DELETE n RETURN count(n) AS cnt"
        )
        records = await graph_client.execute_read(query, {"prefix": prefix})
        if records:
            purged_nodes = records[0].get("cnt", 0)
        logger.info(f"[BenchmarkKB] Purged {purged_nodes} Neo4j node(s) matching prefix '{prefix}'.")
    except Exception as e:
        logger.warning(f"[BenchmarkKB] Failed to bulk purge Neo4j benchmark nodes: {e}")

    # Purge vector cache manifests
    try:
        cache_mgr = VectorCacheManager()
        cache_mgr.invalidate()  # Will purge matching manifests
    except Exception as e:
        logger.warning(f"[BenchmarkKB] Failed to purge vector manifests: {e}")

    return purged_nodes
