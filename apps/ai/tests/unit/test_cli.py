import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from click.testing import CliRunner
import pytest

from src.cli import main
from src.indexer.contracts import IndexJobStatus


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "python_sample"


def test_cli_index_validate_only():
    """Verify cli index command runs directly against RepositoryIndexer in validate-only mode."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "index",
            "--repo-id", "test/repo",
            "--repo-dir", str(FIXTURES_DIR),
            "--validate-only",
        ],
    )

    assert result.exit_code == 0, f"CLI index command failed: {result.output}"
    data = json.loads(result.output)
    assert "job" in data
    assert "state" in data
    assert "validation" in data
    assert data["job"]["status"] == IndexJobStatus.COMPLETED.value
    assert data["validation"]["is_valid"] is True


def test_cli_init_compatibility_command():
    """Verify cli init command runs RepositoryIndexer and returns compatible summary JSON."""
    runner = CliRunner()
    with patch("src.graph.client.Neo4jClient.connect", AsyncMock(side_effect=Exception("No Neo4j"))):
        result = runner.invoke(
            main,
            [
                "init",
                "--repo-id", "test/repo",
                "--repo-dir", str(FIXTURES_DIR),
            ],
        )

    assert result.exit_code == 0, f"CLI init command failed: {result.output}"
    data = json.loads(result.output)
    assert data["status"] in ("READY", "SUCCESS")
    assert "symbols_count" in data
    assert "edges_count" in data
    assert data["validation_passed"] is True


def test_cli_index_missing_required_args():
    """Verify cli index fails with code 2 when required options are omitted."""
    runner = CliRunner()
    result = runner.invoke(main, ["index"])
    assert result.exit_code != 0
    assert "Missing option" in result.output


def test_cli_eval_pr_with_mock_agent(tmp_path: Path):
    """Verify cli eval-pr invokes ReviewAgent and outputs formatted JSON."""
    # Create git directory stub
    (tmp_path / "main.py").write_text("print('hello')\n")
    import git
    repo = git.Repo.init(tmp_path)
    repo.index.add(["main.py"])
    c1 = repo.index.commit("Initial")
    (tmp_path / "main.py").write_text("print('hello world')\n")
    repo.index.add(["main.py"])
    c2 = repo.index.commit("Update")

    mock_review_result = MagicMock()
    mock_review_result.to_dict.return_value = {
        "repo_id": "test/repo",
        "pr_number": 1,
        "verdict": "APPROVE",
        "risk_score": 10,
        "summary": "Clean patch",
    }

    with patch("src.graph.client.Neo4jClient.connect", AsyncMock()), \
         patch("src.graph.client.Neo4jClient.close", AsyncMock()), \
         patch("src.agents.review_agent.ReviewAgent.run", AsyncMock(return_value=mock_review_result)):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "eval-pr",
                "--repo-id", "test/repo",
                "--repo-dir", str(tmp_path),
                "--base-ref", c1.hexsha,
                "--head-ref", c2.hexsha,
            ],
        )

    repo.close()
    assert result.exit_code == 0, f"CLI eval-pr failed: {result.output}"
    data = json.loads(result.output)
    assert data["verdict"] == "APPROVE"
    assert data["risk_score"] == 10
