import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.fixer import run_autonomous_pr_fixer, _apply_simple_fix


@pytest.mark.asyncio
async def test_run_autonomous_pr_fixer_surgical_success():
    mock_llm = MagicMock()
    mock_llm.run_orchestrator = AsyncMock(return_value="""
1. File: src/math.ts, line 4
2. Current: return a / b;
3. Fix: Add zero check if (b === 0) throw new Error("ZeroDivision");
""")
    mock_llm.run_worker = AsyncMock(return_value="""
<<<FILE: src/math.ts>>>
export function add(a: number, b: number) {
  return a + b;
}

export function divide(a: number, b: number) {
  if (b === 0) throw new Error("ZeroDivision");
  return a / b;
}
<<<ENDFILE>>>
""")

    issues = [
        {
            "id": "iss-1",
            "file_path": "src/math.ts",
            "line": 4,
            "title": "Division by zero",
            "description": "divide function does not check if b is zero.",
            "category": "bug",
            "suggested_fix": "Add check for b === 0",
        }
    ]
    file_contents = {
        "src/math.ts": "export function add(a: number, b: number) {\n  return a + b;\n}\n\nexport function divide(a: number, b: number) {\n  return a / b;\n}\n"
    }

    res = await run_autonomous_pr_fixer(
        repo_id="test/repo",
        pr_number=10,
        base_branch="main",
        issues=issues,
        existing_file_contents=file_contents,
        llm_client=mock_llm,
    )

    assert res.success is True
    assert len(res.file_fixes) == 1
    assert res.file_fixes[0].file_path == "src/math.ts"
    assert 'if (b === 0) throw new Error("ZeroDivision");' in res.file_fixes[0].content


@pytest.mark.asyncio
async def test_run_autonomous_pr_fixer_missing_files_error():
    mock_llm = MagicMock()

    res = await run_autonomous_pr_fixer(
        repo_id="test/repo",
        pr_number=10,
        base_branch="main",
        issues=[{"file_path": "non_existent.ts", "title": "Bug"}],
        existing_file_contents={},
        llm_client=mock_llm,
    )

    assert res.success is False
    assert "No file content available" in res.error


def test_apply_simple_fix_regex():
    original = "const x = undefinedMethod();\nreturn x;"
    issues = [
        {
            "suggested_fix": "Replace undefinedMethod() with definedMethod()",
        }
    ]
    patched = _apply_simple_fix(original, issues)
    assert "const x = definedMethod();" in patched
