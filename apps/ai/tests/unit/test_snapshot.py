import pytest
from pathlib import Path
from src.indexer.snapshot import RepositorySnapshot

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_snapshot_non_git_fixture_fallback():
    """Ensure non-git fixture directories can be read seamlessly."""
    fixture_path = FIXTURES_DIR / "python_sample"
    with RepositorySnapshot(fixture_path, target_commit_sha="HEAD") as snap:
        files = snap.list_files()
        assert len(files) >= 3
        assert "calculator.py" in files or any("calculator.py" in f for f in files)
        content = snap.read_bytes("calculator.py")
        assert b"def add" in content


def test_snapshot_missing_directory():
    with pytest.raises(FileNotFoundError):
        RepositorySnapshot("/non/existent/path/for/sure", "HEAD")


def test_snapshot_git_repo_explicit_commit():
    """Test snapshot against the Gitami git repository itself."""
    repo_root = Path(__file__).parent.parent.parent.parent.parent
    with RepositorySnapshot(repo_root, target_commit_sha="HEAD") as snap:
        assert len(snap.resolved_commit_sha) == 40
        files = snap.list_files()
        assert "Readme.md" in files
        content = snap.read_bytes("Readme.md")
        assert len(content) > 0


def test_snapshot_invalid_commit():
    repo_root = Path(__file__).parent.parent.parent.parent.parent
    with pytest.raises(ValueError, match="does not exist in repository"):
        RepositorySnapshot(repo_root, target_commit_sha="nonexistent_sha_xyz123")
