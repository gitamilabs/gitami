"""VectorKBClient — public facade over pluggable vector store and embedding model.

The backend is selected entirely by the .env keys:
    VECTOR_DB : chroma_local | chroma_cloud | qdrant | pinecone | supabase | memory
    EMBEDDER  : gemini | openai | fastembed

All callers (cli.py, init_job.py, pr_eval_job.py, web/app.py, mcp/server.py, etc.)
continue to instantiate VectorKBClient() with no arguments — the factories handle
backend selection transparently.
"""
import logging
import time
from enum import Enum
from typing import List, Dict, Any, Optional

from src.config import settings
from src.vector.embedders.factory import get_embedding_function
from src.vector.stores.factory import get_vector_store
from src.vector.splitter import split_markdown_text

logger = logging.getLogger(__name__)


class ContentType(str, Enum):
    CODE = "code"
    PR = "pr"
    COMMIT = "commit"
    ISSUE = "issue"


class VectorKBClient:
    def __init__(self, persist_directory: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialise the vector knowledge base client.

        :param persist_directory: Deprecated — use CHROMA_PERSIST_DIR in .env instead.
                                  Accepted for backward-compatibility but ignored when
                                  a cloud or non-Chroma backend is active.
        :param api_key: Deprecated — use GEMINI_API_KEY in .env instead.
                        Accepted for backward-compatibility only.
        """
        import src.config as config_module
        current_settings = config_module.settings
        # Override chroma persist dir for backward-compat if passed explicitly
        if persist_directory:
            current_settings.chroma_persist_dir = persist_directory

        self._embedder = get_embedding_function(current_settings)
        self._store = get_vector_store(current_settings, self._embedder)
        self._batch_size: int = self._store.batch_size


    # ── Internal helpers ──────────────────────────────────────────────────────

    def _upsert(self, doc_id: str, document: str, metadata: Dict[str, Any]) -> None:
        """Upsert a single document."""
        self._store.upsert(ids=[doc_id], documents=[document], metadatas=[metadata])

    def _normalize_where(self, where: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Normalise a flat metadata dict into ChromaDB-style $and filter."""
        if not where:
            return None
        for key in ("$and", "$or"):
            if key in where:
                return where
        clean_items = [{k: v} for k, v in where.items() if v is not None and v != ""]
        if not clean_items:
            return None
        if len(clean_items) == 1:
            return clean_items[0]
        return {"$and": clean_items}

    # ── Write methods (identical signatures to previous implementation) ────────

    def add_code_entry(
        self,
        repo: str,
        branch: str,
        file_path: str,
        symbol: str,
        signature: str,
        description: str,
        commit_hash: str,
        start_line: Optional[int] = None,
        code_body: str = "",
    ) -> None:
        """Add or update a single code symbol entry."""
        line_suffix = f"_{start_line}" if start_line is not None else ""
        doc_id = f"code_{repo}_{branch}_{file_path}_{symbol}{line_suffix}"

        doc_parts = [
            f"File: {file_path}" + (f" (lines {start_line})" if start_line else ""),
            f"Symbol: {symbol}",
            f"Signature:\n{signature}",
            f"Description:\n{description}",
        ]
        if code_body:
            doc_parts.append(f"Implementation Code:\n{code_body}")
        document = "\n\n".join(doc_parts)

        metadata = {
            "repo": repo,
            "branch": branch,
            "file_path": file_path,
            "symbol": symbol,
            "content_type": ContentType.CODE.value,
            "commit_hash": commit_hash,
            "last_valid_commit": commit_hash,
        }
        self._upsert(doc_id, document, metadata)

    def add_code_entries_batch(self, entries: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Batch upsert multiple code entries with per-batch resilience and retry.
        Deduplicates by unique doc_id and respects the backend's batch_size.
        """
        if not entries:
            return {"total": 0, "successful": 0, "failed": 0}

        unique_map: Dict[str, tuple] = {}
        for item in entries:
            start_line = item.get("start_line")
            line_suffix = f"_{start_line}" if start_line is not None else ""
            doc_id = f"code_{item['repo']}_{item['branch']}_{item['file_path']}_{item['symbol']}{line_suffix}"

            doc_parts = [
                f"File: {item['file_path']}" + (f" (lines {start_line})" if start_line else ""),
                f"Symbol: {item['symbol']}",
                f"Signature:\n{item['signature']}",
                f"Description:\n{item['description']}",
            ]
            if item.get("code_body"):
                doc_parts.append(f"Implementation Code:\n{item['code_body']}")
            document = "\n\n".join(doc_parts)

            metadata = {
                "repo": item["repo"],
                "branch": item["branch"],
                "file_path": item["file_path"],
                "symbol": item["symbol"],
                "content_type": ContentType.CODE.value,
                "commit_hash": item["commit_hash"],
                "last_valid_commit": item["commit_hash"],
            }
            unique_map[doc_id] = (document, metadata)

        doc_ids = list(unique_map.keys())
        docs = [v[0] for v in unique_map.values()]
        metas = [v[1] for v in unique_map.values()]

        successful_count = 0
        failed_count = 0

        for i in range(0, len(doc_ids), self._batch_size):
            batch_ids = doc_ids[i:i + self._batch_size]
            batch_docs = docs[i:i + self._batch_size]
            batch_metas = metas[i:i + self._batch_size]
            batch_idx = (i // self._batch_size) + 1

            try:
                self._store.upsert(
                    ids=batch_ids,
                    documents=batch_docs,
                    metadatas=batch_metas,
                )
                successful_count += len(batch_ids)
            except Exception as e:
                logger.warning(
                    f"Vector upsert failed for batch {batch_idx} ({len(batch_ids)} docs): {e}. Retrying once after backoff..."
                )
                time.sleep(1.0)
                try:
                    self._store.upsert(
                        ids=batch_ids,
                        documents=batch_docs,
                        metadatas=batch_metas,
                    )
                    successful_count += len(batch_ids)
                    logger.info(f"Retry succeeded for batch {batch_idx}")
                except Exception as retry_err:
                    logger.error(f"Permanent vector upsert failure for batch {batch_idx}: {retry_err}")
                    failed_count += len(batch_ids)

        return {"total": len(doc_ids), "successful": successful_count, "failed": failed_count}

    def add_pr_entry(
        self,
        repo: str,
        branch: str,
        pr_id: str,
        description_text: str,
        commit_hash: str,
    ) -> None:
        """Add or update a Pull Request entry, splitting into semantic markdown chunks if large."""
        chunks = split_markdown_text(description_text, chunk_size=800, chunk_overlap=80)
        if not chunks:
            chunks = [description_text]

        for idx, chunk in enumerate(chunks):
            doc_id = f"pr_{repo}_{branch}_{pr_id}" if len(chunks) == 1 else f"pr_{repo}_{branch}_{pr_id}_chunk_{idx}"
            metadata = {
                "repo": repo,
                "branch": branch,
                "pr_id": pr_id,
                "content_type": ContentType.PR.value,
                "commit_hash": commit_hash,
                "last_valid_commit": commit_hash,
                "chunk_index": idx,
                "total_chunks": len(chunks),
            }
            self._upsert(doc_id, chunk, metadata)

    def add_commit_entry(
        self,
        repo: str,
        branch: str,
        commit_hash: str,
        commit_message: str,
    ) -> None:
        """Add a commit message entry, chunking if message is extensive."""
        chunks = split_markdown_text(commit_message, chunk_size=800, chunk_overlap=80)
        if not chunks:
            chunks = [commit_message]

        for idx, chunk in enumerate(chunks):
            doc_id = f"commit_{repo}_{branch}_{commit_hash}" if len(chunks) == 1 else f"commit_{repo}_{branch}_{commit_hash}_chunk_{idx}"
            metadata = {
                "repo": repo,
                "branch": branch,
                "content_type": ContentType.COMMIT.value,
                "commit_hash": commit_hash,
                "last_valid_commit": commit_hash,
                "chunk_index": idx,
                "total_chunks": len(chunks),
            }
            self._upsert(doc_id, chunk, metadata)

    def add_issue_entry(
        self,
        repo: str,
        issue_id: str,
        issue_text: str,
    ) -> None:
        """Add or update an Issue entry, chunking long issue descriptions semantically."""
        chunks = split_markdown_text(issue_text, chunk_size=800, chunk_overlap=80)
        if not chunks:
            chunks = [issue_text]

        for idx, chunk in enumerate(chunks):
            doc_id = f"issue_{repo}_{issue_id}" if len(chunks) == 1 else f"issue_{repo}_{issue_id}_chunk_{idx}"
            metadata = {
                "repo": repo,
                "issue_id": issue_id,
                "content_type": ContentType.ISSUE.value,
                "chunk_index": idx,
                "total_chunks": len(chunks),
            }
            self._upsert(doc_id, chunk, metadata)

    # ── Lifecycle methods ──────────────────────────────────────────────────────

    def roll_forward_commit(
        self, repo: str, branch: str, old_commit_hash: str, new_commit_hash: str
    ) -> None:
        """
        Update last_valid_commit and commit_hash for all entries in a repo/branch
        that still reference old_commit_hash.
        """
        results = self._store.get(
            where={
                "$and": [
                    {"repo": repo},
                    {"branch": branch},
                    {"last_valid_commit": old_commit_hash},
                ]
            },
            include=["metadatas"],
        )

        if not results or not results.get("ids"):
            return

        ids_to_update = results["ids"]
        metadatas_to_update = results["metadatas"]

        for meta in metadatas_to_update:
            meta["last_valid_commit"] = new_commit_hash
            meta["commit_hash"] = new_commit_hash

        self._store.update(ids=ids_to_update, metadatas=metadatas_to_update)

    def delete_stale_entries(self, repo: str, branch: str, latest_commit_hash: str) -> None:
        """Delete entries for a repo/branch that do not have the latest commit hash."""
        self._store.delete(
            where={
                "$and": [
                    {"repo": repo},
                    {"branch": branch},
                    {"last_valid_commit": {"$ne": latest_commit_hash}},
                ]
            }
        )

    def delete(self, where: Dict[str, Any]) -> None:
        """
        Delete all documents matching the given metadata filter.
        Convenience method that replaces direct .collection.delete() calls.
        """
        self._store.delete(where=where)

    # ── Query ──────────────────────────────────────────────────────────────────

    def query(
        self,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Semantic similarity search with automatic $and formatting and empty-result fallback.
        """
        parsed_where = self._normalize_where(where)
        try:
            res = self._store.query(
                query_texts=query_texts,
                n_results=n_results,
                where=parsed_where,
            )
        except Exception:
            res = self._store.query(query_texts=query_texts, n_results=n_results)

        # Fallback: if filtered query returned nothing, retry without filter
        if parsed_where and res and res.get("documents") and res["documents"][0] == []:
            res = self._store.query(query_texts=query_texts, n_results=n_results)

        return res


    def count(self) -> int:

        """Return total document count in the active vector store."""
        if hasattr(self._store, "count"):
            return self._store.count()
        return 0

    def get_distinct_repos(self) -> List[str]:
        """Return list of unique repository identifiers stored in the active vector store."""
        if hasattr(self._store, "get_distinct_repos"):
            return self._store.get_distinct_repos()
        return []

    @property
    def collection(self):
        """Backward-compatibility property returning store or underlying collection."""
        if hasattr(self._store, "_collection"):
            return self._store._collection
        return self._store

