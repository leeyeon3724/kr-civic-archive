import asyncio
import logging
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import security_dependencies
from app import security_proxy
from app import security_rate_limit
from app.security_jwt import authorize_claims_for_request


def _rate_limit_config(**overrides):
    defaults = {
        "rate_limit_backend": "memory",
        "RATE_LIMIT_PER_MINUTE": 10,
        "REDIS_URL": "redis://localhost:6379/0",
        "RATE_LIMIT_REDIS_PREFIX": "civic_archive:rate_limit",
        "RATE_LIMIT_REDIS_WINDOW_SECONDS": 60,
        "RATE_LIMIT_REDIS_FAILURE_COOLDOWN_SECONDS": 30,
        "RATE_LIMIT_FAIL_OPEN": True,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_security_proxy_rejects_invalid_cidr():
    with pytest.raises(RuntimeError, match="Invalid TRUSTED_PROXY_CIDRS entry"):
        security_proxy.parse_trusted_proxy_networks(["not-a-cidr"])


def test_security_proxy_client_key_uses_xff_only_when_proxy_is_trusted():
    trusted_networks = security_proxy.parse_trusted_proxy_networks(["127.0.0.1/32"])
    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"X-Forwarded-For": "203.0.113.5"},
    )

    client = security_proxy.client_key(request, trusted_proxy_networks=trusted_networks)
    assert client == "203.0.113.5"


def test_security_proxy_client_key_ignores_xff_when_proxy_is_untrusted():
    trusted_networks = security_proxy.parse_trusted_proxy_networks(["10.0.0.0/8"])
    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"X-Forwarded-For": "203.0.113.5"},
    )

    client = security_proxy.client_key(request, trusted_proxy_networks=trusted_networks)
    assert client == "127.0.0.1"


def test_security_proxy_client_key_uses_first_hop_from_xff_chain():
    trusted_networks = security_proxy.parse_trusted_proxy_networks(["127.0.0.1/32"])
    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"X-Forwarded-For": " 203.0.113.5 , 198.51.100.7 "},
    )

    client = security_proxy.client_key(request, trusted_proxy_networks=trusted_networks)
    assert client == "203.0.113.5"


def test_security_proxy_client_key_ignores_invalid_first_xff_hop():
    trusted_networks = security_proxy.parse_trusted_proxy_networks(["127.0.0.1/32"])
    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"X-Forwarded-For": "unknown, 203.0.113.5"},
    )

    client = security_proxy.client_key(request, trusted_proxy_networks=trusted_networks)
    assert client == "127.0.0.1"


def test_security_proxy_client_key_supports_ipv6_hops():
    trusted_networks = security_proxy.parse_trusted_proxy_networks(["::1/128"])
    request = SimpleNamespace(
        client=SimpleNamespace(host="::1"),
        headers={"X-Forwarded-For": "2001:db8::1"},
    )

    client = security_proxy.client_key(request, trusted_proxy_networks=trusted_networks)
    assert client == "2001:db8::1"


def test_security_proxy_client_key_uses_request_id_for_client_resolution_when_client_is_missing():
    trusted_networks = security_proxy.parse_trusted_proxy_networks([])
    request = SimpleNamespace(
        client=None,
        headers={"X-Request-Id": "test-request-id"},
        state=SimpleNamespace(),
    )

    client = security_proxy.client_key(request, trusted_proxy_networks=trusted_networks)
    assert client == "request-id:test-request-id"


def test_security_proxy_client_key_uses_unknown_fallback_when_client_is_missing_and_no_headers():
    trusted_networks = security_proxy.parse_trusted_proxy_networks([])
    first_request = SimpleNamespace(
        client=None,
        headers={},
        state=SimpleNamespace(request_id="state-request-id-1"),
    )
    second_request = SimpleNamespace(
        client=None,
        headers={},
        state=SimpleNamespace(request_id="state-request-id-2"),
    )

    first_client = security_proxy.client_key(first_request, trusted_proxy_networks=trusted_networks)
    second_client = security_proxy.client_key(second_request, trusted_proxy_networks=trusted_networks)
    assert first_client == "request:unknown"
    assert second_client == "request:unknown"


def test_security_proxy_client_key_uses_x_real_ip_when_client_is_missing():
    trusted_networks = security_proxy.parse_trusted_proxy_networks([])
    request = SimpleNamespace(
        client=None,
        headers={"X-Real-IP": "198.51.100.50"},
        state=SimpleNamespace(),
    )

    client = security_proxy.client_key(request, trusted_proxy_networks=trusted_networks)
    assert client == "198.51.100.50"


