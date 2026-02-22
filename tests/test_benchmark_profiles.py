import importlib.util
from pathlib import Path


def _load_benchmark_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_queries.py"
    spec = importlib.util.spec_from_file_location("benchmark_queries", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_get_profile_thresholds_returns_expected_mapping():
    module = _load_benchmark_module()
    thresholds = module.get_profile_thresholds("staging")
    assert thresholds is not None
    assert set(thresholds.keys()) == {"news_list", "minutes_list", "segments_list"}
    assert thresholds["news_list"]["avg_ms"] == 250.0
    assert thresholds["segments_list"]["p95_ms"] == 400.0


def test_evaluate_thresholds_flags_profile_and_global_violations():
    module = _load_benchmark_module()
    results = {
        "news_list": {"avg_ms": 300.0, "p95_ms": 420.0, "tags": [], "runs": 3},
        "minutes_list": {"avg_ms": 210.0, "p95_ms": 310.0, "tags": [], "runs": 3},
        "segments_list": {"avg_ms": 260.0, "p95_ms": 390.0, "tags": [], "runs": 3},
    }

    failures = module.evaluate_thresholds(
        results,
        profile="staging",
        avg_threshold=230.0,
        p95_threshold=350.0,
    )
    assert any("news_list: avg_ms" in failure and "profile[staging]" in failure for failure in failures)
    assert any("news_list: p95_ms" in failure and "profile[staging]" in failure for failure in failures)
    assert any("segments_list: avg_ms" in failure and "global limit 230.00" in failure for failure in failures)
    assert any("minutes_list: p95_ms" in failure and "global limit 350.00" not in failure for failure in failures) is False


def test_evaluate_thresholds_handles_unknown_profile():
    module = _load_benchmark_module()
    results = {
        "news_list": {"avg_ms": 100.0, "p95_ms": 120.0, "tags": [], "runs": 3},
        "minutes_list": {"avg_ms": 100.0, "p95_ms": 120.0, "tags": [], "runs": 3},
        "segments_list": {"avg_ms": 100.0, "p95_ms": 120.0, "tags": [], "runs": 3},
    }
    failures = module.evaluate_thresholds(
        results,
        profile="unknown",
        avg_threshold=None,
        p95_threshold=None,
    )
    assert failures == ["Unknown benchmark profile: unknown"]
