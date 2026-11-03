import json
from typing import Any, Dict, List, Optional
from src.graph.client import Neo4jClient
from src.graph.reader import get_symbol, get_dependents, get_dependencies, get_all_symbols
from src.analysis.blast_radius import compute_blast_radius
from src.analysis.conventions import check_conventions
from src.parsing.parser import CodeParser


async def tool_get_repo_structure(client: Neo4jClient, repo_id: str, branch: str = "main") -> str:
    """Retrieve full file and symbol hierarchy for a repository."""
    query = """
    MATCH (f:File)
    WHERE (f.repo_id = $repo_id OR toLower(f.repo_id) = toLower($repo_id))
      AND ($branch IS NULL OR $branch = '' OR f.branch = $branch OR f.branch IS NULL)
    WITH f.file_path AS file_path, head(collect(f)) AS f
    OPTIONAL MATCH (f)-[:DEFINES]->(s:Symbol)
    WITH file_path, f, collect(CASE WHEN s IS NOT NULL AND s.name IS NOT NULL THEN {
        name: s.name,
        kind: coalesce(s.kind, split(coalesce(s.uid, ''), ':')[0], 'symbol'),
        qname: coalesce(s.qualified_name, s.name)
    } END) AS raw_symbols
    RETURN file_path, f.language AS language, [sym IN raw_symbols WHERE sym IS NOT NULL] AS symbols
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
        MATCH (f:File)
        WHERE (f.repo_id = $repo_id OR toLower(f.repo_id) = toLower($repo_id))
          AND ($branch IS NULL OR $branch = '' OR f.branch = $branch OR f.branch IS NULL)
          AND (f.file_path = $qname 
               OR toLower(f.file_path) ENDS WITH toLower('/' + $qname)
               OR toLower(f.file_path) CONTAINS toLower($qname))
        MATCH (f)-[:DEFINES]->(s:Symbol)
        OPTIONAL MATCH (caller:Symbol)-[:CALLS]->(s)
        OPTIONAL MATCH (s)-[:CALLS]->(callee:Symbol)
        RETURN f.file_path AS file_path,
               s.name AS symbol,
               coalesce(s.kind, split(coalesce(s.uid, ''), ':')[0], 'symbol') AS kind,
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
    MATCH (f:File)
    WHERE (f.repo_id = $repo_id OR toLower(f.repo_id) = toLower($repo_id))
      AND ($branch IS NULL OR $branch = '' OR f.branch = $branch OR f.branch IS NULL)
    AND (f.file_path = $fp 
           OR toLower(f.file_path) ENDS WITH toLower('/' + $fp)
           OR toLower(f.file_path) CONTAINS toLower($fp))
    
    OPTIONAL MATCH (other:File)-[:DEPENDS_ON_FILE]->(f)
    WHERE (other.repo_id = $repo_id OR toLower(other.repo_id) = toLower($repo_id))
    OPTIONAL MATCH (other2:File)-[:IMPORTS]->(:Symbol)<-[:DEFINES]-(f)
    WHERE (other2.repo_id = $repo_id OR toLower(other2.repo_id) = toLower($repo_id))
    
    OPTIONAL MATCH (f)-[:DEPENDS_ON_FILE]->(target:File)
    WHERE (target.repo_id = $repo_id OR toLower(target.repo_id) = toLower($repo_id))
    OPTIONAL MATCH (f)-[:IMPORTS]->(:Symbol)<-[:DEFINES]-(target2:File)
    WHERE (target2.repo_id = $repo_id OR toLower(target2.repo_id) = toLower($repo_id))
    
    OPTIONAL MATCH (f)-[:DEPENDS_ON]->(pkg:Package)
    WHERE (pkg.repo_id = $repo_id OR toLower(pkg.repo_id) = toLower($repo_id))
    
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
    MATCH (s:Symbol)
    WHERE (s.repo_id = $repo_id OR toLower(s.repo_id) = toLower($repo_id))
      AND ($branch IS NULL OR $branch = '' OR s.branch = $branch OR s.branch IS NULL)
      AND (toLower(s.name) CONTAINS toLower($query_str) 
           OR toLower(s.qualified_name) CONTAINS toLower($query_str)
           OR toLower(s.file_path) CONTAINS toLower($query_str))
    RETURN properties(s) AS symbol
    LIMIT 20
    """
    records = await client.execute_query(query, {"repo_id": repo_id, "branch": branch, "query_str": q_clean})
    return json.dumps([r["symbol"] for r in records if "symbol" in r], indent=2)



