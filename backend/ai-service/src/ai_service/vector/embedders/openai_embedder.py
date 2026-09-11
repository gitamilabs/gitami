from typing import List, Dict, Any
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings


class OpenAIEmbedder(EmbeddingFunction):
    """
    Embedding function using OpenAI's text-embedding-3-* models.
    Raises ValueError at construction if api_key is missing.
    Dimensions:
        text-embedding-3-small  -> 1536
        text-embedding-3-large  -> 3072
    """

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY must be set in .env when EMBEDDER=openai. "
                "Add OPENAI_API_KEY=<your-key> to your .env file."
            )
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)
        self.model = model
        self.dimension: int = 3072 if "large" in model else 1536

    def name(self) -> str:
        return "openai"

    def get_config(self) -> Dict[str, Any]:
        return {"model": self.model}

    def __call__(self, input: List[str]) -> List[List[float]]:
        if not input:
            return []
        response = self._client.embeddings.create(model=self.model, input=list(input))
        return [item.embedding for item in response.data]
