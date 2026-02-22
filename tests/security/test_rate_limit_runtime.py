from __future__ import annotations

from unittest.mock import patch

import pytest
from conftest import StubResult, build_test_config
from fastapi.testclient import TestClient

from app import create_app


def test_metrics_not_rate_limited_when_only_rate_limit_is_configured(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(
            build_test_config(
                REQUIRE_API_KEY=False,
                REQUIRE_JWT=False,
                RATE_LIMIT_PER_MINUTE=1,
            )
        )

    with TestClient(app) as tc:
        first = tc.get("/metrics")
        second = tc.get("/metrics")

    assert first.status_code == 200
    assert second.status_code == 200


def test_rate_limit_enforced_for_protected_endpoint(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(
            build_test_config(
                RATE_LIMIT_PER_MINUTE=1,
            )
        )

    with TestClient(app) as tc:
        first = tc.post("/api/echo", json={"n": 1})
        assert first.status_code == 200

        second = tc.post("/api/echo", json={"n": 2})
        assert second.status_code == 429
        body = second.json()
        assert body["code"] == "RATE_LIMITED"
        assert body["message"] == "Too Many Requests"
        assert body.get("request_id")


def test_rate_limit_uses_xff_when_proxy_is_trusted(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(
            build_test_config(
                RATE_LIMIT_PER_MINUTE=1,
                TRUSTED_PROXY_CIDRS="127.0.0.1/32",
            )
        )

    with patch("app.security._remote_ip", return_value="127.0.0.1"), TestClient(app) as tc:
        first = tc.post("/api/echo", json={"n": 1}, headers={"X-Forwarded-For": "203.0.113.1"})
        second = tc.post("/api/echo", json={"n": 2}, headers={"X-Forwarded-For": "203.0.113.2"})
        assert first.status_code == 200
        assert second.status_code == 200


def test_rate_limit_ignores_xff_when_proxy_is_untrusted(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(
            build_test_config(
                RATE_LIMIT_PER_MINUTE=1,
                TRUSTED_PROXY_CIDRS="10.0.0.0/8",
            )
        )

    with patch("app.security._remote_ip", return_value="127.0.0.1"), TestClient(app) as tc:
        first = tc.post("/api/echo", json={"n": 1}, headers={"X-Forwarded-For": "203.0.113.1"})
        second = tc.post("/api/echo", json={"n": 2}, headers={"X-Forwarded-For": "203.0.113.2"})
        assert first.status_code == 200
        assert second.status_code == 429
        assert second.json()["code"] == "RATE_LIMITED"


def test_invalid_trusted_proxy_cidrs_are_rejected(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        with pytest.raises(RuntimeError):
            create_app(
                build_test_config(
                    RATE_LIMIT_PER_MINUTE=1,
                    TRUSTED_PROXY_CIDRS="not-a-cidr",
                )
            )


def test_rate_limit_backend_rejects_invalid_value(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        with pytest.raises(RuntimeError):
            create_app(
                build_test_config(
                    RATE_LIMIT_BACKEND="invalid-backend",
                    RATE_LIMIT_PER_MINUTE=1,
                )
            )


def test_rate_limit_redis_backend_requires_redis_url(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        with pytest.raises(RuntimeError):
            create_app(
                build_test_config(
                    RATE_LIMIT_BACKEND="redis",
                    RATE_LIMIT_PER_MINUTE=1,
                    REDIS_URL=None,
                )
            )


def test_rate_limit_redis_failure_cooldown_must_be_positive(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        with pytest.raises(RuntimeError):
            create_app(
                build_test_config(
                    RATE_LIMIT_REDIS_FAILURE_COOLDOWN_SECONDS=0,
                )
            )


def test_rate_limit_redis_backend_is_usable_with_custom_limiter(make_engine):
    class FakeRedisRateLimiter:
        def __init__(
            self,
            *,
            requests_per_minute: int,
            redis_url: str,
            key_prefix: str,
            window_seconds: int,
            failure_cooldown_seconds: int,
            fail_open: bool,
            monotonic=None,
        ) -> None:
            assert requests_per_minute == 1
            assert redis_url == "redis://localhost:6379/0"
            assert key_prefix == "test-prefix"
            assert window_seconds == 70
            assert failure_cooldown_seconds == 9
            assert fail_open is False
            assert monotonic is None
            self.enabled = True
            self.calls = 0

        def allow(self, _key: str) -> bool:
            self.calls += 1
            return self.calls <= 1

    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())), patch(
        "app.security.RedisRateLimiter",
        FakeRedisRateLimiter,
    ):
        app = create_app(
            build_test_config(
                RATE_LIMIT_BACKEND="redis",
                REDIS_URL="redis://localhost:6379/0",
                RATE_LIMIT_REDIS_PREFIX="test-prefix",
                RATE_LIMIT_REDIS_WINDOW_SECONDS=70,
                RATE_LIMIT_REDIS_FAILURE_COOLDOWN_SECONDS=9,
                RATE_LIMIT_FAIL_OPEN=False,
                RATE_LIMIT_PER_MINUTE=1,
            )
        )

    with TestClient(app) as tc:
        first = tc.post("/api/echo", json={"n": 1})
        assert first.status_code == 200

        second = tc.post("/api/echo", json={"n": 2})
        assert second.status_code == 429
