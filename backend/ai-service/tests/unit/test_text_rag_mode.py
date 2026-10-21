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
    assert result.issues[0]["title"] == "Unhandled promise"
    assert result.issues[0]["file_path"] == "test.js"
