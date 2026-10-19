import os
import time
import json
import asyncio
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.graph.client import Neo4jClient
from src.vector.client import VectorKBClient
from src.kb_unified import UnifiedKB
from src.mcp.tools import (
    tool_hybrid_search,
    tool_vector_search,
    tool_get_symbol_details,
    tool_get_file_dependencies,
    tool_get_repo_structure,
    tool_get_blast_radius,
    tool_search_symbols,
)
from src.agents.llm_client import DualLLMClient
from src.agents.agent_loop import AutonomousAgentLoop
from src.jobs.init_job import run_init_job
from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"

# Shared, long-lived clients for read-mostly endpoints (currently just
# /api/repos). Opening a fresh Neo4j driver and reloading the Chroma
# collection on every single request added several seconds of pure
# connection overhead per call, and under concurrent load (multiple pages
# fetching at once) those requests queued up and got progressively slower —
# reusing one connection across requests removes that overhead entirely.
_shared_graph_client: Optional[Neo4jClient] = None
_shared_vector_client: Optional[VectorKBClient] = None


async def get_shared_graph_client() -> Neo4jClient:
    global _shared_graph_client
    if _shared_graph_client is None:
        _shared_graph_client = Neo4jClient()
        await _shared_graph_client.connect()
    return _shared_graph_client


def get_shared_vector_client() -> VectorKBClient:
    global _shared_vector_client
    if _shared_vector_client is None:
        _shared_vector_client = VectorKBClient()
    return _shared_vector_client


app = FastAPI(
    title="AI Service Knowledge Base & Agent API",
    description="API for Codebase RAG Chat, Graph & Vector Search, Agent Tool Visualization, and Ingestion.",
    version="1.0.0",
)


@app.on_event("shutdown")
async def _close_shared_clients():
    global _shared_graph_client
    if _shared_graph_client is not None:
        await _shared_graph_client.close()
        _shared_graph_client = None

# Enable CORS for local Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    repo_id: str
    message: str
    branch: Optional[str] = "main"
    history: Optional[List[ChatMessage]] = []


class Citation(BaseModel):
    id: int
    file_path: str
    symbol: Optional[str] = None
    lines: Optional[str] = None
    snippet: str
    source_type: str  # 'vector' or 'graph'
    distance: Optional[float] = None


class ToolStep(BaseModel):
    id: str
    tool_name: str
    title: str
    status: str  # 'completed', 'failed', 'running'
    latency_ms: float
    args: Dict[str, Any]
    summary: str
    raw_output: Any


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]
    tool_steps: List[ToolStep]
    repo_id: str
    branch: str
    total_latency_ms: float


class IngestRequest(BaseModel):
    repo_id: str
    repo_dir: Optional[str] = None
    full_name: Optional[str] = None
    access_token: Optional[str] = None
    branch: Optional[str] = "main"
    extraction_mode: Optional[str] = "fast"


class ReindexRequest(BaseModel):
    repo_id: str
    branch: Optional[str] = "main"
    base_commit_sha: Optional[str] = None
    target_commit_sha: Optional[str] = "HEAD"
    repo_dir: Optional[str] = None
    full_name: Optional[str] = None
    access_token: Optional[str] = None
    force_full: Optional[bool] = False


class PromptUpdateRequest(BaseModel):
    text: str


class ContextApiRequest(BaseModel):
    query: str
    repository_ids: Optional[List[str]] = []
    branch: Optional[str] = "main"
    commit_sha: Optional[str] = None
    max_items: Optional[int] = 20
    max_tokens: Optional[int] = 8000
    include_graph: Optional[bool] = True
    include_semantic: Optional[bool] = True
    include_source: Optional[bool] = True
    include_github: Optional[bool] = True
    hops: Optional[int] = 1


@app.get("/api/health")
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "ai-service-kb"}


