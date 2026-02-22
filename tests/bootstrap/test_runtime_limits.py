from __future__ import annotations

from unittest.mock import patch

import pytest
from conftest import StubEngine, StubResult, assert_payload_too_large_response, build_test_config, oversized_echo_body
from fastapi.testclient import TestClient

from app import create_app


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


def test_request_size_guard_rejects_invalid_content_length_header(make_engine):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(build_test_config(MAX_REQUEST_BODY_BYTES=64))

    with TestClient(app) as tc:
        response = tc.post(
            "/api/echo",
            content='{"payload":"x"}',
            headers={"Content-Type": "application/json", "Content-Length": "invalid"},
        )
        assert response.status_code == 400
        payload = response.json()
        assert payload["code"] == "BAD_REQUEST"
        assert payload["message"] == "Invalid Content-Length header"


@pytest.mark.parametrize("method", ["PUT", "PATCH"])
def test_request_size_guard_applies_to_put_and_patch_before_route_resolution(make_engine, method):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(build_test_config(MAX_REQUEST_BODY_BYTES=64))

    with TestClient(app) as tc:
        response = tc.request(
            method,
            "/api/echo",
            content='{"payload":"x"}',
            headers={"Content-Type": "application/json", "Content-Length": "invalid"},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "BAD_REQUEST"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH"])
def test_request_size_guard_rejects_negative_content_length_header(make_engine, method):
    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(build_test_config(MAX_REQUEST_BODY_BYTES=64))

    with TestClient(app) as tc:
        response = tc.request(
            method,
            "/api/echo",
            content='{"payload":"x"}',
            headers={"Content-Type": "application/json", "Content-Length": "-1"},
        )
        assert response.status_code == 400
        payload = response.json()
        assert payload["code"] == "BAD_REQUEST"
        assert payload["message"] == "Invalid Content-Length header"
