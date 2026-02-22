from __future__ import annotations

from typing import Any, cast as typing_cast

from sqlalchemy import Date, bindparam, cast, column, func, select, table, text

from app.ports.dto import NewsArticleRecordDTO, NewsArticleUpsertDTO
from app.repositories.common import (
    add_split_search_filter,
    dedupe_rows_by_key,
    execute_filtered_paginated_query,
    to_json_recordset,
)
from app.repositories.session_provider import ConnectionProvider, open_connection_scope

NEWS_ARTICLES = table(
    "news_articles",
    column("id"),
    column("source"),
    column("title"),
    column("url"),
    column("published_at"),
    column("author"),
    column("summary"),
    column("content"),
    column("keywords"),
    column("created_at"),
    column("updated_at"),
)


def upsert_articles(
    articles: list[NewsArticleUpsertDTO],
    *,
    connection_provider: ConnectionProvider,
) -> tuple[int, int]:
    if not articles:
        return 0, 0

    payload_rows = [
        {
            "source": article.get("source"),
            "title": article.get("title"),
            "url": article.get("url"),
            "published_at": article.get("published_at"),
            "author": article.get("author"),
            "summary": article.get("summary"),
            "content": article.get("content"),
            "keywords": article.get("keywords"),
        }
        for article in articles
    ]
    payload_rows = dedupe_rows_by_key(payload_rows, key="url")

    sql = text(
        """
        WITH payload AS (
            SELECT *
            FROM jsonb_to_recordset(CAST(:items AS jsonb))
              AS p(
                source text,
                title text,
                url text,
                published_at timestamptz,
                author text,
                summary text,
                content text,
                keywords jsonb
              )
        ),
        upserted AS (
            INSERT INTO news_articles
              (source, title, url, published_at, author, summary, content, keywords)
            SELECT
              source, title, url, published_at, author, summary, content, keywords
            FROM payload
            ON CONFLICT (url) DO UPDATE SET
              source = EXCLUDED.source,
              title = EXCLUDED.title,
              published_at = EXCLUDED.published_at,
              author = EXCLUDED.author,
              summary = EXCLUDED.summary,
              content = EXCLUDED.content,
              keywords = EXCLUDED.keywords,
              updated_at = CURRENT_TIMESTAMP
            RETURNING (xmax = 0) AS inserted
        )
        SELECT
          COALESCE(SUM(CASE WHEN inserted THEN 1 ELSE 0 END), 0) AS inserted,
          COALESCE(SUM(CASE WHEN NOT inserted THEN 1 ELSE 0 END), 0) AS updated
        FROM upserted
        """
    )

    with open_connection_scope(connection_provider) as conn:
        row = conn.execute(sql, {"items": to_json_recordset(payload_rows)}).mappings().first() or {}

    return int(row.get("inserted") or 0), int(row.get("updated") or 0)


def list_articles(
    *,
    q: str | None,
    source: str | None,
    date_from: str | None,
    date_to: str | None,
    page: int,
    size: int,
    connection_provider: ConnectionProvider,
) -> tuple[list[NewsArticleRecordDTO], int]:
    conditions: list[Any] = []
    params: dict[str, Any] = {}

    add_split_search_filter(
        query=q,
        columns=[
            NEWS_ARTICLES.c.title,
            NEWS_ARTICLES.c.summary,
            NEWS_ARTICLES.c.content,
        ],
        conditions=conditions,
        params=params,
    )

    if source:
        conditions.append(NEWS_ARTICLES.c.source == bindparam("source"))
        params["source"] = source

    if date_from:
        conditions.append(NEWS_ARTICLES.c.published_at >= bindparam("date_from"))
        params["date_from"] = date_from

    if date_to:
        conditions.append(
            NEWS_ARTICLES.c.published_at
            < (cast(bindparam("date_to"), Date) + text("INTERVAL '1 day'"))
        )
        params["date_to"] = date_to

    list_stmt = (
        select(
            NEWS_ARTICLES.c.id,
            NEWS_ARTICLES.c.source,
            NEWS_ARTICLES.c.title,
            NEWS_ARTICLES.c.url,
            NEWS_ARTICLES.c.published_at,
            NEWS_ARTICLES.c.author,
            NEWS_ARTICLES.c.summary,
            NEWS_ARTICLES.c.keywords,
            NEWS_ARTICLES.c.created_at,
            NEWS_ARTICLES.c.updated_at,
        )
        .order_by(
            func.coalesce(NEWS_ARTICLES.c.published_at, NEWS_ARTICLES.c.created_at).desc(),
            NEWS_ARTICLES.c.id.desc(),
        )
        .limit(bindparam("limit"))
        .offset(bindparam("offset"))
    )

    count_stmt = select(func.count().label("total")).select_from(NEWS_ARTICLES)

    rows, total = execute_filtered_paginated_query(
        list_stmt=list_stmt,
        count_stmt=count_stmt,
        conditions=conditions,
        params=params,
        page=page,
        size=size,
        connection_provider=connection_provider,
    )
    return typing_cast(list[NewsArticleRecordDTO], rows), total


def get_article(
    item_id: int,
    *,
    connection_provider: ConnectionProvider,
) -> NewsArticleRecordDTO | None:
    sql = text(
        "SELECT id, source, title, url, published_at, author, summary, content, keywords, created_at, updated_at "
        "FROM news_articles WHERE id=:id"
    )

    with open_connection_scope(connection_provider) as conn:
        row = conn.execute(sql, {"id": item_id}).mappings().first()

    return typing_cast(NewsArticleRecordDTO, dict(row)) if row else None


def delete_article(
    item_id: int,
    *,
    connection_provider: ConnectionProvider,
) -> bool:
    with open_connection_scope(connection_provider) as conn:
        result = conn.execute(text("DELETE FROM news_articles WHERE id=:id"), {"id": item_id})

    return result.rowcount > 0


class NewsRepository:
    def __init__(self, *, connection_provider: ConnectionProvider) -> None:
        self._connection_provider = connection_provider

    def upsert_articles(self, articles: list[NewsArticleUpsertDTO]) -> tuple[int, int]:
        return upsert_articles(articles, connection_provider=self._connection_provider)

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
        return list_articles(
            q=q,
            source=source,
            date_from=date_from,
            date_to=date_to,
            page=page,
            size=size,
            connection_provider=self._connection_provider,
        )

    def get_article(self, item_id: int) -> NewsArticleRecordDTO | None:
        return get_article(item_id, connection_provider=self._connection_provider)

    def delete_article(self, item_id: int) -> bool:
        return delete_article(item_id, connection_provider=self._connection_provider)
