"""Unit tests for app.cache.ReadCache."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from app.cache import ReadCache


# ---------------------------------------------------------------------------
# No-op behaviour (disabled)
# ---------------------------------------------------------------------------


def test_read_cache_is_inactive_when_ttl_is_zero():
    cache = ReadCache(redis_url="redis://localhost:6379/0", ttl_seconds=0)
    assert not cache.is_active


def test_read_cache_is_inactive_when_redis_url_is_none():
    cache = ReadCache(redis_url=None, ttl_seconds=60)
    assert not cache.is_active


def test_read_cache_get_returns_none_when_inactive():
    cache = ReadCache(redis_url=None, ttl_seconds=0)
    assert cache.get("any-key") is None


def test_read_cache_set_is_noop_when_inactive():
    cache = ReadCache(redis_url=None, ttl_seconds=0)
    cache.set("any-key", {"data": 1})  # must not raise


def test_read_cache_invalidate_prefix_is_noop_when_inactive():
    cache = ReadCache(redis_url=None, ttl_seconds=0)
    cache.invalidate_prefix("news")  # must not raise


# ---------------------------------------------------------------------------
# Key builder
# ---------------------------------------------------------------------------


def test_read_cache_key_joins_parts_with_prefix():
    key = ReadCache.key("news", "list", "source=abc", "page=1")
    assert key == "civic_archive:read:news:list:source=abc:page=1"


def test_read_cache_key_single_part():
    assert ReadCache.key("health") == "civic_archive:read:health"


# ---------------------------------------------------------------------------
# Active cache with mocked Redis client
# ---------------------------------------------------------------------------


def _make_active_cache(ttl: int = 30) -> tuple[ReadCache, MagicMock]:
    """Return a ReadCache instance backed by a mock Redis client."""
    mock_client = MagicMock()
    with patch("redis.from_url", return_value=mock_client):
        import redis  # noqa: F401 — ensure patch target exists

        cache = ReadCache(redis_url="redis://localhost:6379/0", ttl_seconds=ttl)
    # Inject the mock directly (patch already captured it during __init__)
    cache._client = mock_client
    return cache, mock_client


def test_read_cache_get_returns_deserialized_value():
    cache, mock_client = _make_active_cache()
    mock_client.get.return_value = '{"items": [1, 2]}'

    result = cache.get("some-key")

    assert result == {"items": [1, 2]}
    mock_client.get.assert_called_once_with("some-key")


def test_read_cache_get_returns_none_on_cache_miss():
    cache, mock_client = _make_active_cache()
    mock_client.get.return_value = None

    assert cache.get("missing-key") is None


def test_read_cache_get_returns_none_and_logs_on_redis_error():
    cache, mock_client = _make_active_cache()
    mock_client.get.side_effect = ConnectionError("redis down")

    result = cache.get("some-key")

    assert result is None  # fails open


def test_read_cache_set_calls_setex_with_ttl():
    cache, mock_client = _make_active_cache(ttl=120)
    cache.set("k", {"total": 5})

    args = mock_client.setex.call_args
    assert args[0][0] == "k"
    assert args[0][1] == 120
    assert '"total": 5' in args[0][2]


def test_read_cache_set_is_silent_on_redis_error():
    cache, mock_client = _make_active_cache()
    mock_client.setex.side_effect = ConnectionError("redis down")

    cache.set("k", {"data": 1})  # must not raise


def test_read_cache_invalidate_prefix_scans_and_deletes():
    cache, mock_client = _make_active_cache()
    mock_client.scan.side_effect = [
        (0, ["civic_archive:read:news:k1", "civic_archive:read:news:k2"]),
    ]

    cache.invalidate_prefix("news")

    mock_client.scan.assert_called_once_with(0, match="civic_archive:read:news:*", count=100)
    mock_client.delete.assert_called_once_with(
        "civic_archive:read:news:k1", "civic_archive:read:news:k2"
    )


def test_read_cache_invalidate_prefix_handles_pagination():
    cache, mock_client = _make_active_cache()
    mock_client.scan.side_effect = [
        (42, ["civic_archive:read:news:k1"]),
        (0, ["civic_archive:read:news:k2"]),
    ]

    cache.invalidate_prefix("news")

    assert mock_client.scan.call_count == 2
    assert mock_client.delete.call_count == 2


def test_read_cache_close_calls_client_close():
    cache, mock_client = _make_active_cache()
    cache.close()
    mock_client.close.assert_called_once()
