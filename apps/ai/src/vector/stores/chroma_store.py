"""ChromaDB vector store — supports both local persistent and cloud-hosted modes."""
import logging
from typing import List, Optional, Dict, Any

import chromadb

logger = logging.getLogger(__name__)


class ChromaStore:
    """
    Wraps a ChromaDB collection (local PersistentClient or CloudClient).
    Auto-selects cloud mode when chroma_api_key / chroma_tenant / chroma_database
    are all present in settings; falls back to local otherwise.

    Validates embedding dimension at construction time to catch model-switch
    mismatches early (logs a WARNING and recreates the collection if needed).
    """

    def __init__(self, settings, embedder):
        self.batch_size: int = settings.chroma_batch_size
        self._embedder = embedder

        # ── Choose client ─────────────────────────────────────────────────────
        if settings.chroma_api_key and settings.chroma_tenant and settings.chroma_database:
            logger.info("ChromaStore: using CloudClient (tenant=%s)", settings.chroma_tenant)
            self._client = chromadb.CloudClient(
                tenant=settings.chroma_tenant,
                database=settings.chroma_database,
                api_key=settings.chroma_api_key,
            )
        else:
            path = settings.chroma_persist_dir
            logger.info("ChromaStore: using PersistentClient (path=%s)", path)
            self._client = chromadb.PersistentClient(path=path)

        # ── Get or create collection ──────────────────────────────────────────
        self._collection = self._get_or_create_collection()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_or_create_collection(self):
        """Create the collection, recreating it if the stored dimension mismatches."""
        try:
            col = self._client.get_or_create_collection(
                name="knowledge_base",
                embedding_function=self._embedder,
            )
            # Dimension validation: probe with a tiny dummy doc
            self._validate_dimension(col)
            return col
        except ValueError:
            # Conflicting embedding function on disk — recreate
            logger.warning(
                "ChromaStore: collection embedding mismatch detected. Recreating collection."
            )
            return self._recreate_collection()

    def _validate_dimension(self, col):
        """
        Check that the stored embeddings match the current embedder dimension.
        If not, log a warning and recreate the collection.
        """
        try:
            probe = col.get(limit=1, include=["embeddings"])
            stored_embeddings = probe.get("embeddings") or []
            if stored_embeddings and len(stored_embeddings[0]) != self._embedder.dimension:
                logger.warning(
                    "ChromaStore: stored embedding dimension %d does not match "
                    "current embedder dimension %d. Recreating collection to avoid "
                    "query errors. Previous data will be lost.",
                    len(stored_embeddings[0]),
                    self._embedder.dimension,
                )
                self._collection = self._recreate_collection()
        except Exception:
            pass  # Collection may be empty; skip validation

    def _recreate_collection(self):
        try:
            self._client.delete_collection(name="knowledge_base")
        except Exception:
            pass
        return self._client.create_collection(
            name="knowledge_base",
            embedding_function=self._embedder,
        )

    # ── BaseVectorStore interface ─────────────────────────────────────────────

    def upsert(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None,
    ) -> None:
        kwargs: Dict[str, Any] = dict(ids=ids, documents=documents, metadatas=metadatas)
        if embeddings is not None:
            kwargs["embeddings"] = embeddings
        self._collection.upsert(**kwargs)

    def query(
        self,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = dict(query_texts=query_texts, n_results=n_results)
        if where:
            kwargs["where"] = where
        return self._collection.query(**kwargs)

    def delete(self, where: Dict[str, Any]) -> None:
        self._collection.delete(where=where)

    def get(
        self,
        where: Dict[str, Any],
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"where": where}
        if include:
            kwargs["include"] = include
        return self._collection.get(**kwargs)

    def update(self, ids: List[str], metadatas: List[Dict[str, Any]]) -> None:
        self._collection.update(ids=ids, metadatas=metadatas)

    def count(self) -> int:
        """Return total document count in the ChromaDB collection."""
        try:
            return self._collection.count()
        except Exception:
            return 0

    def get_distinct_repos(self) -> List[str]:
        """Return list of unique repositories in the ChromaDB collection."""
        try:
            data = self._collection.get(include=["metadatas"])
            repos = set()
            if data and data.get("metadatas"):
                for meta in data["metadatas"]:
                    if meta and "repo" in meta and meta["repo"]:
                        repos.add(meta["repo"])
            return sorted(list(repos))
        except Exception:
            return []

