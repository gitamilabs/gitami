from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional
from git import Repo

from src.context.contracts import (
    AuthorizedScope,
    ContextItem,
    ContextItemType,
    ContextSource,
)
from src.context.provenance import create_source
from src.vector.client import VectorKBClient, ContentType

logger = logging.getLogger(__name__)


class GitHubRetriever:
    """
    Retrieves PR, Issue, and Git commit maintenance evidence.
    Leverages indexed vector store PR/Issue/Commit entries and local Git commit logs.
    Gracefully degrades if external GitHub APIs are not configured.
    """

    def __init__(
        self,
        vector_client: Optional[VectorKBClient] = None,
        default_repo_root: Optional[str | Path] = None,
    ):
        self.vector_client = vector_client
        self.default_repo_root = Path(default_repo_root).resolve() if default_repo_root else None

    async def retrieve(
        self,
        query: str,
        scope: AuthorizedScope,
        limit: int = 5,
    ) -> List[ContextItem]:
        if not scope.allowed_repo_ids:
            return []

        items: List[ContextItem] = []

        # 1. Retrieve indexed PRs / Issues / Commits from Vector KB if available
        if self.vector_client:
            for repo_id in scope.allowed_repo_ids:
                try:
                    res = self.vector_client.query(
                        query_texts=[query],
                        n_results=limit,
                        where={"repo": repo_id},
                    )
                    if not res:
                        continue

                    docs = res.get("documents", [[]])[0] if res.get("documents") else []
                    metas = res.get("metadatas", [[]])[0] if res.get("metadatas") else []
                    ids = res.get("ids", [[]])[0] if res.get("ids") else []

                    for idx, doc in enumerate(docs):
                        meta = metas[idx] if idx < len(metas) else {}
                        doc_id = ids[idx] if idx < len(ids) else f"gh_{repo_id}_{idx}"
                        c_type = meta.get("content_type")

                        # Filter for PR, Issue, Commit content
                        if c_type == ContentType.PR.value:
                            pr_id = meta.get("pr_id")
                            try:
                                pr_num = int(pr_id) if pr_id and str(pr_id).isdigit() else None
                            except ValueError:
                                pr_num = None

                            source = create_source(
                                kind="github_pr",
                                repository_id=repo_id,
                                commit_sha=meta.get("commit_hash"),
                                pr_number=pr_num,
                            )
                            items.append(
                                ContextItem(
                                    id=f"pr:{repo_id}:{pr_id or doc_id}",
                                    type=ContextItemType.PULL_REQUEST,
                                    title=f"Pull Request #{pr_id or 'unknown'} ({repo_id})",
                                    content=doc,
                                    relevance_score=0.6,
                                    source=source,
                                    metadata=meta,
                                )
                            )
                        elif c_type == ContentType.ISSUE.value:
                            issue_id = meta.get("issue_id")
                            try:
                                issue_num = int(issue_id) if issue_id and str(issue_id).isdigit() else None
                            except ValueError:
                                issue_num = None

                            source = create_source(
                                kind="github_issue",
                                repository_id=repo_id,
                                issue_number=issue_num,
                            )
                            items.append(
                                ContextItem(
                                    id=f"issue:{repo_id}:{issue_id or doc_id}",
                                    type=ContextItemType.ISSUE,
                                    title=f"GitHub Issue #{issue_id or 'unknown'} ({repo_id})",
                                    content=doc,
                                    relevance_score=0.6,
                                    source=source,
                                    metadata=meta,
                                )
                            )
                except Exception as e:
                    logger.debug(f"GitHubRetriever vector query note for repo '{repo_id}': {e}")

        # 2. Retrieve recent matching Git commits from local git repository
        for repo_id in scope.allowed_repo_ids:
            repo_path = scope.repo_paths.get(repo_id) or self.default_repo_root
            if not repo_path or not repo_path.exists():
                continue

            try:
                git_repo = Repo(repo_path, search_parent_directories=True)
                # Search last 20 commits for query keyword
                q_words = [w.lower() for w in query.split() if len(w) > 3]
                found_commits = 0
                for commit in git_repo.iter_commits(max_count=20):
                    msg = commit.message
                    if any(w in msg.lower() for w in q_words):
                        source = create_source(
                            kind="git_commit",
                            repository_id=repo_id,
                            commit_sha=commit.hexsha,
                        )
                        items.append(
                            ContextItem(
                                id=f"commit:{repo_id}:{commit.hexsha[:8]}",
                                type=ContextItemType.COMMIT,
                                title=f"Commit {commit.hexsha[:8]}: {commit.summary}",
                                content=f"Author: {commit.author.name}\nDate: {commit.authored_datetime}\nMessage: {msg.strip()}",
                                relevance_score=0.55,
                                source=source,
                                metadata={"sha": commit.hexsha, "author": commit.author.name},
                            )
                        )
                        found_commits += 1
                        if found_commits >= 3:
                            break
            except Exception as e:
                logger.debug(f"GitHubRetriever Git log note for repo '{repo_id}': {e}")

        return items
