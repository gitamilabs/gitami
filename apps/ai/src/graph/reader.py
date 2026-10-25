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

    # 1. Resolve canonical repository from Neo4j (case-insensitive and suffix-tolerant)
    repo_records = await client.execute_query(
        """
        MATCH (r:Repository)
        WHERE toLower(r.repo_id) = toLower($repo_id)
           OR toLower(r.repo_id) ENDS WITH '/' + toLower($repo_id)
           OR toLower($repo_id) ENDS WITH '/' + toLower(r.repo_id)
        RETURN r.repo_id AS canonical_id, r.uid AS id, properties(r) AS props
        LIMIT 1
        """,
        {"repo_id": repo_id},
    )
    if repo_records:
        canonical_repo_id = repo_records[0].get("canonical_id", repo_id)
        repo_uid = repo_records[0].get("id") or f"repo:{canonical_repo_id}"
        repo_node_props = repo_records[0].get("props", {})
    else:
        canonical_repo_id = repo_id
        repo_uid = f"repo:{repo_id}"
        repo_node_props = {}

    repo_short = canonical_repo_id.split("/")[-1]
    nodes.append({
        "id": repo_uid,
        "label": repo_short,
        "type": "Repository",
        "props": repo_node_props,
        "level": 0,
        "path": "",
        "isRoot": True,
    })
    node_ids.add(repo_uid)
    id_alias_map[repo_uid] = repo_uid
    id_alias_map[canonical_repo_id] = repo_uid
    id_alias_map[repo_id] = repo_uid

    # 2. Fetch Directories
    dir_query = """
    MATCH (d:Directory)
    WHERE toLower(d.repo_id) = toLower($canonical_repo_id)
    RETURN d.uid AS uid, d.path AS path, COALESCE(d.name, split(d.path, '/')[-1]) AS label,
           COALESCE(d.depth, size(split(d.path, '/'))) AS depth, properties(d) AS props
    LIMIT 300
    """
    dir_records = await client.execute_query(dir_query, {"canonical_repo_id": canonical_repo_id})
    for r in dir_records:
        did = r["path"]
        if did in node_ids:
            continue
        depth = int(r.get("depth") or len(did.split("/")))
        props = r.get("props", {})
        nodes.append({
            "id": did,
            "label": r["label"],
            "type": "Directory",
            "props": props,
            "level": depth,
            "path": did,
            "isFolder": True,
        })
        node_ids.add(did)
        id_alias_map[did] = did
        if r.get("uid"):
            id_alias_map[r["uid"]] = did

    # 3. Fetch Files
    file_query = """
    MATCH (f:File)
    WHERE toLower(f.repo_id) = toLower($canonical_repo_id)
      AND (f.branch IS NULL OR f.branch = $branch OR $branch = '' OR $branch = 'main')
    RETURN f.file_path AS id,
           split(f.file_path, '/')[-1] AS label,
           f.parent_dir AS parent_dir,
           size(split(f.file_path, '/')) AS depth,
           properties(f) AS props
    LIMIT $limit
    """
    file_records = await client.execute_query(
        file_query, {"canonical_repo_id": canonical_repo_id, "branch": branch, "limit": max_nodes // 3 or 100}
    )
    for r in file_records:
        fid = r["id"]
        if fid in node_ids:
            continue
        props = r.get("props", {})
        depth = int(r.get("depth") or len(fid.split("/")))
        parent_dir = r.get("parent_dir") or (repo_uid if "/" not in fid else fid.rsplit("/", 1)[0])
        nodes.append({
            "id": fid,
            "label": r["label"],
            "type": "File",
            "props": props,
            "level": depth + 1,
            "path": fid,
            "parentId": parent_dir,
            "isFile": True,
        })
        node_ids.add(fid)
        id_alias_map[fid] = fid
        if props.get("uid"):
            id_alias_map[props["uid"]] = fid

    # 4. Fetch Symbols (dual-labeled :Symbol or specific AST kind)
    sym_query = """
    MATCH (s)
    WHERE (s:Symbol OR s:Function OR s:Class OR s:Method OR s:Interface OR s:Type OR s:Test OR s:Schema OR s:Enum OR s:Router OR s:Relation OR s:Variable OR s:Inferred)
      AND toLower(s.repo_id) = toLower($canonical_repo_id)
      AND (s.branch IS NULL OR s.branch = $branch OR $branch = '' OR $branch = 'main')
      AND NOT (s.name STARTS WITH "{" OR s.name STARTS WITH "[" OR s.name CONTAINS ",")
    RETURN COALESCE(s.qualified_name, s.uid, s.name) AS id,
           COALESCE(s.name, s.qualified_name, s.uid) AS label,
           properties(s) AS props,
           labels(s) AS labels
    LIMIT $limit
    """
    sym_records = await client.execute_query(
        sym_query, {"canonical_repo_id": canonical_repo_id, "branch": branch, "limit": max_nodes}
    )
    for r in sym_records:
        name_val = str(r.get("label") or "")
        if name_val.startswith(("{", "[")) or "," in name_val:
            continue
        sym_labels = r.get("labels", [])
        sym_type = next((lbl for lbl in sym_labels if lbl not in ("Symbol",)), "Symbol")
        props = r.get("props", {})
        props["symbol_type"] = sym_type
        sid = r["id"]
        if sid in node_ids:
            uid = props.get("uid")
            if uid and uid not in node_ids:
                sid = uid
            else:
                continue

        # Calculate hierarchical level
        fpath = props.get("file_path", "")
        fdepth = len(fpath.split("/")) if fpath else 2
        if sym_type in ("Class", "Schema", "Router", "Enum", "Interface"):
            level = fdepth + 2
        elif sym_type in ("Method",):
            level = fdepth + 3
        elif sym_type == "Inferred" or props.get("provenance") == "INFERRED":
            level = 7
        else:
            level = fdepth + 2

        parent_id = props.get("class_name") if sym_type == "Method" else fpath

        nodes.append({
            "id": sid,
            "label": r["label"],
            "type": sym_type,
            "props": props,
            "level": level,
            "path": fpath,
            "parentId": parent_id,
        })
        node_ids.add(sid)
        id_alias_map[sid] = sid
        if props.get("qualified_name"):
            id_alias_map.setdefault(props["qualified_name"], sid)
        if props.get("name"):
            id_alias_map.setdefault(props["name"], sid)
        if props.get("uid"):
            id_alias_map[props["uid"]] = sid

    # 5. Fetch Packages (from external imports)
    pkg_query = """
    MATCH (p:Package)
    WHERE toLower(p.repo_id) = toLower($canonical_repo_id)
    RETURN COALESCE(p.uid, p.name) AS id, p.name AS label, properties(p) AS props
    LIMIT 100
    """
    pkg_records = await client.execute_query(pkg_query, {"canonical_repo_id": canonical_repo_id})
    for r in pkg_records:
        pid = r["id"]
        if pid in node_ids:
            continue
        props = r.get("props", {})
        nodes.append({
            "id": pid,
            "label": r["label"],
            "type": "Package",
            "props": props,
            "level": 7,
        })
        node_ids.add(pid)
        id_alias_map[pid] = pid
        if props.get("name"):
            id_alias_map.setdefault(props["name"], pid)
        if props.get("uid"):
            id_alias_map[props["uid"]] = pid

    def add_edge(src_raw: str, tgt_raw: str, rel: str, props: Optional[Dict[str, Any]] = None):
        src = id_alias_map.get(src_raw, src_raw)
        tgt = id_alias_map.get(tgt_raw, tgt_raw)
        if src in node_ids and tgt in node_ids and src != tgt:
            edge_obj = {"source": src, "target": tgt, "relation": rel}
            if props:
                edge_obj["props"] = props
            edges.append(edge_obj)

    # 6. Fetch CONTAINS edges (Repository -> Directory, Directory -> Directory, Directory -> File, Repository -> File)
    contains_query = """
    MATCH (src)-[r:CONTAINS]->(dst)
    WHERE (src:Repository OR src:Directory)
      AND (dst:Directory OR dst:File)
      AND toLower(src.repo_id) = toLower($canonical_repo_id)
    RETURN COALESCE(src.path, src.uid) AS source,
           COALESCE(dst.path, dst.file_path, dst.uid) AS target,
           "CONTAINS" AS relation,
           properties(r) AS props
    LIMIT $limit
    """
    contains_records = await client.execute_query(
        contains_query, {"canonical_repo_id": canonical_repo_id, "limit": max_nodes * 2}
    )
    for r in contains_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    # 7. Fetch DEFINES edges (File -> Symbol)
    defines_query = """
    MATCH (f:File)-[:DEFINES]->(s)
    WHERE toLower(f.repo_id) = toLower($canonical_repo_id)
      AND toLower(s.repo_id) = toLower($canonical_repo_id)
    RETURN f.file_path AS source, COALESCE(s.qualified_name, s.uid, s.name) AS target, "DEFINES" AS relation
    LIMIT $limit
    """
    defines_records = await client.execute_query(
        defines_query, {"canonical_repo_id": canonical_repo_id, "limit": max_nodes * 2}
    )
    for r in defines_records:
        add_edge(r["source"], r["target"], r["relation"])

    # 8. Fetch HAS_METHOD edges (Class -> Method)
    has_method_query = """
    MATCH (c:Class)-[r:HAS_METHOD]->(m:Method)
    WHERE toLower(c.repo_id) = toLower($canonical_repo_id)
      AND toLower(m.repo_id) = toLower($canonical_repo_id)
    RETURN COALESCE(c.qualified_name, c.uid, c.name) AS source,
           COALESCE(m.qualified_name, m.uid, m.name) AS target,
           "HAS_METHOD" AS relation,
           properties(r) AS props
    LIMIT $limit
    """
    has_method_records = await client.execute_query(
        has_method_query, {"canonical_repo_id": canonical_repo_id, "limit": max_nodes}
    )
    for r in has_method_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    # 9. Fetch CALLS edges (Symbol/File -> Symbol/Inferred)
    calls_query = """
    MATCH (s1)-[r:CALLS]->(s2)
    WHERE toLower(s1.repo_id) = toLower($canonical_repo_id)
      AND toLower(s2.repo_id) = toLower($canonical_repo_id)
    RETURN COALESCE(s1.qualified_name, s1.file_path, s1.uid, s1.name) AS source,
           COALESCE(s2.qualified_name, s2.uid, s2.name) AS target,
           "CALLS" AS relation,
           properties(r) AS props
    LIMIT $limit
    """
    calls_records = await client.execute_query(
        calls_query, {"canonical_repo_id": canonical_repo_id, "limit": max_nodes * 2}
    )
    for r in calls_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    # 10. Fetch IMPORTS edges (File -> Symbol)
    imports_query = """
    MATCH (f:File)-[r:IMPORTS]->(s)
    WHERE toLower(f.repo_id) = toLower($canonical_repo_id)
      AND toLower(s.repo_id) = toLower($canonical_repo_id)
    RETURN f.file_path AS source, COALESCE(s.qualified_name, s.uid, s.name) AS target, "IMPORTS" AS relation, properties(r) AS props
    LIMIT $limit
    """
    imports_records = await client.execute_query(
        imports_query, {"canonical_repo_id": canonical_repo_id, "limit": max_nodes * 2}
    )
    for r in imports_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    # 11. Fetch DEPENDS_ON edges (File -> Package)
    depends_query = """
    MATCH (f:File)-[r:DEPENDS_ON]->(p:Package)
    WHERE toLower(f.repo_id) = toLower($canonical_repo_id)
      AND toLower(p.repo_id) = toLower($canonical_repo_id)
    RETURN f.file_path AS source, COALESCE(p.uid, p.name) AS target, "DEPENDS_ON" AS relation, properties(r) AS props
    LIMIT $limit
    """
    depends_records = await client.execute_query(
        depends_query, {"canonical_repo_id": canonical_repo_id, "limit": max_nodes}
    )
    for r in depends_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    # 12. Fetch DEPENDS_ON_FILE edges (File -> File)
    file_dep_query = """
    MATCH (f1:File)-[r:DEPENDS_ON_FILE]->(f2:File)
    WHERE toLower(f1.repo_id) = toLower($canonical_repo_id)
      AND toLower(f2.repo_id) = toLower($canonical_repo_id)
    RETURN f1.file_path AS source, f2.file_path AS target, "DEPENDS_ON_FILE" AS relation, properties(r) AS props
    LIMIT $limit
    """
    file_dep_records = await client.execute_query(
        file_dep_query, {"canonical_repo_id": canonical_repo_id, "limit": max_nodes}
    )
    for r in file_dep_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    # 13. Fetch EXTENDS edges (Class -> Class)
    extends_query = """
    MATCH (c1:Class)-[r:EXTENDS]->(c2:Class)
    WHERE toLower(c1.repo_id) = toLower($canonical_repo_id)
      AND toLower(c2.repo_id) = toLower($canonical_repo_id)
    RETURN COALESCE(c1.qualified_name, c1.uid, c1.name) AS source,
           COALESCE(c2.qualified_name, c2.uid, c2.name) AS target,
           "EXTENDS" AS relation,
           properties(r) AS props
    LIMIT $limit
    """
    extends_records = await client.execute_query(
        extends_query, {"canonical_repo_id": canonical_repo_id, "limit": max_nodes}
    )
    for r in extends_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    # 14. Fetch IMPLEMENTS edges (Class -> Interface)
    implements_query = """
    MATCH (c:Class)-[r:IMPLEMENTS]->(i:Interface)
    WHERE toLower(c.repo_id) = toLower($canonical_repo_id)
      AND toLower(i.repo_id) = toLower($canonical_repo_id)
    RETURN COALESCE(c.qualified_name, c.uid, c.name) AS source,
           COALESCE(i.qualified_name, i.uid, i.name) AS target,
           "IMPLEMENTS" AS relation,
           properties(r) AS props
    LIMIT $limit
    """
    implements_records = await client.execute_query(
        implements_query, {"canonical_repo_id": canonical_repo_id, "limit": max_nodes}
    )
    for r in implements_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    # 15. Fetch TESTS edges (Test -> Target)
    tests_query = """
    MATCH (t:Test)-[r:TESTS]->(tgt)
    WHERE toLower(t.repo_id) = toLower($canonical_repo_id)
      AND toLower(tgt.repo_id) = toLower($canonical_repo_id)
    RETURN COALESCE(t.qualified_name, t.uid, t.name) AS source,
           COALESCE(tgt.qualified_name, tgt.uid, tgt.name) AS target,
           "TESTS" AS relation,
           properties(r) AS props
    LIMIT $limit
    """
    tests_records = await client.execute_query(
        tests_query, {"canonical_repo_id": canonical_repo_id, "limit": max_nodes}
    )
    for r in tests_records:
        add_edge(r["source"], r["target"], r["relation"], r.get("props"))

    # 16. Fallback synthesis for structural containment: guarantee all directories and files are connected
    existing_edges = {(e["source"], e["target"]) for e in edges}
    for n in nodes:
        nid = n["id"]
        ntype = n.get("type")
        if ntype == "Directory":
            parent = nid.rsplit("/", 1)[0] if "/" in nid else repo_uid
            if (parent, nid) not in existing_edges and parent in node_ids:
                edges.append({"source": parent, "target": nid, "relation": "CONTAINS"})
                existing_edges.add((parent, nid))
        elif ntype == "File":
            fpath = n.get("path") or nid
            parent = fpath.rsplit("/", 1)[0] if "/" in fpath else repo_uid
            if (parent, nid) not in existing_edges and parent in node_ids:
                edges.append({"source": parent, "target": nid, "relation": "CONTAINS"})
                existing_edges.add((parent, nid))
        elif ntype in ("Function", "Class", "Interface", "Type", "Schema", "Router", "Enum"):
            fpath = n.get("path", "")
            if fpath and fpath in node_ids and (fpath, nid) not in existing_edges:
                edges.append({"source": fpath, "target": nid, "relation": "DEFINES"})
                existing_edges.add((fpath, nid))
        elif ntype == "Method":
            pclass = n.get("parentId")
            if pclass and pclass in node_ids and (pclass, nid) not in existing_edges:
                edges.append({"source": pclass, "target": nid, "relation": "HAS_METHOD"})
                existing_edges.add((pclass, nid))

    # Compute child counts and resolved parent IDs from structural edges
    child_counts: Dict[str, int] = {}
    parent_map: Dict[str, str] = {}
    for e in edges:
        if e.get("relation") in ("CONTAINS", "DEFINES", "HAS_METHOD"):
            src = e["source"]
            tgt = e["target"]
            child_counts[src] = child_counts.get(src, 0) + 1
            if tgt not in parent_map:
                parent_map[tgt] = src

    for n in nodes:
        nid = n["id"]
        n["childCount"] = child_counts.get(nid, 0)
        if nid in parent_map:
            n["parentId"] = parent_map[nid]

    extracted_count = sum(1 for n in nodes if n.get("props", {}).get("provenance") != "INFERRED" and n.get("type") not in ("Directory", "Repository"))
    inferred_count = sum(1 for n in nodes if n.get("props", {}).get("provenance") == "INFERRED" or n.get("type") == "Inferred")
    dir_count = sum(1 for n in nodes if n.get("type") == "Directory")
    file_count = sum(1 for n in nodes if n.get("type") == "File")
    sym_count = sum(1 for n in nodes if n.get("type") not in ("Directory", "File", "Repository", "Package", "Inferred"))

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
            "extractedCount": extracted_count,
            "inferredCount": inferred_count,
            "directoryCount": dir_count,
            "fileCount": file_count,
            "symbolCount": sym_count,
            "synthesizedCount": 0,
            "observedCount": 0,
        },
    }


