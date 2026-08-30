"""Factory: resolve EMBEDDER env key -> concrete BaseEmbedder instance."""
import logging

from ai_service.vector.embedders.gemini_embedder import GeminiEmbedder
from ai_service.vector.embedders.openai_embedder import OpenAIEmbedder
from ai_service.vector.embedders.fastembed_embedder import FastEmbedEmbedder

logger = logging.getLogger(__name__)

_VALID_EMBEDDERS = ("gemini", "openai", "fastembed")


def get_embedding_function(settings) -> GeminiEmbedder | OpenAIEmbedder | FastEmbedEmbedder:
    """
    Return the appropriate embedder based on settings.embedder.

    Valid values for EMBEDDER:
        gemini    -- Google Gemini (models/gemini-embedding-001, dim=3072)
        openai    -- OpenAI text-embedding-3-* (dim=1536 or 3072)
        fastembed -- Local ONNX via FastEmbed (~130 MB, dim=384)

    Raises:
        ValueError: if EMBEDDER is not a recognised value, or OPENAI_API_KEY
                    is missing when EMBEDDER=openai.
    """
    key = settings.embedder.lower().strip()
    logger.info("Initialising embedder: %s", key)

    match key:
        case "gemini":
            return GeminiEmbedder(
                api_key=settings.gemini_api_key,
                model_name=settings.gemini_embedding_model,
            )
        case "openai":
            return OpenAIEmbedder(
                api_key=settings.openai_api_key,
                model=settings.openai_embedding_model,
            )
        case "fastembed":
            return FastEmbedEmbedder(model_name=settings.fastembed_model)
        case _:
            raise ValueError(
                f"Unknown EMBEDDER='{settings.embedder}'. "
                f"Valid options: {', '.join(_VALID_EMBEDDERS)}"
            )
