from __future__ import annotations

from typing import Any, cast as typing_cast

from sqlalchemy import bindparam, column, func, select, table, text

from app.ports.dto import SegmentRecordDTO, SegmentUpsertDTO
from app.repositories.common import (
    add_not_none_equals_filter,
    add_split_search_filter,
    add_truthy_equals_filter,
    execute_filtered_paginated_query,
    dedupe_rows_by_key,
    to_json_recordset,
)
from app.repositories.session_provider import ConnectionProvider, open_connection_scope

COUNCIL_SPEECH_SEGMENTS = table(
    "council_speech_segments",
    column("id"),
    column("council"),
    column("committee"),
    column("session"),
    column("meeting_no"),
    column("meeting_no_combined"),
    column("meeting_date"),
    column("content"),
    column("summary"),
    column("subject"),
    column("tag"),
    column("importance"),
    column("moderator"),
    column("questioner"),
    column("answerer"),
    column("party"),
    column("constituency"),
    column("department"),
    column("dedupe_hash"),
    column("created_at"),
    column("updated_at"),
)


def insert_segments(
    items: list[SegmentUpsertDTO],
    *,
    connection_provider: ConnectionProvider,
) -> int:
    if not items:
        return 0

    payload_rows = [
        {
            "council": segment.get("council"),
            "committee": segment.get("committee"),
            "session": segment.get("session"),
            "meeting_no": segment.get("meeting_no"),
            "meeting_no_combined": segment.get("meeting_no_combined"),
            "meeting_date": segment.get("meeting_date"),
            "content": segment.get("content"),
            "summary": segment.get("summary"),
            "subject": segment.get("subject"),
            "tag": segment.get("tag"),
            "importance": segment.get("importance"),
            "moderator": segment.get("moderator"),
            "questioner": segment.get("questioner"),
            "answerer": segment.get("answerer"),
            "party": segment.get("party"),
            "constituency": segment.get("constituency"),
            "department": segment.get("department"),
            "dedupe_hash": segment.get("dedupe_hash"),
            "dedupe_hash_legacy": segment.get("dedupe_hash_legacy"),
        }
        for segment in items
    ]
    if any(segment.get("dedupe_hash") is not None for segment in payload_rows):
        payload_rows = dedupe_rows_by_key(payload_rows, key="dedupe_hash")

    sql = text(
        """
        WITH payload AS (
            SELECT *
            FROM jsonb_to_recordset(CAST(:items AS jsonb))
              AS p(
                council text,
                committee text,
                session text,
                meeting_no integer,
                meeting_no_combined text,
                meeting_date date,
                content text,
                summary text,
                subject text,
                tag jsonb,
                importance integer,
                moderator jsonb,
                questioner jsonb,
                answerer jsonb,
                party text,
                constituency text,
                department text,
                dedupe_hash text,
                dedupe_hash_legacy text
              )
        ),
        inserted_rows AS (
            INSERT INTO council_speech_segments
              (council, committee, "session", meeting_no, meeting_no_combined, meeting_date,
               content, summary, subject, tag, importance, moderator, questioner, answerer,
               party, constituency, department, dedupe_hash)
            SELECT
              council,
              committee,
              session,
              meeting_no,
              meeting_no_combined,
              meeting_date,
              content,
              summary,
              subject,
              tag,
              importance,
              moderator,
              questioner,
              answerer,
              party,
              constituency,
              department,
              dedupe_hash
            FROM payload p
            WHERE NOT EXISTS (
              SELECT 1
              FROM council_speech_segments s
              WHERE s.dedupe_hash = p.dedupe_hash
                 OR (
                   p.dedupe_hash_legacy IS NOT NULL
                   AND s.dedupe_hash = p.dedupe_hash_legacy
                 )
            )
            ON CONFLICT (dedupe_hash) DO NOTHING
            RETURNING 1
        )
        SELECT COUNT(*) AS inserted
        FROM inserted_rows
        """
    )

    with open_connection_scope(connection_provider) as conn:
        row = conn.execute(sql, {"items": to_json_recordset(payload_rows)}).mappings().first() or {}

    return int(row.get("inserted") or 0)


