"""Agent prompts re-exports and builder functions.

Prompts are stored as modular files in `src.prompts` and can be customized at runtime.
"""

from src.prompts import (
    get_prompt,
    REACT_AGENT_SYSTEM_PROMPT as _DEFAULT_REACT,
    PR_ORCHESTRATOR_SYSTEM_PROMPT as _DEFAULT_PR_ORCH,
    PR_WORKER_SYSTEM_PROMPT as _DEFAULT_PR_WORKER,
)


def get_react_agent_prompt() -> str:
    return get_prompt("react_agent", _DEFAULT_REACT)


def get_pr_orchestrator_prompt() -> str:
    return get_prompt("pr_orchestrator", _DEFAULT_PR_ORCH)


def get_pr_worker_prompt() -> str:
    return get_prompt("pr_worker", _DEFAULT_PR_WORKER)


# Module-level references for backwards-compatibility
REACT_AGENT_SYSTEM_PROMPT = _DEFAULT_REACT
SYSTEM_ORCHESTRATOR_PROMPT = _DEFAULT_PR_ORCH
SYSTEM_WORKER_PROMPT = _DEFAULT_PR_WORKER


def build_orchestrator_prompt(
    repo_id: str,
    branch: str,
    changed_files: list[str],
    changed_symbols: list[str],
    blast_radius_json: str,
    diff_text: str,
    convention_violations: list[dict],
    semantic_context: str = "",
) -> str:
    return f"""
Target Repository: {repo_id} (branch: {branch})

Changed Files:
{changed_files}

Changed Symbols:
{changed_symbols}

Knowledge Base Blast Radius Impact (Graph DB):
{blast_radius_json}

Semantic Similarity Context (Vector DB):
{semantic_context}

Convention Violations:
{convention_violations}

Git Patch / Diff Content:
{diff_text}

Analyze the above change and provide:
1. Final Verdict: ACCEPT or SUGGEST
2. Summary rationale explaining blast radius & code impact
3. Line-level suggestion comments for maintaining team code quality.
"""
