from __future__ import annotations

from typing import Any

from sqlalchemy import Text, bindparam, cast, func, literal, or_


def _coalesce_text(column_expr: Any) -> Any:
    return func.coalesce(cast(column_expr, Text), "")


def build_search_document(*, columns: list[Any]) -> Any:
    if not columns:
        return literal("")

    document = _coalesce_text(columns[0])
    for column_expr in columns[1:]:
        document = document + literal(" ") + _coalesce_text(column_expr)
    return document


def build_split_search_condition(*, columns: list[Any]) -> Any:
    search_document = build_search_document(columns=columns)
    trigram_match = search_document.ilike(bindparam("q"))
    fts_match = func.to_tsvector("simple", search_document).op("@@")(
        func.websearch_to_tsquery("simple", bindparam("q_fts"))
    )
    return or_(trigram_match, fts_match)


def build_split_search_params(query: str) -> dict[str, str]:
    normalized = (query or "").strip()
    return {
        "q": f"%{normalized}%",
        "q_fts": normalized,
    }
