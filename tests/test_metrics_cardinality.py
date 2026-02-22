from unittest.mock import patch

from fastapi.testclient import TestClient
from conftest import oversized_echo_body
from conftest import StubResult, build_test_config

from app import create_app
import app.observability as observability


def _histogram_count(metrics_text: str, *, strategy: str) -> float:
    prefix = f'civic_archive_metric_path_label_resolution_seconds_count{{strategy="{strategy}"}} '
    for line in metrics_text.splitlines():
        if line.startswith(prefix):
            return float(line[len(prefix) :])
    return 0.0


def test_metrics_normalizes_unknown_http_method_to_other(client):
    resp = client.request("BREW", "/health")
    assert resp.status_code == 405

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    body = metrics.text
    assert 'method="OTHER",path="/health",status_code="405"' in body
    assert 'method="BREW"' not in body


def test_metrics_records_route_template_cache_strategy_for_pre_route_failures(make_engine):
    observability._ROUTE_TEMPLATE_CACHE.clear()

    with patch("app.database.create_engine", return_value=make_engine(lambda *_: StubResult())):
        app = create_app(build_test_config(MAX_REQUEST_BODY_BYTES=64))

    with TestClient(app) as client:
        before_metrics = client.get("/metrics")
        assert before_metrics.status_code == 200
        before_router = _histogram_count(before_metrics.text, strategy="router")
        before_cache = _histogram_count(before_metrics.text, strategy="cache")

        for _ in range(2):
            oversized = client.post(
                "/api/echo",
                content=oversized_echo_body(),
                headers={"Content-Type": "application/json"},
            )
            assert oversized.status_code == 413

        after_metrics = client.get("/metrics")
        assert after_metrics.status_code == 200
        assert _histogram_count(after_metrics.text, strategy="router") >= before_router + 1
        assert _histogram_count(after_metrics.text, strategy="cache") >= before_cache + 1
