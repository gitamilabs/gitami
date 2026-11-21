import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.mcp.tools import tool_hybrid_search
from src.context.contracts import ContextResult, ContextItem, ContextItemType, ContextSource, RetrievalMetadata


@pytest.mark.asyncio
async def test_tool_hybrid_search_invokes_context_engine_with_tenant_scoping():
    mock_graph_client = AsyncMock()
    mock_vector_client = MagicMock()

    mock_result = ContextResult(
        query="authenticate user",
        project_id="test-project",
        items=[
            ContextItem(
                id="sem:auth1",
                type=ContextItemType.SEMANTIC_CODE,
                title="Auth Helper",
                content="def login(): pass",
                source=ContextSource(kind="semantic", repository_id="org/repo"),
            ),
            ContextItem(
                id="graph:auth2",
                type=ContextItemType.SYMBOL,
                title="Symbol: auth",
                content="def auth(): pass",
                source=ContextSource(kind="graph", repository_id="org/repo", entity_uid="auth", file_path="auth.py"),
            ),
        ],
        sources=[],
        total_candidates=2,
        returned_items=2,
        truncated=False,
        retrieval_metadata=RetrievalMetadata(),
        errors=[],
    )

    with patch("src.context.ContextEngine.retrieve", new_callable=AsyncMock) as mock_retrieve:
        mock_retrieve.return_value = mock_result

        res_str = await tool_hybrid_search(
            graph_client=mock_graph_client,
            vector_client=mock_vector_client,
            repo_id="org/repo",
            query_text="authenticate user",
            branch="dev",
            n_results=5,
            project_id="test-project",
        )

        assert mock_retrieve.called, "ContextEngine.retrieve should have been called"
        req = mock_retrieve.call_args[0][0]
        assert req.project_id == "test-project"
        assert req.repository_ids == ["org/repo"]
        assert req.query == "authenticate user"
        assert req.branch == "dev"
        assert req.max_items == 5

        res = json.loads(res_str)
        assert res["query"] == "authenticate user"
        assert "items" in res
        assert "vector_hits" in res
        assert "graph_hits" in res
        assert len(res["items"]) == 2


def test_kb_unified_is_deleted():
    with pytest.raises(ImportError):
        import src.kb_unified
