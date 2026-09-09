import io
import os
from pathlib import Path
from typing import Dict, List, Optional, Set
from git import Repo, Commit, Tree, Blob


class RepositorySnapshot:
    """
    Isolated snapshot of a repository at an explicit commit SHA.
    
    Extracts files directly from the Git object database at the target commit,
    ensuring immunity to local working-tree dirty edits or branch switches.
    """

    def __init__(self, repo_path: str | Path, target_commit_sha: str):
        self.repo_path = Path(repo_path).resolve()
        self.requested_commit_sha = target_commit_sha
        self._is_git_repo = False
        self._git_repo: Optional[Repo] = None
        self._commit: Optional[Commit] = None
        self._rel_subpath: str = ""
        self.resolved_commit_sha = target_commit_sha
        self._tree_files: Dict[str, Blob] = {}

        self._initialize()

    def _initialize(self) -> None:
        if not self.repo_path.exists():
            raise FileNotFoundError(f"Repository path does not exist: {self.repo_path}")

        try:
            self._git_repo = Repo(self.repo_path, search_parent_directories=True)
            self._is_git_repo = True
            git_root = Path(self._git_repo.working_dir).resolve()
            try:
                rel = self.repo_path.relative_to(git_root).as_posix()
                self._rel_subpath = "" if rel == "." else rel
            except ValueError:
                self._rel_subpath = ""
        except Exception:
            self._is_git_repo = False
            self._git_repo = None
            self._rel_subpath = ""

        if self._is_git_repo and self._git_repo:
            try:
                # Resolve commit (supports rev-parse for tags, branch names, or short SHAs)
                self._commit = self._git_repo.commit(self.requested_commit_sha)
                self.resolved_commit_sha = self._commit.hexsha
                self._build_git_tree_index(self._commit.tree)
            except Exception as e:
                raise ValueError(
                    f"Target commit '{self.requested_commit_sha}' does not exist in repository {self.repo_path}: {e}"
                )
        else:
            # Fallback for non-git directories
            self.resolved_commit_sha = (
                self.requested_commit_sha
                if self.requested_commit_sha not in ("HEAD", "main")
                else "synthetic-commit-0000000000000000000000000000000000000000"
            )

    def _build_git_tree_index(self, tree: Tree, current_path: str = "") -> None:
        """Walk git tree objects recursively and map relative paths to blobs."""
        for item in tree:
            item_path = f"{current_path}/{item.name}".lstrip("/") if current_path else item.name
            if isinstance(item, Tree):
                self._build_git_tree_index(item, item_path)
            elif isinstance(item, Blob):
                if self._rel_subpath:
                    if item_path.startswith(self._rel_subpath + "/"):
                        rel_path = item_path[len(self._rel_subpath) + 1 :]
                        self._tree_files[rel_path] = item
                else:
                    self._tree_files[item_path] = item

    def list_files(self) -> List[str]:
        """Return all file paths relative to the repository root at this commit."""
        if self._is_git_repo and self._commit and (not self._rel_subpath or self._tree_files):
            return sorted(list(self._tree_files.keys()))

        # Non-git directory walk fallback
        files = []
        for p in self.repo_path.rglob("*"):
            if p.is_file():
                rel = p.relative_to(self.repo_path).as_posix()
                files.append(rel)
        return sorted(files)

    def read_bytes(self, file_path: str) -> bytes:
        """Read exact byte content of a file at the target commit."""
        norm_path = file_path.replace("\\", "/").lstrip("/")
        if self._is_git_repo and self._commit and (not self._rel_subpath or self._tree_files):
            blob = self._tree_files.get(norm_path)
            if blob is None:
                raise FileNotFoundError(f"File '{norm_path}' not found at commit {self.resolved_commit_sha}")
            return blob.data_stream.read()

        # Non-git directory fallback
        target = self.repo_path / norm_path
        if not target.is_file():
            raise FileNotFoundError(f"File '{norm_path}' not found on disk at {target}")
        return target.read_bytes()

    def close(self) -> None:
        if self._git_repo:
            self._git_repo.close()
            self._git_repo = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
