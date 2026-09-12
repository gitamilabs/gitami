import json
import pytest
from ai_service.mcp.tools import (
    tool_cpg_dataflow,
    tool_cpg_reachable_guards,
    tool_cpg_callers_with_args,
    execute_tool_by_name,
)


@pytest.mark.asyncio
async def test_cpg_mcp_tools():
    # Test tool_cpg_dataflow returns valid json
    res_df = await tool_cpg_dataflow(repo_id="test-repo", source_pattern="req.body", sink_pattern="query")
    data_df = json.loads(res_df)
    assert "reachable" in data_df
    assert "source" in data_df
    assert "sink" in data_df

    # Test tool_cpg_reachable_guards returns valid json
    res_guards = await tool_cpg_reachable_guards(repo_id="test-repo", symbol_name="query")
    data_guards = json.loads(res_guards)
    assert "guarded" in data_guards
    assert "guards" in data_guards

    # Test tool_cpg_callers_with_args returns valid json
    res_callers = await tool_cpg_callers_with_args(repo_id="test-repo", symbol_name="query")
    data_callers = json.loads(res_callers)
    assert "symbol" in data_callers
    assert "callers_with_args" in data_callers


@pytest.mark.asyncio
async def test_execute_tool_by_name_cpg_dispatch():
    # Test dispatching CPG tools through dynamic executor
    res = await execute_tool_by_name(
        tool_name="cpg_dataflow",
        tool_args={"source": "input", "sink": "exec"},
        graph_client=None,
        vector_client=None,
        repo_id="test-repo",
    )
    parsed = json.loads(res)
    assert "source" in parsed
    assert parsed["source"] == "input"

    res_guard = await execute_tool_by_name(
        tool_name="cpg_reachable_guards",
        tool_args={"symbol": "login"},
        graph_client=None,
        vector_client=None,
        repo_id="test-repo",
    )
    parsed_guard = json.loads(res_guard)
    assert parsed_guard["symbol"] == "login"


def test_format_cpg_security_summary():
    from ai_service.agent.reviewer import format_cpg_security_summary

    target_syms = ["db_execute", "render_html", "log_event"]
    guards_res = [
        {"guards": ["if req.query:", "if is_admin(req):"]},  # Weak presence & auth
        {"guards": ["const clean = DOMPurify.sanitize(input)"]},  # Strong sanitizer
        {"guards": []},  # Unguarded sink
    ]
    callers_res = [
        {"callers_with_args": ["routes.py: search_users(req.params.query)"]},
        {"callers_with_args": ["views.py: show_profile(user_data)"]},
        {"callers_with_args": []},
    ]

    summary = format_cpg_security_summary(target_syms, guards_res, callers_res)

    # Verify header & policy statement
    assert "Joern CPG Structural Control-Flow & Taint Analysis Briefing" in summary
    assert "DEFENSIVE SECURITY POLICY (Zero False Negatives)" in summary

    # Verify weak guard classification on db_execute
    assert "**Symbol: `db_execute`**" in summary
    assert "INSUFFICIENT SANITIZATION" in summary
    assert "Non-Sanitizing Guards: if req.query:, if is_admin(req):" in summary

    # Verify strong sanitizer classification on render_html
    assert "**Symbol: `render_html`**" in summary
    assert "POTENTIALLY SANITIZED" in summary
    assert "DOMPurify.sanitize" in summary

    # Verify unguarded sink on log_event
    assert "**Symbol: `log_event`**" in summary
    assert "NO SANITIZER DETECTED" in summary

