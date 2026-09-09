import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src.graph.client import Neo4jClient
from src.parsing.models import ParseResult, SymbolNode, CallEdge, ImportEdge, HeritageEdge

logger = logging.getLogger(__name__)

PARSER_VERSION = "1.0.0"
SCHEMA_VERSION = "v1"


def make_entity_uid(repo_id: str, kind: str, file_path: str, name: str, parent: Optional[str] = None) -> str:
    """
    Generate a deterministic, branch-independent UID for any code entity.
    
    Format:
        {kind}:{repo_id}:{file_path}::{parent.name if parent else name}
    """
    norm_path = file_path.replace("\\", "/").lstrip("/")
    if parent:
        return f"{kind}:{repo_id}:{norm_path}::{parent}.{name}"
    return f"{kind}:{repo_id}:{norm_path}::{name}"


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
            MERGE (r)-[:CONTAINS {provenance: 'DETERMINISTIC', confidence: 1.0, commit_sha: item.commit_sha}]->(f)
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

            for sym in pr.symbols:
                kind = sym.kind
                parent = sym.class_name

                if kind == "class":
                    label = "Class"
                    uid = make_entity_uid(repo_id, "class", norm_path, sym.name)
                elif kind == "method":
                    label = "Method"
                    uid = make_entity_uid(repo_id, "method", norm_path, sym.name, parent)
                elif kind == "interface":
                    label = "Interface"
                    uid = make_entity_uid(repo_id, "interface", norm_path, sym.name)
                elif kind == "type":
                    label = "Type"
                    uid = make_entity_uid(repo_id, "type", norm_path, sym.name)
                elif kind == "test":
                    label = "Test"
                    uid = make_entity_uid(repo_id, "test", norm_path, sym.name)
                else:
                    label = "Function"
                    uid = make_entity_uid(repo_id, "func", norm_path, sym.name)

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
