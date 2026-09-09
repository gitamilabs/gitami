import pytest
from src.graph.client import Neo4jClient
from src.agents.reviewer import run_agentic_pr_review
from src.parsing.models import SymbolNode


@pytest.mark.asyncio
async def test_run_agentic_pr_review():
    client = Neo4jClient()
    await client.connect()
    try:
        sample_diff = """--- a/tests/fixtures/mern_sample/api.js
+++ b/tests/fixtures/mern_sample/api.js
@@ -2,3 +2,3 @@
 export async function fetchUsers() {
-    return fetch('/users');
+    return fetch('/v2/users');
 }
"""
        sample_symbols = [
            SymbolNode(
                name="fetchUsers",
                kind="function",
                file_path="tests/fixtures/mern_sample/api.js",
                language="javascript",
                start_line=2,
                end_line=5,
                signature="export async function fetchUsers()",
                docstring="",
                qualified_name="tests/fixtures/mern_sample/api.js::fetchUsers",
            )
        ]

        res = await run_agentic_pr_review(
            client=client,
            repo_id="demo-mern",
            branch="main",
            changed_symbols=["tests/fixtures/mern_sample/api.js::fetchUsers"],
            raw_diff_text=sample_diff,
            symbols=sample_symbols,
        )

        assert res.decision.verdict in ("ACCEPT", "SUGGEST")
        assert res.diff_hunks_count > 0
        assert len(res.decision.summary) > 0
    finally:
        await client.close()
