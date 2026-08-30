"""Tests for parallel query execution, post-retrieval context compression, and batch resilience."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from ai_service.web.app import _execute_single_tool, _compress_retrieved_context, ChatRequest
from ai_service.vector.client import VectorKBClient


@pytest.mark.asyncio
async def test_parallel_tool_execution():
    graph_client = MagicMock()
    vector_client = MagicMock()
    vector_client.query.return_value = {
        "documents": [["def foo(): return 1"]],
        "metadatas": [[{"file_path": "foo.py", "symbol_name": "foo"}]],
        "distances": [[0.05]],
    }

    req = ChatRequest(repo_id="test/repo", message="how does foo work?")
    call1 = {"tool_name": "vector_search", "args": {"query": "foo"}}
    call2 = {"tool_name": "vector_search", "args": {"query": "foo"}}

    tasks = [
        _execute_single_tool(1, call1, req, graph_client, vector_client),
        _execute_single_tool(2, call2, req, graph_client, vector_client),
    ]

    results = await asyncio.gather(*tasks)
    assert len(results) == 2
    step1, cits1 = results[0]
    step2, cits2 = results[1]

    assert step1.status == "completed"
    assert step2.status == "completed"
    assert len(cits1) == 1
    assert cits1[0]["file_path"] == "foo.py"


@pytest.mark.asyncio
async def test_compress_retrieved_context_short_skips_llm():
    llm_client = MagicMock()
    chunks = ["[1] Short code chunk in foo.py"]
    res = await _compress_retrieved_context(llm_client, chunks, "foo query")
    assert res == "[1] Short code chunk in foo.py"
    assert not llm_client.run_orchestrator.called


@pytest.mark.asyncio
async def test_compress_retrieved_context_long_triggers_llm():
    llm_client = MagicMock()
    llm_client.run_orchestrator = AsyncMock(return_value="[1] Compressed summary with facts preserved.")
    
    long_chunks = [f"[{i}] Detailed passage describing subsystem {i} in depth with large amount of code." * 10 for i in range(1, 6)]
    res = await _compress_retrieved_context(llm_client, long_chunks, "subsystem query")
    assert res == "[1] Compressed summary with facts preserved."
    assert llm_client.run_orchestrator.called


def test_vector_client_batch_resilience():
    client = VectorKBClient()
    # Mock store
    client._store = MagicMock()
    client._batch_size = 2

    # Simulate store upsert failing on 1st attempt for batch 1, then succeeding on retry
    call_counts = 0

    def mock_upsert(*args, **kwargs):
        nonlocal call_counts
        call_counts += 1
        if call_counts == 1:
            raise ConnectionError("Transient network failure")
        return None

    client._store.upsert.side_effect = mock_upsert

    entries = [
        {"repo": "r", "branch": "b", "file_path": f"f_{i}.py", "symbol": f"s_{i}", "signature": "sig", "description": "desc", "commit_hash": "c"}
        for i in range(2)
    ]
    res = client.add_code_entries_batch(entries)
    assert res["total"] == 2
    assert res["successful"] == 2
    assert res["failed"] == 0
