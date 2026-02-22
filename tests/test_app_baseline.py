from datetime import datetime
import time
from unittest.mock import patch

import pytest
from datetime import timezone
from conftest import (
    StubEngine,
    StubResult,
    assert_payload_too_large_response,
    build_test_config,
    build_test_jwt,
    extract_first_select_params,
    oversized_echo_body,
)
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from app import create_app
from app.services.providers import get_news_service
from app.version import APP_VERSION

def _assert_not_found_error(payload):
    assert payload["error"] == "Not Found"
    assert payload["code"] == "NOT_FOUND"
    assert payload["message"] == "Not Found"
    assert payload.get("request_id")


def _assert_standard_error_shape(payload):
    assert isinstance(payload.get("code"), str) and payload["code"]
    assert isinstance(payload.get("message"), str) and payload["message"]
    assert isinstance(payload.get("error"), str) and payload["error"]
    assert isinstance(payload.get("request_id"), str) and payload["request_id"]


def test_parse_datetime_accepts_supported_formats(utils_module):
    assert utils_module.parse_datetime("2025-08-16T10:32:00Z") == datetime(2025, 8, 16, 10, 32, 0, tzinfo=timezone.utc)
    assert utils_module.parse_datetime("2025-08-16 10:32:00") == datetime(2025, 8, 16, 10, 32, 0, tzinfo=timezone.utc)
    assert utils_module.parse_datetime("2025-08-16T10:32:00") == datetime(2025, 8, 16, 10, 32, 0, tzinfo=timezone.utc)
    assert utils_module.parse_datetime("2025-08-16T19:32:00+09:00") == datetime(
        2025, 8, 16, 10, 32, 0, tzinfo=timezone.utc
    )


def test_parse_datetime_rejects_invalid_format(utils_module):
    with pytest.raises(HTTPException):
        utils_module.parse_datetime("16-08-2025")


def test_normalize_article_requires_title_and_url(news_module):
    with pytest.raises(HTTPException):
        news_module.normalize_article({"title": "only-title"})


def test_normalize_minutes_preserves_string_meeting_no(minutes_module):
    result = minutes_module.normalize_minutes(
        {
            "council": "Sample Council",
            "url": "https://example.com/minutes/1",
            "meeting_no": "Session-A-12",
        }
    )
    assert result["meeting_no"] is None
    assert result["meeting_no_combined"] == "Session-A-12"


def test_normalize_minutes_converts_numeric_meeting_no(minutes_module):
    result = minutes_module.normalize_minutes(
        {
            "council": "Sample Council",
            "session": "29th",
            "url": "https://example.com/minutes/2",
            "meeting_no": 3,
        }
    )
    assert result["meeting_no"] == 3
    assert result["meeting_no_combined"] == "29th 3\ucc28"


def test_normalize_segment_validates_importance(segments_module):
    ok = segments_module.normalize_segment({"council": "A", "importance": "2"})
    assert ok["importance"] == 2

    with pytest.raises(HTTPException):
        segments_module.normalize_segment({"council": "A", "importance": "invalid"})

    with pytest.raises(HTTPException):
        segments_module.normalize_segment({"council": "A", "importance": 4})


def test_upsert_articles_counts_insert_and_update(news_module, make_connection_provider):
    def handler(_statement, _params):
        return StubResult(rows=[{"inserted": 2, "updated": 1}])

    connection_provider, _ = make_connection_provider(handler)

    inserted, updated = news_module.upsert_articles(
        [
            {"title": "n1", "url": "u1"},
            {"title": "n2", "url": "u2"},
            {"title": "n3", "url": "u3"},
        ],
        connection_provider=connection_provider,
    )
    assert inserted == 2
    assert updated == 1


def test_insert_segments_returns_inserted_count(segments_module, make_connection_provider):
    def handler(_statement, _params):
        return StubResult(rows=[{"inserted": 2}])

    connection_provider, _ = make_connection_provider(handler)
    inserted = segments_module.insert_segments(
        [{"council": "A"}, {"council": "B"}],
        connection_provider=connection_provider,
    )
    assert inserted == 2


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}
    assert resp.headers.get("X-Request-Id")


def test_request_id_is_propagated_when_client_sends_header(client):
    request_id = "test-request-id-123"
    resp = client.get("/health", headers={"X-Request-Id": request_id})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-Id") == request_id


def test_validation_error_returns_standard_error_with_details(client):
    request_id = "test-validation-request-id"
    resp = client.get("/api/news?page=abc", headers={"X-Request-Id": request_id})
    assert resp.status_code == 400
    payload = resp.get_json()
    _assert_standard_error_shape(payload)
    assert payload["code"] == "VALIDATION_ERROR"
    assert isinstance(payload.get("details"), list)
    assert resp.headers.get("X-Request-Id") == request_id
    assert payload["request_id"] == request_id


