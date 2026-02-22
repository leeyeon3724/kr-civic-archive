from __future__ import annotations

from sqlalchemy import text

from app.repositories.common import execute_paginated_query
from conftest import StubResult


def test_execute_paginated_query_skips_count_when_first_page_is_not_full(make_connection_provider):
    def handler(_statement, _params):
        return StubResult(rows=[{"id": 1}, {"id": 2}])

    connection_provider, engine = make_connection_provider(handler)
    rows, total = execute_paginated_query(
        list_stmt=text("SELECT id FROM t ORDER BY id DESC LIMIT :limit OFFSET :offset"),
        count_stmt=text("SELECT count(*) AS total FROM t"),
        params={},
        page=1,
        size=20,
        connection_provider=connection_provider,
    )

    assert len(rows) == 2
    assert total == 2
    assert len(engine.connection.calls) == 1


def test_execute_paginated_query_keeps_count_when_first_page_is_full(make_connection_provider):
    call_state = {"calls": 0}

    def handler(_statement, _params):
        if call_state["calls"] == 0:
            call_state["calls"] += 1
            return StubResult(rows=[{"id": 1}, {"id": 2}])
        return StubResult(scalar_value=5)

    connection_provider, engine = make_connection_provider(handler)
    rows, total = execute_paginated_query(
        list_stmt=text("SELECT id FROM t ORDER BY id DESC LIMIT :limit OFFSET :offset"),
        count_stmt=text("SELECT count(*) AS total FROM t"),
        params={},
        page=1,
        size=2,
        connection_provider=connection_provider,
    )

    assert len(rows) == 2
    assert total == 5
    assert len(engine.connection.calls) == 2


def test_execute_paginated_query_keeps_count_for_non_first_page(make_connection_provider):
    call_state = {"calls": 0}

    def handler(_statement, _params):
        if call_state["calls"] == 0:
            call_state["calls"] += 1
            return StubResult(rows=[{"id": 3}])
        return StubResult(scalar_value=21)

    connection_provider, engine = make_connection_provider(handler)
    rows, total = execute_paginated_query(
        list_stmt=text("SELECT id FROM t ORDER BY id DESC LIMIT :limit OFFSET :offset"),
        count_stmt=text("SELECT count(*) AS total FROM t"),
        params={},
        page=2,
        size=20,
        connection_provider=connection_provider,
    )

    assert len(rows) == 1
    assert total == 21
    assert len(engine.connection.calls) == 2


def test_execute_paginated_query_uses_window_total_when_row_total_key_present(make_connection_provider):
    def handler(_statement, _params):
        return StubResult(rows=[{"id": 3, "__total_count": 21}])

    connection_provider, engine = make_connection_provider(handler)
    rows, total = execute_paginated_query(
        list_stmt=text("SELECT id FROM t ORDER BY id DESC LIMIT :limit OFFSET :offset"),
        count_stmt=text("SELECT count(*) AS total FROM t"),
        params={},
        page=2,
        size=20,
        connection_provider=connection_provider,
        row_total_key="__total_count",
    )

    assert rows == [{"id": 3}]
    assert total == 21
    assert len(engine.connection.calls) == 1


def test_execute_paginated_query_falls_back_to_count_when_window_total_missing(make_connection_provider):
    call_state = {"calls": 0}

    def handler(_statement, _params):
        if call_state["calls"] == 0:
            call_state["calls"] += 1
            return StubResult(rows=[])
        return StubResult(scalar_value=21)

    connection_provider, engine = make_connection_provider(handler)
    rows, total = execute_paginated_query(
        list_stmt=text("SELECT id FROM t ORDER BY id DESC LIMIT :limit OFFSET :offset"),
        count_stmt=text("SELECT count(*) AS total FROM t"),
        params={},
        page=2,
        size=20,
        connection_provider=connection_provider,
        row_total_key="__total_count",
    )

    assert rows == []
    assert total == 21
    assert len(engine.connection.calls) == 2
