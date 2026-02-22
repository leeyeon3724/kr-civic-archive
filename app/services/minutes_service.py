from __future__ import annotations

from typing import cast

from app.ports.dto import MinutesRecordDTO, MinutesUpsertDTO
from app.ports.repositories import MinutesRepositoryPort
from app.ports.services import MinutesServicePort
from app.repositories.minutes_repository import MinutesRepository
from app.repositories.session_provider import ConnectionProvider, ensure_connection_provider
from app.services.common import (
    ensure_item_object,
    normalize_list_window,
    normalize_optional_filters,
    require_stripped_text,
)
from app.utils import (
    coerce_meeting_no_int,
    combine_meeting_no,
    ensure_temporal_input,
    normalize_optional_str,
    parse_date,
)


def _normalize_minutes(item: dict[str, object]) -> MinutesUpsertDTO:
    item = ensure_item_object(item)
    council = require_stripped_text(item, "council", error_message="Missing required fields: council, url")
    url = require_stripped_text(item, "url", error_message="Missing required fields: council, url")

    session = normalize_optional_str(item.get("session"))
    meeting_no_raw = item.get("meeting_no")
    meeting_no_int = coerce_meeting_no_int(meeting_no_raw)

    meeting_date = parse_date(
        ensure_temporal_input(
            item.get("meeting_date"),
            error_message="meeting_date format error (YYYY-MM-DD): {value}",
        )
    )

    return {
        "council": council,
        "committee": normalize_optional_str(item.get("committee")),
        "session": session,
        "meeting_no": meeting_no_int,
        "meeting_no_combined": combine_meeting_no(session, meeting_no_raw, meeting_no_int),
        "url": url,
        "meeting_date": meeting_date.date() if meeting_date else None,
        "content": normalize_optional_str(item.get("content")),
        "tag": item.get("tag"),
        "attendee": item.get("attendee"),
        "agenda": item.get("agenda"),
    }


class MinutesService:
    def __init__(self, *, repository: MinutesRepositoryPort) -> None:
        self._repository = repository

    @staticmethod
    def normalize_minutes(item: dict[str, object]) -> MinutesUpsertDTO:
        return _normalize_minutes(item)

    def upsert_minutes(self, items: list[MinutesUpsertDTO]) -> tuple[int, int]:
        return self._repository.upsert_minutes(items)

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
        page, size, date_from, date_to = normalize_list_window(
            page=page,
            size=size,
            date_from=date_from,
            date_to=date_to,
        )
        normalized_filters = normalize_optional_filters(
            {
                "q": q,
                "council": council,
                "committee": committee,
                "session": session,
                "meeting_no": meeting_no,
            }
        )
        return self._repository.list_minutes(
            q=normalized_filters["q"],
            council=normalized_filters["council"],
            committee=normalized_filters["committee"],
            session=normalized_filters["session"],
            meeting_no=normalized_filters["meeting_no"],
            date_from=date_from,
            date_to=date_to,
            page=page,
            size=size,
        )

    def get_minutes(self, item_id: int) -> MinutesRecordDTO | None:
        return self._repository.get_minutes(item_id)

    def delete_minutes(self, item_id: int) -> bool:
        return self._repository.delete_minutes(item_id)


def build_minutes_service(
    *,
    connection_provider: ConnectionProvider,
    repository: MinutesRepositoryPort | None = None,
) -> MinutesServicePort:
    selected_repository = repository or MinutesRepository(connection_provider=connection_provider)
    return cast(MinutesServicePort, cast(object, MinutesService(repository=selected_repository)))


def normalize_minutes(item: dict[str, object]) -> MinutesUpsertDTO:
    return _normalize_minutes(item)


def upsert_minutes(
    items: list[MinutesUpsertDTO],
    *,
    service: MinutesServicePort | None = None,
    connection_provider: ConnectionProvider | None = None,
) -> tuple[int, int]:
    active_service = service or build_minutes_service(connection_provider=ensure_connection_provider(connection_provider))
    return active_service.upsert_minutes(items)


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
    service: MinutesServicePort | None = None,
    connection_provider: ConnectionProvider | None = None,
) -> tuple[list[MinutesRecordDTO], int]:
    active_service = service or build_minutes_service(connection_provider=ensure_connection_provider(connection_provider))
    return active_service.list_minutes(
        q=q,
        council=council,
        committee=committee,
        session=session,
        meeting_no=meeting_no,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=size,
    )


def get_minutes(
    item_id: int,
    *,
    service: MinutesServicePort | None = None,
    connection_provider: ConnectionProvider | None = None,
) -> MinutesRecordDTO | None:
    active_service = service or build_minutes_service(connection_provider=ensure_connection_provider(connection_provider))
    return active_service.get_minutes(item_id)


def delete_minutes(
    item_id: int,
    *,
    service: MinutesServicePort | None = None,
    connection_provider: ConnectionProvider | None = None,
) -> bool:
    active_service = service or build_minutes_service(connection_provider=ensure_connection_provider(connection_provider))
    return active_service.delete_minutes(item_id)
