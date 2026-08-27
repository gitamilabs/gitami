import os
import re
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path

from ai_service.agent.llm_client import DualLLMClient


@dataclass
class FixFileResult:
    file_path: str
    content: str


@dataclass
class AgentFixResult:
    success: bool
    plan_rationale: str
    file_fixes: List[FixFileResult]
    error: Optional[str] = None


async def _fetch_github_file(repo_full_name: str, file_path: str, branch: str) -> Optional[str]:
    """Fetch raw file content from GitHub REST API."""
    import httpx

    # Try with GITHUB_TOKEN first, then without
    github_token = (os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PAT") or "").strip()
    headers = {
        "Accept": "application/vnd.github.v3.raw",
        "User-Agent": "Sentinel-AI-Agent",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    url = f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}?ref={branch}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.text
    except Exception as e:
        print(f"⚠️ Could not fetch {file_path} from GitHub: {e}")

    return None


async def run_autonomous_pr_fixer(
    repo_id: str,
    pr_number: int,
    base_branch: str,
    issues: List[Dict[str, Any]],
    repo_dir: Optional[Path] = None,
    llm_client: Optional[DualLLMClient] = None,
    diff_text: str = "",
    existing_file_contents: Optional[Dict[str, str]] = None,
) -> AgentFixResult:
    """
    Autonomous PR Fix Agent — Surgical Patch Mode:
    1. Fetches exact existing file content from GitHub or local disk.
    2. Gemini Orchestrator plans minimal, targeted code changes.
    3. Groq Worker applies ONLY the specific line-level edits, preserving all other code.
    4. Returns the complete file with minimal surgical changes applied.
    """
    if llm_client is None:
        llm_client = DualLLMClient()

    # Format problem statement / issue details
    issues_text = ""
    target_files = set()
    for idx, item in enumerate(issues, start=1):
        fp = item.get("file_path", "unknown")
        target_files.add(fp)
        issues_text += (
            f"Issue #{idx}:\n"
            f"- Title: {item.get('title')}\n"
            f"- Category: {item.get('category')}\n"
            f"- File: {fp}:{item.get('line', 1)}\n"
            f"- Description: {item.get('description')}\n"
            f"- Suggested Fix: {item.get('suggested_fix', 'N/A')}\n\n"
        )

    # ---- Gather existing file contents ----
    file_contents_map: Dict[str, str] = {}

    # Priority 1: Existing file contents passed in from api-service (fetched from GitHub)
    if existing_file_contents:
        file_contents_map.update(existing_file_contents)

    # Priority 2: Read from local disk if repo_dir exists
    if repo_dir and repo_dir.exists():
        for fp in target_files:
            if fp not in file_contents_map:
                abs_p = repo_dir / fp
                if abs_p.exists() and abs_p.is_file():
                    try:
                        file_contents_map[fp] = abs_p.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        pass

    # Priority 3: Fetch from GitHub REST API
    for fp in target_files:
        if fp not in file_contents_map:
            content = await _fetch_github_file(repo_id, fp, base_branch)
            if content:
                file_contents_map[fp] = content

    # Build existing files context string
    existing_files_text = ""
    for fp, content in file_contents_map.items():
        # Number lines so the LLM can reference them precisely
        numbered_lines = "\n".join(
            f"{i+1}: {line}" for i, line in enumerate(content.split("\n"))
        )
        existing_files_text += f"\n{'='*60}\nFILE: {fp}\n{'='*60}\n{numbered_lines}\n"

    if not existing_files_text:
        return AgentFixResult(
            success=False,
            plan_rationale="Could not retrieve existing file contents from GitHub or local disk.",
            file_fixes=[],
            error="No file content available. Cannot generate surgical patches.",
        )

    # Step 1: Gemini Orchestrator Fix Planner (Surgical Mode)
    orchestrator_system = (
        "You are a Senior Software Engineer planning MINIMAL, SURGICAL code fixes.\n"
        "Your job is to identify the EXACT lines that need to change and describe the fix precisely.\n\n"
        "CRITICAL RULES:\n"
        "1. ONLY fix the specific bugs/issues reported. Do NOT refactor, restructure, or 'improve' unrelated code.\n"
        "2. Identify the exact line numbers that need changes.\n"
        "3. Preserve ALL existing code, comments, docstrings, formatting, and imports that are unrelated to the fix.\n"
        "4. Each fix should typically change 1-5 lines, not entire functions or files.\n"
        "5. Output a clear, numbered list of specific line edits."
    )
    orchestrator_prompt = (
        f"Repository: {repo_id} (PR #{pr_number}, Branch: {base_branch})\n\n"
        f"REPORTED ISSUES TO FIX:\n{issues_text}\n"
        f"DIFF CONTEXT:\n{diff_text[:2000]}\n\n"
        f"EXISTING FILE CONTENTS (with line numbers):\n{existing_files_text[:6000]}\n\n"
        f"For each issue, identify:\n"
        f"1. The exact file and line number(s) to change\n"
        f"2. What the current code says on those lines\n"
        f"3. What it should be changed to\n"
        f"Keep changes MINIMAL. Do not rewrite entire functions or files."
    )

    plan_rationale = await llm_client.run_orchestrator(orchestrator_prompt, orchestrator_system)

    # Step 2: Groq Worker Surgical Patch Generator
    worker_system = (
        "You are an autonomous code fix worker. You apply SURGICAL, MINIMAL patches to existing source files.\n\n"
        "ABSOLUTE RULES — VIOLATION IS UNACCEPTABLE:\n"
        "1. You MUST output the COMPLETE file contents — every single line of the original file.\n"
        "2. You may ONLY change the specific lines identified in the fix plan. ALL other lines MUST remain EXACTLY as they are.\n"
        "3. Do NOT remove, reorder, refactor, simplify, or 'clean up' any code that is not directly related to the fix.\n"
        "4. Do NOT remove comments, docstrings, blank lines, imports, or any other existing code.\n"
        "5. Do NOT change variable names, function signatures, class definitions, or formatting unless the fix specifically requires it.\n"
        "6. The output file should be IDENTICAL to the input file EXCEPT for the 1-5 lines that fix the reported issue.\n"
        "7. If the original file has 139 lines, your output MUST have approximately 139 lines (± the lines added/removed by the fix).\n\n"
        "FORMAT: For each modified file, wrap the COMPLETE file code inside:\n"
        "<<<FILE: path/to/file.ext>>>\n"
        "(complete file with surgical fix applied)\n"
        "<<<ENDFILE>>>\n\n"
        "THINK OF IT AS: Copy-paste the entire original file, then change ONLY the broken line(s)."
    )

    # Build per-file worker prompts
    file_fixes: List[FixFileResult] = []

    for fp in target_files:
        if fp not in file_contents_map:
            continue

        original_content = file_contents_map[fp]
        file_issues = [i for i in issues if i.get("file_path") == fp]

        if not file_issues:
            continue

        file_issues_text = ""
        for idx, item in enumerate(file_issues, start=1):
            file_issues_text += (
                f"Fix #{idx}:\n"
                f"- Line {item.get('line', '?')}: {item.get('title')}\n"
                f"- Problem: {item.get('description')}\n"
                f"- Suggested Fix: {item.get('suggested_fix', 'N/A')}\n\n"
            )

        worker_prompt = f"""Apply MINIMAL surgical fixes to this file.

<fix_plan>
{plan_rationale[:2000]}
</fix_plan>

<specific_fixes_for_this_file>
{file_issues_text}
</specific_fixes_for_this_file>

<original_file path="{fp}">
{original_content}
</original_file>

REMEMBER: Output the COMPLETE file with ONLY the specific bug-fix lines changed. 
Every other line must be IDENTICAL to the original. Do NOT rewrite, refactor, or simplify the file.
Wrap your output in <<<FILE: {fp}>>> ... <<<ENDFILE>>> blocks."""

        worker_output = await llm_client.run_worker(worker_prompt, worker_system)

        # Parse worker output
        file_block_pattern = re.compile(
            r"<<<FILE:\s*([^\n>]+)>>>\n?(.*?)\n?<<<ENDFILE>>>", re.DOTALL
        )

        matches = file_block_pattern.findall(worker_output)
        for matched_path, content in matches:
            clean_path = matched_path.strip()
            clean_content = content.strip()
            if clean_path and clean_content:
                # Validate that the fix didn't drastically change the file
                original_line_count = len(original_content.strip().split("\n"))
                fixed_line_count = len(clean_content.strip().split("\n"))
                diff_ratio = abs(fixed_line_count - original_line_count) / max(original_line_count, 1)

                if diff_ratio > 0.4:
                    # Worker rewrote too much — fall back to original with simple text replacement
                    print(f"⚠️ Fixer output for {fp} changed {int(diff_ratio*100)}% of lines — applying simple replacement fallback")
                    patched = _apply_simple_fix(original_content, file_issues)
                    file_fixes.append(FixFileResult(file_path=fp, content=patched))
                else:
                    file_fixes.append(FixFileResult(file_path=fp, content=clean_content))

        # If no blocks matched, try simple replacement
        if not any(f.file_path == fp for f in file_fixes):
            patched = _apply_simple_fix(original_content, file_issues)
            if patched != original_content:
                file_fixes.append(FixFileResult(file_path=fp, content=patched))

    return AgentFixResult(
        success=len(file_fixes) > 0,
        plan_rationale=plan_rationale,
        file_fixes=file_fixes,
    )


def _apply_simple_fix(original_content: str, issues: List[Dict[str, Any]]) -> str:
    """
    Simple text-replacement fallback: if the LLM rewrites too much,
    apply the suggested_fix as a direct string replacement.
    """
    content = original_content
    for issue in issues:
        suggested_fix = issue.get("suggested_fix", "").strip()
        if not suggested_fix:
            continue

        # Try to parse "Replace X with Y" patterns
        replace_match = re.match(
            r"(?:Replace|Change)\s+[`'\"]?(.+?)[`'\"]?\s+(?:with|to)\s+[`'\"]?(.+?)[`'\"]?\s*$",
            suggested_fix,
            re.IGNORECASE
        )
        if replace_match:
            old_text = replace_match.group(1).strip()
            new_text = replace_match.group(2).strip()
            if old_text in content:
                content = content.replace(old_text, new_text, 1)
                print(f"  ✅ Simple fix applied: '{old_text}' → '{new_text}'")

    return content
