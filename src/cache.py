"""Simple JSON file cache with TTL support."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

CACHE_DIR = Path.home() / ".cache" / "substack-friend-finder"
CACHE_FILE = CACHE_DIR / "cache.json"
DEFAULT_TTL = 86400  # 24 hours


class Cache:
    """Simple JSON file cache."""

    def __init__(self, ttl: int = DEFAULT_TTL):
        self.ttl = ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load cache from disk."""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r") as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._cache = {}

    def _save(self) -> None:
        """Save cache to disk."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(self._cache, f, indent=2)

    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache if it exists and hasn't expired."""
        if key not in self._cache:
            return None

        entry = self._cache[key]
        if time.time() > entry.get("expires", 0):
            del self._cache[key]
            return None

        return entry.get("value")

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in cache with optional custom TTL."""
        self._cache[key] = {
            "value": value,
            "expires": time.time() + (ttl or self.ttl),
        }
        self._save()

    def clear(self) -> None:
        """Clear all cached data."""
        self._cache = {}
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()


# Global cache instance
cache = Cache()
