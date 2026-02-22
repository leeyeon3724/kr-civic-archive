from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import error_response, normalize_http_exception


def register_exception_handlers(api: FastAPI, *, logger: logging.Logger) -> None:
    @api.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return normalize_http_exception(request, exc)

    @api.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        message = "; ".join(err.get("msg", "invalid request") for err in exc.errors())
        return error_response(
            request,
            status_code=400,
            code="VALIDATION_ERROR",
            message=message or "invalid request",
            details=exc.errors(),
        )

    @api.exception_handler(Exception)
    async def server_error_handler(request: Request, _exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", extra={"request_id": getattr(request.state, "request_id", None)})
        return error_response(
            request,
            status_code=500,
            code="INTERNAL_ERROR",
            message="Internal Server Error",
        )
