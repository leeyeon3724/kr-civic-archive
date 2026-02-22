from __future__ import annotations

import json

from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.bootstrap.contracts import DBHealthCheck, ProtectedDependencies, RateLimitHealthCheck
from app.schemas import EchoResponse, ErrorResponse, HealthResponse, ReadinessCheck, ReadinessResponse


def register_system_routes(
    api: FastAPI,
    *,
    protected_dependencies: ProtectedDependencies,
    db_health_check: DBHealthCheck,
    rate_limit_health_check: RateLimitHealthCheck,
) -> None:
    @api.get("/", tags=["system"])
    async def hello_world() -> PlainTextResponse:
        return PlainTextResponse("API Server Available")

    @api.get("/health/live", tags=["system"], response_model=HealthResponse, responses={500: {"model": ErrorResponse}})
    async def health_live() -> HealthResponse:
        return HealthResponse(status="ok")

    @api.get("/health", tags=["system"], response_model=HealthResponse, responses={500: {"model": ErrorResponse}})
    async def health() -> HealthResponse:
        return await health_live()

    @api.get(
        "/health/ready",
        tags=["system"],
        response_model=ReadinessResponse,
        responses={500: {"model": ErrorResponse}, 503: {"model": ReadinessResponse}},
    )
    async def health_ready() -> ReadinessResponse | JSONResponse:
        db_ok, db_detail = db_health_check()
        rate_limit_ok, rate_limit_detail = rate_limit_health_check()
        checks = {
            "database": ReadinessCheck(ok=db_ok, detail=db_detail),
            "rate_limit_backend": ReadinessCheck(ok=rate_limit_ok, detail=rate_limit_detail),
        }
        payload = ReadinessResponse(
            status="ok" if db_ok and rate_limit_ok else "degraded",
            checks=checks,
        )
        if db_ok and rate_limit_ok:
            return payload
        return JSONResponse(status_code=503, content=payload.model_dump())

    @api.post(
        "/api/echo",
        tags=["system"],
        summary="Echo request payload",
        dependencies=protected_dependencies,
        response_model=EchoResponse,
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
    )
    async def echo(request: Request, _payload: dict = Body(default_factory=dict)) -> EchoResponse:
        try:
            data = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = {}
        if data is None:
            data = {}
        return EchoResponse(you_sent=data)
