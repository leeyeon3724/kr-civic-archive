from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any, TypeAlias

ConnectionScope: TypeAlias = AbstractContextManager[Any]
ConnectionProvider: TypeAlias = Callable[[], ConnectionScope]


def ensure_connection_provider(provider: ConnectionProvider | None) -> ConnectionProvider:
    if provider is None:
        raise RuntimeError("connection provider is required")
    return provider


def open_connection_scope(provider: ConnectionProvider) -> ConnectionScope:
    return provider()
