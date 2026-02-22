from __future__ import annotations

from app.config import Config

JWT_SECRET_MIN_BYTES = 32


def validate_startup_config(config: Config) -> None:
    if config.BOOTSTRAP_TABLES_ON_STARTUP:
        raise RuntimeError("BOOTSTRAP_TABLES_ON_STARTUP is disabled. Run 'alembic upgrade head' before startup.")
    if config.REQUIRE_API_KEY and not (config.API_KEY or "").strip():
        raise RuntimeError("REQUIRE_API_KEY=1 requires API_KEY to be set.")
    jwt_secret = (config.JWT_SECRET or "").strip()
    if config.REQUIRE_JWT and not jwt_secret:
        raise RuntimeError("REQUIRE_JWT=1 requires JWT_SECRET to be set.")
    if config.REQUIRE_JWT and len(jwt_secret.encode("utf-8")) < JWT_SECRET_MIN_BYTES:
        raise RuntimeError(f"JWT_SECRET must be at least {JWT_SECRET_MIN_BYTES} bytes.")
    if config.REQUIRE_JWT and (config.JWT_ALGORITHM or "").strip().upper() != "HS256":
        raise RuntimeError("JWT_ALGORITHM must be HS256.")
    if config.JWT_LEEWAY_SECONDS < 0:
        raise RuntimeError("JWT_LEEWAY_SECONDS must be greater than or equal to 0.")
    if config.rate_limit_backend not in {"memory", "redis"}:
        raise RuntimeError("RATE_LIMIT_BACKEND must be one of: memory, redis.")
    if config.rate_limit_backend == "redis" and not (config.REDIS_URL or "").strip():
        raise RuntimeError("RATE_LIMIT_BACKEND=redis requires REDIS_URL to be set.")
    if config.RATE_LIMIT_REDIS_FAILURE_COOLDOWN_SECONDS <= 0:
        raise RuntimeError("RATE_LIMIT_REDIS_FAILURE_COOLDOWN_SECONDS must be greater than 0.")
    if config.DB_POOL_SIZE <= 0:
        raise RuntimeError("DB_POOL_SIZE must be greater than 0.")
    if config.DB_MAX_OVERFLOW < 0:
        raise RuntimeError("DB_MAX_OVERFLOW must be greater than or equal to 0.")
    if config.DB_POOL_TIMEOUT_SECONDS <= 0:
        raise RuntimeError("DB_POOL_TIMEOUT_SECONDS must be greater than 0.")
    if config.DB_POOL_RECYCLE_SECONDS <= 0:
        raise RuntimeError("DB_POOL_RECYCLE_SECONDS must be greater than 0.")
    if config.DB_CONNECT_TIMEOUT_SECONDS <= 0:
        raise RuntimeError("DB_CONNECT_TIMEOUT_SECONDS must be greater than 0.")
    if config.DB_STATEMENT_TIMEOUT_MS <= 0:
        raise RuntimeError("DB_STATEMENT_TIMEOUT_MS must be greater than 0.")
    if config.INGEST_MAX_BATCH_ITEMS <= 0:
        raise RuntimeError("INGEST_MAX_BATCH_ITEMS must be greater than 0.")
    if config.MAX_REQUEST_BODY_BYTES <= 0:
        raise RuntimeError("MAX_REQUEST_BODY_BYTES must be greater than 0.")
    if config.strict_security_mode:
        if not (config.REQUIRE_API_KEY or config.REQUIRE_JWT):
            raise RuntimeError("Strict security mode requires REQUIRE_API_KEY=1 or REQUIRE_JWT=1.")
        if "*" in config.allowed_hosts_list:
            raise RuntimeError("Strict security mode requires explicit ALLOWED_HOSTS (wildcard is not allowed).")
        if "*" in config.cors_allow_origins_list:
            raise RuntimeError("Strict security mode requires explicit CORS_ALLOW_ORIGINS (wildcard is not allowed).")
        if config.RATE_LIMIT_PER_MINUTE <= 0:
            raise RuntimeError("Strict security mode requires RATE_LIMIT_PER_MINUTE > 0.")
