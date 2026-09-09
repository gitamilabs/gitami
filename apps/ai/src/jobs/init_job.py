import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from src.graph.client import Neo4jClient
from src.vector.client import VectorKBClient
from src.parsing.models import ParseResult
from src.indexer.pipeline import RepositoryIndexer
from src.indexer.contracts import IndexJobType

logger = logging.getLogger(__name__)


@dataclass
class InitResult:
    status: str
    symbols_count: int = 0
    edges_count: int = 0
    vector_entries_count: int = 0
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def total_symbols(self) -> int:
        return self.symbols_count

    @property
    def total_files(self) -> int:
        return self.vector_entries_count

    @property
    def total_packages(self) -> int:
        return 0


async def run_init_job(
    repo_id: str,
    branch: str,
    repo_dir: Optional[str | Path] = None,
    parse_results: Optional[List[ParseResult]] = None,
    client: Optional[Neo4jClient] = None,
    vector_client: Optional[VectorKBClient] = None,
    extraction_mode: str = "fast",
) -> InitResult:
    """
    Canonical V1 Repository Initialization.
    Delegates directly to the unified RepositoryIndexer pipeline.
    """
    start_time = time.time()
    try:
        indexer = RepositoryIndexer(
            graph_client=client,
            vector_client=vector_client,
        )

        target_dir = Path(repo_dir) if repo_dir else Path(".")
        job, state, report = await indexer.run(
            repo_dir=target_dir,
            repo_id=repo_id,
            target_commit_sha=branch or "HEAD",
            branch=branch or "main",
            job_type=IndexJobType.INITIAL,
            validate_only=(client is None),
        )

        duration = round(time.time() - start_time, 3)

        if not report.is_valid:
            return InitResult(
                status="ERROR",
                errors=report.fatal_errors,
                duration_seconds=duration,
            )

        return InitResult(
            status="SUCCESS",
            symbols_count=job.stats.entities_created,
            edges_count=job.stats.relationships_created,
            vector_entries_count=job.stats.files_parsed,
            duration_seconds=duration,
        )
    except Exception as e:
        logger.error(f"Initialization failure: {e}", exc_info=True)
        return InitResult(status="ERROR", errors=[str(e)])
