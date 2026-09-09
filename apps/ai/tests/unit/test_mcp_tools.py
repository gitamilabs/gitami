import json
import pytest
from pathlib import Path
from pathlib import Path
from src.graph.client import Neo4jClient
from src.parsing.parser import CodeParser
from src.graph.writer import upsert_file_and_symbols, upsert_call_edges, upsert_import_edges, delete_repo_data
from src.graph.resolver import resolve_repo_imports
from src.jobs.init_job import run_init_job
from src.mcp.tools import (
    tool_get_repo_structure,
    tool_get_symbol_details,
    tool_get_blast_radius,
    tool_get_file_dependencies,
    tool_search_symbols,
)


@pytest.mark.asyncio
async def test_mcp_tools_against_neo4j():
    client = Neo4jClient()
    await client.connect()
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
                await run_init_job(
                    repo_id="demo-mern",
                    branch="main",
                    repo_dir=fixture_dir,
                    client=client,
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
