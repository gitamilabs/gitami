import pytest
from unittest.mock import AsyncMock, MagicMock
from ai_service.agent.reviewer import _chunk_diff_by_files, _parse_worker_issues, run_agentic_pr_review
from ai_service.benchmark.scorer import BenchmarkScorer, semantic_token_similarity
from ai_service.benchmark.datasets.base import GroundTruthIssue


def test_chunk_diff_by_files_small():
    diff = """diff --git a/file1.py b/file1.py
--- a/file1.py
+++ b/file1.py
@@ -1,3 +1,3 @@
-old_code()
+new_code()
"""
    chunks = _chunk_diff_by_files(diff, max_chunk_chars=1000)
    assert len(chunks) == 1
    files, text = chunks[0]
    assert "file1.py" in files
    assert "new_code()" in text


def test_chunk_diff_by_files_multiple():
    diff_file1 = """diff --git a/path/to/alpha.py b/path/to/alpha.py
--- a/path/to/alpha.py
+++ b/path/to/alpha.py
@@ -1,5 +1,5 @@
+alpha_code_line()
"""
    diff_file2 = """diff --git a/path/to/beta.py b/path/to/beta.py
--- a/path/to/beta.py
+++ b/path/to/beta.py
@@ -1,5 +1,5 @@
+beta_code_line()
"""
    combined = diff_file1 + "\n" + diff_file2
    # With a small max_chunk_chars, it should split into 2 chunks
    chunks = _chunk_diff_by_files(combined, max_chunk_chars=len(diff_file1) + 10)
    assert len(chunks) == 2
    assert "path/to/alpha.py" in chunks[0][0]
    assert "path/to/beta.py" in chunks[1][0]


def test_semantic_token_similarity():
    # Long golden comment vs concise prediction
    gt = "The code uses forEach with async callbacks, which causes asynchronous operations to run concurrently without being awaited."
    pred = "Floating async promises in forEach loop"
    sim = semantic_token_similarity(pred, gt)
    assert sim > 0.35, f"Expected similarity > 0.35, got {sim}"

    # CamelCase token splitting
    gt_camel = "Missing check on isConditionalPasskeysEnabled"
    pred_camel = "Potential NullPointer in conditional passkeys check"
    sim_camel = semantic_token_similarity(pred_camel, gt_camel)
    assert sim_camel > 0.25, f"Expected similarity > 0.25, got {sim_camel}"


def test_scorer_pr_level_cross_file_match():
    scorer = BenchmarkScorer()
    pred_issues = [
        {
            "id": "pred-1",
            "title": "Floating async promises in forEach loop",
            "description": "Array.forEach(async ...) does not await promises, causing unhandled rejections.",
            "category": "bug",
            "severity": "error",
            "file_path": "packages/app-store/vital/lib/reschedule.ts",
            "line": 122,
        }
    ]
    # Ground truth mapped to a different file by heuristic locator
    gt_issues = [
        GroundTruthIssue(
            file_path="packages/core/videoClient.ts",
            line_start=39,
            severity="error",
            category="bug",
            title="The code uses forEach with async callbacks",
            description="The code uses forEach with async callbacks, which causes asynchronous operations to run concurrently without being awaited.",
        )
    ]

    # Under Martian PR-level dataset scoring, cross-file semantic matches should be accepted
    score_martian = scorer.score_test_case(
        case_id="case-1",
        dataset_name="martian",
        predicted_issues=pred_issues,
        ground_truth=gt_issues,
    )
    assert score_martian.true_positives == 1
    assert score_martian.false_positives == 0
    assert score_martian.false_negatives == 0
    assert score_martian.precision == 1.0

    # Under VulnGym coordinate dataset scoring, strict file match is required so it should not match cross-file
    score_vulngym = scorer.score_test_case(
        case_id="case-1",
        dataset_name="vulngym",
        predicted_issues=pred_issues,
        ground_truth=gt_issues,
    )
    assert score_vulngym.true_positives == 0
    assert score_vulngym.false_positives == 1
    assert score_vulngym.false_negatives == 1


@pytest.mark.asyncio
async def test_run_agentic_pr_review_text_rag_mode():
    """Verify run_agentic_pr_review runs cleanly in text_rag mode with client=None."""
    mock_llm = MagicMock()
    mock_llm.has_gemini = False
    mock_llm.orchestrator_provider = "ollama"
    mock_llm.run_worker = AsyncMock(
        return_value='```json\n{"issues": [{"title": "Unhandled promise", "description": "Promise unhandled", "category": "bug", "severity": "error", "file_path": "test.js", "line": 5}]}\n```'
    )
    mock_llm.run_orchestrator = AsyncMock(
        return_value='Verdict: SUGGEST\n```json\n{"confirmed_issues": [{"title": "Unhandled promise", "description": "Promise unhandled", "category": "bug", "severity": "error", "file_path": "test.js", "line": 5}]}\n```'
    )

    sample_diff = """diff --git a/test.js b/test.js
--- a/test.js
+++ b/test.js
@@ -1,5 +1,5 @@
-function old() {}
+async function newFunc() { doSomething(); }
"""
    result = await run_agentic_pr_review(
        client=None,
        repo_id="test-repo",
        branch="main",
        changed_symbols=["test.js::newFunc"],
        raw_diff_text=sample_diff,
        symbols=[],
        vector_client=None,
        llm_client=mock_llm,
        mode="text_rag",
    )

    assert result.decision.verdict in ("ACCEPT", "SUGGEST")
    assert len(result.issues) == 1


