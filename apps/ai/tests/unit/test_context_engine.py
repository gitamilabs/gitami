import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.context.contracts import (
    ContextItem,
    ContextItemType,
    ContextRequest,
    ContextSource,
    AuthorizedScope,
    ContextBudget,
)
from src.context.authorization import (
    AuthorizationError,
    ContextAuthorizer,
    StaticAuthResolver,
)
from src.context.ranking import (
    DeterministicRanker,
    ScoringConfig,
    DEFAULT_EXACT_MATCH_SCORE,
    DEFAULT_DIRECT_DEFINITION_SCORE,
    DEFAULT_DIRECT_RELATIONSHIP_SCORE,
)
from src.context.deduplication import (
    ProviderAwareDeduplicator,
    compute_item_identity,
)
from src.context.budgeting import ContextBudgeter, estimate_tokens
from src.context.provenance import validate_provenance, create_source
from src.context.graph_retriever import GraphRetriever
from src.context.semantic_retriever import SemanticRetriever
from src.context.source_retriever import SourceRetriever
from src.context.github_retriever import GitHubRetriever
from src.context.engine import ContextEngine, classify_query_intent


# ── 1. Authorization Security Boundary ──────────────────────────────────────

@pytest.mark.asyncio
async def test_authorization_project_isolation():
    resolver = StaticAuthResolver({
        "project_alpha": {"repo_1": None, "repo_2": None},
        "project_beta": {"repo_3": None},
    })
    authorizer = ContextAuthorizer(resolver=resolver)

    # Project Alpha authorized
    req = ContextRequest(project_id="project_alpha", query="auth")
    scope = await authorizer.authorize(req)
    assert scope.project_id == "project_alpha"
    assert scope.allowed_repo_ids == {"repo_1", "repo_2"}

    # Project Alpha requesting specific authorized repo
    req2 = ContextRequest(project_id="project_alpha", query="auth", repository_ids=["repo_1"])
    scope2 = await authorizer.authorize(req2)
    assert scope2.allowed_repo_ids == {"repo_1"}


@pytest.mark.asyncio
async def test_authorization_unauthorized_repo_rejected():
    resolver = StaticAuthResolver({
        "project_alpha": {"repo_1": None},
        "project_beta": {"repo_2": None},
    })
    authorizer = ContextAuthorizer(resolver=resolver)

    # Attempting to access repo_2 while authenticated for project_alpha
    req = ContextRequest(project_id="project_alpha", query="auth", repository_ids=["repo_2"])
    with pytest.raises(AuthorizationError) as exc_info:
        await authorizer.authorize(req)
    assert "not authorized for project 'project_alpha'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_authorization_unknown_project_rejected():
    resolver = StaticAuthResolver({})
    authorizer = ContextAuthorizer(resolver=resolver)

    req = ContextRequest(project_id="nonexistent_project", query="auth")
    with pytest.raises(AuthorizationError):
        await authorizer.authorize(req)


# ── 2. Query Intent Classification ──────────────────────────────────────────

def test_query_intent_classification():
    assert classify_query_intent("who calls processPayment?") == "call_graph"
    assert classify_query_intent("where is called AuthService?") == "call_graph"
    assert classify_query_intent("run test for UserManager") == "test"
    assert classify_query_intent("what imports payment_service?") == "dependency"
    assert classify_query_intent("def authenticate_user") == "symbol_lookup"
    assert classify_query_intent("how does rate limiting work?") == "semantic_search"


# ── 3. Provider-Aware Deduplication ─────────────────────────────────────────

