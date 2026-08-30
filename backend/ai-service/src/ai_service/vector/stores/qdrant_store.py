"""Qdrant vector store backend."""
import logging
import uuid
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class QdrantStore:
    """
    Vector store backed by Qdrant (cloud or self-hosted).
    Requires QDRANT_URL and QDRANT_API_KEY in settings.
    Uses qdrant-client library.
    """

    def __init__(self, settings, embedder):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        self.batch_size: int = settings.qdrant_batch_size
        self._embedder = embedder
        self._collection = settings.qdrant_collection

        self._client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
        logger.info("QdrantStore: connected to %s, collection=%s", settings.qdrant_url, self._collection)

        # Ensure collection exists with correct dimensionality
        existing = [c.name for c in self._client.get_collections().collections]
        if self._collection not in existing:
            logger.info("QdrantStore: creating collection '%s' (dim=%d)", self._collection, embedder.dimension)
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=embedder.dimension, distance=Distance.COSINE),
            )
        else:
            # Validate dimension
            info = self._client.get_collection(self._collection)
            stored_dim = info.config.params.vectors.size
            if stored_dim != embedder.dimension:
                logger.warning(
                    "QdrantStore: stored dimension %d != embedder dimension %d. "
                    "Recreating collection '%s'. Previous data will be lost.",
                    stored_dim, embedder.dimension, self._collection,
                )
                self._client.recreate_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(size=embedder.dimension, distance=Distance.COSINE),
                )

    # ── BaseVectorStore interface ─────────────────────────────────────────────

    def upsert(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None,
    ) -> None:
        from qdrant_client.models import PointStruct

        if embeddings is None:
            embeddings = self._embedder(documents)

        points = [
            PointStruct(
                id=self._str_to_uuid(doc_id),
                vector=emb,
                payload={**meta, "_doc_id": doc_id, "_document": doc},
            )
            for doc_id, doc, meta, emb in zip(ids, documents, metadatas, embeddings)
        ]
        self._client.upsert(collection_name=self._collection, points=points)

    def query(
        self,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        q_embs = self._embedder(query_texts)
        qdrant_filter = self._build_filter(where) if where else None

        all_ids, all_docs, all_metas, all_dists = [], [], [], []
        for q_emb in q_embs:
            results = self._client.search(
                collection_name=self._collection,
                query_vector=q_emb,
                limit=n_results,
                query_filter=qdrant_filter,
                with_payload=True,
            )
            batch_ids, batch_docs, batch_metas, batch_dists = [], [], [], []
            for hit in results:
                payload = hit.payload or {}
                batch_ids.append(payload.get("_doc_id", str(hit.id)))
                batch_docs.append(payload.get("_document", ""))
                meta = {k: v for k, v in payload.items() if not k.startswith("_")}
                batch_metas.append(meta)
                batch_dists.append(1.0 - hit.score)  # cosine distance
            all_ids.append(batch_ids)
            all_docs.append(batch_docs)
            all_metas.append(batch_metas)
            all_dists.append(batch_dists)

        return {"ids": all_ids, "documents": all_docs, "metadatas": all_metas, "distances": all_dists}

    def delete(self, where: Dict[str, Any]) -> None:
        from qdrant_client.models import FilterSelector
        qdrant_filter = self._build_filter(where)
        if qdrant_filter:
            self._client.delete(
                collection_name=self._collection,
                points_selector=FilterSelector(filter=qdrant_filter),
            )

    def get(
        self,
        where: Dict[str, Any],
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        from qdrant_client.models import Filter
        qdrant_filter = self._build_filter(where)
        results, _ = self._client.scroll(
            collection_name=self._collection,
            scroll_filter=qdrant_filter,
            with_payload=True,
            limit=10_000,
        )
        ids, docs, metas = [], [], []
        for hit in results:
            payload = hit.payload or {}
            ids.append(payload.get("_doc_id", str(hit.id)))
            docs.append(payload.get("_document", ""))
            metas.append({k: v for k, v in payload.items() if not k.startswith("_")})
        return {"ids": ids, "documents": docs, "metadatas": metas}

    def update(self, ids: List[str], metadatas: List[Dict[str, Any]]) -> None:
        from qdrant_client.models import SetPayload
        for doc_id, meta in zip(ids, metadatas):
            self._client.set_payload(
                collection_name=self._collection,
                payload=meta,
                points=[self._str_to_uuid(doc_id)],
            )

    def count(self) -> int:
        """Return total document count in the Qdrant collection."""
        try:
            return self._client.count(collection_name=self._collection).count
        except Exception:
            return 0

    def get_distinct_repos(self) -> List[str]:
        """Return list of unique repositories in the Qdrant collection."""
        try:
            results, _ = self._client.scroll(
                collection_name=self._collection,
                with_payload=True,
                limit=10_000,
            )
            repos = set()
            for hit in results:
                payload = hit.payload or {}
                if "repo" in payload and payload["repo"]:
                    repos.add(payload["repo"])
            return sorted(list(repos))
        except Exception:
            return []


    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _str_to_uuid(s: str) -> str:
        """Convert arbitrary string ID to a deterministic UUID string for Qdrant."""
        return str(uuid.uuid5(uuid.NAMESPACE_URL, s))

    @staticmethod
    def _build_filter(where: Optional[Dict[str, Any]]):
        """Convert ChromaDB-style where dict to a qdrant_client Filter object."""
        if not where:
            return None
        from qdrant_client.models import Filter, FieldCondition, MatchValue, IsNotNullCondition

        def _condition(key: str, value: Any):
            if isinstance(value, dict):
                op, val = next(iter(value.items()))
                if op == "$ne":
                    # Qdrant: must NOT match
                    return Filter(must_not=[FieldCondition(key=key, match=MatchValue(value=val))])
                elif op == "$eq":
                    return FieldCondition(key=key, match=MatchValue(value=val))
            return FieldCondition(key=key, match=MatchValue(value=value))

        if "$and" in where:
            must = []
            for clause in where["$and"]:
                for k, v in clause.items():
                    must.append(_condition(k, v))
            return Filter(must=must)
        if "$or" in where:
            should = []
            for clause in where["$or"]:
                for k, v in clause.items():
                    should.append(_condition(k, v))
            return Filter(should=should)

        must = [_condition(k, v) for k, v in where.items()]
        return Filter(must=must) if must else None
