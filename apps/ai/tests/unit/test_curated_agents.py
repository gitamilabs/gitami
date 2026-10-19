import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents import (
    InvestigationAgent,
    IssueAgent,
    ReviewAgent,
    DocAgent,
    CodeAgent,
    FixPlan,
)
from src.agents.diff_parser import parse_git_diff


@pytest.fixture
def mock_llm_client():
    mock = MagicMock()
    mock.run_orchestrator = AsyncMock(return_value="""{
        "verdict": "Root cause confirmed",
        "root_cause": "Unchecked null pointer access in auth handler",
        "confidence": 0.88,
        "recommended_steps": ["Add null check", "Update tests"],
        "summary_markdown": "### Root Cause: Null pointer in auth",
        "is_spam": false,
        "criticality_score": 8,
        "criticality": "HIGH",
        "ai_code_suspected": false,
        "domain_tags": ["auth", "api"],
        "suggested_labels": ["bug", "severity:high"],
        "summary": "Triage summary",
        "files_to_touch": ["src/auth.ts"],
        "approach": "Add guard clause",
        "test_strategy": "Add unit test for null input",
        "reproduction_test_code": "test('handles null', () => {})",
        "test_file_path": "tests/auth.test.ts",
        "patch_diff": "--- a/src/auth.ts\\n+++ b/src/auth.ts\\n@@ -1 +1,2 @@\\n+if (!user) return null;",
        "pr_title": "fix(auth): guard null user input",
        "pr_description_markdown": "Fixes null pointer"
    }""")
    mock.run_worker = AsyncMock(return_value="""{
        "hypothesis": "Null pointer occurs when token payload is missing sub claim",
        "confidence": 0.70,
        "investigation_target": "src/auth.ts",
        "issues": []
    }""")
    return mock


@pytest.fixture
def mock_graph_client():
    mock = MagicMock()
    mock.connect = AsyncMock()
    mock.close = AsyncMock()
    mock.query = AsyncMock(return_value=[])
    mock.get_file_tree = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_vector_client():
    mock = MagicMock()
    mock.search = AsyncMock(return_value=[])
    mock.batch_upsert = AsyncMock(return_value={"inserted": 1})
    mock.get = AsyncMock(return_value={"documents": [], "metadatas": []})
    mock.delete = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_investigation_agent_fast_path(mock_llm_client, mock_graph_client, mock_vector_client):
    agent = InvestigationAgent(
        llm_client=mock_llm_client,
        graph_client=mock_graph_client,
        vector_client=mock_vector_client,
    )
    # Informational query -> fast single shot
    res = await agent.run(
        query="What is the database schema?",
        repo_id="test/repo",
        branch="main",
        is_incident=False,
    )

    assert res.repo_id == "test/repo"
    assert res.is_deep_investigation is False
    assert res.confidence >= 0.90
    assert len(res.plain_text_summary) > 0


@pytest.mark.asyncio
async def test_investigation_agent_deep_loop(mock_llm_client, mock_graph_client, mock_vector_client):
    agent = InvestigationAgent(
        llm_client=mock_llm_client,
        graph_client=mock_graph_client,
        vector_client=mock_vector_client,
    )
    # Root cause / crash query -> iterative loop
    res = await agent.run(
        query="Why did the server crash with a nil pointer error?",
        repo_id="test/repo",
        branch="main",
        is_incident=True,
        max_steps=4,
    )

    assert res.repo_id == "test/repo"
    assert res.is_deep_investigation is True
    assert len(res.reasoning_trace) > 0
    assert res.root_cause is not None
    assert len(res.recommended_steps) > 0


@pytest.mark.asyncio
async def test_issue_agent_triage_and_ai_code_detection(mock_llm_client, mock_graph_client, mock_vector_client):
    agent = IssueAgent(
        llm_client=mock_llm_client,
        graph_client=mock_graph_client,
        vector_client=mock_vector_client,
    )
    # Issue containing typical LLM disclaimer
    issue_body = "As an AI, I generated this code snippet but it causes an exception."
    res = await agent.run(
        repo_id="test/repo",
        issue_number=101,
        title="Crash in auth token verification",
        body=issue_body,
        author="testuser",
    )

    assert res.issue_number == 101
    assert res.is_spam is False
    assert res.criticality == "HIGH"
    assert res.criticality_score == 8
    assert res.ai_code_suspected is True
    assert "ai-code-suspected" in res.suggested_labels
    assert "auth" in res.domain_tags


@pytest.mark.asyncio
async def test_review_agent_security_and_test_gap(mock_llm_client, mock_graph_client, mock_vector_client):
    agent = ReviewAgent(
        llm_client=mock_llm_client,
        graph_client=mock_graph_client,
        vector_client=mock_vector_client,
    )
    # Diff with security anti-pattern and no tests
    diff_text = """--- a/src/service.ts
+++ b/src/service.ts
@@ -10,2 +10,4 @@
 export function renderUser(html: string) {
+  const secret_api_key = "1234567890abcdef1234567890";
+  element.dangerouslySetInnerHTML = html;
 }
"""
    res = await agent.run(
        repo_id="test/repo",
        pr_number=42,
        base_branch="main",
        head_branch="feature",
        title="Update rendering",
        body="Adds fast render",
        diff_text=diff_text,
    )

    assert res.pr_number == 42
    assert res.risk_score >= 50
    # Must flag security and test coverage gaps
    categories = [item.category for item in res.checklist]
    assert "security" in categories
    assert "test_gap" in categories
    assert len(res.claude_code_export) > 0
    assert "Claude Code Task" in res.claude_code_export


@pytest.mark.asyncio
async def test_doc_agent_workflow_and_kb_indexing(mock_llm_client, mock_graph_client, mock_vector_client):
    agent = DocAgent(
        llm_client=mock_llm_client,
        graph_client=mock_graph_client,
        vector_client=mock_vector_client,
    )
    doc = await agent.generate_workflow_guide(
        repo_id="test/repo",
        feature_name="authentication",
        branch="main",
        feed_to_kb=True,
    )

    assert doc.repo_id == "test/repo"
    assert doc.doc_type == "workflow_guide"
    assert "authentication" in doc.title.lower()
    assert doc.indexed_in_kb is True


@pytest.mark.asyncio
async def test_code_agent_two_stage_workflow(mock_llm_client, mock_graph_client, mock_vector_client):
    agent = CodeAgent(
        llm_client=mock_llm_client,
        graph_client=mock_graph_client,
        vector_client=mock_vector_client,
    )
    # Stage 1: Generate plan requiring maintainer approval
    plan = await agent.generate_fix_plan(
        repo_id="test/repo",
        issue_title="Null pointer in auth handler",
        issue_description="Token payload without sub causes crash",
        trigger_source="review",
    )

    assert plan.needs_approval is True
    assert plan.approved is False
    assert len(plan.files_to_touch) > 0

    # Stage 2: Execute once approved
    executed = await agent.execute_approved_plan(
        plan=plan,
        existing_file_contents={"src/auth.ts": "export function verify() {}"},
    )

    assert executed.status == "ready_for_pr"
    assert len(executed.reproduction_test_code) > 0
    assert len(executed.patch_diff) > 0
    assert len(executed.pr_title) > 0
