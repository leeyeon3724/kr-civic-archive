from sqlalchemy import column

from app.repositories.common import add_split_search_filter


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
