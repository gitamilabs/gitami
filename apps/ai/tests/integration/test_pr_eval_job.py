import tempfile
import pytest
from pathlib import Path
from git import Repo
from unittest.mock import AsyncMock
from src.jobs.pr_eval_job import run_pr_eval_job


@pytest.mark.asyncio
async def test_run_pr_eval_job_flow():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        repo = Repo.init(tmp_path)

        # 1. Base commit
        f1 = tmp_path / "math.py"
        f1.write_text("def add(a, b):\n    return a + b\n")
        repo.index.add(["math.py"])
        commit1 = repo.index.commit("Initial commit")

        # 2. PR commit introducing long function violation
        long_func_body = "\n".join([f"    x_{i} = {i}" for i in range(60)])
        f1.write_text(f"def add(a, b):\n{long_func_body}\n    return a + b\n")
        repo.index.add(["math.py"])
        commit2 = repo.index.commit("PR update")

        mock_client = AsyncMock()
        mock_client.execute_query.return_value = []

        res = await run_pr_eval_job(
            repo_id="test_pr_repo",
            branch="main",
            repo_dir=tmp_path,
            base_ref=commit1.hexsha,
            head_ref=commit2.hexsha,
            client=mock_client,
        )

        repo.close()

        assert res.status == "SUCCESS"
        assert res.decision is not None
        assert res.decision.verdict == "SUGGEST"
        assert any("RULE-001" in s.description for s in res.decision.suggestions)
