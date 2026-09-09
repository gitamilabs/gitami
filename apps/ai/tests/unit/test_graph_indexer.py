import pytest
from unittest.mock import AsyncMock
from src.indexer.graph_indexer import GraphIndexer, make_entity_uid
from src.parsing.models import ParseResult, SymbolNode, HeritageEdge


def test_deterministic_uid_generation():
    # UIDs are branch-independent and stable
    uid1 = make_entity_uid("myorg/myrepo", "func", "src/auth.py", "login")
    uid2 = make_entity_uid("myorg/myrepo", "func", "src/auth.py", "login")
    assert uid1 == uid2
    assert uid1 == "func:myorg/myrepo:src/auth.py::login"

    method_uid = make_entity_uid("myorg/myrepo", "method", "src/user.py", "save", parent="UserService")
    assert method_uid == "method:myorg/myrepo:src/user.py::UserService.save"


@pytest.mark.asyncio
async def test_graph_indexer_queries():
    mock_client = AsyncMock()
    indexer = GraphIndexer(mock_client)

    await indexer.ensure_v1_schema()
    assert mock_client.execute_query.call_count >= 9  # constraints + indexes

    mock_client.reset_mock()
    await indexer.index_repository_node("proj_1", "myorg/myrepo", "c0ffee123456", "main")
    assert mock_client.execute_query.call_count == 1
    call_args = mock_client.execute_query.call_args
    assert "MERGE (r:Repository {uid: $uid})" in call_args[0][0]
    assert call_args[0][1]["uid"] == "repo:myorg/myrepo"


@pytest.mark.asyncio
async def test_idempotent_entity_indexing():
    mock_client = AsyncMock()
    indexer = GraphIndexer(mock_client)

    sym = SymbolNode(
        name="calculate",
        kind="function",
        file_path="math.py",
        language="python",
        start_line=1,
        end_line=5,
        signature="def calculate(x)",
    )
    pr = ParseResult(file_path="math.py", language="python", symbols=[sym])

    # Run 1
    count1 = await indexer.index_symbols_and_entities("repo_a", "sha_111", "main", [pr])
    assert count1 == 1
    query_1 = mock_client.execute_query.call_args[0][0]
    params_1 = mock_client.execute_query.call_args[0][1]

    # Verify MERGE on deterministic uid
    assert "MERGE (e:Function {uid: item.uid})" in query_1
    assert params_1["batch"][0]["uid"] == "func:repo_a:math.py::calculate"

    # Run 2 (same repository and file)
    count2 = await indexer.index_symbols_and_entities("repo_a", "sha_111", "main", [pr])
    assert count2 == 1
    params_2 = mock_client.execute_query.call_args[0][1]
    assert params_1["batch"][0]["uid"] == params_2["batch"][0]["uid"]
