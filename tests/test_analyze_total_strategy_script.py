import importlib.util
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "analyze_total_strategy.py"
    spec = importlib.util.spec_from_file_location("analyze_total_strategy", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summarize_timings_returns_expected_shape():
    module = _load_script_module()
    stats = module.summarize_timings([10.0, 20.0, 30.0, 40.0])
    assert set(stats.keys()) == {"avg_ms", "p95_ms", "min_ms", "max_ms"}
    assert stats["avg_ms"] == 25.0
    assert stats["min_ms"] == 10.0
    assert stats["max_ms"] == 40.0


def test_percentile_handles_empty_input():
    module = _load_script_module()
    assert module.percentile([], 0.95) == 0.0


def test_domain_queries_define_required_strategies():
    module = _load_script_module()
    assert set(module.DOMAIN_QUERIES.keys()) == {"news", "minutes", "segments"}
    for queries in module.DOMAIN_QUERIES.values():
        assert set(queries.keys()) == {"list", "count", "window"}
