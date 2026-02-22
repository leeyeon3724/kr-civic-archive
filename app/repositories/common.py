from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import bindparam

from app.repositories.session_provider import ConnectionProvider, open_connection_scope


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def to_json_recordset(items: list[dict[str, Any]]) -> str:
    return json.dumps(items, ensure_ascii=False, default=_json_default, separators=(",", ":"))


def dedupe_rows_by_key(items: list[dict[str, Any]], *, key: str) -> list[dict[str, Any]]:
    """Keep the last row per key while preserving relative order of retained rows."""
    seen: set[Any] = set()
    deduped_reversed: list[dict[str, Any]] = []
    for item in reversed(items):
        key_value = item.get(key)
        if key_value in seen:
            continue
        seen.add(key_value)
        deduped_reversed.append(item)
    deduped_reversed.reverse()
    return deduped_reversed


def execute_paginated_query(
    *,
    list_stmt: Any,
    count_stmt: Any,
    params: dict[str, Any],
    page: int,
    size: int,
    connection_provider: ConnectionProvider,
) -> tuple[list[dict[str, Any]], int]:
    with open_connection_scope(connection_provider) as conn:
        rows = conn.execute(
            list_stmt,
            {**params, "limit": size, "offset": (page - 1) * size},
        ).mappings().all()
        total = conn.execute(count_stmt, params).scalar() or 0

    return [dict(row) for row in rows], int(total)


def add_truthy_equals_filter(
    *,
    value: Any,
    param_name: str,
    column_expr: Any,
    conditions: list[Any],
    params: dict[str, Any],
) -> None:
    if not value:
        return
    conditions.append(column_expr == bindparam(param_name))
    params[param_name] = value


def add_not_none_equals_filter(
    *,
    value: Any,
    param_name: str,
    column_expr: Any,
    conditions: list[Any],
    params: dict[str, Any],
) -> None:
    if value is None:
        return
    conditions.append(column_expr == bindparam(param_name))
    params[param_name] = value


def execute_filtered_paginated_query(
    *,
    list_stmt: Any,
    count_stmt: Any,
    conditions: list[Any],
    params: dict[str, Any],
    page: int,
    size: int,
    connection_provider: ConnectionProvider,
) -> tuple[list[dict[str, Any]], int]:
    for condition in conditions:
        list_stmt = list_stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    return execute_paginated_query(
        list_stmt=list_stmt,
        count_stmt=count_stmt,
        params=params,
        page=page,
        size=size,
        connection_provider=connection_provider,
    )
