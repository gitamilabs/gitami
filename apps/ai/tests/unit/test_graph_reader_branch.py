import pytest
from unittest.mock import AsyncMock
from src.graph.reader import get_entire_graph


@pytest.mark.asyncio
async def test_get_entire_graph_branch_scoping_cypher():
    mock_client = AsyncMock()
    # Mock return values for queries in get_entire_graph
    # 1: repo query, 2: dir query, 3: file query, 4: sym query, 5: pkg query,
    # 6: contains, 7: defines, 8: rel types, 9: has_method, 10: calls, etc.
    mock_client.execute_query.side_effect = [
        [{"canonical_id": "org/repo", "id": "repo:org/repo", "props": {}}],  # Repo
        [],  # Directories
        [],  # Files
        [],  # Symbols
        [],  # Packages
        [],  # Contains
        [],  # Defines
        [{"types": ["CALLS", "DEFINES", "CONTAINS"]}],  # Rel types
        [],  # Calls
    ]

    await get_entire_graph(mock_client, repo_id="org/repo", branch="main")

    executed_queries = [call.args[0] for call in mock_client.execute_query.call_args_list]

    # Find file query and symbol query
    file_queries = [q for q in executed_queries if "MATCH (f:File)" in q and "-[:DEFINES]->" not in q]
    sym_queries = [q for q in executed_queries if "MATCH (s)" in q]

    assert len(file_queries) == 1, "Expected exactly 1 File query"
    assert len(sym_queries) == 1, "Expected exactly 1 Symbol query"

    file_query = file_queries[0]
    sym_query = sym_queries[0]

    # Cypher queries must use f.branch = 'main' and s.branch = 'main' instead of $branch = 'main'
    assert "$branch = 'main'" not in file_query, "file_query should not contain $branch = 'main'"
    assert "f.branch = 'main'" in file_query, "file_query should contain f.branch = 'main'"

    assert "$branch = 'main'" not in sym_query, "sym_query should not contain $branch = 'main'"
    assert "s.branch = 'main'" in sym_query, "sym_query should contain s.branch = 'main'"
