from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def init_db(
    database_url: str,
    *,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_timeout_seconds: int = 30,
    pool_recycle_seconds: int = 3600,
    connect_timeout_seconds: int = 3,
    statement_timeout_ms: int = 5000,
) -> Engine:
    connect_args = {
        "connect_timeout": max(1, int(connect_timeout_seconds)),
        "options": (
            f"-c statement_timeout={max(1, int(statement_timeout_ms))} "
            "-c application_name=civic_archive_api "
            "-c timezone=UTC"
        ),
    }
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=max(1, int(pool_size)),
        max_overflow=max(0, int(max_overflow)),
        pool_timeout=max(1, int(pool_timeout_seconds)),
        pool_recycle=max(1, int(pool_recycle_seconds)),
        connect_args=connect_args,
        future=True,
    )
