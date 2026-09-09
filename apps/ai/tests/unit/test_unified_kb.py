import unittest
import os
import tempfile
import shutil
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.vector.client import VectorKBClient
from src.kb_unified import UnifiedKB


class TestUnifiedKB(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]

        self.vector_client = VectorKBClient(persist_directory=self.test_dir, api_key="")
        self.mock_graph_client = AsyncMock()
        self.unified = UnifiedKB(neo4j_client=self.mock_graph_client, vector_client=self.vector_client)

    def tearDown(self):
        del self.unified
        del self.vector_client
        import time
        time.sleep(0.5)
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except Exception:
            pass

    async def test_hybrid_search(self):
        # Ingest a vector entry
        self.vector_client.add_code_entry(
            repo="test/repo",
            branch="main",
            file_path="src/utils.py",
            symbol="calculate_risk",
            signature="def calculate_risk():",
            description="Computes risk score for code review.",
            commit_hash="c1"
        )

        # Mock graph query response
        self.mock_graph_client.execute_query.return_value = [
            {"symbol": {"name": "calculate_risk", "qualified_name": "src/utils.py::calculate_risk", "kind": "function"}}
        ]

        result = await self.unified.hybrid_search(
            repo_id="test/repo",
            query_text="risk",
            branch="main",
            n_results=5
        )

        self.assertEqual(result["repo_id"], "test/repo")
        self.assertEqual(result["query"], "risk")
        self.assertIn("vector_hits", result)
        self.assertIn("graph_hits", result)
        self.assertEqual(len(result["graph_hits"]), 1)
        self.assertEqual(result["graph_hits"][0]["name"], "calculate_risk")


if __name__ == '__main__':
    unittest.main()
