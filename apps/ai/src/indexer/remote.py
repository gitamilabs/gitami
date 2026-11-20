import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.indexer.contracts import ChangedFile, ChangedFileType, DiffResult
from src.indexer.discovery import FileDiscovery

logger = logging.getLogger(__name__)

CONFIG_FILES_SET: Set[str] = {
    "tsconfig.json",
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
}


class GitHubApiDiffer:
    """
    Computes precise file-level diff between a base commit and target commit
    using the GitHub Compare Commits API without requiring an on-disk Git clone.
    """

    def __init__(
        self,
        discovery: Optional[FileDiscovery] = None,
        max_changed_files_threshold: int = 50,
        max_change_percentage: float = 0.25,
        sensitive_config_files: Optional[Set[str]] = None,
    ):
        self.discovery = discovery or FileDiscovery()
        self.max_changed_files_threshold = max_changed_files_threshold
        self.max_change_percentage = max_change_percentage
        self.sensitive_config_files = sensitive_config_files or CONFIG_FILES_SET

    def _fetch_compare_api(
        self,
        full_name: str,
        base_commit_sha: str,
        target_commit_sha: str,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch raw JSON response from GitHub's compare API."""
        url = f"https://api.github.com/repos/{full_name}/compare/{base_commit_sha}...{target_commit_sha}"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Gitami-Incremental-Indexer",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data)
        except urllib.error.HTTPError as e:
            logger.error(f"GitHub compare API failed: HTTP {e.code} - {e.reason}")
            raise
        except Exception as e:
            logger.error(f"GitHub compare API network failure: {e}")
            raise

    def compute_diff(
        self,
        full_name: str,
        base_commit_sha: str,
        target_commit_sha: str,
        access_token: Optional[str] = None,
    ) -> DiffResult:
        """
        Compare base_commit_sha and target_commit_sha over GitHub API.

        Returns:
            DiffResult containing categorized file changes and safety determination.
        """
        if base_commit_sha == target_commit_sha:
            return DiffResult(
                base_commit_sha=base_commit_sha,
                target_commit_sha=target_commit_sha,
                is_ancestor=True,
                changed_files=[],
                change_percentage=0.0,
                is_safe_incremental=True,
            )

        try:
            payload = self._fetch_compare_api(
                full_name=full_name,
                base_commit_sha=base_commit_sha,
                target_commit_sha=target_commit_sha,
                access_token=access_token,
            )
        except Exception as err:
            return DiffResult(
                base_commit_sha=base_commit_sha,
                target_commit_sha=target_commit_sha,
                is_ancestor=False,
                is_safe_incremental=False,
                fallback_reason=f"Failed to fetch GitHub compare API: {err}",
            )

        status = payload.get("status", "")
        # Check for history divergence (e.g. force push / rebase)
        if status == "diverged":
            return DiffResult(
                base_commit_sha=base_commit_sha,
                target_commit_sha=target_commit_sha,
                is_ancestor=False,
                is_safe_incremental=False,
                fallback_reason="Git history diverged: base commit is not ancestor of target commit",
            )

        files = payload.get("files", [])

        # Check safety threshold: max changed files limit
        if len(files) > self.max_changed_files_threshold:
            return DiffResult(
                base_commit_sha=base_commit_sha,
                target_commit_sha=target_commit_sha,
                is_ancestor=True,
                is_safe_incremental=False,
                fallback_reason=f"Changed files count ({len(files)}) exceeds threshold ({self.max_changed_files_threshold})",
            )

        changed_files: List[ChangedFile] = []
        for f in files:
            filename = f.get("filename", "")
            norm_path = filename.replace("\\", "/").lstrip("/")

            # Check if any sensitive root config file was altered
            basename = Path(norm_path).name
            if basename in self.sensitive_config_files or norm_path in self.sensitive_config_files:
                return DiffResult(
                    base_commit_sha=base_commit_sha,
                    target_commit_sha=target_commit_sha,
                    is_ancestor=True,
                    is_safe_incremental=False,
                    fallback_reason=f"Core configuration file modified: {norm_path}",
                )

            # Skip noise / ignored paths according to discovery rules
            if not self.discovery.is_indexable_path(norm_path):
                continue

            raw_status = f.get("status", "modified").lower()
            old_path = f.get("previous_filename")
            if old_path:
                old_path = old_path.replace("\\", "/").lstrip("/")

            if raw_status == "added":
                c_type = ChangedFileType.ADDED
            elif raw_status == "removed":
                c_type = ChangedFileType.DELETED
            elif raw_status == "renamed":
                c_type = ChangedFileType.RENAMED
            else:
                c_type = ChangedFileType.MODIFIED

            lang = self.discovery.get_language_for_path(norm_path) or "unknown"
            changed_files.append(
                ChangedFile(
                    path=norm_path,
                    change_type=c_type,
                    old_path=old_path,
                    language=lang,
                )
            )

        return DiffResult(
            base_commit_sha=base_commit_sha,
            target_commit_sha=target_commit_sha,
            is_ancestor=True,
            changed_files=changed_files,
            is_safe_incremental=True,
        )


class RemoteGitHubSnapshot:
    """
    In-memory isolated snapshot of a remote repository at an explicit commit SHA.
    Streams files over HTTPS or serves preloaded bytes without writing to disk.
    """

    def __init__(
        self,
        full_name: str,
        commit_sha: str,
        access_token: Optional[str] = None,
        preloaded_files: Optional[Dict[str, bytes]] = None,
    ):
        self.full_name = full_name
        self.resolved_commit_sha = commit_sha
        self.access_token = access_token
        self._preloaded_files = {
            k.replace("\\", "/").lstrip("/"): v for k, v in (preloaded_files or {}).items()
        }

    def preload_file(self, file_path: str, content: bytes) -> None:
        """Cache file content bytes in memory."""
        norm = file_path.replace("\\", "/").lstrip("/")
        self._preloaded_files[norm] = content

    def read_bytes(self, file_path: str) -> bytes:
        """Read exact byte content of a file at the target commit directly into memory."""
        norm = file_path.replace("\\", "/").lstrip("/")
        if norm in self._preloaded_files:
            return self._preloaded_files[norm]

        # Fetch directly from GitHub raw content API
        url = f"https://raw.githubusercontent.com/{self.full_name}/{self.resolved_commit_sha}/{norm}"
        headers = {"User-Agent": "Gitami-Incremental-Indexer"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
                self._preloaded_files[norm] = content
                return content
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise FileNotFoundError(
                    f"File '{norm}' not found at remote commit {self.resolved_commit_sha}"
                )
            logger.error(f"HTTP error fetching remote file '{norm}': {e.code} {e.reason}")
            raise
        except Exception as e:
            logger.error(f"Network error fetching remote file '{norm}': {e}")
            raise

    def list_files(self) -> List[str]:
        """Return all known preloaded file paths."""
        return sorted(list(self._preloaded_files.keys()))

    def close(self) -> None:
        """Clear in-memory file buffers."""
        self._preloaded_files.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