def test_cross_file_sibling_deduplication():
    from ai_service.agent.reviewer import deduplicate_issues

    issues = [
        {
            "id": "1",
            "title": "Array.forEach with async callback",
            "description": "Array.forEach does not wait for async callback promises to resolve, leading to unhandled errors.",
            "category": "bug",
            "severity": "warning",
            "file_path": "services/auth.ts",
            "line": 45,
        },
        {
            "id": "2",
            "title": "Async callback in forEach loop",
            "description": "Async operations in forEach will execute concurrently without awaiting.",
            "category": "bug",
            "severity": "error",
            "file_path": "services/user.ts",
            "line": 88,
        },
        {
            "id": "3",
            "title": "SQL Injection vulnerability",
            "description": "User input directly concatenated into SQL query string.",
            "category": "security",
            "severity": "critical",
            "file_path": "db/queries.ts",
            "line": 12,
        },
    ]

    deduped = deduplicate_issues(issues, line_window=15, cross_file_threshold=0.48)
    # The two forEach async issues should be merged into 1 (with upgraded severity 'error')
    # and the SQL injection issue kept
    assert len(deduped) == 2
    titles = [i["title"] for i in deduped]
    assert any("SQL Injection" in t for t in titles)
    assert any("forEach" in t for t in titles)
    # Check severity escalation
    foreach_issue = next(i for i in deduped if "forEach" in i["title"])
    assert foreach_issue["severity"] == "error"


@pytest.mark.asyncio
async def test_hierarchical_vetting_gate():
    mock_llm = MagicMock()
    mock_llm.has_gemini = False
    mock_llm.orchestrator_provider = "ollama"

    # Worker reports:
    # 1. Generic placeholder
    # 2. Duplicate of orchestrator issue
    # 3. Low-severity style nit
    # 4. Distinct real bug
    worker_output = """```json
    {
      "issues": [
        {
          "title": "Code Issue Detected",
          "description": "Potential flaw found during deep diff analysis.",
          "category": "bug",
          "severity": "warning",
          "file_path": "src/app.py",
          "line": 1
        },
        {
          "title": "Unhandled promise in async handler",
          "description": "Async handler missing await on database commit call.",
          "category": "bug",
          "severity": "warning",
          "file_path": "src/controllers.py",
          "line": 50
        },
        {
          "title": "Variable naming convention",
          "description": "Variable should use snake_case instead of camelCase.",
          "category": "style",
          "severity": "low",
          "file_path": "src/app.py",
          "line": 15
        },
        {
          "title": "Resource leak in file descriptor",
          "description": "File opened with open() is never closed in exception path.",
          "category": "bug",
          "severity": "error",
          "file_path": "src/utils.py",
          "line": 30
        }
      ]
    }
    ```"""
    mock_llm.run_worker = AsyncMock(return_value=worker_output)

    # Orchestrator confirms the unhandled promise bug
    orch_output = """Verdict: SUGGEST
    ```json
    {
      "confirmed_issues": [
        {
          "title": "Unhandled promise in async handler",
          "description": "Async handler missing await on database commit call.",
          "category": "bug",
          "severity": "error",
          "file_path": "src/controllers.py",
          "line": 48
        }
      ]
    }
    ```"""
    mock_llm.run_orchestrator = AsyncMock(return_value=orch_output)

    sample_diff = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,5 +1,5 @@
+new_code()
"""
    result = await run_agentic_pr_review(
        client=None,
        repo_id="test-repo",
        branch="main",
        raw_diff_text=sample_diff,
        llm_client=mock_llm,
        mode="text_rag",
    )

    # Vetting gate should leave:
    # 1. Orchestrator confirmed issue (unhandled promise)
    # 2. Distinct worker bug (resource leak)
    # Placeholder should be discarded, duplicate should be suppressed, style nit routed to suggestions
    assert len(result.issues) == 2
    issue_titles = [i["title"] for i in result.issues]
    assert any("Unhandled promise" in t for t in issue_titles)
    assert any("Resource leak" in t for t in issue_titles)
    # Style nit should be in decision suggestions
    suggestion_texts = [s.description for s in result.decision.suggestions]
    assert any("Variable naming convention" in s for s in suggestion_texts)