async def tool_vector_search(
    vector_client: Any,
    query_text: str,
    repo_id: Optional[str] = None,
    content_type: Optional[str] = None,
    n_results: int = 5,
    project_id: Optional[str] = None,
) -> str:
    """Semantic similarity search across code, PRs, commits, and issues in Vector KB (non-blocking)."""
    import asyncio

    where_clause = {}
    if repo_id:
        where_clause["repo"] = repo_id
    if project_id and project_id != "default":
        where_clause["project_id"] = project_id
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

    res = await asyncio.to_thread(
        vector_client.query,
        query_texts=[query_text],
        n_results=n_results,
        where=where_clause if where_clause else None,
        project_id=project_id,
    )

    hits = []
    if res and res.get("documents") and len(res["documents"]) > 0 and res["documents"][0]:
        docs = res["documents"][0]
        metas = res["metadatas"][0] if res.get("metadatas") else [{}] * len(docs)
        for doc, meta in zip(docs, metas):
            hits.append({"metadata": meta, "text": doc})

    # If scoped search with a specific content_type returned 0 results, retry without content_type restriction on the same repo
    if not hits and content_type and repo_id:
        scoped_where = {"repo": repo_id}
        if project_id and project_id != "default":
            scoped_where["project_id"] = project_id
        res_retry = await asyncio.to_thread(
            vector_client.query,
            query_texts=[query_text],
            n_results=n_results,
            where=scoped_where,
            project_id=project_id,
        )
        if res_retry and res_retry.get("documents") and len(res_retry["documents"]) > 0 and res_retry["documents"][0]:
            docs = res_retry["documents"][0]
            metas = res_retry.get("metadatas", [[]])[0] if res_retry.get("metadatas") else [{}] * len(docs)
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
    project_id: Optional[str] = None,
) -> str:
    """Perform hybrid search combining vector semantic search and graph structural search."""
    from src.kb_unified import UnifiedKB
    unified = UnifiedKB(neo4j_client=graph_client, vector_client=vector_client)
    res = await unified.hybrid_search(
        repo_id=repo_id,
        query_text=query_text,
        branch=branch,
        n_results=n_results,
        project_id=project_id,
    )
    return json.dumps(res, indent=2)


