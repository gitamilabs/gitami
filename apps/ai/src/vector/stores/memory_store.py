"""In-memory vector store for unit tests — zero external dependencies."""
import math
from typing import List, Optional, Dict, Any


class MemoryStore:
    """
    Pure Python in-memory store.
    Uses brute-force cosine similarity for queries.
    Intended for VECTOR_DB=memory in tests only.
    """

    batch_size: int = 1000

    def __init__(self, embedder):
        self._embedder = embedder
        self._ids: List[str] = []
        self._docs: List[str] = []
        self._metas: List[Dict[str, Any]] = []
        self._embs: List[List[float]] = []

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
        for i, doc_id in enumerate(ids):
            if doc_id in self._ids:
                idx = self._ids.index(doc_id)
                self._docs[idx] = documents[i]
                self._metas[idx] = metadatas[i]
                self._embs[idx] = embeddings[i]
            else:
                self._ids.append(doc_id)
                self._docs.append(documents[i])
                self._metas.append(metadatas[i])
                self._embs.append(embeddings[i])

    def query(
        self,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        q_embs = self._embedder(query_texts)
        all_ids, all_docs, all_metas, all_dists = [], [], [], []
        for q_emb in q_embs:
            scored = []
            for idx, emb in enumerate(self._embs):
                if where and not self._matches(self._metas[idx], where):
                    continue
                scored.append((self._cosine_distance(q_emb, emb), idx))
            scored.sort(key=lambda x: x[0])
            top = scored[:n_results]
            all_ids.append([self._ids[i] for _, i in top])
            all_docs.append([self._docs[i] for _, i in top])
            all_metas.append([self._metas[i] for _, i in top])
            all_dists.append([d for d, _ in top])
        return {"ids": all_ids, "documents": all_docs, "metadatas": all_metas, "distances": all_dists}

    def delete(self, where: Dict[str, Any]) -> None:
        keep = [i for i, m in enumerate(self._metas) if not self._matches(m, where)]
        self._ids    = [self._ids[i]   for i in keep]
        self._docs   = [self._docs[i]  for i in keep]
        self._metas  = [self._metas[i] for i in keep]
        self._embs   = [self._embs[i]  for i in keep]

    def get(
        self,
        where: Dict[str, Any],
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        matches = [i for i, m in enumerate(self._metas) if self._matches(m, where)]
        return {
            "ids":       [self._ids[i]   for i in matches],
            "documents": [self._docs[i]  for i in matches],
            "metadatas": [self._metas[i] for i in matches],
        }

    def update(self, ids: List[str], metadatas: List[Dict[str, Any]]) -> None:
        for doc_id, meta in zip(ids, metadatas):
            if doc_id in self._ids:
                idx = self._ids.index(doc_id)
                self._metas[idx] = meta

    def count(self) -> int:
        """Return total document count in the memory store."""
        return len(self._ids)

    def get_distinct_repos(self) -> List[str]:
        """Return list of unique repositories in the memory store."""
        return sorted(list(set(m["repo"] for m in self._metas if isinstance(m, dict) and "repo" in m and m["repo"])))


    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _cosine_distance(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x ** 2 for x in a)) or 1.0
        mag_b = math.sqrt(sum(x ** 2 for x in b)) or 1.0
        return 1.0 - (dot / (mag_a * mag_b))

    @staticmethod
    def _matches(meta: Dict[str, Any], where: Dict[str, Any]) -> bool:
        """Simple flat equality filter (handles $and lists used by ChromaDB callers)."""
        if "$and" in where:
            return all(MemoryStore._matches(meta, clause) for clause in where["$and"])
        if "$or" in where:
            return any(MemoryStore._matches(meta, clause) for clause in where["$or"])
        for k, v in where.items():
            if isinstance(v, dict):
                op, val = next(iter(v.items()))
                field_val = meta.get(k)
                if op == "$ne" and field_val == val:
                    return False
                if op == "$eq" and field_val != val:
                    return False
            else:
                if meta.get(k) != v:
                    return False
        return True
