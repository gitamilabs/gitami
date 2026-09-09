"""Unit and integration tests for the GitAmi Benchmarking Framework."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from src.benchmark.config import BenchmarkConfig
from src.benchmark.datasets.base import BenchmarkTestCase, GroundTruthIssue
from src.benchmark.datasets.vulngym_adapter import parse_line_span
from src.benchmark.scorer import (
    BenchmarkScorer,
    files_match,
    jaccard_similarity,
)
from src.benchmark.report import (
    BenchmarkReportGenerator,
    compare_benchmark_runs,
)
from src.benchmark.kb_lifecycle import BenchmarkKBContext


def test_benchmark_config_defaults(tmp_path: Path):
    cfg = BenchmarkConfig(
        repos_dir=tmp_path / "repos",
        results_dir=tmp_path / "results",
        sample_size=5,
    )
    assert cfg.sample_size == 5
    assert cfg.cleanup_kb is True
    assert "martian" in cfg.datasets
    assert "vulngym" in cfg.datasets

    cfg.ensure_directories()
    assert (tmp_path / "repos").exists()
    assert (tmp_path / "results").exists()
    assert (tmp_path / "repos" / "diff_cache").exists()


def test_parse_line_span():
    assert parse_line_span(97) == (97, 97)
    assert parse_line_span("348-352") == (348, 352)
    assert parse_line_span("100") == (100, 100)
    assert parse_line_span(None) == (None, None)
    assert parse_line_span("invalid-range-format-here") == (None, None)


def test_files_match():
    assert files_match("src/sentry/api/endpoints/audit.py", "audit.py") is True
    assert files_match("src/sentry/api/endpoints/audit.py", "src/sentry/api/endpoints/audit.py") is True
    assert files_match("api/audit.py", "src/sentry/api/audit.py") is True
    assert files_match("audit.py", "different.py") is False


def test_jaccard_similarity():
    sim = jaccard_similarity(
        "SQL Injection in user search query parameter",
        "Possible SQL injection defect in search handler",
    )
    assert sim > 0.2
    assert jaccard_similarity("", "something") == 0.0


def test_ground_truth_issue_line_range():
    issue = GroundTruthIssue(
        file_path="service.py",
        line_start=50,
        line_end=60,
        severity="error",
        category="security",
        title="Command Injection",
    )
    assert issue.line_in_range(55, tolerance=5) is True
    assert issue.line_in_range(46, tolerance=5) is True
    assert issue.line_in_range(64, tolerance=5) is True
    assert issue.line_in_range(20, tolerance=5) is False


def test_benchmark_scorer():
    scorer = BenchmarkScorer(line_tolerance=10, text_threshold=0.25)

    ground_truth = [
        GroundTruthIssue(
            file_path="app/auth.py",
            line_start=45,
            severity="error",
            category="security",
            title="JWT signature verification bypass",
            description="Token validation skips signature check when alg is none",
        ),
        GroundTruthIssue(
            file_path="app/db.py",
            line_start=120,
            severity="warning",
            category="bug",
            title="Unclosed database connection cursor",
            description="Cursor is not closed in exception handling block",
        ),
    ]

    predicted = [
        {
            "file_path": "app/auth.py",
            "line": 48,
            "category": "security",
            "severity": "error",
            "title": "Insecure JWT verification without signature validation",
            "description": "The JWT token validation allows unsigned tokens",
        },
        {
            "file_path": "app/extra.py",
            "line": 10,
            "category": "convention",
            "severity": "info",
            "title": "Variable name does not follow snake_case",
            "description": "Style guide violation",
        },
    ]

    score = scorer.score_test_case(
        case_id="test_case_1",
        dataset_name="test_suite",
        predicted_issues=predicted,
        ground_truth=ground_truth,
        duration_seconds=1.5,
    )

    assert score.true_positives == 1
    assert score.false_positives == 1
    assert score.false_negatives == 1
    assert score.precision == 0.5
    assert score.recall == 0.5
    assert score.f1_score == 0.5
    assert len(score.matched_pairs) == 1
    assert score.matched_pairs[0].file_matched is True


def test_aggregate_scores_and_report_generation(tmp_path: Path):
    scorer = BenchmarkScorer()
    case1 = scorer.score_test_case(
        case_id="case_1",
        dataset_name="martian",
        predicted_issues=[
            {
                "file_path": "a.py",
                "line": 10,
                "category": "bug",
                "severity": "warning",
                "title": "Bug found",
                "description": "Bug desc",
            }
        ],
        ground_truth=[
            GroundTruthIssue(
                file_path="a.py",
                line_start=12,
                category="bug",
                severity="warning",
                title="Bug found",
                description="Bug desc",
            )
        ],
        duration_seconds=2.0,
    )

    aggregate = scorer.aggregate_scores([case1])
    assert aggregate.total_cases == 1
    assert aggregate.precision == 1.0
    assert aggregate.recall == 1.0
    assert aggregate.f1_score == 1.0

    # Test report generation
    md_file = tmp_path / "report.md"
    json_file = tmp_path / "report.json"
    meta = {"datasets": ["martian"], "sample_size": 1}

    md_content = BenchmarkReportGenerator.generate_markdown(aggregate, [case1], meta, md_file)
    json_data = BenchmarkReportGenerator.generate_json(aggregate, [case1], meta, json_file)

    assert md_file.exists()
    assert json_file.exists()
    assert "GitAmi Benchmark Evaluation Report" in md_content
    assert json_data["aggregate"]["f1_score"] == 1.0


def test_compare_benchmark_runs(tmp_path: Path):
    base_data = {
        "metadata": {"generated_at": "2026-09-01T00:00:00Z"},
        "aggregate": {
            "precision": 0.50,
            "recall": 0.60,
            "f1_score": 0.5455,
            "mean_duration_seconds": 3.0,
        },
        "cases": [{"case_id": "case_1", "f1_score": 0.50}],
    }
    cand_data = {
        "metadata": {"generated_at": "2026-09-09T00:00:00Z"},
        "aggregate": {
            "precision": 0.80,
            "recall": 0.80,
            "f1_score": 0.8000,
            "mean_duration_seconds": 2.2,
        },
        "cases": [{"case_id": "case_1", "f1_score": 1.00}],
    }

    base_path = tmp_path / "base.json"
    cand_path = tmp_path / "cand.json"
    base_path.write_text(json.dumps(base_data), encoding="utf-8")
    cand_path.write_text(json.dumps(cand_data), encoding="utf-8")

    diff_md = compare_benchmark_runs(base_path, cand_path)
    assert "GitAmi Benchmark Comparison Report" in diff_md
    assert "Improved" in diff_md
    assert "case_1" in diff_md


@pytest.mark.asyncio
async def test_kb_context_cleanup():
    mock_graph = MagicMock()
    mock_graph.connect = AsyncMock()
    mock_graph.close = AsyncMock()
    mock_vector = MagicMock()

    # Test context manager teardown execution
    async with BenchmarkKBContext(
        repo_id="benchmark_test_repo",
        branch="main",
        repo_dir=None,
        graph_client=mock_graph,
        vector_client=mock_vector,
        cleanup=True,
    ) as kb_ctx:
        assert kb_ctx.repo_id == "benchmark_test_repo"

    # Verify vector client delete was invoked
    mock_vector.delete.assert_called()


@pytest.mark.asyncio
async def test_runner_orchestration(tmp_path: Path, monkeypatch):
    from unittest.mock import patch
    from src.benchmark.runner import BenchmarkRunner
    from src.agents.reviewer import AgentReviewResult
    from src.analysis.decision import DecisionResult

    # Setup isolated config
    cfg = BenchmarkConfig(
        repos_dir=tmp_path / "repos",
        results_dir=tmp_path / "results",
        sample_size=2,
        cleanup_kb=True,
        datasets=["martian"],
    )

    # Mock Neo4jClient and VectorKBClient so test doesn't require live databases running
    with patch("src.benchmark.runner.Neo4jClient") as mock_neo_cls, \
         patch("src.benchmark.runner.VectorKBClient") as mock_vec_cls, \
         patch("src.benchmark.runner.run_agentic_pr_review") as mock_review, \
         patch("src.benchmark.runner.get_dataset") as mock_get_ds:

        mock_neo = MagicMock()
        mock_neo.connect = AsyncMock()
        mock_neo.close = AsyncMock()
        mock_neo_cls.return_value = mock_neo

        mock_vec = MagicMock()
        mock_vec_cls.return_value = mock_vec

        # Mock review result
        mock_review.return_value = AgentReviewResult(
            decision=DecisionResult(verdict="SUGGEST", risk_score=7.0, summary="High risk"),
            agent_rationale="Found vulnerability",
            diff_hunks_count=1,
            llm_orchestrator_used=True,
            issues=[
                {
                    "title": "SQL Injection vulnerability",
                    "description": "Unsanitized user input in query",
                    "category": "security",
                    "severity": "error",
                    "file_path": "server/api.py",
                    "line": 42,
                }
            ],
        )

        # Mock dataset adapter
        mock_ds = MagicMock()
        mock_ds.load_cases.return_value = [
            BenchmarkTestCase(
                case_id="mock_case_1",
                dataset_name="martian",
                repo_name="test_repo",
                repo_url="https://github.com/example/test",
                commit_or_ref="abc1234",
                diff_text="diff --git a/server/api.py b/server/api.py\n+query = f'SELECT *'",
                language="python",
                ground_truth_issues=[
                    GroundTruthIssue(
                        file_path="server/api.py",
                        line_start=42,
                        severity="error",
                        category="security",
                        title="SQL Injection vulnerability in search API",
                        description="Unsanitized user input in query string",
                    )
                ],
            )
        ]
        mock_get_ds.return_value = mock_ds

        runner = BenchmarkRunner(cfg)
        result = await runner.run(dataset_name="martian")

        assert result.aggregate_score.total_cases == 1
        assert result.aggregate_score.precision == 1.0
        assert result.aggregate_score.recall == 1.0
        assert result.aggregate_score.f1_score == 1.0
        assert result.markdown_report_path.exists()
        assert result.json_report_path.exists()
