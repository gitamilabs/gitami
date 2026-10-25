import importlib
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

import src.config as cfg_module
from src.graph.reader import get_entire_graph
from src.indexer.pipeline import RepositoryIndexer
from src.parsing.models import ParseResult, SymbolNode


@pytest.fixture(autouse=True)
def use_memory_backend(monkeypatch):
    monkeypatch.setenv("VECTOR_DB", "memory")
    monkeypatch.setenv("EMBEDDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


@pytest.fixture
def mock_embedder():
    mock = MagicMock()
    mock.dimension = 4
    mock.side_effect = lambda input: [[1.0, 0.0, 0.0, 0.0] for _ in input]
    return mock


@pytest.fixture
def client(mock_embedder):
    with (
        patch("src.vector.embedders.gemini_embedder.GeminiEmbedder.__init__", return_value=None),
        patch("src.vector.embedders.gemini_embedder.GeminiEmbedder.__call__", mock_embedder.side_effect),
        patch("src.vector.embedders.gemini_embedder.GeminiEmbedder.dimension", new=4, create=True),
    ):
        importlib.reload(cfg_module)
        from src.vector.client import VectorKBClient
        return VectorKBClient()


def test_vector_client_project_isolation(client):
    """Verify that vector entries stored under different project_ids do not leak across queries."""
    # Add code entry for project A
    client.add_code_entry(
        repo="org/shared-repo",
        branch="main",
        file_path="src/billing.py",
        symbol="calculate_tax",
        signature="def calculate_tax():",
        description="Project A custom tax logic",
        commit_hash="c1",
        project_id="proj_a",
        team_id="team_alpha",
    )

    # Add code entry for project B
    client.add_code_entry(
        repo="org/shared-repo",
        branch="main",
        file_path="src/billing.py",
        symbol="calculate_tax",
        signature="def calculate_tax():",
        description="Project B custom tax logic",
        commit_hash="c2",
        project_id="proj_b",
        team_id="team_beta",
    )

    # Query scoped to project A
    res_a = client.query(["tax logic"], n_results=5, project_id="proj_a")
    docs_a = res_a.get("documents", [[]])[0]
    metas_a = res_a.get("metadatas", [[]])[0]
    assert len(docs_a) == 1
    assert "Project A" in docs_a[0]
    assert metas_a[0]["project_id"] == "proj_a"
    assert metas_a[0]["team_id"] == "team_alpha"

    # Query scoped to project B
    res_b = client.query(["tax logic"], n_results=5, project_id="proj_b")
    docs_b = res_b.get("documents", [[]])[0]
    metas_b = res_b.get("metadatas", [[]])[0]
    assert len(docs_b) == 1
    assert "Project B" in docs_b[0]
    assert metas_b[0]["project_id"] == "proj_b"
    assert metas_b[0]["team_id"] == "team_beta"


@pytest.mark.asyncio
async def test_get_entire_graph_project_scoping():
    """Verify get_entire_graph passes project_id parameter to node retrieval Cypher queries."""
    mock_client = AsyncMock()
    mock_client.execute_query.return_value = []

    await get_entire_graph(
        mock_client,
        repo_id="test/repo",
        branch="main",
        project_id="proj_xyz",
    )

    assert mock_client.execute_query.called
    scoped_calls = [
        call for call in mock_client.execute_query.call_args_list
        if len(call[0]) > 1 and isinstance(call[0][1], dict) and "project_id" in call[0][1]
    ]
    assert len(scoped_calls) >= 4  # Repository, Directory, File, Symbol
    for call in scoped_calls:
        assert call[0][1]["project_id"] == "proj_xyz"


@pytest.mark.asyncio
async def test_pipeline_stamps_project_and_team():
    """Verify RepositoryIndexer stamps project_id and team_id on both graph and vector entries."""
    mock_vector = MagicMock()
    indexer = RepositoryIndexer(
        graph_client=None,
        vector_client=mock_vector,
    )

    sym = SymbolNode(
        name="authenticate_user",
        qualified_name="authenticate_user",
        kind="function",
        language="python",
        file_path="src/auth.py",
        start_line=1,
        end_line=10,
        signature="def authenticate_user(token: str):",
        code_body="return jwt.decode(token)",
        docstring="Authenticate incoming request bearer token.",
    )

    pr = ParseResult(
        file_path="src/auth.py",
        language="python",
        symbols=[sym],
    )

    job, state, report = await indexer.run(
        repo_id="test-org/secure-repo",
        target_commit_sha="c1c2c3c4",
        branch="main",
        project_id="proj_corp",
        team_id="team_security",
        validate_only=True,
        parse_results=[pr],
    )

    assert job.project_id == "proj_corp"
    assert job.team_id == "team_security"
    assert mock_vector.add_code_entries_batch.called

    batch_entries = mock_vector.add_code_entries_batch.call_args[0][0]
    assert len(batch_entries) == 1
    assert batch_entries[0]["project_id"] == "proj_corp"
    assert batch_entries[0]["team_id"] == "team_security"


def test_generate_doc_id_bounds_and_determinism():
    """Verify generate_doc_id strictly stays <= 64 bytes even with massive input values."""
    from src.vector.client import generate_doc_id, MAX_DOC_ID_BYTES

    # Scenario matching the user's exact failure:
    # project_id = "64cdcea4-b86a-4c3d-b148-d4c9f46b9db8"
    # repo = "AryanRacha/nodejs-backend-template"
    # path = "src/configs/constants.ts"
    # symbol = "VerificationTokenType"
    long_symbol = "VeryLongSymbolNameExceedingStandardLengthsForTypeScriptAndPythonIdentifiersWithExtremeDetail" * 3
    long_path = "deeply/nested/directory/structure/inside/a/monorepo/packages/backend/src/components/" + ("sub/" * 10) + "file.ts"
    project_id = "64cdcea4-b86a-4c3d-b148-d4c9f46b9db8"
    repo = "AryanRacha/nodejs-backend-template"
    branch = "feature/experimental-branch-with-long-name"

    key1 = f"{project_id}:{repo}:{branch}:{long_path}:{long_symbol}:150"
    key2 = f"{project_id}:{repo}:{branch}:{long_path}:{long_symbol}:151"

    id1 = generate_doc_id("code", key1, hint=long_symbol)
    id2 = generate_doc_id("code", key2, hint=long_symbol)

    # Must be <= MAX_DOC_ID_BYTES (64 bytes), well below Chroma Cloud's 128-byte limit
    assert len(id1.encode("utf-8")) <= MAX_DOC_ID_BYTES <= 128
    assert len(id2.encode("utf-8")) <= MAX_DOC_ID_BYTES <= 128

    # Deterministic
    assert id1 == generate_doc_id("code", key1, hint=long_symbol)

    # Collision-proof across different lines / keys
    assert id1 != id2


def test_add_code_entries_batch_uses_bounded_ids(client):
    """Verify add_code_entries_batch persists documents with IDs <= 64 bytes."""
    entries = [
        {
            "repo": "AryanRacha/nodejs-backend-template",
            "branch": "main",
            "file_path": "src/configs/constants.ts",
            "symbol": "VerificationTokenType",
            "signature": "export enum VerificationTokenType { ... }",
            "description": "Verification token types enum",
            "commit_hash": "a1b2c3d4",
            "start_line": 13,
            "project_id": "64cdcea4-b86a-4c3d-b148-d4c9f46b9db8",
            "team_id": "team_core",
        }
    ]
    res = client.add_code_entries_batch(entries)
    assert res["successful"] == 1

    stored_ids = client._store._ids
    assert len(stored_ids) == 1
    doc_id = stored_ids[0]
    assert len(doc_id.encode("utf-8")) <= 64
    assert doc_id.startswith("code_")

