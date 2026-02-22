from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

DATETIME_FORMATS: tuple[str, ...] = (
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)


def _normalize_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_datetime_value(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return _normalize_utc(raw)
    if isinstance(raw, date):
        return datetime.combine(raw, datetime.min.time(), tzinfo=timezone.utc)
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            return None
        if "T" in value or " " in value:
            iso_candidate = value.replace("Z", "+00:00")
            try:
                return _normalize_utc(datetime.fromisoformat(iso_candidate))
            except ValueError:
                pass
        for fmt in DATETIME_FORMATS:
            try:
                return _normalize_utc(datetime.strptime(value, fmt))
            except ValueError:
                continue
    raise ValueError(f"datetime format error: {raw}")


def parse_date_value(raw: Any) -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("date must be YYYY-MM-DD") from exc
    raise ValueError("date must be YYYY-MM-DD")
