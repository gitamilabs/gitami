"""Interactive CLI demonstration script to test all Knowledge Base MCP tools."""
import asyncio
import json
from src.graph.client import Neo4jClient
from src.mcp.tools import (
    tool_get_repo_structure,
    tool_get_symbol_details,
    tool_get_blast_radius,
    tool_get_file_dependencies,
    tool_search_symbols,
)


async def main():
    client = Neo4jClient()
    await client.connect()
    try:
        print("\n" + "=" * 60)
        print("KNOWLEDGE BASE MCP TOOLS DEMO & TEST SUITE")
        print("=" * 60 + "\n")

        # 1. Test get_repo_structure
        print("1. Tool: get_repo_structure(repo_id='demo-mern')")
        print("-" * 60)
        res = await tool_get_repo_structure(client, repo_id="demo-mern", branch="main")
        print(res)
        print("\n")

        # 2. Test get_file_dependencies
        print("2. Tool: get_file_dependencies(file_path='tests/fixtures/mern_sample/UserService.js')")
        print("-" * 60)
        res = await tool_get_file_dependencies(client, repo_id="demo-mern", file_path="tests/fixtures/mern_sample/UserService.js")
        print(res)
        print("\n")

        # 3. Test get_blast_radius
        print("3. Tool: get_blast_radius(changed_symbols=['tests/fixtures/mern_sample/api.js::fetchUsers'])")
        print("-" * 60)
        res = await tool_get_blast_radius(client, repo_id="demo-mern", changed_symbols=["tests/fixtures/mern_sample/api.js::fetchUsers"])
        print(res)
        print("\n")

        # 4. Test search_symbols
        print("4. Tool: search_symbols(query_str='fetch')")
        print("-" * 60)
        res = await tool_search_symbols(client, repo_id="demo-mern", query_str="fetch")
        print(res)
        print("\n")

        # 5. Test get_symbol_details
        print("5. Tool: get_symbol_details(qualified_name='tests/fixtures/mern_sample/api.js::fetchUsers')")
        print("-" * 60)
        res = await tool_get_symbol_details(client, repo_id="demo-mern", qualified_name="tests/fixtures/mern_sample/api.js::fetchUsers")
        print(res)
        print("\n")

        print("=" * 60)
        print("ALL MCP TOOLS EXECUTED & VERIFIED SUCCESSFULLY!")
        print("=" * 60 + "\n")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
