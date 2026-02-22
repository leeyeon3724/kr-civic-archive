from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.minutes_service import MinutesService
from app.services.news_service import NewsService
from app.services.segments_service import SegmentsService


class DummyNewsRepository:
    def __init__(self) -> None:
        self.last_params: dict | None = None

    def upsert_articles(self, _items):
        return 0, 0

    def list_articles(self, **kwargs):
        self.last_params = kwargs
        return [], 0

    def get_article(self, _item_id):
        return None

    def delete_article(self, _item_id):
        return False


class DummyMinutesRepository:
    def __init__(self) -> None:
        self.last_params: dict | None = None

    def upsert_minutes(self, _items):
        return 0, 0

    def list_minutes(self, **kwargs):
        self.last_params = kwargs
        return [], 0

    def get_minutes(self, _item_id):
        return None

    def delete_minutes(self, _item_id):
        return False


class DummySegmentsRepository:
    def __init__(self) -> None:
        self.last_params: dict | None = None

    def insert_segments(self, _items):
        return 0

    def list_segments(self, **kwargs):
        self.last_params = kwargs
        return [], 0

    def get_segment(self, _item_id):
        return None

    def delete_segment(self, _item_id):
        return False


def test_news_list_normalizes_query_filters_and_dates():
    repository = DummyNewsRepository()
    service = NewsService(repository=repository)

    service.list_articles(
        q="  budget  ",
        source="   ",
        date_from=" 2026-02-01 ",
        date_to="2026-02-28",
        page=1,
        size=20,
    )

    assert repository.last_params is not None
    assert repository.last_params["q"] == "budget"
    assert repository.last_params["source"] is None
    assert repository.last_params["date_from"] == "2026-02-01"
    assert repository.last_params["date_to"] == "2026-02-28"


def test_news_list_rejects_invalid_date_filter():
    repository = DummyNewsRepository()
    service = NewsService(repository=repository)

    with pytest.raises(HTTPException) as exc_info:
        service.list_articles(
            q=None,
            source=None,
            date_from="2026/02/01",
            date_to=None,
            page=1,
            size=20,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "BAD_REQUEST"
    assert "from format error" in exc_info.value.detail["message"]


def test_minutes_list_normalizes_filters():
    repository = DummyMinutesRepository()
    service = MinutesService(repository=repository)

    service.list_minutes(
        q="  traffic  ",
        council=" seoul ",
        committee=" ",
        session=" 301 ",
        meeting_no=" 301 4차 ",
        date_from="2026-02-01",
        date_to=" 2026-02-28 ",
        page=1,
        size=50,
    )

    assert repository.last_params is not None
    assert repository.last_params["q"] == "traffic"
    assert repository.last_params["council"] == "seoul"
    assert repository.last_params["committee"] is None
    assert repository.last_params["session"] == "301"
    assert repository.last_params["meeting_no"] == "301 4차"
    assert repository.last_params["date_to"] == "2026-02-28"


def test_segments_list_normalizes_filters():
    repository = DummySegmentsRepository()
    service = SegmentsService(repository=repository)

    service.list_segments(
        q=" budget ",
        council=" seoul ",
        committee=None,
        session=" 301 ",
        meeting_no=" ",
        importance=2,
        party=" alpha ",
        constituency=" ",
        department=" finance ",
        date_from="2026-02-01",
        date_to="2026-02-28",
        page=2,
        size=100,
    )

    assert repository.last_params is not None
    assert repository.last_params["q"] == "budget"
    assert repository.last_params["council"] == "seoul"
    assert repository.last_params["meeting_no"] is None
    assert repository.last_params["party"] == "alpha"
    assert repository.last_params["constituency"] is None
    assert repository.last_params["department"] == "finance"


@pytest.mark.parametrize(("page", "size"), [(0, 20), (1, 0), (1, 201)])
def test_list_rejects_invalid_pagination(page: int, size: int):
    repository = DummyNewsRepository()
    service = NewsService(repository=repository)

    with pytest.raises(HTTPException) as exc_info:
        service.list_articles(
            q=None,
            source=None,
            date_from=None,
            date_to=None,
            page=page,
            size=size,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "BAD_REQUEST"
