import json
from typing import Any, Dict, List, Optional
from ai_service.graph.client import Neo4jClient
from ai_service.graph.reader import get_symbol, get_dependents, get_dependencies, get_all_symbols
from ai_service.analysis.blast_radius import compute_blast_radius
from ai_service.analysis.conventions import check_conventions
from ai_service.parsing.parser import CodeParser


async def tool_get_repo_structure(client: Neo4jClient, repo_id: str, branch: str = "main") -> str:
    """Retrieve full file and symbol hierarchy for a repository."""
    query = """
    MATCH (f:File {repo_id: $repo_id, branch: $branch})
    OPTIONAL MATCH (f)-[:DEFINES]->(s:Symbol)
    RETURN f.file_path AS file_path, f.language AS language, collect({name: s.name, kind: s.kind, qname: s.qualified_name}) AS symbols
    ORDER BY file_path
    """
    records = await client.execute_query(query, {"repo_id": repo_id, "branch": branch})
    return json.dumps({"repo_id": repo_id, "branch": branch, "files": records}, indent=2)


async def tool_get_symbol_details(client: Neo4jClient, repo_id: str, qualified_name: str, branch: str = "main") -> str:
    """Retrieve detailed properties, callers, and callees for a given symbol or file qualified_name."""
    qname_clean = qualified_name.strip()

    # 1. Try direct symbol lookup
    sym = await get_symbol(client, repo_id, branch, qname_clean)

    # 2. If no direct symbol match, check if qualified_name matches a File node
    if not sym:
        file_sym_query = """
        MATCH (f:File {repo_id: $repo_id, branch: $branch})
        WHERE f.file_path = $qname 
           OR toLower(f.file_path) ENDS WITH toLower('/' + $qname)
           OR toLower(f.file_path) CONTAINS toLower($qname)
        MATCH (f)-[:DEFINES]->(s:Symbol)
        OPTIONAL MATCH (caller:Symbol)-[:CALLS]->(s)
        OPTIONAL MATCH (s)-[:CALLS]->(callee:Symbol)
        RETURN f.file_path AS file_path,
               s.name AS symbol,
               s.kind AS kind,
               s.signature AS signature,
               collect(DISTINCT caller.name) AS callers,
               collect(DISTINCT callee.name) AS callees
        """
        recs = await client.execute_query(file_sym_query, {"repo_id": repo_id, "branch": branch, "qname": qname_clean})
        if recs:
            all_callers = []
            all_callees = []
            defined_symbols = []
            for r in recs:
                defined_symbols.append({"name": r["symbol"], "kind": r["kind"], "signature": r.get("signature")})
                all_callers.extend([c for c in r.get("callers", []) if c])
                all_callees.extend([c for c in r.get("callees", []) if c])

            return json.dumps({
                "query_target": qname_clean,
                "target_type": "file",
                "matched_file": recs[0]["file_path"],
                "defined_symbols": defined_symbols,
                "callers": list(set(all_callers)),
                "callees": list(set(all_callees))
            }, indent=2)

        return json.dumps({"error": f"Symbol or File matching '{qualified_name}' not found in repo '{repo_id}'"})

    name = sym.get("name", "")
    dependents = await get_dependents(client, repo_id, branch, callee_name=name)
    dependencies = await get_dependencies(client, repo_id, branch, caller_qualified_name=sym.get("qualified_name", qualified_name))

    return json.dumps({
        "symbol": sym,
        "callers": dependents,
        "callees": dependencies
    }, indent=2)


async def tool_get_blast_radius(client: Neo4jClient, repo_id: str, changed_symbols: List[str], branch: str = "main") -> str:
    """Compute downstream ripple effect risk score and affected symbols for a list of changed symbol or file names."""
    res = await compute_blast_radius(client, repo_id, branch, changed_symbols)
    return json.dumps({
        "risk_score": res.risk_score,
        "total_affected": res.total_affected,
        "changed_symbols": res.changed_symbols,
        "affected_symbols": [
            {"qualified_name": a.qualified_name, "file_path": a.file_path, "depth": a.depth, "fan_in": a.fan_in}
            for a in res.affected_symbols
        ]
    }, indent=2)


