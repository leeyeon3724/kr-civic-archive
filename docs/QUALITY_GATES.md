# Quality Gates

이 문서는 로컬/CI에서 공통으로 사용하는 검증 명령을 한 곳에 모아둔 기준 문서입니다.

## 기본 게이트 (권장 순서)

```bash
python -m ruff check app tests scripts
python scripts/check_mypy.py
python -m pytest -q -m "not e2e and not integration" --cov=app --cov-report=term --cov-fail-under=85
python scripts/check_docs_routes.py
python scripts/check_schema_policy.py
python scripts/check_version_consistency.py
python scripts/check_slo_policy.py
```

## 브랜치/PR 게이트

```bash
python scripts/check_commit_messages.py --rev-range origin/main..HEAD --mode fail
```

## 변경 유형별 추가 게이트

스키마 변경:

```bash
python -m alembic upgrade head
python -m alembic downgrade -1
```

운영/배포 검증:

```bash
python scripts/check_runtime_health.py --base-url http://localhost:8000
```

성능 민감 변경:

```bash
BENCH_PROFILE=staging BENCH_FAIL_THRESHOLD_MS=250 BENCH_FAIL_P95_THRESHOLD_MS=400 python scripts/benchmark_queries.py
```

통합 테스트:

```bash
RUN_INTEGRATION=1 python -m pytest -m integration
```

E2E 테스트:

```bash
python -m pytest -q -m e2e --base-url http://localhost:8000
E2E_REQUIRE_TARGET=1 python -m pytest -q -m e2e --base-url http://localhost:8000
```

보안/공급망 점검:

```bash
cyclonedx-py requirements --output-reproducible --of JSON -o sbom-runtime.cdx.json requirements.txt
pip-audit -r requirements.txt -r requirements-dev.txt
bandit -q -r app scripts -ll
```
