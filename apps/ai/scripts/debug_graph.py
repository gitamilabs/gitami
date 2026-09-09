"""Dump graph structure for inspection."""
import asyncio
from src.graph.client import Neo4jClient


async def main():
    c = Neo4jClient()
    await c.connect()

    # Count nodes by label
    res = await c.execute_query("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label")
    print("=== NODE COUNTS ===")
    for r in res:
        print(f"  {r['label']}: {r['count']}")

    # Count relationships by type
    res = await c.execute_query("MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count ORDER BY rel_type")
    print("\n=== EDGE COUNTS ===")
    for r in res:
        print(f"  {r['rel_type']}: {r['count']}")

    # Show all File nodes
    res = await c.execute_query("MATCH (f:File) RETURN f.file_path AS path, f.repo_id AS repo ORDER BY f.repo_id, f.file_path")
    print("\n=== FILES ===")
    for r in res:
        print(f"  [{r['repo']}] {r['path']}")

    # Show all Symbols with their file
    res = await c.execute_query("MATCH (f:File)-[:DEFINES]->(s:Symbol) RETURN f.file_path AS file, s.name AS name, s.kind AS kind, s.repo_id AS repo ORDER BY s.repo_id, f.file_path, s.start_line")
    print("\n=== FILE -> DEFINES -> SYMBOL ===")
    for r in res:
        print(f"  [{r['repo']}] {r['file']} -> {r['kind']}: {r['name']}")

    # Show all CALLS edges
    res = await c.execute_query("MATCH (a:Symbol)-[:CALLS]->(b:Symbol) RETURN a.name AS caller, b.name AS callee, a.repo_id AS repo ORDER BY a.repo_id, a.name")
    print("\n=== CALLS ===")
    for r in res:
        print(f"  [{r['repo']}] {r['caller']} -> {r['callee']}")

    # Show IMPORTS edges
    res = await c.execute_query("MATCH (f:File)-[:IMPORTS]->(s:Symbol) RETURN f.file_path AS file, s.name AS sym, f.repo_id AS repo ORDER BY f.repo_id, f.file_path")
    print("\n=== IMPORTS ===")
    for r in res:
        print(f"  [{r['repo']}] {r['file']} -> {r['sym']}")

    # Show DEPENDS_ON (external)
    res = await c.execute_query("MATCH (f:File)-[:DEPENDS_ON]->(p:Package) RETURN f.file_path AS file, p.name AS pkg, f.repo_id AS repo ORDER BY f.repo_id")
    print("\n=== DEPENDS_ON (External) ===")
    for r in res:
        print(f"  [{r['repo']}] {r['file']} -> {r['pkg']}")

    # Show orphan symbols (no DEFINES relationship)
    res = await c.execute_query("MATCH (s:Symbol) WHERE NOT ()-[:DEFINES]->(s) RETURN s.name AS name, s.qualified_name AS qn, s.repo_id AS repo")
    print("\n=== ORPHAN SYMBOLS (no File DEFINES them) ===")
    for r in res:
        print(f"  [{r['repo']}] {r['name']} ({r['qn']})")

    await c.close()


asyncio.run(main())
