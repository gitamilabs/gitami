import time
import json
import logging
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional
from src.prompts import get_prompt
from src.agents.llm_client import DualLLMClient
from src.mcp.tools import execute_tool_by_name

logger = logging.getLogger(__name__)


def _format_conversation_history(history: Optional[List[Dict[str, str]]]) -> str:
    if not history:
        return ""
    lines = ["\n### RECENT CONVERSATION HISTORY:"]
    for msg in history[-6:]:  # keep last 6 turns (user/assistant)
        role = msg.get("role", "user").upper()
        content = msg.get("content", "")[:500]
        lines.append(f"{role}: {content}")
    return "\n".join(lines) + "\n"


class AutonomousAgentLoop:
    """
    Autonomous ReAct (Reasoning + Action) Agent Loop.
    Executes iterative tool calls, streams reasoning thoughts and tool execution trace,
    and returns synthesized final answers with citations.
    """

    def __init__(self, llm_client: DualLLMClient):
        self.llm_client = llm_client

    async def run_stream(
        self,
        user_query: str,
        repo_id: str,
        branch: str,
        graph_client: Any,
        vector_client: Any,
        history: Optional[List[Dict[str, str]]] = None,
        max_steps: int = 3,
        root_directory: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Runs the ReAct loop and yields Server-Sent Events (SSE) formatted strings.
        Event JSON structure:
        - {"type": "thought", "step_index": 1, "content": "..."}
        - {"type": "tool_start", "step_id": "...", "tool_name": "...", "title": "...", "args": {...}}
        - {"type": "tool_end", "step_id": "...", "tool_name": "...", "status": "completed", "latency_ms": 120, "summary": "...", "raw_output": {...}}
        - {"type": "answer_delta", "delta": "..."}
        - {"type": "citations", "citations": [...]}
        - {"type": "done", "total_latency_ms": 1234}
        """
        loop_start = time.perf_counter()
        observations: List[Dict[str, Any]] = []
        citations: List[Dict[str, Any]] = []
        citation_counter = 1

        def format_sse(data: Dict[str, Any]) -> str:
            return f"data: {json.dumps(data)}\n\n"

        # Keep connection alive while starting up
        yield ": ping\n\n"

        history_context = _format_conversation_history(history)

        # Pre-fetch high-confidence governed context via ContextEngine
        initial_context_str = ""
        try:
            from src.context import ContextEngine, ContextRequest, ContextAuthorizer, StaticAuthResolver
            resolver = StaticAuthResolver({repo_id: {repo_id: None}})
            engine = ContextEngine(
                graph_client=graph_client,
                vector_client=vector_client,
                authorizer=ContextAuthorizer(resolver=resolver, graph_client=graph_client),
            )
            ctx_res = await engine.retrieve(ContextRequest(
                project_id=repo_id,
                query=user_query,
                repository_ids=[repo_id],
                branch=branch,
                max_items=3,
                max_tokens=800,
            ))
            if ctx_res and ctx_res.items:
                ctx_parts = []
                for item in ctx_res.items:
                    snippet = item.content[:300]
                    ctx_parts.append(f"- [{item.type.value}] {item.title}: {snippet}")
                    if item.file_path:
                        citations.append({
                            "id": citation_counter,
                            "file_path": item.file_path,
                            "symbol": item.symbol,
                            "lines": item.line_range,
                            "snippet": snippet,
                        })
                        citation_counter += 1
                if ctx_parts:
                    initial_context_str = "\n### INITIAL GOVERNED REPOSITORY CONTEXT:\n" + "\n".join(ctx_parts) + "\n"
        except Exception as e:
            logger.debug(f"ContextEngine pre-fetch notice: {e}")

        for step_idx in range(1, max_steps + 1):
            # Keep connection warm while LLM generates
            yield ": ping\n\n"

            # Formulate conversation prompt history for LLM
            history_str = ""
            if observations:
                history_str = "\n\n### PREVIOUS TOOL OBSERVATIONS IN THIS REASONING LOOP:\n"
                for obs in observations:
                    history_str += (
                        f"Step {obs['step']}:\n"
                        f"- Thought: {obs['thought']}\n"
                        f"- Tool Called: {obs['tool_name']}({json.dumps(obs['args'])})\n"
                        f"- Summary: {obs['output_summary']}\n"
                        f"- Retrieved Payload Snippet:\n{obs['raw'][:500]}\n\n"
                    )

            scope_str = f"Scoped Subdirectory: '{root_directory}' (focus all search & answers strictly on this directory)\n" if root_directory else ""
            prompt = (
                f"Repository: '{repo_id}' (branch: '{branch}')\n"
                f"{scope_str}"
                f"User Question: '{user_query}'\n"
                f"{history_context}"
                f"{initial_context_str}"
                f"{history_str}\n"
                f"Current Reasoning Step #{step_idx}. Decide your next action (call_tool or final_answer) in valid JSON."
            )

            # Call LLM for reasoning turn with keepalive pings
            llm_response_text = ""
            try:
                llm_task = asyncio.create_task(
                    self._call_llm_json(
                        prompt=prompt,
                        system_prompt=get_prompt("react_agent"),
                    )
                )
                while not llm_task.done():
                    try:
                        await asyncio.wait_for(asyncio.shield(llm_task), timeout=2.5)
                    except asyncio.TimeoutError:
                        if not llm_task.done():
                            yield ": ping\n\n"
                llm_response_text = await llm_task
            except Exception as e:
                logger.warning(f"LLM reasoning turn error: {e}")
                yield format_sse({
                    "type": "thought",
                    "step_index": step_idx,
                    "content": f"LLM reasoning turn encountered an issue ({str(e)}), retrying tool execution..."
                })

            # Parse JSON action
            decision = self._parse_llm_json(llm_response_text)
            thought = decision.get("thought", f"Analyzing codebase context for step #{step_idx}...")
            action = decision.get("action", "call_tool")

            # Stream thought event to frontend
            yield format_sse({
                "type": "thought",
                "step_index": step_idx,
                "content": thought,
            })

            if action == "final_answer":
                answer_text = decision.get("answer", "")
                if not answer_text and "final_answer" in decision:
                    answer_text = str(decision["final_answer"])
                if not answer_text:
                    answer_text = "I have reviewed the repository context and completed your request."

                # Stream answer delta and citations
                yield format_sse({"type": "answer_delta", "delta": answer_text})
                yield format_sse({"type": "citations", "citations": citations})
                
                total_latency = round((time.perf_counter() - loop_start) * 1000.0, 2)
                yield format_sse({"type": "done", "total_latency_ms": total_latency})
                return

            # Otherwise, execute requested tool call
            tool_name = decision.get("tool_name", "hybrid_search")
            tool_args = decision.get("tool_args", {"query": user_query})
            step_id = f"step_{step_idx}_{tool_name}"
            title = self._get_tool_title(tool_name)

            # Stream tool_start event
            yield format_sse({
                "type": "tool_start",
                "step_id": step_id,
                "step_index": step_idx,
                "tool_name": tool_name,
                "title": title,
                "args": tool_args,
            })

            # Execute tool dynamically
            t0 = time.perf_counter()
            tool_raw_str = await execute_tool_by_name(
                tool_name=tool_name,
                tool_args=tool_args,
                graph_client=graph_client,
                vector_client=vector_client,
                repo_id=repo_id,
                branch=branch,
            )
            t_latency = round((time.perf_counter() - t0) * 1000.0, 2)

            parsed_raw = {}
            try:
                parsed_raw = json.loads(tool_raw_str)
            except Exception:
                parsed_raw = {"text": tool_raw_str[:1000]}

            # Extract citations and build step summary
            summary, step_citations = self._extract_summary_and_citations(
                tool_name=tool_name,
                parsed_raw=parsed_raw,
                start_citation_id=citation_counter,
            )
            citation_counter += len(step_citations)
            citations.extend(step_citations)

            # Yield tool_end event
            yield format_sse({
                "type": "tool_end",
                "step_id": step_id,
                "step_index": step_idx,
                "tool_name": tool_name,
                "title": title,
                "status": "completed",
                "latency_ms": t_latency,
                "args": tool_args,
                "summary": summary,
                "raw_output": parsed_raw,
            })

            # Record observation in loop context
            observations.append({
                "step": step_idx,
                "thought": thought,
                "tool_name": tool_name,
                "args": tool_args,
                "output_summary": summary,
                "raw": tool_raw_str[:3000],
            })

            # Brief non-blocking delay for smooth UI streaming
            await asyncio.sleep(0.05)

        # Fallback if max_steps reached: synthesize answer with collected context
        synth_obs = [
            {"step": o["step"], "tool": o["tool_name"], "summary": o["output_summary"], "snippet": o["raw"][:350]}
            for o in observations
        ]
        synth_prompt = (
            f"Repository: '{repo_id}' (branch: '{branch}')\n"
            f"User Query: '{user_query}'\n\n"
            f"{history_context}"
            f"--- REASONING TOOL OBSERVATIONS ---\n"
            f"{json.dumps(synth_obs, indent=2)}\n\n"
            f"Synthesize a final cited answer to the user query."
        )
        synth_task = asyncio.create_task(
            self.llm_client.run_orchestrator(
                prompt=synth_prompt,
                system_prompt=get_prompt("chat_synthesis", "Synthesize an accurate codebase answer using bracketed citations [1], [2]."),
                max_tokens=600,
            )
        )
        while not synth_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(synth_task), timeout=2.5)
            except asyncio.TimeoutError:
                if not synth_task.done():
                    yield ": ping\n\n"
        final_answer = await synth_task
        yield format_sse({"type": "answer_delta", "delta": final_answer})
        yield format_sse({"type": "citations", "citations": citations})

        total_latency = round((time.perf_counter() - loop_start) * 1000.0, 2)
        yield format_sse({"type": "done", "total_latency_ms": total_latency})

    async def _call_llm_json(self, prompt: str, system_prompt: str) -> str:
        """Helper to invoke Orchestrator LLM with JSON format expectation."""
        return await self.llm_client.call_orchestrator_json(prompt, system_prompt)

    def _parse_llm_json(self, text: str) -> Dict[str, Any]:
        if not text:
            return {"action": "call_tool", "tool_name": "hybrid_search", "thought": "Executing default hybrid search..."}
        if not text:
            return {"action": "call_tool", "tool_name": "hybrid_search", "thought": "Executing default hybrid search..."}
        try:
            clean = text.strip()
            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0]
            elif "```" in clean:
                clean = clean.split("```")[1].split("```")[0]
            
            # Find outermost JSON object braces
            first_brace = clean.find("{")
            last_brace = clean.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                clean = clean[first_brace:last_brace+1]

            return json.loads(clean.strip())
        except Exception:
            return {"action": "call_tool", "tool_name": "hybrid_search", "thought": text[:200]}

    def _get_tool_title(self, tool_name: str) -> str:
        titles = {
            "hybrid_search": "Unified Vector & Neo4j Graph Search",
            "vector_search": "ChromaDB Semantic Vector Search",
            "get_symbol_details": "Neo4j Symbol & Call Graph Analysis",
            "get_file_dependencies": "Neo4j File Dependency Graph Traversal",
            "get_file_content": "Fetch Repository File Content",
            "get_blast_radius": "Neo4j Blast Radius Ripple Analysis",
            "get_repo_structure": "Neo4j Repository File Hierarchy",
            "search_symbols": "Neo4j Fuzzy Symbol Search",
        }
        return titles.get(tool_name, tool_name.replace("_", " ").title())

    def _extract_summary_and_citations(
        self, tool_name: str, parsed_raw: Dict[str, Any], start_citation_id: int
    ) -> tuple[str, List[Dict[str, Any]]]:
        citations = []
        c_id = start_citation_id

        if tool_name == "vector_search":
            hits = parsed_raw.get("results", [])
            for h in hits:
                meta = h.get("metadata", {})
                text = h.get("text", "")
                citations.append({
                    "id": c_id,
                    "file_path": meta.get("file_path", "codebase"),
                    "symbol": meta.get("symbol_name") or meta.get("name"),
                    "lines": f"{meta.get('start_line', '')}-{meta.get('end_line', '')}" if meta.get("start_line") else None,
                    "snippet": text[:300] + ("..." if len(text) > 300 else ""),
                    "source_type": "vector",
                })
                c_id += 1
            return f"Retrieved {len(hits)} semantic code passage(s) from ChromaDB.", citations

        elif tool_name == "get_file_content":
            f_path = parsed_raw.get("file_path", "file")
            content = parsed_raw.get("content", "")
            lines_cnt = parsed_raw.get("lines_count", 0)
            source = parsed_raw.get("source", "repository")
            if content and lines_cnt > 0:
                citations.append({
                    "id": c_id,
                    "file_path": f_path,
                    "symbol": None,
                    "lines": f"1-{lines_cnt}",
                    "snippet": content[:350] + ("..." if len(content) > 350 else ""),
                    "source_type": "repository",
                })
                return f"Fetched {lines_cnt} line(s) of '{f_path}' from repository ({source}).", citations
            else:
                return f"File '{f_path}' could not be retrieved from repository.", citations

        elif tool_name == "hybrid_search":
            vec_hits = parsed_raw.get("vector_hits", [])
            g_hits = parsed_raw.get("graph_hits", [])
            for g in g_hits:
                if isinstance(g, dict):
                    citations.append({
                        "id": c_id,
                        "file_path": g.get("file_path", g.get("name", "knowledge-graph")),
                        "symbol": g.get("name") or g.get("qualified_name"),
                        "lines": f"{g.get('start_line', '')}-{g.get('end_line', '')}" if g.get("start_line") else None,
                        "snippet": f"Neo4j Symbol: {g.get('name')}\nDocstring: {g.get('docstring', 'None')}",
                        "source_type": "graph",
                    })
                    c_id += 1
            return f"Retrieved {len(vec_hits)} vector hit(s) and {len(g_hits)} Neo4j graph symbol hit(s).", citations

        elif tool_name == "get_symbol_details":
            callers = len(parsed_raw.get("callers", []))
            callees = len(parsed_raw.get("callees", []))
            return f"Analyzed symbol: {callers} caller(s), {callees} callee(s) in Neo4j graph.", citations

        elif tool_name == "get_file_dependencies":
            imp_by = len(parsed_raw.get("imported_by_files", []))
            imp_files = len(parsed_raw.get("imports_files", []))
            pkgs = len(parsed_raw.get("external_packages", []))
            return f"Imported by {imp_by} file(s); imports {imp_files} local file(s) and {pkgs} external package(s).", citations

        elif tool_name == "get_blast_radius":
            risk = parsed_raw.get("risk_score", 0.0)
            aff = parsed_raw.get("total_affected", 0)
            return f"Calculated ripple effect risk score: {risk}. Total downstream affected symbols: {aff}.", citations

        elif tool_name == "get_repo_structure":
            files_list = parsed_raw.get("files", [])
            key_files = [
                f for f in files_list
                if any(k in f.get("file_path", "").lower() for k in ["readme", "package.json", "app.", "index.", "main."])
            ]
            for kf in (key_files[:4] if key_files else files_list[:3]):
                syms_summary = ", ".join([s.get("name", "") for s in kf.get("symbols", []) if s.get("name")][:5])
                citations.append({
                    "id": c_id,
                    "file_path": kf.get("file_path", "structure"),
                    "symbol": None,
                    "lines": None,
                    "snippet": f"Repository File: {kf.get('file_path')} ({kf.get('language') or 'text'})" + (f" - Symbols: {syms_summary}" if syms_summary else ""),
                    "source_type": "graph",
                })
                c_id += 1
            return f"Retrieved hierarchy for {len(files_list)} file(s) in repository.", citations

        else:
            return f"Executed {tool_name} tool call successfully.", citations
