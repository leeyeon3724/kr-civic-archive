from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.common import (
    ensure_item_object,
    normalize_list_window,
    normalize_optional_filters,
    require_stripped_text,
)


def test_ensure_item_object_rejects_non_dict():
    assert ensure_item_object({"id": 1}) == {"id": 1}

    with pytest.raises(HTTPException) as exc_info:
        ensure_item_object(["not", "an", "object"])
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "BAD_REQUEST"


def test_require_stripped_text_validates_required_field():
    payload = {"title": "  budget  "}
    assert require_stripped_text(payload, "title", error_message="Missing required field: title") == "budget"

    with pytest.raises(HTTPException) as exc_info:
        require_stripped_text({"title": "   "}, "title", error_message="Missing required field: title")
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["message"] == "Missing required field: title"


def test_normalize_optional_filters_trims_values():
    normalized = normalize_optional_filters({"q": "  budget  ", "source": "   ", "council": None})
    assert normalized == {"q": "budget", "source": None, "council": None}


def test_normalize_list_window_applies_pagination_and_date_validation():
    page, size, date_from, date_to = normalize_list_window(
        page=2,
        size=50,
        date_from=" 2026-02-01 ",
        date_to="2026-02-28",
    )
    assert page == 2
    assert size == 50
    assert date_from == "2026-02-01"
    assert date_to == "2026-02-28"

    with pytest.raises(HTTPException) as exc_info:
        normalize_list_window(page=1, size=20, date_from="2026/02/01", date_to=None)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "BAD_REQUEST"
