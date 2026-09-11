"""Agent prompts re-exports and builder functions.

Prompts are stored as modular files in `ai_service.prompts` and can be customized at runtime.
"""

from ai_service.prompts import (
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


import json


def build_orchestrator_prompt(
    repo_id: str,
    branch: str,
    changed_files: list[str],
    changed_symbols: list[str],
    blast_radius_json: str,
    diff_text: str,
    convention_violations: list[dict],
    semantic_context: str = "",
    cpg_context: str = "",
    candidate_issues: list[dict] = None,
) -> str:
    cpg_section = f"\nJoern CPG Structural Control-Flow & Call Site Analysis:\n{cpg_context}\n" if cpg_context else ""
    candidate_section = (
        f"\nCandidate Issues from Deep Code Inspector (Worker Node):\n{json.dumps(candidate_issues or [], indent=2)}\n"
        if candidate_issues
        else ""
    )

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
{cpg_section}
Static Convention Violations:
{convention_violations}
{candidate_section}
Git Patch / Diff Content:
{diff_text}

Instructions:
1. Apply the 5-step Falsification Protocol: Verify or falsify the candidate issues using the diff context and Joern CPG reachable guards/callers.
2. Provide your review analysis (Verdict, Risk Assessment, Summary, Review Comments).
3. Conclude with a strict JSON block ```json {{"confirmed_issues": [...]}} ``` containing ONLY the verified, surviving defects.
"""
