import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.web.deps import get_shared_graph_client, get_shared_vector_client
from src.web.schemas import IngestRequest, IngestUrlRequest, ReindexRequest
from src.jobs.init_job import run_init_job
from src.repo.streamer import stream_and_parse_github_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Repository Ingestion & Reindexing"])


@router.post("/ingest")
async def ingest_repository(req: IngestRequest):
    """
    Ingest a repository codebase into Neo4j Graph DB and ChromaDB Vector DB.
    Streams real stage events as NDJSON for durable build tracking.
    """
    graph_client = await get_shared_graph_client()
    vector_client = get_shared_vector_client()

    async def stream_progress():
        queue = asyncio.Queue()

        async def queue_cb(stage: str, status: str, stage_stats: Optional[Dict[str, Any]] = None, stage_error: Optional[str] = None):
            await queue.put({
                "stage": stage,
                "status": status,
                "stats": stage_stats or {},
                "error": stage_error,
                "timestamp": time.time(),
            })

        async def worker():
            try:
                await queue_cb("SNAPSHOT", "RUNNING", {})

                target_full_name = req.full_name or (req.repo_id if "/" in req.repo_id else None)

                if target_full_name:
                    parse_results = stream_and_parse_github_repo(
                        full_name=target_full_name,
                        token=req.access_token,
                        branch=req.branch or "main",
                        root_directory=req.root_directory,
                    )
                    result = await run_init_job(
                        repo_id=req.repo_id,
                        branch=req.branch or "main",
                        parse_results=parse_results,
                        client=graph_client,
                        vector_client=vector_client,
                        extraction_mode=req.extraction_mode or "fast",
                        stage_callback=queue_cb,
                        project_id=req.project_id or "default",
                        team_id=req.team_id,
                        root_directory=req.root_directory,
                    )
                elif req.repo_dir:
                    repo_path = Path(req.repo_dir)
                    if not repo_path.exists():
                        await queue_cb("FAILED", "FAILED", {}, f"Directory '{req.repo_dir}' does not exist")
                        return

                    result = await run_init_job(
                        repo_id=req.repo_id,
                        branch=req.branch or "main",
                        repo_dir=repo_path,
                        client=graph_client,
                        vector_client=vector_client,
                        extraction_mode=req.extraction_mode or "fast",
                        stage_callback=queue_cb,
                        project_id=req.project_id or "default",
                        team_id=req.team_id,
                        root_directory=req.root_directory,
                    )
                else:
                    await queue_cb("FAILED", "FAILED", {}, "Must provide either 'full_name' or 'repo_dir'")
                    return

                if getattr(result, "status", "") == "ERROR":
                    err_msg = "; ".join(getattr(result, "errors", [])) or "Ingestion validation failed"
                    await queue_cb("FAILED", "FAILED", {}, err_msg)
                else:
                    final_stats = {
                        "symbols_parsed": getattr(result, "symbols_count", getattr(result, "total_symbols", 0)),
                        "files_parsed": getattr(result, "vector_entries_count", getattr(result, "total_files", 0)),
                        "packages": getattr(result, "total_packages", 0),
                        "edges_count": getattr(result, "edges_count", 0),
                        "duration_seconds": getattr(result, "duration_seconds", 0.0),
                    }
                    await queue_cb("COMPLETED", "COMPLETED", final_stats)
            except Exception as e:
                await queue_cb("FAILED", "FAILED", {}, str(e))
            finally:
                await queue.put(None)
                try:
                    await graph_client.close()
                except Exception:
                    pass

        asyncio.create_task(worker())

        while True:
            item = await queue.get()
            if item is None:
                break
            yield (json.dumps(item) + "\n").encode("utf-8")

    return StreamingResponse(stream_progress(), media_type="application/x-ndjson")


