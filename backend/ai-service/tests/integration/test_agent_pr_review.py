import pytest
from pathlib import Path
from ai_service.graph.client import Neo4jClient
from ai_service.jobs.init_job import run_init_job
from ai_service.jobs.pr_eval_job import run_pr_eval_job


@pytest.mark.asyncio
async def test_end_to_end_agent_pr_review():
    client = Neo4jClient()
    await client.connect()
    try:
        repo_dir = Path(__file__).parent.parent / "fixtures" / "mern_sample"

        # 1. Run Init Job with Import Resolver
        init_res = await run_init_job(
            repo_id="integration-test-mern",
            branch="main",
            repo_dir=repo_dir,
            client=client,
        )
        assert init_res.status in ("SUCCESS", "CACHED")
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
