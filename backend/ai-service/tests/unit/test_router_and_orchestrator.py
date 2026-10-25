"""Unit tests for GitAmi Deterministic Router, Stateful Orchestrator, Fixer Guardrails, and Telemetry."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from ai_service.agent.router import classify_file, build_route_plan, RoutePlan
from ai_service.agent.telemetry import ReviewTrace, get_current_trace, set_current_trace
from ai_service.agent.orchestrator import StatefulOrchestrator, ReviewState
from ai_service.agent.fixer import classify_mechanical_fix, validate_syntax_guardrail
from ai_service.agent.agent_loop import classify_chat_intent
from ai_service.agent.reviewer import run_agentic_pr_review
from ai_service.agent.llm_client import DualLLMClient


def test_router_skip_tier():
    # Lockfiles
    r1 = classify_file("package-lock.json")
    assert r1.tier == "skip"
    r2 = classify_file("poetry.lock")
    assert r2.tier == "skip"
    r3 = classify_file("Cargo.lock")
    assert r3.tier == "skip"

    # Static assets
    r4 = classify_file("static/images/hero.png")
    assert r4.tier == "skip"
    r5 = classify_file("assets/fonts/inter.woff2")
    assert r5.tier == "skip"

    # Generated bundles
    r6 = classify_file("dist/bundle.min.js")
    assert r6.tier == "skip"
    r7 = classify_file("proto/service_pb2.py")
    assert r7.tier == "skip"

    # RoutePlan all skipped
    lockfile_diff = """diff --git a/package-lock.json b/package-lock.json
index 1111111..2222222 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,3 +1,3 @@
-"version": "1.0.0"
+"version": "1.0.1"
"""
    plan = build_route_plan(lockfile_diff)
    assert plan.all_skipped is True
    assert plan.run_graph is False
    assert plan.run_cpg is False
    assert plan.run_vector is False


def test_router_deep_tier_sinks_and_paths():
    # Auth path
    r_auth = classify_file("src/auth/jwt_handler.py")
    assert r_auth.tier == "deep"
    assert "pr_worker_security" in r_auth.specialists

    # Sensitive SQL sink in diff
    sql_diff = """
+   cursor.execute("SELECT * FROM users WHERE id = '" + user_id + "'")
"""
    r_sql = classify_file("src/controllers/user.py", sql_diff)
    assert r_sql.tier == "deep"
    assert "pr_worker_security" in r_sql.specialists

    # Command execution sink
    cmd_diff = """
+   subprocess.Popen(f"ping {ip_addr}", shell=True)
"""
    r_cmd = classify_file("src/services/network.py", cmd_diff)
    assert r_cmd.tier == "deep"
    assert "pr_worker_security" in r_cmd.specialists

    # Route plan should flag graph and cpg for deep tier
    plan = build_route_plan(cmd_diff, changed_files=["src/services/network.py"])
    assert plan.all_skipped is False
    assert plan.run_graph is True
    assert plan.run_cpg is True


def test_router_light_tier():
    # Docs
    r_doc = classify_file("docs/ARCHITECTURE.md")
    assert r_doc.tier == "light"
    assert "pr_worker_generic" in r_doc.specialists

    # Test file without sinks
    test_diff = """
