from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_benchmark_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_queries.py"
    spec = importlib.util.spec_from_file_location("benchmark_queries", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("endpoint", "top_level_keys"),
    [
        ("/api/news?page=1&size=1", {"page", "size", "total", "items"}),
        ("/api/minutes?page=1&size=1", {"page", "size", "total", "items"}),
        ("/api/segments?page=1&size=1", {"page", "size", "total", "items"}),
    ],
)
def test_refactor_checklist_api_list_contract_shape(client, endpoint: str, top_level_keys: set[str]):
    response = client.get(endpoint)
    assert response.status_code == 200
    payload = response.json()
    assert top_level_keys.issubset(payload.keys())


def test_refactor_checklist_metrics_label_contract(client):
    first_metrics = client.get("/metrics")
    assert first_metrics.status_code == 200
    assert "civic_archive_http_requests_total" in first_metrics.text

    missing = client.get("/no-such-route-regression-template")
    assert missing.status_code == 404

    second_metrics = client.get("/metrics")
    assert second_metrics.status_code == 200
    assert 'path="/_unmatched"' in second_metrics.text


def test_refactor_checklist_benchmark_profile_scenarios():
    module = _load_benchmark_module()
    thresholds = module.get_profile_thresholds("staging")
    assert thresholds is not None
    assert set(thresholds.keys()) == {"news_list", "minutes_list", "segments_list"}
