"""Simple file-based cache for API responses."""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default cache directory
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "confluence-markdown"

# Default TTL in seconds (1 hour)
DEFAULT_TTL = 3600


class Cache:
    """Simple file-based cache with TTL support."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl: int = DEFAULT_TTL,
        enabled: bool = True,
    ):
        """
        Initialize cache.

        Args:
            cache_dir: Directory for cache files
            ttl: Time-to-live in seconds (default: 1 hour)
            enabled: Whether caching is enabled
        """
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.ttl = ttl
        self.enabled = enabled

        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, key: str) -> str:
        """Generate a safe filename from cache key."""
        return hashlib.md5(key.encode()).hexdigest()

    def _get_cache_path(self, key: str) -> Path:
        """Get full path for a cache key."""
        return self.cache_dir / f"{self._get_cache_key(key)}.json"

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if not self.enabled:
            return None

        cache_path = self._get_cache_path(key)
        if not cache_path.exists():
            return None

        try:
            with open(cache_path) as f:
                data = json.load(f)

            # Check TTL
            if time.time() - data.get("timestamp", 0) > self.ttl:
                logger.debug("Cache expired for key: %s", key[:50])
                cache_path.unlink(missing_ok=True)
                return None

            logger.debug("Cache hit for key: %s", key[:50])
            return data.get("value")

        except (json.JSONDecodeError, OSError) as e:
            logger.debug("Cache read error: %s", e)
            return None

    def set(self, key: str, value: Any) -> None:
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
        """
        if not self.enabled:
            return

        cache_path = self._get_cache_path(key)
        try:
            data = {
                "timestamp": time.time(),
                "key": key[:100],  # Store truncated key for debugging
                "value": value,
            }
            with open(cache_path, "w") as f:
                json.dump(data, f)
            logger.debug("Cached value for key: %s", key[:50])
        except (TypeError, OSError) as e:
            logger.debug("Cache write error: %s", e)

    def delete(self, key: str) -> None:
        """Delete a cached value."""
        if not self.enabled:
            return

        cache_path = self._get_cache_path(key)
        cache_path.unlink(missing_ok=True)

    def clear(self) -> int:
        """
        Clear all cached values.

        Returns:
            Number of cache files deleted
        """
        if not self.enabled or not self.cache_dir.exists():
            return 0

        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                count += 1
            except OSError:
                pass

        logger.info("Cleared %d cache files", count)
        return count

    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of expired entries removed
        """
        if not self.enabled or not self.cache_dir.exists():
            return 0

        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                if time.time() - data.get("timestamp", 0) > self.ttl:
                    cache_file.unlink()
                    count += 1
            except (json.JSONDecodeError, OSError):
                # Remove corrupted cache files
                cache_file.unlink(missing_ok=True)
                count += 1

        if count > 0:
            logger.debug("Cleaned up %d expired cache entries", count)
        return count
