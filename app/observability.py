from __future__ import annotations

from collections import OrderedDict
import logging
import threading
import time
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match

REQUEST_COUNT = Counter(
    "civic_archive_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "civic_archive_http_request_duration_seconds",
    "HTTP request latency (seconds)",
    ["method", "path"],
)
PATH_LABEL_RESOLUTION_LATENCY = Histogram(
    "civic_archive_metric_path_label_resolution_seconds",
    "Metric path label resolution latency (seconds)",
    ["strategy"],
)
DB_QUERY_DURATION = Histogram(
    "civic_archive_db_query_duration_seconds",
    "Database query execution duration (seconds)",
)
ALLOWED_HTTP_METHOD_LABELS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
MAX_PATH_LABEL_LENGTH = 96
ROUTE_TEMPLATE_CACHE_MAX_SIZE = 512

logger = logging.getLogger("civic_archive.api")
_ROUTE_TEMPLATE_CACHE: OrderedDict[tuple[str, str], str] = OrderedDict()
_ROUTE_TEMPLATE_CACHE_LOCK = threading.RLock()


def _route_cache_key(request: Request) -> tuple[str, str]:
    raw_path = request.scope.get("path")
    path = str(raw_path) if isinstance(raw_path, str) else request.url.path
    return (_metric_method_label(request.method), path)


def _route_template_cache_get(cache_key: tuple[str, str]) -> str | None:
    with _ROUTE_TEMPLATE_CACHE_LOCK:
        route_path = _ROUTE_TEMPLATE_CACHE.get(cache_key)
        if route_path is None:
            return None
        _ROUTE_TEMPLATE_CACHE.move_to_end(cache_key)
        return route_path


def _route_template_cache_set(cache_key: tuple[str, str], route_path: str) -> None:
    with _ROUTE_TEMPLATE_CACHE_LOCK:
        _ROUTE_TEMPLATE_CACHE[cache_key] = route_path
        _ROUTE_TEMPLATE_CACHE.move_to_end(cache_key)
        while len(_ROUTE_TEMPLATE_CACHE) > ROUTE_TEMPLATE_CACHE_MAX_SIZE:
            _ROUTE_TEMPLATE_CACHE.popitem(last=False)


def _resolve_route_template_from_router(request: Request, api: FastAPI | None = None) -> str | None:
    if api is None:
        return None

    scope = request.scope
    for route in api.router.routes:
        try:
            matched, _ = route.matches(scope)
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
        if matched != Match.FULL:
            continue
        route_path = getattr(route, "path", None)
        if route_path:
            return str(route_path)
    return None


def _route_template(request: Request, api: FastAPI | None = None) -> tuple[str, str]:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if route_path:
        return str(route_path), "scope"

    cache_key = _route_cache_key(request)
    cached = _route_template_cache_get(cache_key)
    if cached is not None:
        return cached, "cache"
    resolved = _resolve_route_template_from_router(request, api)
    if resolved:
        _route_template_cache_set(cache_key, resolved)
        return resolved, "router"
    return "/_unmatched", "fallback"


def _metric_method_label(method: str | None) -> str:
    normalized = (method or "").upper()
    if normalized in ALLOWED_HTTP_METHOD_LABELS:
        return normalized
    return "OTHER"


def _metric_path_label(request: Request, api: FastAPI | None = None) -> tuple[str, str]:
    path, strategy = _route_template(request, api)
    if len(path) > MAX_PATH_LABEL_LENGTH:
        return "/_label_too_long", "label_too_long"
    return path, strategy


def _metric_status_label(status_code: int) -> str:
    if 100 <= int(status_code) <= 599:
        return str(int(status_code))
    return "000"


def _status_code_from_exception(exc: Exception) -> int:
    if isinstance(exc, RequestValidationError):
        return 400
    if isinstance(exc, StarletteHTTPException):
        return int(exc.status_code)
    return 500


def _build_request_log_payload(
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    elapsed_seconds: float,
    client_ip: str | None,
) -> dict[str, str | int | float | None]:
    return {
        "request_id": request_id,
        "method": method,
        "path": path,
        "status_code": int(status_code),
        "duration_ms": round(elapsed_seconds * 1000, 2),
        "client_ip": client_ip,
    }


def metric_status_label(status_code: int) -> str:
    return _metric_status_label(status_code)


def status_code_from_exception(exc: Exception) -> int:
    return _status_code_from_exception(exc)


def build_request_log_payload(
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    elapsed_seconds: float,
    client_ip: str | None,
) -> dict[str, str | int | float | None]:
    return _build_request_log_payload(
        request_id=request_id,
        method=method,
        path=path,
        status_code=status_code,
        elapsed_seconds=elapsed_seconds,
        client_ip=client_ip,
    )


def _observe_request_metrics(*, method: str, path: str, status_code: int, elapsed_seconds: float) -> None:
    method_label = _metric_method_label(method)
    status_label = _metric_status_label(status_code)
    REQUEST_COUNT.labels(method_label, path, status_label).inc()
    REQUEST_LATENCY.labels(method_label, path).observe(elapsed_seconds)


def _build_request_observability_payload(
    *,
    request: Request,
    api: FastAPI,
    request_id: str,
    method: str,
    status_code: int,
    started: float,
) -> dict[str, str | int | float | None]:
    elapsed_seconds = time.perf_counter() - started
    path_resolution_started = time.perf_counter()
    path, path_strategy = _metric_path_label(request, api)
    PATH_LABEL_RESOLUTION_LATENCY.labels(path_strategy).observe(
        time.perf_counter() - path_resolution_started
    )
    _observe_request_metrics(
        method=method,
        path=path,
        status_code=status_code,
        elapsed_seconds=elapsed_seconds,
    )
    client_ip = request.client.host if request.client else None
    return _build_request_log_payload(
        request_id=request_id,
        method=method,
        path=path,
        status_code=status_code,
        elapsed_seconds=elapsed_seconds,
        client_ip=client_ip,
    )


def register_observability(api: FastAPI, *, metrics_dependencies: list[Any] | None = None) -> None:
    route_dependencies = metrics_dependencies or []

    @api.middleware("http")
    async def request_observability(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or getattr(request.state, "request_id", None) or str(uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        method = request.method
        response: Response | None = None

        try:
            response = await call_next(request)
        except Exception as exc:
            status_code = _status_code_from_exception(exc)
            log_payload = _build_request_observability_payload(
                request=request,
                api=api,
                request_id=request_id,
                method=method,
                status_code=status_code,
                started=started,
            )
            if status_code >= 500:
                logger.exception(
                    "request_failed",
                    extra=log_payload,
                )
            else:
                logger.warning(
                    "request_failed",
                    extra=log_payload,
                )
            raise

        assert response is not None
        status_code = int(response.status_code)
        log_payload = _build_request_observability_payload(
            request=request,
            api=api,
            request_id=request_id,
            method=method,
            status_code=status_code,
            started=started,
        )
        response.headers["X-Request-Id"] = request_id
        logger.info(
            "request_completed",
            extra=log_payload,
        )
        return response

    @api.get("/metrics", tags=["system"], include_in_schema=False, dependencies=route_dependencies)
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
