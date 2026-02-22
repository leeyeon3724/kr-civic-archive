from __future__ import annotations

from typing import cast

from app.ports.dto import NewsArticleRecordDTO, NewsArticleUpsertDTO
from app.ports.repositories import NewsRepositoryPort
from app.ports.services import NewsServicePort
from app.repositories.news_repository import NewsRepository
from app.repositories.session_provider import ConnectionProvider, ensure_connection_provider
from app.services.common import (
    ensure_item_object,
    normalize_list_window,
    normalize_optional_filters,
    require_stripped_text,
)
from app.utils import (
    ensure_temporal_input,
    normalize_optional_str,
    parse_datetime,
)


def _normalize_article(item: dict[str, object]) -> NewsArticleUpsertDTO:
    item = ensure_item_object(item)
    title = require_stripped_text(item, "title", error_message="Missing required fields: title, url")
    url = require_stripped_text(item, "url", error_message="Missing required fields: title, url")

    return {
        "source": normalize_optional_str(item.get("source")),
        "title": title,
        "url": url,
        "published_at": parse_datetime(
            ensure_temporal_input(
                item.get("published_at"),
                error_message="published_at format error: {value}",
            )
        ),
        "author": normalize_optional_str(item.get("author")),
        "summary": normalize_optional_str(item.get("summary")),
        "content": normalize_optional_str(item.get("content")),
        "keywords": item.get("keywords"),
    }


class NewsService:
    def __init__(self, *, repository: NewsRepositoryPort) -> None:
        self._repository = repository

    @staticmethod
    def normalize_article(item: dict[str, object]) -> NewsArticleUpsertDTO:
        return _normalize_article(item)

    def upsert_articles(self, items: list[NewsArticleUpsertDTO]) -> tuple[int, int]:
        return self._repository.upsert_articles(items)

    def list_articles(
        self,
        *,
        q: str | None,
        source: str | None,
        date_from: str | None,
        date_to: str | None,
        page: int,
        size: int,
    ) -> tuple[list[NewsArticleRecordDTO], int]:
        page, size, date_from, date_to = normalize_list_window(
            page=page,
            size=size,
            date_from=date_from,
            date_to=date_to,
        )
        normalized_filters = normalize_optional_filters({"q": q, "source": source})
        return self._repository.list_articles(
            q=normalized_filters["q"],
            source=normalized_filters["source"],
            date_from=date_from,
            date_to=date_to,
            page=page,
            size=size,
        )

    def get_article(self, item_id: int) -> NewsArticleRecordDTO | None:
        return self._repository.get_article(item_id)

    def delete_article(self, item_id: int) -> bool:
        return self._repository.delete_article(item_id)


def build_news_service(
    *,
    connection_provider: ConnectionProvider,
    repository: NewsRepositoryPort | None = None,
) -> NewsServicePort:
    selected_repository = repository or NewsRepository(connection_provider=connection_provider)
    return cast(NewsServicePort, cast(object, NewsService(repository=selected_repository)))


def normalize_article(item: dict[str, object]) -> NewsArticleUpsertDTO:
    return _normalize_article(item)


def upsert_articles(
    items: list[NewsArticleUpsertDTO],
    *,
    service: NewsServicePort | None = None,
    connection_provider: ConnectionProvider | None = None,
) -> tuple[int, int]:
    active_service = service or build_news_service(connection_provider=ensure_connection_provider(connection_provider))
    return active_service.upsert_articles(items)


def list_articles(
    *,
    q: str | None,
    source: str | None,
    date_from: str | None,
    date_to: str | None,
    page: int,
    size: int,
    service: NewsServicePort | None = None,
    connection_provider: ConnectionProvider | None = None,
) -> tuple[list[NewsArticleRecordDTO], int]:
    active_service = service or build_news_service(connection_provider=ensure_connection_provider(connection_provider))
    return active_service.list_articles(
        q=q,
        source=source,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=size,
    )


def get_article(
    item_id: int,
    *,
    service: NewsServicePort | None = None,
    connection_provider: ConnectionProvider | None = None,
) -> NewsArticleRecordDTO | None:
    active_service = service or build_news_service(connection_provider=ensure_connection_provider(connection_provider))
    return active_service.get_article(item_id)


def delete_article(
    item_id: int,
    *,
    service: NewsServicePort | None = None,
    connection_provider: ConnectionProvider | None = None,
) -> bool:
    active_service = service or build_news_service(connection_provider=ensure_connection_provider(connection_provider))
    return active_service.delete_article(item_id)
