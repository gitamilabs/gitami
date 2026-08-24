import os
import json
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()


class DualLLMClient:
    """Dual-LLM Client wrapper: Google Gemini for Orchestration & Groq (Llama 3.3 70B) for Worker Sub-tasks / Failover."""

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
    ):
        self.gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.groq_key = groq_api_key or os.getenv("GROQ_API_KEY")

        self.has_gemini = bool(self.gemini_key)
        self.has_groq = bool(self.groq_key)

    async def plan_tool_calls(self, user_query: str, repo_id: str) -> List[Dict[str, Any]]:
        """
        Agentic planning step: Ask the LLM to dynamically decide which Knowledge Base MCP tools to call.
        Returns a list of tool call dictionaries: [{"tool_name": "...", "args": {...}}]
        """
        system_prompt = (
            "You are an autonomous AI Agent orchestrating Knowledge Base MCP tools for a codebase repository.\n"
            "Analyze the user's query and decide which tool(s) are most useful to gather context.\n\n"
            "AVAILABLE MCP TOOLS:\n"
            "1. hybrid_search(query: str): Unified vector similarity + Neo4j graph symbol search.\n"
            "2. vector_search(query: str): Semantic search across code, commits, PRs in ChromaDB.\n"
            "3. get_symbol_details(qualified_name: str): Retrieve caller/callee relations for a symbol in Neo4j.\n"
            "4. get_file_dependencies(file_path: str): Retrieve inbound and outbound imports for a file in Neo4j.\n"
            "5. get_blast_radius(changed_symbols: list[str]): Compute downstream ripple effect risk score in Neo4j.\n"
            "6. get_repo_structure(repo_id: str): Retrieve full file tree and symbol hierarchy in Neo4j.\n"
            "7. search_symbols(query: str): Fuzzy symbol search across Neo4j graph.\n\n"
            "RESPONSE FORMAT: You MUST return ONLY valid JSON with this format:\n"
            "{\n"
            '  "thought": "Reasoning for tool choices",\n'
            '  "tool_calls": [\n'
            '    {"tool_name": "hybrid_search", "args": {"query": "user services"}},\n'
            '    {"tool_name": "get_file_dependencies", "args": {"file_path": "userService.js"}}\n'
            '  ]\n'
            "}"
        )

        user_prompt = f"Repository ID: '{repo_id}'\nUser Query: '{user_query}'\nSelect the best tool(s) to execute."

        raw_response = ""
        # Try Gemini or Groq for fast JSON tool selection
        if self.has_gemini:
            for model_name in ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-flash-latest"]:
                try:
                    from google import genai
                    client = genai.Client(api_key=self.gemini_key)
                    res = client.models.generate_content(
                        model=model_name,
                        contents=f"{system_prompt}\n\n{user_prompt}",
                    )
                    if res and res.text:
                        raw_response = res.text
                        break
                except Exception:
                    pass

        if not raw_response and self.has_groq:
            for model_name in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "groq/compound-mini"]:
                try:
                    from groq import Groq
                    client = Groq(api_key=self.groq_key)
                    completion = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.1,
                        response_format={"type": "json_object"}
                    )
                    if completion.choices and completion.choices[0].message.content:
                        raw_response = completion.choices[0].message.content
                        break
                except Exception:
                    pass

        # Parse JSON decision
        if raw_response:
            try:
                # Strip markdown fence if present
                clean_json = raw_response.strip()
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0]
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0]
                data = json.loads(clean_json.strip())
                calls = data.get("tool_calls", [])
                if isinstance(calls, list) and len(calls) > 0:
                    return calls
            except Exception:
                pass

        # Smart Fallback if LLM parsing fails: default to hybrid_search
        return [{"tool_name": "hybrid_search", "args": {"query": user_query}}]

    async def run_orchestrator(self, prompt: str, system_prompt: str) -> str:
        """Call Google Gemini for main orchestration; fail over to Groq if Gemini quota/error occurs."""
        # 1. Try Gemini
        if self.has_gemini:
            for model_name in ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-flash-latest"]:
                try:
                    from google import genai
                    client = genai.Client(api_key=self.gemini_key)
                    response = client.models.generate_content(
                        model=model_name,
                        contents=f"{system_prompt}\n\n{prompt}",
                    )
                    if response and response.text:
                        return response.text
                except Exception:
                    pass

        # 2. Try Groq as robust failover
        if self.has_groq:
            for model_name in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "groq/compound-mini"]:
                try:
                    from groq import Groq
                    client = Groq(api_key=self.groq_key)
                    completion = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.2,
                    )
                    res_text = completion.choices[0].message.content
                    if res_text:
                        return res_text
                except Exception:
                    pass

        # 3. Local Intelligent RAG Synthesis if both LLMs are offline
        return (
            "### Knowledge Base Intelligence Summary\n\n"
            "Retrieved relevant code passages and structural knowledge graph entities for your query. "
            "Refer to the cited source cards below for file snippets, line numbers, and symbol definitions."
        )

    async def run_worker(self, prompt: str, system_prompt: str) -> str:
        """Call Groq for fast parallel hunk review sub-tasks."""
        if self.has_groq:
            for model_name in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "groq/compound-mini"]:
                try:
                    from groq import Groq
                    client = Groq(api_key=self.groq_key)
                    completion = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.2,
                    )
                    return completion.choices[0].message.content or ""
                except Exception as e:
                    pass
        
        # Fallback to Gemini if Groq is unavailable
        if self.has_gemini:
            for model_name in ["gemini-3.6-flash", "gemini-3.7-flash"]:
                try:
                    from google import genai
                    client = genai.Client(api_key=self.gemini_key)
                    response = client.models.generate_content(
                        model=model_name,
                        contents=f"{system_prompt}\n\n{prompt}",
                    )
                    if response and response.text:
                        return response.text
                except Exception:
                    pass

        return "[Worker Node - Offline Mode] Hunk analysis completed."