async def tool_get_file_content(repo_id: str, file_path: str, branch: str = "main") -> str:
    """Fetch raw source code, documentation, or configuration file contents from repository (GitHub remote or in-memory)."""
    import os
    import urllib.request
    from pathlib import Path
    from src.config import settings

    clean_path = file_path.strip().lstrip("/").lstrip("\\")
    token = getattr(settings, "github_token", None) or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    headers = {"User-Agent": "GitAmi-Agent"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Priority 1: GitHub Remote Fetch (Cloud-native / Diskless)
    if "/" in repo_id and not repo_id.startswith("local:"):
        candidate_branches = [b for b in [branch, "main", "master", "HEAD"] if b]
        # Deduplicate while preserving order
        candidate_branches = list(dict.fromkeys(candidate_branches))

        # Build path variations to guard against case mismatches (e.g. Readme.md vs README.md)
        p_obj = Path(clean_path)
        path_variations = [clean_path]
        if p_obj.name.lower() in ("readme.md", "package.json", "license", "dockerfile", "tsconfig.json"):
            for v in (p_obj.name.upper(), p_obj.name.lower(), p_obj.name.capitalize()):
                cand_rel = (p_obj.parent / v).as_posix() if p_obj.parent != Path(".") else v
                if cand_rel not in path_variations:
                    path_variations.append(cand_rel)

        for br in candidate_branches:
            for p_cand in path_variations:
                url = f"https://raw.githubusercontent.com/{repo_id}/{br}/{p_cand}"
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=8) as response:
                        if response.status == 200:
                            text = response.read().decode("utf-8", errors="ignore")
                            lines = text.splitlines()
                            return json.dumps({
                                "file_path": p_cand,
                                "lines_count": len(lines),
                                "content": text[:5000],
                                "truncated": len(text) > 5000,
                                "source": "github_remote",
                            }, indent=2)
                except Exception:
                    continue

    # Priority 2: Dedicated local repo directory ONLY if explicitly configured (local development)
    repos_dir = os.environ.get("REPOS_DIR")
    target_file = None
    if repos_dir:
        repo_name = repo_id.split("/")[-1]
        repo_slug = repo_id.replace("/", "_")
        cand_dirs = [Path(repos_dir) / repo_name, Path(repos_dir) / repo_slug]
        for cd in cand_dirs:
            p = cd / clean_path
            if p.exists() and p.is_file():
                target_file = p
                break

    if target_file and target_file.exists():
        try:
            text = target_file.read_text(encoding="utf-8", errors="ignore")
            lines = text.splitlines()
            return json.dumps({
                "file_path": file_path,
                "lines_count": len(lines),
                "content": text[:5000],
                "truncated": len(text) > 5000,
                "source": "local_repository",
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to read file '{file_path}': {str(e)}"})

    return json.dumps({
        "error": f"File '{file_path}' not found in repository '{repo_id}'",
        "file_path": file_path,
        "content": "",
    }, indent=2)


async def tool_retrieve_context(
    graph_client: Any,
    vector_client: Any,
    repo_id: str,
    query: str,
    branch: str = "main",
    max_items: int = 10,
    project_id: Optional[str] = None,
) -> str:
    """Retrieve governed multi-provider context (graph, vector, source, PRs) via ContextEngine."""
    from dataclasses import asdict
    from src.context import ContextEngine, ContextRequest, ContextAuthorizer, StaticAuthResolver
    effective_project = project_id or repo_id
    resolver = StaticAuthResolver({effective_project: {repo_id: None}})
    engine = ContextEngine(
        graph_client=graph_client,
        vector_client=vector_client,
        authorizer=ContextAuthorizer(resolver=resolver, graph_client=graph_client),
    )
    req = ContextRequest(
        project_id=effective_project,
        query=query,
        repository_ids=[repo_id],
        branch=branch,
        max_items=max_items,
    )
    res = await engine.retrieve(req)
    return json.dumps(asdict(res), indent=2)


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
        if tool_name in ("retrieve_context", "get_governed_context", "context_engine"):
            query = tool_args.get("query") or tool_args.get("q") or ""
            max_items = tool_args.get("max_items", 10)
            return await tool_retrieve_context(
                graph_client=graph_client,
                vector_client=vector_client,
                repo_id=repo_id,
                query=query,
                branch=branch,
                max_items=max_items,
            )
        elif tool_name == "hybrid_search":
            query = tool_args.get("query") or tool_args.get("query_text") or tool_args.get("q") or ""
            return await tool_hybrid_search(
                graph_client, vector_client, repo_id=repo_id, query_text=query, branch=branch
            )
        elif tool_name == "vector_search":
            query = tool_args.get("query") or tool_args.get("query_text") or tool_args.get("q") or ""
            ctype = tool_args.get("content_type")
            return await tool_vector_search(
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
            return await tool_get_file_content(repo_id=repo_id, file_path=fpath, branch=branch)
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


