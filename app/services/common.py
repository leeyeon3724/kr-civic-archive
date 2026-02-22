from __future__ import annotations

from collections.abc import Mapping

from app.utils import bad_request, normalize_date_filter, normalize_optional_str, normalize_pagination


def ensure_item_object(item: object) -> dict[str, object]:
    if not isinstance(item, dict):
        raise bad_request("Each item must be a JSON object.")
    return item


def require_stripped_text(
    item: Mapping[str, object],
    field_name: str,
    *,
    error_message: str,
) -> str:
    value = item.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise bad_request(error_message)
    return value.strip()


def normalize_optional_filters(filters: Mapping[str, str | None]) -> dict[str, str | None]:
    return {key: normalize_optional_str(value) for key, value in filters.items()}


def normalize_list_window(
    *,
    page: int,
    size: int,
    date_from: str | None,
    date_to: str | None,
) -> tuple[int, int, str | None, str | None]:
    normalized_page, normalized_size = normalize_pagination(page, size)
    normalized_date_from = normalize_date_filter(date_from, field_name="from")
    normalized_date_to = normalize_date_filter(date_to, field_name="to")
    return normalized_page, normalized_size, normalized_date_from, normalized_date_to
