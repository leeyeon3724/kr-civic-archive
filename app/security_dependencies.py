from __future__ import annotations

import hmac
from collections.abc import Callable
from typing import Any

from fastapi import Header, Request

from app.errors import http_error
from app.security_jwt import authorize_claims_for_request, validate_jwt_hs256


def build_api_key_dependency(config: Any) -> Callable[..., Any]:
    expected_key = config.API_KEY or ""
    require_api_key = bool(config.REQUIRE_API_KEY)

    async def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
        if not require_api_key:
            return
        if not x_api_key:
            raise http_error(
                401,
                "UNAUTHORIZED",
                "Unauthorized",
                details={"auth_type": "api_key", "reason": "missing_api_key"},
            )
        if not hmac.compare_digest(x_api_key, expected_key):
            raise http_error(
                401,
                "UNAUTHORIZED",
                "Unauthorized",
                details={"auth_type": "api_key", "reason": "invalid_api_key"},
            )

    return verify_api_key


def build_jwt_dependency(
    config: Any,
    *,
    validate_jwt: Callable[[str, Any], dict[str, Any]] = validate_jwt_hs256,
    authorize_claims: Callable[[Request, dict[str, Any], Any], None] = authorize_claims_for_request,
) -> Callable[..., Any]:
    require_jwt = bool(config.REQUIRE_JWT)

    async def verify_jwt(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> None:
        if not require_jwt:
            return

        if not authorization:
            raise http_error(
                401,
                "UNAUTHORIZED",
                "Unauthorized",
                details={"auth_type": "jwt", "reason": "missing_authorization_header"},
            )
        scheme, _, value = authorization.partition(" ")
        token = value.strip()
        if scheme.lower() != "bearer" or not token:
            raise http_error(
                401,
                "UNAUTHORIZED",
                "Unauthorized",
                details={"auth_type": "jwt", "reason": "invalid_authorization_header"},
            )

        claims = validate_jwt(token, config)
        authorize_claims(request, claims, config)
        request.state.auth_claims = claims

    return verify_jwt
