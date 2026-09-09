"""Supabase pgvector store backend using supabase-py."""
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class SupabaseStore:
    """
    Vector store backed by Supabase with the pgvector extension.
    Requires SUPABASE_URL and SUPABASE_SERVICE_KEY in settings.

    Prerequisites (one-time SQL setup — see supabase_migration.sql):
        1. Enable the vector extension: CREATE EXTENSION IF NOT EXISTS vector;
        2. Create the knowledge_base table with a vector column.
        3. Create the match_documents() RPC function for similarity search.

    Dimension validation: checked via table column metadata on init.
    """

    def __init__(self, settings, embedder):
        from supabase import create_client

        self.batch_size: int = settings.supabase_batch_size
        self._embedder = embedder
        self._table = settings.supabase_table

        self._client = create_client(settings.supabase_url, settings.supabase_service_key)
        logger.info(
            "SupabaseStore: connected to %s, table=%s", settings.supabase_url, self._table
        )

        # Warn about dimension mismatch (cannot recreate — Supabase DDL requires migration)
        self._check_dimension()

    def _check_dimension(self) -> None:
        """Log a warning if the table's vector column dimension differs from the embedder."""
        try:
            result = (
                self._client.rpc(
                    "get_vector_dimension",
                    {"table_name": self._table},
                ).execute()
            )
            stored_dim = result.data
            if stored_dim is not None:
                dim_int = int(stored_dim)
                if dim_int != self._embedder.dimension and dim_int != (self._embedder.dimension - 4):
                    logger.warning(
                        "SupabaseStore: stored vector dimension %s != embedder dimension %d. "
                        "Run supabase_migration.sql to recreate the table with the correct dimension.",
                        stored_dim,
                        self._embedder.dimension,
                    )

        except Exception as exc:
            logger.debug("SupabaseStore: could not check vector dimension: %s", exc)

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

        rows = [
            {
                "id": doc_id,
                "content": doc,
                "embedding": emb,
                "metadata": meta,
            }
            for doc_id, doc, meta, emb in zip(ids, documents, metadatas, embeddings)
        ]
        for i in range(0, len(rows), self.batch_size):
            (
                self._client.table(self._table)
                .upsert(rows[i:i + self.batch_size], on_conflict="id")
                .execute()
            )

    def query(
        self,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        q_embs = self._embedder(query_texts)
        filter_json = self._build_filter(where) if where else {}

        all_ids, all_docs, all_metas, all_dists = [], [], [], []
        for q_emb in q_embs:
            result = self._client.rpc(
                "match_documents",
                {
                    "query_embedding": q_emb,
                    "match_count": n_results,
                    "filter": filter_json,
                    "table_name": self._table,
                },
            ).execute()

            batch_ids, batch_docs, batch_metas, batch_dists = [], [], [], []
            for row in (result.data or []):
                batch_ids.append(row["id"])
                batch_docs.append(row.get("content", ""))
                batch_metas.append(row.get("metadata", {}))
                batch_dists.append(1.0 - row.get("similarity", 0.0))
            all_ids.append(batch_ids)
            all_docs.append(batch_docs)
            all_metas.append(batch_metas)
            all_dists.append(batch_dists)

        return {"ids": all_ids, "documents": all_docs, "metadatas": all_metas, "distances": all_dists}

    def delete(self, where: Dict[str, Any]) -> None:
        def _has_complex_ops(w: Any) -> bool:
            if isinstance(w, dict):
                for k, v in w.items():
                    if k.startswith("$") and k not in ("$and", "$or", "$eq"):
                        return True
                    if isinstance(v, dict) and any(sub_k.startswith("$") and sub_k != "$eq" for sub_k in v):
                        return True
                    if _has_complex_ops(v):
                        return True
            elif isinstance(w, list):
                for item in w:
                    if _has_complex_ops(item):
                        return True
            return False

        if _has_complex_ops(where):
            # Complex filter (e.g. $ne in delete_stale_entries)
            eq_filter = self._build_filter(where)
            docs = self.get(where=eq_filter)
            from src.vector.stores.memory_store import MemoryStore
            matching_ids = [
                doc_id
                for doc_id, meta in zip(docs["ids"], docs["metadatas"])
                if MemoryStore._matches(meta, where)
            ]
            if matching_ids:
                for i in range(0, len(matching_ids), self.batch_size):
                    batch = matching_ids[i:i + self.batch_size]
                    self._client.table(self._table).delete().in_("id", batch).execute()
        else:
            filter_json = self._build_filter(where)
            self._client.rpc(
                "delete_documents",
                {"filter": filter_json, "table_name": self._table},
            ).execute()


    def get(
        self,
        where: Dict[str, Any],
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        filter_json = self._build_filter(where)
        result = self._client.rpc(
            "get_documents",
            {"filter": filter_json, "table_name": self._table},
        ).execute()
        ids, docs, metas = [], [], []
        for row in (result.data or []):
            ids.append(row["id"])
            docs.append(row.get("content", ""))
            metas.append(row.get("metadata", {}))
        return {"ids": ids, "documents": docs, "metadatas": metas}

    def update(self, ids: List[str], metadatas: List[Dict[str, Any]]) -> None:
        for doc_id, meta in zip(ids, metadatas):
            (
                self._client.table(self._table)
                .update({"metadata": meta})
                .eq("id", doc_id)
                .execute()
            )

    def count(self) -> int:
        """Return the exact total document count in the Supabase knowledge_base table."""
        try:
            res = (
                self._client.table(self._table)
                .select("id", count="exact", head=True)
                .execute()
            )
            return res.count if res.count is not None else 0
        except Exception as exc:
            logger.warning("SupabaseStore: could not get count: %s", exc)
            return 0

    def get_distinct_repos(self) -> List[str]:
        """Fetch distinct repository identifiers indexed in Supabase."""
        try:
            # Check if custom RPC function exists
            res = self._client.rpc("get_distinct_repos", {"table_name": self._table}).execute()
            if res.data and isinstance(res.data, list):
                repos = set()
                for item in res.data:
                    if isinstance(item, str):
                        repos.add(item)
                    elif isinstance(item, dict) and "repo" in item:
                        repos.add(item["repo"])
                if repos:
                    return sorted(list(repos))
        except Exception:
            pass

        # Fallback: scan metadata column
        try:
            res = self._client.table(self._table).select("metadata").limit(10000).execute()
            repos = set()
            for row in (res.data or []):
                meta = row.get("metadata") or {}
                if isinstance(meta, dict) and "repo" in meta and meta["repo"]:
                    repos.add(meta["repo"])
            return sorted(list(repos))
        except Exception as exc:
            logger.warning("SupabaseStore: could not fetch distinct repos: %s", exc)
            return []


    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _build_filter(where: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert ChromaDB-style where dict to a JSON object that the
        match_documents / delete_documents Postgres RPCs can filter on
        via jsonb containment (@>).
        """
        if not where:
            return {}
        if "$and" in where:
            merged: Dict[str, Any] = {}
            for clause in where["$and"]:
                merged.update(SupabaseStore._build_filter(clause))
            return merged
        # Flat equality filter — pgvector RPCs use jsonb @> operator
        result: Dict[str, Any] = {}
        for k, v in where.items():
            if isinstance(v, dict):
                # Only equality is supported via jsonb containment
                op, val = next(iter(v.items()))
                if op in ("$eq",):
                    result[k] = val
            else:
                result[k] = v
        return result
