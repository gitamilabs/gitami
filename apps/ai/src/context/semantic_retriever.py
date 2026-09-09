from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.context.contracts import (
    AuthorizedScope,
    ContextItem,
    ContextItemType,
    ContextSource,
)
from src.context.provenance import create_source
from src.vector.client import VectorKBClient

logger = logging.getLogger(__name__)


class SemanticRetriever:
    """
    Retrieves semantic code snippets from the vector store.
    Strictly post-filters results to prevent cross-repository leakage.
    """

    def __init__(self, client: VectorKBClient):
        self.client = client

    async def retrieve(
        self,
        query: str,
        scope: AuthorizedScope,
        limit: int = 10,
    ) -> List[ContextItem]:
        if not scope.allowed_repo_ids:
            return []

        items: List[ContextItem] = []
        n_per_repo = max(2, limit // max(len(scope.allowed_repo_ids), 1))

        for repo_id in scope.allowed_repo_ids:
            try:
                # Query with where filter on repo
                res = self.client.query(
                    query_texts=[query],
                    n_results=n_per_repo,
                    where={"repo": repo_id},
                )
            except Exception as e:
                logger.warning(f"Vector search failed for repo '{repo_id}': {e}")
                continue

            if not res:
                continue

            documents = res.get("documents", [[]])[0] if res.get("documents") else []
            metadatas = res.get("metadatas", [[]])[0] if res.get("metadatas") else []
            distances = res.get("distances", [[]])[0] if res.get("distances") else []
            ids = res.get("ids", [[]])[0] if res.get("ids") else []

            for idx, doc in enumerate(documents):
                meta = metadatas[idx] if idx < len(metadatas) else {}
                doc_id = ids[idx] if idx < len(ids) else f"vec_{repo_id}_{idx}"
                dist = distances[idx] if idx < len(distances) else 0.5

                # STRICT SECURITY GATE: Enforce repository boundary
                hit_repo = meta.get("repo") or repo_id
                if hit_repo not in scope.allowed_repo_ids:
                    logger.warning(
                        f"Cross-repo vector leakage prevented! Hit repo '{hit_repo}' not in authorized scope {scope.allowed_repo_ids}"
                    )
                    continue

                file_path = meta.get("file_path", "")
                symbol = meta.get("symbol") or meta.get("name", "")
                commit_sha = meta.get("commit_hash") or meta.get("last_valid_commit")
                start_line = meta.get("start_line")

                # Convert distance to normalized similarity (0.0 - 1.0)
                sim_score = max(0.0, min(1.0, 1.0 - float(dist)))

                source = create_source(
                    kind="semantic",
                    repository_id=hit_repo,
                    file_path=file_path,
                    entity_uid=meta.get("uid"),
                    commit_sha=commit_sha,
                    start_line=start_line,
                    confidence=sim_score,
                )

                title_text = f"Code: {symbol} in {file_path}" if symbol and file_path else f"Snippet: {file_path or doc_id}"

                items.append(
                    ContextItem(
                        id=f"sem:{doc_id}",
                        type=ContextItemType.SEMANTIC_CODE,
                        title=title_text,
                        content=doc,
                        relevance_score=round(sim_score * 0.8, 4),
                        source=source,
                        metadata={
                            "similarity": sim_score,
                            "symbol": symbol,
                            "file_path": file_path,
                            "distance": dist,
                        },
                    )
                )

        return items
