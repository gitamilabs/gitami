import time
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from git import Repo

from src.graph.client import Neo4jClient
from src.graph.resolver import resolve_repo_imports
from src.indexer.contracts import (
    IndexJob,
    IndexJobStatus,
    IndexJobType,
    RepositoryIndexState,
    IndexStateStatus,
    IndexingStats,
    IncrementalIndexingStats,
    ValidationReport,
)
from src.indexer.differ import GitDiffer
from src.indexer.snapshot import RepositorySnapshot
from src.indexer.discovery import FileDiscovery
from src.indexer.graph_indexer import GraphIndexer, PARSER_VERSION, SCHEMA_VERSION
from src.indexer.validator import IndexValidator
from src.parsing.parser import CodeParser
from src.parsing.models import ParseResult
from src.vector.client import VectorKBClient
from src.vector.cleaner import clean_code_symbol, filter_repetitive_boilerplate

logger = logging.getLogger(__name__)

_indexer_locks: Dict[Tuple[str, str], asyncio.Lock] = {}


def _get_repo_lock(repo_id: str, branch: str) -> asyncio.Lock:
    key = (repo_id, branch)
    if key not in _indexer_locks:
        _indexer_locks[key] = asyncio.Lock()
    return _indexer_locks[key]


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
        differ: Optional[GitDiffer] = None,
    ):
        self.graph_client = graph_client
        self.vector_client = vector_client
        self.parser = parser or CodeParser()
        self.discovery = discovery or FileDiscovery()
        self.validator = validator or IndexValidator()
        self.differ = differ or GitDiffer(discovery=self.discovery)

    async def run(
        self,
        repo_dir: Optional[str | Path] = None,
        repo_id: str = "default",
        target_commit_sha: str = "HEAD",
        branch: str = "main",
        project_id: str = "default",
        team_id: Optional[str] = None,
        job_type: IndexJobType = IndexJobType.INITIAL,
        validate_only: bool = False,
        stage_callback: Optional[Any] = None,
        parse_results: Optional[List[ParseResult]] = None,
    ) -> Tuple[IndexJob, RepositoryIndexState, ValidationReport]:
        """
        Execute the canonical full indexing pipeline against an explicit commit SHA.
        Supports both on-disk git repository paths and pre-parsed in-memory results
        (e.g., from zero-disk tarball streaming).
        
        Returns:
            Tuple[IndexJob, RepositoryIndexState, ValidationReport]
        """
        async with _get_repo_lock(repo_id, branch):
            return await self._run(
                repo_dir=repo_dir,
                repo_id=repo_id,
                target_commit_sha=target_commit_sha,
                branch=branch,
                project_id=project_id,
                team_id=team_id,
                job_type=job_type,
                validate_only=validate_only,
                stage_callback=stage_callback,
                parse_results=parse_results,
            )

    async def _run(
        self,
        repo_dir: Optional[str | Path] = None,
        repo_id: str = "default",
        target_commit_sha: str = "HEAD",
        branch: str = "main",
        project_id: str = "default",
        team_id: Optional[str] = None,
        job_type: IndexJobType = IndexJobType.INITIAL,
        validate_only: bool = False,
        stage_callback: Optional[Any] = None,
        parse_results: Optional[List[ParseResult]] = None,
    ) -> Tuple[IndexJob, RepositoryIndexState, ValidationReport]:
        start_time = time.time()
        job = IndexJob(
            project_id=project_id,
            team_id=team_id,
            repository_id=repo_id,
            type=job_type,
            target_commit_sha=target_commit_sha,
            branch=branch,
        )
        job.transition_to(IndexJobStatus.RUNNING, stage="INITIALIZING")

        stats = IndexingStats()
        fatal_errors: List[str] = []
        warnings: List[str] = []

        async def emit_stage(stage_name: str, status_name: str = "RUNNING", stage_stats: Optional[Dict[str, Any]] = None, stage_error: Optional[str] = None):
            if stage_callback:
                try:
                    s_data = stage_stats if stage_stats is not None else stats.model_dump()
                    res = stage_callback(stage_name, status_name, s_data, stage_error)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as cb_err:
                    logger.debug(f"Stage callback error: {cb_err}")

        owns_graph_client = False
        if self.graph_client is None and not validate_only:
            self.graph_client = Neo4jClient()
            try:
                await self.graph_client.connect()
                owns_graph_client = True
            except Exception as e:
                logger.warning(f"Could not connect to Neo4j, running in offline/dry mode: {e}")

        try:
            # ── 1. Repository Snapshot & Code Analysis ──────────────────────────
            job.stage = "SNAPSHOT"
            job.progress = 10
            await emit_stage("SNAPSHOT", "RUNNING")

            if parse_results is not None:
                # Mode A: Pre-parsed in-memory results (e.g. tarball streamer)
                resolved_sha = (
                    target_commit_sha
                    if target_commit_sha not in ("HEAD", "main", "master", "trunk", "dev") and target_commit_sha
                    else "synthetic-commit-0000000000000000000000000000000000000000"
                )
                job.target_commit_sha = resolved_sha

                job.stage = "DISCOVERY"
                job.progress = 25
                stats.files_discovered = len(parse_results)
                stats.files_skipped = 0
                await emit_stage("DISCOVERY", "RUNNING", {"files_discovered": len(parse_results), "files_skipped": 0})

                job.stage = "AST_ANALYSIS"
                job.progress = 45
                stats.files_parsed = len(parse_results)
                for pr in parse_results:
                    if pr.errors:
                        stats.parse_errors += len(pr.errors)
                        warnings.extend([f"{pr.file_path}: {err}" for err in pr.errors])
                await emit_stage("AST_ANALYSIS", "RUNNING", {"files_parsed": stats.files_parsed, "parse_errors": stats.parse_errors})
            else:
                # Mode B: On-disk repository snapshot
                if not repo_dir:
                    raise ValueError("Either 'repo_dir' or 'parse_results' must be provided for indexing.")
                with RepositorySnapshot(repo_dir, target_commit_sha) as snapshot:
                    resolved_sha = snapshot.resolved_commit_sha
                    job.target_commit_sha = resolved_sha

                    job.stage = "DISCOVERY"
                    job.progress = 25
                    await emit_stage("DISCOVERY", "RUNNING")
                    discovered_files, skipped_count = self.discovery.discover_files(snapshot)
                    stats.files_discovered = len(discovered_files)
                    stats.files_skipped = skipped_count
                    await emit_stage("DISCOVERY", "RUNNING", {"files_discovered": len(discovered_files), "files_skipped": skipped_count})

                    job.stage = "AST_ANALYSIS"
                    job.progress = 45
                    await emit_stage("AST_ANALYSIS", "RUNNING")
                    parse_results = []

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
                    await emit_stage("AST_ANALYSIS", "RUNNING", {"files_parsed": stats.files_parsed, "parse_errors": stats.parse_errors})

            # ── 4. Graph Indexing (Neo4j) ───────────────────────────────────
            if not validate_only and self.graph_client:
                job.stage = "GRAPH_INDEXING"
                job.progress = 70
                await emit_stage("GRAPH_INDEXING", "RUNNING")
                graph_indexer = GraphIndexer(self.graph_client)

                await graph_indexer.ensure_v1_schema()
                await graph_indexer.index_repository_node(
                    project_id=project_id,
                    repo_id=repo_id,
                    commit_sha=resolved_sha,
                    branch=branch,
                    team_id=team_id,
                )

                dirs_count, files_count = await graph_indexer.index_directories_and_files(
                    repo_id=repo_id,
                    commit_sha=resolved_sha,
                    branch=branch,
                    parse_results=parse_results,
                    project_id=project_id,
                    team_id=team_id,
                )

                symbols_count = await graph_indexer.index_symbols_and_entities(
                    repo_id=repo_id,
                    commit_sha=resolved_sha,
                    branch=branch,
                    parse_results=parse_results,
                    project_id=project_id,
                    team_id=team_id,
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
                    branch=branch,
                )

                tests_count = await graph_indexer.index_tests(
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
                    dirs_count + files_count + symbols_count + heritage_count + calls_count + imports_count + tests_count
                )
            else:
                # Synthetic count calculation for validation/dry runs
                extracted_symbols = sum(len(pr.symbols) for pr in parse_results)
                stats.entities_created = len(parse_results) + extracted_symbols
                stats.relationships_created = sum(
                    len(pr.calls) + len(pr.imports) + len(pr.heritage) for pr in parse_results
                )

            await emit_stage("GRAPH_INDEXING", "RUNNING", {"entities_created": stats.entities_created, "relationships_created": stats.relationships_created})

            # ── 5. Semantic Indexing (Optional / Decoupled) ─────────────────
            if self.vector_client:
                job.stage = "SEMANTIC_INDEXING"
                job.progress = 85
                await emit_stage("SEMANTIC_INDEXING", "RUNNING")
                try:
                    raw_symbols = []
                    for pr in parse_results:
                        raw_symbols.extend(pr.symbols)

                    cleaned_symbols = []
                    for sym in raw_symbols:
                        cs = clean_code_symbol(sym)
                        if cs is not None:
                            cleaned_symbols.append(cs)

                    curated_symbols = filter_repetitive_boilerplate(cleaned_symbols)
                    vector_entries = []
                    for sym in curated_symbols:
                        vector_entries.append({
                            "project_id": project_id,
                            "team_id": team_id or "",
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
        await emit_stage("VALIDATION", "RUNNING")
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
            await emit_stage("COMPLETED", "COMPLETED", stats.model_dump())
            state = RepositoryIndexState(
                repository_id=repo_id,
                branch=branch,
                indexed_commit_sha=job.target_commit_sha,
                index_version="v1",
                schema_version=SCHEMA_VERSION,
                parser_version=PARSER_VERSION,
                status=IndexStateStatus.READY,
                generation=1,
                last_successful_index_at=datetime.now(timezone.utc),
                stats=stats.model_dump(),
            )
        else:
            err_summary = "; ".join(report.fatal_errors) or "Validation failed"
            job.transition_to(IndexJobStatus.FAILED, stage="FAILED", error=err_summary)
            await emit_stage("FAILED", "FAILED", stats.model_dump(), err_summary)
            state = RepositoryIndexState(
                repository_id=repo_id,
                branch=branch,
                indexed_commit_sha=job.target_commit_sha,
                index_version="v1",
                schema_version=SCHEMA_VERSION,
                parser_version=PARSER_VERSION,
                status=IndexStateStatus.FAILED,
                generation=1,
                indexing_error=err_summary,
                stats=stats.model_dump(),
            )

        if owns_graph_client and self.graph_client:
            try:
                await self.graph_client.close()
            except Exception:
                pass

        return job, state, report

    async def run_incremental(
        self,
        repo_dir: str | Path,
        repo_id: str,
        target_commit_sha: str = "HEAD",
        base_commit_sha: Optional[str] = None,
        branch: str = "main",
        project_id: str = "default",
        current_state: Optional[RepositoryIndexState] = None,
        validate_only: bool = False,
    ) -> Tuple[IndexJob, RepositoryIndexState, ValidationReport]:
        """
        Execute incremental repository indexing between base commit and target commit.
        Falls back safely to full rebuild when safety criteria are not satisfied.
        """
        async with _get_repo_lock(repo_id, branch):
            start_time = time.time()
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

            # ── 1. Resolve target commit SHA ─────────────────────────────────────
            try:
                with RepositorySnapshot(repo_dir, target_commit_sha) as snapshot:
                    resolved_target_sha = snapshot.resolved_commit_sha
            except Exception as snap_err:
                fatal_msg = f"Failed to resolve target commit '{target_commit_sha}': {snap_err}"
                logger.error(fatal_msg)
                job = IndexJob(
                    project_id=project_id,
                    repository_id=repo_id,
                    type=IndexJobType.INCREMENTAL,
                    target_commit_sha=target_commit_sha,
                    branch=branch,
                )
                job.transition_to(IndexJobStatus.FAILED, stage="SNAPSHOT", error=fatal_msg)
                st = current_state or RepositoryIndexState(
                    repository_id=repo_id,
                    branch=branch,
                    indexed_commit_sha=target_commit_sha,
                    status=IndexStateStatus.FAILED,
                    indexing_error=fatal_msg,
                )
                rep = ValidationReport(
                    is_valid=False,
                    repository_exists=True,
                    commit_exists=False,
                    files_discovered=0,
                    files_parsed=0,
                    entities_created=0,
                    relationships_created=0,
                    fatal_errors=[fatal_msg],
                )
                if owns_graph_client and self.graph_client:
                    try:
                        await self.graph_client.close()
                    except Exception:
                        pass
                return job, st, rep

            # ── 2. Determine base commit SHA ─────────────────────────────────────
            resolved_base_sha = base_commit_sha
            if not resolved_base_sha:
                if current_state and current_state.indexed_commit_sha:
                    resolved_base_sha = current_state.indexed_commit_sha
                elif self.graph_client:
                    graph_indexer = GraphIndexer(self.graph_client)
                    db_state = await graph_indexer.get_repository_state(repo_id)
                    if db_state and db_state.get("latest_commit_sha"):
                        resolved_base_sha = db_state["latest_commit_sha"]

            if not resolved_base_sha:
                logger.info("No base commit available for incremental index. Falling back to full rebuild.")
                if owns_graph_client and self.graph_client:
                    try:
                        await self.graph_client.close()
                        self.graph_client = None
                    except Exception:
                        pass
                return await self._run(
                    repo_dir=repo_dir,
                    repo_id=repo_id,
                    target_commit_sha=resolved_target_sha,
                    branch=branch,
                    project_id=project_id,
                    job_type=IndexJobType.FULL_REINDEX,
                    validate_only=validate_only,
                )

            # ── 3. Validate previous state invariants ────────────────────────────
            if current_state:
                if current_state.status != IndexStateStatus.READY:
                    logger.warning(
                        f"Previous index state is '{current_state.status}'. Falling back to full rebuild."
                    )
                    if owns_graph_client and self.graph_client:
                        try:
                            await self.graph_client.close()
                            self.graph_client = None
                        except Exception:
                            pass
                    return await self._run(
                        repo_dir=repo_dir,
                        repo_id=repo_id,
                        target_commit_sha=resolved_target_sha,
                        branch=branch,
                        project_id=project_id,
                        job_type=IndexJobType.FULL_REINDEX,
                        validate_only=validate_only,
                    )
                if (
                    current_state.schema_version != SCHEMA_VERSION
                    or current_state.parser_version != PARSER_VERSION
                ):
                    logger.warning(
                        "Schema or parser version incompatibility detected. Falling back to full rebuild."
                    )
                    if owns_graph_client and self.graph_client:
                        try:
                            await self.graph_client.close()
                            self.graph_client = None
                        except Exception:
                            pass
                    return await self._run(
                        repo_dir=repo_dir,
                        repo_id=repo_id,
                        target_commit_sha=resolved_target_sha,
                        branch=branch,
                        project_id=project_id,
                        job_type=IndexJobType.FULL_REINDEX,
                        validate_only=validate_only,
                    )

            # ── 4. Git diff calculation & ancestry validation ────────────────────
            diff_res = self.differ.compute_diff(repo_dir, resolved_base_sha, resolved_target_sha)

            # Check ancestry and out-of-order execution
            if not diff_res.is_ancestor:
                # Check if target is actually an ancestor of base (out-of-order backwards roll)
                try:
                    repo = Repo(repo_dir, search_parent_directories=True)
                    try:
                        c_target = repo.commit(resolved_target_sha)
                        c_base = repo.commit(resolved_base_sha)
                        if repo.is_ancestor(c_target, c_base):
                            err_msg = (
                                f"Out-of-order protection: target commit '{resolved_target_sha}' is older than "
                                f"currently indexed commit '{resolved_base_sha}'."
                            )
                            logger.error(err_msg)
                            job = IndexJob(
                                project_id=project_id,
                                repository_id=repo_id,
                                type=IndexJobType.INCREMENTAL,
                                base_commit_sha=resolved_base_sha,
                                target_commit_sha=resolved_target_sha,
                                branch=branch,
                            )
                            job.transition_to(IndexJobStatus.FAILED, stage="ANCESTRY_VALIDATION", error=err_msg)
                            st = current_state or RepositoryIndexState(
                                repository_id=repo_id,
                                branch=branch,
                                indexed_commit_sha=resolved_base_sha,
                                status=IndexStateStatus.READY,
                            )
                            st.indexing_error = err_msg
                            rep = ValidationReport(
                                is_valid=False,
                                repository_exists=True,
                                commit_exists=True,
                                files_discovered=0,
                                files_parsed=0,
                                entities_created=0,
                                relationships_created=0,
                                fatal_errors=[err_msg],
                            )
                            if owns_graph_client and self.graph_client:
                                try:
                                    await self.graph_client.close()
                                except Exception:
                                    pass
                            return job, st, rep
                    finally:
                        repo.close()
                except Exception as anc_err:
                    logger.warning(f"Notice checking ancestor relationship: {anc_err}")

                # Base not ancestor of target and not newer -> branch diverged or rebased.
                logger.warning(
                    f"Base commit '{resolved_base_sha}' is not an ancestor of '{resolved_target_sha}'. "
                    "Falling back to full rebuild."
                )
                if owns_graph_client and self.graph_client:
                    try:
                        await self.graph_client.close()
                        self.graph_client = None
                    except Exception:
                        pass
                return await self._run(
                    repo_dir=repo_dir,
                    repo_id=repo_id,
                    target_commit_sha=resolved_target_sha,
                    branch=branch,
                    project_id=project_id,
                    job_type=IndexJobType.FULL_REINDEX,
                    validate_only=validate_only,
                )

            # Safety threshold check
            if not diff_res.is_safe_incremental:
                logger.info(
                    f"Incremental indexing unsafe ({diff_res.fallback_reason}). Falling back to full rebuild."
                )
                if owns_graph_client and self.graph_client:
                    try:
                        await self.graph_client.close()
                        self.graph_client = None
                    except Exception:
                        pass
                return await self._run(
                    repo_dir=repo_dir,
                    repo_id=repo_id,
                    target_commit_sha=resolved_target_sha,
                    branch=branch,
                    project_id=project_id,
                    job_type=IndexJobType.FULL_REINDEX,
                    validate_only=validate_only,
                )

            # Trivial idempotency check (same commit)
            if resolved_base_sha == resolved_target_sha:
                logger.info(f"Target commit {resolved_target_sha} == base commit {resolved_base_sha}. Idempotent no-op.")
                job = IndexJob(
                    project_id=project_id,
                    repository_id=repo_id,
                    type=IndexJobType.INCREMENTAL,
                    base_commit_sha=resolved_base_sha,
                    target_commit_sha=resolved_target_sha,
                    branch=branch,
                )
                job.transition_to(IndexJobStatus.RUNNING, stage="INITIALIZING")
                job.transition_to(IndexJobStatus.COMPLETED, stage="COMPLETED")
                st = current_state or RepositoryIndexState(
                    repository_id=repo_id,
                    branch=branch,
                    indexed_commit_sha=resolved_target_sha,
                    previous_commit_sha=resolved_base_sha,
                    status=IndexStateStatus.READY,
                )
                rep = ValidationReport(
                    is_valid=True,
                    repository_exists=True,
                    commit_exists=True,
                    files_discovered=0,
                    files_parsed=0,
                    entities_created=0,
                    relationships_created=0,
                )
                if owns_graph_client and self.graph_client:
                    try:
                        await self.graph_client.close()
                    except Exception:
                        pass
                return job, st, rep

            # ── 5. Incremental Pipeline Execution ────────────────────────────────
            job = IndexJob(
                project_id=project_id,
                repository_id=repo_id,
                type=IndexJobType.INCREMENTAL,
                base_commit_sha=resolved_base_sha,
                target_commit_sha=resolved_target_sha,
                branch=branch,
            )
            job.transition_to(IndexJobStatus.RUNNING, stage="AFFECTED_DISCOVERY")

            stats = IncrementalIndexingStats(
                base_commit_sha=resolved_base_sha,
                target_commit_sha=resolved_target_sha,
                files_added=len(diff_res.added),
                files_modified=len(diff_res.modified),
                files_deleted=len(diff_res.deleted),
                files_renamed=len(diff_res.renamed),
                files_discovered=len(diff_res.changed_files),
            )

            try:
                with RepositorySnapshot(repo_dir, resolved_target_sha) as snapshot:
                    all_directly_changed = set(f.path for f in diff_res.changed_files)
                    for rf in diff_res.renamed:
                        if rf.old_path:
                            all_directly_changed.add(rf.old_path)

                    graph_indexer = GraphIndexer(self.graph_client) if self.graph_client else None
                    affected_to_rewire: List[str] = []

                    # Identify affected files BEFORE mutating the graph
                    if graph_indexer and not validate_only:
                        affected_files = await graph_indexer.find_affected_files(repo_id, list(all_directly_changed))
                        deleted_paths = set(f.path for f in diff_res.deleted) | set(
                            f.old_path for f in diff_res.renamed if f.old_path
                        )
                        affected_to_rewire = [
                            p for p in affected_files
                            if p not in all_directly_changed and p not in deleted_paths
                        ]
                        stats.files_affected = len(affected_to_rewire)

                        # Process deletions (deleted files + old paths of renamed files)
                        job.stage = "DELETIONS"
                        job.progress = 20
                        for df in diff_res.deleted:
                            await graph_indexer.delete_file_and_symbols(repo_id, df.path)
                        for rf in diff_res.renamed:
                            if rf.old_path:
                                await graph_indexer.delete_file_and_symbols(repo_id, rf.old_path)

                    # Parse directly changed files from target snapshot
                    job.stage = "AST_ANALYSIS"
                    job.progress = 40
                    added_prs: List[ParseResult] = []
                    modified_prs: List[ParseResult] = []

                    for cf in diff_res.added + diff_res.renamed:
                        try:
                            code_bytes = snapshot.read_bytes(cf.path)
                            pr = self.parser.parse_code_bytes(code_bytes, cf.path)
                            if pr:
                                added_prs.append(pr)
                                stats.files_parsed += 1
                        except Exception as e:
                            stats.parse_errors += 1
                            warnings.append(f"Failed to parse added/renamed {cf.path}: {e}")

                    for cf in diff_res.modified:
                        try:
                            code_bytes = snapshot.read_bytes(cf.path)
                            pr = self.parser.parse_code_bytes(code_bytes, cf.path)
                            if pr:
                                modified_prs.append(pr)
                                stats.files_parsed += 1
                        except Exception as e:
                            stats.parse_errors += 1
                            warnings.append(f"Failed to parse modified {cf.path}: {e}")

                    # Reconcile symbols & graph state
                    if graph_indexer and not validate_only:
                        job.stage = "RECONCILIATION"
                        job.progress = 60

                        # Index new files & symbols
                        if added_prs:
                            d_cnt, f_cnt = await graph_indexer.index_directories_and_files(
                                repo_id=repo_id,
                                commit_sha=resolved_target_sha,
                                branch=branch,
                                parse_results=added_prs,
                                project_id=project_id,
                                team_id=team_id,
                            )
                            s_cnt = await graph_indexer.index_symbols_and_entities(
                                repo_id=repo_id,
                                commit_sha=resolved_target_sha,
                                branch=branch,
                                parse_results=added_prs,
                                project_id=project_id,
                                team_id=team_id,
                            )
                            stats.entities_created += d_cnt + f_cnt + s_cnt

                        # Reconcile modified files' symbols
                        for pr in modified_prs:
                            c_cnt, u_cnt, d_cnt = await graph_indexer.reconcile_file_symbols(
                                repo_id=repo_id,
                                file_path=pr.file_path,
                                new_symbols=pr.symbols,
                                commit_sha=resolved_target_sha,
                                branch=branch,
                                project_id=project_id,
                                team_id=team_id,
                            )
                            stats.entities_reconciled += c_cnt + u_cnt + d_cnt

                        # Purge old outgoing relationships for modified files before rewiring
                        if modified_prs:
                            await graph_indexer.purge_file_outgoing_relationships(
                                repo_id, [pr.file_path for pr in modified_prs]
                            )

                        # Wire relationships for directly changed files
                        job.stage = "RELATIONSHIPS"
                        job.progress = 75
                        directly_changed_prs = added_prs + modified_prs
                        if directly_changed_prs:
                            h_cnt = await graph_indexer.index_heritage(repo_id, resolved_target_sha, directly_changed_prs)
                            c_cnt, i_cnt = await graph_indexer.index_calls_and_imports(repo_id, resolved_target_sha, directly_changed_prs)
                            t_cnt = await graph_indexer.index_tests(repo_id, resolved_target_sha, directly_changed_prs)
                            stats.relationships_created += h_cnt + c_cnt + i_cnt + t_cnt

                        # Rewire affected files
                        job.stage = "REWIRING"
                        job.progress = 85
                        if affected_to_rewire:
                            affected_prs: List[ParseResult] = []
                            for af_path in affected_to_rewire:
                                try:
                                    af_bytes = snapshot.read_bytes(af_path)
                                    af_pr = self.parser.parse_code_bytes(af_bytes, af_path)
                                    if af_pr:
                                        affected_prs.append(af_pr)
                                except Exception as af_err:
                                    warnings.append(f"Failed to parse affected file {af_path}: {af_err}")

                            if affected_prs:
                                rewired = await graph_indexer.rewire_affected_relationships(
                                    repo_id=repo_id,
                                    commit_sha=resolved_target_sha,
                                    branch=branch,
                                    affected_files=affected_to_rewire,
                                    parse_results=affected_prs,
                                )
                                stats.relationships_reconciled = rewired

                        # Cleanup empty directory nodes
                        await graph_indexer.cleanup_empty_directories(repo_id)
                        await graph_indexer.cleanup_orphaned_external_entities(repo_id)

                        # Post-processing import resolution
                        try:
                            await resolve_repo_imports(self.graph_client, repo_id=repo_id, branch=branch)
                        except Exception as res_err:
                            warnings.append(f"Import resolution notice: {res_err}")

                        # Update repository node
                        await graph_indexer.index_repository_node(
                            project_id=project_id,
                            repo_id=repo_id,
                            commit_sha=resolved_target_sha,
                            branch=branch,
                            team_id=team_id,
                        )

                    # ── Incremental Vector Sync ─────────────────────────────────
                    if self.vector_client and not validate_only:
                        try:
                            # 1. Purge vector entries for deleted files and renamed old paths
                            for df in diff_res.deleted:
                                del_filter = [
                                    {"repo": repo_id},
                                    {"branch": branch},
                                    {"file_path": df.path},
                                ]
                                if project_id and project_id != "default":
                                    del_filter.append({"project_id": project_id})
                                self.vector_client.delete(where={"$and": del_filter})
                            for rf in diff_res.renamed:
                                if rf.old_path:
                                    ren_filter = [
                                        {"repo": repo_id},
                                        {"branch": branch},
                                        {"file_path": rf.old_path},
                                    ]
                                    if project_id and project_id != "default":
                                        ren_filter.append({"project_id": project_id})
                                    self.vector_client.delete(where={"$and": ren_filter})

                            # 2. Purge old vector entries for modified files
                            for mf in diff_res.modified:
                                mod_filter = [
                                    {"repo": repo_id},
                                    {"branch": branch},
                                    {"file_path": mf.path},
                                ]
                                if project_id and project_id != "default":
                                    mod_filter.append({"project_id": project_id})
                                self.vector_client.delete(where={"$and": mod_filter})

                            # 3. Add cleaned symbols for added and modified files
                            raw_inc_symbols = []
                            for pr in added_prs + modified_prs:
                                raw_inc_symbols.extend(pr.symbols)

                            cleaned_inc_symbols = []
                            for sym in raw_inc_symbols:
                                cs = clean_code_symbol(sym)
                                if cs is not None:
                                    cleaned_inc_symbols.append(cs)

                            curated_inc_symbols = filter_repetitive_boilerplate(cleaned_inc_symbols)
                            inc_vector_entries = []
                            for sym in curated_inc_symbols:
                                inc_vector_entries.append({
                                    "project_id": project_id,
                                    "team_id": team_id or "",
                                    "repo": repo_id,
                                    "branch": branch,
                                    "file_path": sym.file_path,
                                    "symbol": sym.name,
                                    "start_line": sym.start_line,
                                    "signature": sym.signature,
                                    "description": sym.docstring or f"{sym.kind} {sym.name} in {sym.file_path}",
                                    "code_body": sym.code_body,
                                    "commit_hash": resolved_target_sha,
                                })
                            if inc_vector_entries:
                                self.vector_client.add_code_entries_batch(inc_vector_entries)

                            # 4. Roll forward commit hash for untouched entries
                            self.vector_client.roll_forward_commit(
                                repo=repo_id,
                                branch=branch,
                                old_commit_hash=resolved_base_sha,
                                new_commit_hash=resolved_target_sha,
                            )
                        except Exception as vec_err:
                            warnings.append(f"Incremental vector sync warning (non-fatal): {vec_err}")

            except Exception as e:
                fatal_errors.append(f"Fatal incremental indexing pipeline failure: {str(e)}")

            stats.duration_seconds = round(time.time() - start_time, 3)
            job.stats = stats

            # ── 6. Validation ────────────────────────────────────────────────────
            job.stage = "VALIDATION"
            job.progress = 95
            report = self.validator.validate(
                repo_id=repo_id,
                commit_sha=job.target_commit_sha,
                stats=stats,
                fatal_errors=fatal_errors,
                warnings=warnings,
            )

            # ── 7. State Transition ──────────────────────────────────────────────
            current_gen = current_state.generation if current_state else 1
            if report.is_valid:
                job.transition_to(IndexJobStatus.COMPLETED, stage="COMPLETED")
                if current_state:
                    current_state.advance_to(
                        new_commit_sha=resolved_target_sha,
                        stats=stats.model_dump(),
                        schema_version=SCHEMA_VERSION,
                        parser_version=PARSER_VERSION,
                    )
                    state = current_state
                else:
                    state = RepositoryIndexState(
                        repository_id=repo_id,
                        branch=branch,
                        indexed_commit_sha=resolved_target_sha,
                        previous_commit_sha=resolved_base_sha,
                        index_version="v1",
                        schema_version=SCHEMA_VERSION,
                        parser_version=PARSER_VERSION,
                        status=IndexStateStatus.READY,
                        generation=current_gen + 1,
                        last_successful_index_at=datetime.now(timezone.utc),
                        stats=stats.model_dump(),
                    )
            else:
                err_summary = "; ".join(report.fatal_errors) or "Validation failed"
                job.transition_to(IndexJobStatus.FAILED, stage="FAILED", error=err_summary)
                if current_state:
                    current_state.status = IndexStateStatus.FAILED
                    current_state.indexing_error = err_summary
                    state = current_state
                else:
                    state = RepositoryIndexState(
                        repository_id=repo_id,
                        branch=branch,
                        indexed_commit_sha=resolved_base_sha,
                        previous_commit_sha=None,
                        index_version="v1",
                        schema_version=SCHEMA_VERSION,
                        parser_version=PARSER_VERSION,
                        status=IndexStateStatus.FAILED,
                        generation=current_gen,
                        indexing_error=err_summary,
                        stats=stats.model_dump(),
                    )

            if owns_graph_client and self.graph_client:
                try:
                    await self.graph_client.close()
                except Exception:
                    pass

            return job, state, report

