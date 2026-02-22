from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

ProtectedDependencies: TypeAlias = list[Any]
DBHealthCheck: TypeAlias = Callable[[], tuple[bool, str | None]]
RateLimitHealthCheck: TypeAlias = Callable[[], tuple[bool, str | None]]
