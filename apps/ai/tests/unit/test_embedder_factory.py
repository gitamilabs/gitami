"""Unit tests for the embedder factory."""
import pytest
from unittest.mock import patch, MagicMock


class MockSettings:
    embedder = "gemini"
    gemini_api_key = "test-key"
    gemini_embedding_model = "models/gemini-embedding-001"
    openai_api_key = "sk-test"
    openai_embedding_model = "text-embedding-3-small"
    fastembed_model = "BAAI/bge-small-en-v1.5"


def test_factory_returns_gemini():
    from src.vector.embedders.gemini_embedder import GeminiEmbedder
    from src.vector.embedders.factory import get_embedding_function

    s = MockSettings()
    s.embedder = "gemini"
    with patch("src.vector.embedders.gemini_embedder.GeminiEmbedder.__init__", return_value=None):
        embedder = get_embedding_function(s)
    assert isinstance(embedder, GeminiEmbedder)


def test_factory_returns_openai():
    from src.vector.embedders.openai_embedder import OpenAIEmbedder
    from src.vector.embedders.factory import get_embedding_function

    s = MockSettings()
    s.embedder = "openai"
    with patch("openai.OpenAI", MagicMock(), create=True):
        embedder = get_embedding_function(s)
    assert isinstance(embedder, OpenAIEmbedder)


def test_factory_returns_fastembed():
    from src.vector.embedders.fastembed_embedder import FastEmbedEmbedder
    from src.vector.embedders.factory import get_embedding_function

    s = MockSettings()
    s.embedder = "fastembed"
    mock_te = MagicMock()
    with patch.dict("sys.modules", {"fastembed": MagicMock(TextEmbedding=mock_te)}):
        embedder = get_embedding_function(s)
    assert isinstance(embedder, FastEmbedEmbedder)


def test_factory_raises_on_unknown_embedder():
    from src.vector.embedders.factory import get_embedding_function

    s = MockSettings()
    s.embedder = "not_a_real_embedder"
    with pytest.raises(ValueError, match="Unknown EMBEDDER"):
        get_embedding_function(s)


def test_openai_raises_without_api_key():
    from src.vector.embedders.openai_embedder import OpenAIEmbedder

    with pytest.raises(ValueError, match="OPENAI_API_KEY must be set"):
        OpenAIEmbedder(api_key="", model="text-embedding-3-small")


def test_openai_dimension_small():
    with patch("openai.OpenAI", MagicMock(), create=True):
        from src.vector.embedders.openai_embedder import OpenAIEmbedder
        e = OpenAIEmbedder(api_key="sk-test", model="text-embedding-3-small")
        assert e.dimension == 1536


def test_openai_dimension_large():
    with patch("openai.OpenAI", MagicMock(), create=True):
        from src.vector.embedders.openai_embedder import OpenAIEmbedder
        e = OpenAIEmbedder(api_key="sk-test", model="text-embedding-3-large")
        assert e.dimension == 3072

