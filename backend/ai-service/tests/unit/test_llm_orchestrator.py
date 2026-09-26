import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from ai_service.agent.llm_client import DualLLMClient


@pytest.mark.asyncio
async def test_run_orchestrator_ollama_qwen_primary():
    client = DualLLMClient(
        gemini_api_key="gemini-key",
        groq_api_key="groq-key",
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5-coder:latest",
        orchestrator_provider="ollama",
        orchestrator_model="qwen2.5-coder:latest",
    )

    with patch.object(client, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = "### Qwen Orchestrator Verdict: ACCEPT"
        res = await client.run_orchestrator("Review this PR diff", "System instructions")

        assert res == "### Qwen Orchestrator Verdict: ACCEPT"
        mock_ollama.assert_called_once()
        _, kwargs = mock_ollama.call_args
        assert kwargs["model"] == "qwen2.5-coder:latest"


@pytest.mark.asyncio
async def test_run_orchestrator_groq_qwen_fallback():
    client = DualLLMClient(
        gemini_api_key="gemini-key",
        groq_api_key="groq-key",
        ollama_base_url="http://localhost:11434",
        orchestrator_provider="ollama",
        orchestrator_model="qwen2.5-coder:latest",
    )

    with patch.object(client, "_call_ollama", new_callable=AsyncMock) as mock_ollama, \
         patch.object(client, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_ollama.return_value = None
        mock_groq.return_value = "### Groq Qwen Verdict: ACCEPT"

        res = await client.run_orchestrator("Review diff")
        assert res == "### Groq Qwen Verdict: ACCEPT"
        mock_ollama.assert_called_once()
        mock_groq.assert_called_once()
        _, kwargs = mock_groq.call_args
        assert "qwen/qwen3.8-27b" in kwargs["models"]


@pytest.mark.asyncio
async def test_run_orchestrator_gemini_fallback():
    client = DualLLMClient(
        gemini_api_key="gemini-key",
        ollama_base_url="http://localhost:11434",
        orchestrator_provider="ollama",
    )
    client.has_groq = False

    with patch.object(client, "_call_ollama", new_callable=AsyncMock) as mock_ollama, \
         patch.object(client, "_call_gemini", new_callable=AsyncMock) as mock_gemini:
        mock_ollama.return_value = None
        mock_gemini.return_value = "### Gemini Fallback Verdict: ACCEPT"

        res = await client.run_orchestrator("Review diff")
        assert res == "### Gemini Fallback Verdict: ACCEPT"
        mock_ollama.assert_called_once()
        mock_gemini.assert_called_once()


@pytest.mark.asyncio
async def test_run_orchestrator_offline_mode():
    client = DualLLMClient(
        ollama_base_url="http://localhost:11434",
        orchestrator_provider="ollama",
    )
    client.has_groq = False
    client.has_gemini = False

    with patch.object(client, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = None
        res = await client.run_orchestrator("Review diff")
        assert "Knowledge Base Intelligence Summary" in res


@pytest.mark.asyncio
async def test_plan_tool_calls_qwen():
    client = DualLLMClient(
        ollama_base_url="http://localhost:11434",
        orchestrator_provider="ollama",
        orchestrator_model="qwen2.5-coder:latest",
    )

    with patch.object(client, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = '```json\n{"tool_calls": [{"tool_name": "blast_radius", "args": {"symbol": "auth"}}]}\n```'
        calls = await client.plan_tool_calls("Where is auth called?", "my-repo")
        assert len(calls) == 1
        assert calls[0]["tool_name"] == "blast_radius"
        mock_ollama.assert_called_once()
        _, kwargs = mock_ollama.call_args
        assert kwargs["model"] == "qwen2.5-coder:latest"
        assert kwargs["json_mode"] is True


@pytest.mark.asyncio
async def test_api_config_qwen_orchestrator():
    from fastapi.testclient import TestClient
    from ai_service.web.app import app

    test_client = TestClient(app)
    resp = test_client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert data["models"]["orchestrator_provider"] == "ollama"
    assert data["models"]["primary_orchestrator"] == "qwen2.5-coder:latest"
