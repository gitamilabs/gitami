from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from src.analysis.report import generate_graph_report, render_graph_report
from src.web.app import app
from src.web.deps import get_shared_graph_client


SAMPLE_NODES = [
    {"id": "file1.py", "label": "file1.py", "type": "File"},
    {"id": "file2.py", "label": "file2.py", "type": "File"},
]

SAMPLE_EDGES = [
    {"source": "file1.py", "target": "file2.py", "type": "IMPORTS"},
]

SAMPLE_COMMUNITIES = {
    0: ["file1.py", "file2.py"]
}

SAMPLE_GOD_NODES = [
    {"id": "file1.py", "label": "file1.py", "type": "File", "degree": 5, "in_degree": 2, "out_degree": 3}
]

SAMPLE_SURPRISING = [
    {
        "source": "file1.py",
        "source_label": "file1.py",
        "source_community": 0,
        "target": "file2.py",
        "target_label": "file2.py",
        "target_community": 1,
        "relation": "CALLS",
    }
]

SAMPLE_CYCLES = [
    ["file1.py", "file2.py"]
]


def test_generate_graph_report_in_memory():
    """Verify generate_graph_report returns markdown string directly without writing files."""
    report_md = generate_graph_report(
        repo_id="owner/repo",
        nodes=SAMPLE_NODES,
        edges=SAMPLE_EDGES,
        communities=SAMPLE_COMMUNITIES,
        god_nodes=SAMPLE_GOD_NODES,
        surprising=SAMPLE_SURPRISING,
        cycles=SAMPLE_CYCLES,
    )

    assert isinstance(report_md, str)
    assert "# Graphify Architectural Report: owner/repo" in report_md
    assert "- **Total Nodes**: 2" in report_md
    assert "- **Total Edges**: 1" in report_md
    assert "- **Number of Communities**: 1" in report_md
    assert "| `file1.py` | File | 5 | 2 | 3 |" in report_md
    assert "| `file1.py` (0) | CALLS | `file2.py` (1) |" in report_md
    assert "`file1.py` -> `file2.py` -> `file1.py`" in report_md


def test_render_graph_report_alias():
    """Verify render_graph_report is an alias that renders in-memory markdown."""
    report_md = render_graph_report(
        repo_id="owner/repo",
        nodes=SAMPLE_NODES,
        edges=SAMPLE_EDGES,
        communities=SAMPLE_COMMUNITIES,
        god_nodes=SAMPLE_GOD_NODES,
        surprising=[],
        cycles=[],
    )

    assert isinstance(report_md, str)
    assert "# Graphify Architectural Report: owner/repo" in report_md
    assert "*No surprising cross-community connections found.*" in report_md
    assert "*No import cycles detected.*" in report_md


def test_generate_graph_report_with_out_dir(tmp_path: Path):
    """Verify generate_graph_report optionally writes to disk when out_dir is provided."""
    out_dir = tmp_path / "reports"
    report_md = generate_graph_report(
        repo_id="owner/repo",
        nodes=SAMPLE_NODES,
        edges=SAMPLE_EDGES,
        communities=SAMPLE_COMMUNITIES,
        god_nodes=SAMPLE_GOD_NODES,
        surprising=SAMPLE_SURPRISING,
        cycles=SAMPLE_CYCLES,
        out_dir=out_dir,
    )

    assert isinstance(report_md, str)
    assert (out_dir / "graph.json").exists()
    assert (out_dir / "GRAPH_REPORT.md").exists()
    assert (out_dir / "GRAPH_REPORT.md").read_text(encoding="utf-8") == report_md


def test_graph_report_route_returns_in_memory_markdown_without_tmp_leak():
    """Verify GET /api/graph-report/{repo_id} generates report in-memory with zero /tmp files."""
    mock_graph_client = AsyncMock()

    app.dependency_overrides[get_shared_graph_client] = lambda: mock_graph_client

    mock_graph_data = {
        "nodes": SAMPLE_NODES,
        "edges": SAMPLE_EDGES,
    }

    tmp_root = Path(tempfile.gettempdir())
    leak_dir = tmp_root / "graphify_reports"

    # Remove leak_dir if leftover from previous legacy runs
    if leak_dir.exists():
        import shutil
        shutil.rmtree(leak_dir, ignore_errors=True)

    with patch("src.web.routes.graph.get_entire_graph", AsyncMock(return_value=mock_graph_data)):
        client = TestClient(app)
        response = client.get("/api/graph-report/test_owner/test_repo")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["repo_id"] == "test_owner/test_repo"
    assert "# Graphify Architectural Report: test_owner/test_repo" in data["report_markdown"]
    assert "- **Total Nodes**: 2" in data["report_markdown"]

    # Invariant: zero disk files created in /tmp
    assert not leak_dir.exists(), f"Expected no temporary files under {leak_dir}, but directory was created!"
