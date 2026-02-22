from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.parsing import parse_date_value, parse_datetime_value


class StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorResponse(BaseModel):
    code: str = Field(examples=["NOT_FOUND"])
    message: str = Field(examples=["Not Found"])
    error: str = Field(examples=["Not Found"])
    request_id: Optional[str] = Field(default=None, examples=["c752262e-cf42-4075-917b-95ffcb5ceeeb"])
    details: Any = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "VALIDATION_ERROR",
                "message": "Input should be a valid integer",
                "error": "Input should be a valid integer",
                "request_id": "c752262e-cf42-4075-917b-95ffcb5ceeeb",
                "details": [{"loc": ["query", "page"], "msg": "Input should be a valid integer"}],
            }
        }
    )


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])


class ReadinessCheck(BaseModel):
    ok: bool
    detail: Optional[str] = None


class ReadinessResponse(BaseModel):
    status: str = Field(examples=["ok", "degraded"])
    checks: dict[str, ReadinessCheck]


class EchoResponse(BaseModel):
    you_sent: Any


class UpsertResponse(BaseModel):
    inserted: int
    updated: int


class InsertResponse(BaseModel):
    inserted: int


class DeleteResponse(BaseModel):
    status: str
    id: int


class NewsUpsertItem(StrictRequestModel):
    source: Optional[str] = None
    title: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    published_at: Optional[datetime] = None
    author: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    keywords: Any = None

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "source": "local-news",
                "title": "City budget hearing update",
                "url": "https://example.com/news/100",
                "published_at": "2026-02-17T09:30:00Z",
                "author": "Reporter",
                "summary": "Budget committee summary",
                "content": "Detailed article text",
                "keywords": ["budget", "council"],
            }
        },
    )

    @field_validator("title", "url")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("published_at", mode="before")
    @classmethod
    def _validate_published_at(cls, value: Any) -> Optional[datetime]:
        try:
            return parse_datetime_value(value)
        except ValueError:
            raise ValueError(f"published_at format error: {value}")


NewsUpsertPayload = NewsUpsertItem | list[NewsUpsertItem]


class MinutesUpsertItem(StrictRequestModel):
    council: str = Field(..., min_length=1)
    committee: Optional[str] = None
    session: Optional[str] = None
    meeting_no: Optional[int | str] = None
    url: str = Field(..., min_length=1)
    meeting_date: Optional[date] = None
    content: Optional[str] = None
    tag: Any = None
    attendee: Any = None
    agenda: Any = None

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "council": "seoul",
                "committee": "budget",
                "session": "301",
                "meeting_no": "301 4차",
                "url": "https://example.com/minutes/100",
                "meeting_date": "2026-02-17",
                "content": "minutes text",
                "tag": ["budget"],
                "attendee": {"count": 12},
                "agenda": ["budget approval"],
            }
        },
    )

    @field_validator("council", "url")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("meeting_date", mode="before")
    @classmethod
    def _validate_meeting_date(cls, value: Any) -> Optional[date]:
        try:
            return parse_date_value(value)
        except ValueError as exc:
            raise ValueError("meeting_date must be YYYY-MM-DD") from exc


MinutesUpsertPayload = MinutesUpsertItem | list[MinutesUpsertItem]


class SegmentsInsertItem(StrictRequestModel):
    council: str = Field(..., min_length=1)
    committee: Optional[str] = None
    session: Optional[str] = None
    meeting_no: Optional[int | str] = None
    meeting_date: Optional[date] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    subject: Optional[str] = None
    tag: Any = None
    importance: Optional[int] = Field(default=None, ge=1, le=3)
    moderator: Any = None
    questioner: Any = None
    answerer: Any = None
    party: Optional[str] = None
    constituency: Optional[str] = None
    department: Optional[str] = None

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "council": "seoul",
                "committee": "budget",
                "session": "301",
                "meeting_no": "301 4차",
                "meeting_date": "2026-02-17",
                "content": "segment text",
                "summary": "summary",
                "subject": "budget floor speech",
                "tag": ["budget"],
                "importance": 2,
                "questioner": {"name": "member"},
                "answerer": [{"name": "official"}],
                "party": "party-a",
                "constituency": "district-1",
                "department": "finance",
            }
        },
    )

    @field_validator("council")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("meeting_date", mode="before")
    @classmethod
    def _validate_meeting_date(cls, value: Any) -> Optional[date]:
        try:
            return parse_date_value(value)
        except ValueError as exc:
            raise ValueError("meeting_date must be YYYY-MM-DD") from exc


SegmentsInsertPayload = SegmentsInsertItem | list[SegmentsInsertItem]


class NewsItemBase(BaseModel):
    id: int
    source: Optional[str] = None
    title: str
    url: str
    published_at: Optional[datetime] = None
    author: Optional[str] = None
    summary: Optional[str] = None
    keywords: Any = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NewsItemDetail(NewsItemBase):
    content: Optional[str] = None


class NewsListResponse(BaseModel):
    page: int
    size: int
    total: int
    items: list[NewsItemBase]


class MinutesItemBase(BaseModel):
    id: int
    council: str
    committee: Optional[str] = None
    session: Optional[str] = None
    meeting_no: Optional[str] = None
    url: str
    meeting_date: Optional[date] = None
    tag: Any = None
    attendee: Any = None
    agenda: Any = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MinutesItemDetail(MinutesItemBase):
    content: Optional[str] = None


class MinutesListResponse(BaseModel):
    page: int
    size: int
    total: int
    items: list[MinutesItemBase]


class SegmentsItemBase(BaseModel):
    id: int
    council: str
    committee: Optional[str] = None
    session: Optional[str] = None
    meeting_no: Optional[str] = None
    meeting_date: Optional[date] = None
    summary: Optional[str] = None
    subject: Optional[str] = None
    tag: Any = None
    importance: Optional[int] = None
    moderator: Any = None
    questioner: Any = None
    answerer: Any = None
    party: Optional[str] = None
    constituency: Optional[str] = None
    department: Optional[str] = None


class SegmentsItemDetail(SegmentsItemBase):
    content: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SegmentsListResponse(BaseModel):
    page: int
    size: int
    total: int
    items: list[SegmentsItemBase]
