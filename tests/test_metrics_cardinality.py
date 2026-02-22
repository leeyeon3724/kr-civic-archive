from concurrent.futures import ThreadPoolExecutor
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


def test_route_template_cache_operations_are_thread_safe(monkeypatch):
    observability._ROUTE_TEMPLATE_CACHE.clear()
    monkeypatch.setattr(observability, "ROUTE_TEMPLATE_CACHE_MAX_SIZE", 1)
    errors: list[Exception] = []

    def write_cache(worker: int) -> None:
        for index in range(1000):
            key = ("GET", f"/api/thread-{worker % 3}-{index % 5}")
            try:
                observability._route_template_cache_set(key, key[1])
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

    def read_cache(worker: int) -> None:
        for index in range(1000):
            key = ("GET", f"/api/thread-{worker % 3}-{index % 5}")
            try:
                observability._route_template_cache_get(key)
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = []
        for worker in range(4):
            futures.append(pool.submit(write_cache, worker))
            futures.append(pool.submit(read_cache, worker))
        for future in futures:
            future.result()

    assert errors == []
    assert len(observability._ROUTE_TEMPLATE_CACHE) <= observability.ROUTE_TEMPLATE_CACHE_MAX_SIZE
