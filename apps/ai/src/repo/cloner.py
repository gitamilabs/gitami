from pathlib import Path
from typing import Optional
from git import Repo


def clone_repo(clone_url: str, token: Optional[str], dest_dir: Path, branch: Optional[str] = None) -> Path:
    """Clone a git repository to dest_dir using optional authentication token."""
    dest_dir.mkdir(parents=True, exist_ok=True)

    url = clone_url
    if token and "https://" in clone_url:
        # Inject token into HTTPS URL: https://x-access-token:TOKEN@github.com/...
        url = clone_url.replace("https://", f"https://x-access-token:{token}@")

    repo = Repo.clone_from(url, dest_dir, branch=branch)
    return dest_dir


def checkout_branch(repo_path: Path, branch: str) -> None:
    """Checkout a specified git branch in local repo."""
    repo = Repo(repo_path)
    repo.git.checkout(branch)
