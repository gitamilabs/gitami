import time
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from src.graph.client import Neo4jClient
from src.graph.resolver import resolve_repo_imports
from src.indexer.contracts import (
    IndexJob,
    IndexJobStatus,
    IndexJobType,
    RepositoryIndexState,
    IndexStateStatus,
    IndexingStats,
    ValidationReport,
)
from src.indexer.snapshot import RepositorySnapshot
from src.indexer.discovery import FileDiscovery
from src.indexer.graph_indexer import GraphIndexer, PARSER_VERSION, SCHEMA_VERSION
from src.indexer.validator import IndexValidator
from src.parsing.parser import CodeParser
from src.parsing.models import ParseResult
from src.vector.client import VectorKBClient

logger = logging.getLogger(__name__)


class RepositoryIndexer:
    """
    Canonical V1 Repository Indexer coordinating deterministic code snapshotting,
    AST analysis, Neo4j graph indexing, and index validation.
    """

    def __init__(
        self,
        graph_client: Optional[Neo4jClient] = None,
        vector_client: Optional[VectorKBClient] = None,
        parser: Optional[CodeParser] = None,
        discovery: Optional[FileDiscovery] = None,
        validator: Optional[IndexValidator] = None,
    ):
        self.graph_client = graph_client
        self.vector_client = vector_client
        self.parser = parser or CodeParser()
        self.discovery = discovery or FileDiscovery()
        self.validator = validator or IndexValidator()

    async def run(
        self,
        repo_dir: str | Path,
        repo_id: str,
        target_commit_sha: str = "HEAD",
        branch: str = "main",
        project_id: str = "default",
        job_type: IndexJobType = IndexJobType.INITIAL,
        validate_only: bool = False,
    ) -> Tuple[IndexJob, RepositoryIndexState, ValidationReport]:
        """
        Execute the canonical indexing pipeline against an explicit commit SHA.
        
        Returns:
            Tuple[IndexJob, RepositoryIndexState, ValidationReport]
        """
        start_time = time.time()
        job = IndexJob(
            project_id=project_id,
            repository_id=repo_id,
            type=job_type,
            target_commit_sha=target_commit_sha,
            branch=branch,
        )
        job.transition_to(IndexJobStatus.RUNNING, stage="INITIALIZING")

        stats = IndexingStats()
        fatal_errors: List[str] = []
        warnings: List[str] = []

        owns_graph_client = False
        if self.graph_client is None and not validate_only:
            self.graph_client = Neo4jClient()
            try:
                await self.graph_client.connect()
                owns_graph_client = True
            except Exception as e:
                logger.warning(f"Could not connect to Neo4j, running in offline/dry mode: {e}")

        try:
            # ── 1. Repository Snapshot ──────────────────────────────────────────
            job.stage = "SNAPSHOT"
            job.progress = 10
            with RepositorySnapshot(repo_dir, target_commit_sha) as snapshot:
                resolved_sha = snapshot.resolved_commit_sha
                job.target_commit_sha = resolved_sha

                # ── 2. File Discovery ───────────────────────────────────────────
                job.stage = "DISCOVERY"
                job.progress = 25
                discovered_files, skipped_count = self.discovery.discover_files(snapshot)
                stats.files_discovered = len(discovered_files)
                stats.files_skipped = skipped_count

                # ── 3. Code Analysis (AST) ──────────────────────────────────────
                job.stage = "AST_ANALYSIS"
                job.progress = 45
                parse_results: List[ParseResult] = []

                for df in discovered_files:
                    try:
                        code_bytes = snapshot.read_bytes(df.file_path)
                        pr = self.parser.parse_code_bytes(code_bytes, df.file_path)
                        if pr:
                            parse_results.append(pr)
                            stats.files_parsed += 1
                            if pr.errors:
                                stats.parse_errors += len(pr.errors)
                                warnings.extend([f"{df.file_path}: {err}" for err in pr.errors])
                        else:
                            stats.files_skipped += 1
                    except Exception as parse_err:
                        stats.parse_errors += 1
                        warnings.append(f"Failed to parse {df.file_path}: {parse_err}")

                # ── 4. Graph Indexing (Neo4j) ───────────────────────────────────
                if not validate_only and self.graph_client:
                    job.stage = "GRAPH_INDEXING"
                    job.progress = 70
                    graph_indexer = GraphIndexer(self.graph_client)

                    await graph_indexer.ensure_v1_schema()
                    await graph_indexer.index_repository_node(
                        project_id=project_id,
                        repo_id=repo_id,
                        commit_sha=resolved_sha,
                        branch=branch,
                    )

                    dirs_count, files_count = await graph_indexer.index_directories_and_files(
                        repo_id=repo_id,
                        commit_sha=resolved_sha,
                        branch=branch,
                        parse_results=parse_results,
                    )

                    symbols_count = await graph_indexer.index_symbols_and_entities(
                        repo_id=repo_id,
                        commit_sha=resolved_sha,
                        branch=branch,
                        parse_results=parse_results,
                    )

                    heritage_count = await graph_indexer.index_heritage(
                        repo_id=repo_id,
                        commit_sha=resolved_sha,
                        parse_results=parse_results,
                    )

                    calls_count, imports_count = await graph_indexer.index_calls_and_imports(
                        repo_id=repo_id,
                        commit_sha=resolved_sha,
                        parse_results=parse_results,
                    )

                    # Post-processing import resolution
                    try:
                        await resolve_repo_imports(self.graph_client, repo_id=repo_id, branch=branch)
                    except Exception as res_err:
                        warnings.append(f"Import resolution notice: {res_err}")

                    stats.entities_created = 1 + dirs_count + files_count + symbols_count
                    stats.relationships_created = (
                        dirs_count + files_count + symbols_count + heritage_count + calls_count + imports_count
                    )
                else:
                    # Synthetic count calculation for validation/dry runs
                    extracted_symbols = sum(len(pr.symbols) for pr in parse_results)
                    stats.entities_created = len(parse_results) + extracted_symbols
                    stats.relationships_created = sum(
                        len(pr.calls) + len(pr.imports) + len(pr.heritage) for pr in parse_results
                    )

                # ── 5. Semantic Indexing (Optional / Decoupled) ─────────────────
                if self.vector_client:
                    job.stage = "SEMANTIC_INDEXING"
                    job.progress = 85
                    try:
                        vector_entries = []
                        for pr in parse_results:
                            for sym in pr.symbols:
                                vector_entries.append({
                                    "repo": repo_id,
                                    "branch": branch,
                                    "file_path": sym.file_path,
                                    "symbol": sym.name,
                                    "start_line": sym.start_line,
                                    "signature": sym.signature,
                                    "description": sym.docstring or f"{sym.kind} {sym.name} in {sym.file_path}",
                                    "code_body": sym.code_body,
                                    "commit_hash": resolved_sha,
                                })
                        if vector_entries:
                            self.vector_client.add_code_entries_batch(vector_entries)
                    except Exception as vec_err:
                        warnings.append(f"Semantic vector indexing warning (non-fatal): {vec_err}")

        except Exception as fatal_e:
            fatal_errors.append(f"Fatal indexing pipeline failure: {str(fatal_e)}")

        stats.duration_seconds = round(time.time() - start_time, 3)
        job.stats = stats

        # ── 6. Validation ───────────────────────────────────────────────────────
        job.stage = "VALIDATION"
        job.progress = 95
        report = self.validator.validate(
            repo_id=repo_id,
            commit_sha=job.target_commit_sha,
            stats=stats,
            fatal_errors=fatal_errors,
            warnings=warnings,
        )

        # ── 7. State Transition ─────────────────────────────────────────────────
        if report.is_valid:
            job.transition_to(IndexJobStatus.COMPLETED, stage="COMPLETED")
            state = RepositoryIndexState(
                repository_id=repo_id,
                branch=branch,
                indexed_commit_sha=job.target_commit_sha,
                index_version="v1",
                schema_version=SCHEMA_VERSION,
                parser_version=PARSER_VERSION,
                status=IndexStateStatus.READY,
                stats=stats.model_dump(),
            )
        else:
            err_summary = "; ".join(report.fatal_errors) or "Validation failed"
            job.transition_to(IndexJobStatus.FAILED, stage="FAILED", error=err_summary)
            state = RepositoryIndexState(
                repository_id=repo_id,
                branch=branch,
                indexed_commit_sha=job.target_commit_sha,
                index_version="v1",
                schema_version=SCHEMA_VERSION,
                parser_version=PARSER_VERSION,
                status=IndexStateStatus.FAILED,
                stats=stats.model_dump(),
            )

        if owns_graph_client and self.graph_client:
            try:
                await self.graph_client.close()
            except Exception:
                pass

        return job, state, report
