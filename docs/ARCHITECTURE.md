# 아키텍처

## 기술 스택

- Python 3.12
- FastAPI
- PostgreSQL 16 (SQLAlchemy 2.0 + psycopg)
- pydantic-settings
- Alembic
- prometheus-client
- Redis (선택: 분산 rate limit)
- Docker Compose
- HAProxy (compose gateway)
- pytest

## 프로젝트 구조

```text
app/
├── __init__.py          # create_app() 조합/오케스트레이션 엔트리포인트
├── main.py              # ASGI 엔트리포인트(app 인스턴스 export)
├── version.py           # 앱 버전 단일 소스(APP_VERSION)
├── config.py            # 환경변수 -> database_url
├── database.py          # init_db() 전용 (런타임 DDL 없음)
├── errors.py            # 표준 에러 payload/HTTPException 헬퍼
├── logging_config.py    # JSON 구조화 로깅 설정
├── observability.py     # request-id, 요청 로깅, Prometheus 메트릭
├── security.py          # 보안 호환 facade (기존 import/patch 포인트 유지)
├── security_dependencies.py # API key/JWT FastAPI dependency 빌더
├── security_jwt.py      # JWT claim 검증/인가 보조 로직
├── security_proxy.py    # trusted proxy/XFF 기반 client key 해석
├── security_rate_limit.py # rate limiter 구현/백엔드 헬스체크
├── parsing.py           # 날짜/시간 파싱 공통 정책
├── bootstrap/           # 앱 부트스트랩 경계(검증/미들웨어/시스템 라우트/예외 핸들러)
│   ├── contracts.py
│   ├── validation.py
│   ├── middleware.py
│   ├── routes.py
│   ├── system_routes.py
│   └── exception_handlers.py
├── schemas.py           # Pydantic 요청/응답 모델
├── utils.py             # 파서/페이로드 검증 공통 함수
├── ports/               # 서비스/리포지토리 포트 인터페이스 (Protocol)
│   ├── dto.py           # 계층 경계용 TypedDict DTO
│   ├── repositories.py
│   └── services.py
├── services/            # 입력 정규화/검증 레이어
│   ├── providers.py     # FastAPI Depends용 서비스 provider
│   ├── news_service.py
│   ├── minutes_service.py
│   └── segments_service.py
├── repositories/        # SQL 실행/조회 레이어 (PostgreSQL 쿼리)
│   ├── session_provider.py # DB 연결 scope provider 계약 (필수 provider 검증/오픈)
│   ├── news_repository.py
│   ├── minutes_repository.py
│   └── segments_repository.py
└── routes/
    ├── __init__.py      # APIRouter 등록
    ├── news.py
    ├── minutes.py
    └── segments.py
main.py                  # uvicorn 실행 진입점
alembic.ini
migrations/
└── versions/
    ├── 35f43b134803_initial_schema.py
    ├── 0df9d6f13c5a_add_segments_dedupe_hash.py
    ├── 9c4f6e1a2b7d_make_news_published_at_timestamptz.py
    └── b7d1c2a4e8f9_add_search_strategy_indexes.py
scripts/
├── bootstrap_db.py      # alembic upgrade head 실행
├── benchmark_queries.py # 대표 조회 쿼리 성능 회귀 체크
├── check_commit_messages.py # 커밋 메시지 정책 검사 (Conventional Commits + scope)
├── check_docs_routes.py # API.md 라우트 계약 + README 링크 검사
├── check_mypy.py        # mypy 타입체크 래퍼 (blocking 기본)
├── check_schema_policy.py # 런타임 수동 DDL 금지 정책 검사
├── check_slo_policy.py  # SLO 정책 문서 기준선 검사
├── check_quality_metrics.py # 품질 지표 정책 문서 기준선 검사
├── check_runtime_health.py # 배포 전 liveness/readiness 가드 검사
├── check_version_consistency.py # APP_VERSION <-> app/__init__.py <-> CHANGELOG 정합성 검사
Dockerfile
docker-compose.yml
docker/
└── haproxy/
    └── haproxy.cfg      # gateway -> api 다중 인스턴스 라우팅
tests/
├── test_integration_postgres.py # PostgreSQL 컨테이너 기반 통합 테스트
```

## 계층 구조

- route: HTTP 요청/응답 처리 (`Depends`로 서비스 주입)
- service: 입력 정규화/비즈니스 검증 (생성자/팩토리 기반 DI)
- repository: SQL/DB 접근 (`connection_provider` 주입 가능)

흐름: `route -> service -> repository`

## 데이터 모델

| 테이블 | 용도 | 중복 처리 | 핵심 필드 |
|--------|------|-----------|-----------|
| `news_articles` | 뉴스/기사 | `url` UNIQUE + upsert | title, url, published_at(TIMESTAMPTZ, UTC), content, keywords(JSONB) |
| `council_minutes` | 의회 회의록 | `url` UNIQUE + upsert | council, url, meeting_date, content, tag/attendee/agenda(JSONB) |
| `council_speech_segments` | 발언 단락 | `dedupe_hash` UNIQUE + idempotent insert | council, meeting_date, content, importance, questioner/answerer(JSONB) |

## 앱 초기화 흐름

