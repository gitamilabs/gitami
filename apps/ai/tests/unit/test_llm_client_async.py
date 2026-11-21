import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from src.agents.llm_client import DualLLMClient, GEMINI_MODELS, GROQ_MODELS
from src.context import get_governed_engine, ContextEngine, ContextRequest
from src.web.app import app


# ── 1. Model Harmonization Verification ─────────────────────────────────────

def test_gemini_models_harmonization():
    """Verify hallucinated/non-existent Gemini models are removed and official models are present."""
    # Disallowed hallucinated models
    disallowed = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash"]
    for model in disallowed:
        assert model not in GEMINI_MODELS, f"Disallowed model {model} found in GEMINI_MODELS"

    # Official production models
    assert "gemini-2.5-flash" in GEMINI_MODELS
    assert "gemini-2.0-flash" in GEMINI_MODELS


def test_groq_models_harmonization():
    """Verify hallucinated Groq models are removed and official models are present."""
    disallowed = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.6-27b",
        "qwen/qwen3.8-27b",
    ]
    for model in disallowed:
        assert model not in GROQ_MODELS, f"Disallowed model {model} found in GROQ_MODELS"

    assert "llama-3.3-70b-versatile" in GROQ_MODELS
    assert "llama-3.1-8b-instant" in GROQ_MODELS


def test_get_default_model():
    """Verify DualLLMClient.get_default_model returns production identifiers."""
    assert DualLLMClient.get_default_model("gemini") == "gemini-2.5-flash"
    assert DualLLMClient.get_default_model("groq") == "llama-3.3-70b-versatile"


# ── 2. Async Google GenAI Client & _call_gemini ─────────────────────────────

@pytest.mark.asyncio
async def test_call_gemini_invokes_async_aio_generate_content():
    """_call_gemini invokes asynchronous client.aio.models.generate_content."""
    client = DualLLMClient(gemini_api_key="test-gemini-key")

    mock_response = MagicMock()
    mock_response.text = "Async response from Gemini 2.5"

    mock_genai_client = MagicMock()
    mock_genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch.object(client, "_get_genai_client", return_value=mock_genai_client):
        res = await client._call_gemini(
            prompt="What is this function?",
            system_prompt="You are a code analyzer",
            models=["gemini-2.5-flash"],
            json_mode=False,
        )

        assert res == "Async response from Gemini 2.5"
        mock_genai_client.aio.models.generate_content.assert_awaited_once_with(
            model="gemini-2.5-flash",
            contents="You are a code analyzer\n\nWhat is this function?",
        )


@pytest.mark.asyncio
async def test_call_gemini_json_mode_and_model_fallback():
    """_call_gemini configures json mode and falls back through models on failure."""
    client = DualLLMClient(gemini_api_key="test-gemini-key")

    mock_response = MagicMock()
    mock_response.text = '{"status": "ok"}'

    mock_genai_client = MagicMock()
    # First model raises error, second succeeds
    mock_genai_client.aio.models.generate_content = AsyncMock(
        side_effect=[Exception("404 model not found"), mock_response]
    )

    with patch.object(client, "_get_genai_client", return_value=mock_genai_client):
        res = await client._call_gemini(
            prompt="Return JSON",
            system_prompt="System instructions",
            models=["gemini-2.5-flash", "gemini-2.0-flash"],
            json_mode=True,
        )

        assert res == '{"status": "ok"}'
        assert mock_genai_client.aio.models.generate_content.await_count == 2
        call_kwargs = mock_genai_client.aio.models.generate_content.call_args_list[0][1]
        assert call_kwargs["config"] == {"response_mime_type": "application/json"}


# ── 3. Async Groq Client & _call_groq ───────────────────────────────────────

@pytest.mark.asyncio
async def test_call_groq_uses_async_groq_and_awaits():
    """_call_groq uses AsyncGroq and awaits client.chat.completions.create."""
    client = DualLLMClient(groq_api_key="test-groq-key")

    mock_choice = MagicMock()
    mock_choice.message.content = "Async response from Llama 3.3"
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch.object(client, "_get_groq_client", return_value=mock_groq_client):
        res = await client._call_groq(
            prompt="Review this code",
            system_prompt="You are a reviewer",
            models=["llama-3.3-70b-versatile"],
            temperature=0.3,
            json_mode=False,
        )

        assert res == "Async response from Llama 3.3"
        mock_groq_client.chat.completions.create.assert_awaited_once_with(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a reviewer"},
                {"role": "user", "content": "Review this code"},
            ],
            temperature=0.3,
        )


