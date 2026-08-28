import unittest
import json
import os
import tempfile
import shutil
from unittest.mock import AsyncMock

from ai_service.vector.client import VectorKBClient
from ai_service.mcp.tools import tool_vector_search, tool_hybrid_search


class TestMCPVectorTools(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]

        self.vector_client = VectorKBClient(persist_directory=self.test_dir, api_key="")
        self.mock_graph_client = AsyncMock()

    def tearDown(self):
        del self.vector_client
        import time
        time.sleep(0.5)
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except Exception:
            pass

    async def test_tool_vector_search(self):
        self.vector_client.add_code_entry(
            repo="org/repo",
            branch="main",
            file_path="auth.py",
            symbol="login",
            signature="def login(user, password):",
            description="Authenticates user against system database.",
            commit_hash="abc1234"
        )

        res_str = await tool_vector_search(
            vector_client=self.vector_client,
            query_text="auth",
            repo_id="org/repo",
            n_results=3
        )

        res = json.loads(res_str)
        self.assertEqual(res["query"], "auth")
        self.assertIn("results", res)

    async def test_tool_hybrid_search(self):
        self.mock_graph_client.execute_query.return_value = [
            {"symbol": {"name": "login", "qualified_name": "auth.py::login"}}
        ]

        res_str = await tool_hybrid_search(
            graph_client=self.mock_graph_client,
            vector_client=self.vector_client,
            repo_id="org/repo",
            query_text="login",
            branch="main"
        )

        res = json.loads(res_str)
        self.assertIn("vector_hits", res)
        self.assertIn("graph_hits", res)


if __name__ == '__main__':
    unittest.main()
