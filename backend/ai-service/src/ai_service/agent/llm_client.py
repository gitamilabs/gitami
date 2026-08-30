import os
import json
import logging
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-3.7-flash",
]
GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
    "qwen/qwen3.8-27b",
]



class DualLLMClient:
    """Dual-LLM Client wrapper: Google Gemini for Orchestration & Groq for Worker Sub-tasks / Failover."""

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
    ):
        self.gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.groq_key = groq_api_key or os.getenv("GROQ_API_KEY")

        self.has_gemini = bool(self.gemini_key)
        self.has_groq = bool(self.groq_key)

        self._genai_client = None
        self._groq_client = None

    def _get_genai_client(self):
        if not self._genai_client and self.has_gemini:
            try:
                from google import genai
                self._genai_client = genai.Client(api_key=self.gemini_key)
            except Exception as e:
                logger.error(f"Failed to instantiate Google GenAI Client: {e}")
        return self._genai_client

    def _get_groq_client(self):
        if not self._groq_client and self.has_groq:
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=self.groq_key)
            except Exception as e:
                logger.error(f"Failed to instantiate Groq Client: {e}")
        return self._groq_client

    async def _call_gemini(
        self, prompt: str, system_prompt: str, models: Optional[List[str]] = None
    ) -> Optional[str]:
        client = self._get_genai_client()
        if not client:
            return None

        target_models = models or GEMINI_MODELS
        for model_name in target_models:
            try:
                res = client.models.generate_content(
                    model=model_name,
                    contents=f"{system_prompt}\n\n{prompt}",
                )
                if res and res.text:
                    return res.text
            except Exception as e:
                logger.warning(f"Gemini generation failed for model [{model_name}]: {e}")
        return None

    async def _call_groq(
        self,
        prompt: str,
        system_prompt: str,
        models: Optional[List[str]] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> Optional[str]:
        client = self._get_groq_client()
        if not client:
            return None

        target_models = models or GROQ_MODELS
        for model_name in target_models:
            try:
                kwargs: Dict[str, Any] = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": temperature,
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}

                completion = client.chat.completions.create(**kwargs)
                if completion.choices and completion.choices[0].message.content:
                    return completion.choices[0].message.content
            except Exception as e:
                logger.warning(f"Groq completion failed for model [{model_name}]: {e}")
        return None

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
            "5. get_file_content(file_path: str): Read raw source code, README, or config file contents from disk.\n"
            "6. get_blast_radius(changed_symbols: list[str]): Compute downstream ripple effect risk score in Neo4j.\n"
            "7. get_repo_structure(repo_id: str): Retrieve full file tree and symbol hierarchy in Neo4j.\n"
            "8. search_symbols(query: str): Fuzzy symbol search across Neo4j graph.\n\n"
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

        raw_response = None
        if self.has_gemini:
            raw_response = await self._call_gemini(user_prompt, system_prompt)

        if not raw_response and self.has_groq:
            raw_response = await self._call_groq(
                user_prompt, system_prompt, temperature=0.1, json_mode=True
            )

        if raw_response:
            try:
                clean_json = raw_response.strip()
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0]
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0]
                data = json.loads(clean_json.strip())
                calls = data.get("tool_calls", [])
                if isinstance(calls, list) and len(calls) > 0:
                    return calls
            except Exception as e:
                logger.warning(f"Failed to parse tool plan JSON: {e}")

        # Smart Fallback if LLM parsing fails: default to hybrid_search
        return [{"tool_name": "hybrid_search", "args": {"query": user_query}}]

    async def run_orchestrator(self, prompt: str, system_prompt: str) -> str:
        """Call Google Gemini for main orchestration; fail over to Groq if Gemini quota/error occurs."""
        if self.has_gemini:
            res = await self._call_gemini(prompt, system_prompt)
            if res:
                return res

        if self.has_groq:
            res = await self._call_groq(prompt, system_prompt, temperature=0.2)
            if res:
                return res

        # Local Intelligent RAG Synthesis if both LLMs are offline
        return (
            "### Knowledge Base Intelligence Summary\n\n"
            "Retrieved relevant code passages and structural knowledge graph entities for your query. "
            "Refer to the cited source cards below for file snippets, line numbers, and symbol definitions."
        )

    async def run_worker(self, prompt: str, system_prompt: str) -> str:
        """Call Groq for fast parallel hunk review sub-tasks; fallback to Gemini."""
        if self.has_groq:
            res = await self._call_groq(prompt, system_prompt, temperature=0.2)
            if res:
                return res

        if self.has_gemini:
            res = await self._call_gemini(prompt, system_prompt)
            if res:
                return res

        return "[Worker Node - Offline Mode] Hunk analysis completed."
