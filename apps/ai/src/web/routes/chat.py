import asyncio
import json
import time
from typing import Any, Dict, List

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.agents.agent_loop import AutonomousAgentLoop
from src.agents.llm_client import DualLLMClient
from src.graph.client import Neo4jClient
from src.mcp.tools import (
    tool_get_blast_radius,
    tool_get_file_dependencies,
    tool_get_repo_structure,
    tool_get_symbol_details,
    tool_hybrid_search,
    tool_search_symbols,
    tool_vector_search,
)
from src.vector.client import VectorKBClient
from src.web.deps import get_shared_graph_client, get_shared_vector_client
from src.web.schemas import ChatRequest, ChatResponse, Citation, ToolStep

router = APIRouter(tags=["chat"])


@router.post("/api/chat/stream")
async def agent_chat_stream(req: ChatRequest):
    """
    Autonomous ReAct Agentic RAG Streaming Endpoint (SSE):
    1. Agent runs iterative ReAct reasoning loop.
    2. Streams thoughts, tool calls, tool responses, answer text deltas, and citations.
    """
    graph_client = await get_shared_graph_client()
    vector_client = get_shared_vector_client()
    llm_client = DualLLMClient()
    agent_loop = AutonomousAgentLoop(llm_client=llm_client)

    history_payload = (
        [{"role": m.role, "content": m.content} for m in req.history]
        if req.history
        else None
    )

    async def event_generator():
        async for event in agent_loop.run_stream(
            user_query=req.message,
            repo_id=req.repo_id,
            branch=req.branch or "main",
            graph_client=graph_client,
            vector_client=vector_client,
            history=history_payload,
        ):
            yield event

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
            raw_str = await tool_vector_search(
                vector_client,
                query_text=q,
                repo_id=req.repo_id,
                n_results=5,
                project_id=req.project_id,
            )
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
            raw_str = await tool_hybrid_search(
                graph_client,
                vector_client,
                repo_id=req.repo_id,
                query_text=q,
                branch=req.branch or "main",
                n_results=5,
                project_id=req.project_id,
            )
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
                        "lines": f"{g.get('start_line', '')}-{g.get('end_line', '')}" if g.get("start_line") else None,
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
            raw_str = await tool_get_blast_radius(
                graph_client,
                repo_id=req.repo_id,
                changed_symbols=syms,
                branch=req.branch or "main",
            )
            t_raw = json.loads(raw_str)
            risk = t_raw.get("risk_score", 0.0)
            affected = t_raw.get("total_affected", 0)
            t_summary = f"Calculated ripple effect risk score: {risk}. Total downstream affected symbols: {affected}."

        elif t_name == "get_file_dependencies":
            t_title = "Neo4j File Dependency Graph Traversal"
            f_p = t_args.get("file_path") or t_args.get("file") or t_args.get("path") or "userService.js"
            raw_str = await tool_get_file_dependencies(
                graph_client,
                repo_id=req.repo_id,
                file_path=f_p,
                branch=req.branch or "main",
            )
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
            raw_str = await tool_get_symbol_details(
                graph_client,
                repo_id=req.repo_id,
                qualified_name=q_name,
                branch=req.branch or "main",
            )
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
            from dataclasses import asdict
            from src.context import ContextAuthorizer, ContextEngine, ContextRequest, StaticAuthResolver

            resolver = StaticAuthResolver({req.repo_id: {req.repo_id: None}})
            engine = ContextEngine(
                graph_client=graph_client,
                vector_client=vector_client,
                authorizer=ContextAuthorizer(resolver=resolver, graph_client=graph_client),
            )
            q = t_args.get("query", req.message)
            ctx_res = await engine.retrieve(
                ContextRequest(
                    project_id=req.repo_id,
                    query=q,
                    repository_ids=[req.repo_id],
                    branch=req.branch or "main",
                    max_items=t_args.get("max_items", 8),
                )
            )
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
    except Exception:
        pass

    return raw_context[:2500]


@router.post("/api/chat", response_model=ChatResponse)
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

    graph_client = await get_shared_graph_client()
    vector_client = get_shared_vector_client()
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
