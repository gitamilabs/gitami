import tempfile
import asyncio
from pathlib import Path
from git import Repo
import pytest

from src.graph.client import Neo4jClient
from src.indexer.contracts import IndexJobStatus, IndexStateStatus
from src.indexer.pipeline import RepositoryIndexer


async def clear_repo_graph(client: Neo4jClient, repo_id: str):
    """Purge all nodes and relationships for a test repo_id in Neo4j."""
    query = "MATCH (n {repo_id: $repo_id}) DETACH DELETE n"
    await client.execute_query(query, {"repo_id": repo_id})


async def export_normalized_graph(client: Neo4jClient, repo_id: str):
    """
    Extract all nodes and relationships for a repository, normalizing repo_id
    so two different repos can be compared for strict structural & semantic equivalence.
    """
    # 1. Fetch all nodes
    node_query = """
    MATCH (n {repo_id: $repo_id})
    RETURN labels(n) AS labels,
           n.uid AS uid,
           n.name AS name,
           n.file_path AS file_path,
           n.class_name AS class_name,
           n.qualified_name AS qualified_name
    """
    node_records = await client.execute_query(node_query, {"repo_id": repo_id})
    
    normalized_nodes = {}
    for r in node_records:
        raw_uid = r.get("uid") or ""
        norm_uid = raw_uid.replace(repo_id, "REPO")
        labels = tuple(sorted(r.get("labels", [])))
        normalized_nodes[norm_uid] = {
            "labels": labels,
            "name": r.get("name"),
            "file_path": r.get("file_path"),
            "class_name": r.get("class_name"),
            "qualified_name": r.get("qualified_name"),
        }

    # 2. Fetch all relationships
    rel_query = """
    MATCH (src {repo_id: $repo_id})-[r]->(dst {repo_id: $repo_id})
    RETURN type(r) AS rel_type,
           src.uid AS src_uid,
           dst.uid AS dst_uid,
           r.provenance AS provenance
    """
    rel_records = await client.execute_query(rel_query, {"repo_id": repo_id})

    normalized_rels = set()
    for r in rel_records:
        src = (r.get("src_uid") or "").replace(repo_id, "REPO")
        dst = (r.get("dst_uid") or "").replace(repo_id, "REPO")
        rel_type = r.get("rel_type")
        normalized_rels.add((rel_type, src, dst))

    return normalized_nodes, normalized_rels


