from __future__ import annotations

from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError
from jwt.types import Options

from app.errors import http_error


def extract_values_set(claims: dict[str, Any], *keys: str) -> set[str]:
    values: set[str] = set()
    for key in keys:
        raw = claims.get(key)
        if isinstance(raw, str):
            if key == "scope":
                values.update(token for token in raw.split() if token)
            elif raw.strip():
                values.add(raw.strip())
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, str) and item.strip():
                    values.add(item.strip())
    return values


def required_scope_for_method(config: Any, method: str) -> str | None:
    normalized = (method or "").upper()
    if normalized in {"GET", "HEAD"}:
        return (config.JWT_SCOPE_READ or "").strip() or None
    if normalized in {"POST", "PUT", "PATCH"}:
        return (config.JWT_SCOPE_WRITE or "").strip() or None
    if normalized == "DELETE":
        return (config.JWT_SCOPE_DELETE or "").strip() or None
    return None


def validate_jwt_hs256(token: str, config: Any) -> dict[str, Any]:
    secret = (config.JWT_SECRET or "").strip()
    if not secret:
        raise http_error(401, "UNAUTHORIZED", "Unauthorized")

    audience = (config.JWT_AUDIENCE or "").strip() or None
    issuer = (config.JWT_ISSUER or "").strip() or None
    leeway_seconds = max(0, int(config.JWT_LEEWAY_SECONDS))

    options: Options = {
        "require": ["sub", "exp"],
        "verify_signature": True,
        "verify_exp": True,
        "verify_nbf": True,
        "verify_aud": audience is not None,
        "verify_iss": issuer is not None,
    }

    try:
        payload = jwt.decode(
            token,
            key=secret,
            algorithms=["HS256"],
            options=options,
            audience=audience,
            issuer=issuer,
            leeway=leeway_seconds,
        )
    except (InvalidTokenError, TypeError, ValueError):
        raise http_error(401, "UNAUTHORIZED", "Unauthorized")

    if not isinstance(payload, dict):
        raise http_error(401, "UNAUTHORIZED", "Unauthorized")
    return payload


def authorize_claims_for_request(request: Any, claims: dict[str, Any], config: Any) -> None:
    required_scope = required_scope_for_method(config, request.method)
    if not required_scope:
        return

    admin_role = (config.JWT_ADMIN_ROLE or "").strip()
    role_values = extract_values_set(claims, "role", "roles")
    if admin_role and admin_role in role_values:
        return

    scope_values = extract_values_set(claims, "scope", "scopes")
    if required_scope not in scope_values:
        raise http_error(403, "FORBIDDEN", "Forbidden")
