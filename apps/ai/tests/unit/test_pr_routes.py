import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from src.web.app import app
from src.web.deps import get_shared_graph_client, get_shared_vector_client


@pytest.fixture
def mock_clients():
    mock_graph = MagicMock()
    mock_graph.connect = AsyncMock()
    mock_graph.close = AsyncMock()
    mock_graph.execute_query = AsyncMock(return_value=[])

    mock_vector = MagicMock()
    mock_vector.query = MagicMock(return_value={"documents": [[]], "metadatas": [[]], "ids": [[]]})

    return mock_graph, mock_vector


@pytest.fixture(autouse=True)
def override_deps(mock_clients):
    mock_graph, mock_vector = mock_clients

    async def override_graph():
        return mock_graph

    def override_vector():
        return mock_vector

    app.dependency_overrides[get_shared_graph_client] = override_graph
    app.dependency_overrides[get_shared_vector_client] = override_vector
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_pr_review_guardrail_ai_fix(client):
    """Guardrail: AI fix branches must skip review to prevent recursive loops."""
    payload = {
        "repo_id": "test/repo",
        "pr_number": 42,
        "base_branch": "main",
        "head_branch": "ai-fix/patch-101",
        "title": "fix: automated repair",
        "body": "Automated patch",
        "diff_text": "+const x = 1;",
    }
    response = client.post("/api/pr/review", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "ACCEPT"
    assert data["status"] == "skipped_ai_fix"
    assert data["risk_score"] == 0.0


def test_pr_review_route_curated_agent(client):
    """PR Review route executes ReviewAgent and returns standard contract plus enriched fields."""
    sample_diff = """--- a/src/auth.ts
+++ b/src/auth.ts
@@ -1,3 +1,4 @@
 export function verify(token: string) {
+  const secret = 'super-secret-key-1234567890';
   return true;
 }
"""
    payload = {
        "repo_id": "test/repo",
        "pr_number": 7,
        "base_branch": "main",
        "head_branch": "feature/auth",
        "title": "Add auth verify",
        "body": "Implements auth",
        "diff_text": sample_diff,
    }

    with patch("src.web.routes.pr.DualLLMClient") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm.run_orchestrator = AsyncMock(return_value='{"summary": "Review complete", "checklist": []}')
        mock_llm.run_worker = AsyncMock(return_value='{"issues": []}')
        mock_llm_cls.return_value = mock_llm

        response = client.post("/api/pr/review", json=payload)

    assert response.status_code == 200
    data = response.json()
    # Backward compatible fields
    assert "verdict" in data
    assert "risk_score" in data
    assert "summary" in data
    assert "agent_rationale" in data
    assert "issues" in data
    # Enriched fields
    assert "checklist" in data
    assert "blast_radius" in data
    assert "claude_code_export" in data


def test_pr_fix_route_code_agent(client):
    """PR Fix route executes CodeAgent and returns patched file fixes."""
    payload = {
        "repo_id": "test/repo",
        "pr_number": 7,
        "base_branch": "main",
        "issues": [
            {
                "id": "iss-1",
                "file_path": "src/math.ts",
                "line": 4,
                "title": "Division by zero",
                "description": "b can be 0",
                "suggested_fix": "Add check",
            }
        ],
        "existing_file_contents": {
            "src/math.ts": "export function divide(a, b) {\n  return a / b;\n}\n"
        },
    }

    with patch("src.web.routes.pr.DualLLMClient") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm.run_orchestrator = AsyncMock(return_value='''{
            "summary": "Fix division by zero",
            "files_to_touch": ["src/math.ts"],
            "approach": "Add b === 0 guard",
            "test_strategy": "Test with b=0",
            "reproduction_test_code": "test('zero', () => {})",
            "test_file_path": "tests/math.test.ts",
            "patch_diff": "--- a/src/math.ts\\n+++ b/src/math.ts\\n",
            "pr_title": "fix(math): check zero",
            "pr_description_markdown": "Fixes zero division"
        }''')
        mock_llm.run_worker = AsyncMock(return_value='''
<<<FILE: src/math.ts>>>
export function divide(a, b) {
  if (b === 0) throw new Error("ZeroDivision");
  return a / b;
}
<<<ENDFILE>>>
''')
        mock_llm_cls.return_value = mock_llm

        response = client.post("/api/pr/fix", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "plan_rationale" in data
    assert len(data["file_fixes"]) > 0
    assert data["file_fixes"][0]["file_path"] == "src/math.ts"
    assert "ZeroDivision" in data["file_fixes"][0]["content"]
