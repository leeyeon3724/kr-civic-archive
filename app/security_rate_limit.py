from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

redis_module: Any | None
RedisBaseError: type[Exception]
RedisNoScriptError: type[Exception]

try:
    import redis as redis_module
    from redis.exceptions import NoScriptError as RedisNoScriptError
    from redis.exceptions import RedisError as RedisBaseError
except ImportError:  # pragma: no cover - exercised only when redis is unavailable.
    redis_module = None

    class _RedisBaseError(Exception):
        pass

    class _RedisNoScriptError(_RedisBaseError):
        pass

    RedisBaseError = _RedisBaseError
    RedisNoScriptError = _RedisNoScriptError

# Backward-compatible aliases for runtime integrations.
redis = redis_module
RedisError = RedisBaseError
NoScriptError = RedisNoScriptError

logger = logging.getLogger("civic_archive.security")


class InMemoryRateLimiter:
    """Fixed-window limiter keyed by client identity."""

    def __init__(self, requests_per_minute: int) -> None:
        self.requests_per_minute = max(0, requests_per_minute)
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[int, int]] = {}

    @property
    def enabled(self) -> bool:
        return self.requests_per_minute > 0

    def allow(self, key: str) -> bool:
        if not self.enabled:
            return True

        now_window = int(time.time() // 60)
        with self._lock:
            prev_window, count = self._windows.get(key, (now_window, 0))
            if prev_window != now_window:
                prev_window, count = now_window, 0

            count += 1
            self._windows[key] = (prev_window, count)
            self._prune(now_window)
            return count <= self.requests_per_minute

    def _prune(self, now_window: int) -> None:
        if len(self._windows) < 4096:
            return
        min_window = now_window - 1
        self._windows = {k: v for k, v in self._windows.items() if v[0] >= min_window}


class RedisRateLimiter:
    """Redis-backed fixed-window limiter keyed by client identity."""

    _WINDOW_SCRIPT = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
  redis.call("EXPIRE", KEYS[1], tonumber(ARGV[1]))
end
return current
"""

    def __init__(
        self,
        *,
        requests_per_minute: int,
        redis_url: str,
        key_prefix: str,
        window_seconds: int,
        failure_cooldown_seconds: int,
        fail_open: bool,
        monotonic: Callable[[], float] | None = None,
        redis_dependency: Any | None = redis,
        redis_base_error: type[Exception] = RedisBaseError,
        redis_no_script_error: type[Exception] = RedisNoScriptError,
    ) -> None:
        self.requests_per_minute = max(0, requests_per_minute)
        self.key_prefix = key_prefix
        self.window_seconds = max(1, window_seconds)
        self.failure_cooldown_seconds = max(1, int(failure_cooldown_seconds))
        self.fail_open = bool(fail_open)
        self._monotonic = monotonic or time.monotonic
        self._script_sha: str | None = None
        self._client: Any | None = None
        self._degraded_until = 0.0
        self._redis_base_error = redis_base_error
        self._redis_no_script_error = redis_no_script_error

        if not self.enabled:
            return

        if redis_dependency is None:
            raise RuntimeError("redis package is required for RATE_LIMIT_BACKEND=redis.")

        self._client = redis_dependency.Redis.from_url(
            redis_url,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
            decode_responses=False,
        )

    @property
    def enabled(self) -> bool:
        return self.requests_per_minute > 0

    def allow(self, key: str) -> bool:
        if not self.enabled:
            return True
        if self._client is None:
            return True

        now = self._monotonic()
        if now < self._degraded_until:
            return self.fail_open

        bucket = int(time.time() // 60)
        redis_key = f"{self.key_prefix}:{bucket}:{key}"

        try:
            current = int(self._eval_counter(redis_key))
        except self._redis_base_error:
            self._degraded_until = now + float(self.failure_cooldown_seconds)
            logger.warning(
                "rate_limit_redis_error",
                extra={
                    "fail_open": self.fail_open,
                    "cooldown_seconds": self.failure_cooldown_seconds,
                },
            )
            return self.fail_open

        self._degraded_until = 0.0
        return current <= self.requests_per_minute

    def _eval_counter(self, redis_key: str) -> int:
        assert self._client is not None
        if self._script_sha is None:
            self._script_sha = self._client.script_load(self._WINDOW_SCRIPT)

        try:
            return int(self._client.evalsha(self._script_sha, 1, redis_key, self.window_seconds))
        except self._redis_no_script_error:
            return int(self._client.eval(self._WINDOW_SCRIPT, 1, redis_key, self.window_seconds))


def build_rate_limiter(
    config: Any,
    *,
    redis_rate_limiter_cls: type[RedisRateLimiter] = RedisRateLimiter,
    in_memory_rate_limiter_cls: type[InMemoryRateLimiter] = InMemoryRateLimiter,
) -> InMemoryRateLimiter | RedisRateLimiter:
    if config.rate_limit_backend == "redis":
        redis_url = (config.REDIS_URL or "").strip()
        if not redis_url:
            raise RuntimeError("RATE_LIMIT_BACKEND=redis requires REDIS_URL to be set.")
        return redis_rate_limiter_cls(
            requests_per_minute=config.RATE_LIMIT_PER_MINUTE,
            redis_url=redis_url,
            key_prefix=config.RATE_LIMIT_REDIS_PREFIX,
            window_seconds=config.RATE_LIMIT_REDIS_WINDOW_SECONDS,
            failure_cooldown_seconds=config.RATE_LIMIT_REDIS_FAILURE_COOLDOWN_SECONDS,
            fail_open=config.RATE_LIMIT_FAIL_OPEN,
        )
    if config.rate_limit_backend == "memory":
        return in_memory_rate_limiter_cls(config.RATE_LIMIT_PER_MINUTE)
    raise RuntimeError("RATE_LIMIT_BACKEND must be one of: memory, redis.")


def check_rate_limit_backend_health(
    config: Any,
    *,
    redis_dependency: Any | None = redis,
    redis_base_error: type[Exception] = RedisBaseError,
) -> tuple[bool, str | None]:
    backend = config.rate_limit_backend
    if backend == "memory":
        return True, "memory backend"

    if config.RATE_LIMIT_PER_MINUTE <= 0:
        return True, "rate limit disabled"

    redis_url = (config.REDIS_URL or "").strip()
    if not redis_url:
        return False, "REDIS_URL is not set"
    if redis_dependency is None:
        return False, "redis package is not available"

    try:
        client = redis_dependency.Redis.from_url(
            redis_url,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
            decode_responses=False,
        )
        client.ping()
        return True, None
    except redis_base_error as exc:
        return False, str(exc)
