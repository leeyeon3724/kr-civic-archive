from datetime import date

from fastapi import APIRouter, Body, Depends, Query, Request

from app.errors import http_error
from app.ports.dto import MinutesUpsertDTO
from app.ports.services import MinutesServicePort
from app.routes.common import ERROR_RESPONSES, enforce_ingest_batch_limit
from app.schemas import (
    DeleteResponse,
    MinutesItemBase,
    MinutesItemDetail,
    MinutesListResponse,
    MinutesUpsertPayload,
    UpsertResponse,
)
from app.services.providers import get_minutes_service

router = APIRouter(tags=["minutes"])


@router.post(
    "/api/minutes",
    summary="Upsert minutes items",
    response_model=UpsertResponse,
    status_code=201,
    responses=ERROR_RESPONSES,
)
def save_minutes(
    request: Request,
    payload: MinutesUpsertPayload = Body(
        ...,
        examples=[
            {
                "council": "seoul",
                "committee": "budget",
                "session": "301",
                "meeting_no": "301 4\ucc28",
                "url": "https://example.com/minutes/100",
                "meeting_date": "2026-02-17",
            }
        ],
    ),
    service: MinutesServicePort = Depends(get_minutes_service),
) -> UpsertResponse:
    payload_items = payload if isinstance(payload, list) else [payload]
    enforce_ingest_batch_limit(request, len(payload_items))
    items: list[MinutesUpsertDTO] = [service.normalize_minutes(item.model_dump()) for item in payload_items]
    inserted, updated = service.upsert_minutes(items)
    return UpsertResponse(inserted=inserted, updated=updated)


@router.get(
    "/api/minutes",
    summary="List minutes items",
    response_model=MinutesListResponse,
    responses=ERROR_RESPONSES,
)
def list_minutes(
    q: str | None = Query(default=None),
    council: str | None = Query(default=None),
    committee: str | None = Query(default=None),
    session: str | None = Query(default=None),
    meeting_no: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    service: MinutesServicePort = Depends(get_minutes_service),
) -> MinutesListResponse:
    rows, total = service.list_minutes(
        q=q,
        council=council,
        committee=committee,
        session=session,
        meeting_no=meeting_no,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
        page=page,
        size=size,
    )

    return MinutesListResponse(
        page=page,
        size=size,
        total=total,
        items=[MinutesItemBase.model_validate(row) for row in rows],
    )


@router.get(
    "/api/minutes/{item_id}",
    summary="Get minutes item detail",
    response_model=MinutesItemDetail,
    responses=ERROR_RESPONSES,
)
def get_minutes(item_id: int, service: MinutesServicePort = Depends(get_minutes_service)) -> MinutesItemDetail:
    row = service.get_minutes(item_id)
    if not row:
        raise http_error(404, "NOT_FOUND", "Not Found")
    return MinutesItemDetail.model_validate(row)


@router.delete(
    "/api/minutes/{item_id}",
    summary="Delete minutes item",
    response_model=DeleteResponse,
    responses=ERROR_RESPONSES,
)
def delete_minutes(item_id: int, service: MinutesServicePort = Depends(get_minutes_service)) -> DeleteResponse:
    deleted = service.delete_minutes(item_id)
    if not deleted:
        raise http_error(404, "NOT_FOUND", "Not Found")
    return DeleteResponse(status="deleted", id=item_id)