def test_security_rate_limit_builds_memory_limiter():
    limiter = security_rate_limit.build_rate_limiter(_rate_limit_config(rate_limit_backend="memory"))
    assert isinstance(limiter, security_rate_limit.InMemoryRateLimiter)


def test_security_rate_limit_rejects_unknown_backend():
    with pytest.raises(RuntimeError, match="RATE_LIMIT_BACKEND must be one of: memory, redis."):
        security_rate_limit.build_rate_limiter(_rate_limit_config(rate_limit_backend="unknown"))


def test_security_rate_limit_redis_requires_url():
    with pytest.raises(RuntimeError, match="RATE_LIMIT_BACKEND=redis requires REDIS_URL to be set."):
        security_rate_limit.build_rate_limiter(
            _rate_limit_config(rate_limit_backend="redis", REDIS_URL=""),
        )


def test_security_rate_limit_health_reports_memory_backend():
    ok, reason = security_rate_limit.check_rate_limit_backend_health(
        _rate_limit_config(rate_limit_backend="memory"),
    )
    assert ok is True
    assert reason == "memory backend"


def test_security_rate_limit_redis_limiter_requires_package_when_enabled():
    with pytest.raises(RuntimeError, match="redis package is required for RATE_LIMIT_BACKEND=redis."):
        security_rate_limit.RedisRateLimiter(
            requests_per_minute=1,
            redis_url="redis://localhost:6379/0",
            key_prefix="test",
            window_seconds=60,
            failure_cooldown_seconds=30,
            fail_open=True,
            redis_dependency=None,
        )


def test_security_dependencies_api_key_rejects_invalid_header():
    dependency = security_dependencies.build_api_key_dependency(
        SimpleNamespace(REQUIRE_API_KEY=True, API_KEY="expected"),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(dependency(x_api_key="wrong"))
    assert exc_info.value.status_code == 401


def test_security_dependencies_jwt_dependency_uses_injected_jwt_handlers():
    seen = {}

    def fake_validate(token, _config):
        seen["token"] = token
        return {"sub": "user-1", "scope": "archive:write", "exp": 1735689600}

    def fake_authorize(request, claims, _config):
        seen["method"] = request.method
        seen["claims"] = claims

    dependency = security_dependencies.build_jwt_dependency(
        SimpleNamespace(REQUIRE_JWT=True),
        validate_jwt=fake_validate,
        authorize_claims=fake_authorize,
    )
    request = SimpleNamespace(method="POST", state=SimpleNamespace())

    asyncio.run(dependency(request, authorization="Bearer token-abc"))
    assert seen["token"] == "token-abc"
    assert seen["method"] == "POST"
    assert request.state.auth_claims["sub"] == "user-1"


def test_authorize_claims_logs_admin_role_bypass(caplog):
    config = SimpleNamespace(
        JWT_SCOPE_READ="archive:read",
        JWT_SCOPE_WRITE="archive:write",
        JWT_SCOPE_DELETE="archive:delete",
        JWT_ADMIN_ROLE="admin",
    )
    request = SimpleNamespace(method="POST", url=SimpleNamespace(path="/api/news"))
    claims = {"sub": "svc-account-1", "role": "admin", "scope": ""}

    with caplog.at_level(logging.INFO, logger="civic_archive.security"):
        authorize_claims_for_request(request, claims, config)

    audit_records = [r for r in caplog.records if r.message == "admin_role_access_granted"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record.__dict__.get("sub") == "svc-account-1"
    assert record.__dict__.get("admin_role") == "admin"
    assert record.__dict__.get("method") == "POST"
    assert record.__dict__.get("path") == "/api/news"


def test_authorize_claims_does_not_log_for_normal_scope_grant(caplog):
    config = SimpleNamespace(
        JWT_SCOPE_READ="archive:read",
        JWT_SCOPE_WRITE="archive:write",
        JWT_SCOPE_DELETE="archive:delete",
        JWT_ADMIN_ROLE="admin",
    )
    request = SimpleNamespace(method="POST", url=SimpleNamespace(path="/api/news"))
    claims = {"sub": "regular-user", "scope": "archive:write"}

    with caplog.at_level(logging.INFO, logger="civic_archive.security"):
        authorize_claims_for_request(request, claims, config)

    audit_records = [r for r in caplog.records if r.message == "admin_role_access_granted"]
    assert len(audit_records) == 0
