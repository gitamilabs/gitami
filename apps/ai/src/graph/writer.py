from typing import List, Optional
from src.graph.client import Neo4jClient
from src.parsing.models import SymbolNode, CallEdge, ImportEdge


async def upsert_file_and_symbols(client: Neo4jClient, repo_id: str, branch: str, file_path: str, language: str, symbols: List[SymbolNode]) -> int:
    """Create a File node and its Symbol nodes with DEFINES relationships."""
    # 1. Create or merge the File node
    file_query = """
    MERGE (f:File {repo_id: $repo_id, branch: $branch, file_path: $file_path})
    SET f.language = $language
    """
    await client.execute_query(file_query, {"repo_id": repo_id, "branch": branch, "file_path": file_path, "language": language})

    if not symbols:
        return 1

    # 2. Create Symbol nodes with DEFINES edges from File
    sym_query = """
    UNWIND $batch AS item
    MATCH (f:File {repo_id: $repo_id, branch: $branch, file_path: item.file_path})
    MERGE (s:Symbol {repo_id: $repo_id, branch: $branch, qualified_name: item.qualified_name})
    SET s.name = item.name,
        s.kind = item.kind,
        s.file_path = item.file_path,
        s.language = item.language,
        s.start_line = item.start_line,
        s.end_line = item.end_line,
        s.signature = item.signature,
        s.docstring = item.docstring
    MERGE (f)-[:DEFINES]->(s)
    """

    batch = [
        {
            "qualified_name": sym.qualified_name,
            "name": sym.name,
            "kind": sym.kind,
            "file_path": sym.file_path,
            "language": sym.language,
            "start_line": sym.start_line,
            "end_line": sym.end_line,
            "signature": sym.signature,
            "docstring": sym.docstring,
        }
        for sym in symbols
    ]

    await client.execute_query(sym_query, {"repo_id": repo_id, "branch": branch, "batch": batch})
    return len(symbols)


# Keep the old name as an alias for backward compatibility
async def upsert_symbols(client: Neo4jClient, repo_id: str, branch: str, symbols: List[SymbolNode]) -> int:
    """MERGE Symbol nodes into Neo4j scoped strictly to repo_id and branch."""
    if not symbols:
        return 0

    # Group symbols by file_path
    by_file: dict[str, list[SymbolNode]] = {}
    for sym in symbols:
        by_file.setdefault(sym.file_path, []).append(sym)

    total = 0
    for fp, file_syms in by_file.items():
        lang = file_syms[0].language if file_syms else "unknown"
        total += await upsert_file_and_symbols(client, repo_id, branch, fp, lang, file_syms)
    return total


async def upsert_call_edges(client: Neo4jClient, repo_id: str, branch: str, calls: List[CallEdge]) -> int:
    """Create CALLS relationships only between existing Symbol nodes within the same repo_id.
    Calls to unknown/external symbols are skipped (no orphan stub nodes)."""
    if not calls:
        return 0

    # Use MATCH (not MERGE) for callee — only connect to known symbols
    query = """
    UNWIND $batch AS item
    MATCH (caller:Symbol {repo_id: $repo_id, branch: $branch, qualified_name: item.caller_symbol})
    MATCH (callee:Symbol {repo_id: $repo_id, branch: $branch})
    WHERE callee.name = item.callee_name
    MERGE (caller)-[r:CALLS]->(callee)
    SET r.file_path = item.file_path, r.line = item.line
    """

    batch = [
        {
            "caller_symbol": c.caller_symbol,
            "callee_name": c.callee_name,
            "file_path": c.file_path,
            "line": c.line,
        }
        for c in calls
    ]

    await client.execute_query(query, {"repo_id": repo_id, "branch": branch, "batch": batch})
    return len(calls)


async def upsert_import_edges(client: Neo4jClient, repo_id: str, branch: str, imports: List[ImportEdge]) -> int:
    """Create IMPORTS relationships. Internal imports connect to existing Symbols.
    External imports create a Package node."""
    if not imports:
        return 0

    for imp in imports:
        # Try to match an internal symbol first
        internal_query = """
        MATCH (f:File {repo_id: $repo_id, branch: $branch, file_path: $importer_file})
        MATCH (s:Symbol {repo_id: $repo_id, branch: $branch, name: $imported_symbol})
        MERGE (f)-[r:IMPORTS]->(s)
        SET r.module_path = $module_path, r.line = $line
        """
        result = await client.execute_query(internal_query, {
            "repo_id": repo_id,
            "branch": branch,
            "importer_file": imp.importer_file,
            "imported_symbol": imp.imported_symbol,
            "module_path": imp.module_path,
            "line": imp.line,
        })

        # If no internal match found, create a Package dependency node
        ext_query = """
        MATCH (f:File {repo_id: $repo_id, branch: $branch, file_path: $importer_file})
        MERGE (pkg:Package {name: $module_path, repo_id: $repo_id, branch: $branch})
        MERGE (f)-[r:DEPENDS_ON]->(pkg)
        SET r.imported_symbol = $imported_symbol, r.line = $line
        """
        await client.execute_query(ext_query, {
            "repo_id": repo_id,
            "branch": branch,
            "importer_file": imp.importer_file,
            "module_path": imp.module_path,
            "imported_symbol": imp.imported_symbol,
            "line": imp.line,
        })

    return len(imports)


async def delete_file_data(client: Neo4jClient, repo_id: str, branch: str, file_path: str) -> None:
    """Delete a file node and all its symbols and edges within a repo_id."""
    query = """
    MATCH (f:File {repo_id: $repo_id, branch: $branch, file_path: $file_path})
    OPTIONAL MATCH (f)-[:DEFINES]->(s:Symbol)
    DETACH DELETE f, s
    """
    await client.execute_query(query, {"repo_id": repo_id, "branch": branch, "file_path": file_path})


async def delete_repo_data(client: Neo4jClient, repo_id: str, branch: Optional[str] = None) -> None:
    """Delete all nodes and edges belonging to a specific repo_id (and optional branch)."""
    if branch:
        query = "MATCH (n {repo_id: $repo_id, branch: $branch}) DETACH DELETE n"
        params = {"repo_id": repo_id, "branch": branch}
    else:
        query = "MATCH (n {repo_id: $repo_id}) DETACH DELETE n"
        params = {"repo_id": repo_id}

    await client.execute_query(query, params)
