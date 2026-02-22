from __future__ import annotations

import logging
from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.bootstrap.exception_handlers import register_exception_handlers
from app.observability import register_observability
from app.security import build_rate_limit_dependency
from app.security_dependencies import build_api_key_dependency


def _build_app_with_dependency(dependency) -> FastAPI:
    api = FastAPI()
    register_observability(api)
    register_exception_handlers(api, logger=logging.getLogger("test.error.contracts"))

    @api.get("/secure", dependencies=[Depends(dependency)])
    async def secure_route():
        return {"ok": True}

    return api


def _assert_error_contract(response, expected_code: str, expected_status: int) -> None:
    assert response.status_code == expected_status
    payload = response.json()
    assert payload["code"] == expected_code
    assert payload["message"]
    assert payload["error"] == payload["message"]
    assert payload["request_id"]
    assert response.headers["X-Request-Id"] == payload["request_id"]


def test_api_key_unauthorized_error_has_request_id_header():
    dependency = build_api_key_dependency(SimpleNamespace(REQUIRE_API_KEY=True, API_KEY="expected"))
    app = _build_app_with_dependency(dependency)

    with TestClient(app) as client:
        response = client.get("/secure")

    _assert_error_contract(response, expected_code="UNAUTHORIZED", expected_status=401)


def test_rate_limit_error_has_request_id_header():
    dependency = build_rate_limit_dependency(
        SimpleNamespace(
            RATE_LIMIT_PER_MINUTE=1,
            rate_limit_backend="memory",
            REDIS_URL="",
            RATE_LIMIT_REDIS_PREFIX="civic_archive:rate_limit",
            RATE_LIMIT_REDIS_WINDOW_SECONDS=65,
            RATE_LIMIT_REDIS_FAILURE_COOLDOWN_SECONDS=5,
            RATE_LIMIT_FAIL_OPEN=True,
            trusted_proxy_cidrs_list=[],
        )
    )
    app = _build_app_with_dependency(dependency)

    with TestClient(app) as client:
        first = client.get("/secure")
        second = client.get("/secure")

    assert first.status_code == 200
    _assert_error_contract(second, expected_code="RATE_LIMITED", expected_status=429)
