import pytest
from unittest.mock import AsyncMock
from src.graph.writer import upsert_symbols, upsert_call_edges, delete_repo_data
from src.parsing.models import SymbolNode, CallEdge


@pytest.mark.asyncio
async def test_upsert_symbols_multi_repo_isolation():
    mock_client = AsyncMock()

    symbols = [
        SymbolNode(
            name="add",
            kind="function",
            file_path="math.py",
            language="python",
            start_line=1,
            end_line=5,
            qualified_name="math.py::add",
        )
    ]

    await upsert_symbols(mock_client, repo_id="repo_123", branch="main", symbols=symbols)

    assert mock_client.execute_query.called
    call_args = mock_client.execute_query.call_args[0]
    query = call_args[0]
    params = call_args[1]

    # Verify query enforces repo_id and branch
    assert "repo_id: $repo_id" in query
    assert "branch: $branch" in query
    assert params["repo_id"] == "repo_123"
    assert params["branch"] == "main"
    assert len(params["batch"]) == 1


@pytest.mark.asyncio
async def test_delete_repo_data_scoped():
    mock_client = AsyncMock()
    await delete_repo_data(mock_client, repo_id="repo_A", branch="dev")

    assert mock_client.execute_query.called
    call_args = mock_client.execute_query.call_args[0]
    params = call_args[1]
    assert params == {"repo_id": "repo_A", "branch": "dev"}
