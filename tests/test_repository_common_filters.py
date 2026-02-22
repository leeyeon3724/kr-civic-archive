from sqlalchemy import column

from app.repositories.common import (
    add_date_from_filter,
    add_date_to_filter_inclusive,
    add_date_to_filter_next_day_exclusive,
    add_split_search_filter,
    add_truthy_equals_filter,
)


def test_add_split_search_filter_ignores_none_and_blank_query():
    conditions = []
    params = {}
    columns = [column("title"), column("content")]

    add_split_search_filter(query=None, columns=columns, conditions=conditions, params=params)
    add_split_search_filter(query="   ", columns=columns, conditions=conditions, params=params)

    assert conditions == []
    assert params == {}


def test_add_split_search_filter_appends_condition_and_params():
    conditions = []
    params = {}
    columns = [column("title"), column("content")]

    add_split_search_filter(query=" budget report ", columns=columns, conditions=conditions, params=params)

    assert len(conditions) == 1
    assert params["q"] == "%budget report%"
    assert params["q_fts"] == "budget report"


def test_add_truthy_equals_filter_trims_string_value():
    conditions = []
    params = {}

    add_truthy_equals_filter(
        value="  education  ",
        param_name="committee",
        column_expr=column("committee"),
        conditions=conditions,
        params=params,
    )

    assert len(conditions) == 1
    assert params["committee"] == "education"


def test_add_truthy_equals_filter_ignores_blank_string_value():
    conditions = []
    params = {}

    add_truthy_equals_filter(
        value="   ",
        param_name="committee",
        column_expr=column("committee"),
        conditions=conditions,
        params=params,
    )

    assert conditions == []
    assert params == {}


def test_add_date_filters_handle_trim_and_blank_values():
    conditions = []
    params = {}

    add_date_from_filter(
        value=" 2026-02-01 ",
        param_name="date_from",
        column_expr=column("meeting_date"),
        conditions=conditions,
        params=params,
    )
    add_date_to_filter_inclusive(
        value="2026-02-28",
        param_name="date_to",
        column_expr=column("meeting_date"),
        conditions=conditions,
        params=params,
    )
    add_date_to_filter_next_day_exclusive(
        value="2026-02-28",
        param_name="published_to",
        column_expr=column("published_at"),
        conditions=conditions,
        params=params,
    )

    assert len(conditions) == 3
    assert params["date_from"] == "2026-02-01"
    assert params["date_to"] == "2026-02-28"
    assert params["published_to"] == "2026-02-28"
    assert "INTERVAL '1 day'" in str(conditions[2])

    blank_conditions = []
    blank_params = {}
    add_date_from_filter(
        value="   ",
        param_name="date_from",
        column_expr=column("meeting_date"),
        conditions=blank_conditions,
        params=blank_params,
    )
    add_date_to_filter_inclusive(
        value=None,
        param_name="date_to",
        column_expr=column("meeting_date"),
        conditions=blank_conditions,
        params=blank_params,
    )

    assert blank_conditions == []
    assert blank_params == {}
