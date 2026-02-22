# SLO 정책

이 문서는 `civic-archive-api`의 서비스 수준 지표(SLI), 목표(SLO), 오류 예산(error budget) 정책, 알림 정책을 정의합니다.

## 범위

- 서비스: `civic-archive-api`
- 환경: 프로덕션 (`APP_ENV=production`)
- 요청 범위: `/api/*` 엔드포인트
- 관측 원천: Prometheus 메트릭 (`civic_archive_http_requests_total`, `civic_archive_http_request_duration_seconds`)

## SLI 정의

### 가용성 SLI

- 정의: `/api/*` 요청 중 성공 요청 비율
- 성공 기준: HTTP 상태 코드 `< 500`
- 계산식:
  - `availability = 1 - (5xx_requests / total_requests)`

### 지연시간 SLI

- 정의: `/api/*` 요청 p95 지연시간
- 원천: `civic_archive_http_request_duration_seconds` 히스토그램
- 계산식:
  - `histogram_quantile(0.95, sum(rate(civic_archive_http_request_duration_seconds_bucket{path=~"/api/.*"}[5m])) by (le))`

## SLO 목표

- 가용성 SLO (30일 롤링): `>= 99.9%`
- 지연시간 SLO (5분 윈도우 p95): `<= 250ms`
- 준비성(Readiness) SLO:
  - `/health/live` = `200`
  - `/health/ready` = `200`

## 오류 예산 정책

- 가용성 SLO 99.9%의 월간 오류 예산:
  - 30일 기준 약 43분 12초

소진(Burn) 정책:

- 2시간 소진율 > 예산 10%: 온콜 즉시 호출, 비핵심 배포 중단
- 24시간 소진율 > 예산 25%: 기능 롤아웃 전 인시던트 리뷰 필수
- 30일 소진율 > 예산 50%: 비핵심 변경 신뢰성 동결
- 30일 소진율 > 예산 80%: 인시던트/보안/신뢰성 변경만 허용

## 알림 정책

### 페이징 알림 (긴급)

- `5xx error ratio > 5%`가 5분 지속
- `p95 latency > 500ms`가 10분 지속
- `/health/ready != 200`이 3회 연속 발생

### 경고 알림 (주의)

- `5xx error ratio > 1%`가 15분 지속
- `p95 latency > 300ms`가 15분 지속
- 24시간 내 error budget 소진율 > 25%

## 배포 가드레일

프로덕션 배포 전 아래 항목을 실행합니다.

1. `docs/QUALITY_GATES.md`의 품질 게이트 실행
2. DB 마이그레이션 점검:
   - `python -m alembic upgrade head`
3. 배포 전 런타임 점검(대상 환경):
   - `python scripts/check_runtime_health.py --base-url <target-base-url>`
4. 벤치마크 회귀 점검:
   - `BENCH_PROFILE=staging BENCH_FAIL_THRESHOLD_MS=250 BENCH_FAIL_P95_THRESHOLD_MS=400 python scripts/benchmark_queries.py`

## 인시던트 연계

- 인시던트 대응 체크리스트 및 롤백 지침: `docs/OPERATIONS.md`
