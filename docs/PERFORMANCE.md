# 성능 정책

이 문서는 조회 API 성능 가드레일과 벤치마크 임계값 정책을 정의합니다.

## 범위

- 대상 엔드포인트:
  - `GET /api/news`
  - `GET /api/minutes`
  - `GET /api/segments`
- 측정 도구: `scripts/benchmark_queries.py`
- 기본 seed 데이터: 시나리오당 300행
- 기본 반복 횟수: 시나리오당 25회

## 검색 쿼리 전략

- 검색 조건(`q`)은 단일 `ILIKE`에서 분리 전략으로 전환:
  - trigram 경로: `ILIKE` + `pg_trgm` GIN 인덱스
  - FTS 경로: `to_tsvector('simple', ...) @@ websearch_to_tsquery('simple', :q)` + GIN 인덱스
- 테이블별 공통 검색 문서 표현식에 맞춰 아래 인덱스를 운영:
  - `*_search_trgm` (GIN + `gin_trgm_ops`)
  - `*_search_fts` (GIN + `to_tsvector`)
- 필터+정렬 경로 안정화를 위해 `*_filters_date_id`, `*_date_id` 복합 btree 인덱스를 함께 사용

## 인덱스 친화 정렬 경로

- 목록 정렬은 날짜 컬럼 기준 `DESC NULLS LAST, id DESC`를 기본으로 유지합니다.
  - `news_articles`: `published_at DESC NULLS LAST, id DESC`
  - `council_minutes`: `meeting_date DESC NULLS LAST, id DESC`
  - `council_speech_segments`: `meeting_date DESC NULLS LAST, id DESC`
- `COALESCE(date, created_at)` 기반 정렬은 인덱스 활용을 저해할 수 있으므로 기본 경로에서 사용하지 않습니다.

## 엔드포인트 지연 예산

| 시나리오 | 엔드포인트 | 예산 유형 | 목표 |
|----------|------------|------------|------|
| `news_list` | `/api/news` | p95 latency | `<= 300ms` (prod) |
| `minutes_list` | `/api/minutes` | p95 latency | `<= 320ms` (prod) |
| `segments_list` | `/api/segments` | p95 latency | `<= 350ms` (prod) |

참고:

- prod budget은 릴리스 승인 기준선으로 사용합니다.
- staging/dev는 회귀 조기 감지를 위한 완화 임계값을 사용합니다.

## 임계값 프로파일

`scripts/benchmark_queries.py --profile <profile>`로 프로파일 임계값을 적용합니다.

| 프로파일 | news (avg/p95) | minutes (avg/p95) | segments (avg/p95) | 목적 |
|---------|------------------|-------------------|--------------------|------|
| `dev` | `350/550ms` | `350/550ms` | `450/700ms` | 로컬/기능개발 중 이상 징후 탐지 |
| `staging` | `250/400ms` | `250/400ms` | `250/400ms` | CI/사전 검증 기준 |
| `prod` | `180/300ms` | `200/320ms` | `220/350ms` | 릴리스 승인 기준 |

추가 전역 임계값:

- `BENCH_FAIL_THRESHOLD_MS` (avg 공통 상한)
- `BENCH_FAIL_P95_THRESHOLD_MS` (p95 공통 상한)
- 프로파일 임계값과 함께 사용 시 둘 다 만족해야 통과합니다.

## 벤치마크 실행 전략

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

## total 산출 전략 비교

`LIMIT/OFFSET + COUNT(*)` 분리 전략과 `COUNT(*) OVER()` 단일 쿼리 전략을 동일 조건에서 비교할 때 아래 스크립트를 사용합니다.

현재 런타임 기본 전략:

- 목록 조회 SQL에 `COUNT(*) OVER()`를 포함해 `rows > 0` 구간에서 별도 `COUNT(*)` round-trip을 제거
- 빈 페이지(`rows == 0`)에서는 API 계약(`total` 항상 반환) 유지를 위해 `COUNT(*)` fallback 수행

```bash
python scripts/analyze_total_strategy.py --runs 30 --limit 20 --offset 0 --output-json artifacts/total-strategy.json
```

핵심 해석 포인트:

- `split_strategy_ms.roundtrip`: 완전 분리 전략(legacy) 기준값
- `window_strategy_ms.roundtrip`: `COUNT(*) OVER()` 기반 기준값
- `notes.window_total_absent_when_no_rows=true`: 단일 쿼리 단독으로는 빈 페이지 total 누락 가능성이 있어 fallback 정책을 함께 검증

운영 데이터 분포 기반 검토 시 아래 오프셋을 함께 측정합니다.

- `offset=0` (첫 페이지)
- `offset=200` (중간 페이지)
- `offset=2000` (깊은 페이지)

비교 결과는 `docs/CHANGELOG.md` 또는 성능 검토 문서에 요약합니다.

## 릴리스 노트 벤치마크 델타

성능 민감 변경 PR/릴리스 노트에는 아래 항목을 기록합니다.

- 기준 커밋 대비 delta(%) 또는 delta(ms)
- 악화 시 원인/완화 계획
- `scripts/benchmark_queries.py --baseline-json ... --output-md ...` 결과 표를 첨부

예시 템플릿:

| 시나리오 | 기준선 p95(ms) | 현재 p95(ms) | 델타 |
|----------|-------------------|------------------|------|
| `news_list` | 210 | 230 | `+9.5%` |
| `minutes_list` | 240 | 236 | `-1.7%` |
| `segments_list` | 280 | 295 | `+5.4%` |

## 처리량 가드레일 초안

- 배치 ingest 상한: `INGEST_MAX_BATCH_ITEMS` (기본값 `200`)
- 요청 크기 상한: `MAX_REQUEST_BODY_BYTES` (기본값 `1,048,576`)
- 초과 fallback 동작:
  - 요청을 `413 PAYLOAD_TOO_LARGE`로 거부
  - `details`에 설정 상한과 관측 값을 포함
- 운영 체크리스트 연계: `docs/OPERATIONS.md`의 안정화/런타임 점검 항목에서 확인

