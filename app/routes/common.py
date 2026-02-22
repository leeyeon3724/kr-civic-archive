from datetime import date
from typing import Any, TypeVar

from fastapi import Request

from app.errors import http_error
from app.schemas import ErrorResponse

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}


def enforce_ingest_batch_limit(request: Request, batch_size: int) -> None:
    config = getattr(request.app.state, "config", None)
    limit = int(getattr(config, "INGEST_MAX_BATCH_ITEMS", 200))
    if batch_size > limit:
        raise http_error(
            413,
            "PAYLOAD_TOO_LARGE",
            "Payload Too Large",
            details={"max_batch_items": limit, "received_batch_items": int(batch_size)},
        )


PayloadItemT = TypeVar("PayloadItemT")
ResourceT = TypeVar("ResourceT")


def normalize_ingest_payload(
    request: Request,
    payload: PayloadItemT | list[PayloadItemT],
) -> list[PayloadItemT]:
    payload_items = payload if isinstance(payload, list) else [payload]
    enforce_ingest_batch_limit(request, len(payload_items))
    return payload_items


def ensure_resource_found(resource: ResourceT | None) -> ResourceT:
    if not resource:
        raise http_error(404, "NOT_FOUND", "Not Found")
    return resource


def ensure_delete_succeeded(deleted: bool) -> None:
    if not deleted:
        raise http_error(404, "NOT_FOUND", "Not Found")


def to_date_filter(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
