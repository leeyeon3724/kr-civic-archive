# Guardrails Policy

이 문서는 운영/릴리스 가드 체크 항목을 실행 문맥별로 통합한 단일 기준입니다.
명령 상세 원문은 `docs/QUALITY_GATES.md`를 기준으로 하며, 본 문서는 실행 순서와 적용 문맥을 정의합니다.

## Local/CI Baseline

항상 아래 순서로 실행합니다.

```bash
python -m ruff check app tests scripts
python scripts/check_mypy.py
python -m pytest -q -m "not e2e and not integration" --cov=app --cov-report=term --cov-fail-under=85
python scripts/check_docs_routes.py
python scripts/check_schema_policy.py
python scripts/check_version_consistency.py
python scripts/check_slo_policy.py
python scripts/check_quality_metrics.py
```

## PR Context

- baseline 게이트 전부 통과
- 커밋 메시지 정책 게이트:

```bash
python scripts/check_commit_messages.py --rev-range origin/main..HEAD --mode fail
```

- 정책/운영 변경 PR은 `docs/API.md`, `docs/ENV.md`, `docs/ARCHITECTURE.md`, `docs/OPERATIONS.md` 정합성을 함께 업데이트

## Release Context

- PR context 통과 후 아래 게이트를 추가 실행

```bash
python scripts/check_runtime_health.py --base-url http://localhost:8000
EXPECTED_VERSION=<X.Y.Z> python scripts/check_version_consistency.py
BENCH_PROFILE=staging BENCH_FAIL_THRESHOLD_MS=250 BENCH_FAIL_P95_THRESHOLD_MS=400 python scripts/benchmark_queries.py
```

## Incident/Degraded Context

- 장애 모드 확인 시 readiness degraded를 명시적으로 허용

```bash
python scripts/check_runtime_health.py --base-url http://localhost:8000 --allow-ready-degraded
```

- incident 종료 후 `docs/OPERATIONS.md` 템플릿 기준으로 회고를 기록하고 필요 시 `docs/CHANGELOG.md` `Unreleased`에 반영
