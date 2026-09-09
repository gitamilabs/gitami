"""Gemini embedding model implementation using google-genai SDK."""
import time
from typing import List, Dict, Any

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings


class GeminiEmbedder(EmbeddingFunction):
    """
    Embedding function using Google's google-genai SDK.
    Implements exponential backoff on rate-limit errors (429 / RESOURCE_EXHAUSTED).
    Dimension: 3072 for models/gemini-embedding-001.
    """

    dimension: int = 3072

    def __init__(self, api_key: str, model_name: str = "models/gemini-embedding-001"):
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def name(self) -> str:
        return "gemini_embedder"

    def get_config(self) -> Dict[str, Any]:
        return {"model_name": self.model_name}

    def __call__(self, input: Documents) -> Embeddings:
        if not input:
            return []

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self._client.models.embed_content(
                    model=self.model_name,
                    contents=list(input),
                )
                return [emb.values for emb in response.embeddings]
            except Exception as e:
                err_str = str(e)
                if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str) and attempt < max_retries - 1:
                    time.sleep(4 * (attempt + 1))
                    continue

                # Batch failed -- fall back to per-document embedding
                embeddings = []
                for doc in input:
                    try:
                        res = self._client.models.embed_content(
                            model=self.model_name,
                            contents=doc,
                        )
                        embeddings.append(res.embeddings[0].values)
                    except Exception:
                        embeddings.append([0.0] * self.dimension)
                return embeddings

        return [[0.0] * self.dimension for _ in input]
