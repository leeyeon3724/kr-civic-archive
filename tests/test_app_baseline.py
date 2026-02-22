from datetime import datetime
from unittest.mock import patch

import pytest
from datetime import timezone
from conftest import (
    StubEngine,
    StubResult,
    assert_payload_too_large_response,
    build_test_config,
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


def test_normalize_minutes_keeps_numeric_string_meeting_no_as_text(minutes_module):
    result = minutes_module.normalize_minutes(
        {
            "council": "Sample Council",
            "session": "29th",
            "url": "https://example.com/minutes/2a",
            "meeting_no": "3",
        }
    )
    assert result["meeting_no"] is None
    assert result["meeting_no_combined"] == "3"


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


def test_normalize_minutes_ignores_boolean_meeting_no(minutes_module):
    result = minutes_module.normalize_minutes(
        {
            "council": "Sample Council",
            "session": "29th",
            "url": "https://example.com/minutes/3",
            "meeting_no": True,
        }
    )
    assert result["meeting_no"] is None
    assert result["meeting_no_combined"] == "29th"


def test_normalize_segment_validates_importance(segments_module):
    ok = segments_module.normalize_segment({"council": "A", "importance": "2"})
    assert ok["importance"] == 2

    with pytest.raises(HTTPException):
        segments_module.normalize_segment({"council": "A", "importance": "invalid"})

    with pytest.raises(HTTPException):
        segments_module.normalize_segment({"council": "A", "importance": 4})


def test_normalize_segment_ignores_boolean_meeting_no(segments_module):
    result = segments_module.normalize_segment(
        {
            "council": "A",
            "session": "301",
            "meeting_no": False,
        }
    )
    assert result["meeting_no"] is None
    assert result["meeting_no_combined"] == "301"


def test_normalize_segment_keeps_numeric_string_meeting_no_as_text(segments_module):
    result = segments_module.normalize_segment(
        {
            "council": "A",
            "session": "301",
            "meeting_no": "3",
        }
    )
    assert result["meeting_no"] is None
    assert result["meeting_no_combined"] == "3"


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

    parsed = make_url(config.database_engine_url)
    assert parsed.username == "app-user"
    assert parsed.password == "pa:ss@word"
    assert parsed.host == "db.internal"
    assert parsed.database == "archive"
    assert "pa:ss@word" not in config.database_url
    assert "***" in config.database_url


def test_build_test_config_is_deterministic_against_env(monkeypatch):
    monkeypatch.setenv("REQUIRE_API_KEY", "1")
    monkeypatch.setenv("POSTGRES_PASSWORD", "env-secret")

    config = build_test_config()

    assert config.REQUIRE_API_KEY is False
    assert config.POSTGRES_PASSWORD == "change_me"


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
        request_id = "test-overflow-1"
        response = tc.post(
            "/api/echo",
            content=body,
            headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        )
        payload = assert_payload_too_large_response(response, max_request_body_bytes=64)
        assert response.headers["X-Request-Id"] == request_id
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
        assert response.headers.get("X-Request-Id")
        payload = response.json()
        assert payload["code"] == "PAYLOAD_TOO_LARGE"
        assert payload["details"]["max_request_body_bytes"] == 64
        assert payload["details"]["request_body_bytes"] > 64
        assert "content_length" not in payload["details"]
