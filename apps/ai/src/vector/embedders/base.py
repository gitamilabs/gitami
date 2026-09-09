"""BaseEmbedder protocol shared by all concrete embedding implementations."""
from typing import Protocol, List, runtime_checkable


@runtime_checkable
class BaseEmbedder(Protocol):
    """Protocol that all embedder implementations must satisfy."""

    dimension: int
    """Output vector dimensionality (e.g. 3072 for Gemini, 1536 for OpenAI small, 384 for FastEmbed)."""

    def __call__(self, input: List[str]) -> List[List[float]]:
        """Embed a batch of text strings and return a list of float vectors."""
        ...
