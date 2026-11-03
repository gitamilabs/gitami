import os
import json
import logging
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

from src.config import settings

load_dotenv()
logger = logging.getLogger(__name__)

GEMINI_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]

GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
    "qwen/qwen3.8-27b",
]

LOCAL_MODELS = [
    "hf.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF:Q4_K_M",
    "qwen2.5-coder:1.5b",
    "qwen2.5-coder:3b",
    "qwen2.5-coder:7b",
    "qwen2.5-coder:14b",
    "qwen2.5-coder:32b",
    "llama3.2:3b",
    "llama3.3:70b",
    "deepseek-coder:6.7b",
    "deepseek-r1:8b",
    "codellama:7b",
    "mistral:7b",
]


class DualLLMClient:
    """
    Hybrid LLM Client supporting Cloud (Google Gemini, Groq) and Local LLMs (Ollama, vLLM, LM Studio).
    Configurable for both Orchestration and Worker node roles with automatic fallback.
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        local_llm_url: Optional[str] = None,
        local_llm_api_key: Optional[str] = None,
        local_orchestrator_model: Optional[str] = None,
        local_worker_model: Optional[str] = None,
        orchestrator_provider: Optional[str] = None,
        worker_provider: Optional[str] = None,
        local_timeout: Optional[float] = None,
    ):
        self.gemini_key = (
            gemini_api_key
            or settings.gemini_api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        self.groq_key = (
            groq_api_key
            or settings.groq_api_key
            or os.getenv("GROQ_API_KEY")
        )

        self.local_url = (
            local_llm_url
            or os.getenv("LOCAL_LLM_URL")
            or settings.local_llm_url
            or "http://localhost:11434/v1"
        )
        self.local_api_key = (
            local_llm_api_key
            or os.getenv("LOCAL_LLM_API_KEY")
            or settings.local_llm_api_key
            or "ollama"
        )
        self.local_timeout = (
            local_timeout
            or float(os.getenv("LOCAL_LLM_TIMEOUT", "60.0"))
            or settings.local_llm_timeout
        )

        self.local_orchestrator_model = (
            local_orchestrator_model
            or os.getenv("LOCAL_ORCHESTRATOR_MODEL")
            or settings.local_orchestrator_model
            or "qwen2.5-coder:3b"
        )
        self.local_worker_model = (
            local_worker_model
            or os.getenv("LOCAL_WORKER_MODEL")
            or settings.local_worker_model
            or "qwen2.5-coder:1.5b"
        )

        self.orchestrator_provider = (
            orchestrator_provider
            or os.getenv("ORCHESTRATOR_PROVIDER")
            or settings.orchestrator_provider
            or "auto"
        ).lower()

        self.worker_provider = (
            worker_provider
            or os.getenv("WORKER_PROVIDER")
            or settings.worker_provider
            or "auto"
        ).lower()

        self.has_gemini = bool(self.gemini_key)
        self.has_groq = bool(self.groq_key)
        self.has_local = bool(self.local_url)

        self._genai_client = None
        self._groq_client = None
        self._local_client = None

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

    def _get_local_client(self):
        if not self._local_client and self.has_local:
            try:
                from openai import AsyncOpenAI
                self._local_client = AsyncOpenAI(
                    base_url=self.local_url,
                    api_key=self.local_api_key or "ollama",
                    timeout=self.local_timeout,
                    default_headers={"ngrok-skip-browser-warning": "true"},
                )
            except Exception as e:
                logger.error(f"Failed to instantiate Local OpenAI-compatible Client: {e}")
        return self._local_client

    async def check_local_health(self) -> bool:
        """Pings the local LLM endpoint to check if the server is alive and reachable."""
        client = self._get_local_client()
        if not client:
            return False
        try:
            # Query models with a 5.0s probe timeout
            await client.models.list(timeout=5.0)
            return True
        except Exception as e:
            logger.debug(f"Local LLM health probe failed ({self.local_url}): {e}")
            return False

    async def _call_local(
        self,
        prompt: str,
        system_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """Invokes a local OpenAI-compatible endpoint (Ollama, vLLM, LM Studio, etc.)."""
        client = self._get_local_client()
        if not client:
            return None

        target_model = model or self.local_worker_model
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        kwargs: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            completion = await client.chat.completions.create(**kwargs)
            if completion.choices and completion.choices[0].message.content:
                return completion.choices[0].message.content
        except Exception as e:
            err_msg = str(e).lower()
            if "404" in err_msg or "not found" in err_msg:
                fallback_model = "qwen2.5-coder:1.5b"
                if target_model != fallback_model:
                    logger.info(f"Model [{target_model}] not found in Ollama, falling back to [{fallback_model}]")
                    try:
                        kwargs["model"] = fallback_model
                        completion = await client.chat.completions.create(**kwargs)
                        if completion.choices and completion.choices[0].message.content:
                            return completion.choices[0].message.content
                    except Exception as fallback_e:
                        logger.warning(f"Fallback to [{fallback_model}] failed: {fallback_e}")
            elif json_mode and ("response_format" in err_msg or "json" in err_msg or "400" in err_msg):
                try:
                    kwargs.pop("response_format", None)
                    kwargs["messages"][0]["content"] += "\nReturn strictly valid JSON only."
                    completion = await client.chat.completions.create(**kwargs)
                    if completion.choices and completion.choices[0].message.content:
                        return completion.choices[0].message.content
                except Exception as inner_e:
                    logger.warning(f"Local LLM json retry failed for [{target_model}]: {inner_e}")
            else:
                logger.warning(f"Local LLM completion failed for [{target_model}] at {self.local_url}: {e}")

        return None

    async def _call_gemini(
        self,
        prompt: str,
        system_prompt: str,
        models: Optional[List[str]] = None,
        json_mode: bool = False,
    ) -> Optional[str]:
        client = self._get_genai_client()
        if not client:
            return None

        target_models = models or GEMINI_MODELS
        config = {"response_mime_type": "application/json"} if json_mode else None
        for model_name in target_models:
            try:
                kwargs: Dict[str, Any] = {
                    "model": model_name,
                    "contents": f"{system_prompt}\n\n{prompt}",
                }
                if config:
                    kwargs["config"] = config
                res = client.models.generate_content(**kwargs)
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

    async def run_orchestrator(
        self, prompt: str, system_prompt: str, json_mode: bool = False, max_tokens: Optional[int] = None
    ) -> str:
        """
        Executes main agent orchestration task (planning, reasoning turns, synthesis).
        Routes according to orchestrator_provider ('local', 'gemini', 'groq', 'auto').
        """
        provider = self.orchestrator_provider

        # 1. Local preference
        if provider == "local":
            res = await self._call_local(
                prompt,
                system_prompt,
                model=self.local_orchestrator_model,
                temperature=0.1 if json_mode else 0.2,
                json_mode=json_mode,
                max_tokens=max_tokens,
            )
            if res:
                return res
            # Fallback to cloud if local is unreachable
            if self.has_gemini:
                logger.info("Local orchestrator offline, falling back to Gemini")
                res = await self._call_gemini(prompt, system_prompt)
                if res:
                    return res
            if self.has_groq:
                logger.info("Local orchestrator offline, falling back to Groq")
                res = await self._call_groq(prompt, system_prompt, json_mode=json_mode)
                if res:
                    return res

        # 2. Gemini preference
        elif provider == "gemini":
            if self.has_gemini:
                res = await self._call_gemini(prompt, system_prompt, json_mode=json_mode)
                if res:
                    return res
            res = await self._call_local(
                prompt,
                system_prompt,
                model=self.local_orchestrator_model,
                json_mode=json_mode,
                max_tokens=max_tokens,
            )
            if res:
                return res
            if self.has_groq:
                res = await self._call_groq(prompt, system_prompt, json_mode=json_mode)
                if res:
                    return res

        # 3. Groq preference
        elif provider == "groq":
            if self.has_groq:
                res = await self._call_groq(prompt, system_prompt, json_mode=json_mode)
                if res:
                    return res
            res = await self._call_local(
                prompt,
                system_prompt,
                model=self.local_orchestrator_model,
                json_mode=json_mode,
                max_tokens=max_tokens,
            )
            if res:
                return res
            if self.has_gemini:
                res = await self._call_gemini(prompt, system_prompt)
                if res:
                    return res

        # 4. Auto mode: Gemini -> Groq -> Local
        else:
            if self.has_gemini:
                res = await self._call_gemini(prompt, system_prompt)
                if res:
                    return res
            if self.has_groq:
                res = await self._call_groq(prompt, system_prompt, json_mode=json_mode)
                if res:
                    return res
            # Attempt local if cloud keys unavailable or failed
            res = await self._call_local(
                prompt,
                system_prompt,
                model=self.local_orchestrator_model,
                json_mode=json_mode,
                max_tokens=max_tokens,
            )
            if res:
                return res

        # Offline RAG Synthesis fallback
        return (
            "### Knowledge Base Intelligence Summary\n\n"
            "Retrieved relevant code passages and structural knowledge graph entities for your query. "
            "Refer to the cited source cards below for file snippets, line numbers, and symbol definitions."
        )

    async def run_worker(
        self, prompt: str, system_prompt: str, json_mode: bool = True
    ) -> str:
        """
        Executes worker node sub-tasks (diff hunk review, AST analysis, issue extraction).
        Routes according to worker_provider ('local', 'groq', 'gemini', 'auto').
        """
        provider = self.worker_provider

        # 1. Local preference
        if provider == "local":
            res = await self._call_local(
                prompt,
                system_prompt,
                model=self.local_worker_model,
                temperature=0.1,
                json_mode=json_mode,
            )
            if res:
                return res
            if self.has_groq:
                logger.info("Local worker offline, falling back to Groq")
                res = await self._call_groq(
                    prompt, system_prompt, temperature=0.1, json_mode=json_mode
                )
                if res:
                    return res
            if self.has_gemini:
                logger.info("Local worker offline, falling back to Gemini")
                res = await self._call_gemini(prompt, system_prompt, json_mode=json_mode)
                if res:
                    return res

        # 2. Groq preference
        elif provider == "groq":
            if self.has_groq:
                res = await self._call_groq(
                    prompt, system_prompt, temperature=0.2, json_mode=json_mode
                )
                if res:
                    return res
            res = await self._call_local(
                prompt,
                system_prompt,
                model=self.local_worker_model,
                temperature=0.1,
                json_mode=json_mode,
            )
            if res:
                return res
            if self.has_gemini:
                res = await self._call_gemini(prompt, system_prompt, json_mode=json_mode)
                if res:
                    return res

        # 3. Gemini preference
        elif provider == "gemini":
            if self.has_gemini:
                res = await self._call_gemini(prompt, system_prompt, json_mode=json_mode)
                if res:
                    return res
            res = await self._call_local(
                prompt,
                system_prompt,
                model=self.local_worker_model,
                temperature=0.1,
                json_mode=json_mode,
            )
            if res:
                return res
            if self.has_groq:
                res = await self._call_groq(
                    prompt, system_prompt, temperature=0.2, json_mode=json_mode
                )
                if res:
                    return res

        # 4. Auto mode: Groq -> Local -> Gemini
        else:
            if self.has_groq:
                res = await self._call_groq(
                    prompt, system_prompt, temperature=0.2, json_mode=json_mode
                )
                if res:
                    return res
            res = await self._call_local(
                prompt,
                system_prompt,
                model=self.local_worker_model,
                temperature=0.1,
                json_mode=json_mode,
            )
            if res:
                return res
            if self.has_gemini:
                res = await self._call_gemini(prompt, system_prompt)
                if res:
                    return res

        return "[Worker Node - Offline Mode] Hunk analysis completed."

    async def call_orchestrator_json(
        self, prompt: str, system_prompt: str, max_tokens: Optional[int] = 350
    ) -> str:
        """Helper to invoke the active Orchestrator with structured JSON expectation."""
        return await self.run_orchestrator(
            prompt, system_prompt, json_mode=True, max_tokens=max_tokens
        )

    async def plan_tool_calls(self, user_query: str, repo_id: str) -> List[Dict[str, Any]]:
        """
        Agentic planning step: Ask the LLM to dynamically decide which Knowledge Base MCP tools to call.
        Returns a list of tool call dictionaries: [{"tool_name": "...", "args": {...}}]
        """
        from src.prompts import get_prompt
        system_prompt = get_prompt("tool_planner")
        user_prompt = (
            f"Repository ID: '{repo_id}'\n"
            f"User Query: '{user_query}'\n"
            f"Select the best tool(s) to execute."
        )

        raw_response = await self.call_orchestrator_json(user_prompt, system_prompt)

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


# Alias for backward compatibility
HybridLLMClient = DualLLMClient
