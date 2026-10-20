"""API Key Rotator for free-tier resilience against rate limits and quota exhaustion."""

import asyncio
import logging
import os
from typing import Callable, List, Optional, TypeVar, Any

logger = logging.getLogger(__name__)

T = TypeVar("T")


def parse_keys(raw: Optional[str]) -> List[str]:
    """Parse comma-separated or space-separated API keys into a cleaned list."""
    if not raw:
        return []
    keys = []
    for token in raw.replace(";", ",").split(","):
        cleaned = token.strip()
        if cleaned:
            keys.append(cleaned)
    return keys


class APIKeyRotator:
    """
    Thread-safe / async key rotator.
    Maintains a pool of API keys, tracks rotation indices,
    and automatically switches to the next available key when a rate limit occurs.
    """

    def __init__(self, service_name: str, keys: Optional[List[str]] = None):
        self.service_name = service_name
        self.keys: List[str] = [k for k in (keys or []) if k]
        self._current_index: int = 0
        self._lock = asyncio.Lock()

    @property
    def key_count(self) -> int:
        return len(self.keys)

    @property
    def has_keys(self) -> bool:
        return len(self.keys) > 0

    def get_current_key(self) -> Optional[str]:
        """Return the currently active API key, or None if no keys configured."""
        if not self.keys:
            return None
        return self.keys[self._current_index % len(self.keys)]

    async def rotate(self, reason: str = "rate limit") -> str:
        """Switch to next key in the pool and return it."""
        async with self._lock:
            if not self.keys:
                return ""
            old_idx = self._current_index % len(self.keys)
            self._current_index = (self._current_index + 1) % len(self.keys)
            new_idx = self._current_index
            masked_new = self.keys[new_idx][:4] + "..." + self.keys[new_idx][-4:] if len(self.keys[new_idx]) > 8 else "***"
            logger.warning(
                f"[{self.service_name}] Rotating API key due to {reason}: "
                f"switched from key #{old_idx + 1} to key #{new_idx + 1} ({masked_new})."
            )
            return self.keys[new_idx]

    @classmethod
    def from_env(cls, service_name: str, primary_env: str, list_env: str) -> "APIKeyRotator":
        """Instantiate rotator from environment variables."""
        raw_list = os.environ.get(list_env, "")
        keys = parse_keys(raw_list)

        primary = os.environ.get(primary_env, "").strip()
        if primary and primary not in keys:
            keys.insert(0, primary)

        return cls(service_name=service_name, keys=keys)
