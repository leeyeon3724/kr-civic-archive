import logging

import pytest
from conftest import build_test_config
from fastapi import FastAPI, HTTPException, Query
from fastapi.testclient import TestClient

import app.bootstrap.routes as bootstrap_routes_module
from app.bootstrap.exception_handlers import register_exception_handlers
from app.bootstrap.middleware import register_core_middleware
from app.bootstrap.routes import register_domain_routes
from app.bootstrap.system_routes import register_system_routes
from app.bootstrap.validation import validate_startup_config


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
