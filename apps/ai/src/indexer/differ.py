import logging
from pathlib import Path
from typing import List, Optional, Set
import git
from git import Repo

from src.indexer.contracts import ChangedFile, ChangedFileType, DiffResult
from src.indexer.discovery import FileDiscovery

logger = logging.getLogger(__name__)


class GitDiffer:
    """
    Computes precise file-level diff between a base commit and target commit.
    
    Guarantees:
    1. Validates commit existence and ancestor relationship.
    2. Uses Git's native rename detection (-M / find_renames=True).
    3. Filters paths using FileDiscovery language and noise rules.
    4. Computes conservative change percentage:
       changed logical paths / max(number of indexable files at base, 1).
    5. Flags unsafe incremental operations (> 50% change or non-ancestor).
    """

    def __init__(
        self,
        discovery: Optional[FileDiscovery] = None,
        max_change_percentage: float = 0.50,
    ):
        self.discovery = discovery or FileDiscovery()
        self.max_change_percentage = max_change_percentage

    def compute_diff(
        self,
        repo_path: str | Path,
        base_commit_sha: str,
        target_commit_sha: str,
    ) -> DiffResult:
        """
        Execute git diff between base_commit_sha and target_commit_sha.
        
        Returns:
            DiffResult with categorized changed files and safety determination.
        """
        try:
            repo = Repo(repo_path, search_parent_directories=True)
        except Exception as e:
            return DiffResult(
                base_commit_sha=base_commit_sha,
                target_commit_sha=target_commit_sha,
                is_ancestor=False,
                is_safe_incremental=False,
                fallback_reason=f"Failed to open Git repository at '{repo_path}': {e}",
            )

        try:
            # 1. Validate commit existence
            try:
                base_commit = repo.commit(base_commit_sha)
            except Exception:
                return DiffResult(
                    base_commit_sha=base_commit_sha,
                    target_commit_sha=target_commit_sha,
                    is_ancestor=False,
                    is_safe_incremental=False,
                    fallback_reason=f"Base commit '{base_commit_sha}' does not exist in repository",
                )

            try:
                target_commit = repo.commit(target_commit_sha)
            except Exception:
                return DiffResult(
                    base_commit_sha=base_commit.hexsha,
                    target_commit_sha=target_commit_sha,
                    is_ancestor=False,
                    is_safe_incremental=False,
                    fallback_reason=f"Target commit '{target_commit_sha}' does not exist in repository",
                )

            base_sha = base_commit.hexsha
            target_sha = target_commit.hexsha

            # Trivial identity check: same commit
            if base_sha == target_sha:
                return DiffResult(
                    base_commit_sha=base_sha,
                    target_commit_sha=target_sha,
                    is_ancestor=True,
                    changed_files=[],
                    change_percentage=0.0,
                    is_safe_incremental=True,
                )

            # 2. Validate ancestor relationship
            is_ancestor = repo.is_ancestor(base_commit, target_commit)
            if not is_ancestor:
                return DiffResult(
                    base_commit_sha=base_sha,
                    target_commit_sha=target_sha,
                    is_ancestor=False,
                    is_safe_incremental=False,
                    fallback_reason=f"Base commit '{base_sha}' is not an ancestor of target '{target_sha}'",
                )

            # 3. Compute Git diff with automatic rename detection
            diff_index = base_commit.diff(target_commit)
            changed_files: List[ChangedFile] = []
            logical_paths_changed: Set[str] = set()

            for d in diff_index:
                if d.renamed_file:
                    old_path = d.a_path.replace("\\", "/").lstrip("/")
                    new_path = d.b_path.replace("\\", "/").lstrip("/")
                    
                    old_is_code = self.discovery.is_indexable_path(old_path)
                    new_is_code = self.discovery.is_indexable_path(new_path)

                    if old_is_code and new_is_code:
                        changed_files.append(
                            ChangedFile(
                                path=new_path,
                                change_type=ChangedFileType.RENAMED,
                                old_path=old_path,
                                language=self.discovery.get_language_for_path(new_path),
                            )
                        )
                        logical_paths_changed.add(new_path)
                    elif old_is_code and not new_is_code:
                        # Renamed to a non-code/ignored file -> effectively deleted from code graph
                        changed_files.append(
                            ChangedFile(
                                path=old_path,
                                change_type=ChangedFileType.DELETED,
                                language=self.discovery.get_language_for_path(old_path),
                            )
                        )
                        logical_paths_changed.add(old_path)
                    elif not old_is_code and new_is_code:
                        # Renamed from ignored to code -> effectively added
                        changed_files.append(
                            ChangedFile(
                                path=new_path,
                                change_type=ChangedFileType.ADDED,
                                language=self.discovery.get_language_for_path(new_path),
                            )
                        )
                        logical_paths_changed.add(new_path)

                elif d.new_file:
                    path = d.b_path.replace("\\", "/").lstrip("/")
                    if self.discovery.is_indexable_path(path):
                        changed_files.append(
                            ChangedFile(
                                path=path,
                                change_type=ChangedFileType.ADDED,
                                language=self.discovery.get_language_for_path(path),
                            )
                        )
                        logical_paths_changed.add(path)

                elif d.deleted_file:
                    path = d.a_path.replace("\\", "/").lstrip("/")
                    if self.discovery.is_indexable_path(path):
                        changed_files.append(
                            ChangedFile(
                                path=path,
                                change_type=ChangedFileType.DELETED,
                                language=self.discovery.get_language_for_path(path),
                            )
                        )
                        logical_paths_changed.add(path)

                else:
                    # Modified file
                    path = (d.b_path or d.a_path).replace("\\", "/").lstrip("/")
                    if self.discovery.is_indexable_path(path):
                        changed_files.append(
                            ChangedFile(
                                path=path,
                                change_type=ChangedFileType.MODIFIED,
                                language=self.discovery.get_language_for_path(path),
                            )
                        )
                        logical_paths_changed.add(path)

            # 4. Calculate change percentage against total indexable files at base
            base_file_count = 0
            for item in base_commit.tree.traverse():
                if item.type == "blob" and self.discovery.is_indexable_path(item.path):
                    base_file_count += 1

            denominator = max(base_file_count, 1)
            change_percentage = round(len(logical_paths_changed) / denominator, 4)

            # 5. Determine safety
            is_safe = True
            fallback_reason = None

            if change_percentage > self.max_change_percentage:
                is_safe = False
                fallback_reason = (
                    f"Change percentage ({change_percentage:.1%}, {len(logical_paths_changed)}/{denominator} files) "
                    f"exceeds safety threshold ({self.max_change_percentage:.0%})"
                )

            return DiffResult(
                base_commit_sha=base_sha,
                target_commit_sha=target_sha,
                is_ancestor=True,
                changed_files=changed_files,
                change_percentage=change_percentage,
                is_safe_incremental=is_safe,
                fallback_reason=fallback_reason,
            )

        finally:
            repo.close()
