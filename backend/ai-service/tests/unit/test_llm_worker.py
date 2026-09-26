import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from ai_service.agent.llm_client import DualLLMClient, OLLAMA_MODELS


@pytest.mark.asyncio
async def test_ollama_call_success():
    client = DualLLMClient(
        gemini_api_key="test-gemini",
        groq_api_key="test-groq",
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5-coder:latest",
        worker_provider="ollama",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen2.5-coder:latest",
        "message": {"role": "assistant", "content": '{"issues": []}'},
        "done": True,
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await client._call_ollama(
            prompt="Analyze this diff",
            system_prompt="You are a code review worker",
            json_mode=True,
        )

        assert res == '{"issues": []}'
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["model"] == "qwen2.5-coder:latest"
        assert payload["format"] == "json"
        assert payload["messages"][1]["content"] == "Analyze this diff"


@pytest.mark.asyncio
async def test_ollama_call_error_and_cooldown():
    client = DualLLMClient(
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5-coder:latest",
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = Exception("Connection refused to localhost:11434")
        res = await client._call_ollama(
            prompt="Test prompt",
            system_prompt="Test system",
        )
        assert res is None
        assert client._ollama_cooldown_until > 0

        # Subsequent call should immediately return None due to cooldown
        res_cached = await client._call_ollama(
            prompt="Test prompt 2",
            system_prompt="Test system",
        )
        assert res_cached is None


@pytest.mark.asyncio
async def test_run_worker_ollama_primary():
    client = DualLLMClient(
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5-coder:latest",
        worker_provider="ollama",
    )

    with patch.object(client, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = '{"issues": [{"title": "Bug found"}]}'

        res = await client.run_worker("Review diff containing json")
        assert res == '{"issues": [{"title": "Bug found"}]}'
        mock_ollama.assert_called_once()


@pytest.mark.asyncio
async def test_run_worker_fallback_to_groq():
    client = DualLLMClient(
        groq_api_key="gsk-test",
        ollama_base_url="http://localhost:11434",
        worker_provider="ollama",
    )

    with patch.object(client, "_call_ollama", new_callable=AsyncMock) as mock_ollama, \
         patch.object(client, "_call_groq", new_callable=AsyncMock) as mock_groq:
        # Ollama fails / returns None
        mock_ollama.return_value = None
        mock_groq.return_value = '{"issues": [{"title": "From Groq Fallback"}]}'

        res = await client.run_worker("Review diff")
        assert res == '{"issues": [{"title": "From Groq Fallback"}]}'
        mock_ollama.assert_called_once()
        mock_groq.assert_called_once()


@pytest.mark.asyncio
async def test_run_worker_fallback_to_gemini():
    client = DualLLMClient(
        gemini_api_key="gemini-test",
        ollama_base_url="http://localhost:11434",
        worker_provider="ollama",
    )
    client.has_groq = False

    with patch.object(client, "_call_ollama", new_callable=AsyncMock) as mock_ollama, \
         patch.object(client, "_call_gemini", new_callable=AsyncMock) as mock_gemini:
        mock_ollama.return_value = None
        mock_gemini.return_value = '{"issues": [{"title": "From Gemini Fallback"}]}'

        res = await client.run_worker("Review diff")
        assert res == '{"issues": [{"title": "From Gemini Fallback"}]}'
        mock_ollama.assert_called_once()
        mock_gemini.assert_called_once()


@pytest.mark.asyncio
async def test_run_worker_offline_mode():
    client = DualLLMClient(
        ollama_base_url="http://localhost:11434",
        worker_provider="ollama",
    )
    client.has_groq = False
    client.has_gemini = False

    with patch.object(client, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
        mock_ollama.return_value = None
        res = await client.run_worker("Review diff")
        assert "[Worker Node - Offline Mode]" in res


@pytest.mark.asyncio
async def test_api_config_ollama_settings():
    from fastapi.testclient import TestClient
    from ai_service.web.app import app

    test_client = TestClient(app)
    resp = test_client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert data["models"]["worker_provider"] == "ollama"
    assert data["models"]["ollama_model"] == "qwen2.5-coder:latest"
    assert data["models"]["worker_model"] == "qwen2.5-coder:latest"
    assert "qwen2.5-coder:latest" in data["models"]["ollama_models"]
