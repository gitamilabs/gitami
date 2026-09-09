"""Central registry and management for AI system prompts."""

from pathlib import Path
from typing import Dict, Any, List, Optional
import importlib
import logging

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent

# Registry mapping prompt_key -> module_name
PROMPT_MODULES = {
    "react_agent": "src.prompts.react_agent",
    "chat_synthesis": "src.prompts.chat_synthesis",
    "context_compressor": "src.prompts.context_compressor",
    "tool_planner": "src.prompts.tool_planner",
    "pr_orchestrator": "src.prompts.pr_orchestrator",
    "pr_worker": "src.prompts.pr_worker",
    "pr_reviewer_worker": "src.prompts.pr_reviewer_worker",
    "fixer_orchestrator": "src.prompts.fixer_orchestrator",
    "fixer_worker": "src.prompts.fixer_worker",
}


def _get_module(key: str):
    if key not in PROMPT_MODULES:
        return None
    try:
        mod_name = PROMPT_MODULES[key]
        return importlib.import_module(mod_name)
    except Exception as e:
        logger.error(f"Failed to import prompt module {key}: {e}")
        return None


def get_prompt(key: str, default: str = "") -> str:
    """Get the active prompt string for a key."""
    mod = _get_module(key)
    if mod and hasattr(mod, "PROMPT"):
        return getattr(mod, "PROMPT")
    return default


def get_prompt_info(key: str) -> Optional[Dict[str, Any]]:
    """Get full metadata for a prompt."""
    mod = _get_module(key)
    if not mod:
        return None
    return {
        "key": key,
        "title": getattr(mod, "TITLE", key.replace("_", " ").title()),
        "description": getattr(mod, "DESCRIPTION", ""),
        "prompt": getattr(mod, "PROMPT", ""),
        "default_prompt": getattr(mod, "DEFAULT_PROMPT", getattr(mod, "PROMPT", "")),
        "is_customized": getattr(mod, "PROMPT", "") != getattr(mod, "DEFAULT_PROMPT", ""),
    }


def list_prompts() -> List[Dict[str, Any]]:
    """List all registered prompts and their metadata."""
    results = []
    for key in PROMPT_MODULES:
        info = get_prompt_info(key)
        if info:
            results.append(info)
    return results


def update_prompt(key: str, new_text: str) -> Optional[Dict[str, Any]]:
    """Update a prompt in memory and persist it to its .py file."""
    if key not in PROMPT_MODULES:
        return None
    mod = _get_module(key)
    if not mod:
        return None

    file_path = PROMPTS_DIR / f"{key}.py"
    title = getattr(mod, "TITLE", key.replace("_", " ").title())
    description = getattr(mod, "DESCRIPTION", "")
    default_prompt = getattr(mod, "DEFAULT_PROMPT", getattr(mod, "PROMPT", ""))

    content = f'''"""System Prompt - {title}."""

TITLE = {repr(title)}
DESCRIPTION = {repr(description)}

DEFAULT_PROMPT = {repr(default_prompt)}

PROMPT = {repr(new_text)}
'''
    try:
        file_path.write_text(content, encoding="utf-8")
        # Update in-memory module
        mod.PROMPT = new_text
        return get_prompt_info(key)
    except Exception as e:
        logger.error(f"Failed to save prompt file {file_path}: {e}")
        return None


def reset_prompt(key: str) -> Optional[Dict[str, Any]]:
    """Reset a prompt to its original default text."""
    mod = _get_module(key)
    if not mod:
        return None
    default_prompt = getattr(mod, "DEFAULT_PROMPT", "")
    return update_prompt(key, default_prompt)


# Convenient lazy accessors/re-exports
from src.prompts.react_agent import PROMPT as REACT_AGENT_SYSTEM_PROMPT
from src.prompts.chat_synthesis import PROMPT as CHAT_SYNTHESIS_SYSTEM_PROMPT
from src.prompts.context_compressor import PROMPT as CONTEXT_COMPRESSOR_SYSTEM_PROMPT
from src.prompts.tool_planner import PROMPT as TOOL_PLANNER_SYSTEM_PROMPT
from src.prompts.pr_orchestrator import PROMPT as PR_ORCHESTRATOR_SYSTEM_PROMPT
from src.prompts.pr_worker import PROMPT as PR_WORKER_SYSTEM_PROMPT
from src.prompts.pr_reviewer_worker import PROMPT as PR_REVIEWER_WORKER_SYSTEM_PROMPT
from src.prompts.fixer_orchestrator import PROMPT as FIXER_ORCHESTRATOR_SYSTEM_PROMPT
from src.prompts.fixer_worker import PROMPT as FIXER_WORKER_SYSTEM_PROMPT
