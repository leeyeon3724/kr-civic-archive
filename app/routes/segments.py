from datetime import date

from fastapi import APIRouter, Body, Depends, Query, Request

from app.errors import http_error
from app.ports.dto import SegmentUpsertDTO
from app.ports.services import SegmentsServicePort
from app.routes.common import ERROR_RESPONSES, enforce_ingest_batch_limit
from app.schemas import (
    DeleteResponse,
    InsertResponse,
    SegmentsInsertPayload,
    SegmentsItemBase,
    SegmentsItemDetail,
    SegmentsListResponse,
)
from app.services.providers import get_segments_service

router = APIRouter(tags=["segments"])


@router.post(
    "/api/segments",
    summary="Insert speech segments",
    response_model=InsertResponse,
    status_code=201,
    responses=ERROR_RESPONSES,
)
def save_segments(
    request: Request,
    payload: SegmentsInsertPayload = Body(
        ...,
        examples=[
            {
                "council": "seoul",
                "committee": "budget",
                "session": "301",
                "meeting_no": "301 4\ucc28",
                "meeting_date": "2026-02-17",
                "content": "segment text",
                "importance": 2,
            }
        ],
    ),
    service: SegmentsServicePort = Depends(get_segments_service),
) -> InsertResponse:
    payload_items = payload if isinstance(payload, list) else [payload]
    enforce_ingest_batch_limit(request, len(payload_items))
    items: list[SegmentUpsertDTO] = [service.normalize_segment(item.model_dump()) for item in payload_items]
    inserted = service.insert_segments(items)
    return InsertResponse(inserted=inserted)


@router.get(
    "/api/segments",
    summary="List speech segments",
    response_model=SegmentsListResponse,
    responses=ERROR_RESPONSES,
)
def list_segments(
    q: str | None = Query(default=None),
    council: str | None = Query(default=None),
    committee: str | None = Query(default=None),
    session: str | None = Query(default=None),
    meeting_no: str | None = Query(default=None),
    importance: int | None = Query(default=None, ge=1, le=3),
    party: str | None = Query(default=None),
    constituency: str | None = Query(default=None),
    department: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    service: SegmentsServicePort = Depends(get_segments_service),
) -> SegmentsListResponse:
    rows, total = service.list_segments(
        q=q,
        council=council,
        committee=committee,
        session=session,
        meeting_no=meeting_no,
        importance=importance,
        party=party,
        constituency=constituency,
        department=department,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
        page=page,
        size=size,
    )

    return SegmentsListResponse(
        page=page,
        size=size,
        total=total,
        items=[SegmentsItemBase.model_validate(row) for row in rows],
    )


@router.get(
    "/api/segments/{item_id}",
    summary="Get speech segment detail",
    response_model=SegmentsItemDetail,
    responses=ERROR_RESPONSES,
)
def get_segment(item_id: int, service: SegmentsServicePort = Depends(get_segments_service)) -> SegmentsItemDetail:
    row = service.get_segment(item_id)
    if not row:
        raise http_error(404, "NOT_FOUND", "Not Found")
    return SegmentsItemDetail.model_validate(row)


@router.delete(
    "/api/segments/{item_id}",
    summary="Delete speech segment",
    response_model=DeleteResponse,
    responses=ERROR_RESPONSES,
)
def delete_segment(item_id: int, service: SegmentsServicePort = Depends(get_segments_service)) -> DeleteResponse:
    deleted = service.delete_segment(item_id)
    if not deleted:
        raise http_error(404, "NOT_FOUND", "Not Found")
    return DeleteResponse(status="deleted", id=item_id)
