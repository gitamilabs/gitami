from typing import Any, Dict, List, Optional
from ai_service.graph.client import Neo4jClient


async def get_symbol(client: Neo4jClient, repo_id: str, branch: str, qualified_name: str) -> Optional[Dict[str, Any]]:
    """Fetch a single symbol node by name or qualified_name within repo_id."""
    query = """
    MATCH (s:Symbol {repo_id: $repo_id, branch: $branch})
    WHERE s.qualified_name = $qualified_name 
       OR s.name = $qualified_name 
       OR toLower(s.name) = toLower($qualified_name)
       OR toLower(s.qualified_name) CONTAINS toLower($qualified_name)
    RETURN properties(s) AS symbol
    LIMIT 1
    """
    records = await client.execute_query(query, {"repo_id": repo_id, "branch": branch, "qualified_name": qualified_name})
    if records and records[0].get("symbol"):
        return records[0]["symbol"]
    return None


async def get_dependents(
    client: Neo4jClient, repo_id: str, branch: str, callee_name: str, max_depth: int = 3
) -> List[Dict[str, Any]]:
    """Traverse the reverse call graph: find all callers depending on callee_name up to max_depth."""
    query = f"""
    MATCH (callee:Symbol {{repo_id: $repo_id, branch: $branch}})
    WHERE callee.name = $callee_name 
       OR callee.qualified_name = $callee_name 
       OR toLower(callee.name) = toLower($callee_name)
       OR toLower(callee.qualified_name) CONTAINS toLower($callee_name)
    MATCH path = (caller:Symbol {{repo_id: $repo_id, branch: $branch}})-[:CALLS*1..{max_depth}]->(callee)
    RETURN DISTINCT caller.qualified_name AS qualified_name,
                    caller.name AS name,
                    caller.file_path AS file_path,
                    caller.kind AS kind,
                    length(path) AS depth
    ORDER BY depth ASC
    """
    records = await client.execute_query(query, {"repo_id": repo_id, "branch": branch, "callee_name": callee_name})
    return records


async def get_dependencies(
    client: Neo4jClient, repo_id: str, branch: str, caller_qualified_name: str, max_depth: int = 3
) -> List[Dict[str, Any]]:
    """Traverse outgoing call graph: find all functions invoked by caller_qualified_name."""
    query = f"""
    MATCH (caller:Symbol {{repo_id: $repo_id, branch: $branch}})
    WHERE caller.qualified_name = $caller_qualified_name 
       OR caller.name = $caller_qualified_name 
       OR toLower(caller.name) = toLower($caller_qualified_name)
       OR toLower(caller.qualified_name) CONTAINS toLower($caller_qualified_name)
    MATCH path = (caller)-[:CALLS*1..{max_depth}]->(callee:Symbol {{repo_id: $repo_id, branch: $branch}})
    RETURN DISTINCT callee.qualified_name AS qualified_name,
                    callee.name AS name,
                    callee.file_path AS file_path,
                    length(path) AS depth
    ORDER BY depth ASC
    """
    records = await client.execute_query(
        query, {"repo_id": repo_id, "branch": branch, "caller_qualified_name": caller_qualified_name}
    )
    return records


async def get_all_symbols(client: Neo4jClient, repo_id: str, branch: str) -> List[Dict[str, Any]]:
    """Fetch all symbols belonging to a repo_id and branch."""
    query = """
    MATCH (s:Symbol {repo_id: $repo_id, branch: $branch})
    RETURN properties(s) AS symbol
    """
    records = await client.execute_query(query, {"repo_id": repo_id, "branch": branch})
    return [r["symbol"] for r in records if "symbol" in r]


async def get_entire_graph(client: Neo4jClient, repo_id: str, branch: str) -> Dict[str, Any]:
    """Fetch all nodes (Files, Symbols, Packages) and edges (DEFINES, CALLS, IMPORTS, DEPENDS_ON) for a repo."""
    nodes = []
    edges = []

    # 1. Fetch Files
    file_query = """
    MATCH (f:File {repo_id: $repo_id, branch: $branch})
    RETURN f.file_path AS id, "File" AS label, properties(f) AS props
    """
    file_records = await client.execute_query(file_query, {"repo_id": repo_id, "branch": branch})
    for r in file_records:
        nodes.append({"id": r["id"], "label": r["label"], "type": "File", "props": r["props"]})

    # 2. Fetch Symbols
    sym_query = """
    MATCH (s:Symbol {repo_id: $repo_id, branch: $branch})
    RETURN s.qualified_name AS id, s.name AS label, properties(s) AS props
    """
    sym_records = await client.execute_query(sym_query, {"repo_id": repo_id, "branch": branch})
    for r in sym_records:
        nodes.append({"id": r["id"], "label": r["label"], "type": "Symbol", "props": r["props"]})

    # 3. Fetch Packages (from external imports)
    pkg_query = """
    MATCH (p:Package {repo_id: $repo_id, branch: $branch})
    RETURN p.name AS id, p.name AS label, properties(p) AS props
    """
    pkg_records = await client.execute_query(pkg_query, {"repo_id": repo_id, "branch": branch})
    for r in pkg_records:
        nodes.append({"id": r["id"], "label": r["label"], "type": "Package", "props": r["props"]})

    # 4. Fetch DEFINES edges (File -> Symbol)
    defines_query = """
    MATCH (f:File {repo_id: $repo_id, branch: $branch})-[:DEFINES]->(s:Symbol {repo_id: $repo_id, branch: $branch})
    RETURN f.file_path AS source, s.qualified_name AS target, "DEFINES" AS relation
    """
    defines_records = await client.execute_query(defines_query, {"repo_id": repo_id, "branch": branch})
    for r in defines_records:
        edges.append({"source": r["source"], "target": r["target"], "relation": r["relation"]})

    # 5. Fetch CALLS edges (Symbol -> Symbol)
    calls_query = """
    MATCH (s1:Symbol {repo_id: $repo_id, branch: $branch})-[r:CALLS]->(s2:Symbol {repo_id: $repo_id, branch: $branch})
    RETURN s1.qualified_name AS source, s2.qualified_name AS target, "CALLS" AS relation, properties(r) AS props
    """
    calls_records = await client.execute_query(calls_query, {"repo_id": repo_id, "branch": branch})
    for r in calls_records:
        edges.append({"source": r["source"], "target": r["target"], "relation": r["relation"], "props": r["props"]})

    # 6. Fetch IMPORTS edges (File -> Symbol)
    imports_query = """
    MATCH (f:File {repo_id: $repo_id, branch: $branch})-[r:IMPORTS]->(s:Symbol {repo_id: $repo_id, branch: $branch})
    RETURN f.file_path AS source, s.qualified_name AS target, "IMPORTS" AS relation, properties(r) AS props
    """
    imports_records = await client.execute_query(imports_query, {"repo_id": repo_id, "branch": branch})
    for r in imports_records:
        edges.append({"source": r["source"], "target": r["target"], "relation": r["relation"], "props": r["props"]})

    # 7. Fetch DEPENDS_ON edges (File -> Package)
    depends_query = """
    MATCH (f:File {repo_id: $repo_id, branch: $branch})-[r:DEPENDS_ON]->(p:Package {repo_id: $repo_id, branch: $branch})
    RETURN f.file_path AS source, p.name AS target, "DEPENDS_ON" AS relation, properties(r) AS props
    """
    depends_records = await client.execute_query(depends_query, {"repo_id": repo_id, "branch": branch})
    for r in depends_records:
        edges.append({"source": r["source"], "target": r["target"], "relation": r["relation"], "props": r["props"]})

    return {"nodes": nodes, "edges": edges}


