from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

DEFAULT_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    413: "PAYLOAD_TOO_LARGE",
    429: "RATE_LIMITED",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_ERROR",
}


def build_error_payload(
    *,
    code: str,
    message: str,
    request_id: Optional[str] = None,
    details: Optional[Any] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "message": message,
        # Keep backward-compatibility for existing clients/tests.
        "error": message,
    }
    if request_id:
        payload["request_id"] = request_id
    if details is not None:
        payload["details"] = jsonable_encoder(details)
    return payload


def http_error(status_code: int, code: str, message: str, *, details: Optional[Any] = None) -> HTTPException:
    detail: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        detail["details"] = details
    return HTTPException(status_code=status_code, detail=detail)


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Optional[Any] = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    headers = {"X-Request-Id": request_id} if request_id else None
    return JSONResponse(
        build_error_payload(code=code, message=message, request_id=request_id, details=details),
        status_code=status_code,
        headers=headers,
    )


def normalize_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code") or DEFAULT_ERROR_CODES.get(exc.status_code, "HTTP_ERROR"))
        message = str(detail.get("message") or detail.get("error") or "Request failed")
        details = detail.get("details")
    else:
        code = DEFAULT_ERROR_CODES.get(exc.status_code, "HTTP_ERROR")
        message = str(detail) if detail is not None else "Request failed"
        details = None

    return error_response(request, status_code=exc.status_code, code=code, message=message, details=details)