@pytest.mark.asyncio
async def test_incremental_vs_full_equivalence():
    """
    The Primary Acceptance Invariant:
    Graph(Full Index at C) == Graph(Full Index at A -> Inc A->B -> Inc B->C)
    """
    client = Neo4jClient()
    await client.connect()

    repo_id_full = "test_equiv_full_c"
    repo_id_inc = "test_equiv_inc_c"

    await clear_repo_graph(client, repo_id_full)
    await clear_repo_graph(client, repo_id_inc)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        git_repo = Repo.init(tmp_path)

        # ── Commit A ────────────────────────────────────────────────────────
        # Classes, methods, functions, calls, inheritance, tests
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)
        (tmp_path / "tests").mkdir(parents=True, exist_ok=True)

        f_base = tmp_path / "src" / "base.py"
        f_base.write_text("class BaseProcessor:\n    def process(self, data: str) -> str:\n        return data.strip()\n")

        f_service = tmp_path / "src" / "service.py"
        f_service.write_text(
            "from src.base import BaseProcessor\n\n"
            "class DataService(BaseProcessor):\n"
            "    def transform(self, raw: str) -> str:\n"
            "        cleaned = self.process(raw)\n"
            "        return cleaned.upper()\n\n"
            "def run_service():\n"
            "    service = DataService()\n"
            "    return service.transform(' test ')\n"
        )

        f_legacy = tmp_path / "src" / "legacy.py"
        f_legacy.write_text("def legacy_helper():\n    return 'legacy'\n")

        f_del = tmp_path / "src" / "to_delete.py"
        f_del.write_text("def ephemeral_func():\n    return 'delete_me'\n")

        f_test = tmp_path / "tests" / "test_service.py"
        f_test.write_text(
            "def test_transform():\n"
            "    from src.service import DataService\n"
            "    s = DataService()\n"
            "    assert s.transform(' x ') == 'X'\n"
        )

        # Baseline utility files to reflect realistic repository size
        (tmp_path / "src" / "utils").mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "utils" / "math.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
        (tmp_path / "src" / "utils" / "text.py").write_text("def sanitize(s: str) -> str:\n    return s.strip()\n")
        (tmp_path / "src" / "config.py").write_text("class Config:\n    ENV = 'production'\n")
        (tmp_path / "src" / "logger.py").write_text("def log(msg: str):\n    pass\n")
        (tmp_path / "src" / "constants.py").write_text("VERSION = '1.0.0'\n")

        git_repo.index.add([
            "src/base.py",
            "src/service.py",
            "src/legacy.py",
            "src/to_delete.py",
            "tests/test_service.py",
            "src/utils/math.py",
            "src/utils/text.py",
            "src/config.py",
            "src/logger.py",
            "src/constants.py",
        ])
        commit_a = git_repo.index.commit("Commit A")
        sha_a = commit_a.hexsha

        # ── Commit B ────────────────────────────────────────────────────────
        # - Added: src/auth.py
        # - Modified: src/service.py (delete run_service, call auth)
        # - Deleted: src/to_delete.py
        # - Renamed: src/legacy.py -> src/compat.py
        f_auth = tmp_path / "src" / "auth.py"
        f_auth.write_text("class Authenticator:\n    def verify(self, token: str) -> bool:\n        return len(token) > 0\n")

        f_service.write_text(
            "from src.base import BaseProcessor\n"
            "from src.auth import Authenticator\n\n"
            "class DataService(BaseProcessor):\n"
            "    def transform(self, raw: str) -> str:\n"
            "        auth = Authenticator()\n"
            "        auth.verify('tok')\n"
            "        cleaned = self.process(raw)\n"
            "        return cleaned.upper()\n"
        )

        git_repo.index.remove(["src/to_delete.py"])
        f_del.unlink()

        git_repo.git.mv("src/legacy.py", "src/compat.py")

        git_repo.index.add(["src/auth.py", "src/service.py", "src/compat.py"])
        commit_b = git_repo.index.commit("Commit B")
        sha_b = commit_b.hexsha

        # ── Commit C ────────────────────────────────────────────────────────
        # - Modified: src/base.py (add Worker)
        # - Modified: src/service.py (DataService extends Worker instead of BaseProcessor)
        # - Modified: tests/test_service.py (add test_verify -> tests verify)
        f_base.write_text(
            "class BaseProcessor:\n    def process(self, data: str) -> str:\n        return data.strip()\n\n"
            "class Worker:\n    def process(self, data: str) -> str:\n        return data.lower()\n"
        )

        f_service.write_text(
            "from src.base import Worker\n"
            "from src.auth import Authenticator\n\n"
            "class DataService(Worker):\n"
            "    def transform(self, raw: str) -> str:\n"
            "        auth = Authenticator()\n"
            "        auth.verify('tok')\n"
            "        cleaned = self.process(raw)\n"
            "        return cleaned.upper()\n"
        )

        f_test.write_text(
            "def test_transform():\n"
            "    from src.service import DataService\n"
            "    s = DataService()\n"
            "    assert s.transform(' x ') == 'X'\n\n"
            "def test_verify():\n"
            "    from src.auth import Authenticator\n"
            "    a = Authenticator()\n"
            "    assert a.verify('t')\n"
        )

        git_repo.index.add(["src/base.py", "src/service.py", "tests/test_service.py"])
        commit_c = git_repo.index.commit("Commit C")
        sha_c = commit_c.hexsha

        try:
            indexer_full = RepositoryIndexer(graph_client=client)
            indexer_inc = RepositoryIndexer(graph_client=client)

            # ── BUILD GRAPH 1: Full Index at C ──────────────────────────────
            print("\n[Step 1] Full Index at Commit C...", flush=True)
            job_full_c, state_full_c, rep_full_c = await indexer_full.run(
                repo_dir=tmp_path,
                repo_id=repo_id_full,
                target_commit_sha=sha_c,
            )
            assert job_full_c.status == IndexJobStatus.COMPLETED
            assert state_full_c.status == IndexStateStatus.READY
            assert rep_full_c.is_valid is True
            print("  Full Index at C completed successfully.", flush=True)

            # ── BUILD GRAPH 2: Full Index(A) -> Inc(A->B) -> Inc(B->C) ──────
            # Step 1: Full Index at A
            print("[Step 2] Full Index at Commit A...", flush=True)
            job_a, state_a, rep_a = await indexer_inc.run(
                repo_dir=tmp_path,
                repo_id=repo_id_inc,
                target_commit_sha=sha_a,
            )
            assert job_a.status == IndexJobStatus.COMPLETED
            assert state_a.status == IndexStateStatus.READY
            print("  Full Index at A completed successfully.", flush=True)

            # Step 2: Incremental A -> B
            print("[Step 3] Incremental Index Commit A -> Commit B...", flush=True)
            job_b, state_b, rep_b = await indexer_inc.run_incremental(
                repo_dir=tmp_path,
                repo_id=repo_id_inc,
                base_commit_sha=sha_a,
                target_commit_sha=sha_b,
                current_state=state_a,
            )
            assert job_b.status == IndexJobStatus.COMPLETED
            assert state_b.status == IndexStateStatus.READY
            assert state_b.indexed_commit_sha == sha_b
            assert state_b.previous_commit_sha == sha_a
            assert state_b.generation == 2
            print("  Incremental A -> B completed successfully.", flush=True)

            # Step 3: Incremental B -> C
            print("[Step 4] Incremental Index Commit B -> Commit C...", flush=True)
            job_c, state_c, rep_c = await indexer_inc.run_incremental(
                repo_dir=tmp_path,
                repo_id=repo_id_inc,
                base_commit_sha=sha_b,
                target_commit_sha=sha_c,
                current_state=state_b,
            )
            assert job_c.status == IndexJobStatus.COMPLETED
            assert state_c.status == IndexStateStatus.READY
            assert state_c.indexed_commit_sha == sha_c
            assert state_c.previous_commit_sha == sha_b
            assert state_c.generation == 3
            print("  Incremental B -> C completed successfully.", flush=True)

            # ── EXTRACT AND COMPARE GRAPHS ──────────────────────────────────
            print("[Step 5] Extracting and comparing Graph(Full(C)) vs Graph(Incremental(C))...", flush=True)
            nodes_full, rels_full = await export_normalized_graph(client, repo_id_full)
            nodes_inc, rels_inc = await export_normalized_graph(client, repo_id_inc)

            # Assert node sets are strictly identical
            missing_in_inc = set(nodes_full.keys()) - set(nodes_inc.keys())
            surplus_in_inc = set(nodes_inc.keys()) - set(nodes_full.keys())
            assert not missing_in_inc, f"Nodes present in Full(C) but missing in Incremental: {missing_in_inc}"
            assert not surplus_in_inc, f"Nodes present in Incremental but missing in Full(C): {surplus_in_inc}"

            # Assert semantic properties match for every single node
            for uid, full_props in nodes_full.items():
                inc_props = nodes_inc[uid]
                assert full_props == inc_props, f"Node {uid} semantic property divergence: {full_props} != {inc_props}"

            # Assert relationship sets are strictly identical
            missing_rels = rels_full - rels_inc
            surplus_rels = rels_inc - rels_full
            assert not missing_rels, f"Relationships in Full(C) but missing in Incremental: {missing_rels}"
            assert not surplus_rels, f"Relationships in Incremental but missing in Full(C): {surplus_rels}"
            print(f"  EQUIVALENCE VERIFIED: {len(nodes_full)} nodes and {len(rels_full)} relationships are identical!", flush=True)

            # ── IDEMPOTENCY TEST: Repeat Inc(B->C) ──────────────────────────
            print("[Step 6] Testing Idempotency (Repeat Inc(B->C))...", flush=True)
            job_c2, state_c2, rep_c2 = await indexer_inc.run_incremental(
                repo_dir=tmp_path,
                repo_id=repo_id_inc,
                base_commit_sha=sha_c,
                target_commit_sha=sha_c,
                current_state=state_c,
            )
            assert job_c2.status == IndexJobStatus.COMPLETED
            nodes_inc2, rels_inc2 = await export_normalized_graph(client, repo_id_inc)
            assert nodes_inc2 == nodes_inc
            assert rels_inc2 == rels_inc
            print("  Idempotency verified.", flush=True)

            # ── OUT-OF-ORDER PROTECTION TEST ────────────────────────────────
            print("[Step 7] Testing Out-of-Order Stale Commit Rejection...", flush=True)
            job_stale, state_stale, rep_stale = await indexer_inc.run_incremental(
                repo_dir=tmp_path,
                repo_id=repo_id_inc,
                base_commit_sha=sha_c,
                target_commit_sha=sha_a,
                current_state=state_c,
            )
            assert job_stale.status == IndexJobStatus.FAILED
            assert "Out-of-order protection" in job_stale.error
            assert state_stale.indexed_commit_sha == sha_c  # did not roll backwards!
            print("  Out-of-order rejection verified.", flush=True)

        finally:
            git_repo.close()
            await clear_repo_graph(client, repo_id_full)
            await clear_repo_graph(client, repo_id_inc)
            await client.close()
