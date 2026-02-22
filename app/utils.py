from datetime import date, datetime
from typing import Any

from fastapi import HTTPException

from app.errors import http_error
from app.parsing import parse_date_value, parse_datetime_value


def bad_request(message: str) -> HTTPException:
    return http_error(400, "BAD_REQUEST", message)


def normalize_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def parse_datetime(dt: str | datetime | date | None) -> datetime | None:
    try:
        return parse_datetime_value(dt)
    except ValueError:
        raise bad_request(f"published_at format error: {dt}")


def parse_date(d: str | datetime | date | None) -> datetime | None:
    try:
        parsed = parse_date_value(d)
    except ValueError:
        raise bad_request(f"meeting_date format error (YYYY-MM-DD): {d}")
    if parsed is None:
        return None
    return datetime.combine(parsed, datetime.min.time())


def combine_meeting_no(session_val, meeting_no_raw, meeting_no_int) -> str | None:
    if isinstance(meeting_no_raw, str) and meeting_no_raw.strip():
        return meeting_no_raw.strip()
    if meeting_no_int is not None and session_val:
        return f"{session_val} {int(meeting_no_int)}\ucc28"
    if meeting_no_int is not None:
        return f"{int(meeting_no_int)}\ucc28"
    return session_val


def coerce_meeting_no_int(meeting_no_raw: Any) -> int | None:
    if meeting_no_raw is None or isinstance(meeting_no_raw, str):
        return None
    try:
        return int(meeting_no_raw)
    except (TypeError, ValueError):
        return None


def normalize_date_filter(value: str | None, *, field_name: str) -> str | None:
    normalized = normalize_optional_str(value)
    if normalized is None:
        return None
    try:
        parse_date_value(normalized)
    except ValueError:
        raise bad_request(f"{field_name} format error (YYYY-MM-DD): {value}")
    return normalized


def normalize_pagination(page: int, size: int) -> tuple[int, int]:
    if page < 1:
        raise bad_request("page must be greater than or equal to 1.")
    if size < 1:
        raise bad_request("size must be greater than or equal to 1.")
    if size > 200:
        raise bad_request("size must be less than or equal to 200.")
    return page, size
