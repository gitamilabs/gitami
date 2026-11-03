import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.llm_client import DualLLMClient, LOCAL_MODELS
from src.agents.agent_loop import AutonomousAgentLoop


@pytest.mark.asyncio
async def test_dual_llm_client_initialization_local():
    client = DualLLMClient(
        local_llm_url="http://localhost:11434/v1",
        local_orchestrator_model="qwen2.5-coder:7b",
        local_worker_model="llama3.2:3b",
        orchestrator_provider="local",
        worker_provider="local",
    )
    assert client.local_url == "http://localhost:11434/v1"
    assert client.local_orchestrator_model == "qwen2.5-coder:7b"
    assert client.local_worker_model == "llama3.2:3b"
    assert client.orchestrator_provider == "local"
    assert client.worker_provider == "local"
    assert client.has_local is True


@pytest.mark.asyncio
async def test_call_local_success():
    client = DualLLMClient(local_llm_url="http://localhost:11434/v1")

    mock_choice = MagicMock()
    mock_choice.message.content = '{"action": "final_answer", "answer": "Hello from local LLM"}'
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    mock_openai = MagicMock()
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch.object(client, "_get_local_client", return_value=mock_openai):
        res = await client._call_local(
            prompt="Test prompt",
            system_prompt="Test system",
            model="qwen2.5-coder:7b",
            json_mode=True,
        )

        assert res == '{"action": "final_answer", "answer": "Hello from local LLM"}'
        mock_openai.chat.completions.create.assert_called_once()
        call_kwargs = mock_openai.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "qwen2.5-coder:7b"
        assert call_kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_call_local_json_retry_on_unsupported_format():
    """If local model does not support response_format json_object, it retries without response_format."""
    client = DualLLMClient(local_llm_url="http://localhost:11434/v1")

    mock_choice = MagicMock()
    mock_choice.message.content = '{"retry": "success"}'
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    mock_openai = MagicMock()
    # First call throws 400 for response_format, second call succeeds
    mock_openai.chat.completions.create = AsyncMock(
        side_effect=[Exception("400 response_format not supported"), mock_completion]
    )

    with patch.object(client, "_get_local_client", return_value=mock_openai):
        res = await client._call_local(
            prompt="Generate JSON",
            system_prompt="System prompt",
            model="qwen2.5-coder:7b",
            json_mode=True,
        )

        assert res == '{"retry": "success"}'
        assert mock_openai.chat.completions.create.call_count == 2


@pytest.mark.asyncio
async def test_run_orchestrator_local_provider():
    """When orchestrator_provider is 'local', it routes to _call_local with the orchestrator model."""
    client = DualLLMClient(
        orchestrator_provider="local",
        local_orchestrator_model="qwen2.5-coder:14b",
    )

    with patch.object(client, "_call_local", new_callable=AsyncMock) as mock_local:
        mock_local.return_value = "Orchestrator answer from Local"

        ans = await client.run_orchestrator("User query", "System instruction")
        assert ans == "Orchestrator answer from Local"
        mock_local.assert_called_once_with(
            "User query",
            "System instruction",
            model="qwen2.5-coder:14b",
            temperature=0.2,
            json_mode=False,
            max_tokens=None,
        )


@pytest.mark.asyncio
async def test_run_orchestrator_local_failover_to_gemini():
    """If local orchestrator fails, it falls back to Gemini if available."""
    client = DualLLMClient(
        gemini_api_key="mock-gemini-key",
        orchestrator_provider="local",
    )

    with patch.object(client, "_call_local", new_callable=AsyncMock, return_value=None):
        with patch.object(client, "_call_gemini", new_callable=AsyncMock, return_value="Gemini fallback answer"):
            ans = await client.run_orchestrator("Query", "System")
            assert ans == "Gemini fallback answer"


@pytest.mark.asyncio
async def test_run_worker_local_provider():
    """When worker_provider is 'local', it routes to _call_local with the worker model."""
    client = DualLLMClient(
        worker_provider="local",
        local_worker_model="qwen2.5-coder:7b",
    )

    with patch.object(client, "_call_local", new_callable=AsyncMock) as mock_local:
        mock_local.return_value = '{"issues": [{"title": "Local Bug Detected"}]}'

        ans = await client.run_worker("Diff text", "Worker system", json_mode=True)
        assert "Local Bug Detected" in ans
        mock_local.assert_called_once_with(
            "Diff text",
            "Worker system",
            model="qwen2.5-coder:7b",
            temperature=0.1,
            json_mode=True,
        )


@pytest.mark.asyncio
async def test_run_worker_local_failover_to_groq():
    """If local worker fails, it falls back to Groq if available."""
    client = DualLLMClient(
        groq_api_key="mock-groq-key",
        worker_provider="local",
    )

    with patch.object(client, "_call_local", new_callable=AsyncMock, return_value=None):
        with patch.object(client, "_call_groq", new_callable=AsyncMock, return_value="Groq fallback review"):
            ans = await client.run_worker("Diff text", "Worker system")
            assert ans == "Groq fallback review"


@pytest.mark.asyncio
async def test_check_local_health_probe():
    client = DualLLMClient(local_llm_url="http://localhost:11434/v1")

    mock_openai = MagicMock()
    mock_openai.models.list = AsyncMock(return_value=[MagicMock()])

    with patch.object(client, "_get_local_client", return_value=mock_openai):
        is_alive = await client.check_local_health()
        assert is_alive is True

    # When probe fails
    mock_openai.models.list = AsyncMock(side_effect=Exception("Connection refused"))
    with patch.object(client, "_get_local_client", return_value=mock_openai):
        is_alive = await client.check_local_health()
        assert is_alive is False


@pytest.mark.asyncio
async def test_agent_loop_uses_local_orchestrator():
    """Verify that AutonomousAgentLoop delegates ReAct JSON turns to local orchestrator."""
    client = DualLLMClient(
        orchestrator_provider="local",
        local_orchestrator_model="qwen2.5-coder:7b",
    )
    agent = AutonomousAgentLoop(llm_client=client)

    decision_json = json.dumps({
        "action": "final_answer",
        "thought": "Synthesizing answer locally",
        "answer": "This is a local agentic response.",
    })

    with patch.object(client, "call_orchestrator_json", new_callable=AsyncMock, return_value=decision_json) as mock_orch:
        res = await agent._call_llm_json("Prompt", "System")
        assert res == decision_json
        mock_orch.assert_called_once_with("Prompt", "System")