@app.post("/projects/{project_id}/context")
@app.post("/api/projects/{project_id}/context")
async def retrieve_project_context(project_id: str, body: ContextApiRequest):
    """
    Governed Context Engine retrieval endpoint for Gitami.
    Enforces Organization -> Project -> Repository authorization before querying
    Neo4j graph, semantic vectors, Git snapshots, and GitHub evidence.
    """
    from dataclasses import asdict
    from src.context import (
        ContextEngine,
        ContextRequest as CtxRequest,
        AuthorizationError,
    )

    graph_client = await get_shared_graph_client()
    vector_client = get_shared_vector_client()
    engine = ContextEngine(graph_client=graph_client, vector_client=vector_client)

    req = CtxRequest(
        project_id=project_id,
        query=body.query,
        repository_ids=body.repository_ids or [],
        branch=body.branch or "main",
        commit_sha=body.commit_sha,
        max_items=body.max_items or 20,
        max_tokens=body.max_tokens or 8000,
        include_graph=body.include_graph if body.include_graph is not None else True,
        include_semantic=body.include_semantic if body.include_semantic is not None else True,
        include_source=body.include_source if body.include_source is not None else True,
        include_github=body.include_github if body.include_github is not None else True,
        hops=body.hops or 1,
    )

    try:
        res = await engine.retrieve(req)
        return asdict(res)
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/config")
async def get_system_config():
    """Get active system configuration including Vector DB, Embedder, and Model lists."""
    from src.config import settings
    from src.agents.llm_client import GEMINI_MODELS, GROQ_MODELS
    return {
        "vector_db": settings.vector_db,
        "embedder": settings.embedder,
        "models": {
            "gemini_models": GEMINI_MODELS,
            "groq_models": GROQ_MODELS,
            "primary_orchestrator": GEMINI_MODELS[0] if GEMINI_MODELS else "gemini-3.6-flash",
            "worker_model": GROQ_MODELS[0] if GROQ_MODELS else "openai/gpt-oss-120b",
        },
        "storage": {
            "qdrant_collection": settings.qdrant_collection,
            "pinecone_index": settings.pinecone_index,
            "supabase_table": settings.supabase_table,
            "chroma_persist_dir": settings.chroma_persist_dir,
        },
    }


@app.get("/api/prompts")
async def list_all_prompts():
    """List all AI system prompts with descriptions, current text, and customization status."""
    from src.prompts import list_prompts
    return {"prompts": list_prompts()}


@app.get("/api/prompts/{key}")
async def get_single_prompt(key: str):
    """Get full details of a specific AI system prompt."""
    from src.prompts import get_prompt_info
    info = get_prompt_info(key)
    if not info:
        raise HTTPException(status_code=404, detail=f"Prompt '{key}' not found.")
    return info


@app.put("/api/prompts/{key}")
async def update_single_prompt(key: str, body: PromptUpdateRequest):
    """Update and persist an AI system prompt."""
    from src.prompts import update_prompt
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="Prompt text cannot be empty.")
    result = update_prompt(key, body.text)
    if not result:
        raise HTTPException(status_code=404, detail=f"Prompt '{key}' not found or could not be updated.")
    return {"status": "success", "prompt": result}


@app.post("/api/prompts/{key}/reset")
async def reset_single_prompt(key: str):
    """Reset an AI system prompt to its default original text."""
    from src.prompts import reset_prompt
    result = reset_prompt(key)
    if not result:
        raise HTTPException(status_code=404, detail=f"Prompt '{key}' not found or could not be reset.")
    return {"status": "success", "prompt": result}


@app.get("/api/repos")
async def list_repositories():
    """List indexed repositories from Vector KB and Graph DB."""
    try:
        vector_client = get_shared_vector_client()
        vector_repos = set(vector_client.get_distinct_repos())
        vector_count = vector_client.count()

        graph_repos = set()
        try:
            graph_client = await get_shared_graph_client()
            records = await graph_client.execute_query("MATCH (f:File) RETURN DISTINCT f.repo_id AS repo")
            for r in records:
                if r.get("repo"):
                    graph_repos.add(r["repo"])
        except Exception:
            pass

        all_repos = sorted(list(vector_repos.union(graph_repos)))

        return {
            "repos": all_repos,
            "vector_count": vector_count,
            "graph_repos": list(graph_repos),
        }
    except Exception as e:
        return {"repos": [], "error": str(e)}



