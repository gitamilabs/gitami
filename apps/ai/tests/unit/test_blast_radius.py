import pytest
from unittest.mock import AsyncMock
from src.analysis.blast_radius import compute_blast_radius


@pytest.mark.asyncio
async def test_compute_blast_radius_mocked():
    mock_client = AsyncMock()

    # Mock Neo4j query records for get_dependents
    mock_client.execute_query.return_value = [
        {"qualified_name": "app.py::main", "file_path": "app.py", "depth": 1},
        {"qualified_name": "server.py::start", "file_path": "server.py", "depth": 2},
    ]

    res = await compute_blast_radius(
        client=mock_client,
        repo_id="test_repo",
        branch="main",
        changed_symbols=["util.py::helper"],
        max_depth=3,
    )

    assert res.total_affected == 2
    assert res.risk_score > 0.0
    assert res.affected_symbols[0].qualified_name == "app.py::main"
