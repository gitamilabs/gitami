import unittest
import os
import tempfile
import shutil
from src.vector.client import VectorKBClient as VectorDBClient, ContentType

class TestVectorDBClient(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # We will use a dummy API key to avoid calling the real API during basic logic tests
        # However, to avoid network errors from Gemini embedding model initialization,
        # we can let it fallback to default by passing api_key="" and ensuring GEMINI_API_KEY is not set.
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]
            
        self.client = VectorDBClient(persist_directory=self.test_dir, api_key="")
        try:
            self.client.collection.delete(where={"repo": "test/repo"})
        except Exception:
            pass

    def tearDown(self):
        # Close chroma to release file locks before deleting temp dir
        del self.client
        import time
        time.sleep(0.5)
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except Exception:
            pass

    def test_add_code_entry(self):
        self.client.add_code_entry(
            repo="test/repo",
            branch="main",
            file_path="src/main.py",
            symbol="my_func",
            signature="def my_func():",
            description="A test function",
            commit_hash="commit1"
        )
        
        results = self.client.collection.get(
            where={"repo": "test/repo"}
        )
        self.assertEqual(len(results["ids"]), 1)
        self.assertEqual(results["metadatas"][0]["content_type"], ContentType.CODE.value)
        self.assertEqual(results["metadatas"][0]["last_valid_commit"], "commit1")

    def test_roll_forward_commit(self):
        # Add an entry
        self.client.add_code_entry(
            repo="test/repo",
            branch="main",
            file_path="src/main.py",
            symbol="my_func",
            signature="def my_func():",
            description="A test function",
            commit_hash="commit1"
        )
        
        # Roll forward
        self.client.roll_forward_commit("test/repo", "main", "commit1", "commit2")
        
        results = self.client.collection.get(
            where={"repo": "test/repo"}
        )
        self.assertEqual(results["metadatas"][0]["last_valid_commit"], "commit2")
        self.assertEqual(results["metadatas"][0]["commit_hash"], "commit2")

    def test_delete_stale_entries(self):
        # Add two entries
        self.client.add_code_entry(
            repo="test/repo",
            branch="main",
            file_path="src/main.py",
            symbol="func1",
            signature="def func1():",
            description="desc",
            commit_hash="commit1"
        )
        self.client.add_code_entry(
            repo="test/repo",
            branch="main",
            file_path="src/main.py",
            symbol="func2",
            signature="def func2():",
            description="desc",
            commit_hash="commit2"
        )
        
        # Assume roll forward left func1 at commit1, and func2 is at commit2.
        self.client.delete_stale_entries("test/repo", "main", "commit2")
        
        results = self.client.collection.get(
            where={"repo": "test/repo"}
        )
        self.assertEqual(len(results["ids"]), 1)
        self.assertEqual(results["metadatas"][0]["symbol"], "func2")

if __name__ == '__main__':
    unittest.main()
