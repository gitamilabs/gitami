from typing import List, Dict, Any
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings


class FastEmbedEmbedder(EmbeddingFunction):
    """
    Local ONNX-based embedding using the fastembed library (by Qdrant).
    Default model: BAAI/bge-small-en-v1.5 (~130 MB download on first use).
    Dimension: 384.

    Advantages over sentence-transformers/BGE-M3:
        - No PyTorch dependency
        - ~130 MB vs ~1 GB for BGE-M3
        - No GPU required
        - Fast CPU inference via ONNX Runtime
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        from fastembed import TextEmbedding
        self._model = TextEmbedding(model_name=model_name)
        self.model_name = model_name
        # bge-small-en-v1.5 dim=384; bge-base-en-v1.5 dim=768
        dim_map = {
            "BAAI/bge-small-en-v1.5": 384,
            "BAAI/bge-base-en-v1.5": 768,
            "BAAI/bge-large-en-v1.5": 1024,
            "snowflake/snowflake-arctic-embed-xs": 384,
        }
        self.dimension: int = dim_map.get(model_name, 384)

    def name(self) -> str:
        return "fastembed"

    def get_config(self) -> Dict[str, Any]:
        return {"model_name": self.model_name}

    def __call__(self, input: List[str]) -> List[List[float]]:
        if not input:
            return []
        return [emb.tolist() for emb in self._model.embed(list(input))]
