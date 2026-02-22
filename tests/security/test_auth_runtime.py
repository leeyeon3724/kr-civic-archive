from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from conftest import StubResult, build_test_config, build_test_jwt
from fastapi.testclient import TestClient

from app import create_app


def test_api_key_required_for_protected_endpoint(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(
            build_test_config(
                REQUIRE_API_KEY=True,
                API_KEY="top-secret",
            )
        )

    with TestClient(app) as tc:
        unauthorized = tc.post("/api/echo", json={"hello": "world"})
        assert unauthorized.status_code == 401
        body = unauthorized.json()
        assert body["code"] == "UNAUTHORIZED"
        assert body["message"] == "Unauthorized"
        assert body.get("request_id")

        authorized = tc.post("/api/echo", json={"hello": "world"}, headers={"X-API-Key": "top-secret"})
        assert authorized.status_code == 200
        assert authorized.json() == {"you_sent": {"hello": "world"}}


def test_metrics_requires_api_key_when_enabled(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(
            build_test_config(
                REQUIRE_API_KEY=True,
                API_KEY="top-secret",
            )
        )

    with TestClient(app) as tc:
        unauthorized = tc.get("/metrics")
        assert unauthorized.status_code == 401
        assert unauthorized.json()["code"] == "UNAUTHORIZED"

        authorized = tc.get("/metrics", headers={"X-API-Key": "top-secret"})
        assert authorized.status_code == 200
        assert "civic_archive_http_requests_total" in authorized.text


def test_protected_endpoint_requires_both_api_key_and_jwt_when_both_enabled(make_engine):
    secret = "jwt-combined-auth-secret-0123456789abcdef"
    now = int(time.time())
    write_token = build_test_jwt(
        secret,
        {
            "sub": "combined-auth-user",
            "scope": "archive:write archive:read",
            "exp": now + 300,
        },
    )

    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(
            build_test_config(
                REQUIRE_API_KEY=True,
                API_KEY="top-secret",
                REQUIRE_JWT=True,
                JWT_SECRET=secret,
            )
        )

    with TestClient(app) as tc:
        only_api_key = tc.post("/api/echo", json={"hello": "world"}, headers={"X-API-Key": "top-secret"})
        assert only_api_key.status_code == 401
        assert only_api_key.json()["code"] == "UNAUTHORIZED"

        only_jwt = tc.post("/api/echo", json={"hello": "world"}, headers={"Authorization": f"Bearer {write_token}"})
        assert only_jwt.status_code == 401
        assert only_jwt.json()["code"] == "UNAUTHORIZED"

        both_headers = tc.post(
            "/api/echo",
            json={"hello": "world"},
            headers={"X-API-Key": "top-secret", "Authorization": f"Bearer {write_token}"},
        )
        assert both_headers.status_code == 200
        assert both_headers.json() == {"you_sent": {"hello": "world"}}


def test_metrics_endpoint_requires_both_api_key_and_jwt_when_both_enabled(make_engine):
    secret = "jwt-combined-metrics-secret-0123456789abcdef"
    now = int(time.time())
    read_token = build_test_jwt(
        secret,
        {
            "sub": "combined-metrics-user",
            "scope": "archive:read",
            "exp": now + 300,
        },
    )

    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(
            build_test_config(
                REQUIRE_API_KEY=True,
                API_KEY="top-secret",
                REQUIRE_JWT=True,
                JWT_SECRET=secret,
            )
        )

    with TestClient(app) as tc:
        only_api_key = tc.get("/metrics", headers={"X-API-Key": "top-secret"})
        assert only_api_key.status_code == 401
        assert only_api_key.json()["code"] == "UNAUTHORIZED"

        only_jwt = tc.get("/metrics", headers={"Authorization": f"Bearer {read_token}"})
        assert only_jwt.status_code == 401
        assert only_jwt.json()["code"] == "UNAUTHORIZED"

        both_headers = tc.get(
            "/metrics",
            headers={"X-API-Key": "top-secret", "Authorization": f"Bearer {read_token}"},
        )
        assert both_headers.status_code == 200
        assert "civic_archive_http_requests_total" in both_headers.text


def test_jwt_required_for_protected_endpoint(make_engine):
    secret = "jwt-test-secret-0123456789abcdef"
    now = int(time.time())
    write_token = build_test_jwt(
        secret,
        {
            "sub": "user-1",
            "scope": "archive:write archive:read",
            "exp": now + 300,
        },
    )

    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(
            build_test_config(
                REQUIRE_JWT=True,
                JWT_SECRET=secret,
            )
        )

    with TestClient(app) as tc:
        unauthorized = tc.post("/api/echo", json={"hello": "world"})
        assert unauthorized.status_code == 401
        assert unauthorized.json()["code"] == "UNAUTHORIZED"

        malformed = tc.post("/api/echo", json={"hello": "world"}, headers={"Authorization": "Bearer bad-token"})
        assert malformed.status_code == 401
        assert malformed.json()["code"] == "UNAUTHORIZED"

        authorized = tc.post(
            "/api/echo",
            json={"hello": "world"},
            headers={"Authorization": f"Bearer {write_token}"},
        )
        assert authorized.status_code == 200
        assert authorized.json() == {"you_sent": {"hello": "world"}}


def test_jwt_forbidden_without_required_scope(make_engine):
    secret = "jwt-scope-test-secret-0123456789ab"
    now = int(time.time())
    read_only_token = build_test_jwt(
        secret,
        {
            "sub": "user-2",
            "scope": "archive:read",
            "exp": now + 300,
        },
    )

    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(
            build_test_config(
                REQUIRE_JWT=True,
                JWT_SECRET=secret,
            )
        )

    with TestClient(app) as tc:
        forbidden = tc.post(
            "/api/echo",
            json={"hello": "world"},
            headers={"Authorization": f"Bearer {read_only_token}"},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["code"] == "FORBIDDEN"


def test_jwt_admin_role_bypasses_scope_checks(make_engine):
    secret = "jwt-admin-test-secret-0123456789ab"
    now = int(time.time())
    admin_token = build_test_jwt(
        secret,
        {
            "sub": "admin-1",
            "roles": ["admin"],
            "exp": now + 300,
        },
    )

    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(
            build_test_config(
                REQUIRE_JWT=True,
                JWT_SECRET=secret,
            )
        )

    with TestClient(app) as tc:
        response = tc.post(
            "/api/echo",
            json={"hello": "world"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200


def test_jwt_rejects_tokens_missing_required_sub_or_exp(make_engine):
    secret = "jwt-required-claims-secret-012345"
    now = int(time.time())
    missing_sub = build_test_jwt(
        secret,
        {
            "scope": "archive:write",
            "exp": now + 300,
        },
    )
    missing_exp = build_test_jwt(
        secret,
        {
            "sub": "user-required-claims",
            "scope": "archive:write",
        },
    )

    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(
            build_test_config(
                REQUIRE_JWT=True,
                JWT_SECRET=secret,
            )
        )

    with TestClient(app) as tc:
        sub_missing_response = tc.post(
            "/api/echo",
            json={"hello": "world"},
            headers={"Authorization": f"Bearer {missing_sub}"},
        )
        assert sub_missing_response.status_code == 401
        assert sub_missing_response.json()["code"] == "UNAUTHORIZED"

        exp_missing_response = tc.post(
            "/api/echo",
            json={"hello": "world"},
            headers={"Authorization": f"Bearer {missing_exp}"},
        )
        assert exp_missing_response.status_code == 401
        assert exp_missing_response.json()["code"] == "UNAUTHORIZED"


def test_jwt_leeway_allows_slightly_expired_token(make_engine):
    secret = "jwt-leeway-secret-0123456789abcdef"
    now = int(time.time())
    write_token = build_test_jwt(
        secret,
        {
            "sub": "user-leeway",
            "scope": "archive:write",
            "exp": now - 1,
        },
    )

    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(
            build_test_config(
                REQUIRE_JWT=True,
                JWT_SECRET=secret,
                JWT_LEEWAY_SECONDS=5,
            )
        )

    with TestClient(app) as tc:
        response = tc.post(
            "/api/echo",
            json={"hello": "world"},
            headers={"Authorization": f"Bearer {write_token}"},
        )
        assert response.status_code == 200
        assert response.json() == {"you_sent": {"hello": "world"}}


def test_jwt_configuration_requires_secret(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        with pytest.raises(RuntimeError):
            create_app(
                build_test_config(
                    REQUIRE_JWT=True,
                    JWT_SECRET=None,
                )
            )


def test_jwt_configuration_rejects_short_secret(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        with pytest.raises(RuntimeError, match="JWT_SECRET must be at least 32 bytes."):
            create_app(
                build_test_config(
                    REQUIRE_JWT=True,
                    JWT_SECRET="short-secret",
                )
            )


def test_jwt_algorithm_must_be_hs256(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        with pytest.raises(RuntimeError):
            create_app(
                build_test_config(
                    REQUIRE_JWT=True,
                    JWT_SECRET="test-secret-0123456789abcdefghijkl",
                    JWT_ALGORITHM="RS256",
                )
            )


def test_jwt_leeway_must_be_non_negative(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        with pytest.raises(RuntimeError, match="JWT_LEEWAY_SECONDS must be greater than or equal to 0."):
            create_app(
                build_test_config(
                    REQUIRE_JWT=True,
                    JWT_SECRET="test-secret-0123456789abcdefghijkl",
                    JWT_LEEWAY_SECONDS=-1,
                )
            )


def test_strict_security_mode_requires_authentication(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        with pytest.raises(RuntimeError):
            create_app(
                build_test_config(
                    SECURITY_STRICT_MODE=True,
                    ALLOWED_HOSTS="api.example.com",
                    CORS_ALLOW_ORIGINS="https://app.example.com",
                    RATE_LIMIT_PER_MINUTE=60,
                )
            )


def test_strict_security_mode_rejects_wildcard_allowed_hosts(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        with pytest.raises(RuntimeError):
            create_app(
                build_test_config(
                    SECURITY_STRICT_MODE=True,
                    REQUIRE_API_KEY=True,
                    API_KEY="strict-key",
                    ALLOWED_HOSTS="*",
                    CORS_ALLOW_ORIGINS="https://app.example.com",
                    RATE_LIMIT_PER_MINUTE=60,
                )
            )


def test_strict_security_mode_rejects_wildcard_cors(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        with pytest.raises(RuntimeError):
            create_app(
                build_test_config(
                    SECURITY_STRICT_MODE=True,
                    REQUIRE_API_KEY=True,
                    API_KEY="strict-key",
                    ALLOWED_HOSTS="api.example.com",
                    CORS_ALLOW_ORIGINS="*",
                    RATE_LIMIT_PER_MINUTE=60,
                )
            )


def test_strict_security_mode_requires_positive_rate_limit(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        with pytest.raises(RuntimeError):
            create_app(
                build_test_config(
                    SECURITY_STRICT_MODE=True,
                    REQUIRE_API_KEY=True,
                    API_KEY="strict-key",
                    ALLOWED_HOSTS="api.example.com",
                    CORS_ALLOW_ORIGINS="https://app.example.com",
                    RATE_LIMIT_PER_MINUTE=0,
                )
            )


def test_production_env_enables_strict_security_mode(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        with pytest.raises(RuntimeError):
            create_app(
                build_test_config(
                    APP_ENV="production",
                )
            )


def test_strict_security_mode_accepts_secure_configuration(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(
            build_test_config(
                SECURITY_STRICT_MODE=True,
                REQUIRE_API_KEY=True,
                API_KEY="strict-key",
                ALLOWED_HOSTS="api.example.com",
                CORS_ALLOW_ORIGINS="https://app.example.com",
                RATE_LIMIT_PER_MINUTE=60,
            )
        )
    assert app is not None


def test_strict_security_mode_rejects_short_jwt_secret_when_jwt_enabled(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        with pytest.raises(RuntimeError, match="JWT_SECRET must be at least 32 bytes."):
            create_app(
                build_test_config(
                    SECURITY_STRICT_MODE=True,
                    REQUIRE_JWT=True,
                    JWT_SECRET="short-secret",
                    ALLOWED_HOSTS="api.example.com",
                    CORS_ALLOW_ORIGINS="https://app.example.com",
                    RATE_LIMIT_PER_MINUTE=60,
                )
            )
