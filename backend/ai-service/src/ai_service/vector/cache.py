"""Vector Store Ingestion Caching Manager."""

import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class VectorCacheManager:
    """Manages disk-based ingestion cache manifests keyed on repository commit and extraction variant."""

    def __init__(self, cache_dir: Optional[str | Path] = None):
        if cache_dir is None:
            self.cache_dir = Path("./chroma_db/.cache/vector_manifests")
        else:
            self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def compute_cache_key(
        self,
        repo_id: str,
        branch: str,
        commit_hash: str,
        extraction_mode: str = "fast",
    ) -> str:
        """Derive a deterministic cache key from document identifiers and extraction variant."""
        raw_key = f"{repo_id}::{branch}::{commit_hash}::{extraction_mode}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:24]

    def _manifest_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"

    def is_cached(
        self,
        repo_id: str,
        branch: str,
        commit_hash: str,
        extraction_mode: str = "fast",
        min_entries: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """Check if an ingestion manifest exists and meets the minimum chunk threshold.
        
        Returns the manifest dict if valid, or None if a cache miss.
        """
        # Skip cache for HEAD / empty commit markers to ensure fresh indexing during active dev
        if not commit_hash or commit_hash.upper() == "HEAD":
            return None

        cache_key = self.compute_cache_key(repo_id, branch, commit_hash, extraction_mode)
        path = self._manifest_path(cache_key)

        if not path.exists():
            return None

        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            vector_count = manifest.get("vector_entries_count", 0)
            
            # Skip cache for very small documents below threshold
            if vector_count < min_entries:
                logger.info(f"Cache skipped for small document ({vector_count} entries < {min_entries} threshold)")
                return None

            logger.info(f"Vector store cache HIT for {repo_id}@{commit_hash} (key: {cache_key})")
            return manifest
        except Exception as e:
            logger.warning(f"Failed to read cache manifest {path}: {e}")
            return None

    def save_manifest(
        self,
        repo_id: str,
        branch: str,
        commit_hash: str,
        extraction_mode: str,
        manifest_data: Dict[str, Any],
    ) -> None:
        """Atomically persist an ingestion manifest to disk."""
        if not commit_hash or commit_hash.upper() == "HEAD":
            return

        cache_key = self.compute_cache_key(repo_id, branch, commit_hash, extraction_mode)
        path = self._manifest_path(cache_key)

        data = {
            "cache_key": cache_key,
            "repo_id": repo_id,
            "branch": branch,
            "commit_hash": commit_hash,
            "extraction_mode": extraction_mode,
            **manifest_data,
        }

        try:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.info(f"Vector store cache manifest saved: {path.name}")
        except Exception as e:
            logger.warning(f"Failed to write vector cache manifest {path}: {e}")

    def invalidate(self, repo_id: Optional[str] = None, branch: Optional[str] = None) -> int:
        """Invalidate cache entries for a given repository."""
        count = 0
        for p in self.cache_dir.glob("*.json"):
            try:
                manifest = json.loads(p.read_text(encoding="utf-8"))
                if repo_id and manifest.get("repo_id") != repo_id:
                    continue
                if branch and manifest.get("branch") != branch:
                    continue
                p.unlink()
                count += 1
            except Exception:
                pass
        return count
