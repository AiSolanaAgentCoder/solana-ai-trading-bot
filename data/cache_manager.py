"""
In-memory cache manager with TTL support.

Provides a unified caching interface using an in-memory LRU cache.
No external services (Redis etc.) required — fully self-contained.
Cache entries are keyed by a namespace + identifier and honour a
per-namespace TTL.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class _InMemoryCache:
    """Simple in-memory LRU-ish cache with TTL support."""

    def __init__(self, max_size: int = 4096) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._max_size = max_size

    async def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        expiry, value = entry
        if time.time() > expiry:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if len(self._store) >= self._max_size:
            # Evict oldest 25 %
            sorted_keys = sorted(self._store, key=lambda k: self._store[k][0])
            for k in sorted_keys[: self._max_size // 4]:
                del self._store[k]
        self._store[key] = (time.time() + ttl, value)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def clear(self) -> None:
        self._store.clear()

    async def close(self) -> None:
        self._store.clear()


class CacheManager:
    """In-memory cache with TTL and namespace support.

    Usage:
        cache = CacheManager()
        await cache.initialize()
        await cache.set("prices", "SOL", 142.5, ttl=15)
        price = await cache.get("prices", "SOL")
    """

    def __init__(self) -> None:
        self._memory = _InMemoryCache()
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize the in-memory cache."""
        logger.info("cache.initialized", backend="in-memory")

    def _build_key(self, namespace: str, identifier: str) -> str:
        return f"solai:{namespace}:{identifier}"

    async def get(self, namespace: str, identifier: str) -> Optional[Any]:
        """Retrieve a cached value."""
        key = self._build_key(namespace, identifier)
        try:
            return await self._memory.get(key)
        except Exception as exc:
            logger.error("cache.get_error", key=key, error=str(exc))
            return None

    async def set(
        self, namespace: str, identifier: str, value: Any, ttl: Optional[int] = None
    ) -> None:
        """Store a value with optional TTL."""
        key = self._build_key(namespace, identifier)
        if ttl is None:
            ttl_map = {
                "rpc": self._settings.cache_ttl_rpc,
                "prices": self._settings.cache_ttl_price,
                "predictions": self._settings.cache_ttl_prediction,
                "metadata": self._settings.cache_ttl_metadata,
            }
            ttl = ttl_map.get(namespace, 300)

        try:
            await self._memory.set(key, value, ttl)
        except Exception as exc:
            logger.error("cache.set_error", key=key, error=str(exc))

    async def delete(self, namespace: str, identifier: str) -> None:
        """Remove a specific cache entry."""
        key = self._build_key(namespace, identifier)
        try:
            await self._memory.delete(key)
        except Exception as exc:
            logger.error("cache.delete_error", key=key, error=str(exc))

    async def invalidate_namespace(self, namespace: str) -> None:
        """Invalidate all entries in a namespace."""
        prefix = f"solai:{namespace}:"
        keys_to_delete = [
            k for k in list(self._memory._store.keys()) if k.startswith(prefix)
        ]
        for key in keys_to_delete:
            del self._memory._store[key]
        if keys_to_delete:
            logger.info("cache.namespace_invalidated", namespace=namespace,
                       count=len(keys_to_delete))

    async def close(self) -> None:
        """Shut down cache gracefully."""
        await self._memory.close()
        logger.info("cache.closed")
