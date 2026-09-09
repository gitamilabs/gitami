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
