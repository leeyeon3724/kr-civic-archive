from app.repositories.search import build_split_search_condition, build_split_search_params
from sqlalchemy import column


def test_build_split_search_params_keeps_trigram_and_fts_values():
    params = build_split_search_params("budget report")
    assert params["q"] == "%budget report%"
    assert params["q_fts"] == "budget report"


def test_build_split_search_condition_contains_trigram_and_fts_operators():
    expr = build_split_search_condition(columns=[column("title"), column("content")])
    sql = str(expr).lower()
    assert "like lower(:q)" in sql
    assert "to_tsvector" in sql
    assert "websearch_to_tsquery" in sql
