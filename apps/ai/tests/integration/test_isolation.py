import pytest
from unittest.mock import AsyncMock
from src.graph.writer import upsert_symbols, delete_repo_data
from src.graph.reader import get_all_symbols, get_symbol
from src.parsing.models import SymbolNode


@pytest.mark.asyncio
async def test_multi_repo_isolation_logic():
    """Verify that operations on repo_A do not affect or leak data into repo_B."""
    # Store records in in-memory dictionary acting as graph DB mock
    db = {}

    async def fake_execute_query(query, parameters=None):
        params = parameters or {}
        repo_id = params.get("repo_id")
        branch = params.get("branch")

        if "MERGE (s:Symbol" in query:
            batch = params.get("batch", [])
            for item in batch:
                key = (repo_id, branch, item["qualified_name"])
                db[key] = {**item, "repo_id": repo_id, "branch": branch}
            return []

        elif "DETACH DELETE n" in query:
            to_del = [k for k in db if k[0] == repo_id and (not branch or k[1] == branch)]
            for k in to_del:
                del db[k]
            return []

        elif "MATCH (s:Symbol {repo_id: $repo_id, branch: $branch})" in query:
            res = [v for k, v in db.items() if k[0] == repo_id and k[1] == branch]
            return [{"symbol": r} for r in res]

        return []

    mock_client = AsyncMock()
    mock_client.execute_query.side_effect = fake_execute_query

    sym_a = SymbolNode(name="funcA", kind="function", file_path="a.py", language="python", start_line=1, end_line=5, qualified_name="a.py::funcA")
    sym_b = SymbolNode(name="funcB", kind="function", file_path="b.py", language="python", start_line=1, end_line=5, qualified_name="b.py::funcB")

    # Ingest for repo_A and repo_B
    await upsert_symbols(mock_client, repo_id="repo_A", branch="main", symbols=[sym_a])
    await upsert_symbols(mock_client, repo_id="repo_B", branch="main", symbols=[sym_b])

    # Assert repo_A only sees funcA
    symbols_a = await get_all_symbols(mock_client, repo_id="repo_A", branch="main")
    assert len(symbols_a) == 1
    assert symbols_a[0]["name"] == "funcA"

    # Assert repo_B only sees funcB
    symbols_b = await get_all_symbols(mock_client, repo_id="repo_B", branch="main")
    assert len(symbols_b) == 1
    assert symbols_b[0]["name"] == "funcB"

    # Delete repo_A data -> assert repo_B remains untouched!
    await delete_repo_data(mock_client, repo_id="repo_A", branch="main")

    symbols_a_after = await get_all_symbols(mock_client, repo_id="repo_A", branch="main")
    assert len(symbols_a_after) == 0

    symbols_b_after = await get_all_symbols(mock_client, repo_id="repo_B", branch="main")
    assert len(symbols_b_after) == 1
    assert symbols_b_after[0]["name"] == "funcB"
