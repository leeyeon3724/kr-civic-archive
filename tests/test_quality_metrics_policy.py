import importlib.util
from pathlib import Path


def _load_quality_metrics_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_quality_metrics.py"
    spec = importlib.util.spec_from_file_location("check_quality_metrics", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_quality_metrics_content_accepts_minimal_valid_doc():
    module = _load_quality_metrics_module()
    text = """
## 범위
## 성능 지표
p95
ingest
throughput
query count
## 안정성 지표
4xx
5xx
mttr
rate_limit_backend
fallback
## 신뢰성 지표
sla
/health/live
/health/ready
request_id
## 유지보수성 지표
policy regression
coverage
mypy
check_docs_routes.py
## 검토 주기
## 릴리스 게이트
check_quality_metrics.py
"""
    assert module.validate_quality_metrics_content(text) == []


def test_validate_quality_metrics_content_rejects_missing_heading():
    module = _load_quality_metrics_module()
    errors = module.validate_quality_metrics_content("## Scope")
    assert any("## 성능 지표" in error for error in errors)


def test_validate_quality_metrics_content_rejects_missing_pattern():
    module = _load_quality_metrics_module()
    text = """
## 범위
## 성능 지표
## 안정성 지표
## 신뢰성 지표
## 유지보수성 지표
## 검토 주기
## 릴리스 게이트
"""
    errors = module.validate_quality_metrics_content(text)
    assert any("p95" in error for error in errors)
