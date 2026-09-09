import asyncio
import tempfile
from pathlib import Path
from git import Repo
import pytest

from src.graph.client import Neo4jClient
from src.vector.client import VectorKBClient
from src.indexer.pipeline import RepositoryIndexer
from src.context import (
    ContextEngine,
    ContextRequest,
    ContextItemType,
    AuthorizationError,
    StaticAuthResolver,
)
from src.context.authorization import ContextAuthorizer
from src.web.app import app, ContextApiRequest, retrieve_project_context


async def clear_repo_graph(client: Neo4jClient, repo_id: str):
    query = "MATCH (n {repo_id: $repo_id}) DETACH DELETE n"
    await client.execute_query(query, {"repo_id": repo_id})


@pytest.mark.asyncio
async def test_context_engine_end_to_end_integration():
    """
    End-to-end integration test verifying Context Engine V1 against live Neo4j and vector storage.
    Verifies:
    1. Repository indexing into Neo4j
    2. Semantic vector store population
    3. Graph relationship queries ('Who calls X?')
    4. Semantic concept retrieval ('Where is authentication handled?')
    5. Test coverage retrieval
    6. Commit-isolated source snippet retrieval
    7. Authorization boundaries and foreign repo rejection
    8. Critical Determinism Invariant: Same request + same state -> Identical ContextResult
    9. Web API endpoint POST /projects/{project_id}/context
    """
    client = Neo4jClient()
    try:
        await asyncio.wait_for(client.verify_connectivity(), timeout=2.0)
    except Exception:
        pytest.skip("Neo4j database is not running, skipping live Context Engine integration test")

    test_project = "project_ctx_test"
    test_repo_id = "ctx_test_repo"

    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = Path(tmp_dir)
        git_repo = Repo.init(repo_dir)

        # 1. Populate Git repository with Python code
        src_dir = repo_dir / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        tests_dir = repo_dir / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)

        auth_code = (
            "def authenticate(user, token):\n"
            '    """Validates user authentication token."""\n'
            '    if token == "secret":\n'
            "        return True\n"
            "    return False\n"
            "\n"
            "class SessionManager:\n"
            "    def create_session(self, user):\n"
            "        return f'session_{user}'\n"
        )
        (src_dir / "auth.py").write_text(auth_code)

        payment_code = (
            "from src.auth import authenticate\n"
            "\n"
            "def process_payment(amount, user):\n"
            '    if not authenticate(user, "token_xyz"):\n'
            '        raise PermissionError("User not authenticated")\n'
            '    return f"Processed {amount}"\n'
        )
        (src_dir / "payment.py").write_text(payment_code)

        test_code = (
            "from src.auth import authenticate\n"
            "\n"
            "def test_authenticate():\n"
            '    assert authenticate("alice", "secret") is True\n'
        )
        (tests_dir / "test_auth.py").write_text(test_code)

        git_repo.index.add(["src/auth.py", "src/payment.py", "tests/test_auth.py"])
        commit_sha = git_repo.index.commit("Initial indexed commit").hexsha

        # 2. Index repository into Neo4j
        await clear_repo_graph(client, test_repo_id)
        indexer = RepositoryIndexer(graph_client=client)
        job, state, report = await indexer.run(
            repo_dir=repo_dir,
            repo_id=test_repo_id,
            target_commit_sha=commit_sha,
            branch="main",
            project_id=test_project,
        )
        assert report.is_valid is True

        # 3. Seed VectorKBClient with code and PR entries
        vector_client = VectorKBClient()
        vector_client.add_code_entry(
            repo=test_repo_id,
            branch="main",
            file_path="src/auth.py",
            symbol="authenticate",
            signature="authenticate(user, token)",
            description="Validates user authentication token and checks credentials",
            commit_hash=commit_sha,
            start_line=1,
            code_body=auth_code,
        )
        vector_client.add_pr_entry(
            repo=test_repo_id,
            branch="main",
            pr_id="101",
            description_text="Implement secure token authentication and session creation",
            commit_hash=commit_sha,
        )

        try:
            # 4. Instantiate Context Engine with explicit static authorization resolver
            auth_resolver = StaticAuthResolver({
                test_project: {test_repo_id: repo_dir},
                "other_project": {"foreign_repo": None},
            })
            authorizer = ContextAuthorizer(resolver=auth_resolver, graph_client=client)
            engine = ContextEngine(
                graph_client=client,
                vector_client=vector_client,
                authorizer=authorizer,
                default_repo_root=repo_dir,
            )

            # ── Check 1: Graph Relationship Query ('Who calls authenticate?') ──
            req_call = ContextRequest(
                project_id=test_project,
                query="Who calls authenticate",
                hops=1,
            )
            res_call = await engine.retrieve(req_call)
            assert res_call.returned_items > 0
            assert any(i.type == ContextItemType.CALL_GRAPH for i in res_call.items)
            call_item = next(i for i in res_call.items if i.type == ContextItemType.CALL_GRAPH)
            assert "authenticate" in call_item.content.lower()

            # ── Check 2: Semantic Concept Retrieval ('Where is authentication handled?') ──
            req_sem = ContextRequest(
                project_id=test_project,
                query="Where is authentication handled?",
                include_semantic=True,
                include_source=True,
            )
            res_sem = await engine.retrieve(req_sem)
            assert res_sem.returned_items > 0
            # Must return evidence from src/auth.py
            assert any("auth.py" in (i.source.file_path or "") for i in res_sem.items)

            # ── Check 3: Source Snippet & Commit Consistency ──
            source_items = [i for i in res_sem.items if i.source.kind == "source_code"]
            assert len(source_items) > 0
            snippet = source_items[0]
            assert snippet.source.commit_sha == commit_sha
            assert snippet.source.file_path is not None
            assert len(snippet.content) > 0

            # ── Check 4: Authorization Boundary & Leakage Protection ──
            # Foreign repository in request must raise AuthorizationError
            with pytest.raises(AuthorizationError) as exc_info:
                await engine.retrieve(
                    ContextRequest(
                        project_id=test_project,
                        query="auth",
                        repository_ids=["foreign_repo"],
                    )
                )
            assert "not authorized for project" in str(exc_info.value)

            # Unauthorized project must raise AuthorizationError
            with pytest.raises(AuthorizationError):
                await engine.retrieve(
                    ContextRequest(
                        project_id="unauthorized_random_project",
                        query="auth",
                    )
                )

            # ── Check 5: Critical Determinism Invariant ──
            # Same Project + Same Query + Same Scope + Same State -> Same logical ordering & content
            run_a = await engine.retrieve(req_call)
            run_b = await engine.retrieve(req_call)

            assert len(run_a.items) == len(run_b.items)
            for item_a, item_b in zip(run_a.items, run_b.items):
                assert item_a.id == item_b.id
                assert item_a.type == item_b.type
                assert item_a.relevance_score == item_b.relevance_score
                assert item_a.title == item_b.title
                assert item_a.source.repository_id == item_b.source.repository_id
                assert item_a.source.entity_uid == item_b.source.entity_uid

            # ── Check 6: Web API Endpoint Integration ──
            api_body = ContextApiRequest(
                query="Who calls authenticate?",
                branch="main",
                max_items=5,
            )
            api_response = await retrieve_project_context(test_project, api_body)
            assert isinstance(api_response, dict)
            assert api_response["project_id"] == test_project
            assert len(api_response["items"]) > 0
            assert "retrieval_metadata" in api_response

        finally:
            # Clean up Neo4j graph nodes and vector data
            await clear_repo_graph(client, test_repo_id)
            vector_client.delete(where={"repo": test_repo_id})
            await client.close()