+   assert result == 42
"""
    r_test = classify_file("tests/unit/test_math.py", test_diff)
    assert r_test.tier == "light"


def test_telemetry_trace():
    trace = ReviewTrace(pr_id="test_repo/123", tier_plan={"tier": "deep"})
    assert trace.total_calls == 0

    trace.record_llm_call("groq", tokens_in=100, tokens_out=20)
    trace.record_llm_call("gemini", tokens_in=500, tokens_out=80)
    trace.finish()

    d = trace.to_dict()
    assert d["pr_id"] == "test_repo/123"
    assert d["llm_calls_by_provider"]["groq"] == 1
    assert d["llm_calls_by_provider"]["gemini"] == 1
    assert d["total_calls"] == 2
    assert d["tokens_in"] == 600
    assert d["tokens_out"] == 100
    assert d["latency_ms"] >= 0.0


def test_fixer_mechanical_classifier():
    # .size() on JS array -> .length
    issue_size = {
        "title": "Invalid .size() method called on JS Array",
        "description": "Calling .size() on array causes runtime TypeError in JavaScript",
        "suggested_fix": "items.length",
        "line": 2,
    }
    content_js = "function check(items) {\n    return items.size() > 0;\n}"
    res = classify_mechanical_fix(issue_size, content_js)
    assert res is not None
    target, replacement = res
    assert ".size()" in target
    assert ".length" in replacement

    # Replace X with Y pattern
    issue_replace = {
        "title": "Deprecated constant",
        "description": "Use MAX_SIZE instead of OLD_SIZE",
        "suggested_fix": "Replace OLD_SIZE with MAX_SIZE",
    }
    content_py = "limit = OLD_SIZE * 2"
    res_py = classify_mechanical_fix(issue_replace, content_py)
    assert res_py is not None
    assert res_py == ("OLD_SIZE", "MAX_SIZE")


def test_syntax_guardrail_validation():
    # Python syntax validation
    valid_py = "def compute(a: int) -> int:\n    return a * 2\n"
    invalid_py = "def compute(a: int) ->\n    return a * 2\n"
    assert validate_syntax_guardrail(valid_py, "math.py") is True
    assert validate_syntax_guardrail(invalid_py, "math.py") is False

    # JSON syntax validation
    valid_json = '{"name": "gitami", "active": true}'
    invalid_json = '{"name": "gitami", "active": true,'
    assert validate_syntax_guardrail(valid_json, "config.json") is True
    assert validate_syntax_guardrail(invalid_json, "config.json") is False

    # JavaScript Tree-sitter validation
    valid_js = "function add(x, y) { return x + y; }"
    invalid_js = "function add(x, y) { return x +; }"
    assert validate_syntax_guardrail(valid_js, "calc.js") is True
    assert validate_syntax_guardrail(invalid_js, "calc.js") is False


def test_chat_intent_router():
    # Blast radius query
    b_intent = classify_chat_intent("What is the blast radius of AuthService?", "repo1", "main")
    assert b_intent is not None
    assert b_intent["intent"] == "blast_radius"
    assert b_intent["tool_name"] == "get_blast_radius"

    # File dependencies query
    d_intent = classify_chat_intent("What are the dependencies of api.js?", "repo1", "main")
    assert d_intent is not None
    assert d_intent["intent"] == "file_deps"
    assert d_intent["tool_name"] == "get_file_dependencies"

    # Symbol lookup query
    s_intent = classify_chat_intent("Where is fetchUsers defined in this repo?", "repo1", "main")
    assert s_intent is not None
    assert s_intent["intent"] == "symbol_lookup"
    assert s_intent["tool_name"] == "hybrid_search"

    # Open-ended question should not match fast intent
    open_intent = classify_chat_intent("Can you explain how auth works and suggest refactorings?", "repo1", "main")
    assert open_intent is None


@pytest.mark.asyncio
async def test_reviewer_zero_call_short_circuit():
    lockfile_diff = """diff --git a/yarn.lock b/yarn.lock
index e69de29..d95f3ad 100644
--- a/yarn.lock
+++ b/yarn.lock
@@ -1,3 +1,3 @@
-"react@^18.0.0":
+"react@^18.2.0":
"""
    # Create mock LLM client to verify 0 calls are made
    mock_llm = MagicMock(spec=DualLLMClient)
    mock_llm.run_worker = AsyncMock()
    mock_llm.run_orchestrator = AsyncMock()
    mock_llm.has_gemini = True
    mock_llm.has_groq = True

    result = await run_agentic_pr_review(
        repo_id="short-circuit-demo",
        raw_diff_text=lockfile_diff,
        llm_client=mock_llm,
        mode="text_rag",
    )

    assert result.decision.verdict == "ACCEPT"
    assert result.decision.risk_score == 0.0
    assert len(result.issues) == 0
    # Zero calls to LLMs
    mock_llm.run_worker.assert_not_called()
    mock_llm.run_orchestrator.assert_not_called()
    assert result.trace is not None
    assert result.trace.total_calls == 0


@pytest.mark.asyncio
async def test_stateful_orchestrator_batched_verification():
    mock_llm = MagicMock(spec=DualLLMClient)
    # Mock batched verification returning confirmed and dismissed issues
    batched_response = json.dumps({
        "confirmed_issues": [
            {
                "id": "c1",
                "title": "Unescaped SQL query",
                "description": "SQL injection via string interpolation",
                "category": "security",
                "severity": "error",
                "file_path": "src/user.py",
                "line": 42,
                "suggested_fix": "Use parameterized query",
            }
        ],
        "dismissed_issues": [
            {
                "id": "c2",
                "title": "Potential null dereference",
                "dismissal_reason": "Guarded by compile-time TypeScript non-null assertion",
            }
        ],
        "verdict": "SUGGEST",
    })
    mock_llm.run_orchestrator = AsyncMock(return_value=batched_response)

    orch = StatefulOrchestrator(llm_client=mock_llm, max_steps=2, batch_verify=True)
    plan = RoutePlan(files=[], run_graph=False, run_cpg=False, run_vector=False, all_skipped=False)
    candidates = [
        {"id": "c1", "title": "Unescaped SQL query", "severity": "error", "file_path": "src/user.py", "line": 42},
        {"id": "c2", "title": "Potential null dereference", "severity": "warning", "file_path": "src/app.ts", "line": 10},
    ]

    state = await orch.run(
        plan=plan,
        candidates=candidates,
        raw_diff_text="sample diff",
        repo_id="test_repo",
    )

    assert len(state.verified) == 1
    assert state.verified[0]["id"] == "c1"
    assert len(state.dismissed) == 1
    assert state.dismissed[0][0]["id"] == "c2"
    assert state.status == "done"
    # Exactly 1 batched verification call made to orchestrator
    mock_llm.run_orchestrator.assert_called_once()
