import logging
from datetime import date

import pytest
from conftest import build_test_config
from fastapi import FastAPI, HTTPException, Query
from fastapi.testclient import TestClient
from unittest.mock import patch

import app.bootstrap.routes as bootstrap_routes_module
from app.bootstrap.exception_handlers import register_exception_handlers
from app.bootstrap.middleware import register_core_middleware
from app.bootstrap.routes import register_domain_routes
from app.bootstrap.system_routes import register_system_routes
from app.bootstrap.validation import validate_startup_config
from app import create_app
from app.routes.common import (
    ensure_delete_succeeded,
    ensure_resource_found,
    normalize_ingest_payload,
    to_date_filter,
)


def test_validation_module_rejects_invalid_rate_limit_backend():
    with pytest.raises(RuntimeError, match="RATE_LIMIT_BACKEND must be one of: memory, redis."):
        validate_startup_config(build_test_config(RATE_LIMIT_BACKEND="invalid"))


def test_routes_module_forwards_protected_dependencies(monkeypatch):
    api = FastAPI()
    captured = {}
    marker_dependency = object()

    def fake_register_routes(app, *, dependencies=None):
        captured["app"] = app
        captured["dependencies"] = dependencies

    monkeypatch.setattr(bootstrap_routes_module, "register_routes", fake_register_routes)
    register_domain_routes(api, protected_dependencies=[marker_dependency])

    assert captured["app"] is api
    assert captured["dependencies"] == [marker_dependency]


def test_middleware_module_enforces_request_size_guard():
    api = FastAPI()
    register_core_middleware(api, build_test_config(MAX_REQUEST_BODY_BYTES=64))

    @api.get("/status")
    async def status():
        return {"status": "ok"}

    @api.post("/api/echo")
    async def echo(request_body: dict):
        return request_body

    with TestClient(api) as client:
        health = client.get("/status")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        oversized = client.post(
            "/api/echo",
            content='{"payload":"' + ("x" * 200) + '"}',
            headers={"Content-Type": "application/json"},
        )
        assert oversized.status_code == 413
        error_body = oversized.json()
        assert error_body["code"] == "PAYLOAD_TOO_LARGE"
        assert error_body["details"]["max_request_body_bytes"] == 64


def test_system_routes_module_readiness_and_echo():
    api = FastAPI()
    register_system_routes(
        api,
        protected_dependencies=[],
        db_health_check=lambda: (True, None),
        rate_limit_health_check=lambda: (False, "redis down"),
    )

    with TestClient(api) as client:
        ready = client.get("/health/ready")
        assert ready.status_code == 503
        readiness_body = ready.json()
        assert readiness_body["status"] == "degraded"
        assert readiness_body["checks"]["database"]["ok"] is True
        assert readiness_body["checks"]["rate_limit_backend"]["ok"] is False

        echo = client.post("/api/echo", json={"hello": "world"})
        assert echo.status_code == 200
        assert echo.json() == {"you_sent": {"hello": "world"}}


def test_system_routes_echo_reflects_any_json_payload():
    api = FastAPI()
    register_system_routes(
        api,
        protected_dependencies=[],
        db_health_check=lambda: (True, None),
        rate_limit_health_check=lambda: (True, None),
    )

    with TestClient(api) as client:
        array_resp = client.post("/api/echo", json=[{"id": 1}, {"id": 2}])
        assert array_resp.status_code == 200
        assert array_resp.json() == {"you_sent": [{"id": 1}, {"id": 2}]}

        string_resp = client.post("/api/echo", json="plain")
        assert string_resp.status_code == 200
        assert string_resp.json() == {"you_sent": "plain"}


def test_create_app_disposes_db_engine_on_shutdown():
    class _NoopScope:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    class _TrackingEngine:
        def __init__(self):
            self.disposed = False

        def begin(self):
            return _NoopScope()

        def dispose(self):
            self.disposed = True

    engine = _TrackingEngine()
    with patch("app.database.create_engine", return_value=engine):
        app = create_app(build_test_config())

    with TestClient(app):
        assert engine.disposed is False

    assert engine.disposed is True


def test_exception_handlers_module_normalizes_errors():
    api = FastAPI()
    register_exception_handlers(api, logger=logging.getLogger("test.bootstrap.handlers"))

    @api.get("/validation")
    async def validation_route(page: int = Query(...)):
        return {"page": page}

    @api.get("/http")
    async def http_route():
        raise HTTPException(status_code=404, detail="Not Found")

    @api.get("/boom")
    async def boom_route():
        raise RuntimeError("boom")

    with TestClient(api, raise_server_exceptions=False) as client:
        validation = client.get("/validation?page=abc")
        assert validation.status_code == 400
        assert validation.json()["code"] == "VALIDATION_ERROR"

        http_error = client.get("/http")
        assert http_error.status_code == 404
        assert http_error.json()["code"] == "NOT_FOUND"

        boom = client.get("/boom")
        assert boom.status_code == 500
        assert boom.json()["code"] == "INTERNAL_ERROR"


def test_routes_common_date_filter_normalizes_optional_values():
    assert to_date_filter(None) is None
    assert to_date_filter(date(2026, 2, 22)) == "2026-02-22"


def test_routes_common_normalize_ingest_payload_handles_single_and_list():
    config = build_test_config(INGEST_MAX_BATCH_ITEMS=2)
    request = type("Req", (), {"app": type("App", (), {"state": type("State", (), {"config": config})()})()})()

    single = normalize_ingest_payload(request, {"id": 1})
    assert single == [{"id": 1}]

    multiple = normalize_ingest_payload(request, [{"id": 1}, {"id": 2}])
    assert multiple == [{"id": 1}, {"id": 2}]

    with pytest.raises(HTTPException) as exc_info:
        normalize_ingest_payload(request, [{"id": 1}, {"id": 2}, {"id": 3}])
    assert exc_info.value.status_code == 413


def test_routes_common_not_found_guards():
    assert ensure_resource_found({"id": 1}) == {"id": 1}
    assert ensure_resource_found({}) == {}
    assert ensure_resource_found(0) == 0

    with pytest.raises(HTTPException) as missing_resource:
        ensure_resource_found(None)
    assert missing_resource.value.status_code == 404

    ensure_delete_succeeded(True)

    with pytest.raises(HTTPException) as delete_failed:
        ensure_delete_succeeded(False)
    assert delete_failed.value.status_code == 404
