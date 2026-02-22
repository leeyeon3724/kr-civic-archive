from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, bindparam, cast, text

from app.repositories.search import build_split_search_condition, build_split_search_params
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


def normalize_optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _extract_row_total(
    rows: list[dict[str, Any]],
    *,
    row_total_key: str,
) -> int | None:
    if not rows:
        return None
    if row_total_key not in rows[0]:
        return None

    raw_total = rows[0][row_total_key]
    for row in rows:
        row.pop(row_total_key, None)
    if raw_total is None:
        return None
    return int(raw_total)


def execute_paginated_query(
    *,
    list_stmt: Any,
    count_stmt: Any,
    params: dict[str, Any],
    page: int,
    size: int,
    connection_provider: ConnectionProvider,
    row_total_key: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    with open_connection_scope(connection_provider) as conn:
        rows = conn.execute(
            list_stmt,
            {**params, "limit": size, "offset": (page - 1) * size},
        ).mappings().all()
        row_dicts = [dict(row) for row in rows]
        if row_total_key:
            total = _extract_row_total(row_dicts, row_total_key=row_total_key)
            if total is None:
                if page == 1 and len(row_dicts) < size:
                    total = len(row_dicts)
                else:
                    total = conn.execute(count_stmt, params).scalar() or 0
        else:
            # 첫 페이지 결과가 page size보다 작으면 전체 건수는 rows 길이와 동일합니다.
            # 이 경우 count query를 생략해 DB round-trip을 줄입니다.
            if page == 1 and len(row_dicts) < size:
                total = len(row_dicts)
            else:
                total = conn.execute(count_stmt, params).scalar() or 0

    return row_dicts, int(total)


def add_truthy_equals_filter(
    *,
    value: Any,
    param_name: str,
    column_expr: Any,
    conditions: list[Any],
    params: dict[str, Any],
) -> None:
    if isinstance(value, str):
        value = normalize_optional_str(value)
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


def add_split_search_filter(
    *,
    query: str | None,
    columns: list[Any],
    conditions: list[Any],
    params: dict[str, Any],
) -> None:
    normalized_query = normalize_optional_str(query)
    if normalized_query is None:
        return
    conditions.append(build_split_search_condition(columns=columns))
    params.update(build_split_search_params(normalized_query))


def add_date_from_filter(
    *,
    value: str | None,
    param_name: str,
    column_expr: Any,
    conditions: list[Any],
    params: dict[str, Any],
) -> None:
    normalized_value = normalize_optional_str(value)
    if normalized_value is None:
        return
    conditions.append(column_expr >= bindparam(param_name))
    params[param_name] = normalized_value


def add_date_to_filter_inclusive(
    *,
    value: str | None,
    param_name: str,
    column_expr: Any,
    conditions: list[Any],
    params: dict[str, Any],
) -> None:
    normalized_value = normalize_optional_str(value)
    if normalized_value is None:
        return
    conditions.append(column_expr <= bindparam(param_name))
    params[param_name] = normalized_value


def add_date_to_filter_next_day_exclusive(
    *,
    value: str | None,
    param_name: str,
    column_expr: Any,
    conditions: list[Any],
    params: dict[str, Any],
) -> None:
    normalized_value = normalize_optional_str(value)
    if normalized_value is None:
        return
    conditions.append(column_expr < (cast(bindparam(param_name), Date) + text("INTERVAL '1 day'")))
    params[param_name] = normalized_value


def execute_filtered_paginated_query(
    *,
    list_stmt: Any,
    count_stmt: Any,
    conditions: list[Any],
    params: dict[str, Any],
    page: int,
    size: int,
    connection_provider: ConnectionProvider,
    row_total_key: str | None = None,
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
        row_total_key=row_total_key,
    )
