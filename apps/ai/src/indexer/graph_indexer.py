import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src.graph.client import Neo4jClient
from src.graph.resolver import resolve_repo_imports
from src.parsing.models import ParseResult, SymbolNode, CallEdge, ImportEdge, HeritageEdge

logger = logging.getLogger(__name__)


PARSER_VERSION = "1.0.0"
SCHEMA_VERSION = "v1"


def make_entity_uid(
    repo_id: str,
    kind: str,
    file_path: str,
    name: str,
    parent: Optional[str] = None,
    occurrence: Optional[int] = None,
) -> str:
    """
    Generate a deterministic, branch-independent, commit-independent UID for any code entity.
    
    Format:
        {kind}:{repo_id}:{norm_path}::{scoped_name}[#{occurrence}]
    """
    norm_kind = "func" if kind.lower() == "function" else kind.lower()
    norm_path = file_path.replace("\\", "/").lstrip("/")
    scoped_name = f"{parent}.{name}" if parent else name
    base = f"{norm_kind}:{repo_id}:{norm_path}::{scoped_name}"
    if occurrence is not None and occurrence >= 0:
        return f"{base}#{occurrence}"
    return base


def compute_symbol_uids(
    repo_id: str,
    norm_path: str,
    symbols: List[SymbolNode],
) -> List[Tuple[SymbolNode, str, str]]:
    """
    Compute deterministic UIDs for all symbols in a file, disambiguating
    duplicate declarations in the same lexical scope with deterministic #0, #1 suffixes.
    
    Returns:
        List of (SymbolNode, label, uid)
    """
    scope_keys = [(sym.kind, sym.class_name, sym.name) for sym in symbols]
    key_counts = Counter(scope_keys)
    key_seen: Dict[Tuple[str, Optional[str], str], int] = {}

    results = []
    for sym in symbols:
        kind = sym.kind
        parent = sym.class_name
        scope_key = (kind, parent, sym.name)

        occurrence = None
        if key_counts[scope_key] > 1:
            occurrence = key_seen.get(scope_key, 0)
            key_seen[scope_key] = occurrence + 1

        if kind == "class":
            label = "Class"
            uid = make_entity_uid(repo_id, "class", norm_path, sym.name, parent=parent, occurrence=occurrence)
        elif kind == "method":
            label = "Method"
            uid = make_entity_uid(repo_id, "method", norm_path, sym.name, parent=parent, occurrence=occurrence)
        elif kind == "interface":
            label = "Interface"
            uid = make_entity_uid(repo_id, "interface", norm_path, sym.name, parent=parent, occurrence=occurrence)
        elif kind == "type":
            label = "Type"
            uid = make_entity_uid(repo_id, "type", norm_path, sym.name, parent=parent, occurrence=occurrence)
        elif kind == "test":
            label = "Test"
            uid = make_entity_uid(repo_id, "test", norm_path, sym.name, parent=parent, occurrence=occurrence)
        else:
            label = "Function"
            uid = make_entity_uid(repo_id, "func", norm_path, sym.name, parent=parent, occurrence=occurrence)

        results.append((sym, label, uid))
    return results


