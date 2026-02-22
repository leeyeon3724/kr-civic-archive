import logging
from contextlib import AbstractContextManager
from contextlib import asynccontextmanager
from contextlib import suppress
from typing import Any, cast

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.bootstrap import (
    register_core_middleware,
    register_domain_routes,
    register_exception_handlers,
    register_system_routes,
    validate_startup_config,
)
from app.config import Config
from app.database import init_db
from app.logging_config import configure_logging
from app.observability import register_observability
from app.security import (
    build_api_key_dependency,
    build_jwt_dependency,
    build_metrics_access_dependencies,
    build_rate_limit_dependency,
    check_rate_limit_backend_health,
)
from app.version import APP_VERSION

OPENAPI_TAGS: list[dict[str, str]] = [
    {"name": "system", "description": "System and health endpoints"},
    {"name": "news", "description": "News ingestion and search"},
    {"name": "minutes", "description": "Council minutes ingestion and search"},
    {"name": "segments", "description": "Speech segment ingestion and search"},
]

logger = logging.getLogger("civic_archive.api")


def create_app(app_config: Config | None = None) -> FastAPI:
    if app_config is None:
        app_config = Config()

    configure_logging(level=app_config.LOG_LEVEL, json_logs=app_config.LOG_JSON)

    @asynccontextmanager
    async def _lifespan(_api: FastAPI):
        try:
            yield
        finally:
            db_engine = getattr(_api.state, "db_engine", None)
            if db_engine is None or not hasattr(db_engine, "dispose"):
                return
            with suppress(Exception):
                db_engine.dispose()

    api = FastAPI(
        title="Civic Archive API",
        version=APP_VERSION,
        description="Local council archive API with FastAPI + PostgreSQL",
        openapi_tags=OPENAPI_TAGS,
        lifespan=_lifespan,
    )
    api.state.config = app_config

    validate_startup_config(app_config)
    register_core_middleware(api, app_config)

    db_engine = init_db(
        app_config.database_engine_url,
        pool_size=app_config.DB_POOL_SIZE,
        max_overflow=app_config.DB_MAX_OVERFLOW,
        pool_timeout_seconds=app_config.DB_POOL_TIMEOUT_SECONDS,
        pool_recycle_seconds=app_config.DB_POOL_RECYCLE_SECONDS,
        connect_timeout_seconds=app_config.DB_CONNECT_TIMEOUT_SECONDS,
        statement_timeout_ms=app_config.DB_STATEMENT_TIMEOUT_MS,
    )

    def connection_provider() -> AbstractContextManager[Connection]:
        return cast(AbstractContextManager[Connection], cast(object, db_engine.begin()))

    api.state.db_engine = db_engine
    api.state.connection_provider = connection_provider

    api_key_dependency = build_api_key_dependency(app_config)
    jwt_dependency = build_jwt_dependency(app_config)
    rate_limit_dependency = build_rate_limit_dependency(app_config)
    protected_dependencies: list[Any] = [
        Depends(api_key_dependency),
        Depends(jwt_dependency),
        Depends(rate_limit_dependency),
    ]
    metrics_dependencies = build_metrics_access_dependencies(app_config)
    register_observability(api, metrics_dependencies=metrics_dependencies)

    def db_health_check() -> tuple[bool, str | None]:
        try:
            with api.state.connection_provider() as conn:
                conn.execute(text("SELECT 1"))
            return True, None
        except Exception as exc:
            logger.exception("health_db_check_failed", extra={"error": type(exc).__name__})
            return False, "database connection failed"

    register_domain_routes(api, protected_dependencies=protected_dependencies)
    register_system_routes(
        api,
        protected_dependencies=protected_dependencies,
        db_health_check=db_health_check,
        rate_limit_health_check=lambda: check_rate_limit_backend_health(app_config),
    )
    register_exception_handlers(api, logger=logger)

    return api
