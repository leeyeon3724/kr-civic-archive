from __future__ import annotations

from typing import Protocol

from app.ports.dto import (
    MinutesRecordDTO,
    MinutesUpsertDTO,
    NewsArticleRecordDTO,
    NewsArticleUpsertDTO,
    SegmentRecordDTO,
    SegmentUpsertDTO,
)


class NewsRepositoryPort(Protocol):
    def upsert_articles(self, articles: list[NewsArticleUpsertDTO]) -> tuple[int, int]:
        ...

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
        ...

    def get_article(self, item_id: int) -> NewsArticleRecordDTO | None:
        ...

    def delete_article(self, item_id: int) -> bool:
        ...


class MinutesRepositoryPort(Protocol):
    def upsert_minutes(self, items: list[MinutesUpsertDTO]) -> tuple[int, int]:
        ...

    def list_minutes(
        self,
        *,
        q: str | None,
        council: str | None,
        committee: str | None,
        session: str | None,
        meeting_no: str | None,
        date_from: str | None,
        date_to: str | None,
        page: int,
        size: int,
    ) -> tuple[list[MinutesRecordDTO], int]:
        ...

    def get_minutes(self, item_id: int) -> MinutesRecordDTO | None:
        ...

    def delete_minutes(self, item_id: int) -> bool:
        ...


class SegmentsRepositoryPort(Protocol):
    def insert_segments(self, items: list[SegmentUpsertDTO]) -> int:
        ...

    def list_segments(
        self,
        *,
        q: str | None,
        council: str | None,
        committee: str | None,
        session: str | None,
        meeting_no: str | None,
        importance: int | None,
        party: str | None,
        constituency: str | None,
        department: str | None,
        date_from: str | None,
        date_to: str | None,
        page: int,
        size: int,
    ) -> tuple[list[SegmentRecordDTO], int]:
        ...

    def get_segment(self, item_id: int) -> SegmentRecordDTO | None:
        ...

    def delete_segment(self, item_id: int) -> bool:
        ...
