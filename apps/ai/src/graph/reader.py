from typing import Any, Dict, List, Optional
from src.graph.client import Neo4jClient


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


async def get_entire_graph(
    client: Neo4jClient, repo_id: str, branch: str, max_nodes: int = 500
) -> Dict[str, Any]:
    """Fetch nodes (Files, Symbols, Packages, Inferred) and edges (DEFINES, CALLS, IMPORTS, DEPENDS_ON, DEPENDS_ON_FILE, EXTENDS, IMPLEMENTS, TESTS) for a repo."""
    nodes = []
    edges = []
    node_ids = set()
    id_alias_map = {}

    # 1. Fetch Files
    file_query = """
    MATCH (f:File {repo_id: $repo_id, branch: $branch})
    RETURN f.file_path AS id,
           split(f.file_path, '/')[-1] AS label,
           properties(f) AS props
    LIMIT $limit
    """
    file_records = await client.execute_query(
        file_query, {"repo_id": repo_id, "branch": branch, "limit": max_nodes // 3 or 100}
    )
    for r in file_records:
        fid = r["id"]
        props = r.get("props", {})
        nodes.append({"id": fid, "label": r["label"], "type": "File", "props": props})
        node_ids.add(fid)
        id_alias_map[fid] = fid
        if props.get("uid"):
            id_alias_map[props["uid"]] = fid

    # 2. Fetch Symbols (dual-labeled :Symbol or specific AST kind)
    sym_query = """
    MATCH (s)
    WHERE (s:Symbol OR s:Function OR s:Class OR s:Method OR s:Interface OR s:Type OR s:Test OR s:Schema OR s:Enum OR s:Router OR s:Relation OR s:Variable OR s:Inferred)
      AND s.repo_id = $repo_id AND s.branch = $branch
    RETURN COALESCE(s.qualified_name, s.uid, s.name) AS id,
           COALESCE(s.name, s.qualified_name, s.uid) AS label,
           properties(s) AS props,
           labels(s) AS labels
    LIMIT $limit
    """
    sym_records = await client.execute_query(
        sym_query, {"repo_id": repo_id, "branch": branch, "limit": max_nodes}
    )
    for r in sym_records:
        sym_labels = r.get("labels", [])
        sym_type = next((lbl for lbl in sym_labels if lbl not in ("Symbol",)), "Symbol")
        props = r.get("props", {})
        props["symbol_type"] = sym_type
        sid = r["id"]
        nodes.append({"id": sid, "label": r["label"], "type": sym_type, "props": props})
        node_ids.add(sid)
        id_alias_map[sid] = sid
        if props.get("qualified_name"):
            id_alias_map[props["qualified_name"]] = sid
        if props.get("name"):
            id_alias_map[props["name"]] = sid
        if props.get("uid"):
            id_alias_map[props["uid"]] = sid

    # 3. Fetch Packages (from external imports)
    pkg_query = """
    MATCH (p:Package {repo_id: $repo_id, branch: $branch})
    RETURN COALESCE(p.uid, p.name) AS id, p.name AS label, properties(p) AS props
    LIMIT 100
    """
    pkg_records = await client.execute_query(pkg_query, {"repo_id": repo_id, "branch": branch})
    for r in pkg_records:
        pid = r["id"]
        props = r.get("props", {})
        nodes.append({"id": pid, "label": r["label"], "type": "Package", "props": props})
        node_ids.add(pid)
        id_alias_map[pid] = pid
        if props.get("name"):
            id_alias_map[props["name"]] = pid
        if props.get("uid"):
            id_alias_map[props["uid"]] = pid

    def add_edge(src_raw: str, tgt_raw: str, rel: str, props: Optional[Dict[str, Any]] = None):
        src = id_alias_map.get(src_raw, src_raw)
        tgt = id_alias_map.get(tgt_raw, tgt_raw)
        if src in node_ids and tgt in node_ids:
            edge_obj = {"source": src, "target": tgt, "relation": rel}
            if props:
                edge_obj["props"] = props
            edges.append(edge_obj)

    # 4. Fetch DEFINES edges (File -> Symbol)
    defines_query = """
    MATCH (f:File {repo_id: $repo_id, branch: $branch})-[:DEFINES]->(s)
    WHERE s.repo_id = $repo_id AND s.branch = $branch
    RETURN f.file_path AS source, COALESCE(s.qualified_name, s.uid, s.name) AS target, "DEFINES" AS relation
    LIMIT $limit
    """
    defines_records = await client.execute_query(
        defines_query, {"repo_id": repo_id, "branch": branch, "limit": max_nodes * 2}
    )
    for r in defines_records:
        add_edge(r["source"], r["target"], r["relation"])

    # 5. Fetch CALLS edges (Symbol/File -> Symbol/Inferred)
    calls_query = """
    MATCH (s1)-[r:CALLS]->(s2)
    WHERE s1.repo_id = $repo_id AND s1.branch = $branch
      AND s2.repo_id = $repo_id AND s2.branch = $branch
    RETURN COALESCE(s1.qualified_name, s1.file_path, s1.uid, s1.name) AS source,
           COALESCE(s2.qualified_name, s2.uid, s2.name) AS target,
           "CALLS" AS relation,
           properties(r) AS props
    LIMIT $limit
    """
    calls_records = await client.execute_query(
        calls_query, {"repo_id": repo_id, "branch": branch, "limit": max_nodes * 2}
    )
    for r in calls_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    # 6. Fetch IMPORTS edges (File -> Symbol)
    imports_query = """
    MATCH (f:File {repo_id: $repo_id, branch: $branch})-[r:IMPORTS]->(s)
    WHERE s.repo_id = $repo_id AND s.branch = $branch
    RETURN f.file_path AS source, COALESCE(s.qualified_name, s.uid, s.name) AS target, "IMPORTS" AS relation, properties(r) AS props
    LIMIT $limit
    """
    imports_records = await client.execute_query(
        imports_query, {"repo_id": repo_id, "branch": branch, "limit": max_nodes * 2}
    )
    for r in imports_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    # 7. Fetch DEPENDS_ON edges (File -> Package)
    depends_query = """
    MATCH (f:File {repo_id: $repo_id, branch: $branch})-[r:DEPENDS_ON]->(p:Package {repo_id: $repo_id, branch: $branch})
    RETURN f.file_path AS source, COALESCE(p.uid, p.name) AS target, "DEPENDS_ON" AS relation, properties(r) AS props
    LIMIT $limit
    """
    depends_records = await client.execute_query(
        depends_query, {"repo_id": repo_id, "branch": branch, "limit": max_nodes}
    )
    for r in depends_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    # 8. Fetch DEPENDS_ON_FILE edges (File -> File)
    file_dep_query = """
    MATCH (f1:File {repo_id: $repo_id, branch: $branch})-[r:DEPENDS_ON_FILE]->(f2:File {repo_id: $repo_id, branch: $branch})
    RETURN f1.file_path AS source, f2.file_path AS target, "DEPENDS_ON_FILE" AS relation, properties(r) AS props
    LIMIT $limit
    """
    file_dep_records = await client.execute_query(
        file_dep_query, {"repo_id": repo_id, "branch": branch, "limit": max_nodes}
    )
    for r in file_dep_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    # 9. Fetch EXTENDS edges (Class -> Class)
    extends_query = """
    MATCH (c1:Class {repo_id: $repo_id, branch: $branch})-[r:EXTENDS]->(c2:Class {repo_id: $repo_id, branch: $branch})
    RETURN COALESCE(c1.qualified_name, c1.uid, c1.name) AS source,
           COALESCE(c2.qualified_name, c2.uid, c2.name) AS target,
           "EXTENDS" AS relation,
           properties(r) AS props
    LIMIT $limit
    """
    extends_records = await client.execute_query(
        extends_query, {"repo_id": repo_id, "branch": branch, "limit": max_nodes}
    )
    for r in extends_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    # 10. Fetch IMPLEMENTS edges (Class -> Interface)
    implements_query = """
    MATCH (c:Class {repo_id: $repo_id, branch: $branch})-[r:IMPLEMENTS]->(i:Interface {repo_id: $repo_id, branch: $branch})
    RETURN COALESCE(c.qualified_name, c.uid, c.name) AS source,
           COALESCE(i.qualified_name, i.uid, i.name) AS target,
           "IMPLEMENTS" AS relation,
           properties(r) AS props
    LIMIT $limit
    """
    implements_records = await client.execute_query(
        implements_query, {"repo_id": repo_id, "branch": branch, "limit": max_nodes}
    )
    for r in implements_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    # 11. Fetch TESTS edges (Test -> Target)
    tests_query = """
    MATCH (t:Test {repo_id: $repo_id, branch: $branch})-[r:TESTS]->(tgt {repo_id: $repo_id, branch: $branch})
    RETURN COALESCE(t.qualified_name, t.uid, t.name) AS source,
           COALESCE(tgt.qualified_name, tgt.uid, tgt.name) AS target,
           "TESTS" AS relation,
           properties(r) AS props
    LIMIT $limit
    """
    tests_records = await client.execute_query(
        tests_query, {"repo_id": repo_id, "branch": branch, "limit": max_nodes}
    )
    for r in tests_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    extracted_count = sum(1 for n in nodes if n.get("props", {}).get("provenance") != "INFERRED")
    inferred_count = sum(1 for n in nodes if n.get("props", {}).get("provenance") == "INFERRED" or n.get("type") == "Inferred")

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
            "extractedCount": extracted_count,
            "inferredCount": inferred_count,
            "synthesizedCount": 0,
            "observedCount": 0,
        },
    }