@router.post("/ingest-url")
async def ingest_from_github_url(req: IngestUrlRequest):
    """
    Ingest a repository by cloning it with automatic temp directory cleanup and size validation.
    """
    import git
    import tempfile

    repo_id = (req.repo_id or "").strip()
    if not repo_id:
        url_clean = req.repo_url.rstrip("/")
        if url_clean.endswith(".git"):
            url_clean = url_clean[:-4]
        parts = url_clean.split("/")
        if len(parts) >= 2:
            repo_id = f"{parts[-2]}/{parts[-1]}"
        elif len(parts) == 1:
            repo_id = parts[0]
        else:
            repo_id = "github-repo"

    with tempfile.TemporaryDirectory() as tmp_dir:
        target_dir = Path(tmp_dir) / "repo"
        try:
            git.Repo.clone_from(req.repo_url, target_dir, depth=1)
        except Exception as clone_err:
            raise HTTPException(status_code=400, detail=f"Failed to clone repository: {clone_err}")

        # Size guard: protect against unexpectedly massive repos (> 500 MB)
        total_size = sum(f.stat().st_size for f in target_dir.rglob("*") if f.is_file())
        if total_size > 500 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Repository exceeds maximum allowed size (500 MB).")

        graph_client = await get_shared_graph_client()
        vector_client = get_shared_vector_client()
        try:
            init_res = await run_init_job(
                repo_id=repo_id,
                branch=req.branch or "main",
                repo_dir=target_dir,
                client=graph_client,
                vector_client=vector_client,
                extraction_mode=req.extraction_mode or "fast",
                project_id=req.project_id or "default",
                team_id=req.team_id,
                root_directory=req.root_directory,
            )

            return {
                "status": init_res.status,
                "repo_id": repo_id,
                "symbols_parsed": getattr(init_res, "symbols_count", getattr(init_res, "total_symbols", 0)),
                "files_parsed": getattr(init_res, "vector_entries_count", getattr(init_res, "total_files", 0)),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ingestion from GitHub URL failed: {str(e)}")


@router.post("/reindex")
async def reindex_repository(req: ReindexRequest):
    """
    Incremental or full reindexing endpoint for a repository codebase.
    Driven securely by internal API calls from Bun.
    Streams stage events as NDJSON for durable build tracking.
    """
    from src.indexer.pipeline import RepositoryIndexer
    from src.indexer.contracts import IndexJobType

    graph_client = await get_shared_graph_client()
    vector_client = get_shared_vector_client()

    async def stream_progress():
        queue = asyncio.Queue()

        async def queue_cb(stage: str, status: str, stage_stats: Optional[Dict[str, Any]] = None, stage_error: Optional[str] = None):
            await queue.put({
                "stage": stage,
                "status": status,
                "stats": stage_stats or {},
                "error": stage_error,
                "timestamp": time.time(),
            })

        async def worker():
            try:
                indexer = RepositoryIndexer(
                    graph_client=graph_client,
                    vector_client=vector_client,
                )

                target_full_name = req.full_name or (req.repo_id if "/" in req.repo_id else None)

                if req.repo_dir and Path(req.repo_dir).exists():
                    target_dir = Path(req.repo_dir)
                    if not req.force_full and req.base_commit_sha:
                        job, state, report = await indexer.run_incremental(
                            repo_dir=target_dir,
                            repo_id=req.repo_id,
                            target_commit_sha=req.target_commit_sha or "HEAD",
                            base_commit_sha=req.base_commit_sha,
                            branch=req.branch or "main",
                            project_id=req.project_id or "default",
                        )
                    else:
                        job, state, report = await indexer.run(
                            repo_dir=target_dir,
                            repo_id=req.repo_id,
                            target_commit_sha=req.target_commit_sha or "HEAD",
                            branch=req.branch or "main",
                            project_id=req.project_id or "default",
                            job_type=IndexJobType.FULL_REINDEX if req.force_full else IndexJobType.INITIAL,
                            stage_callback=queue_cb,
                            root_directory=req.root_directory,
                        )
                elif target_full_name:
                    # In-memory remote tarball stream
                    await queue_cb("SNAPSHOT", "RUNNING", {})
                    parse_results = stream_and_parse_github_repo(
                        full_name=target_full_name,
                        token=req.access_token,
                        branch=req.branch or "main",
                        root_directory=req.root_directory,
                    )
                    job, state, report = await indexer.run(
                        repo_id=req.repo_id,
                        target_commit_sha=req.target_commit_sha or req.branch or "HEAD",
                        branch=req.branch or "main",
                        project_id=req.project_id or "default",
                        job_type=IndexJobType.FULL_REINDEX if req.force_full else IndexJobType.INITIAL,
                        stage_callback=queue_cb,
                        parse_results=parse_results,
                        root_directory=req.root_directory,
                    )
                else:
                    await queue_cb("FAILED", "FAILED", {}, "Must provide either valid 'repo_dir' or 'full_name'")
                    return

                if not report.is_valid:
                    err_msg = "; ".join(report.fatal_errors) or "Reindexing validation failed"
                    await queue_cb("FAILED", "FAILED", {}, err_msg)
                else:
                    final_stats = job.stats.model_dump() if hasattr(job.stats, "model_dump") else {}
                    await queue_cb("COMPLETED", "COMPLETED", final_stats)
            except Exception as e:
                logger.error(f"Reindexing worker error: {e}", exc_info=True)
                await queue_cb("FAILED", "FAILED", {}, str(e))
            finally:
                await queue.put(None)

        asyncio.create_task(worker())

        while True:
            item = await queue.get()
            if item is None:
                break
            yield json.dumps(item) + "\n"

    return StreamingResponse(stream_progress(), media_type="application/x-ndjson")
