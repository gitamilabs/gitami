from pathlib import Path
from src.indexer.discovery import FileDiscovery
from src.indexer.snapshot import RepositorySnapshot

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_file_discovery_python_fixture():
    snap = RepositorySnapshot(FIXTURES_DIR / "python_sample", "HEAD")
    discovery = FileDiscovery()
    files, skipped = discovery.discover_files(snap)

    assert len(files) >= 4
    file_map = {f.file_path: f for f in files}
    assert "calculator.py" in file_map
    assert file_map["calculator.py"].language == "python"
    assert len(file_map["calculator.py"].sha256) == 64
    assert file_map["calculator.py"].size_bytes > 0


def test_file_discovery_mern_fixture():
    snap = RepositorySnapshot(FIXTURES_DIR / "mern_sample", "HEAD")
    discovery = FileDiscovery()
    files, skipped = discovery.discover_files(snap)

    assert len(files) >= 4
    exts = {Path(f.file_path).suffix for f in files}
    assert ".js" in exts or ".jsx" in exts


def test_file_discovery_with_root_directory():
    snap = RepositorySnapshot(FIXTURES_DIR / "mern_sample", "HEAD")
    discovery = FileDiscovery()
    # Discover strictly within "controllers" or "routes" subfolder
    all_files, _ = discovery.discover_files(snap)
    subdirs = {Path(f.file_path).parts[0] for f in all_files if len(Path(f.file_path).parts) > 1}
    if subdirs:
        chosen_sub = next(iter(subdirs))
        filtered_files, skipped = discovery.discover_files(snap, root_directory=chosen_sub)
        assert len(filtered_files) > 0
        assert all(f.file_path.startswith(f"{chosen_sub}/") or f.file_path == chosen_sub for f in filtered_files)
        assert skipped > 0
