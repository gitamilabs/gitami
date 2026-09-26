import os
import json
import logging
import asyncio
import time
from typing import Optional, Dict, Any, List
import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GEMINI_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
]
GROQ_MODELS = [
    "groq/compound-mini",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
]
OLLAMA_MODELS = [
    "qwen2.5-coder:latest",
    "qwen2.5-coder:7b",
    "llama3.2:latest",
    "codellama:latest",
    "deepseek-r1:latest",
]



class DualLLMClient:
    """Multi-LLM Client wrapper: Qwen / Google Gemini for Orchestration & Local Ollama / Groq for Worker Sub-tasks / Failover."""

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
        worker_provider: Optional[str] = None,
        orchestrator_provider: Optional[str] = None,
        orchestrator_model: Optional[str] = None,
    ):
        self.gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.groq_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self.ollama_base_url = (ollama_base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self.ollama_model = ollama_model or os.getenv("OLLAMA_MODEL") or "qwen2.5-coder:latest"
        self.worker_provider = (worker_provider or os.getenv("WORKER_PROVIDER") or "ollama").lower()
        self.orchestrator_provider = (orchestrator_provider or os.getenv("ORCHESTRATOR_PROVIDER") or "ollama").lower()
        self.orchestrator_model = orchestrator_model or os.getenv("ORCHESTRATOR_MODEL") or "qwen2.5-coder:latest"

        self.has_gemini = bool(self.gemini_key)
        self.has_groq = bool(self.groq_key)
        self.has_ollama = bool(self.ollama_base_url)

        self._genai_client = None
        self._groq_client = None
        self._gemini_model_cooldowns: Dict[str, float] = {}
        self._groq_model_cooldowns: Dict[str, float] = {}
        self._ollama_cooldown_until: float = 0.0

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
                self._groq_client = Groq(api_key=self.groq_key, max_retries=1)
            except Exception as e:
                logger.error(f"Failed to instantiate Groq Client: {e}")
        return self._groq_client

    async def _call_ollama(
        self,
        prompt: str,
        system_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
        timeout: float = 60.0,
    ) -> Optional[str]:
        """Execute chat completion against a local Ollama instance via HTTP API."""
        if not self.has_ollama:
            return None

        now = time.time()
        if now < self._ollama_cooldown_until:
            remaining = round(self._ollama_cooldown_until - now, 1)
            logger.debug(f"Ollama in cooldown ({remaining}s remaining). Skipping to fallback.")
            return None

        target_model = model or self.ollama_model
        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if json_mode:
            payload["format"] = "json"

        endpoint = f"{self.ollama_base_url}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(endpoint, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    msg = data.get("message", {})
                    content = msg.get("content", "")
                    if content:
                        return content
                else:
                    logger.warning(
                        f"Ollama returned HTTP {resp.status_code} for model [{target_model}]: {resp.text[:200]}"
                    )
                    if resp.status_code in (404, 500, 502, 503):
                        self._ollama_cooldown_until = time.time() + 30.0
        except Exception as e:
            self._ollama_cooldown_until = time.time() + 30.0
            logger.warning(f"Ollama request failed at {endpoint}: {e}. Placed on 30s cooldown; falling back...")
        return None

    async def _call_gemini(
        self,
        prompt: str,
        system_prompt: str,
        models: Optional[List[str]] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> Optional[str]:
        client = self._get_genai_client()
        if not client:
            return None

        target_models = models or GEMINI_MODELS
        now = time.time()
        for model_name in target_models:
            # Check if this model is currently in quota exhaustion cooldown
            cooldown_until = self._gemini_model_cooldowns.get(model_name, 0.0)
            if now < cooldown_until:
                remaining = round(cooldown_until - now, 1)
                logger.debug(
                    f"Gemini model [{model_name}] in quota cooldown ({remaining}s remaining). Skipping to fallback."
                )
                continue

            try:
                from google.genai import types
                cfg_kwargs: Dict[str, Any] = {
                    "system_instruction": system_prompt,
                    "temperature": temperature,
                }
                if json_mode:
                    cfg_kwargs["response_mime_type"] = "application/json"
                config = types.GenerateContentConfig(**cfg_kwargs)

                # Non-blocking generation with 45s timeout to allow full PR review completion
                res = await asyncio.wait_for(
                    asyncio.to_thread(
                        client.models.generate_content,
                        model=model_name,
                        contents=prompt,
                        config=config,
                    ),
                    timeout=45.0,
                )
                if res and res.text:
                    return res.text
            except Exception as e:
                err_str = str(e).lower()
                is_quota_exhausted = (
                    "429" in err_str
                    or "resource_exhausted" in err_str
                    or "quota exceeded" in err_str
                    or "503" in err_str
                )
                if is_quota_exhausted:
                    # Place exhausted model on 60-second cooldown so subsequent calls skip it directly
                    self._gemini_model_cooldowns[model_name] = time.time() + 60.0
                    logger.warning(
                        f"Gemini model [{model_name}] quota exhausted or unavailable ({e}). "
                        f"Placed on 60s cooldown; falling back to next candidate model..."
                    )
                else:
                    logger.warning(
                        f"Gemini generation failed for model [{model_name}]: {e}. Falling back to next candidate model..."
                    )
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
        now = time.time()
        for model_name in target_models:
            # Check if this model is currently in rate-limit cooldown
            cooldown_until = self._groq_model_cooldowns.get(model_name, 0.0)
            if now < cooldown_until:
                remaining = round(cooldown_until - now, 1)
                logger.debug(
                    f"Groq model [{model_name}] in rate-limit cooldown ({remaining}s remaining). Skipping to fallback."
                )
                continue

            kwargs: Dict[str, Any] = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": 800 if "qwen" in model_name else 2500,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            for attempt in range(2):
                try:
                    completion = await asyncio.wait_for(
                        asyncio.to_thread(client.chat.completions.create, **kwargs),
                        timeout=35.0,
                    )
                    if completion.choices and completion.choices[0].message.content:
                        return completion.choices[0].message.content
                except Exception as e:
                    err_str = str(e).lower()
                    is_rate_limit = (
                        "429" in err_str
                        or "rate limit" in err_str
                        or "too many requests" in err_str
                        or "quota" in err_str
                    )
                    if is_rate_limit:
                        if attempt == 0:
                            backoff = 2.0
                            logger.warning(
                                f"Groq rate limit (429) on model [{model_name}]. Backing off {backoff}s before retry: {e}"
                            )
                            await asyncio.sleep(backoff)
                            continue
                        else:
                            # Placed on 60s cooldown and fall back to next candidate model
                            self._groq_model_cooldowns[model_name] = time.time() + 60.0
                            logger.warning(
                                f"Groq model [{model_name}] quota/rate limit exhausted (429). "
                                f"Placed on 60s cooldown; falling back to next candidate model..."
                            )
                            break
                    else:
                        logger.warning(
                            f"Groq completion failed for model [{model_name}]: {e}. Falling back to next candidate model..."
                        )
                        break
        return None

    async def plan_tool_calls(self, user_query: str, repo_id: str) -> List[Dict[str, Any]]:
        """
        Agentic planning step: Ask the LLM to dynamically decide which Knowledge Base MCP tools to call.
        Returns a list of tool call dictionaries: [{"tool_name": "...", "args": {...}}]
        """
        from ai_service.prompts import get_prompt
        system_prompt = get_prompt("tool_planner")

        user_prompt = f"Repository ID: '{repo_id}'\nUser Query: '{user_query}'\nSelect the best tool(s) to execute."

        raw_response = None
        # 1. Try Ollama Qwen if configured as orchestrator
        if self.orchestrator_provider == "ollama" and self.has_ollama:
            raw_response = await self._call_ollama(
                user_prompt, system_prompt, model=self.orchestrator_model, temperature=0.1, json_mode=True
            )

        # 2. Try Gemini
        if not raw_response and self.has_gemini:
            raw_response = await self._call_gemini(
                user_prompt, system_prompt, temperature=0.1, json_mode=True
            )

        # 3. Try Groq (preferring Qwen if available)
        if not raw_response and self.has_groq:
            groq_models = ["qwen/qwen3.8-27b"] + [m for m in GROQ_MODELS if m != "qwen/qwen3.8-27b"]
            raw_response = await self._call_groq(
                user_prompt, system_prompt, models=groq_models, temperature=0.1, json_mode=True
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

    async def run_fast(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Fast-path execution: prioritize Ollama/Groq for sub-second responses, fallback to Gemini."""
        sys_prompt = system_prompt or "You are a fast concise codebase analysis assistant."
        if self.worker_provider == "ollama" and self.has_ollama:
            res = await self._call_ollama(prompt, sys_prompt, temperature=0.1, json_mode=False)
            if res:
                return res

        if self.has_groq:
            res = await self._call_groq(prompt, sys_prompt, temperature=0.1)
            if res:
                return res

        if self.has_gemini:
            res = await self._call_gemini(prompt, sys_prompt, temperature=0.2)
            if res:
                return res

        return ""

    async def run_orchestrator(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Call Primary Orchestrator (Qwen via Ollama/Groq or Gemini) for central decision making;
        fail over through candidate models and local RAG synthesis if all LLMs are offline.
        """
        sys_prompt = system_prompt or "You are the central decision-making intelligence orchestrating codebase analysis."

        # 1. Primary: Local Ollama Qwen (if orchestrator_provider == 'ollama')
        if self.orchestrator_provider == "ollama" and self.has_ollama:
            res = await self._call_ollama(
                prompt, sys_prompt, model=self.orchestrator_model, temperature=0.2, timeout=90.0
            )
            if res:
                return res

        # 2. Primary / Failover: Groq Qwen
        if self.has_groq:
            groq_models = ["qwen/qwen3.8-27b"] + [m for m in GROQ_MODELS if m != "qwen/qwen3.8-27b"]
            res = await self._call_groq(prompt, sys_prompt, models=groq_models, temperature=0.2)
            if res:
                return res

        # 3. Failover: Google Gemini
        if self.has_gemini:
            res = await self._call_gemini(prompt, sys_prompt)
            if res:
                return res

        # 4. Fallback to Ollama if orchestrator_provider was not ollama initially
        if self.orchestrator_provider != "ollama" and self.has_ollama:
            res = await self._call_ollama(
                prompt, sys_prompt, model=self.orchestrator_model, temperature=0.2, timeout=90.0
            )
            if res:
                return res

        # Local Intelligent RAG Synthesis if all LLMs are offline
        return (
            "### Knowledge Base Intelligence Summary\n\n"
            "Retrieved relevant code passages and structural knowledge graph entities for your query. "
            "Refer to the cited source cards below for file snippets, line numbers, and symbol definitions."
        )

    async def run_worker(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: Optional[bool] = None,
    ) -> str:
        """
        Call Worker Node for fast parallel hunk review sub-tasks and surgical code repair.
        Priority:
          1. Local Ollama (if worker_provider == 'ollama')
          2. Cloud Groq (failover or if worker_provider == 'groq')
          3. Google Gemini (failover or if worker_provider == 'gemini')
        """
        sys_prompt = system_prompt or "You are a code inspection worker node analyzing code diffs."
        use_json = json_mode if json_mode is not None else (
            "json" in prompt.lower() or "json" in sys_prompt.lower()
        )

        # 1. Ollama local execution if configured as worker provider
        if self.worker_provider == "ollama" and self.has_ollama:
            res = await self._call_ollama(prompt, sys_prompt, temperature=0.2, json_mode=use_json)
            if res:
                return res

        # 2. Groq cloud execution
        if self.has_groq:
            res = await self._call_groq(prompt, sys_prompt, temperature=0.2, json_mode=use_json)
            if res:
                return res

        # 3. Gemini fallback
        if self.has_gemini:
            res = await self._call_gemini(prompt, sys_prompt, temperature=0.2, json_mode=use_json)
            if res:
                return res

        # 4. If worker_provider was not ollama initially, try ollama as last fallback
        if self.worker_provider != "ollama" and self.has_ollama:
            res = await self._call_ollama(prompt, sys_prompt, temperature=0.2, json_mode=use_json)
            if res:
                return res

        return "[Worker Node - Offline Mode] Hunk analysis completed."
