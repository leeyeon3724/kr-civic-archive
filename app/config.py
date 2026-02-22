from __future__ import annotations

from typing import List

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "app_user"
    POSTGRES_PASSWORD: str = "change_me"
    POSTGRES_DB: str = "civic_archive"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT_SECONDS: int = 30
    DB_POOL_RECYCLE_SECONDS: int = 3600
    DB_CONNECT_TIMEOUT_SECONDS: int = 3
    DB_STATEMENT_TIMEOUT_MS: int = 5000
    INGEST_MAX_BATCH_ITEMS: int = 200
    MAX_REQUEST_BODY_BYTES: int = 1_048_576

    DEBUG: bool = False
    APP_ENV: str = "development"
    SECURITY_STRICT_MODE: bool = False
    PORT: int = 8000
    BOOTSTRAP_TABLES_ON_STARTUP: bool = False

    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True
    REQUIRE_API_KEY: bool = False
    API_KEY: str | None = None
    REQUIRE_JWT: bool = False
    JWT_SECRET: str | None = None
    JWT_ALGORITHM: str = "HS256"
    JWT_LEEWAY_SECONDS: int = 0
    JWT_AUDIENCE: str | None = None
    JWT_ISSUER: str | None = None
    JWT_SCOPE_READ: str = "archive:read"
    JWT_SCOPE_WRITE: str = "archive:write"
    JWT_SCOPE_DELETE: str = "archive:delete"
    JWT_ADMIN_ROLE: str = "admin"
    RATE_LIMIT_PER_MINUTE: int = 0
    RATE_LIMIT_BACKEND: str = "memory"
    REDIS_URL: str | None = None
    RATE_LIMIT_REDIS_PREFIX: str = "civic_archive:rate_limit"
    RATE_LIMIT_REDIS_WINDOW_SECONDS: int = 65
    RATE_LIMIT_REDIS_FAILURE_COOLDOWN_SECONDS: int = 5
    RATE_LIMIT_FAIL_OPEN: bool = True
    TRUSTED_PROXY_CIDRS: str = ""
    CORS_ALLOW_ORIGINS: str = "*"
    CORS_ALLOW_METHODS: str = "GET,POST,DELETE,OPTIONS"
    CORS_ALLOW_HEADERS: str = "*"
    ALLOWED_HOSTS: str = "*"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return URL.create(
            "postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=int(self.POSTGRES_PORT),
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)

    @staticmethod
    def _parse_csv(value: str) -> List[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def cors_allow_origins_list(self) -> List[str]:
        values = self._parse_csv(self.CORS_ALLOW_ORIGINS)
        return values or ["*"]

    @property
    def cors_allow_methods_list(self) -> List[str]:
        values = self._parse_csv(self.CORS_ALLOW_METHODS)
        return values or ["GET", "POST", "DELETE", "OPTIONS"]

    @property
    def cors_allow_headers_list(self) -> List[str]:
        values = self._parse_csv(self.CORS_ALLOW_HEADERS)
        return values or ["*"]

    @property
    def allowed_hosts_list(self) -> List[str]:
        values = self._parse_csv(self.ALLOWED_HOSTS)
        return values or ["*"]

    @property
    def trusted_proxy_cidrs_list(self) -> List[str]:
        return self._parse_csv(self.TRUSTED_PROXY_CIDRS)

    @property
    def rate_limit_backend(self) -> str:
        value = (self.RATE_LIMIT_BACKEND or "").strip().lower()
        return value or "memory"

    @property
    def app_env(self) -> str:
        value = (self.APP_ENV or "").strip().lower()
        return value or "development"

    @property
    def strict_security_mode(self) -> bool:
        if bool(self.SECURITY_STRICT_MODE):
            return True
        return self.app_env in {"prod", "production"}
