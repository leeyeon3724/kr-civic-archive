from __future__ import annotations

from datetime import date, datetime
from typing import cast

from app.ports.dto import NewsArticleRecordDTO, NewsArticleUpsertDTO
from app.ports.repositories import NewsRepositoryPort
from app.ports.services import NewsServicePort
from app.repositories.news_repository import NewsRepository
from app.repositories.session_provider import ConnectionProvider, ensure_connection_provider
from app.utils import bad_request, normalize_date_filter, normalize_optional_str, normalize_pagination, parse_datetime


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _as_datetime_input(value: object) -> str | datetime | date | None:
    if value is None or isinstance(value, (str, datetime, date)):
        return value
    raise bad_request(f"published_at format error: {value}")


def _normalize_article(item: dict[str, object]) -> NewsArticleUpsertDTO:
    if not isinstance(item, dict):
        raise bad_request("Each item must be a JSON object.")

    title = item.get("title")
    url = item.get("url")
    if not isinstance(title, str) or not title.strip() or not isinstance(url, str) or not url.strip():
        raise bad_request("Missing required fields: title, url")

    return {
        "source": _optional_str(item.get("source")),
        "title": title.strip(),
        "url": url.strip(),
        "published_at": parse_datetime(_as_datetime_input(item.get("published_at"))),
        "author": _optional_str(item.get("author")),
        "summary": _optional_str(item.get("summary")),
        "content": _optional_str(item.get("content")),
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
        page, size = normalize_pagination(page, size)
        return self._repository.list_articles(
            q=normalize_optional_str(q),
            source=normalize_optional_str(source),
            date_from=normalize_date_filter(date_from, field_name="from"),
            date_to=normalize_date_filter(date_to, field_name="to"),
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
