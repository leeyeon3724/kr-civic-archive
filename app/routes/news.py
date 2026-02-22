from datetime import date

from fastapi import APIRouter, Body, Depends, Query, Request

from app.errors import http_error
from app.ports.dto import NewsArticleUpsertDTO
from app.ports.services import NewsServicePort
from app.routes.common import ERROR_RESPONSES, enforce_ingest_batch_limit
from app.schemas import (
    DeleteResponse,
    NewsItemBase,
    NewsItemDetail,
    NewsListResponse,
    NewsUpsertPayload,
    UpsertResponse,
)
from app.services.providers import get_news_service

router = APIRouter(tags=["news"])


@router.post(
    "/api/news",
    summary="Upsert news items",
    response_model=UpsertResponse,
    status_code=201,
    responses=ERROR_RESPONSES,
)
def save_news(
    request: Request,
    payload: NewsUpsertPayload = Body(
        ...,
        examples=[
            {
                "source": "local-news",
                "title": "City budget hearing update",
                "url": "https://example.com/news/100",
                "published_at": "2026-02-17T09:30:00Z",
            },
            [
                {
                    "source": "local-news",
                    "title": "City budget hearing update",
                    "url": "https://example.com/news/100",
                },
                {
                    "source": "daily",
                    "title": "Council vote summary",
                    "url": "https://example.com/news/101",
                },
            ],
        ],
    ),
    service: NewsServicePort = Depends(get_news_service),
) -> UpsertResponse:
    payload_items = payload if isinstance(payload, list) else [payload]
    enforce_ingest_batch_limit(request, len(payload_items))
    items: list[NewsArticleUpsertDTO] = [service.normalize_article(item.model_dump()) for item in payload_items]
    inserted, updated = service.upsert_articles(items)
    return UpsertResponse(inserted=inserted, updated=updated)


@router.get(
    "/api/news",
    summary="List news items",
    response_model=NewsListResponse,
    responses=ERROR_RESPONSES,
)
def list_news(
    q: str | None = Query(default=None, description="title/summary/content partial text"),
    source: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    service: NewsServicePort = Depends(get_news_service),
) -> NewsListResponse:
    rows, total = service.list_articles(
        q=q,
        source=source,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
        page=page,
        size=size,
    )

    return NewsListResponse(page=page, size=size, total=total, items=[NewsItemBase.model_validate(row) for row in rows])


@router.get(
    "/api/news/{item_id}",
    summary="Get news item detail",
    response_model=NewsItemDetail,
    responses=ERROR_RESPONSES,
)
def get_news(item_id: int, service: NewsServicePort = Depends(get_news_service)) -> NewsItemDetail:
    row = service.get_article(item_id)
    if not row:
        raise http_error(404, "NOT_FOUND", "Not Found")
    return NewsItemDetail.model_validate(row)


@router.delete(
    "/api/news/{item_id}",
    summary="Delete news item",
    response_model=DeleteResponse,
    responses=ERROR_RESPONSES,
)
def delete_news(item_id: int, service: NewsServicePort = Depends(get_news_service)) -> DeleteResponse:
    deleted = service.delete_article(item_id)
    if not deleted:
        raise http_error(404, "NOT_FOUND", "Not Found")
    return DeleteResponse(status="deleted", id=item_id)