@pytest.mark.asyncio
async def test_call_groq_json_mode_and_fallback():
    """_call_groq passes json_object response_format and falls back on exception."""
    client = DualLLMClient(groq_api_key="test-groq-key")

    mock_choice = MagicMock()
    mock_choice.message.content = '{"result": "success"}'
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create = AsyncMock(
        side_effect=[Exception("503 Rate limit"), mock_completion]
    )

    with patch.object(client, "_get_groq_client", return_value=mock_groq_client):
        res = await client._call_groq(
            prompt="Analyze JSON",
            system_prompt="System",
            models=["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
            json_mode=True,
        )

        assert res == '{"result": "success"}'
        assert mock_groq_client.chat.completions.create.await_count == 2
        first_call_kwargs = mock_groq_client.chat.completions.create.call_args_list[0][1]
        assert first_call_kwargs["response_format"] == {"type": "json_object"}


# ── 4. Canonical get_governed_engine Factory ─────────────────────────────────

@pytest.mark.asyncio
async def test_get_governed_engine_factory():
    """get_governed_engine constructs authorized ContextEngine scoped to repo_id."""
    mock_graph = MagicMock()
    mock_vector = MagicMock()

    engine = get_governed_engine(
        repo_id="owner/repo",
        graph_client=mock_graph,
        vector_client=mock_vector,
    )

    assert isinstance(engine, ContextEngine)
    assert engine.graph_client is mock_graph
    assert engine.vector_client is mock_vector
    assert engine.authorizer is not None
    # Verify StaticAuthResolver scoping
    scope_map = engine.authorizer._resolver._project_repos
    assert "owner/repo" in scope_map
    assert "owner/repo" in scope_map["owner/repo"]

    # Verify authorization check passes for the repo
    scope = await engine.authorizer.authorize(ContextRequest(project_id="owner/repo", query="test"))
    assert "owner/repo" in scope.allowed_repo_ids


# ── 5. Chat Route Hermetic Async Unblocking Tests ────────────────────────────

def test_chat_query_endpoint_hermetic():
    """Verify /api/chat works asynchronously without event loop blocking."""
    test_client = TestClient(app)

    with patch("src.web.routes.chat.get_shared_graph_client", new_callable=AsyncMock) as mock_gc, \
         patch("src.web.routes.chat.get_shared_vector_client") as mock_vc, \
         patch("src.web.routes.chat.DualLLMClient") as mock_llm_cls:

        mock_llm_instance = MagicMock()
        mock_llm_instance.plan_tool_calls = AsyncMock(return_value=[
            {"tool_name": "retrieve_context", "args": {"query": "how to auth"}}
        ])
        mock_llm_instance.run_orchestrator = AsyncMock(return_value="Synthesized answer [1]")
        mock_llm_cls.return_value = mock_llm_instance

        mock_gc.return_value = MagicMock()
        mock_vc.return_value = MagicMock()

        from src.context.contracts import ContextResult, ContextItem, ContextItemType, ContextSource, RetrievalMetadata

        with patch("src.web.routes.chat.get_governed_engine") as mock_get_engine:
            mock_engine = MagicMock()
            real_result = ContextResult(
                query="how to auth",
                project_id="test/repo",
                items=[
                    ContextItem(
                        id="c1",
                        type=ContextItemType.SYMBOL,
                        source=ContextSource(
                            kind="graph",
                            repository_id="test/repo",
                            file_path="auth.py",
                            start_line=10,
                            end_line=20,
                        ),
                        title="login",
                        content="def login(): pass",
                        relevance_score=0.95,
                        metadata={"symbol": "login"},
                    )
                ],
                sources=[],
                total_candidates=1,
                returned_items=1,
                truncated=False,
                retrieval_metadata=RetrievalMetadata(),
            )
            mock_engine.retrieve = AsyncMock(return_value=real_result)
            mock_get_engine.return_value = mock_engine

            resp = test_client.post("/api/chat", json={
                "repo_id": "test/repo",
                "message": "how does login work?"
            })

            assert resp.status_code == 200
            data = resp.json()
            assert data["answer"] == "Synthesized answer [1]"
            assert len(data["citations"]) >= 1
            assert data["citations"][0]["file_path"] == "auth.py"
            assert len(data["tool_steps"]) >= 1
            mock_get_engine.assert_called()


def test_chat_stream_endpoint_hermetic():
    """Verify /api/chat/stream streams events without event loop deadlock."""
    test_client = TestClient(app)

    with patch("src.web.routes.chat.get_shared_graph_client", new_callable=AsyncMock) as mock_gc, \
         patch("src.web.routes.chat.get_shared_vector_client") as mock_vc, \
         patch("src.web.routes.chat.DualLLMClient") as mock_llm_cls:

        mock_llm_instance = MagicMock()
        mock_llm_cls.return_value = mock_llm_instance

        mock_gc.return_value = MagicMock()
        mock_vc.return_value = MagicMock()

        with patch("src.web.routes.chat.AutonomousAgentLoop.run_stream") as mock_run_stream:
            async def fake_stream(*args, **kwargs):
                yield 'data: {"type": "thought", "content": "thinking"}\n\n'
                yield 'data: {"type": "done", "total_latency_ms": 100}\n\n'

            mock_run_stream.side_effect = fake_stream

            resp = test_client.post("/api/chat/stream", json={
                "repo_id": "test/repo",
                "message": "stream check"
            })

            assert resp.status_code == 200
            content = resp.text
            assert 'data: {"type": "thought", "content": "thinking"}' in content
            assert 'data: {"type": "done", "total_latency_ms": 100}' in content
