from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Mapping, cast

from app.ports.dto import SegmentRecordDTO, SegmentUpsertDTO
from app.ports.repositories import SegmentsRepositoryPort
from app.ports.services import SegmentsServicePort
from app.repositories.segments_repository import SegmentsRepository
from app.repositories.session_provider import ConnectionProvider, ensure_connection_provider
from app.utils import (
    bad_request,
    coerce_meeting_no_int,
    combine_meeting_no,
    normalize_date_filter,
    normalize_optional_str,
    normalize_pagination,
    parse_date,
)

LEGACY_EMPTY_STRING_FIELDS: tuple[str, ...] = (
    "committee",
    "session",
    "meeting_no_combined",
    "content",
    "summary",
    "subject",
    "party",
    "constituency",
    "department",
)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _as_date_input(value: object) -> str | datetime | date | None:
    if value is None or isinstance(value, (str, datetime, date)):
        return value
    raise bad_request(f"meeting_date format error (YYYY-MM-DD): {value}")


def _canonical_json_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_canonical_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _canonical_json_value(value[key]) for key in sorted(value, key=str)}
    return value


def _build_segment_dedupe_hash(item: Mapping[str, object]) -> str:
    canonical_payload = _canonical_json_value(
        {
            "council": item.get("council"),
            "committee": item.get("committee"),
            "session": item.get("session"),
            "meeting_no": item.get("meeting_no"),
            "meeting_no_combined": item.get("meeting_no_combined"),
            "meeting_date": item.get("meeting_date"),
            "content": item.get("content"),
            "summary": item.get("summary"),
            "subject": item.get("subject"),
            "tag": item.get("tag"),
            "importance": item.get("importance"),
            "moderator": item.get("moderator"),
            "questioner": item.get("questioner"),
            "answerer": item.get("answerer"),
            "party": item.get("party"),
            "constituency": item.get("constituency"),
            "department": item.get("department"),
        }
    )
    encoded = json.dumps(canonical_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _build_legacy_segment_dedupe_hash(item: Mapping[str, object]) -> str:
    legacy_payload: dict[str, object] = dict(item)
    for field in LEGACY_EMPTY_STRING_FIELDS:
        if legacy_payload.get(field) is None:
            legacy_payload[field] = ""
    return _build_segment_dedupe_hash(legacy_payload)


def _normalize_segment(item: dict[str, object]) -> SegmentUpsertDTO:
    if not isinstance(item, dict):
        raise bad_request("Each item must be a JSON object.")

    council = item.get("council")
    if not isinstance(council, str) or not council.strip():
        raise bad_request("Missing required field: council")

    session = _optional_str(item.get("session"))
    meeting_no_raw = item.get("meeting_no")
    meeting_no_int = coerce_meeting_no_int(meeting_no_raw)

    meeting_date = parse_date(_as_date_input(item.get("meeting_date")))

    normalized: SegmentUpsertDTO = {
        "council": council.strip(),
        "committee": _optional_str(item.get("committee")),
        "session": session,
        "meeting_no": meeting_no_int,
        "meeting_no_combined": combine_meeting_no(session, meeting_no_raw, meeting_no_int),
        "meeting_date": meeting_date.date() if meeting_date else None,
        "content": _optional_str(item.get("content")),
        "summary": _optional_str(item.get("summary")),
        "subject": _optional_str(item.get("subject")),
        "tag": item.get("tag"),
        "importance": parse_importance_value(item.get("importance"), required=False),
        "moderator": item.get("moderator"),
        "questioner": item.get("questioner"),
        "answerer": item.get("answerer"),
        "party": _optional_str(item.get("party")),
        "constituency": _optional_str(item.get("constituency")),
        "department": _optional_str(item.get("department")),
        "dedupe_hash": "",
        "dedupe_hash_legacy": None,
    }
    normalized["dedupe_hash"] = _build_segment_dedupe_hash(normalized)
    normalized["dedupe_hash_legacy"] = _build_legacy_segment_dedupe_hash(normalized)
    return normalized


def parse_importance_value(raw: object, *, required: bool) -> int | None:
    if raw is None:
        if required:
            raise bad_request("importance must be one of 1, 2, 3.")
        return None

    if isinstance(raw, bool):
        raise bad_request("importance must be an integer (1, 2, 3).")
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            raise bad_request("importance must be an integer (1, 2, 3).")
        try:
            value = int(stripped)
        except ValueError:
            raise bad_request("importance must be an integer (1, 2, 3).")
    else:
        raise bad_request("importance must be an integer (1, 2, 3).")

    if value not in (1, 2, 3):
        raise bad_request("importance must be one of 1, 2, 3.")

    return value


def parse_importance_query(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise bad_request("importance must be an integer.")
    if value not in (1, 2, 3):
        raise bad_request("importance must be one of 1, 2, 3.")
    return value


class SegmentsService:
    def __init__(self, *, repository: SegmentsRepositoryPort) -> None:
        self._repository = repository

    @staticmethod
    def normalize_segment(item: dict[str, object]) -> SegmentUpsertDTO:
        return _normalize_segment(item)

    def insert_segments(self, items: list[SegmentUpsertDTO]) -> int:
        return self._repository.insert_segments(items)

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
        page, size = normalize_pagination(page, size)
        return self._repository.list_segments(
            q=normalize_optional_str(q),
            council=normalize_optional_str(council),
            committee=normalize_optional_str(committee),
            session=normalize_optional_str(session),
            meeting_no=normalize_optional_str(meeting_no),
            importance=importance,
            party=normalize_optional_str(party),
            constituency=normalize_optional_str(constituency),
            department=normalize_optional_str(department),
            date_from=normalize_date_filter(date_from, field_name="from"),
            date_to=normalize_date_filter(date_to, field_name="to"),
            page=page,
            size=size,
        )

    def get_segment(self, item_id: int) -> SegmentRecordDTO | None:
        return self._repository.get_segment(item_id)

    def delete_segment(self, item_id: int) -> bool:
        return self._repository.delete_segment(item_id)


def build_segments_service(
    *,
    connection_provider: ConnectionProvider,
    repository: SegmentsRepositoryPort | None = None,
) -> SegmentsServicePort:
    selected_repository = repository or SegmentsRepository(connection_provider=connection_provider)
    return cast(SegmentsServicePort, cast(object, SegmentsService(repository=selected_repository)))


def normalize_segment(item: dict[str, object]) -> SegmentUpsertDTO:
    return _normalize_segment(item)


def insert_segments(
    items: list[SegmentUpsertDTO],
    *,
    service: SegmentsServicePort | None = None,
    connection_provider: ConnectionProvider | None = None,
) -> int:
    active_service = service or build_segments_service(connection_provider=ensure_connection_provider(connection_provider))
    return active_service.insert_segments(items)


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
    service: SegmentsServicePort | None = None,
    connection_provider: ConnectionProvider | None = None,
) -> tuple[list[SegmentRecordDTO], int]:
    active_service = service or build_segments_service(connection_provider=ensure_connection_provider(connection_provider))
    return active_service.list_segments(
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
    )


def get_segment(
    item_id: int,
    *,
    service: SegmentsServicePort | None = None,
    connection_provider: ConnectionProvider | None = None,
) -> SegmentRecordDTO | None:
    active_service = service or build_segments_service(connection_provider=ensure_connection_provider(connection_provider))
    return active_service.get_segment(item_id)


def delete_segment(
    item_id: int,
    *,
    service: SegmentsServicePort | None = None,
    connection_provider: ConnectionProvider | None = None,
) -> bool:
    active_service = service or build_segments_service(connection_provider=ensure_connection_provider(connection_provider))
    return active_service.delete_segment(item_id)