def list_segments(
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
    connection_provider: ConnectionProvider,
) -> tuple[list[SegmentRecordDTO], int]:
    conditions: list[Any] = []
    params: dict[str, Any] = {}

    add_split_search_filter(
        query=q,
        columns=[
            COUNCIL_SPEECH_SEGMENTS.c.council,
            COUNCIL_SPEECH_SEGMENTS.c.committee,
            COUNCIL_SPEECH_SEGMENTS.c["session"],
            COUNCIL_SPEECH_SEGMENTS.c.content,
            COUNCIL_SPEECH_SEGMENTS.c.summary,
            COUNCIL_SPEECH_SEGMENTS.c.subject,
            COUNCIL_SPEECH_SEGMENTS.c.party,
            COUNCIL_SPEECH_SEGMENTS.c.constituency,
            COUNCIL_SPEECH_SEGMENTS.c.department,
            COUNCIL_SPEECH_SEGMENTS.c.tag,
            COUNCIL_SPEECH_SEGMENTS.c.questioner,
            COUNCIL_SPEECH_SEGMENTS.c.answerer,
        ],
        conditions=conditions,
        params=params,
    )

    for param_name, column_expr, value in (
        ("council", COUNCIL_SPEECH_SEGMENTS.c.council, council),
        ("committee", COUNCIL_SPEECH_SEGMENTS.c.committee, committee),
        ("session", COUNCIL_SPEECH_SEGMENTS.c["session"], session),
        ("meeting_no", COUNCIL_SPEECH_SEGMENTS.c.meeting_no_combined, meeting_no),
        ("party", COUNCIL_SPEECH_SEGMENTS.c.party, party),
        ("constituency", COUNCIL_SPEECH_SEGMENTS.c.constituency, constituency),
        ("department", COUNCIL_SPEECH_SEGMENTS.c.department, department),
    ):
        add_truthy_equals_filter(
            value=value,
            param_name=param_name,
            column_expr=column_expr,
            conditions=conditions,
            params=params,
        )

    add_not_none_equals_filter(
        value=importance,
        param_name="importance",
        column_expr=COUNCIL_SPEECH_SEGMENTS.c.importance,
        conditions=conditions,
        params=params,
    )

    if date_from:
        conditions.append(COUNCIL_SPEECH_SEGMENTS.c.meeting_date >= bindparam("date_from"))
        params["date_from"] = date_from

    if date_to:
        conditions.append(COUNCIL_SPEECH_SEGMENTS.c.meeting_date <= bindparam("date_to"))
        params["date_to"] = date_to

    list_stmt = (
        select(
            COUNCIL_SPEECH_SEGMENTS.c.id,
            COUNCIL_SPEECH_SEGMENTS.c.council,
            COUNCIL_SPEECH_SEGMENTS.c.committee,
            COUNCIL_SPEECH_SEGMENTS.c["session"],
            COUNCIL_SPEECH_SEGMENTS.c.meeting_no_combined.label("meeting_no"),
            COUNCIL_SPEECH_SEGMENTS.c.meeting_date,
            COUNCIL_SPEECH_SEGMENTS.c.summary,
            COUNCIL_SPEECH_SEGMENTS.c.subject,
            COUNCIL_SPEECH_SEGMENTS.c.tag,
            COUNCIL_SPEECH_SEGMENTS.c.importance,
            COUNCIL_SPEECH_SEGMENTS.c.moderator,
            COUNCIL_SPEECH_SEGMENTS.c.questioner,
            COUNCIL_SPEECH_SEGMENTS.c.answerer,
            COUNCIL_SPEECH_SEGMENTS.c.party,
            COUNCIL_SPEECH_SEGMENTS.c.constituency,
            COUNCIL_SPEECH_SEGMENTS.c.department,
        )
        .order_by(
            COUNCIL_SPEECH_SEGMENTS.c.meeting_date.desc().nullslast(),
            COUNCIL_SPEECH_SEGMENTS.c.id.desc(),
        )
        .limit(bindparam("limit"))
        .offset(bindparam("offset"))
    )

    count_stmt = select(func.count().label("total")).select_from(COUNCIL_SPEECH_SEGMENTS)

    rows, total = execute_filtered_paginated_query(
        list_stmt=list_stmt,
        count_stmt=count_stmt,
        conditions=conditions,
        params=params,
        page=page,
        size=size,
        connection_provider=connection_provider,
    )
    return typing_cast(list[SegmentRecordDTO], rows), total


def get_segment(
    item_id: int,
    *,
    connection_provider: ConnectionProvider,
) -> SegmentRecordDTO | None:
    sql = text(
        """
        SELECT id, council, committee, "session",
               meeting_no_combined AS meeting_no, meeting_date,
               content, summary, subject, tag, importance,
               moderator, questioner, answerer,
               party, constituency, department,
               created_at, updated_at
        FROM council_speech_segments
        WHERE id=:id
        """
    )

    with open_connection_scope(connection_provider) as conn:
        row = conn.execute(sql, {"id": item_id}).mappings().first()

    return typing_cast(SegmentRecordDTO, dict(row)) if row else None


def delete_segment(
    item_id: int,
    *,
    connection_provider: ConnectionProvider,
) -> bool:
    with open_connection_scope(connection_provider) as conn:
        result = conn.execute(text("DELETE FROM council_speech_segments WHERE id=:id"), {"id": item_id})

    return result.rowcount > 0


class SegmentsRepository:
    def __init__(self, *, connection_provider: ConnectionProvider) -> None:
        self._connection_provider = connection_provider

    def insert_segments(self, items: list[SegmentUpsertDTO]) -> int:
        return insert_segments(items, connection_provider=self._connection_provider)

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
        return list_segments(
            q=q,
            council=council,
            committee=committee,
            session=session,
            meeting_no=meeting_no,
            importance=importance,
            party=party,
            constituency=constituency,
            department=department,
            date_from=date_from,
            date_to=date_to,
            page=page,
            size=size,
            connection_provider=self._connection_provider,
        )

    def get_segment(self, item_id: int) -> SegmentRecordDTO | None:
        return get_segment(item_id, connection_provider=self._connection_provider)

    def delete_segment(self, item_id: int) -> bool:
        return delete_segment(item_id, connection_provider=self._connection_provider)
