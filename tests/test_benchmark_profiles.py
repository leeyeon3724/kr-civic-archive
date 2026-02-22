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


def test_compute_baseline_deltas_calculates_ms_and_percent_changes():
    module = _load_benchmark_module()
    current = {
        "news_list": {"avg_ms": 220.0, "p95_ms": 330.0, "tags": [], "runs": 3},
        "minutes_list": {"avg_ms": 200.0, "p95_ms": 300.0, "tags": [], "runs": 3},
        "segments_list": {"avg_ms": 210.0, "p95_ms": 320.0, "tags": [], "runs": 3},
    }
    baseline = {
        "news_list": {"avg_ms": 200.0, "p95_ms": 300.0, "tags": [], "runs": 3},
        "minutes_list": {"avg_ms": 200.0, "p95_ms": 300.0, "tags": [], "runs": 3},
        "segments_list": {"avg_ms": 240.0, "p95_ms": 360.0, "tags": [], "runs": 3},
    }

    delta = module.compute_baseline_deltas(current_results=current, baseline_results=baseline)

    assert delta["news_list"]["delta_avg_ms"] == 20.0
    assert delta["news_list"]["delta_avg_pct"] == 10.0
    assert delta["news_list"]["delta_p95_ms"] == 30.0
    assert delta["segments_list"]["delta_p95_ms"] == -40.0
    assert delta["segments_list"]["delta_p95_pct"] == -11.11


def test_render_markdown_report_includes_baseline_delta_table():
    module = _load_benchmark_module()
    report = {
        "news_list": {"avg_ms": 210.0, "p95_ms": 320.0, "runs": 3, "tags": []},
        "minutes_list": {"avg_ms": 200.0, "p95_ms": 300.0, "runs": 3, "tags": []},
        "segments_list": {"avg_ms": 220.0, "p95_ms": 340.0, "runs": 3, "tags": []},
        "_meta": {"profile": "staging"},
        "_delta": {
            "news_list": {
                "baseline_p95_ms": 300.0,
                "current_p95_ms": 320.0,
                "delta_p95_ms": 20.0,
                "delta_p95_pct": 6.67,
            }
        },
    }

    markdown = module.render_markdown_report(report)
    assert "## Scenario Summary" in markdown
    assert "## Baseline Delta" in markdown
    assert "| news_list | 300.00 | 320.00 | +20.00 | +6.67% |" in markdown
