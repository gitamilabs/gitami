from pathlib import Path
from typing import List, Dict, Optional, Set
from src.graph.client import Neo4jClient


def resolve_relative_path(importer_file: str, module_path: str, known_files: Set[str]) -> Optional[str]:
    """Resolve a relative import path (e.g. ./api.js, ../utils) against known file paths in the repo."""
    importer_dir = Path(importer_file).parent
    
    # Clean leading ./ or ../ for Path join
    raw_target = (importer_dir / module_path).as_posix()
    
    # Normalize path strings (strip double slashes, handle relative dot components)
    try:
        norm_target = Path(raw_target).as_posix()
    except Exception:
        norm_target = raw_target

    candidates = [
        norm_target,
        f"{norm_target}.js",
        f"{norm_target}.jsx",
        f"{norm_target}.ts",
        f"{norm_target}.tsx",
        f"{norm_target}/index.js",
        f"{norm_target}/index.jsx",
        f"{norm_target}/index.ts",
        f"{norm_target}/index.tsx",
    ]

    for cand in candidates:
        if cand in known_files:
            return cand
    return None


def resolve_python_path(importer_file: str, module_path: str, known_files: Set[str]) -> Optional[str]:
    """Resolve a Python import (e.g. user_model, utils.helpers) against known files in the repo."""
    importer_dir = Path(importer_file).parent
    as_path = module_path.replace(".", "/")

    candidates = [
        f"{as_path}.py",
        f"{as_path}/__init__.py",
        (importer_dir / f"{as_path}.py").as_posix(),
        (importer_dir / f"{as_path}/__init__.py").as_posix(),
    ]

    for cand in candidates:
        if cand in known_files:
            return cand
    return None


async def resolve_repo_imports(client: Neo4jClient, repo_id: str, branch: str) -> Dict[str, int]:
    """Post-processing pass to link File nodes to target internal Symbols and Files, cleaning up local Package stubs."""
    # 1. Fetch all known File paths for this repo_id + branch
    files_query = """
    MATCH (f:File {repo_id: $repo_id, branch: $branch})
    RETURN f.file_path AS file_path
    """
    file_records = await client.execute_query(files_query, {"repo_id": repo_id, "branch": branch})
    known_files = {r["file_path"] for r in file_records if r.get("file_path")}

    if not known_files:
        return {"resolved_internal": 0, "file_dependencies": 0}

    # 2. Fetch all DEPENDS_ON relationships to Package nodes or raw module imports
    imports_query = """
    MATCH (f:File {repo_id: $repo_id, branch: $branch})-[r:DEPENDS_ON]->(p:Package {repo_id: $repo_id, branch: $branch})
    RETURN f.file_path AS importer_file, p.name AS module_path, r.imported_symbol AS imported_symbol
    """
    import_records = await client.execute_query(imports_query, {"repo_id": repo_id, "branch": branch})

    resolved_internal_count = 0
    file_dep_count = 0

    for rec in import_records:
        importer_file = rec["importer_file"]
        module_path = rec["module_path"]
        imported_symbol = rec.get("imported_symbol", "")

        target_file = None
        if module_path.startswith("."):
            target_file = resolve_relative_path(importer_file, module_path, known_files)
        else:
            target_file = resolve_python_path(importer_file, module_path, known_files)

        if target_file:
            # 3. Create DEPENDS_ON_FILE and IMPORTS relationships to actual Symbol
            link_query = """
            MATCH (f:File {repo_id: $repo_id, branch: $branch, file_path: $importer_file})
            MATCH (target:File {repo_id: $repo_id, branch: $branch, file_path: $target_file})
            MERGE (f)-[:DEPENDS_ON_FILE]->(target)
            WITH f, target
            OPTIONAL MATCH (s:Symbol {repo_id: $repo_id, branch: $branch, file_path: $target_file, name: $imported_symbol})
            FOREACH (_ IN CASE WHEN s IS NOT NULL THEN [1] ELSE [] END | MERGE (f)-[:IMPORTS {module_path: $module_path}]->(s))
            """
            await client.execute_query(
                link_query,
                {
                    "repo_id": repo_id,
                    "branch": branch,
                    "importer_file": importer_file,
                    "target_file": target_file,
                    "imported_symbol": imported_symbol,
                    "module_path": module_path,
                },
            )
            file_dep_count += 1
            resolved_internal_count += 1

            # 4. Remove the redundant external Package stub node for relative path
            if module_path.startswith("."):
                del_pkg_query = """
                MATCH (p:Package {repo_id: $repo_id, branch: $branch, name: $module_path})
                DETACH DELETE p
                """
                await client.execute_query(del_pkg_query, {"repo_id": repo_id, "branch": branch, "module_path": module_path})

    return {"resolved_internal": resolved_internal_count, "file_dependencies": file_dep_count}
