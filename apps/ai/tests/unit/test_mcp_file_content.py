import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from src.mcp.tools import tool_get_file_content


@pytest.mark.asyncio
async def test_tool_get_file_content_uses_httpx_async():
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.text = "print('hello from async github')\nline 2"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("urllib.request.urlopen") as mock_urllib:

        mock_get.return_value = mock_response

        res_str = await tool_get_file_content(
            repo_id="owner/repo",
            file_path="main.py",
            branch="main",
        )

        assert mock_get.called, "httpx.AsyncClient.get should be called for remote fetching"
        assert not mock_urllib.called, "urllib.request should never be called"

        res = json.loads(res_str)
        assert res["file_path"] == "main.py"
        assert res["lines_count"] == 2
        assert "print('hello from async github')" in res["content"]
        assert res["source"] == "github_remote"


@pytest.mark.asyncio
async def test_tool_get_file_content_fallback_on_404():
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 404
    mock_response.text = "Not Found"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        res_str = await tool_get_file_content(
            repo_id="owner/repo",
            file_path="nonexistent.py",
            branch="main",
        )

        res = json.loads(res_str)
        assert "error" in res
        assert "not found" in res["error"].lower()