def test_provider_aware_deduplication():
    dedup = ProviderAwareDeduplicator()

    item1 = ContextItem(
        id="graph:func:r1:auth.py::login",
        type=ContextItemType.SYMBOL,
        title="Function: login",
        content="Short content",
        relevance_score=0.8,
        source=create_source(kind="graph", repository_id="r1", file_path="auth.py", entity_uid="func:r1:auth.py::login"),
        metadata={"calls": ["validate"]},
    )
    item2 = ContextItem(
        id="sem:vec_r1_0",
        type=ContextItemType.SYMBOL,
        title="Function: login",
        content="Longer enriched content for login function",
        relevance_score=0.9,
        source=create_source(kind="semantic", repository_id="r1", file_path="auth.py", entity_uid="func:r1:auth.py::login"),
        metadata={"docstring": "Authenticates user"},
    )

    # Distinct GitHub item in same file/repo
    item3 = ContextItem(
        id="pr:r1:42",
        type=ContextItemType.PULL_REQUEST,
        title="PR #42",
        content="PR fixing login",
        relevance_score=0.5,
        source=create_source(kind="github_pr", repository_id="r1", file_path="auth.py", pr_number=42),
    )

    items, count = dedup.deduplicate([item1, item2, item3])
    assert len(items) == 2  # item1 and item2 merged, item3 kept distinct!
    assert count == 1

    merged = next(i for i in items if i.source.entity_uid == "func:r1:auth.py::login")
    assert merged.relevance_score == 0.9  # Highest score kept
    assert "calls" in merged.metadata
    assert "docstring" in merged.metadata
    assert "Longer enriched content" in merged.content


# ── 4. Deterministic Ranking & Scoring Configuration ────────────────────────

def test_deterministic_ranking():
    config = ScoringConfig(
        exact_match_score=DEFAULT_EXACT_MATCH_SCORE,
        direct_definition_score=DEFAULT_DIRECT_DEFINITION_SCORE,
        direct_relationship_score=DEFAULT_DIRECT_RELATIONSHIP_SCORE,
    )
    ranker = DeterministicRanker(config=config)

    item_exact = ContextItem(
        id="exact_item",
        type=ContextItemType.SYMBOL,
        title="UserManager",
        content="class UserManager",
        source=create_source(kind="graph", repository_id="r1", entity_uid="class:r1:user.py::UserManager"),
    )
    item_rel = ContextItem(
        id="rel_item",
        type=ContextItemType.CALL_GRAPH,
        title="Call: login -> UserManager",
        content="login calls UserManager",
        source=create_source(kind="graph", repository_id="r1"),
        metadata={"hop_distance": 1},
    )
    item_other = ContextItem(
        id="other_item",
        type=ContextItemType.SEMANTIC_CODE,
        title="Snippet: payment.py",
        content="def pay()",
        source=create_source(kind="semantic", repository_id="r1"),
        metadata={"similarity": 0.4},
    )

    ranked1 = ranker.rank([item_other, item_rel, item_exact], query="UserManager")
    ranked2 = ranker.rank([item_rel, item_exact, item_other], query="UserManager")

    # Invariant: Output is strictly identical regardless of input collection order
    assert [i.id for i in ranked1] == [i.id for i in ranked2]
    assert ranked1[0].id == "exact_item"
    assert ranked1[0].relevance_score >= ranked1[1].relevance_score >= ranked1[2].relevance_score


# ── 5. Context Budgeting ────────────────────────────────────────────────────

def test_context_budgeting_item_and_tokens():
    budgeter = ContextBudgeter()
    items = [
        ContextItem(id=f"item_{i}", type=ContextItemType.SYMBOL, title=f"Title {i}", content="word " * 50, relevance_score=1.0 - (i * 0.1))
        for i in range(10)
    ]

    # Limit to max 3 items
    budget_items = ContextBudget(max_items=3, max_tokens=10000)
    res_items, trunc = budgeter.apply_budget(items, budget_items)
    assert len(res_items) == 3
    assert trunc is True
    assert [i.id for i in res_items] == ["item_0", "item_1", "item_2"]

    # Limit by token budget
    budget_tokens = ContextBudget(max_items=20, max_tokens=100)
    res_tokens, trunc2 = budgeter.apply_budget(items, budget_tokens)
    assert len(res_tokens) < len(items)
    assert trunc2 is True


# ── 6. Provenance Validation ────────────────────────────────────────────────

def test_provenance_validation():
    valid_source = create_source(
        kind="graph",
        repository_id="repo_real",
        file_path="src/main.py",
        entity_uid="func:repo_real:src/main.py::main",
        commit_sha="abc12345",
        start_line=1,
        end_line=10,
    )
    valid_item = ContextItem(id="i1", type=ContextItemType.SYMBOL, title="main", content="def main(): pass", source=valid_source)
    assert validate_provenance(valid_item) is True

    # Missing repository_id
    invalid_source = ContextSource(kind="graph", repository_id="")
    invalid_item = ContextItem(id="i2", type=ContextItemType.SYMBOL, title="test", content="", source=invalid_source)
    assert validate_provenance(invalid_item) is False

    # Fabricated placeholder
    fake_source = create_source(kind="graph", repository_id="repo_1", file_path="PLACEHOLDER_FILE")
    fake_item = ContextItem(id="i3", type=ContextItemType.SYMBOL, title="test", content="", source=fake_source)
    assert validate_provenance(fake_item) is False


