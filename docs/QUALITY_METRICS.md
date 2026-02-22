# 품질 지표

이 문서는 `civic-archive-api`의 핵심 품질 지표(성능, 안정성, 신뢰성, 유지보수성)와 릴리스 게이트 기준을 정의합니다.

## 범위

- 대상 API: `/api/news`, `/api/minutes`, `/api/segments`
- 대상 환경: `development`, `staging`, `production`
- 측정 원천:
  - 벤치마크: `scripts/benchmark_queries.py`
  - 런타임 헬스: `scripts/check_runtime_health.py`
  - 코드 품질: `python -m pytest ... --cov`, `scripts/check_mypy.py`, `scripts/check_docs_routes.py`

## 성능 지표

| 지표 | 목표 | 측정 원천 | 게이트 |
|------|------|-----------|--------|
| 목록 API p95 지연시간 | `docs/PERFORMANCE.md` 프로파일 기준 충족 | `scripts/benchmark_queries.py` | 성능 민감 변경 PR 필수 |
| 목록 API 평균 지연시간 | profile + `BENCH_FAIL_THRESHOLD_MS` 기준 충족 | `scripts/benchmark_queries.py` | 성능 민감 변경 PR 필수 |
| 목록 API p95 상한 | profile + `BENCH_FAIL_P95_THRESHOLD_MS` 기준 충족 | `scripts/benchmark_queries.py` | 성능 민감 변경 PR 필수 |
| ingest 경로 p95 지연시간 | ingest 경로 p95 지연이 운영 기준선 대비 급증하지 않음 | API logs, `docs/OPERATIONS.md` | 운영 모니터링 |
| 배치 처리량(throughput) | ingest 배치 처리량(건/분) 기준선 대비 급락 없음 | API logs, 운영 대시보드 | 운영 모니터링 |
| 목록 쿼리 수 패턴 | 목록 조회 요청당 DB query count 패턴 고정(주요 경로 N+1 회귀 금지) | benchmark/profile review | 성능 리뷰 필수 |

## 안정성 지표

| 지표 | 목표 | 측정 원천 | 게이트 |
|------|------|-----------|--------|
| 검증 오류 비율 (4xx incl. 400/422) | 분기 기준선 대비 4xx 급증(예: +30% 이상) 시 원인 분석 및 payload/스키마 회귀 차단 | `/metrics`, API logs | 운영 모니터링 |
| 서버 오류 비율 (5xx) | 지속적 5xx 증가 없음 | `/metrics`, `docs/SLO.md` | 배포 판단 지표 |
| rate_limit_backend fallback 동작 | Redis 장애 시 `RATE_LIMIT_FAIL_OPEN` 정책대로 fallback 동작 | `/health/ready`, `scripts/check_runtime_health.py` | 장애 모드 검증 |
| readiness 강등 발생 | 장애 모드 외 지속 발생 금지 | `/health/ready`, `scripts/check_runtime_health.py` | 배포 전 체크 |
| readiness MTTR | readiness degraded 상태의 치유 시간(MTTR) 15분 이내 복구 목표 | incident log, `docs/OPERATIONS.md` | 운영 사후 검토 |

## 신뢰성 지표

| 지표 | 목표 | 측정 원천 | 게이트 |
|------|------|-----------|--------|
| health live 성공율 SLA | `/health/live` 성공율 SLA `>= 99.95%` | `scripts/check_runtime_health.py`, `docs/SLO.md` | 배포 전 필수 |
| health ready 성공율 SLA | 정상 모드 `/health/ready` 성공율 SLA `>= 99.9%`, 장애 모드 `503(degraded)` 명시적 관리 | `scripts/check_runtime_health.py`, `docs/SLO.md` | 배포 전 필수 |
| 요청 추적 완결성 | 오류 응답에 `X-Request-Id` + `request_id` 유지, 장애 분석 시 요청 추적 완결성 보장 | 테스트/로그 | 보안/예외 회귀 테스트 |

## 유지보수성 지표

| 지표 | 목표 | 측정 원천 | 게이트 |
|------|------|-----------|--------|
| 테스트 커버리지(coverage) | unit/contract 기준 `>= 85%` | `pytest --cov` | 기본 게이트 필수 |
| 타입 검사 상태 | `mypy` 오류 0 | `scripts/check_mypy.py` | 기본 게이트 필수 |
| 문서-라우트 정합성 | API/ENV/BACKLOG/보안 정책 정합성 유지 | `scripts/check_docs_routes.py` | 기본 게이트 필수 |
| 스키마 정책 안전성 | 런타임 수동 DDL 패턴 0 | `scripts/check_schema_policy.py` | 기본 게이트 필수 |
| 정책 회귀(policy regression) 복구 시간 | 정책 스크립트 실패 감지 후 1 파이프라인 내 복구(회귀 탐지 시간 최소화) | 정책 스크립트 CI 이력 | PR/릴리스 회고 |

## 검토 주기

- PR 단위: 변경 영향 범위에 맞는 품질 지표 변화 확인
- 릴리스 단위: `docs/PERFORMANCE.md`, `docs/SLO.md`, 본 문서 기준으로 게이트 재검토
- 월 단위: 임계값 조정 필요 여부 점검(실측 데이터 기반)

## 릴리스 게이트

- 기본 릴리스 게이트:
  - `python -m ruff check app tests scripts`
  - `python scripts/check_mypy.py`
  - `python -m pytest -q -m "not e2e and not integration" --cov=app --cov-report=term --cov-fail-under=85`
  - `python scripts/check_docs_routes.py`
  - `python scripts/check_schema_policy.py`
  - `python scripts/check_version_consistency.py`
  - `python scripts/check_slo_policy.py`
  - `python scripts/check_quality_metrics.py`
- 성능 민감 변경은 benchmark 게이트를 추가로 적용합니다.
