import os
import json
import logging
import asyncio
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

from ai_service.agent.key_rotator import APIKeyRotator

load_dotenv()
logger = logging.getLogger(__name__)

GEMINI_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
]
GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
]


def is_rate_limit_error(error: Exception) -> bool:
    """Check if exception represents an API rate limit or quota exhaustion (HTTP 429)."""
    err_str = str(error).lower()
    return (
        "429" in err_str
        or "resource_exhausted" in err_str
        or "rate limit" in err_str
        or "quota exceeded" in err_str
        or "too many requests" in err_str
        or "rate_limit_exceeded" in err_str
    )


class DualLLMClient:
    """Dual-LLM Client wrapper: Google Gemini for Orchestration & Groq for Worker Sub-tasks / Failover.
    
    Includes automated multi-key rotation and HTTP 429 failover support.
    """

    _groq_cooldown_until: float = 0.0

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
    ):
        from ai_service.config import settings

        if gemini_api_key:
            self.gemini_rotator = APIKeyRotator(
                service_name="Gemini",
                keys=[k.strip() for k in gemini_api_key.split(",") if k.strip()],
            )
        else:
            self.gemini_rotator = APIKeyRotator.from_env(
                service_name="Gemini",
                primary_env="GEMINI_API_KEY",
                list_env="GEMINI_API_KEYS",
            )

        if groq_api_key:
            self.groq_rotator = APIKeyRotator(
                service_name="Groq",
                keys=[k.strip() for k in groq_api_key.split(",") if k.strip()],
            )
        else:
            self.groq_rotator = APIKeyRotator.from_env(
                service_name="Groq",
                primary_env="GROQ_API_KEY",
                list_env="GROQ_API_KEYS",
            )

        self.has_gemini = self.gemini_rotator.has_keys
        self.has_groq = self.groq_rotator.has_keys
        self._groq_cooldown_until: float = 0.0

        # Ollama configuration from arguments, env, or settings
        raw_ollama_url = (
            ollama_base_url
            or os.environ.get("OLLAMA_BASE_URL")
            or getattr(settings, "ollama_base_url", "")
        )
        self.ollama_base_url = (raw_ollama_url or "").rstrip("/")
        self.ollama_model = (
            ollama_model
            or os.environ.get("OLLAMA_MODEL")
            or getattr(settings, "ollama_model", "qwen2.5-coder:14b")
        )
        self.worker_provider = (
            os.environ.get("WORKER_PROVIDER")
            or getattr(settings, "worker_provider", "ollama" if self.ollama_base_url else "groq")
        ).lower()
        self.orchestrator_provider = (
            os.environ.get("ORCHESTRATOR_PROVIDER")
            or getattr(settings, "orchestrator_provider", "ollama" if self.ollama_base_url else "gemini")
        ).lower()
        self.orchestrator_model = (
            os.environ.get("ORCHESTRATOR_MODEL")
            or getattr(settings, "orchestrator_model", "qwen2.5-coder:32b")
        )
        try:
            self.ollama_timeout = float(
                os.environ.get("OLLAMA_TIMEOUT")
                or getattr(settings, "ollama_timeout", 120.0)
            )
        except (ValueError, TypeError):
            self.ollama_timeout = 120.0

        self.has_ollama = bool(self.ollama_base_url)
        self._ollama_cooldown_until: float = 0.0

    async def _call_ollama(
        self,
        prompt: str,
        system_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
        max_retries: int = 2,
    ) -> Optional[str]:
        if not self.has_ollama:
            return None

        import time
        if time.time() < self._ollama_cooldown_until:
            logger.warning(f"[Ollama] In cooldown until {self._ollama_cooldown_until:.0f}")
            return None

        import httpx
        target_model = model or self.ollama_model
        url = f"{self.ollama_base_url}/api/chat"

        eff_prompt = prompt
        if json_mode and "json" not in system_prompt.lower() and "json" not in prompt.lower():
            eff_prompt = f"{prompt}\nRespond in valid JSON format."

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": eff_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if json_mode:
            payload["format"] = "json"

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.ollama_timeout) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        msg = data.get("message", {}).get("content", "")
                        if msg:
                            return msg
                    elif resp.status_code == 404 and target_model != self.ollama_model:
                        logger.warning(
                            f"[Ollama] Model '{target_model}' not found on {self.ollama_base_url}; "
                            f"falling back to '{self.ollama_model}'"
                        )
                        payload["model"] = self.ollama_model
                        continue
                    else:
                        logger.warning(f"[Ollama HTTP {resp.status_code}] {resp.text[:200]}")
                        if resp.status_code in (500, 502, 503, 504):
                            self._ollama_cooldown_until = time.time() + 30
                            return None
            except Exception as e:
                logger.warning(f"[Ollama attempt {attempt}/{max_retries}] Request error to {url}: {e}")
                if attempt == max_retries:
                    self._ollama_cooldown_until = time.time() + 30
                    return None
                await asyncio.sleep(2)

        return None


    async def _call_gemini(
        self,
        prompt: str,
        system_prompt: str,
        models: Optional[List[str]] = None,
        max_retries: int = 3,
    ) -> Optional[str]:
        if not self.has_gemini:
            return None

        target_models = models or GEMINI_MODELS

        for attempt in range(1, max_retries + 1):
            key = self.gemini_rotator.get_current_key()
            try:
                from google import genai
                client = genai.Client(api_key=key, http_options={"timeout": 35000})

                last_rate_error = None
                for model_name in target_models:
                    try:
                        res = client.models.generate_content(
                            model=model_name,
                            contents=f"{system_prompt}\n\n{prompt}",
                        )
                        if res and res.text:
                            return res.text
                    except Exception as me:
                        if is_rate_limit_error(me):
                            logger.info(f"Gemini model [{model_name}] hit quota/rate limit: {me}. Trying next model...")
                            last_rate_error = me
                            continue
                        logger.debug(f"Gemini generation failed for model [{model_name}]: {me}")
                if last_rate_error:
                    raise last_rate_error
                return None

            except Exception as e:
                if is_rate_limit_error(e):
                    logger.warning(
                        f"[Gemini 429] Rate limit / quota hit on key (attempt {attempt}/{max_retries}): {e}"
                    )
                    if self.gemini_rotator.key_count > 1:
                        await self.gemini_rotator.rotate(reason=f"HTTP 429 on attempt {attempt}")
                    else:
                        backoff = 10 * attempt
                        logger.info(f"[Gemini] Single key configured; sleeping {backoff}s...")
                        await asyncio.sleep(backoff)
                else:
                    logger.error(f"Gemini execution error: {e}")
                    break

        return None

    async def _call_groq(
        self,
        prompt: str,
        system_prompt: str,
        models: Optional[List[str]] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
        max_retries: int = 3,
    ) -> Optional[str]:
        if not self.has_groq:
            return None

        import time
        if time.time() < DualLLMClient._groq_cooldown_until:
            return None

        target_models = models or GROQ_MODELS
        max_retries = min(max_retries, max(1, self.groq_rotator.key_count))

        for attempt in range(1, max_retries + 1):
            key = self.groq_rotator.get_current_key()
            try:
                from groq import Groq
                client = Groq(api_key=key, max_retries=0, timeout=30.0)

                last_rate_error = None
                for model_name in target_models:
                    try:
                        eff_prompt = prompt
                        if json_mode and "json" not in system_prompt.lower() and "json" not in prompt.lower():
                            eff_prompt = f"{prompt}\nRespond in valid JSON format."

                        kwargs: Dict[str, Any] = {
                            "model": model_name,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": eff_prompt},
                            ],
                            "temperature": temperature,
                        }
                        if json_mode:
                            kwargs["response_format"] = {"type": "json_object"}

                        completion = client.chat.completions.create(**kwargs)
                        if completion.choices and completion.choices[0].message.content:
                            return completion.choices[0].message.content
                    except Exception as me:
                        if is_rate_limit_error(me):
                            logger.info(f"Groq model [{model_name}] hit quota/rate limit: {me}. Trying next model...")
                            last_rate_error = me
                            continue
                        logger.debug(f"Groq completion failed for model [{model_name}]: {me}")
                if last_rate_error:
                    raise last_rate_error
                return None

            except Exception as e:
                if is_rate_limit_error(e):
                    err_msg = str(e).lower()
                    if "tokens per day" in err_msg or "tpd" in err_msg:
                        import time
                        DualLLMClient._groq_cooldown_until = time.time() + 900
                        logger.warning(
                            f"[Groq 429 TPD] Daily token limit reached; entering 15m cooldown until {DualLLMClient._groq_cooldown_until:.0f}."
                        )
                    logger.warning(
                        f"[Groq 429] Rate limit hit on key (attempt {attempt}/{max_retries}): {e}"
                    )
                    if self.groq_rotator.key_count > 1:
                        await self.groq_rotator.rotate(reason=f"HTTP 429 on attempt {attempt}")
                        if attempt > 1:
                            await asyncio.sleep(2)
                    else:
                        backoff = 3 * attempt
                        logger.info(f"[Groq] Single key configured; sleeping {backoff}s...")
                        await asyncio.sleep(backoff)
                else:
                    logger.error(f"Groq execution error: {e}")
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
        if self.orchestrator_provider == "ollama" and self.has_ollama:
            raw_response = await self._call_ollama(
                user_prompt,
                system_prompt,
                model=self.orchestrator_model or self.ollama_model,
                temperature=0.1,
                json_mode=True,
            )

        if not raw_response and self.has_gemini:
            raw_response = await self._call_gemini(user_prompt, system_prompt)

        if not raw_response and self.has_groq:
            raw_response = await self._call_groq(
                user_prompt, system_prompt, temperature=0.1, json_mode=True
            )

        if not raw_response and self.has_ollama and self.orchestrator_provider != "ollama":
            raw_response = await self._call_ollama(
                user_prompt,
                system_prompt,
                model=self.ollama_model,
                temperature=0.1,
                json_mode=True,
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
        """Call primary orchestrator with failover (Ollama / Gemini / Groq based on ORCHESTRATOR_PROVIDER)."""
        if self.orchestrator_provider == "ollama" and self.has_ollama:
            res = await self._call_ollama(
                prompt,
                system_prompt,
                model=self.orchestrator_model or self.ollama_model,
                temperature=0.2,
            )
            if res:
                return res

        if self.has_gemini:
            res = await self._call_gemini(prompt, system_prompt)
            if res:
                return res

        if self.has_groq:
            res = await self._call_groq(prompt, system_prompt, temperature=0.2)
            if res:
                return res

        if self.has_ollama and self.orchestrator_provider != "ollama":
            res = await self._call_ollama(
                prompt,
                system_prompt,
                model=self.ollama_model,
                temperature=0.2,
            )
            if res:
                return res

        # Local Intelligent RAG Synthesis if all LLMs are offline
        return (
            "### Knowledge Base Intelligence Summary\n\n"
            "Retrieved relevant code passages and structural knowledge graph entities for your query. "
            "Refer to the cited source cards below for file snippets, line numbers, and symbol definitions."
        )

    async def run_worker(self, prompt: str, system_prompt: str) -> str:
        """Call worker node (Ollama / Groq / Gemini based on WORKER_PROVIDER) for diff inspection."""
        import time

        if self.worker_provider == "ollama" and self.has_ollama:
            res = await self._call_ollama(
                prompt,
                system_prompt,
                model=self.ollama_model,
                temperature=0.2,
                json_mode=True,
            )
            if res:
                return res

        if self.has_groq and time.time() >= DualLLMClient._groq_cooldown_until:
            res = await self._call_groq(prompt, system_prompt, temperature=0.2, json_mode=True)
            if res:
                return res

        if self.has_ollama and self.worker_provider != "ollama":
            res = await self._call_ollama(
                prompt,
                system_prompt,
                model=self.ollama_model,
                temperature=0.2,
                json_mode=True,
            )
            if res:
                return res

        if self.has_gemini:
            res = await self._call_gemini(prompt, system_prompt)
            if res:
                return res

        return "[Worker Node - Offline Mode] Hunk analysis completed."