class GraphIndexer:
    """
    Indexes repository AST structures into Neo4j following the V1 Graph Ontology.
    
    Guarantees:
    1. Deterministic entity identity independent of Git branch.
    2. Full idempotency on repeat runs via Neo4j uniqueness constraints and MERGE.
    3. Deterministic provenance (source, confidence: 1.0, parser_version, commit_sha).
    """

    def __init__(self, client: Neo4jClient):
        self.client = client

    async def ensure_v1_schema(self) -> None:
        """Create canonical uniqueness constraints and indexes for V1 Graph Ontology."""
        constraints = [
            "CREATE CONSTRAINT repo_uid_unique IF NOT EXISTS FOR (r:Repository) REQUIRE r.uid IS UNIQUE",
            "CREATE CONSTRAINT dir_uid_unique IF NOT EXISTS FOR (d:Directory) REQUIRE d.uid IS UNIQUE",
            "CREATE CONSTRAINT file_uid_unique IF NOT EXISTS FOR (f:File) REQUIRE f.uid IS UNIQUE",
            "CREATE CONSTRAINT class_uid_unique IF NOT EXISTS FOR (c:Class) REQUIRE c.uid IS UNIQUE",
            "CREATE CONSTRAINT func_uid_unique IF NOT EXISTS FOR (fn:Function) REQUIRE fn.uid IS UNIQUE",
            "CREATE CONSTRAINT method_uid_unique IF NOT EXISTS FOR (m:Method) REQUIRE m.uid IS UNIQUE",
            "CREATE CONSTRAINT interface_uid_unique IF NOT EXISTS FOR (i:Interface) REQUIRE i.uid IS UNIQUE",
            "CREATE CONSTRAINT type_uid_unique IF NOT EXISTS FOR (t:Type) REQUIRE t.uid IS UNIQUE",
            "CREATE CONSTRAINT test_uid_unique IF NOT EXISTS FOR (t:Test) REQUIRE t.uid IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX file_repo_idx IF NOT EXISTS FOR (f:File) ON (f.repo_id, f.commit_sha)",
            "CREATE INDEX func_repo_idx IF NOT EXISTS FOR (fn:Function) ON (fn.repo_id, fn.name)",
        ]

        for query in constraints + indexes:
            try:
                await self.client.execute_query(query)
            except Exception as e:
                logger.warning(f"Notice executing schema constraint/index '{query[:40]}...': {e}")

    async def index_repository_node(
        self, project_id: str, repo_id: str, commit_sha: str, branch: str = "main"
    ) -> str:
        """Upsert the top-level :Repository node."""
        repo_uid = f"repo:{repo_id}"
        query = """
        MERGE (r:Repository {uid: $uid})
        SET r.repo_id = $repo_id,
            r.project_id = $project_id,
            r.latest_commit_sha = $commit_sha,
            r.default_branch = $branch,
            r.indexed_at = $indexed_at,
            r.schema_version = $schema_version
        RETURN r.uid AS uid
        """
        params = {
            "uid": repo_uid,
            "repo_id": repo_id,
            "project_id": project_id,
            "commit_sha": commit_sha,
            "branch": branch,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": SCHEMA_VERSION,
        }
        await self.client.execute_query(query, params)
        return repo_uid

    async def index_directories_and_files(
        self, repo_id: str, commit_sha: str, branch: str, parse_results: List[ParseResult]
    ) -> Tuple[int, int]:
        """Upsert :Directory and :File nodes and connect :Repository CONTAINS :File."""
        repo_uid = f"repo:{repo_id}"
        dirs_created: Set[str] = set()
        file_count = 0

        # Discover unique directories
        dir_batches = []
        file_batches = []
        now_str = datetime.now(timezone.utc).isoformat()

        for pr in parse_results:
            norm_path = pr.file_path.replace("\\", "/").lstrip("/")
            file_uid = f"file:{repo_id}:{norm_path}"
            parent_dir = str(Path(norm_path).parent).replace("\\", "/")
            if parent_dir == ".":
                parent_dir = ""

            file_batches.append({
                "uid": file_uid,
                "file_path": norm_path,
                "language": pr.language,
                "repo_id": repo_id,
                "commit_sha": commit_sha,
                "branch": branch,
                "parent_dir": parent_dir,
                "indexed_at": now_str,
            })

            if parent_dir and parent_dir not in dirs_created:
                dirs_created.add(parent_dir)
                dir_batches.append({
                    "uid": f"dir:{repo_id}:{parent_dir}",
                    "path": parent_dir,
                    "repo_id": repo_id,
                    "commit_sha": commit_sha,
                })

        # Upsert Directory nodes and Repository -> Directory CONTAINS
        if dir_batches:
            dir_query = """
            UNWIND $batch AS item
            MATCH (r:Repository {uid: $repo_uid})
            MERGE (d:Directory {uid: item.uid})
            SET d.path = item.path,
                d.repo_id = item.repo_id,
                d.commit_sha = item.commit_sha
            MERGE (r)-[:CONTAINS {provenance: 'DETERMINISTIC', confidence: 1.0}]->(d)
            """
            await self.client.execute_query(dir_query, {"repo_uid": repo_uid, "batch": dir_batches})

        # Upsert File nodes and Repository -> File CONTAINS
        if file_batches:
            file_query = """
            UNWIND $batch AS item
            MATCH (r:Repository {uid: $repo_uid})
            MERGE (f:File {uid: item.uid})
            SET f.file_path = item.file_path,
                f.language = item.language,
                f.repo_id = item.repo_id,
                f.commit_sha = item.commit_sha,
                f.branch = item.branch,
                f.indexed_at = item.indexed_at,
                f.schema_version = $schema_version
            MERGE (r)-[rel:CONTAINS]->(f)
            SET rel.provenance = 'DETERMINISTIC',
                rel.confidence = 1.0,
                rel.commit_sha = item.commit_sha
            """
            await self.client.execute_query(
                file_query,
                {"repo_uid": repo_uid, "schema_version": SCHEMA_VERSION, "batch": file_batches},
            )
            file_count = len(file_batches)

        return len(dirs_created), file_count

    async def index_symbols_and_entities(
        self, repo_id: str, commit_sha: str, branch: str, parse_results: List[ParseResult]
    ) -> int:
        """
        Upsert Class, Function, Method, Interface, Type, and Test nodes with DEFINES & HAS_METHOD.
        Uses compute_symbol_uids for deterministic lexical scope and occurrence disambiguation.
        """
        now_str = datetime.now(timezone.utc).isoformat()
        total_symbols = 0

        # Group symbols by entity label for targeted Neo4j queries
        by_label: Dict[str, List[Dict[str, Any]]] = {
            "Class": [],
            "Function": [],
            "Method": [],
            "Interface": [],
            "Type": [],
            "Test": [],
        }

        for pr in parse_results:
            norm_path = pr.file_path.replace("\\", "/").lstrip("/")
            file_uid = f"file:{repo_id}:{norm_path}"
            computed = compute_symbol_uids(repo_id, norm_path, pr.symbols)

            for sym, label, uid in computed:
                by_label[label].append({
                    "uid": uid,
                    "file_uid": file_uid,
                    "name": sym.name,
                    "file_path": norm_path,
                    "language": sym.language,
                    "start_line": sym.start_line,
                    "end_line": sym.end_line,
                    "signature": sym.signature,
                    "docstring": sym.docstring,
                    "qualified_name": sym.qualified_name,
                    "class_name": sym.class_name,
                    "repo_id": repo_id,
                    "commit_sha": commit_sha,
                    "branch": branch,
                    "indexed_at": now_str,
                })
                total_symbols += 1

        # Execute batched upserts for each label

        for label, batch in by_label.items():
            if not batch:
                continue

            query = f"""
            UNWIND $batch AS item
            MATCH (f:File {{uid: item.file_uid}})
            MERGE (e:{label} {{uid: item.uid}})
            SET e.name = item.name,
                e.file_path = item.file_path,
                e.language = item.language,
                e.start_line = item.start_line,
                e.end_line = item.end_line,
                e.signature = item.signature,
                e.docstring = item.docstring,
                e.qualified_name = item.qualified_name,
                e.class_name = item.class_name,
                e.repo_id = item.repo_id,
                e.commit_sha = item.commit_sha,
                e.branch = item.branch,
                e.parser_version = $parser_version,
                e.schema_version = $schema_version,
                e.indexed_at = item.indexed_at
            MERGE (f)-[r:DEFINES]->(e)
            SET r.provenance = 'DETERMINISTIC',
                r.confidence = 1.0,
                r.commit_sha = item.commit_sha
            """
            await self.client.execute_query(
                query,
                {
                    "parser_version": PARSER_VERSION,
                    "schema_version": SCHEMA_VERSION,
                    "batch": batch,
                },
            )

        # Wire Class HAS_METHOD Method relationships
        method_batch = [item for item in by_label["Method"] if item.get("class_name")]
        if method_batch:
            has_method_query = """
            UNWIND $batch AS item
            WITH item WHERE item.class_name IS NOT NULL
            MATCH (c:Class {repo_id: item.repo_id, file_path: item.file_path, name: item.class_name})
            MATCH (m:Method {uid: item.uid})
            MERGE (c)-[r:HAS_METHOD]->(m)
            SET r.provenance = 'DETERMINISTIC',
                r.confidence = 1.0,
                r.commit_sha = item.commit_sha
            """
            await self.client.execute_query(has_method_query, {"batch": method_batch})

        return total_symbols

    async def index_heritage(
        self, repo_id: str, commit_sha: str, parse_results: List[ParseResult]
    ) -> int:
        """Upsert EXTENDS and IMPLEMENTS relationships from AST heritage."""
        heritage_edges = []
        for pr in parse_results:
            norm_path = pr.file_path.replace("\\", "/").lstrip("/")
            for h in pr.heritage:
                subclass_uid = make_entity_uid(repo_id, "class", norm_path, h.subclass_name)
                heritage_edges.append({
                    "subclass_uid": subclass_uid,
                    "subclass_name": h.subclass_name,
                    "target_name": h.target_name,
                    "kind": h.kind,
                    "file_path": norm_path,
                    "line": h.line,
                    "repo_id": repo_id,
                    "commit_sha": commit_sha,
                })

        if not heritage_edges:
            return 0

        extends_batch = [h for h in heritage_edges if h["kind"] == "extends"]
        implements_batch = [h for h in heritage_edges if h["kind"] == "implements"]

        if extends_batch:
            extends_query = """
            UNWIND $batch AS item
            MATCH (sub:Class {uid: item.subclass_uid})
            MATCH (parent:Class {repo_id: item.repo_id, name: item.target_name})
            MERGE (sub)-[r:EXTENDS]->(parent)
            SET r.provenance = 'DETERMINISTIC',
                r.confidence = 1.0,
                r.file_path = item.file_path,
                r.line = item.line,
                r.commit_sha = item.commit_sha
            """
            await self.client.execute_query(extends_query, {"batch": extends_batch})

        if implements_batch:
            implements_query = """
            UNWIND $batch AS item
            MATCH (sub:Class {uid: item.subclass_uid})
            MATCH (iface:Interface {repo_id: item.repo_id, name: item.target_name})
            MERGE (sub)-[r:IMPLEMENTS]->(iface)
            SET r.provenance = 'DETERMINISTIC',
                r.confidence = 1.0,
                r.file_path = item.file_path,
                r.line = item.line,
                r.commit_sha = item.commit_sha
            """
            await self.client.execute_query(implements_query, {"batch": implements_batch})

        return len(heritage_edges)

    async def index_calls_and_imports(
        self, repo_id: str, commit_sha: str, parse_results: List[ParseResult]
    ) -> Tuple[int, int]:
        """Upsert CALLS, IMPORTS, and DEPENDS_ON relationships."""
        call_batch = []
        import_batch = []

        for pr in parse_results:
            norm_path = pr.file_path.replace("\\", "/").lstrip("/")
            file_uid = f"file:{repo_id}:{norm_path}"

            for c in pr.calls:
                call_batch.append({
                    "caller_symbol": c.caller_symbol,
                    "callee_name": c.callee_name,
                    "file_path": norm_path,
                    "line": c.line,
                    "repo_id": repo_id,
                    "commit_sha": commit_sha,
                })

            for imp in pr.imports:
                import_batch.append({
                    "file_uid": file_uid,
                    "importer_file": norm_path,
                    "imported_symbol": imp.imported_symbol,
                    "module_path": imp.module_path,
                    "line": imp.line,
                    "repo_id": repo_id,
                    "commit_sha": commit_sha,
                })

        calls_count = 0
        if call_batch:
            # Wire caller to matching Function/Method callee with provenance
            calls_query = """
            UNWIND $batch AS item
            MATCH (caller {repo_id: item.repo_id, qualified_name: item.caller_symbol})
            MATCH (callee {repo_id: item.repo_id, name: item.callee_name})
            WHERE callee:Function OR callee:Method
            MERGE (caller)-[r:CALLS]->(callee)
            SET r.provenance = 'DETERMINISTIC',
                r.confidence = 0.95,
                r.file_path = item.file_path,
                r.line = item.line,
                r.commit_sha = item.commit_sha
            """
            await self.client.execute_query(calls_query, {"batch": call_batch})
            calls_count = len(call_batch)

        imports_count = 0
        if import_batch:
            imports_query = """
            UNWIND $batch AS item
            MATCH (f:File {uid: item.file_uid})
            OPTIONAL MATCH (s {repo_id: item.repo_id, name: item.imported_symbol})
            WHERE s:Function OR s:Class OR s:Interface OR s:Type
            FOREACH (_ IN CASE WHEN s IS NOT NULL THEN [1] ELSE [] END |
                MERGE (f)-[r:IMPORTS]->(s)
                SET r.provenance = 'DETERMINISTIC',
                    r.confidence = 1.0,
                    r.module_path = item.module_path,
                    r.line = item.line,
                    r.commit_sha = item.commit_sha
            )
            """
            await self.client.execute_query(imports_query, {"batch": import_batch})
            imports_count = len(import_batch)

        return calls_count, imports_count

    async def index_tests(
        self, repo_id: str, commit_sha: str, parse_results: List[ParseResult]
    ) -> int:
        """Upsert deterministic TESTS relationships connecting Test nodes to targets."""
        test_edges = []
        for pr in parse_results:
            norm_path = pr.file_path.replace("\\", "/").lstrip("/")
            computed = compute_symbol_uids(repo_id, norm_path, pr.symbols)
            for sym, label, test_uid in computed:
                if sym.kind == "test" or label == "Test":
                    # Test calls target
                    for call in pr.calls:
                        if call.caller_symbol == sym.qualified_name:
                            test_edges.append({
                                "repo_id": repo_id,
                                "test_uid": test_uid,
                                "target_name": call.callee_name,
                                "commit_sha": commit_sha,
                            })
                    # Test name convention test_<func> or <func>Test
                    clean_target = sym.name
                    if clean_target.startswith("test_"):
                        clean_target = clean_target[5:]
                    elif clean_target.endswith("Test"):
                        clean_target = clean_target[:-4]
                    if clean_target and clean_target != sym.name:
                        test_edges.append({
                            "repo_id": repo_id,
                            "test_uid": test_uid,
                            "target_name": clean_target,
                            "commit_sha": commit_sha,
                        })

        if not test_edges:
            return 0

        query = """
        UNWIND $batch AS item
        MATCH (t:Test {repo_id: item.repo_id, uid: item.test_uid})
        MATCH (target {repo_id: item.repo_id, name: item.target_name})
        WHERE target:Function OR target:Method OR target:Class
        MERGE (t)-[r:TESTS]->(target)
        SET r.provenance = 'DETERMINISTIC',
            r.confidence = 1.0,
            r.commit_sha = item.commit_sha
        """
        await self.client.execute_query(query, {"batch": test_edges})
        return len(test_edges)

    async def delete_file_and_symbols(self, repo_id: str, file_path: str) -> None:
        """
        Delete a file node and all symbols canonically owned by it via :DEFINES.
        Safely detaches all incoming/outgoing relationships without affecting external packages
        or symbols owned by other files.
        """
        norm_path = file_path.replace("\\", "/").lstrip("/")
        query = """
        MATCH (f:File {repo_id: $repo_id, file_path: $file_path})
        OPTIONAL MATCH (f)-[:DEFINES]->(s)
        DETACH DELETE f, s
        """
        await self.client.execute_query(query, {"repo_id": repo_id, "file_path": norm_path})

    async def reconcile_file_symbols(
        self,
        repo_id: str,
        file_path: str,
        new_symbols: List[SymbolNode],
        commit_sha: str,
        branch: str,
    ) -> Tuple[int, int, int]:
        """
        Reconcile symbols for a modified file:
        S_old = symbols currently owned by file in graph
        S_new = symbols extracted from new AST
        
        Deletes S_old - S_new (stale symbols)
        Updates S_old ∩ S_new (retained symbols)
        Creates S_new - S_old (added symbols)
        
        Returns:
            (created_count, updated_count, deleted_count)
        """
        norm_path = file_path.replace("\\", "/").lstrip("/")
        file_uid = f"file:{repo_id}:{norm_path}"
        now_str = datetime.now(timezone.utc).isoformat()

        # 1. Fetch current symbols canonically owned by this file
        fetch_query = """
        MATCH (f:File {uid: $file_uid})-[:DEFINES]->(s)
        RETURN s.uid AS uid
        """
        records = await self.client.execute_query(fetch_query, {"file_uid": file_uid})
        old_uids: Set[str] = {r["uid"] for r in records if r.get("uid")}

        # 2. Compute new symbol UIDs using occurrence disambiguation
        computed = compute_symbol_uids(repo_id, norm_path, new_symbols)
        new_uids = {uid for _, _, uid in computed}

        to_delete = old_uids - new_uids
        to_create = new_uids - old_uids
        to_update = new_uids & old_uids

        # 3. Update File node commit_sha
        update_file_query = """
        MATCH (f:File {uid: $file_uid})
        SET f.commit_sha = $commit_sha,
            f.branch = $branch,
            f.indexed_at = $indexed_at
        """
        await self.client.execute_query(
            update_file_query,
            {"file_uid": file_uid, "commit_sha": commit_sha, "branch": branch, "indexed_at": now_str}
        )

        # 4. Delete stale symbols canonically owned by this file
        if to_delete:
            delete_query = """
            UNWIND $stale_uids AS stale_uid
            MATCH (s {uid: stale_uid})
            DETACH DELETE s
            """
            await self.client.execute_query(delete_query, {"stale_uids": list(to_delete)})

        # 5. Group new & updated symbols by label
        by_label: Dict[str, List[Dict[str, Any]]] = {
            "Class": [], "Function": [], "Method": [], "Interface": [], "Type": [], "Test": []
        }
        for sym, label, uid in computed:
            by_label[label].append({
                "uid": uid,
                "file_uid": file_uid,
                "name": sym.name,
                "file_path": norm_path,
                "language": sym.language,
                "start_line": sym.start_line,
                "end_line": sym.end_line,
                "signature": sym.signature,
                "docstring": sym.docstring,
                "qualified_name": sym.qualified_name,
                "class_name": sym.class_name,
                "repo_id": repo_id,
                "commit_sha": commit_sha,
                "branch": branch,
                "indexed_at": now_str,
            })

        # 6. Upsert active symbols
        for label, batch in by_label.items():
            if not batch:
                continue
            query = f"""
            UNWIND $batch AS item
            MATCH (f:File {{uid: item.file_uid}})
            MERGE (e:{label} {{uid: item.uid}})
            SET e.name = item.name,
                e.file_path = item.file_path,
                e.language = item.language,
                e.start_line = item.start_line,
                e.end_line = item.end_line,
                e.signature = item.signature,
                e.docstring = item.docstring,
                e.qualified_name = item.qualified_name,
                e.class_name = item.class_name,
                e.repo_id = item.repo_id,
                e.commit_sha = item.commit_sha,
                e.branch = item.branch,
                e.parser_version = $parser_version,
                e.schema_version = $schema_version,
                e.indexed_at = item.indexed_at
            MERGE (f)-[r:DEFINES]->(e)
            SET r.provenance = 'DETERMINISTIC',
                r.confidence = 1.0,
                r.commit_sha = item.commit_sha
            """
            await self.client.execute_query(
                query,
                {"parser_version": PARSER_VERSION, "schema_version": SCHEMA_VERSION, "batch": batch}
            )

        # 7. Re-wire HAS_METHOD for methods in this file
        method_batch = [item for item in by_label["Method"] if item.get("class_name")]
        if method_batch:
            has_method_query = """
            UNWIND $batch AS item
            WITH item WHERE item.class_name IS NOT NULL
            MATCH (c:Class {repo_id: item.repo_id, file_path: item.file_path, name: item.class_name})
            MATCH (m:Method {uid: item.uid})
            MERGE (c)-[r:HAS_METHOD]->(m)
            SET r.provenance = 'DETERMINISTIC',
                r.confidence = 1.0,
                r.commit_sha = item.commit_sha
            """
            await self.client.execute_query(has_method_query, {"batch": method_batch})

        return len(to_create), len(to_update), len(to_delete)

    async def purge_file_outgoing_relationships(self, repo_id: str, file_paths: List[str]) -> None:
        """
        Purge stale outgoing relationships (IMPORTS, CALLS, EXTENDS, IMPLEMENTS, TESTS, DEPENDS_ON_FILE)
        from specified files and their owned symbols before re-evaluating relationships.
        """
        if not file_paths:
            return
        norm_paths = [p.replace("\\", "/").lstrip("/") for p in file_paths]
        purge_query = """
        UNWIND $paths AS path
        MATCH (f:File {repo_id: $repo_id, file_path: path})
        OPTIONAL MATCH (f)-[r_imp:IMPORTS|DEPENDS_ON_FILE]->()
        DELETE r_imp
        WITH f
        OPTIONAL MATCH (f)-[:DEFINES]->(s)
        OPTIONAL MATCH (s)-[r_out:CALLS|EXTENDS|IMPLEMENTS|TESTS]->()
        DELETE r_out
        """
        await self.client.execute_query(purge_query, {"repo_id": repo_id, "paths": norm_paths})

    async def cleanup_empty_directories(self, repo_id: str) -> int:
        """Remove any directory nodes that have no child files under their path."""
        query = """
        MATCH (d:Directory {repo_id: $repo_id})
        WHERE NOT EXISTS {
            MATCH (f:File {repo_id: $repo_id})
            WHERE f.file_path STARTS WITH (d.path + "/")
        }
        DETACH DELETE d
        RETURN count(d) AS deleted_count
        """
        records = await self.client.execute_query(query, {"repo_id": repo_id})
        return records[0]["deleted_count"] if records else 0

    async def get_repository_state(self, repo_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the persisted state of a repository node from Neo4j."""
        query = """
        MATCH (r:Repository {repo_id: $repo_id})
        RETURN r.repo_id AS repo_id,
               r.latest_commit_sha AS latest_commit_sha,
               r.previous_commit_sha AS previous_commit_sha,
               r.generation AS generation,
               r.default_branch AS branch,
               r.schema_version AS schema_version,
               r.indexed_at AS indexed_at
        """
        records = await self.client.execute_query(query, {"repo_id": repo_id})
        if records:
            return dict(records[0])
        return None

    async def find_affected_files(self, repo_id: str, directly_changed_files: List[str]) -> Set[str]:
        """
        Identify files whose relationships could be affected by changes to directly_changed_files.
        Covers all five material relationship types: IMPORTS, CALLS, EXTENDS, IMPLEMENTS, TESTS,
        as well as file-level dependencies.
        """
        if not directly_changed_files:
            return set()

        norm_paths = [p.replace("\\", "/").lstrip("/") for p in directly_changed_files]
        query = """
        UNWIND $changed_paths AS path
        MATCH (f:File {repo_id: $repo_id, file_path: path})
        OPTIONAL MATCH (f)-[:DEFINES]->(s)

        // 1. Files importing this file or symbols in this file
        OPTIONAL MATCH (importer:File {repo_id: $repo_id})-[:IMPORTS]->(s)
        OPTIONAL MATCH (importer_f:File {repo_id: $repo_id})-[:IMPORTS]->(f)
        OPTIONAL MATCH (dep_f:File {repo_id: $repo_id})-[:DEPENDS_ON_FILE]->(f)

        // 2. Callers of symbols in this file
        OPTIONAL MATCH (caller)-[:CALLS]->(s)
        OPTIONAL MATCH (caller_f:File {repo_id: $repo_id})-[:DEFINES]->(caller)

        // 3. Subclasses of classes in this file
        OPTIONAL MATCH (sub:Class)-[:EXTENDS]->(s)
        OPTIONAL MATCH (sub_f:File {repo_id: $repo_id})-[:DEFINES]->(sub)

        // 4. Implementers of interfaces in this file
        OPTIONAL MATCH (impl:Class)-[:IMPLEMENTS]->(s)
        OPTIONAL MATCH (impl_f:File {repo_id: $repo_id})-[:DEFINES]->(impl)

        // 5. Tests targeting symbols in this file
        OPTIONAL MATCH (t:Test)-[:TESTS]->(s)
        OPTIONAL MATCH (test_f:File {repo_id: $repo_id})-[:DEFINES]->(t)

        WITH collect(DISTINCT importer.file_path) +
             collect(DISTINCT importer_f.file_path) +
             collect(DISTINCT dep_f.file_path) +
             collect(DISTINCT caller_f.file_path) +
             collect(DISTINCT sub_f.file_path) +
             collect(DISTINCT impl_f.file_path) +
             collect(DISTINCT test_f.file_path) AS affected_paths
        UNWIND affected_paths AS p
        WITH DISTINCT p
        WHERE p IS NOT NULL AND NOT p IN $changed_paths
        RETURN collect(p) AS affected_files
        """
        records = await self.client.execute_query(query, {"repo_id": repo_id, "changed_paths": norm_paths})
        if records and records[0].get("affected_files"):
            return set(records[0]["affected_files"])
        return set()

    async def rewire_affected_relationships(
        self,
        repo_id: str,
        commit_sha: str,
        branch: str,
        affected_files: List[str],
        parse_results: List[ParseResult],
    ) -> int:
        """
        Rewire outgoing relationships (IMPORTS, CALLS, EXTENDS, IMPLEMENTS, TESTS) for affected files
        without destroying or churning their canonical symbol nodes.
        """
        if not affected_files or not parse_results:
            return 0

        norm_paths = [p.replace("\\", "/").lstrip("/") for p in affected_files]
        affected_parse_results = [
            pr for pr in parse_results
            if pr.file_path.replace("\\", "/").lstrip("/") in norm_paths
        ]
        if not affected_parse_results:
            return 0

        # Purge stale outgoing relationships from affected files and their symbols
        await self.purge_file_outgoing_relationships(repo_id, norm_paths)

        # Re-wire heritage, calls, imports, and tests for affected files
        heritage_count = await self.index_heritage(repo_id, commit_sha, affected_parse_results)
        calls_count, imports_count = await self.index_calls_and_imports(repo_id, commit_sha, affected_parse_results)
        tests_count = await self.index_tests(repo_id, commit_sha, affected_parse_results)

        # Re-run import resolution
        try:
            await resolve_repo_imports(self.client, repo_id=repo_id, branch=branch)
        except Exception as e:
            logger.warning(f"Notice during affected import resolution: {e}")

        return heritage_count + calls_count + imports_count + tests_count

