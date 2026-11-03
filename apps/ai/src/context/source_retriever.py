from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from src.context.contracts import (
    AuthorizedScope,
    ContextItem,
    ContextItemType,
    ContextSource,
)
from src.context.provenance import create_source
from src.indexer.snapshot import RepositorySnapshot

logger = logging.getLogger(__name__)


class SourceRetriever:
    """
    Retrieves focused source code snippets for candidate entities/files.
    Strictly reuses RepositorySnapshot for commit isolation to ensure that
    if a commit_sha is requested, source is guaranteed to come from that revision.
    """

    def __init__(self, default_repo_root: Optional[str | Path] = None):
        self._default_repo_root = Path(default_repo_root).resolve() if default_repo_root else None

    def _resolve_repo_path(self, repo_id: str, scope: AuthorizedScope) -> Optional[Path]:
        """Resolves local filesystem directory for repo_id if strictly available."""
        if repo_id in scope.repo_paths and scope.repo_paths[repo_id] is not None:
            p = scope.repo_paths[repo_id]
            if p.exists():
                return p

        # Fallback to default_repo_root ONLY if it matches the target repo name
        if self._default_repo_root and self._default_repo_root.exists():
            repo_name = repo_id.split("/")[-1]
            if self._default_repo_root.name == repo_name or (self._default_repo_root / repo_name).exists():
                return self._default_repo_root

        return None

    def retrieve_snippet(
        self,
        repo_id: str,
        file_path: str,
        scope: AuthorizedScope,
        commit_sha: Optional[str] = None,
        entity_uid: Optional[str] = None,
        symbol_name: Optional[str] = None,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> Optional[ContextItem]:
        """
        Retrieves a focused code snippet at an explicit commit revision.
        Supports both local on-disk repos and remote GitHub repos.
        """
        import os

        if repo_id not in scope.allowed_repo_ids:
            logger.warning(f"SourceRetriever rejected access to unauthorized repo '{repo_id}'")
            return None

        lines: List[str] = []
        resolved_sha = commit_sha or "HEAD"

        repo_path = self._resolve_repo_path(repo_id, scope)
        if repo_path and repo_path.exists():
            target_sha = commit_sha or "HEAD"
            snapshot: Optional[RepositorySnapshot] = None
            try:
                snapshot = RepositorySnapshot(repo_path, target_sha)
                raw_bytes = snapshot.read_bytes(file_path)
                full_text = raw_bytes.decode("utf-8", errors="replace")
                lines = full_text.splitlines()
                resolved_sha = snapshot.resolved_commit_sha
            except Exception as e:
                logger.warning(
                    f"SourceRetriever could not read '{file_path}' from local repo '{repo_id}': {e}"
                )
            finally:
                if snapshot:
                    snapshot.close()

        # If not retrieved from local disk, fallback to remote GitHub
        if not lines and "/" in repo_id and not repo_id.startswith("local:"):
            try:
                import urllib.request
                from src.config import settings

                token = getattr(settings, "github_token", None) or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
                headers = {"User-Agent": "GitAmi-Agent"}
                if token:
                    headers["Authorization"] = f"Bearer {token}"

                clean_path = file_path.strip().lstrip("/").lstrip("\\")
                ref = commit_sha or scope.default_branch or "main"
                url = f"https://raw.githubusercontent.com/{repo_id}/{ref}/{clean_path}"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=6) as response:
                    if response.status == 200:
                        full_text = response.read().decode("utf-8", errors="replace")
                        lines = full_text.splitlines()
                        resolved_sha = ref
            except Exception as e:
                logger.debug(f"SourceRetriever remote fetch note for '{file_path}': {e}")

        if not lines:
            return None

        # Slice focused snippet if lines provided
        if start_line is not None and end_line is not None and 1 <= start_line <= len(lines):
            actual_end = min(end_line, len(lines))
            slice_lines = lines[start_line - 1 : actual_end]
            # Number lines for clarity
            snippet = "\n".join(f"{start_line + i:4d} | {line}" for i, line in enumerate(slice_lines))
            title = f"Source: {symbol_name or file_path} (lines {start_line}-{actual_end})"
        else:
            # First 50 lines max if no range specified
            max_head = min(50, len(lines))
            snippet = "\n".join(f"{i + 1:4d} | {lines[i]}" for i in range(max_head))
            start_line = 1
            end_line = max_head
            title = f"Source: {file_path} (lines 1-{max_head})"

        source = create_source(
            kind="source_code",
            repository_id=repo_id,
            file_path=file_path,
            entity_uid=entity_uid,
            commit_sha=resolved_sha,
            start_line=start_line,
            end_line=end_line,
        )

        item_id = f"source:{repo_id}:{file_path}:{start_line}_{end_line}"
        return ContextItem(
            id=item_id,
            type=ContextItemType.SYMBOL if symbol_name else ContextItemType.FILE,
            title=title,
            content=snippet,
            relevance_score=0.85,
            source=source,
            metadata={
                "resolved_commit_sha": resolved_sha,
                "requested_commit_sha": target_sha,
                "file_path": file_path,
                "start_line": start_line,
                "end_line": end_line,
            },
        )