async def tool_get_file_dependencies(client: Neo4jClient, repo_id: str, file_path: str, branch: str = "main") -> str:
    """Get internal and external dependencies for a file, plus other files that depend on it."""
    fp_clean = file_path.strip()
    query = """
    MATCH (f:File {repo_id: $repo_id, branch: $branch})
    WHERE f.file_path = $fp 
       OR toLower(f.file_path) ENDS WITH toLower('/' + $fp)
       OR toLower(f.file_path) CONTAINS toLower($fp)
    
    OPTIONAL MATCH (other:File {repo_id: $repo_id, branch: $branch})-[:DEPENDS_ON_FILE]->(f)
    OPTIONAL MATCH (other2:File {repo_id: $repo_id, branch: $branch})-[:IMPORTS]->(:Symbol)<-[:DEFINES]-(f)
    
    OPTIONAL MATCH (f)-[:DEPENDS_ON_FILE]->(target:File {repo_id: $repo_id, branch: $branch})
    OPTIONAL MATCH (f)-[:IMPORTS]->(:Symbol)<-[:DEFINES]-(target2:File {repo_id: $repo_id, branch: $branch})
    
    OPTIONAL MATCH (f)-[:DEPENDS_ON]->(pkg:Package {repo_id: $repo_id, branch: $branch})
    
    RETURN f.file_path AS file_path,
           collect(DISTINCT coalesce(other.file_path, other2.file_path)) AS imported_by_files,
           collect(DISTINCT coalesce(target.file_path, target2.file_path)) AS imports_files,
           collect(DISTINCT pkg.name) AS external_packages
    LIMIT 5
    """
    records = await client.execute_query(query, {"repo_id": repo_id, "branch": branch, "fp": fp_clean})
    if not records:
        return json.dumps({
            "file_path": file_path,
            "error": f"File matching '{file_path}' not found in repo '{repo_id}'",
            "imported_by_files": [],
            "imports_files": [],
            "external_packages": []
        }, indent=2)

    rec = records[0]
    return json.dumps({
        "file_path": rec.get("file_path", file_path),
        "imported_by_files": [x for x in rec.get("imported_by_files", []) if x],
        "imports_files": [x for x in rec.get("imports_files", []) if x],
        "external_packages": [x for x in rec.get("external_packages", []) if x]
    }, indent=2)


async def tool_search_symbols(client: Neo4jClient, repo_id: str, query_str: str, branch: str = "main") -> str:
    """Fuzzy search symbol names matching query string."""
    q_clean = query_str.strip()
    query = """
    MATCH (s:Symbol {repo_id: $repo_id, branch: $branch})
    WHERE toLower(s.name) CONTAINS toLower($query_str) 
       OR toLower(s.qualified_name) CONTAINS toLower($query_str)
       OR toLower(s.file_path) CONTAINS toLower($query_str)
    RETURN properties(s) AS symbol
    LIMIT 20
    """
    records = await client.execute_query(query, {"repo_id": repo_id, "branch": branch, "query_str": q_clean})
    return json.dumps([r["symbol"] for r in records if "symbol" in r], indent=2)



def tool_vector_search(
    vector_client: Any,
    query_text: str,
    repo_id: Optional[str] = None,
    content_type: Optional[str] = None,
    n_results: int = 5,
) -> str:
    """Semantic similarity search across code, PRs, commits, and issues in Vector KB."""
    where_clause = {}
    if repo_id:
        where_clause["repo"] = repo_id
    if content_type:
        ct_lower = content_type.lower()
        if "code" in ct_lower:
            where_clause["content_type"] = "code"
        elif "pr" in ct_lower or "pull" in ct_lower:
            where_clause["content_type"] = "pr"
        elif "commit" in ct_lower:
            where_clause["content_type"] = "commit"
        elif "issue" in ct_lower:
            where_clause["content_type"] = "issue"

    res = vector_client.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where_clause if where_clause else None,
    )

    hits = []
    if res and res.get("documents") and len(res["documents"]) > 0 and res["documents"][0]:
        docs = res["documents"][0]
        metas = res["metadatas"][0] if res.get("metadatas") else [{}] * len(docs)
        for doc, meta in zip(docs, metas):
            hits.append({"metadata": meta, "text": doc})

    return json.dumps({"query": query_text, "results": hits}, indent=2)


async def tool_hybrid_search(
    graph_client: Neo4jClient,
    vector_client: Any,
    repo_id: str,
    query_text: str,
    branch: str = "main",
    n_results: int = 5,
) -> str:
    """Perform hybrid search combining vector semantic search and graph structural search."""
    from ai_service.kb_unified import UnifiedKB
    unified = UnifiedKB(neo4j_client=graph_client, vector_client=vector_client)
    res = await unified.hybrid_search(
        repo_id=repo_id,
        query_text=query_text,
        branch=branch,
        n_results=n_results,
    )
    return json.dumps(res, indent=2)