@app.post("/api/ingest")
async def ingest_repository(req: IngestRequest):
    """
    Ingest a repository codebase into Neo4j Graph DB and ChromaDB Vector DB.
    Streams real stage events as NDJSON for durable build tracking.
    """
    from src.repo.streamer import stream_and_parse_github_repo

    async def stream_progress():
        graph_client = Neo4jClient()
        try:
            await graph_client.connect()
        except Exception:
            pass
        vector_client = VectorKBClient()

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

                if req.full_name:
                    parse_results = stream_and_parse_github_repo(
                        full_name=req.full_name,
                        token=req.access_token,
                        branch=req.branch or "main",
                    )
                    result = await run_init_job(
                        repo_id=req.repo_id,
                        branch=req.branch or "main",
                        parse_results=parse_results,
                        client=graph_client,
                        vector_client=vector_client,
                        extraction_mode=req.extraction_mode or "fast",
                        stage_callback=queue_cb,
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

@app.post("/api/chat/stream")
async def agent_chat_stream(req: ChatRequest):
    """
    Autonomous ReAct Agentic RAG Streaming Endpoint (SSE):
    1. Agent runs iterative ReAct reasoning loop.
    2. Streams thoughts, tool calls, tool responses, answer text deltas, and citations.
    """
    graph_client = Neo4jClient()
    try:
        await graph_client.connect()
    except Exception:
        pass

    vector_client = VectorKBClient()
    llm_client = DualLLMClient()
    agent_loop = AutonomousAgentLoop(llm_client=llm_client)

    async def event_generator():
        try:
            async for event in agent_loop.run_stream(
                user_query=req.message,
                repo_id=req.repo_id,
                branch=req.branch or "main",
                graph_client=graph_client,
                vector_client=vector_client,
            ):
                yield event
        finally:
            try:
                await graph_client.close()
            except Exception:
                pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def _execute_single_tool(
    step_idx: int,
    call: Dict[str, Any],
    req: ChatRequest,
    graph_client: Neo4jClient,
    vector_client: VectorKBClient,
) -> tuple[ToolStep, List[Dict[str, Any]]]:
    """Execute a single MCP tool asynchronously, returning (ToolStep, raw_citations_data)."""
    t_name = call.get("tool_name", "vector_search")
    t_args = call.get("args", {})
    t_start = time.perf_counter()
    t_raw: Dict[str, Any] = {}
    t_title = t_name.replace("_", " ").title()
    t_summary = ""
    local_cits_data: List[Dict[str, Any]] = []

    try:
        if t_name == "vector_search":
            t_title = "ChromaDB Semantic Vector Search"
            q = t_args.get("query", req.message)
            raw_str = await tool_vector_search(vector_client, query_text=q, repo_id=req.repo_id, n_results=5)
            t_raw = json.loads(raw_str)
            hits = t_raw.get("results", [])
            t_summary = f"Retrieved {len(hits)} semantic vector code passages from ChromaDB."

            for hit in hits:
                meta = hit.get("metadata", {})
                text = hit.get("text", "")
                file_path = meta.get("file_path", meta.get("repo", "codebase"))
                sym_name = meta.get("symbol_name") or meta.get("name")
                start_l = meta.get("start_line")
                end_l = meta.get("end_line")
                line_str = f"{start_l}-{end_l}" if start_l and end_l else None

                local_cits_data.append({
                    "file_path": file_path,
                    "symbol": sym_name,
                    "lines": line_str,
                    "snippet": text[:300] + ("..." if len(text) > 300 else ""),
                    "source_type": "vector",
                    "distance": round(hit.get("distance", 0.0), 4) if hit.get("distance") else None,
                    "full_text": text[:600],
                })

        elif t_name == "hybrid_search":
            t_title = "Unified Vector & Graph Search"
            q = t_args.get("query", req.message)
            raw_str = await tool_hybrid_search(graph_client, vector_client, repo_id=req.repo_id, query_text=q, branch=req.branch or "main", n_results=5)
            t_raw = json.loads(raw_str)
            vec_hits = t_raw.get("vector_hits", [])
            g_hits = t_raw.get("graph_hits", [])
            t_summary = f"Retrieved {len(vec_hits)} vector hits and {len(g_hits)} Neo4j graph symbol hits."

            for g in g_hits:
                if isinstance(g, dict):
                    f_p = g.get("file_path", g.get("name", "knowledge-graph"))
                    s_n = g.get("name") or g.get("qualified_name")
                    local_cits_data.append({
                        "file_path": f_p,
                        "symbol": s_n,
                        "lines": f"{g.get('start_line', '')}-{g.get('end_line', '')}" if g.get('start_line') else None,
                        "snippet": f"Neo4j {g.get('kind', 'symbol')} Node: {s_n}\nDocstring: {g.get('docstring', 'None')}",
                        "source_type": "graph",
                        "distance": None,
                        "full_text": f"Neo4j Node: {s_n}\nDocstring: {g.get('docstring', 'None')}",
                    })

        elif t_name == "get_blast_radius":
            t_title = "Neo4j Downstream Ripple Blast Radius"
            syms = (
                t_args.get("changed_symbols")
                or t_args.get("symbols")
                or t_args.get("changed_symbol")
                or t_args.get("symbol")
                or ["userService"]
            )
            if isinstance(syms, str):
                syms = [syms]
            raw_str = await tool_get_blast_radius(graph_client, repo_id=req.repo_id, changed_symbols=syms, branch=req.branch or "main")
            t_raw = json.loads(raw_str)
            risk = t_raw.get("risk_score", 0.0)
            affected = t_raw.get("total_affected", 0)
            t_summary = f"Calculated ripple effect risk score: {risk}. Total downstream affected symbols: {affected}."

        elif t_name == "get_file_dependencies":
            t_title = "Neo4j File Dependency Graph Traversal"
            f_p = t_args.get("file_path") or t_args.get("file") or t_args.get("path") or "userService.js"
            raw_str = await tool_get_file_dependencies(graph_client, repo_id=req.repo_id, file_path=f_p, branch=req.branch or "main")
            t_raw = json.loads(raw_str)
            imp_by = len(t_raw.get("imported_by_files", []))
            imp_in = len(t_raw.get("imports_files", []))
            t_summary = f"File '{f_p}' imported by {imp_by} files; imports {imp_in} internal files."

        elif t_name == "get_symbol_details":
            t_title = "Neo4j Symbol & Call Graph Analysis"
            q_name = (
                t_args.get("qualified_name")
                or t_args.get("symbol_name")
                or t_args.get("name")
                or t_args.get("symbol")
                or "userService"
            )
            raw_str = await tool_get_symbol_details(graph_client, repo_id=req.repo_id, qualified_name=q_name, branch=req.branch or "main")
            t_raw = json.loads(raw_str)
            callers_cnt = len(t_raw.get("callers", []))
            t_summary = f"Analyzed symbol '{q_name}': found {callers_cnt} caller node(s)."

        elif t_name == "get_repo_structure":
            t_title = "Neo4j Repository File Hierarchy"
            raw_str = await tool_get_repo_structure(graph_client, repo_id=req.repo_id, branch=req.branch or "main")
            t_raw = json.loads(raw_str)
            files_cnt = len(t_raw.get("files", []))
            t_summary = f"Retrieved structure for {files_cnt} indexed files in Neo4j."

        elif t_name in ("retrieve_context", "get_governed_context", "context_engine"):
            t_title = "Governed Context Engine"
            from src.context import ContextEngine, ContextRequest, ContextAuthorizer, StaticAuthResolver
            from dataclasses import asdict
            resolver = StaticAuthResolver({req.repo_id: {req.repo_id: None}})
            engine = ContextEngine(
                graph_client=graph_client,
                vector_client=vector_client,
                authorizer=ContextAuthorizer(resolver=resolver, graph_client=graph_client),
            )
            q = t_args.get("query", req.message)
            ctx_res = await engine.retrieve(ContextRequest(
                project_id=req.repo_id,
                query=q,
                repository_ids=[req.repo_id],
                branch=req.branch or "main",
                max_items=t_args.get("max_items", 8),
            ))
            t_raw = asdict(ctx_res)
            t_summary = f"Retrieved {len(ctx_res.items)} governed items across graph, vector, and source."
            for itm in ctx_res.items:
                local_cits_data.append({
                    "file_path": itm.file_path or itm.title,
                    "symbol": itm.symbol,
                    "lines": itm.line_range,
                    "snippet": itm.content[:300] + ("..." if len(itm.content) > 300 else ""),
                    "source_type": itm.source.value if hasattr(itm.source, "value") else str(itm.source),
                    "distance": round(1.0 - itm.score, 4) if itm.score else None,
                    "full_text": itm.content[:600],
                })

        else:
            t_title = "Neo4j Fuzzy Symbol Search"
            q = (
                t_args.get("query")
                or t_args.get("query_str")
                or t_args.get("q")
                or t_args.get("symbol")
                or req.message
            )
            raw_str = await tool_search_symbols(graph_client, repo_id=req.repo_id, query_str=q, branch=req.branch or "main")
            t_raw = json.loads(raw_str)
            t_summary = f"Found {len(t_raw)} matching graph symbols."

    except Exception as e:
        t_raw = {"error": str(e)}
        t_summary = f"Tool execution error: {str(e)}"

    t_latency = (time.perf_counter() - t_start) * 1000.0
    step = ToolStep(
        id=f"step_{step_idx}_{t_name}",
        tool_name=t_name,
        title=t_title,
        status="completed",
        latency_ms=round(t_latency, 2),
        args=t_args,
        summary=t_summary,
        raw_output=t_raw,
    )
    return step, local_cits_data


async def _compress_retrieved_context(
    llm_client: DualLLMClient,
    context_chunks: List[str],
    user_query: str,
) -> str:
    """Post-retrieval context compression pass: condenses retrieved passages into high-density facts while preserving citations."""
    if not context_chunks:
        return "No specific vector passages retrieved."

    raw_context = "\n\n".join(context_chunks)
    if len(raw_context) < 1500:
        return raw_context

    from src.prompts import get_prompt
    compress_system_prompt = get_prompt("context_compressor")
    compress_prompt = (
        f"User Query: {user_query}\n\n"
        f"Retrieved Code & Graph Context to Compress:\n{raw_context[:4000]}"
    )
    try:
        compressed = await llm_client.run_orchestrator(compress_prompt, compress_system_prompt)
        if compressed and len(compressed.strip()) > 0:
            return compressed.strip()
    except Exception as e:
        pass


    return raw_context[:2500]


@app.post("/api/chat", response_model=ChatResponse)
async def agent_chat_query(req: ChatRequest):
    """
    Autonomous Agentic RAG Endpoint:
    1. LLM evaluates query and plans dynamic MCP tool calls.
    2. Executes chosen tools in parallel via asyncio.gather.
    3. Streams tool steps trace to frontend visualizer.
    4. Formulates cited sources with collision-free sequential IDs.
    5. Compresses retrieved context if dense.
    6. Synthesizes final response using LLM.
    """
    total_start = time.perf_counter()
    tool_steps: List[ToolStep] = []
    citations: List[Citation] = []
    citation_id_counter = 1
    context_chunks = []

    graph_client = Neo4jClient()
    try:
        await graph_client.connect()
    except Exception:
        pass

    vector_client = VectorKBClient()
    llm_client = DualLLMClient()

    # Step 1: Agent plans dynamic tool calls
    planned_calls = await llm_client.plan_tool_calls(user_query=req.message, repo_id=req.repo_id)

    # Ensure governed context retrieval or hybrid search is included if no tools planned
    has_retrieval = any(c.get("tool_name") in ["retrieve_context", "hybrid_search", "vector_search"] for c in planned_calls)
    if not has_retrieval:
        planned_calls.insert(0, {"tool_name": "retrieve_context", "args": {"query": req.message}})

    # Step 2: Parallel execution of all planned tools (zero sequential bottleneck)
    tasks = [
        _execute_single_tool(idx, call, req, graph_client, vector_client)
        for idx, call in enumerate(planned_calls, start=1)
    ]
    parallel_results = await asyncio.gather(*tasks, return_exceptions=True)

    for res in parallel_results:
        if isinstance(res, Exception):
            tool_steps.append(
                ToolStep(
                    id=f"step_err_{len(tool_steps)+1}",
                    tool_name="tool_execution",
                    title="Parallel Execution Error",
                    status="failed",
                    latency_ms=0.0,
                    args={},
                    summary=f"Tool failed with exception: {res}",
                    raw_output={"error": str(res)},
                )
            )
            continue

        step, cits_data = res
        tool_steps.append(step)

        for c_data in cits_data:
            cit = Citation(
                id=citation_id_counter,
                file_path=c_data["file_path"],
                symbol=c_data.get("symbol"),
                lines=c_data.get("lines"),
                snippet=c_data.get("snippet", ""),
                source_type=c_data.get("source_type", "vector"),
                distance=c_data.get("distance"),
            )
            citations.append(cit)
            context_chunks.append(
                f"[{citation_id_counter}] {c_data.get('source_type', 'Source').capitalize()} Hit - File: {c_data['file_path']} (Symbol: {c_data.get('symbol') or 'N/A'})\n{c_data.get('full_text', '')}"
            )
            citation_id_counter += 1

    # Step 3: Post-Retrieval Context Compression Pass
    context_str = await _compress_retrieved_context(llm_client, context_chunks, req.message)

    # Step 4: LLM Synthesis with Gemini / Groq Orchestrator
    t_synth_start = time.perf_counter()

    from src.prompts import get_prompt
    system_prompt = get_prompt("chat_synthesis")

    prompt = (
        f"Repository: {req.repo_id} (branch: {req.branch or 'main'})\n"
        f"User Query: {req.message}\n\n"
        f"--- EXECUTED MCP TOOL RESULTS ---\n"
        f"{json.dumps([s.raw_output for s in tool_steps], indent=2)[:3000]}\n\n"
        f"--- RETRIEVED COMPRESSED CONTEXT ---\n"
        f"{context_str}\n\n"
        f"Please provide a comprehensive answer with inline citations [1], [2], etc."
    )

    synthesis_response = await llm_client.run_orchestrator(prompt, system_prompt)
    t_synth_latency = (time.perf_counter() - t_synth_start) * 1000.0

    tool_steps.append(
        ToolStep(
            id=f"step_{len(tool_steps)+1}_llm_synthesis",
            tool_name="dual_llm_synthesis",
            title="Google Gemini Dual-LLM Orchestrator",
            status="completed",
            latency_ms=round(t_synth_latency, 2),
            args={"model": "gemini-3.6-flash", "citations_count": len(citations)},
            summary="Synthesized Knowledge Base context into a cited response.",
            raw_output={"response_length": len(synthesis_response)},
        )
    )

    total_latency = (time.perf_counter() - total_start) * 1000.0

    return ChatResponse(
        answer=synthesis_response,
        citations=citations,
        tool_steps=tool_steps,
        repo_id=req.repo_id,
        branch=req.branch or "main",
        total_latency_ms=round(total_latency, 2),
    )


# ---------------------------------------------------------------------------
# PR Review & AI Fix Agent Endpoints
# ---------------------------------------------------------------------------

class PRReviewRequest(BaseModel):
    repo_id: str
    pr_number: int
    base_branch: str = "main"
    head_branch: str
    title: str
    body: Optional[str] = ""
    diff_text: Optional[str] = None


class PRFixRequest(BaseModel):
    repo_id: str
    pr_number: int
    base_branch: str = "main"
    issues: List[Dict[str, Any]]
    diff_text: str = ""
    existing_file_contents: Optional[Dict[str, str]] = None


class IngestUrlRequest(BaseModel):
    repo_url: str
    repo_id: Optional[str] = None
    branch: Optional[str] = "main"
    extraction_mode: Optional[str] = "fast"


@app.post("/api/pr/review")
async def review_pull_request(req: PRReviewRequest):
    """
    Execute autonomous agentic PR review:
    Orchestrator (Gemini) uses Knowledge Base tools + Workers (Groq Llama 3.3 70B) analyze diff hunks.
    """
    # Guardrail: Skip AI fix branches
    if req.head_branch.startswith("ai-fix/") or req.title.lower().startswith("[ai fix]"):
        return {
            "verdict": "ACCEPT",
            "risk_score": 0.0,
            "summary": "Skipped review for AI Fix Agent PR (ai-fix/* branch).",
            "agent_rationale": "Self-review skipped to prevent loop.",
            "issues": [],
            "status": "skipped_ai_fix",
        }

    graph_client = Neo4jClient()
    try:
        await graph_client.connect()
    except Exception:
        pass

    vector_client = VectorKBClient()
    llm_client = DualLLMClient()

    raw_diff = req.diff_text or ""
    if not raw_diff:
        raw_diff = (
            f"PR Title: {req.title}\n"
            f"PR Description: {req.body}\n"
            f"Base Branch: {req.base_branch}\n"
            f"Head Branch: {req.head_branch}\n\n"
            f"/// PR Diff changes in {req.repo_id} for head branch {req.head_branch} ///\n"
        )

    from src.agents.reviewer import run_agentic_pr_review

    try:
        result = await run_agentic_pr_review(
            client=graph_client,
            repo_id=req.repo_id,
            branch=req.head_branch,
            changed_symbols=[],
            raw_diff_text=raw_diff,
            symbols=[],
            vector_client=vector_client,
            llm_client=llm_client,
        )

        return {
            "verdict": result.decision.verdict,
            "risk_score": result.decision.risk_score,
            "summary": result.decision.summary,
            "agent_rationale": result.agent_rationale,
            "issues": result.issues,
            "diff_hunks_count": result.diff_hunks_count,
            "llm_orchestrator_used": result.llm_orchestrator_used,
        }
    finally:
        try:
            await graph_client.close()
        except Exception:
            pass


@app.post("/api/pr/fix")
async def fix_pull_request_issues(req: PRFixRequest):
    """
    Autonomous PR Fix Agent (Surgical Patch Mode):
    Fetches real file content, applies minimal line-level fixes, validates output.
    """
    from src.agents.fixer import run_autonomous_pr_fixer

    llm_client = DualLLMClient()
    fix_res = await run_autonomous_pr_fixer(
        repo_id=req.repo_id,
        pr_number=req.pr_number,
        base_branch=req.base_branch,
        issues=req.issues,
        llm_client=llm_client,
        diff_text=req.diff_text,
        existing_file_contents=req.existing_file_contents,
    )

    return {
        "success": fix_res.success,
        "plan_rationale": fix_res.plan_rationale,
        "file_fixes": [
            {"file_path": f.file_path, "content": f.content}
            for f in fix_res.file_fixes
        ],
        "error": fix_res.error,
    }


# ---------------------------------------------------------------------------
# Curated Multi-Agent System Endpoints (Investigation, Issue, Doc, Code)
# ---------------------------------------------------------------------------

class InvestigationRequest(BaseModel):
    query: str
    repo_id: str
    branch: Optional[str] = "main"
    is_incident: bool = False
    incident_context: Optional[Dict[str, Any]] = None
    max_steps: Optional[int] = 8


class IssueAnalyzeRequest(BaseModel):
    repo_id: str
    issue_number: int
    title: str
    body: Optional[str] = ""
    author: Optional[str] = "unknown"
    labels: Optional[List[str]] = []
    existing_issues: Optional[List[Dict[str, Any]]] = None


class DocGenerateRequest(BaseModel):
    repo_id: str
    doc_type: str = "workflow_guide"  # "workflow_guide", "onboarding_doc", "weekly_changelog"
    topic: str
    branch: Optional[str] = "main"
    feed_to_kb: bool = True
    merged_prs: Optional[List[Dict[str, Any]]] = None


class CodePlanRequest(BaseModel):
    repo_id: str
    issue_title: str
    issue_description: str
    trigger_source: str = "review"
    affected_files: Optional[List[str]] = None
    branch: Optional[str] = "main"


class CodeExecuteRequest(BaseModel):
    plan: Dict[str, Any]
    existing_file_contents: Dict[str, str]
    maintainer_notes: Optional[str] = None


@app.post("/api/investigate")
async def investigate_codebase(req: InvestigationRequest):
    """
    Executes the Curated Investigation Agent:
    - Fast single-shot path for informational questions
    - Up to 8-step iterative hypothesis testing loop for root cause debugging & incidents
    """
    from src.agents import InvestigationAgent
    agent = InvestigationAgent(
        llm_client=DualLLMClient(),
        graph_client=get_shared_graph_client(),
        vector_client=get_shared_vector_client(),
    )
    result = await agent.run(
        query=req.query,
        repo_id=req.repo_id,
        branch=req.branch or "main",
        is_incident=req.is_incident,
        incident_context=req.incident_context,
        max_steps=req.max_steps or 8,
    )
    return result.to_dict()


@app.post("/api/issue/analyze")
async def analyze_github_issue(req: IssueAnalyzeRequest):
    """
    Executes the Curated Issue Agent:
    - Spam detection
    - Duplicate detection across open/closed issues
    - Criticality scoring (1-10)
    - Domain tagging
    - AI Code Suspected flag
    """
    from src.agents import IssueAgent
    agent = IssueAgent(
        llm_client=DualLLMClient(),
        graph_client=get_shared_graph_client(),
        vector_client=get_shared_vector_client(),
    )
    result = await agent.run(
        repo_id=req.repo_id,
        issue_number=req.issue_number,
        title=req.title,
        body=req.body or "",
        author=req.author or "unknown",
        existing_labels=req.labels,
        existing_issues=req.existing_issues,
    )
    return result.to_dict()


@app.post("/api/doc/generate")
async def generate_documentation(req: DocGenerateRequest):
    """
    Executes the Curated Doc Agent:
    - Generates workflow guides, onboarding docs per domain, or weekly changelogs
    - Automatically feeds generated docs back into the Vector KB
    """
    from src.agents import DocAgent
    agent = DocAgent(
        llm_client=DualLLMClient(),
        graph_client=get_shared_graph_client(),
        vector_client=get_shared_vector_client(),
    )
    if req.doc_type == "onboarding_doc":
        res = await agent.generate_onboarding_doc(
            repo_id=req.repo_id,
            domain=req.topic,
            branch=req.branch or "main",
            feed_to_kb=req.feed_to_kb,
        )
    elif req.doc_type == "weekly_changelog":
        res = await agent.generate_weekly_changelog(
            repo_id=req.repo_id,
            merged_prs=req.merged_prs or [],
            week_label=req.topic or "This Week",
        )
    else:
        res = await agent.generate_workflow_guide(
            repo_id=req.repo_id,
            feature_name=req.topic,
            branch=req.branch or "main",
            feed_to_kb=req.feed_to_kb,
        )
    return res.to_dict()


@app.post("/api/code/plan")
async def plan_code_fix(req: CodePlanRequest):
    """
    Executes Code Agent Stage 1:
    - Generates a surgical fix plan (files to touch, approach, test strategy)
    - Waits for maintainer approval before executing
    """
    from src.agents import CodeAgent
    agent = CodeAgent(
        llm_client=DualLLMClient(),
        graph_client=get_shared_graph_client(),
        vector_client=get_shared_vector_client(),
    )
    plan = await agent.generate_fix_plan(
        repo_id=req.repo_id,
        issue_title=req.issue_title,
        issue_description=req.issue_description,
        trigger_source=req.trigger_source,
        affected_files=req.affected_files,
        branch=req.branch or "main",
    )
    return plan.to_dict()


@app.post("/api/code/execute")
async def execute_code_fix(req: CodeExecuteRequest):
    """
    Executes Code Agent Stage 2:
    - Synthesizes reproduction test and verified implementation patch for an approved plan
    """
    from src.agents import CodeAgent, FixPlan
    agent = CodeAgent(
        llm_client=DualLLMClient(),
        graph_client=get_shared_graph_client(),
        vector_client=get_shared_vector_client(),
    )
    p = req.plan
    plan_obj = FixPlan(
        plan_id=p.get("plan_id", "plan_1"),
        repo_id=p.get("repo_id", ""),
        trigger_source=p.get("trigger_source", "review"),
        summary=p.get("summary", ""),
        files_to_touch=p.get("files_to_touch", []),
        approach=p.get("approach", ""),
        test_strategy=p.get("test_strategy", ""),
        risk_assessment=p.get("risk_assessment", "medium"),
        needs_approval=False,
        approved=True,
    )
    result = await agent.execute_approved_plan(
        plan=plan_obj,
        existing_file_contents=req.existing_file_contents,
        maintainer_notes=req.maintainer_notes,
    )
    return result.to_dict()


@app.post("/api/ingest-url")
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

        graph_client = Neo4jClient()
        try:
            await graph_client.connect()
        except Exception:
            pass

        vector_client = VectorKBClient()
        try:
            init_res = await run_init_job(
                repo_id=repo_id,
                branch=req.branch or "main",
                repo_dir=target_dir,
                client=graph_client,
                vector_client=vector_client,
                extraction_mode=req.extraction_mode or "fast",
            )

            return {
                "status": init_res.status,
                "repo_id": repo_id,
                "symbols_parsed": getattr(init_res, "symbols_count", getattr(init_res, "total_symbols", 0)),
                "files_parsed": getattr(init_res, "vector_entries_count", getattr(init_res, "total_files", 0)),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ingestion from GitHub URL failed: {str(e)}")
        finally:
            try:
                await graph_client.close()
            except Exception:
                pass


@app.post("/api/reindex")
async def reindex_repository(req: ReindexRequest):
    """
    Incremental or full reindexing endpoint for a repository codebase.
    Driven securely by internal API calls from Bun.
    Streams stage events as NDJSON for durable build tracking.
    """
    from src.indexer.pipeline import RepositoryIndexer
    from src.indexer.contracts import IndexJobType
    from src.repo.streamer import stream_and_parse_github_repo

    async def stream_progress():
        graph_client = Neo4jClient()
        try:
            await graph_client.connect()
        except Exception:
            pass
        vector_client = VectorKBClient()
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

                if req.repo_dir and Path(req.repo_dir).exists():
                    target_dir = Path(req.repo_dir)
                    if not req.force_full and req.base_commit_sha:
                        job, state, report = await indexer.run_incremental(
                            repo_dir=target_dir,
                            repo_id=req.repo_id,
                            target_commit_sha=req.target_commit_sha or "HEAD",
                            base_commit_sha=req.base_commit_sha,
                            branch=req.branch or "main",
                        )
                    else:
                        job, state, report = await indexer.run(
                            repo_dir=target_dir,
                            repo_id=req.repo_id,
                            target_commit_sha=req.target_commit_sha or "HEAD",
                            branch=req.branch or "main",
                            job_type=IndexJobType.FULL_REINDEX if req.force_full else IndexJobType.INITIAL,
                            stage_callback=queue_cb,
                        )
                elif req.full_name:
                    # In-memory remote tarball stream
                    await queue_cb("SNAPSHOT", "RUNNING", {})
                    parse_results = stream_and_parse_github_repo(
                        full_name=req.full_name,
                        token=req.access_token,
                        branch=req.branch or "main",
                    )
                    job, state, report = await indexer.run(
                        repo_id=req.repo_id,
                        target_commit_sha=req.target_commit_sha or req.branch or "HEAD",
                        branch=req.branch or "main",
                        job_type=IndexJobType.FULL_REINDEX if req.force_full else IndexJobType.INITIAL,
                        stage_callback=queue_cb,
                        parse_results=parse_results,
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
                try:
                    await graph_client.close()
                except Exception:
                    pass

        asyncio.create_task(worker())

        while True:
            item = await queue.get()
            if item is None:
                break
            yield json.dumps(item) + "\n"

    return StreamingResponse(stream_progress(), media_type="application/x-ndjson")


@app.get("/api/graph/{repo_id:path}")
async def get_graph_data(repo_id: str, branch: str = "main", max_nodes: int = 500):
    """
    Returns actual Neo4j nodes and edges for the interactive knowledge graph.
    """
    graph_client = Neo4jClient()
    try:
        await graph_client.connect()
        from src.graph.reader import get_entire_graph
        from src.analysis.graph_analysis import compute_graph_presentation
        raw_data = await get_entire_graph(graph_client, repo_id=repo_id, branch=branch, max_nodes=max_nodes)
        presentation = compute_graph_presentation(raw_data)
        return {
            "status": "success",
            "repo_id": repo_id,
            "branch": branch,
            "nodes": presentation["nodes"],
            "edges": presentation["edges"],
            "communities": presentation["communities"],
            "stats": presentation["stats"],
            "total_nodes": presentation["stats"]["nodeCount"],
            "total_edges": presentation["stats"]["edgeCount"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            await graph_client.close()
        except Exception:
            pass


@app.get("/api/graph-report/{repo_id:path}")
async def get_graph_report(repo_id: str, branch: str = "main"):
    """
    Generates and returns the Graphify architectural report (GRAPH_REPORT.md).
    Runs community clustering, god node detection, and import cycle analysis.
    """
    graph_client = Neo4jClient()
    try:
        await graph_client.connect()
        from src.graph.reader import get_entire_graph
        from src.analysis.graph_analysis import (
            build_networkx_graph, cluster_graph, find_god_nodes, 
            find_surprising_connections, find_import_cycles
        )
        from src.analysis.report import generate_graph_report
        import tempfile
        
        graph_data = await get_entire_graph(graph_client, repo_id=repo_id, branch=branch)
        G = build_networkx_graph(graph_data)
        
        communities = cluster_graph(G)
        god_nodes = find_god_nodes(G)
        surprising = find_surprising_connections(G, communities)
        cycles = find_import_cycles(G)
        
        tmp_dir = Path(tempfile.gettempdir()) / "graphify_reports" / repo_id.replace("/", "_")
        md_path = generate_graph_report(
            repo_id=repo_id,
            nodes=graph_data["nodes"],
            edges=graph_data["edges"],
            communities=communities,
            god_nodes=god_nodes,
            surprising=surprising,
            cycles=cycles,
            out_dir=tmp_dir
        )
        
        if md_path.exists():
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"status": "success", "repo_id": repo_id, "report_markdown": content}
        else:
            raise HTTPException(status_code=500, detail="Failed to generate report file.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            await graph_client.close()
        except Exception:
            pass

