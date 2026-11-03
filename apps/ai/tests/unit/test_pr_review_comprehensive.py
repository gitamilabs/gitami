import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.reviewer import run_agentic_pr_review, AgentReviewResult
from src.agents.review_agent import ReviewAgent
from src.analysis.decision import Verdict
from src.parsing.models import SymbolNode


SAMPLE_DIFF_WITH_ISSUES = """--- a/src/auth/service.ts
+++ b/src/auth/service.ts
@@ -15,6 +15,10 @@ export class AuthService {
   async validateToken(token: string) {
+    const api_secret = "sk_live_1234567890abcdef123456";
+    console.log("Token validation:", token);
+    // TODO: implement proper JWT validation later
+    return token.invalidMethodCall();
   }
 }
"""

SAMPLE_CLEAN_DIFF = """--- a/src/utils/math.ts
+++ b/src/utils/math.ts
@@ -5,3 +5,3 @@ export function add(a: number, b: number): number {
-  return a - b;
+  return a + b;
 }
--- a/tests/utils/math.test.ts
+++ b/tests/utils/math.test.ts
@@ -10,3 +10,3 @@ describe('math', () => {
-  expect(add(1, 2)).toBe(-1);
+  expect(add(1, 2)).toBe(3);
 });
"""


@pytest.fixture
def mock_clients():
    graph = MagicMock()
    graph.connect = AsyncMock()
    graph.close = AsyncMock()
    graph.execute_query = AsyncMock(return_value=[])

    vector = MagicMock()
    vector.search = AsyncMock(return_value=[])

    llm = MagicMock()
    llm.has_gemini = False
    llm.has_groq = False
    llm.has_local = False
    llm.run_worker = AsyncMock(return_value=json.dumps({
        "issues": [
            {
                "title": "Invalid method call on token",
                "description": "Calling non-existent invalidMethodCall() will throw TypeError at runtime.",
                "category": "bug",
                "severity": "error",
                "file_path": "src/auth/service.ts",
                "line": 19,
                "suggested_fix": "Use jwt.verify(token, secret) instead.",
            }
        ]
    }))
    llm.run_orchestrator = AsyncMock(return_value="PR introduces a critical runtime TypeError in AuthService.")

    return graph, vector, llm


@pytest.mark.asyncio
async def test_pr_review_with_worker_detection(mock_clients):
    graph, vector, llm = mock_clients

    result: AgentReviewResult = await run_agentic_pr_review(
        client=graph,
        repo_id="test-org/test-repo",
        branch="feature/auth",
        changed_symbols=["AuthService.validateToken"],
        raw_diff_text=SAMPLE_DIFF_WITH_ISSUES,
        symbols=[],
        vector_client=vector,
        llm_client=llm,
    )

    assert result.decision.verdict == "SUGGEST"
    assert result.decision.risk_score > 0
    assert result.diff_hunks_count > 0

    # Verify worker issue was captured
    worker_issues = [i for i in result.issues if i.get("category") == "bug"]
    assert len(worker_issues) == 1
    assert "Invalid method call" in worker_issues[0]["title"]
    assert worker_issues[0]["severity"] == "error"

    # Verify static convention issues were captured (console.log, secret, TODO)
    convention_issues = [i for i in result.issues if i.get("category") == "convention"]
    rule_ids = [i.get("title") for i in convention_issues]
    assert any("RULE-006" in r for r in rule_ids)  # console.log
    assert any("RULE-009" in r for r in rule_ids)  # hardcoded secret


@pytest.mark.asyncio
async def test_pr_review_root_directory_scoping(mock_clients):
    graph, vector, llm = mock_clients

    # Scoped to apps/web -> diff modifies src/auth/service.ts, so should skip review
    result = await run_agentic_pr_review(
        client=graph,
        repo_id="test-org/test-repo",
        branch="feature/auth",
        changed_symbols=[],
        raw_diff_text=SAMPLE_DIFF_WITH_ISSUES,
        symbols=[],
        vector_client=vector,
        llm_client=llm,
        root_directory="apps/web",
    )

    assert result.decision.verdict == "ACCEPT"
    assert result.decision.risk_score == 0.0
    assert result.diff_hunks_count == 0
    assert "scoped root directory" in result.decision.summary


@pytest.mark.asyncio
async def test_pr_review_zero_tokens_offline_fallback(mock_clients):
    graph, vector, llm = mock_clients

    # Worker and Orchestrator return offline fallback string
    llm.run_worker = AsyncMock(return_value="[Worker Node - Offline Mode] Hunk analysis completed.")
    llm.run_orchestrator = AsyncMock(return_value="[Orchestrator Offline Summary]")

    result = await run_agentic_pr_review(
        client=graph,
        repo_id="test-org/test-repo",
        branch="feature/auth",
        changed_symbols=[],
        raw_diff_text=SAMPLE_DIFF_WITH_ISSUES,
        symbols=[],
        vector_client=vector,
        llm_client=llm,
    )

    # Even with 0 LLM tokens, static convention linting catches secrets and console.logs
    assert result.decision.verdict == "SUGGEST"
    assert len(result.issues) >= 2
    rule_issues = [i["title"] for i in result.issues]
    assert any("RULE-009" in r for r in rule_issues)  # Secret detected deterministically!


@pytest.mark.asyncio
async def test_pr_review_clean_diff_accept(mock_clients):
    graph, vector, llm = mock_clients

    llm.run_worker = AsyncMock(return_value=json.dumps({"issues": []}))
    llm.run_orchestrator = AsyncMock(return_value="Clean bug fix with unit test.")

    result = await run_agentic_pr_review(
        client=graph,
        repo_id="test-org/test-repo",
        branch="fix/math",
        changed_symbols=["add"],
        raw_diff_text=SAMPLE_CLEAN_DIFF,
        symbols=[],
        vector_client=vector,
        llm_client=llm,
    )

    assert result.decision.verdict == "ACCEPT"
    assert result.decision.risk_score == 0.0
    assert len(result.issues) == 0
