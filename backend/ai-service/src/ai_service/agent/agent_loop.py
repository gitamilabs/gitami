import time
import json
import logging
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional
from ai_service.prompts import get_prompt
from ai_service.agent.llm_client import DualLLMClient
from ai_service.mcp.tools import execute_tool_by_name

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
        max_steps: int = 4,
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

        history_context = _format_conversation_history(history)

        for step_idx in range(1, max_steps + 1):
            # Formulate conversation prompt history for LLM
            history_str = ""
            if observations:
                history_str = "\n\n### PREVIOUS TOOL OBSERVATIONS & RETRIEVED CODE PASSAGES IN THIS REASONING LOOP:\n"
                for obs in observations:
                    age = step_idx - obs["step"]
                    max_chars = max(600, 1800 // (age + 1))
                    history_str += (
                        f"Step {obs['step']}:\n"
                        f"- Thought: {obs['thought']}\n"
                        f"- Tool Called: {obs['tool_name']}({json.dumps(obs['args'])})\n"
                        f"- Summary: {obs['output_summary']}\n"
                        f"- Retrieved Payload / Code Content:\n{obs['raw'][:max_chars]}\n\n"
                    )

            prompt = (
                f"Repository: '{repo_id}' (branch: '{branch}')\n"
                f"User Question: '{user_query}'\n"
                f"{history_context}"
                f"{history_str}\n"
                f"Current Reasoning Step #{step_idx}. Decide your next action (call_tool or final_answer) in valid JSON."
            )

            # Call LLM for reasoning turn
            llm_response_text = ""
            try:
                llm_response_text = await self._call_llm_json(
                    prompt=prompt,
                    system_prompt=get_prompt("react_agent"),
                )
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
        synth_prompt = (
            f"Repository: '{repo_id}' (branch: '{branch}')\n"
            f"User Query: '{user_query}'\n\n"
            f"{history_context}"
            f"--- REASONING TOOL OBSERVATIONS ---\n"
            f"{json.dumps([o['raw'] for o in observations], indent=2)[:3000]}\n\n"
            f"Synthesize a final cited answer to the user query."
        )
        final_answer = await self.llm_client.run_orchestrator(
            prompt=synth_prompt,
            system_prompt=get_prompt("chat_synthesis", "Synthesize an accurate codebase answer using bracketed citations [1], [2]."),
        )
        yield format_sse({"type": "answer_delta", "delta": final_answer})
        yield format_sse({"type": "citations", "citations": citations})

        total_latency = round((time.perf_counter() - loop_start) * 1000.0, 2)
        yield format_sse({"type": "done", "total_latency_ms": total_latency})

    async def _call_llm_json(self, prompt: str, system_prompt: str) -> str:
        """Helper to invoke LLM with JSON format expectation."""
        if self.llm_client.has_gemini:
            res = await self.llm_client._call_gemini(prompt, system_prompt, temperature=0.1, json_mode=True)
            if res:
                return res

        if self.llm_client.has_groq:
            res = await self.llm_client._call_groq(prompt, system_prompt, temperature=0.1, json_mode=True)
            if res:
                return res

        return ""

    def _parse_llm_json(self, text: str) -> Dict[str, Any]:
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
            "get_file_content": "Read Repository File Content from Disk",
            "get_blast_radius": "Neo4j Blast Radius Ripple Analysis",
            "get_repo_structure": "Neo4j Repository File Hierarchy",
            "search_symbols": "Neo4j Fuzzy Symbol Search",
            "cpg_dataflow": "Joern CPG Interprocedural Taint Tracking",
            "cpg_reachable_guards": "Joern CPG Reachable Guards & Sanitizer Check",
            "cpg_callers_with_args": "Joern CPG Call Sites & Argument Tracing",
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
                sym = meta.get("symbol") or meta.get("symbol_name") or meta.get("name")
                start_l = meta.get("start_line")
                end_l = meta.get("end_line")
                line_str = f"{start_l}-{end_l}" if start_l and end_l else (str(start_l) if start_l else None)
                citations.append({
                    "id": c_id,
                    "file_path": meta.get("file_path", "codebase"),
                    "symbol": sym,
                    "lines": line_str,
                    "snippet": text[:500] + ("..." if len(text) > 500 else ""),
                    "source_type": "vector",
                })
                c_id += 1
            return f"Retrieved {len(hits)} semantic code passage(s) from ChromaDB.", citations

        elif tool_name == "get_file_content":
            f_path = parsed_raw.get("file_path", "file")
            content = parsed_raw.get("content", "")
            lines_cnt = parsed_raw.get("lines_count", 0)
            if content:
                citations.append({
                    "id": c_id,
                    "file_path": f_path,
                    "symbol": None,
                    "lines": f"1-{lines_cnt}",
                    "snippet": content[:500] + ("..." if len(content) > 500 else ""),
                    "source_type": "disk",
                })
            return f"Read {lines_cnt} line(s) of '{f_path}' directly from repository disk.", citations

        elif tool_name == "hybrid_search":
            vec_hits = parsed_raw.get("vector_hits", [])
            g_hits = parsed_raw.get("graph_hits", [])
            seen_cits = set()

            for v in vec_hits:
                meta = v.get("metadata", {})
                text = v.get("document", "")
                sym = meta.get("symbol") or meta.get("symbol_name") or meta.get("name")
                f_path = meta.get("file_path", "codebase")
                start_l = meta.get("start_line")
                end_l = meta.get("end_line")
                line_str = f"{start_l}-{end_l}" if start_l and end_l else (str(start_l) if start_l else None)
                cit_key = f"{f_path}:{sym or ''}:{line_str or ''}"
                seen_cits.add(cit_key)
                citations.append({
                    "id": c_id,
                    "file_path": f_path,
                    "symbol": sym,
                    "lines": line_str,
                    "snippet": text[:500] + ("..." if len(text) > 500 else ""),
                    "source_type": "vector",
                })
                c_id += 1

            for g in g_hits:
                if isinstance(g, dict):
                    f_p = g.get("file_path", g.get("name", "knowledge-graph"))
                    s_n = g.get("name") or g.get("qualified_name")
                    g_start = g.get("start_line")
                    g_end = g.get("end_line")
                    g_lines = f"{g_start}-{g_end}" if g_start and g_end else (str(g_start) if g_start else None)
                    cit_key = f"{f_p}:{s_n or ''}:{g_lines or ''}"
                    if cit_key in seen_cits:
                        continue
                    seen_cits.add(cit_key)
                    citations.append({
                        "id": c_id,
                        "file_path": f_p,
                        "symbol": s_n,
                        "lines": g_lines,
                        "snippet": f"Neo4j Symbol: {s_n}\nDocstring: {g.get('docstring', 'None')}",
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
            files = len(parsed_raw.get("files", []))
            return f"Retrieved hierarchy for {files} file(s) in repository.", citations

        else:
            return f"Executed {tool_name} tool call successfully.", citations