```text
create_app()
  -> Config() 로드
  -> validate_startup_config()             # 환경/보안/운영 가드 검증
  -> register_core_middleware()            # CORS/TrustedHost + request_size_guard
  -> configure_logging()                # JSON 로그 포맷
  -> init_db(database_url + pool/timeout runtime tuning)
  -> app.state.db_engine / app.state.connection_provider 설정
  -> API 보호 의존성(api-key/jwt/rate-limit) 구성
  -> register_observability()           # X-Request-Id + metrics + request logging
  -> register_domain_routes(...)        # APIRouter 등록
  -> register_system_routes(...)        # /health, /api/echo 등 시스템 라우트 등록
  -> register_exception_handlers(...)   # 표준 에러 스키마 핸들러 등록
```

ASGI 엔트리포인트: `app.main:app`

## 마이그레이션 정책

- 표준 스키마 변경은 Alembic revision으로 관리
- 마이그레이션은 SQLAlchemy/Alembic 객체(`op.create_table`, `op.create_index`) 기반으로 관리
- 앱 런타임 수동 DDL(`CREATE/ALTER/DROP TABLE`) 금지
- `BOOTSTRAP_TABLES_ON_STARTUP=0` 고정(1 설정 시 앱 시작 실패)
- 배포/CI 파이프라인에서 `alembic upgrade head` 실행을 필수화

## 주요 설계 결정

- PostgreSQL upsert: `ON CONFLICT ... DO UPDATE`
- 배치 ingest 최적화: `jsonb_to_recordset` 기반 단일 SQL 실행(뉴스/회의록 upsert, 세그먼트 insert)
- 검색: trigram(`ILIKE` + `pg_trgm`) + FTS(`to_tsvector/websearch_to_tsquery`) 분리 전략
- 검색 인덱스: 주요 조회 테이블별 GIN trigram index + GIN FTS index + 필터/정렬 복합 btree index
- 목록 total: `COUNT(*) OVER()` 우선 + 빈 페이지(`rows == 0`) 시 `COUNT(*)` fallback
- 요청/응답 검증: FastAPI + Pydantic 모델 기반으로 OpenAPI 자동 문서화
- 에러 표준화: `code/message/error/request_id/details` 단일 포맷
- 관측성: request-id 미들웨어, 구조화 로그, `/metrics` 메트릭 (라우트 미매칭은 `/_unmatched`, 알 수 없는 HTTP method는 `OTHER` 라벨로 고정)
- 보안 기본선: API key 선택적 강제(`REQUIRE_API_KEY`), JWT 인증/인가(`REQUIRE_JWT` + scope/role), IP rate-limit(`RATE_LIMIT_PER_MINUTE`)
- Compose 배포 경계: 단일 `docker-compose.yml` + `--env-file(.env.dev/.env.prod)` + `gateway` 경유 공개 포트로 `api` 서비스 수평 확장(`--scale api=N`) 지원
- 분산 rate-limit: `RATE_LIMIT_BACKEND=redis`, `REDIS_URL`로 멀티 인스턴스 환경 지원
- Redis limiter 안정화: 장애 시 쿨다운(`RATE_LIMIT_REDIS_FAILURE_COOLDOWN_SECONDS`) + fallback(`RATE_LIMIT_FAIL_OPEN`) 지원
- 프록시 신뢰 경계: `TRUSTED_PROXY_CIDRS`에 매치되는 원격 IP에서만 `X-Forwarded-For`를 신뢰
- 운영 strict 모드: `SECURITY_STRICT_MODE=1` 또는 `APP_ENV=production`에서 인증/호스트/CORS/rate-limit 가드 강제
- `DEBUG`: 앱 설정 플래그이며, 개발 서버 리로드는 `uvicorn --reload` 실행 옵션으로 제어
- DB 런타임 튜닝: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS`, `DB_CONNECT_TIMEOUT_SECONDS`, `DB_STATEMENT_TIMEOUT_MS`
- ingest 안전 가드: `INGEST_MAX_BATCH_ITEMS`, `MAX_REQUEST_BODY_BYTES` 기반으로 oversized 요청을 `413`으로 차단
- DB DI 최종화: 앱 상태(`app.state.connection_provider`)에서 repository까지 명시적 주입, 전역 엔진 상태 의존 제거
- 서비스 DI: `app/services/providers.py`에서 request 단위 `get_*_service` provider를 통해 route 계층에 주입
- 포트 분리: `app/ports/services.py`, `app/ports/repositories.py`에 Protocol 인터페이스를 모아 계층 결합도 축소
- 타입체크 범위: `mypy.ini` + `scripts/check_mypy.py` (bootstrap/routes/services/ports/repositories/observability 범위 blocking)
- 성능 회귀 체크: `scripts/benchmark_queries.py` + avg/p95 threshold 검사
- 성능 임계값 프로파일: `docs/PERFORMANCE.md` + `scripts/benchmark_queries.py --profile <dev|staging|prod>`
- 품질 지표 가드: `docs/QUALITY_METRICS.md` + `scripts/check_quality_metrics.py`
- 문서-코드 정합성: `scripts/check_docs_routes.py` + CI
- 커밋 메시지 정책: `scripts/check_commit_messages.py`
- 버전 정합성: `scripts/check_version_consistency.py` + CI
- 공급망 보안: `docs/QUALITY_GATES.md`의 CycloneDX SBOM + `pip-audit` + `bandit` 기준
- SLO 운영 가드: `docs/SLO.md`, `docs/OPERATIONS.md`, `scripts/check_slo_policy.py`, `scripts/check_runtime_health.py`