async def tool_get_file_content(repo_id: str, file_path: str) -> str:
    """Read actual raw source code, documentation, or configuration file contents from repository disk."""
    from pathlib import Path

    clean_path = file_path.strip().lstrip("/").lstrip("\\")
    repo_slug = repo_id.replace("/", "_")

    candidates = [
        Path("./chroma_db/repos") / repo_slug / clean_path,
        Path("./chroma_db/repos") / repo_id / clean_path,
        Path(".") / clean_path,
    ]

    target_file = None
    for cand in candidates:
        if cand.exists() and cand.is_file():
            target_file = cand
            break

    if not target_file:
        repo_dir = Path("./chroma_db/repos") / repo_slug
        if repo_dir.exists():
            for p in repo_dir.rglob(Path(clean_path).name):
                if p.is_file():
                    target_file = p
                    break

    if not target_file or not target_file.exists():
        return json.dumps({
            "error": f"File '{file_path}' not found on disk for repo '{repo_id}'",
            "file_path": file_path,
            "content": "",
        }, indent=2)

    try:
        text = target_file.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        return json.dumps({
            "file_path": file_path,
            "lines_count": len(lines),
            "content": text[:5000],
            "truncated": len(text) > 5000,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to read file '{file_path}': {str(e)}"})


async def execute_tool_by_name(
    tool_name: str,
    tool_args: Dict[str, Any],
    graph_client: Any,
    vector_client: Any,
    repo_id: str,
    branch: str = "main",
) -> str:
    """Dynamically execute an MCP tool by name with arguments."""
    try:
        if tool_name == "hybrid_search":
            query = tool_args.get("query") or tool_args.get("query_text") or tool_args.get("q") or ""
            return await tool_hybrid_search(
                graph_client, vector_client, repo_id=repo_id, query_text=query, branch=branch
            )
        elif tool_name == "vector_search":
            query = tool_args.get("query") or tool_args.get("query_text") or tool_args.get("q") or ""
            ctype = tool_args.get("content_type")
            return tool_vector_search(
                vector_client, query_text=query, repo_id=repo_id, content_type=ctype
            )
        elif tool_name == "get_symbol_details":
            qname = (
                tool_args.get("qualified_name")
                or tool_args.get("symbol_name")
                or tool_args.get("name")
                or tool_args.get("symbol")
                or ""
            )
            return await tool_get_symbol_details(
                graph_client, repo_id=repo_id, qualified_name=qname, branch=branch
            )
        elif tool_name == "get_file_dependencies":
            fpath = tool_args.get("file_path") or tool_args.get("file") or tool_args.get("path") or ""
            return await tool_get_file_dependencies(
                graph_client, repo_id=repo_id, file_path=fpath, branch=branch
            )
        elif tool_name == "get_file_content":
            fpath = tool_args.get("file_path") or tool_args.get("file") or tool_args.get("path") or "README.md"
            return await tool_get_file_content(repo_id=repo_id, file_path=fpath)
        elif tool_name == "get_blast_radius":
            syms = (
                tool_args.get("changed_symbols")
                or tool_args.get("symbols")
                or tool_args.get("changed_symbol")
                or tool_args.get("symbol")
                or []
            )
            if isinstance(syms, str):
                syms = [syms]
            return await tool_get_blast_radius(
                graph_client, repo_id=repo_id, changed_symbols=syms, branch=branch
            )
        elif tool_name == "get_repo_structure":
            return await tool_get_repo_structure(graph_client, repo_id=repo_id, branch=branch)
        elif tool_name == "search_symbols":
            query = (
                tool_args.get("query")
                or tool_args.get("query_str")
                or tool_args.get("q")
                or tool_args.get("symbol")
                or ""
            )
            return await tool_search_symbols(
                graph_client, repo_id=repo_id, query_str=query, branch=branch
            )
        else:
            # Fallback to hybrid search if tool name is unknown
            query = tool_args.get("query", str(tool_args))
            return await tool_hybrid_search(
                graph_client, vector_client, repo_id=repo_id, query_text=query, branch=branch
            )
    except Exception as e:
        return json.dumps({"error": f"Failed to execute tool '{tool_name}': {str(e)}"})


