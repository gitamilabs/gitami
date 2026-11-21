import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from src.graph.client import Neo4jClient
from src.parsing.parser import CodeParser
from src.graph.writer import upsert_file_and_symbols, upsert_call_edges, upsert_import_edges, delete_repo_data
from src.graph.resolver import resolve_repo_imports
from src.indexer.pipeline import RepositoryIndexer
from src.mcp.tools import (
    tool_get_repo_structure,
    tool_get_symbol_details,
    tool_get_blast_radius,
    tool_get_file_dependencies,
    tool_search_symbols,
    execute_tool_by_name,
)


@pytest.mark.asyncio
async def test_tool_get_repo_structure_hermetic():
    client = AsyncMock()
    client.execute_query.return_value = [
        {"file_path": "main.py", "language": "python", "symbols": [{"name": "app", "kind": "variable", "qname": "main.py::app"}]}
    ]
    res_str = await tool_get_repo_structure(client, repo_id="org/repo", branch="main")
    res = json.loads(res_str)
    assert res["repo_id"] == "org/repo"
    assert len(res["files"]) == 1
    assert res["files"][0]["file_path"] == "main.py"


@pytest.mark.asyncio
async def test_tool_get_symbol_details_hermetic():
    client = AsyncMock()
    # Mock symbol lookup found
    client.execute_query.side_effect = [
        [{"symbol": {"name": "calculate", "qualified_name": "calc.py::calculate"}}],  # get_symbol
        [{"qualified_name": "caller.py::run", "name": "run", "file_path": "caller.py", "kind": "function", "depth": 1}],  # get_dependents
        [{"qualified_name": "math.py::add", "name": "add", "file_path": "math.py", "depth": 1}],  # get_dependencies
    ]
    res_str = await tool_get_symbol_details(client, repo_id="org/repo", qualified_name="calculate", branch="main")
    res = json.loads(res_str)
    assert "symbol" in res
    assert res["symbol"]["name"] == "calculate"
    assert len(res["callers"]) == 1
    assert len(res["callees"]) == 1


@pytest.mark.asyncio
async def test_tool_get_file_dependencies_hermetic():
    client = AsyncMock()
    client.execute_query.return_value = [
        {
            "file_path": "src/app.py",
            "imported_by_files": ["tests/test_app.py"],
            "imports_files": ["src/db.py"],
            "external_packages": ["fastapi"],
        }
    ]
    res_str = await tool_get_file_dependencies(client, repo_id="org/repo", file_path="src/app.py", branch="main")
    res = json.loads(res_str)
    assert res["file_path"] == "src/app.py"
    assert "tests/test_app.py" in res["imported_by_files"]
    assert "src/db.py" in res["imports_files"]
    assert "fastapi" in res["external_packages"]


@pytest.mark.asyncio
async def test_tool_search_symbols_hermetic():
    client = AsyncMock()
    client.execute_query.return_value = [
        {"symbol": {"name": "login", "qualified_name": "auth.py::login"}}
    ]
    res_str = await tool_search_symbols(client, repo_id="org/repo", query_str="login", branch="main")
    res = json.loads(res_str)
    assert isinstance(res, list)
    assert len(res) == 1
    assert res[0]["name"] == "login"


@pytest.mark.asyncio
async def test_execute_tool_by_name_dispatch():
    mock_gc = AsyncMock()
    mock_vc = MagicMock()
    mock_gc.execute_query.return_value = [{"symbol": {"name": "foo"}}]

    res_str = await execute_tool_by_name(
        tool_name="search_symbols",
        tool_args={"query": "foo"},
        graph_client=mock_gc,
        vector_client=mock_vc,
        repo_id="org/repo",
    )
    res = json.loads(res_str)
    assert isinstance(res, list)
    assert res[0]["name"] == "foo"


@pytest.mark.asyncio
async def test_mcp_tools_against_neo4j():
    client = Neo4jClient()
    try:
        await asyncio.wait_for(client.verify_connectivity(), timeout=1.5)
    except Exception:
        pytest.skip("Neo4j database is not running, skipping live MCP test")
    try:
        # Seed test data for demo-mern
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "mern_sample"
        parser = CodeParser()
        parse_results = parser.parse_directory(fixtures_dir)
        for pr in parse_results:
            await upsert_file_and_symbols(client, repo_id="demo-mern", branch="main", file_path=pr.file_path, language=pr.language, symbols=pr.symbols)
        for pr in parse_results:
            await upsert_call_edges(client, repo_id="demo-mern", branch="main", calls=pr.calls)
            await upsert_import_edges(client, repo_id="demo-mern", branch="main", imports=pr.imports)
        await resolve_repo_imports(client, repo_id="demo-mern", branch="main")

        # Check if demo-mern is seeded, otherwise seed it from fixture
        struct_json = await tool_get_repo_structure(client, repo_id="demo-mern", branch="main")
        struct = json.loads(struct_json)
        if len(struct.get("files", [])) == 0:
            fixture_dir = Path(__file__).parent.parent / "fixtures" / "mern_sample"
            if fixture_dir.exists():
                indexer = RepositoryIndexer(graph_client=client)
                await indexer.run(
                    repo_id="demo-mern",
                    branch="main",
                    repo_dir=fixture_dir,
                )
                struct_json = await tool_get_repo_structure(client, repo_id="demo-mern", branch="main")
                struct = json.loads(struct_json)

        assert struct["repo_id"] == "demo-mern"

        # Test search symbols
        search_json = await tool_search_symbols(client, repo_id="demo-mern", query_str="fetchUsers")
        results = json.loads(search_json)
        assert isinstance(results, list)

        # Test blast radius
        blast_json = await tool_get_blast_radius(client, repo_id="demo-mern", changed_symbols=["api.js::fetchUsers"])
        blast = json.loads(blast_json)
        assert "risk_score" in blast

        # Test file dependencies
        file_deps_json = await tool_get_file_dependencies(client, repo_id="demo-mern", file_path="UserService.js")
        file_deps_json = await tool_get_file_dependencies(client, repo_id="demo-mern", file_path="UserService.js")
        deps = json.loads(file_deps_json)
        assert "api.js" in deps["imports_files"]
    finally:
        await delete_repo_data(client, repo_id="demo-mern", branch="main")
        await client.close()