# ── 7. Semantic Cross-Repo Leakage Prevention ───────────────────────────────

@pytest.mark.asyncio
async def test_semantic_retriever_filters_foreign_repositories():
    mock_vec = MagicMock()
    # Mock vector client returning items for both authorized repo_A and foreign repo_B
    mock_vec.query.return_value = {
        "ids": [["doc_a", "doc_b"]],
        "documents": [["Code for A", "Code for B"]],
        "metadatas": [[{"repo": "repo_A", "file_path": "a.py"}, {"repo": "repo_B", "file_path": "b.py"}]],
        "distances": [[0.1, 0.1]],
    }

    retriever = SemanticRetriever(mock_vec)
    scope = AuthorizedScope(project_id="proj_1", allowed_repo_ids={"repo_A"})

    results = await retriever.retrieve("search query", scope=scope)
    assert len(results) == 1
    assert results[0].source.repository_id == "repo_A"
    assert "repo_B" not in [r.source.repository_id for r in results]


# ── 8. Source Retriever Commit Consistency ──────────────────────────────────

def test_source_retriever_commit_consistency(tmp_path):
    import git

    # Create a small git repo with 2 commits
    r = git.Repo.init(tmp_path)
    test_file = tmp_path / "app.py"
    
    test_file.write_text("def version_one():\n    return 1\n")
    r.index.add(["app.py"])
    commit1 = r.index.commit("commit 1").hexsha

    test_file.write_text("def version_two():\n    return 2\n")
    r.index.add(["app.py"])
    commit2 = r.index.commit("commit 2").hexsha

    retriever = SourceRetriever(default_repo_root=tmp_path)
    scope = AuthorizedScope(project_id="proj_1", allowed_repo_ids={"test_repo"}, repo_paths={"test_repo": tmp_path})

    # Retrieve at commit 1
    item_c1 = retriever.retrieve_snippet(
        repo_id="test_repo",
        file_path="app.py",
        scope=scope,
        commit_sha=commit1,
        start_line=1,
        end_line=2,
    )
    assert item_c1 is not None
    assert "version_one" in item_c1.content
    assert item_c1.source.commit_sha == commit1

    # Retrieve at commit 2
    item_c2 = retriever.retrieve_snippet(
        repo_id="test_repo",
        file_path="app.py",
        scope=scope,
        commit_sha=commit2,
        start_line=1,
        end_line=2,
    )
    assert item_c2 is not None
    assert "version_two" in item_c2.content
    assert item_c2.source.commit_sha == commit2

    # Request invalid non-existent commit -> must return None (no silent wrong revision fallback)
    item_bad = retriever.retrieve_snippet(
        repo_id="test_repo",
        file_path="app.py",
        scope=scope,
        commit_sha="0000000000000000000000000000000000000000",
    )
    assert item_bad is None


# ── 9. Provider Failure Resilience ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_provider_failure_resilience():
    # Setup mock authorizer
    authorizer = ContextAuthorizer(
        resolver=StaticAuthResolver({"proj_1": {"repo_1": None}})
    )

    engine = ContextEngine(authorizer=authorizer)

    # Mock graph retriever to succeed
    engine.graph_retriever = AsyncMock()
    engine.graph_retriever.retrieve.return_value = [
        ContextItem(
            id="g1",
            type=ContextItemType.SYMBOL,
            title="Func A",
            content="def a(): pass",
            source=create_source(kind="graph", repository_id="repo_1"),
        )
    ]

    # Mock semantic retriever to fail with exception
    engine.semantic_retriever = AsyncMock()
    engine.semantic_retriever.retrieve.side_effect = RuntimeError("Vector DB connection timeout")

    req = ContextRequest(project_id="proj_1", query="test query", include_source=False, include_github=False)
    res = await engine.retrieve(req)

    # Invariant: Partial results returned + ProviderError recorded
    assert res.returned_items == 1
    assert res.items[0].id == "g1"
    assert len(res.errors) == 1
    assert res.errors[0].provider == "semantic"
    assert "Vector DB connection timeout" in res.errors[0].error
