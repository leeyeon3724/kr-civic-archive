# Performance Policy

이 문서는 조회 API 성능 가드레일과 벤치마크 임계값 정책을 정의합니다.

## Scope

- 대상 엔드포인트:
  - `GET /api/news`
  - `GET /api/minutes`
  - `GET /api/segments`
- 측정 도구: `scripts/benchmark_queries.py`
- 기본 seed 데이터: 300 rows/scenario
- 기본 반복 횟수: 25 runs/scenario

## Search Query Strategy

- 검색 조건(`q`)은 단일 `ILIKE`에서 분리 전략으로 전환:
  - trigram 경로: `ILIKE` + `pg_trgm` GIN 인덱스
  - FTS 경로: `to_tsvector('simple', ...) @@ websearch_to_tsquery('simple', :q)` + GIN 인덱스
- 테이블별 공통 검색 문서 표현식에 맞춰 아래 인덱스를 운영:
  - `*_search_trgm` (GIN + `gin_trgm_ops`)
  - `*_search_fts` (GIN + `to_tsvector`)
- 필터+정렬 경로 안정화를 위해 `*_filters_date_id`, `*_date_id` 복합 btree 인덱스를 함께 사용

## Index-Friendly Ordering Path

- 목록 정렬은 날짜 컬럼 기준 `DESC NULLS LAST, id DESC`를 기본으로 유지합니다.
  - `news_articles`: `published_at DESC NULLS LAST, id DESC`
  - `council_minutes`: `meeting_date DESC NULLS LAST, id DESC`
  - `council_speech_segments`: `meeting_date DESC NULLS LAST, id DESC`
- `COALESCE(date, created_at)` 기반 정렬은 인덱스 활용을 저해할 수 있으므로 기본 경로에서 사용하지 않습니다.

## Endpoint Latency Budget

| Scenario | Endpoint | Budget Type | Target |
|----------|----------|-------------|--------|
| `news_list` | `/api/news` | p95 latency | `<= 300ms` (prod) |
| `minutes_list` | `/api/minutes` | p95 latency | `<= 320ms` (prod) |
| `segments_list` | `/api/segments` | p95 latency | `<= 350ms` (prod) |

참고:

- prod budget은 릴리스 승인 기준선으로 사용합니다.
- staging/dev는 회귀 조기 감지를 위한 완화 임계값을 사용합니다.

## Threshold Profiles

`scripts/benchmark_queries.py --profile <profile>`로 프로파일 임계값을 적용합니다.

| Profile | news (avg/p95) | minutes (avg/p95) | segments (avg/p95) | 목적 |
|---------|-----------------|-------------------|--------------------|------|
| `dev` | `350/550ms` | `350/550ms` | `450/700ms` | 로컬/기능개발 중 이상 징후 탐지 |
| `staging` | `250/400ms` | `250/400ms` | `250/400ms` | CI/사전 검증 기준 |
| `prod` | `180/300ms` | `200/320ms` | `220/350ms` | 릴리스 승인 기준 |

추가 전역 임계값:

- `BENCH_FAIL_THRESHOLD_MS` (avg 공통 상한)
- `BENCH_FAIL_P95_THRESHOLD_MS` (p95 공통 상한)
- 프로파일 임계값과 함께 사용 시 둘 다 만족해야 통과합니다.

## Benchmark Execution Strategy

기본 실행:

```bash
python scripts/benchmark_queries.py --profile dev
```

CI 유사 실행:

```bash
BENCH_PROFILE=staging BENCH_FAIL_THRESHOLD_MS=250 BENCH_FAIL_P95_THRESHOLD_MS=400 python scripts/benchmark_queries.py
```

리포트 산출(JSON/Markdown + baseline delta):

```bash
python scripts/benchmark_queries.py \
  --profile staging \
  --baseline-json artifacts/bench-baseline.json \
  --output-json artifacts/bench-current.json \
  --output-md artifacts/bench-report.md
```

릴리스 전 점검:

```bash
python scripts/benchmark_queries.py --profile prod --runs 40 --seed-rows 500
```

## Release Note Benchmark Delta

성능 민감 변경 PR/릴리스 노트에는 아래 항목을 기록합니다.

- 기준 커밋 대비 delta(%) 또는 delta(ms)
- 악화 시 원인/완화 계획
- `scripts/benchmark_queries.py --baseline-json ... --output-md ...` 결과 표를 첨부

예시 템플릿:

| Scenario | Baseline p95(ms) | Current p95(ms) | Delta |
|----------|------------------|-----------------|-------|
| `news_list` | 210 | 230 | `+9.5%` |
| `minutes_list` | 240 | 236 | `-1.7%` |
| `segments_list` | 280 | 295 | `+5.4%` |

## Throughput Guardrails Draft

- Batch ingest limit: `INGEST_MAX_BATCH_ITEMS` (default `200`)
- Request size limit: `MAX_REQUEST_BODY_BYTES` (default `1,048,576`)
- Oversize fallback behavior:
  - reject request with `413 PAYLOAD_TOO_LARGE`
  - include `details` with configured limit and observed value
- 운영 체크리스트 연계: `docs/OPERATIONS.md`의 Stabilize/Runtime checks 항목에서 확인

