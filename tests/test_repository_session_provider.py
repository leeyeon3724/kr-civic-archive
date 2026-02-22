import pytest
from conftest import StubResult

from app.repositories import news_repository
from app.repositories import session_provider as session_provider_module


def test_open_connection_scope_uses_explicit_provider(make_engine):
    engine = make_engine(lambda _statement, _params: StubResult())

    with session_provider_module.open_connection_scope(engine.begin) as conn:
        conn.execute("SELECT 1")

    assert len(engine.connection.calls) == 1


def test_repository_function_accepts_explicit_connection_provider(make_engine):
    default_engine = make_engine(lambda _statement, _params: StubResult())
    injected_engine = make_engine(
        lambda _statement, params: StubResult(rows=[{"id": 7}])
        if params and params.get("id") == 7
        else StubResult()
    )

    row = news_repository.get_article(7, connection_provider=injected_engine.begin)
    assert row == {"id": 7}
    assert len(default_engine.connection.calls) == 0
    assert len(injected_engine.connection.calls) == 1


def test_ensure_connection_provider_rejects_none():
    with pytest.raises(RuntimeError, match="connection provider is required"):
        session_provider_module.ensure_connection_provider(None)
