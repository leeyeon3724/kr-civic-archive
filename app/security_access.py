from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends


def build_protected_dependencies(
    config: Any,
    *,
    build_api_key_dependency: Callable[[Any], Callable[..., Any]],
    build_jwt_dependency: Callable[[Any], Callable[..., Any]],
    build_rate_limit_dependency: Callable[[Any], Callable[..., Any]],
) -> list[Any]:
    api_key_dependency = build_api_key_dependency(config)
    jwt_dependency = build_jwt_dependency(config)
    rate_limit_dependency = build_rate_limit_dependency(config)
    return [
        Depends(api_key_dependency),
        Depends(jwt_dependency),
        Depends(rate_limit_dependency),
    ]


def build_metrics_access_dependencies(
    config: Any,
    *,
    build_api_key_dependency: Callable[[Any], Callable[..., Any]],
    build_jwt_dependency: Callable[[Any], Callable[..., Any]],
) -> list[Any]:
    dependencies: list[Any] = []

    if bool(config.REQUIRE_API_KEY):
        dependencies.append(Depends(build_api_key_dependency(config)))
    if bool(config.REQUIRE_JWT):
        dependencies.append(Depends(build_jwt_dependency(config)))

    return dependencies