def test_save_news_accepts_object_and_list(client, override_dependency):
    class FakeNewsService:
        @staticmethod
        def normalize_article(item):
            return item

        @staticmethod
        def upsert_articles(items):
            return len(items), 0

    override_dependency(get_news_service, lambda: FakeNewsService())

    one = client.post("/api/news", json={"title": "t1", "url": "u1"})
    assert one.status_code == 201
    assert one.get_json() == {"inserted": 1, "updated": 0}

    many = client.post(
        "/api/news",
        json=[{"title": "t2", "url": "u2"}, {"title": "t3", "url": "u3"}],
    )
    assert many.status_code == 201
    assert many.get_json() == {"inserted": 2, "updated": 0}


def test_save_news_rejects_invalid_json_body(client):
    resp = client.post("/api/news", data="{invalid", content_type="application/json")
    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload["code"] in {"BAD_REQUEST", "VALIDATION_ERROR"}
    assert "error" in payload


def test_save_minutes_requires_json(client):
    resp = client.post("/api/minutes", data="plain text", content_type="text/plain")
    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload["code"] in {"BAD_REQUEST", "VALIDATION_ERROR"}


def test_save_segments_requires_json(client):
    resp = client.post("/api/segments", data="plain text", content_type="text/plain")
    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload["code"] in {"BAD_REQUEST", "VALIDATION_ERROR"}


def test_list_news_returns_paginated_payload(client, use_stub_connection_provider):
    call_state = {"calls": 0}

    def handler(_statement, _params):
        if call_state["calls"] == 0:
            call_state["calls"] += 1
            return StubResult(
                rows=[
                    {
                        "id": 10,
                        "source": "paper",
                        "title": "budget news",
                        "url": "https://example.com/n/10",
                        "published_at": "2025-01-01 00:00:00",
                        "author": "author",
                        "summary": "summary",
                        "keywords": '["budget"]',
                        "created_at": "2025-01-01 00:00:00",
                        "updated_at": "2025-01-01 00:00:00",
                    }
                ]
            )
        return StubResult(scalar_value=1)

    engine = use_stub_connection_provider(handler)

    resp = client.get("/api/news?page=2&size=1&q=budget")
    data = resp.get_json()

    assert resp.status_code == 200
    assert data["page"] == 2
    assert data["size"] == 1
    assert data["total"] == 1
    assert data["items"][0]["id"] == 10

    first_select_params = extract_first_select_params(engine)
    assert first_select_params["limit"] == 1
    assert first_select_params["offset"] == 1
    assert first_select_params["q"] == "%budget%"
    assert first_select_params["q_fts"] == "budget"


def test_get_news_404_when_not_found(client, use_stub_connection_provider):
    def handler(_statement, _params):
        return StubResult(rows=[])

    use_stub_connection_provider(handler)

    resp = client.get("/api/news/999")
    assert resp.status_code == 404
    _assert_not_found_error(resp.get_json())


def test_delete_news_success_and_not_found(client, use_stub_connection_provider):
    def handler(_statement, params):
        if params["id"] == 1:
            return StubResult(rowcount=1)
        if params["id"] == 2:
            return StubResult(rowcount=0)
        return StubResult()

    use_stub_connection_provider(handler)

    ok_resp = client.delete("/api/news/1")
    assert ok_resp.status_code == 200
    assert ok_resp.get_json() == {"status": "deleted", "id": 1}

    miss_resp = client.delete("/api/news/2")
    assert miss_resp.status_code == 404
    _assert_not_found_error(miss_resp.get_json())


def test_list_segments_rejects_invalid_importance(client):
    resp = client.get("/api/segments?importance=high")
    assert resp.status_code == 400
    payload = resp.get_json()
    assert payload["code"] == "VALIDATION_ERROR"
    assert "error" in payload


def test_unknown_route_returns_json_404(client):
    resp = client.get("/no-such-route")
    assert resp.status_code == 404
    payload = resp.get_json()
    _assert_not_found_error(payload)
    assert resp.headers.get("X-Request-Id")
    assert payload["request_id"] == resp.headers.get("X-Request-Id")


