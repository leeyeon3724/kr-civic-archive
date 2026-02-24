import time as _time
from contextlib import contextmanager
from typing import Any, Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


class _InstrumentedConnection:
    """Wraps a SQLAlchemy connection to record per-query latency."""

    def __init__(self, conn: Any, histogram: Any) -> None:
        self._conn = conn
        self._histogram = histogram

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        started = _time.perf_counter()
        try:
            return self._conn.execute(*args, **kwargs)
        finally:
            self._histogram.observe(_time.perf_counter() - started)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


@contextmanager
def instrumented_begin(engine: Engine) -> Generator[Any, None, None]:
    from app.observability import DB_QUERY_DURATION

    with engine.begin() as conn:
        yield _InstrumentedConnection(conn, DB_QUERY_DURATION)


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
