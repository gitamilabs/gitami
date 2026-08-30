"""Tests for Vector Store Ingestion Cache Manager."""

import tempfile
from pathlib import Path
from ai_service.vector.cache import VectorCacheManager


def test_cache_key_generation():
    mgr = VectorCacheManager(cache_dir=Path("./tmp_test_cache"))
    key1 = mgr.compute_cache_key("owner/repo", "main", "abc12345", "fast")
    key2 = mgr.compute_cache_key("owner/repo", "main", "abc12345", "fast")
    key_rich = mgr.compute_cache_key("owner/repo", "main", "abc12345", "rich")
    
    assert key1 == key2
    assert key1 != key_rich


def test_cache_miss_and_hit_lifecycle():
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = VectorCacheManager(cache_dir=Path(tmp_dir))

        # 1. Miss initially
        res = mgr.is_cached("org/project", "main", "commit_sha_123", "fast")
        assert res is None

        # 2. Save manifest
        mgr.save_manifest(
            repo_id="org/project",
            branch="main",
            commit_hash="commit_sha_123",
            extraction_mode="fast",
            manifest_data={"symbols_count": 42, "edges_count": 10, "vector_entries_count": 50},
        )

        # 3. Hit now
        cached = mgr.is_cached("org/project", "main", "commit_sha_123", "fast", min_entries=5)
        assert cached is not None
        assert cached["symbols_count"] == 42
        assert cached["vector_entries_count"] == 50

        # 4. Invalidation
        invalidated = mgr.invalidate(repo_id="org/project")
        assert invalidated == 1
        assert mgr.is_cached("org/project", "main", "commit_sha_123", "fast") is None
