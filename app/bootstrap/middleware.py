from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any, cast
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import Config
from app.errors import error_response

ReceiveMessage = MutableMapping[str, Any]
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH"})
API_PATH_PREFIX = "/api/"
REQUEST_SIZE_GUARD_DETAILS_ATTR = "_request_size_guard_details"
REQUEST_RECEIVE_ATTR = "_receive"


def _is_request_size_guard_target(request: Request) -> bool:
    return request.url.path.startswith(API_PATH_PREFIX) and request.method in WRITE_METHODS


def _payload_too_large_response(
    request: Request,
    *,
    details: dict[str, Any],
) -> Response:
    return error_response(
        request,
        status_code=413,
        code="PAYLOAD_TOO_LARGE",
        message="Payload Too Large",
        details=details,
    )


def _invalid_content_length_response(request: Request) -> Response:
    return error_response(
        request,
        status_code=400,
        code="BAD_REQUEST",
        message="Invalid Content-Length header",
    )


def register_core_middleware(api: FastAPI, config: Config) -> None:
    api.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_allow_origins_list,
        allow_methods=config.cors_allow_methods_list,
        allow_headers=config.cors_allow_headers_list,
    )
    api.add_middleware(TrustedHostMiddleware, allowed_hosts=config.allowed_hosts_list)

    @api.middleware("http")
    async def request_size_guard(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.request_id = request.headers.get("X-Request-Id") or getattr(request.state, "request_id", None) or str(uuid4())

        if _is_request_size_guard_target(request):
            max_request_body_bytes = int(config.MAX_REQUEST_BODY_BYTES)
            content_length = None
            content_length_raw = (request.headers.get("content-length") or "").strip()
            if content_length_raw:
                try:
                    content_length = int(content_length_raw)
                except ValueError:
                    return _invalid_content_length_response(request)
                if content_length > max_request_body_bytes:
                    return _payload_too_large_response(
                        request,
                        details={
                            "max_request_body_bytes": max_request_body_bytes,
                            "content_length": content_length,
                        },
                    )
            received_bytes = 0
            original_receive = cast(Callable[[], Awaitable[ReceiveMessage]], getattr(request, REQUEST_RECEIVE_ATTR))

            async def guarded_receive() -> ReceiveMessage:
                nonlocal received_bytes
                message = await original_receive()
                if message.get("type") != "http.request":
                    return message

                chunk = message.get("body", b"") or b""
                received_bytes += len(chunk)
                if received_bytes > max_request_body_bytes:
                    overflow_details = {
                        "max_request_body_bytes": max_request_body_bytes,
                        "request_body_bytes": received_bytes,
                    }
                    if content_length is not None:
                        overflow_details["content_length"] = content_length
                    setattr(request.state, REQUEST_SIZE_GUARD_DETAILS_ATTR, overflow_details)
                    # Stop reading request body as soon as the limit is exceeded.
                    return {"type": "http.request", "body": b"", "more_body": False}
                return message

            setattr(request, REQUEST_RECEIVE_ATTR, guarded_receive)
        try:
            response = await call_next(request)
        except Exception:
            guard_details = getattr(request.state, REQUEST_SIZE_GUARD_DETAILS_ATTR, None)
            if guard_details is not None:
                return _payload_too_large_response(request, details=guard_details)
            raise

        guard_details = getattr(request.state, REQUEST_SIZE_GUARD_DETAILS_ATTR, None)
        if guard_details is not None:
            return _payload_too_large_response(request, details=guard_details)
        return response
