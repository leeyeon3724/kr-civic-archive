from __future__ import annotations

from typing import Any, Callable

from fastapi import Depends, Request

from app.errors import http_error
from app.security_dependencies import (
    build_api_key_dependency as _build_api_key_dependency_impl,
    build_jwt_dependency as _build_jwt_dependency_impl,
)
from app.security_jwt import (
    authorize_claims_for_request as _authorize_claims_for_request_impl,
    extract_values_set as _extract_values_set_impl,
    required_scope_for_method as _required_scope_for_method_impl,
    validate_jwt_hs256 as _validate_jwt_hs256_impl,
)
from app.security_proxy import (
    TrustedProxyNetwork,
    client_key as _client_key_impl,
    is_trusted_proxy as _is_trusted_proxy_impl,
    parse_trusted_proxy_networks as _parse_trusted_proxy_networks_impl,
    remote_ip as _remote_ip_impl,
)
from app.security_rate_limit import (
    InMemoryRateLimiter as _InMemoryRateLimiterImpl,
    RedisBaseError as _RedisBaseErrorImpl,
    RedisNoScriptError as _RedisNoScriptErrorImpl,
    RedisRateLimiter as _RedisRateLimiterImpl,
    build_rate_limiter as _build_rate_limiter_impl,
    check_rate_limit_backend_health as _check_rate_limit_backend_health_impl,
    redis as _redis_impl,
)

redis_module: Any | None = _redis_impl
RedisBaseError: type[Exception] = _RedisBaseErrorImpl
RedisNoScriptError: type[Exception] = _RedisNoScriptErrorImpl

# Backward-compatible aliases for existing tests/runtime monkeypatch hooks.
redis = redis_module
RedisError = RedisBaseError
NoScriptError = RedisNoScriptError

InMemoryRateLimiter = _InMemoryRateLimiterImpl


class RedisRateLimiter(_RedisRateLimiterImpl):
    def __init__(
        self,
        *,
        requests_per_minute: int,
        redis_url: str,
        key_prefix: str,
        window_seconds: int,
        failure_cooldown_seconds: int,
        fail_open: bool,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        super().__init__(
            requests_per_minute=requests_per_minute,
            redis_url=redis_url,
            key_prefix=key_prefix,
            window_seconds=window_seconds,
            failure_cooldown_seconds=failure_cooldown_seconds,
            fail_open=fail_open,
            monotonic=monotonic,
            redis_dependency=redis,
            redis_base_error=RedisBaseError,
            redis_no_script_error=RedisNoScriptError,
        )


def _extract_values_set(claims: dict, *keys: str) -> set[str]:
    return _extract_values_set_impl(claims, *keys)


def _required_scope_for_method(config, method: str) -> str | None:
    return _required_scope_for_method_impl(config, method)


def _validate_jwt_hs256(token: str, config) -> dict:
    return _validate_jwt_hs256_impl(token, config)


def _authorize_claims_for_request(request: Request, claims: dict, config) -> None:
    _authorize_claims_for_request_impl(request, claims, config)


def _parse_trusted_proxy_networks(cidrs: list[str]) -> list[TrustedProxyNetwork]:
    return _parse_trusted_proxy_networks_impl(cidrs)


def _remote_ip(request: Request) -> str:
    return _remote_ip_impl(request)


def _is_trusted_proxy(remote_ip: str, trusted_proxy_networks: list[TrustedProxyNetwork]) -> bool:
    return _is_trusted_proxy_impl(remote_ip, trusted_proxy_networks)


def _client_key(request: Request, *, trusted_proxy_networks: list[TrustedProxyNetwork]) -> str:
    return _client_key_impl(
        request,
        trusted_proxy_networks=trusted_proxy_networks,
        remote_ip_resolver=_remote_ip,
    )


def _build_rate_limiter(config):
    return _build_rate_limiter_impl(
        config,
        redis_rate_limiter_cls=RedisRateLimiter,
        in_memory_rate_limiter_cls=InMemoryRateLimiter,
    )


def check_rate_limit_backend_health(config) -> tuple[bool, str | None]:
    return _check_rate_limit_backend_health_impl(
        config,
        redis_dependency=redis,
        redis_base_error=RedisBaseError,
    )


def build_api_key_dependency(config) -> Callable:
    return _build_api_key_dependency_impl(config)


def build_jwt_dependency(config) -> Callable:
    return _build_jwt_dependency_impl(
        config,
        validate_jwt=_validate_jwt_hs256,
        authorize_claims=_authorize_claims_for_request,
    )


def build_rate_limit_dependency(config) -> Callable:
    limiter = _build_rate_limiter(config)
    trusted_proxy_networks = _parse_trusted_proxy_networks(config.trusted_proxy_cidrs_list)

    async def verify_rate_limit(request: Request) -> None:
        if not limiter.enabled:
            return
        if not limiter.allow(_client_key(request, trusted_proxy_networks=trusted_proxy_networks)):
            raise http_error(
                429,
                "RATE_LIMITED",
                "Too Many Requests",
                details={
                    "reason": "rate_limit_exceeded",
                    "limit_per_minute": int(config.RATE_LIMIT_PER_MINUTE),
                    "backend": str(config.rate_limit_backend),
                },
            )

    return verify_rate_limit


def build_metrics_access_dependencies(config: Any) -> list[Any]:
    dependencies: list[Any] = []

    if bool(config.REQUIRE_API_KEY):
        dependencies.append(Depends(build_api_key_dependency(config)))
    if bool(config.REQUIRE_JWT):
        dependencies.append(Depends(build_jwt_dependency(config)))

    # 운영 관측성 엔드포인트는 API 보호 정책과 분리해 운영합니다.
    # 기본 동작은 API 보호 정책만 따릅니다.
    return dependencies
