import asyncio
import pytest
from pathlib import Path
from src.graph.client import Neo4jClient
from src.jobs.init_job import run_init_job
from src.jobs.pr_eval_job import run_pr_eval_job


@pytest.mark.asyncio
async def test_end_to_end_agent_pr_review():
    client = Neo4jClient()
    try:
        await asyncio.wait_for(client.verify_connectivity(), timeout=1.5)
    except Exception:
        pytest.skip("Neo4j database is not running, skipping live agent integration test")
    try:
        repo_dir = Path(__file__).parent.parent / "fixtures" / "mern_sample"

        # 1. Run Init Job with Import Resolver
        init_res = await run_init_job(
            repo_id="integration-test-mern",
            branch="main",
            repo_dir=repo_dir,
            client=client,
        )
        assert init_res.status == "SUCCESS"
        assert init_res.symbols_count > 0

        # 2. Run PR Evaluation with Agentic Reviewer
        eval_res = await run_pr_eval_job(
            repo_id="integration-test-mern",
            branch="main",
            repo_dir=repo_dir,
            base_ref="HEAD~1",
            head_ref="HEAD",
            client=client,
            use_agent=True,
        )
        assert eval_res.status == "SUCCESS", f"Eval failed with errors: {eval_res.errors}"
        assert eval_res.decision is not None
        assert eval_res.decision.verdict in ("ACCEPT", "SUGGEST")
    finally:
        await client.close()
