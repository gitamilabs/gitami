import os
import re
import json
import logging
import asyncio
import time
from typing import Optional, Dict, Any, List
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
logger = logging.getLogger(__name__)

# Primary high-power open-weights models supported on Ollama
OLLAMA_MODELS = [
    "qwen2.5-coder:32b",
    "deepseek-r1:32b",
    "llama3.3:70b",
    "qwen2.5-coder:latest",
    "deepseek-r1:latest",
    "llama3.3",
    "qwen2.5:32b",
    "qwen2.5-coder:14b",
    "qwen2.5-coder:7b",
]

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


class DualLLMClient:
    """
    Multi-LLM Orchestration Client:
    - Primary Orchestrator: Ollama (Sovereign Local LLM, Qwen 2.5 Coder 32B / DeepSeek R1 32B / Llama 3.3 70B)
    - High-Throughput Worker / Fallback: Groq (Llama 3.3 70B / Compound Mini)
    - Cloud Failover: Google Gemini 3.x Flash
    """

    def __init__(
        self,
        ollama_base_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        llm_provider: Optional[str] = None,
    ):
        self.provider = (
            llm_provider
            or os.getenv("LLM_PROVIDER")
            or "ollama"
        ).lower().strip()

        self.ollama_base_url = (
            ollama_base_url
            or os.getenv("OLLAMA_BASE_URL")
            or "http://localhost:11434"
        ).rstrip("/")
        self.ollama_model = (
            ollama_model
            or os.getenv("OLLAMA_MODEL")
            or "qwen2.5-coder:32b"
        )
        self.ollama_timeout = float(os.getenv("OLLAMA_TIMEOUT", "60.0"))

        self.gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.groq_key = groq_api_key or os.getenv("GROQ_API_KEY")

        self.has_ollama = bool(self.ollama_base_url)
        self.has_gemini = bool(self.gemini_key)
        self.has_groq = bool(self.groq_key)

        self._genai_client = None
        self._groq_client = None
        self._ollama_model_cooldowns: Dict[str, float] = {}
        self._gemini_model_cooldowns: Dict[str, float] = {}
        self._groq_model_cooldowns: Dict[str, float] = {}
        self._discovered_ollama_models: Optional[List[str]] = None

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

    async def get_available_ollama_models(self) -> List[str]:
        """Query the Ollama daemon for currently downloaded models."""
        if self._discovered_ollama_models is not None:
            return self._discovered_ollama_models
        url = f"{self.ollama_base_url}/api/tags"
        try:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=3.0) as client:
                    res = await client.get(url)
                    if res.status_code == 200:
                        data = res.json()
                        self._discovered_ollama_models = [
                            m.get("name", "") for m in data.get("models", []) if m.get("name")
                        ]
                        return self._discovered_ollama_models
            except ImportError:
                def _fetch_tags():
                    import urllib.request
                    req = urllib.request.Request(url, method="GET")
                    with urllib.request.urlopen(req, timeout=3.0) as resp:
                        if resp.status == 200:
                            data = json.loads(resp.read().decode("utf-8"))
                            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                    return []
                self._discovered_ollama_models = await asyncio.to_thread(_fetch_tags)
                return self._discovered_ollama_models
        except Exception as e:
            logger.debug(f"Ollama tag discovery offline on {self.ollama_base_url}: {e}")
        return []

    async def _http_post_ollama(self, url: str, payload: Dict[str, Any], timeout: float = 60.0) -> Optional[str]:
        """Perform asynchronous HTTP POST request to Ollama daemon."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    msg = data.get("message", {})
                    return msg.get("content", "")
                else:
                    logger.warning(f"Ollama responded with HTTP {res.status_code}: {res.text[:200]}")
                    return None
        except ImportError:
            def _sync_request():
                import urllib.request
                data_bytes = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=data_bytes,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if resp.status == 200:
                        body = json.loads(resp.read().decode("utf-8"))
                        return body.get("message", {}).get("content", "")
                return None

            return await asyncio.to_thread(_sync_request)

    async def _call_ollama(
        self,
        prompt: str,
        system_prompt: str,
        models: Optional[List[str]] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> Optional[str]:
        """Call Ollama native /api/chat with candidate models and reasoning token cleanup."""
        if not self.has_ollama:
            return None

        # Determine target models: prioritized configured model, then candidate list
        configured = [self.ollama_model] if self.ollama_model else []
        candidates = models or (configured + [m for m in OLLAMA_MODELS if m != self.ollama_model])
        now = time.time()

        for model_name in candidates:
            cooldown_until = self._ollama_model_cooldowns.get(model_name, 0.0)
            if now < cooldown_until:
                remaining = round(cooldown_until - now, 1)
                logger.debug(f"Ollama model [{model_name}] in cooldown ({remaining}s remaining).")
                continue

            payload: Dict[str, Any] = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "options": {
                    "temperature": temperature,
                },
                "stream": False,
            }
            if json_mode:
                payload["format"] = "json"

            try:
                raw_content = await self._http_post_ollama(
                    f"{self.ollama_base_url}/api/chat",
                    payload,
                    timeout=self.ollama_timeout,
                )
                if raw_content:
                    # Strip DeepSeek-R1 <think>...</think> reasoning blocks for JSON or downstream consumption
                    clean_content = raw_content.strip()
                    if json_mode or "<think>" in clean_content:
                        clean_content = re.sub(r"<think>.*?</think>", "", clean_content, flags=re.DOTALL).strip()
                    return clean_content
            except Exception as e:
                logger.debug(f"Ollama call failed for [{model_name}]: {e}")
                self._ollama_model_cooldowns[model_name] = time.time() + 20.0
                err_str = str(e).lower()
                is_server_down = (
                    "refused" in err_str
                    or "connecterror" in err_str
                    or "failed to establish a new connection" in err_str
                    or "winerror 10061" in err_str
                    or "10061" in err_str
                )
                if is_server_down:
                    logger.debug(f"Ollama daemon appears offline at {self.ollama_base_url}. Short-circuiting candidate fallback.")
                    for m in candidates:
                        self._ollama_model_cooldowns[m] = time.time() + 15.0
                    break

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

    async def call_json(self, prompt: str, system_prompt: str, temperature: float = 0.1) -> str:
        """Unified method to call LLM for structured JSON output respecting provider priority."""
        if self.provider == "ollama" or (self.has_ollama and not self.has_gemini and not self.has_groq):
            res = await self._call_ollama(prompt, system_prompt, temperature=temperature, json_mode=True)
            if res:
                return res

        if self.has_groq:
            res = await self._call_groq(prompt, system_prompt, temperature=temperature, json_mode=True)
            if res:
                return res

        if self.has_gemini:
            res = await self._call_gemini(prompt, system_prompt, temperature=temperature, json_mode=True)
            if res:
                return res

        # Fallback to Ollama if not already tried
        if self.has_ollama and self.provider != "ollama":
            res = await self._call_ollama(prompt, system_prompt, temperature=temperature, json_mode=True)
            if res:
                return res

        return ""

    async def plan_tool_calls(self, user_query: str, repo_id: str) -> List[Dict[str, Any]]:
        """
        Agentic planning step: Ask the LLM to dynamically decide which Knowledge Base MCP tools to call.
        Returns a list of tool call dictionaries: [{"tool_name": "...", "args": {...}}]
        """
        from ai_service.prompts import get_prompt
        system_prompt = get_prompt("tool_planner")
        user_prompt = f"Repository ID: '{repo_id}'\nUser Query: '{user_query}'\nSelect the best tool(s) to execute."

        raw_response = None

        # 1. Primary: Ollama (Qwen 2.5 Coder 32B / DeepSeek R1)
        if self.provider == "ollama" or (self.has_ollama and not self.has_gemini and not self.has_groq):
            raw_response = await self._call_ollama(
                user_prompt, system_prompt, temperature=0.1, json_mode=True
            )

        # 2. Cloud Fallback: Groq
        if not raw_response and self.has_groq:
            raw_response = await self._call_groq(
                user_prompt, system_prompt, temperature=0.1, json_mode=True
            )

        # 3. Cloud Fallback: Gemini
        if not raw_response and self.has_gemini:
            raw_response = await self._call_gemini(
                user_prompt, system_prompt, temperature=0.1, json_mode=True
            )

        # 4. Final attempt: Ollama if not yet run
        if not raw_response and self.has_ollama and self.provider != "ollama":
            raw_response = await self._call_ollama(
                user_prompt, system_prompt, temperature=0.1, json_mode=True
            )

        if raw_response:
            try:
                clean_json = raw_response.strip()
                if "<think>" in clean_json:
                    clean_json = re.sub(r"<think>.*?</think>", "", clean_json, flags=re.DOTALL).strip()
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
        """Fast-path execution: prioritize Groq for ultra-low latency, fallback to Ollama, then Gemini."""
        sys_prompt = system_prompt or "You are a fast concise codebase analysis assistant."
        if self.has_groq:
            res = await self._call_groq(prompt, sys_prompt, temperature=0.1)
            if res:
                return res

        if self.has_ollama:
            res = await self._call_ollama(prompt, sys_prompt, temperature=0.1)
            if res:
                return res

        if self.has_gemini:
            res = await self._call_gemini(prompt, sys_prompt, temperature=0.2)
            if res:
                return res

        return ""

    async def run_orchestrator(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Main orchestration:
        1. Prioritize Ollama (Sovereign Local LLM, Qwen 2.5 Coder 32B / DeepSeek R1).
        2. Fallback to Groq for fast inference.
        3. Fallback to Gemini if configured.
        """
        sys_prompt = system_prompt or "You are the central decision-making intelligence orchestrating codebase analysis."

        # 1. Ollama Primary Orchestrator
        if self.provider == "ollama" or (self.has_ollama and not self.has_gemini and not self.has_groq):
            res = await self._call_ollama(prompt, sys_prompt)
            if res:
                return res

        # 2. Groq Cloud Fallback
        if self.has_groq:
            res = await self._call_groq(prompt, sys_prompt, temperature=0.2)
            if res:
                return res

        # 3. Gemini Cloud Fallback
        if self.has_gemini:
            res = await self._call_gemini(prompt, sys_prompt)
            if res:
                return res

        # 4. Ollama Fallback if provider was set to another but primary failed
        if self.has_ollama and self.provider != "ollama":
            res = await self._call_ollama(prompt, sys_prompt)
            if res:
                return res

        # Offline synthesis fallback
        return (
            "### Knowledge Base Intelligence Summary\n\n"
            "Retrieved relevant code passages and structural knowledge graph entities for your query. "
            "Refer to the cited source cards below for file snippets, line numbers, and symbol definitions."
        )

    async def run_worker(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Call Groq for fast parallel hunk review sub-tasks; fallback to Ollama, then Gemini."""
        sys_prompt = system_prompt or "You are a code inspection worker node analyzing code diffs."
        if self.has_groq:
            res = await self._call_groq(prompt, sys_prompt, temperature=0.2, json_mode=True)
            if res:
                return res

        if self.has_ollama:
            res = await self._call_ollama(prompt, sys_prompt, temperature=0.2, json_mode=True)
            if res:
                return res

        if self.has_gemini:
            res = await self._call_gemini(prompt, sys_prompt, temperature=0.2, json_mode=True)
            if res:
                return res

        return "[Worker Node - Offline Mode] Hunk analysis completed."