def test_metrics_endpoint_exposes_prometheus_text(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in (resp.headers.get("content-type") or "")
    body = resp.text
    assert "civic_archive_http_requests_total" in body
    assert "civic_archive_http_request_duration_seconds" in body


def test_metrics_uses_low_cardinality_label_for_unmatched_route(client):
    unmatched_path = "/no-such-route-cardinality-unique-case"
    missing = client.get(unmatched_path)
    assert missing.status_code == 404

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    body = metrics.text
    assert 'path="/_unmatched"' in body
    assert f'path="{unmatched_path}"' not in body


def test_openapi_version_uses_app_version_constant(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.get_json()["info"]["version"] == APP_VERSION


def test_database_url_preserves_special_character_credentials():
    config = build_test_config(
        POSTGRES_HOST="db.internal",
        POSTGRES_PORT=5432,
        POSTGRES_USER="app-user",
        POSTGRES_PASSWORD="pa:ss@word",
        POSTGRES_DB="archive",
    )

    parsed = make_url(config.database_url)
    assert parsed.username == "app-user"
    assert parsed.password == "pa:ss@word"
    assert parsed.host == "db.internal"
    assert parsed.database == "archive"


def test_build_test_config_is_deterministic_against_env(monkeypatch):
    monkeypatch.setenv("REQUIRE_API_KEY", "1")
    monkeypatch.setenv("POSTGRES_PASSWORD", "env-secret")

    config = build_test_config()

    assert config.REQUIRE_API_KEY is False
    assert config.POSTGRES_PASSWORD == "change_me"


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


def test_create_app_applies_database_runtime_tuning():
    captured = {}

    def fake_create_engine(url, **create_engine_kwargs):
        captured["url"] = url
        captured["kwargs"] = create_engine_kwargs

        def _default_handler(_statement, _params=None):
            return StubResult()

        return StubEngine(_default_handler)

    with patch("app.database.create_engine", side_effect=fake_create_engine):
        app = create_app(
            build_test_config(
                DB_POOL_SIZE=7,
                DB_MAX_OVERFLOW=13,
                DB_POOL_TIMEOUT_SECONDS=11,
                DB_POOL_RECYCLE_SECONDS=1800,
                DB_CONNECT_TIMEOUT_SECONDS=4,
                DB_STATEMENT_TIMEOUT_MS=4500,
            )
        )

    assert app is not None
    init_kwargs = captured["kwargs"]
    assert init_kwargs["pool_size"] == 7
    assert init_kwargs["max_overflow"] == 13
    assert init_kwargs["pool_timeout"] == 11
    assert init_kwargs["pool_recycle"] == 1800
    assert init_kwargs["connect_args"]["connect_timeout"] == 4
    assert "statement_timeout=4500" in init_kwargs["connect_args"]["options"]
    assert "application_name=civic_archive_api" in init_kwargs["connect_args"]["options"]
    assert "timezone=UTC" in init_kwargs["connect_args"]["options"]


@pytest.mark.parametrize(
    ("config_overrides", "expected_message"),
    [
        ({"DB_POOL_SIZE": 0}, "DB_POOL_SIZE must be greater than 0."),
        ({"DB_MAX_OVERFLOW": -1}, "DB_MAX_OVERFLOW must be greater than or equal to 0."),
        ({"DB_POOL_TIMEOUT_SECONDS": 0}, "DB_POOL_TIMEOUT_SECONDS must be greater than 0."),
        ({"DB_POOL_RECYCLE_SECONDS": 0}, "DB_POOL_RECYCLE_SECONDS must be greater than 0."),
        ({"DB_CONNECT_TIMEOUT_SECONDS": 0}, "DB_CONNECT_TIMEOUT_SECONDS must be greater than 0."),
        ({"DB_STATEMENT_TIMEOUT_MS": 0}, "DB_STATEMENT_TIMEOUT_MS must be greater than 0."),
        ({"INGEST_MAX_BATCH_ITEMS": 0}, "INGEST_MAX_BATCH_ITEMS must be greater than 0."),
        ({"MAX_REQUEST_BODY_BYTES": 0}, "MAX_REQUEST_BODY_BYTES must be greater than 0."),
    ],
)
def test_create_app_rejects_invalid_database_runtime_tuning(config_overrides, expected_message):
    with pytest.raises(RuntimeError, match=expected_message):
        create_app(build_test_config(**config_overrides))


def test_ingest_batch_limit_rejects_oversized_payload(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(build_test_config(INGEST_MAX_BATCH_ITEMS=1))

    with TestClient(app) as tc:
        response = tc.post(
            "/api/news",
            json=[
                {"title": "n1", "url": "https://example.com/news/1"},
                {"title": "n2", "url": "https://example.com/news/2"},
            ],
        )
        assert response.status_code == 413
        payload = response.json()
        assert payload["code"] == "PAYLOAD_TOO_LARGE"
        assert payload["message"] == "Payload Too Large"
        assert payload["details"]["max_batch_items"] == 1
        assert payload["details"]["received_batch_items"] == 2


def test_request_size_guard_rejects_large_content_length(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(build_test_config(MAX_REQUEST_BODY_BYTES=64))

    with TestClient(app) as tc:
        body = oversized_echo_body()
        response = tc.post(
            "/api/echo",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        payload = assert_payload_too_large_response(response, max_request_body_bytes=64)
        assert payload["details"]["content_length"] > 64


def test_request_size_guard_rejects_oversized_streaming_body_without_reliable_content_length(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(build_test_config(MAX_REQUEST_BODY_BYTES=64))

    def payload_chunks():
        yield b'{"payload":"'
        yield b"x" * 200
        yield b'"}'

    with TestClient(app) as tc:
        response = tc.post(
            "/api/echo",
            content=payload_chunks(),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 413
        payload = response.json()
        assert payload["code"] == "PAYLOAD_TOO_LARGE"
        assert payload["details"]["max_request_body_bytes"] == 64
        assert payload["details"]["request_body_bytes"] > 64
        assert "content_length" not in payload["details"]
