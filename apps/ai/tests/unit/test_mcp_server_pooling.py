import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.mcp import server


@pytest.mark.asyncio
async def test_mcp_server_tools_reuse_shared_clients():
    mock_shared_graph = AsyncMock()
    mock_shared_vector = MagicMock()

    with patch("src.mcp.server.get_shared_graph_client", new_callable=AsyncMock) as mock_get_graph, \
         patch("src.mcp.server.get_shared_vector_client") as mock_get_vector, \
         patch("src.mcp.server.tool_get_repo_structure", new_callable=AsyncMock) as mock_repo_struct, \
         patch("src.mcp.server.tool_get_symbol_details", new_callable=AsyncMock) as mock_sym_details, \
         patch("src.mcp.server.tool_get_blast_radius", new_callable=AsyncMock) as mock_blast, \
         patch("src.mcp.server.tool_get_file_dependencies", new_callable=AsyncMock) as mock_file_deps, \
         patch("src.mcp.server.tool_search_symbols", new_callable=AsyncMock) as mock_search_syms, \
         patch("src.mcp.server.tool_vector_search", new_callable=AsyncMock) as mock_vec_search, \
         patch("src.mcp.server.tool_hybrid_search", new_callable=AsyncMock) as mock_hyb_search:

        mock_get_graph.return_value = mock_shared_graph
        mock_get_vector.return_value = mock_shared_vector

        # 1. get_repo_structure
        await server.get_repo_structure(repo_id="test/repo", branch="main")
        assert mock_get_graph.called
        mock_repo_struct.assert_awaited_once_with(mock_shared_graph, repo_id="test/repo", branch="main")

        # 2. get_symbol_details
        await server.get_symbol_details(repo_id="test/repo", qualified_name="foo", branch="main")
        mock_sym_details.assert_awaited_once_with(mock_shared_graph, repo_id="test/repo", qualified_name="foo", branch="main")

        # 3. get_blast_radius
        await server.get_blast_radius(repo_id="test/repo", changed_symbols=["foo"], branch="main")
        mock_blast.assert_awaited_once_with(mock_shared_graph, repo_id="test/repo", changed_symbols=["foo"], branch="main")

        # 4. get_file_dependencies
        await server.get_file_dependencies(repo_id="test/repo", file_path="main.py", branch="main")
        mock_file_deps.assert_awaited_once_with(mock_shared_graph, repo_id="test/repo", file_path="main.py", branch="main")

        # 5. search_symbols
        await server.search_symbols(repo_id="test/repo", query="foo", branch="main")
        mock_search_syms.assert_awaited_once_with(mock_shared_graph, repo_id="test/repo", query_str="foo", branch="main")

        # 6. vector_search
        await server.vector_search(query="foo", repo_id="test/repo", n_results=5)
        assert mock_get_vector.called
        mock_vec_search.assert_awaited_once_with(mock_shared_vector, query_text="foo", repo_id="test/repo", n_results=5)

        # 7. hybrid_search
        await server.hybrid_search(repo_id="test/repo", query="foo", branch="main", n_results=5, project_id="proj-123")
        mock_hyb_search.assert_awaited_once_with(
            mock_shared_graph,
            mock_shared_vector,
            repo_id="test/repo",
            query_text="foo",
            branch="main",
            n_results=5,
            project_id="proj-123",
        )
