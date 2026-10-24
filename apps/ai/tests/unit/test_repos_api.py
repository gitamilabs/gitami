import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from src.web.app import app

client = TestClient(app)


def test_list_repositories():
    with patch("src.web.routes.repos.get_shared_vector_client") as mock_vc, \
         patch("src.web.routes.repos.get_shared_graph_client", new_callable=AsyncMock) as mock_gc:
        
        vc_instance = MagicMock()
        vc_instance.get_distinct_repos.return_value = ["repo_a", "repo_b"]
        vc_instance.count.return_value = 42
        mock_vc.return_value = vc_instance

        gc_instance = AsyncMock()
        gc_instance.execute_query.return_value = [{"repo": "repo_b"}, {"repo": "repo_c"}]
        mock_gc.return_value = gc_instance

        response = client.get("/api/repos")
        assert response.status_code == 200
        data = response.json()
        assert "repos" in data
        assert data["repos"] == ["repo_a", "repo_b", "repo_c"]
        assert data["vector_count"] == 42


def test_delete_repository_endpoint():
    with patch("src.web.routes.repos.get_shared_vector_client") as mock_vc, \
         patch("src.web.routes.repos.get_shared_graph_client", new_callable=AsyncMock) as mock_gc, \
         patch("src.web.routes.repos.delete_repo_data", new_callable=AsyncMock) as mock_delete_graph:
        
        vc_instance = MagicMock()
        mock_vc.return_value = vc_instance

        gc_instance = AsyncMock()
        mock_gc.return_value = gc_instance

        response = client.delete("/api/repos/AryanRacha/test-repo")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["repo_id"] == "AryanRacha/test-repo"
        assert data["deleted_graph"] is True
        assert data["deleted_vector"] is True

        mock_delete_graph.assert_called_once_with(gc_instance, repo_id="AryanRacha/test-repo", branch=None)
        vc_instance.delete.assert_called_once_with(where={"repo": "AryanRacha/test-repo"})


def test_delete_repository_with_branch():
    with patch("src.web.routes.repos.get_shared_vector_client") as mock_vc, \
         patch("src.web.routes.repos.get_shared_graph_client", new_callable=AsyncMock) as mock_gc, \
         patch("src.web.routes.repos.delete_repo_data", new_callable=AsyncMock) as mock_delete_graph:
        
        vc_instance = MagicMock()
        mock_vc.return_value = vc_instance

        gc_instance = AsyncMock()
        mock_gc.return_value = gc_instance

        response = client.delete("/api/repos/AryanRacha/test-repo?branch=dev")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["branch"] == "dev"

        mock_delete_graph.assert_called_once_with(gc_instance, repo_id="AryanRacha/test-repo", branch="dev")
        vc_instance.delete.assert_called_once_with(where={"$and": [{"repo": "AryanRacha/test-repo"}, {"branch": "dev"}]})
