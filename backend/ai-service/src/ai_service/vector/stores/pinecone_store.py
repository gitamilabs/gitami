"""Pinecone vector store backend."""
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class PineconeStore:
    """
    Vector store backed by Pinecone serverless index.
    Requires PINECONE_API_KEY and PINECONE_INDEX in settings.
    Uses pinecone-client library.
    """

    def __init__(self, settings, embedder):
        from pinecone import Pinecone, ServerlessSpec

        self.batch_size: int = settings.pinecone_batch_size
        self._embedder = embedder
        self._index_name = settings.pinecone_index

        pc = Pinecone(api_key=settings.pinecone_api_key)

        existing = [idx.name for idx in pc.list_indexes()]
        if self._index_name not in existing:
            logger.info(
                "PineconeStore: creating index '%s' (dim=%d, env=%s)",
                self._index_name, embedder.dimension, settings.pinecone_environment,
            )
            pc.create_index(
                name=self._index_name,
                dimension=embedder.dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region=settings.pinecone_environment or "us-east-1"),
            )
        else:
            # Validate dimension
            desc = pc.describe_index(self._index_name)
            stored_dim = desc.dimension
            if stored_dim != embedder.dimension:
                logger.warning(
                    "PineconeStore: stored dimension %d != embedder dimension %d for index '%s'. "
                    "Delete the index manually and restart to recreate it.",
                    stored_dim, embedder.dimension, self._index_name,
                )

        self._index = pc.Index(self._index_name)
        logger.info("PineconeStore: connected to index '%s'", self._index_name)

    # ── BaseVectorStore interface ─────────────────────────────────────────────

    def upsert(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None,
    ) -> None:
        if embeddings is None:
            embeddings = self._embedder(documents)

        vectors = [
            {
                "id": doc_id,
                "values": emb,
                "metadata": {**meta, "_document": doc},
            }
            for doc_id, doc, meta, emb in zip(ids, documents, metadatas, embeddings)
        ]
        # Pinecone recommends batches <= 100 vectors
        for i in range(0, len(vectors), self.batch_size):
            self._index.upsert(vectors=vectors[i:i + self.batch_size])

    def query(
        self,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        q_embs = self._embedder(query_texts)
        pinecone_filter = self._build_filter(where) if where else None

        all_ids, all_docs, all_metas, all_dists = [], [], [], []
        for q_emb in q_embs:
            kwargs: Dict[str, Any] = dict(
                vector=q_emb, top_k=n_results, include_metadata=True
            )
            if pinecone_filter:
                kwargs["filter"] = pinecone_filter
            response = self._index.query(**kwargs)

            batch_ids, batch_docs, batch_metas, batch_dists = [], [], [], []
            for match in response.matches:
                meta = match.metadata or {}
                batch_ids.append(match.id)
                batch_docs.append(meta.pop("_document", ""))
                batch_metas.append(meta)
                batch_dists.append(1.0 - match.score)  # cosine distance
            all_ids.append(batch_ids)
            all_docs.append(batch_docs)
            all_metas.append(batch_metas)
            all_dists.append(batch_dists)

        return {"ids": all_ids, "documents": all_docs, "metadatas": all_metas, "distances": all_dists}

    def delete(self, where: Dict[str, Any]) -> None:
        pinecone_filter = self._build_filter(where)
        if pinecone_filter:
            self._index.delete(filter=pinecone_filter)

    def get(
        self,
        where: Dict[str, Any],
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        # Pinecone does not support arbitrary metadata-only fetches without a vector;
        # fall back to a zero-vector query with a large top_k.
        logger.debug("PineconeStore.get() uses zero-vector query (Pinecone limitation)")
        zero = [0.0] * self._embedder.dimension
        pinecone_filter = self._build_filter(where)
        kwargs: Dict[str, Any] = dict(vector=zero, top_k=1000, include_metadata=True)
        if pinecone_filter:
            kwargs["filter"] = pinecone_filter
        response = self._index.query(**kwargs)
        ids, docs, metas = [], [], []
        for match in response.matches:
            meta = match.metadata or {}
            ids.append(match.id)
            docs.append(meta.pop("_document", ""))
            metas.append(meta)
        return {"ids": ids, "documents": docs, "metadatas": metas}

    def update(self, ids: List[str], metadatas: List[Dict[str, Any]]) -> None:
        for doc_id, meta in zip(ids, metadatas):
            self._index.update(id=doc_id, set_metadata=meta)

    def count(self) -> int:
        """Return total document count in the Pinecone index."""
        try:
            stats = self._index.describe_index_stats()
            return stats.total_vector_count or 0
        except Exception:
            return 0

    def get_distinct_repos(self) -> List[str]:
        """Return list of unique repositories in the Pinecone index."""
        # Pinecone does not support scanning across all metadata keys without a query
        return []


    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _build_filter(where: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Convert ChromaDB-style where dict to Pinecone metadata filter."""
        if not where:
            return None
        if "$and" in where:
            return {"$and": [PineconeStore._build_filter(c) for c in where["$and"]]}
        if "$or" in where:
            return {"$or": [PineconeStore._build_filter(c) for c in where["$or"]]}
        result = {}
        for k, v in where.items():
            if isinstance(v, dict):
                op, val = next(iter(v.items()))
                pinecone_op = {"$ne": "$ne", "$eq": "$eq"}.get(op, op)
                result[k] = {pinecone_op: val}
            else:
                result[k] = {"$eq": v}
        return result
