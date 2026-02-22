from __future__ import annotations

from typing import Any, cast as typing_cast

from sqlalchemy import bindparam, column, func, select, table, text

from app.ports.dto import MinutesRecordDTO, MinutesUpsertDTO
from app.repositories.common import (
    add_truthy_equals_filter,
    dedupe_rows_by_key,
    execute_filtered_paginated_query,
    to_json_recordset,
)
from app.repositories.search import build_split_search_condition, build_split_search_params
from app.repositories.session_provider import ConnectionProvider, open_connection_scope

COUNCIL_MINUTES = table(
    "council_minutes",
    column("id"),
    column("council"),
    column("committee"),
    column("session"),
    column("meeting_no"),
    column("meeting_no_combined"),
    column("url"),
    column("meeting_date"),
    column("content"),
    column("tag"),
    column("attendee"),
    column("agenda"),
    column("created_at"),
    column("updated_at"),
)


def upsert_minutes(
    items: list[MinutesUpsertDTO],
    *,
    connection_provider: ConnectionProvider,
) -> tuple[int, int]:
    if not items:
        return 0, 0

    payload_rows = [
        {
            "council": minute.get("council"),
            "committee": minute.get("committee"),
            "session": minute.get("session"),
            "meeting_no": minute.get("meeting_no"),
            "meeting_no_combined": minute.get("meeting_no_combined"),
            "url": minute.get("url"),
            "meeting_date": minute.get("meeting_date"),
            "content": minute.get("content"),
            "tag": minute.get("tag"),
            "attendee": minute.get("attendee"),
            "agenda": minute.get("agenda"),
        }
        for minute in items
    ]
    payload_rows = dedupe_rows_by_key(payload_rows, key="url")

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
                url text,
                meeting_date date,
                content text,
                tag jsonb,
                attendee jsonb,
                agenda jsonb
              )
        ),
        upserted AS (
            INSERT INTO council_minutes
              (council, committee, "session", meeting_no, meeting_no_combined, url, meeting_date, content, tag, attendee, agenda)
            SELECT
              council,
              committee,
              session,
              meeting_no,
              meeting_no_combined,
              url,
              meeting_date,
              content,
              tag,
              attendee,
              agenda
            FROM payload
            ON CONFLICT (url) DO UPDATE SET
              council = EXCLUDED.council,
              committee = EXCLUDED.committee,
              "session" = EXCLUDED."session",
              meeting_no = EXCLUDED.meeting_no,
              meeting_no_combined = EXCLUDED.meeting_no_combined,
              meeting_date = EXCLUDED.meeting_date,
              content = EXCLUDED.content,
              tag = EXCLUDED.tag,
              attendee = EXCLUDED.attendee,
              agenda = EXCLUDED.agenda,
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


def list_minutes(
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
    connection_provider: ConnectionProvider,
) -> tuple[list[MinutesRecordDTO], int]:
    conditions = []
    params: dict[str, Any] = {}

    normalized_q = (q or "").strip()
    if normalized_q:
        conditions.append(
            build_split_search_condition(
                columns=[
                    COUNCIL_MINUTES.c.council,
                    COUNCIL_MINUTES.c.committee,
                    COUNCIL_MINUTES.c["session"],
                    COUNCIL_MINUTES.c.content,
                    COUNCIL_MINUTES.c.agenda,
                ]
            )
        )
        params.update(build_split_search_params(normalized_q))

    for param_name, column_expr, value in (
        ("council", COUNCIL_MINUTES.c.council, council),
        ("committee", COUNCIL_MINUTES.c.committee, committee),
        ("session", COUNCIL_MINUTES.c["session"], session),
        ("meeting_no", COUNCIL_MINUTES.c.meeting_no_combined, meeting_no),
    ):
        add_truthy_equals_filter(
            value=value,
            param_name=param_name,
            column_expr=column_expr,
            conditions=conditions,
            params=params,
        )

    if date_from:
        conditions.append(COUNCIL_MINUTES.c.meeting_date >= bindparam("date_from"))
        params["date_from"] = date_from

    if date_to:
        conditions.append(COUNCIL_MINUTES.c.meeting_date <= bindparam("date_to"))
        params["date_to"] = date_to

    list_stmt = (
        select(
            COUNCIL_MINUTES.c.id,
            COUNCIL_MINUTES.c.council,
            COUNCIL_MINUTES.c.committee,
            COUNCIL_MINUTES.c["session"],
            COUNCIL_MINUTES.c.meeting_no_combined.label("meeting_no"),
            COUNCIL_MINUTES.c.url,
            COUNCIL_MINUTES.c.meeting_date,
            COUNCIL_MINUTES.c.tag,
            COUNCIL_MINUTES.c.attendee,
            COUNCIL_MINUTES.c.agenda,
            COUNCIL_MINUTES.c.created_at,
            COUNCIL_MINUTES.c.updated_at,
        )
        .order_by(
            func.coalesce(COUNCIL_MINUTES.c.meeting_date, COUNCIL_MINUTES.c.created_at).desc(),
            COUNCIL_MINUTES.c.id.desc(),
        )
        .limit(bindparam("limit"))
        .offset(bindparam("offset"))
    )

    count_stmt = select(func.count().label("total")).select_from(COUNCIL_MINUTES)

    rows, total = execute_filtered_paginated_query(
        list_stmt=list_stmt,
        count_stmt=count_stmt,
        conditions=conditions,
        params=params,
        page=page,
        size=size,
        connection_provider=connection_provider,
    )
    return typing_cast(list[MinutesRecordDTO], rows), total


def get_minutes(
    item_id: int,
    *,
    connection_provider: ConnectionProvider,
) -> MinutesRecordDTO | None:
    sql = text(
        """
        SELECT id, council, committee, "session", meeting_no_combined AS meeting_no,
               url, meeting_date, content, tag, attendee, agenda, created_at, updated_at
        FROM council_minutes
        WHERE id=:id
        """
    )

    with open_connection_scope(connection_provider) as conn:
        row = conn.execute(sql, {"id": item_id}).mappings().first()

    return typing_cast(MinutesRecordDTO, dict(row)) if row else None


def delete_minutes(
    item_id: int,
    *,
    connection_provider: ConnectionProvider,
) -> bool:
    with open_connection_scope(connection_provider) as conn:
        result = conn.execute(text("DELETE FROM council_minutes WHERE id=:id"), {"id": item_id})

    return result.rowcount > 0


class MinutesRepository:
    def __init__(self, *, connection_provider: ConnectionProvider) -> None:
        self._connection_provider = connection_provider

    def upsert_minutes(self, items: list[MinutesUpsertDTO]) -> tuple[int, int]:
        return upsert_minutes(items, connection_provider=self._connection_provider)

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
        return list_minutes(
            q=q,
            council=council,
            committee=committee,
            session=session,
            meeting_no=meeting_no,
            date_from=date_from,
            date_to=date_to,
            page=page,
            size=size,
            connection_provider=self._connection_provider,
        )

    def get_minutes(self, item_id: int) -> MinutesRecordDTO | None:
        return get_minutes(item_id, connection_provider=self._connection_provider)

    def delete_minutes(self, item_id: int) -> bool:
        return delete_minutes(item_id, connection_provider=self._connection_provider)
