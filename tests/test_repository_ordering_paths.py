from __future__ import annotations

from app.repositories import minutes_repository, news_repository, segments_repository
from conftest import StubResult


def _make_list_query_handler():
    call_state = {"calls": 0}

    def handler(_statement, _params):
        if call_state["calls"] == 0:
            call_state["calls"] += 1
            return StubResult(rows=[])
        return StubResult(scalar_value=0)

    return handler


def test_news_list_query_uses_index_friendly_order_path(make_connection_provider):
    connection_provider, engine = make_connection_provider(_make_list_query_handler())

    rows, total = news_repository.list_articles(
        q=None,
        source=None,
        date_from=None,
        date_to=None,
        page=1,
        size=20,
        connection_provider=connection_provider,
    )

    assert rows == []
    assert total == 0
    sql = engine.connection.calls[0]["statement"].lower()
    assert "coalesce(" not in sql
    assert "published_at desc nulls last" in sql
    assert "count(*) over ()" in sql


def test_minutes_list_query_uses_index_friendly_order_path(make_connection_provider):
    connection_provider, engine = make_connection_provider(_make_list_query_handler())

    rows, total = minutes_repository.list_minutes(
        q=None,
        council=None,
        committee=None,
        session=None,
        meeting_no=None,
        date_from=None,
        date_to=None,
        page=1,
        size=20,
        connection_provider=connection_provider,
    )

    assert rows == []
    assert total == 0
    sql = engine.connection.calls[0]["statement"].lower()
    assert "coalesce(" not in sql
    assert "meeting_date desc nulls last" in sql
    assert "count(*) over ()" in sql


def test_segments_list_query_uses_index_friendly_order_path(make_connection_provider):
    connection_provider, engine = make_connection_provider(_make_list_query_handler())

    rows, total = segments_repository.list_segments(
        q=None,
        council=None,
        committee=None,
        session=None,
        meeting_no=None,
        importance=None,
        party=None,
        constituency=None,
        department=None,
        date_from=None,
        date_to=None,
        page=1,
        size=20,
        connection_provider=connection_provider,
    )

    assert rows == []
    assert total == 0
    sql = engine.connection.calls[0]["statement"].lower()
    assert "coalesce(" not in sql
    assert "meeting_date desc nulls last" in sql
    assert "count(*) over ()" in sql
