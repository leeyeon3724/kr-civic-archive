from __future__ import annotations

from collections import OrderedDict
import logging
import sys
import time
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
ALLOWED_HTTP_METHOD_LABELS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
MAX_PATH_LABEL_LENGTH = 96
ROUTE_TEMPLATE_CACHE_MAX_SIZE = 512

logger = logging.getLogger("civic_archive.api")
_ROUTE_TEMPLATE_CACHE: OrderedDict[tuple[str, str], str] = OrderedDict()


def _route_cache_key(request: Request) -> tuple[str, str]:
    raw_path = request.scope.get("path")
    path = str(raw_path) if isinstance(raw_path, str) else request.url.path
    return (_metric_method_label(request.method), path)


def _route_template_cache_get(cache_key: tuple[str, str]) -> str | None:
    route_path = _ROUTE_TEMPLATE_CACHE.get(cache_key)
    if route_path is None:
        return None
    _ROUTE_TEMPLATE_CACHE.move_to_end(cache_key)
    return route_path


def _route_template_cache_set(cache_key: tuple[str, str], route_path: str) -> None:
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


def register_observability(api: FastAPI) -> None:
    @api.middleware("http")
    async def request_observability(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or str(uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        client_ip = request.client.host if request.client else None
        response: Response | None = None

        try:
            response = await call_next(request)
        finally:
            elapsed = time.perf_counter() - started
            path_resolution_started = time.perf_counter()
            path, path_strategy = _metric_path_label(request, api)
            PATH_LABEL_RESOLUTION_LATENCY.labels(path_strategy).observe(
                time.perf_counter() - path_resolution_started
            )
            current_exc = sys.exc_info()[1]
            if current_exc is not None:
                status_code = 500
                if isinstance(current_exc, Exception):
                    status_code = _status_code_from_exception(current_exc)
                _observe_request_metrics(
                    method=request.method,
                    path=path,
                    status_code=status_code,
                    elapsed_seconds=elapsed,
                )
                log_payload = _build_request_log_payload(
                    request_id=request_id,
                    method=request.method,
                    path=path,
                    status_code=status_code,
                    elapsed_seconds=elapsed,
                    client_ip=client_ip,
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
            else:
                assert response is not None
                status_code = int(response.status_code)
                _observe_request_metrics(
                    method=request.method,
                    path=path,
                    status_code=status_code,
                    elapsed_seconds=elapsed,
                )
                response.headers["X-Request-Id"] = request_id
                log_payload = _build_request_log_payload(
                    request_id=request_id,
                    method=request.method,
                    path=path,
                    status_code=status_code,
                    elapsed_seconds=elapsed,
                    client_ip=client_ip,
                )
                logger.info(
                    "request_completed",
                    extra=log_payload,
                )

        assert response is not None
        return response

    @api.get("/metrics", tags=["system"], include_in_schema=False)
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
