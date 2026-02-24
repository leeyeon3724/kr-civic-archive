"""Read-through cache backed by Redis.

Usage
-----
When ``READ_CACHE_TTL_SECONDS`` is 0 (the default) or ``REDIS_URL`` is not
set, ``ReadCache`` operates as a transparent no-op — no Redis connection is
established and every ``get`` returns ``None``.  No code path needs to
special-case whether caching is enabled; callers simply check the return
value of ``get`` and fall through to the DB on a miss.

Cache keys
----------
Build keys with ``ReadCache.key(*parts)`` to produce a colon-delimited,
prefix-scoped string, e.g.::

    cache.key("news", "list", "source=abc", "page=1")
    # → "civic_archive:read:news:list:source=abc:page=1"

Invalidation
------------
On write operations call ``invalidate_prefix(domain)`` (e.g. ``"news"``) to
delete all cached keys under that domain prefix.  This uses Redis ``SCAN``
with ``MATCH`` to avoid blocking the server with ``KEYS``.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("civic_archive.cache")

_KEY_PREFIX = "civic_archive:read"


class ReadCache:
    def __init__(self, *, redis_url: str | None, ttl_seconds: int) -> None:
        self._ttl = max(0, ttl_seconds)
        self._client: Any = None
        if self._ttl > 0 and redis_url:
            try:
                import redis as _redis

                self._client = _redis.from_url(redis_url, decode_responses=True)
            except ImportError:
                logger.warning("cache_redis_import_failed", extra={"reason": "redis package unavailable"})
            except Exception as exc:
                logger.warning("cache_redis_connect_failed", extra={"error": str(exc)})

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self._client is not None and self._ttl > 0

    @staticmethod
    def key(*parts: str) -> str:
        return ":".join([_KEY_PREFIX, *parts])

    def get(self, cache_key: str) -> Any | None:
        if not self.is_active:
            return None
        try:
            raw = self._client.get(cache_key)
            return json.loads(raw) if raw is not None else None
        except Exception as exc:
            logger.warning("cache_get_failed", extra={"key": cache_key, "error": str(exc)})
            return None

    def set(self, cache_key: str, value: Any) -> None:
        if not self.is_active:
            return
        try:
            self._client.setex(cache_key, self._ttl, json.dumps(value, default=str))
        except Exception as exc:
            logger.warning("cache_set_failed", extra={"key": cache_key, "error": str(exc)})

    def invalidate_prefix(self, domain: str) -> None:
        """Delete all keys whose name starts with ``<prefix>:<domain>:``."""
        if not self.is_active:
            return
        pattern = f"{_KEY_PREFIX}:{domain}:*"
        try:
            cursor = 0
            while True:
                cursor, keys = self._client.scan(cursor, match=pattern, count=100)
                if keys:
                    self._client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:
            logger.warning("cache_invalidate_failed", extra={"pattern": pattern, "error": str(exc)})

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
