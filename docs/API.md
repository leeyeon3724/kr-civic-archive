# API 레퍼런스

## 엔드포인트 요약

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 서버 가용성 메시지 |
| GET | `/health` | 헬스체크 |
| GET | `/health/live` | liveness 헬스체크 |
| GET | `/health/ready` | readiness 헬스체크 (DB/Rate limiter backend) |
| GET | `/metrics` | Prometheus 메트릭 |
| POST | `/api/echo` | 요청 JSON 반사 |
| POST | `/api/news` | 뉴스 upsert (단건/배치) |
| GET | `/api/news` | 뉴스 목록 |
| GET | `/api/news/{id}` | 뉴스 상세 |
| DELETE | `/api/news/{id}` | 뉴스 삭제 |
| POST | `/api/minutes` | 회의록 upsert (단건/배치) |
| GET | `/api/minutes` | 회의록 목록 |
| GET | `/api/minutes/{id}` | 회의록 상세 |
| DELETE | `/api/minutes/{id}` | 회의록 삭제 |
| POST | `/api/segments` | 발언 단락 insert (단건/배치) |
| GET | `/api/segments` | 발언 단락 목록 |
| GET | `/api/segments/{id}` | 발언 단락 상세 |
| DELETE | `/api/segments/{id}` | 발언 단락 삭제 |

## 공통 규칙

- 목록 API 페이지네이션: `page`(기본 1, 최소 1), `size`(기본 20, 1~200)
- 목록 API 응답: `{"page": 1, "size": 20, "total": 123, "items": [...]}`
- 에러 응답(표준): `{"code": "...", "message": "...", "error": "...", "request_id": "...", "details": ...}`
- 경로 변수 `{id}`는 정수
- 모든 응답 헤더에 `X-Request-Id` 포함
- 검증 실패는 `400 (VALIDATION_ERROR)`로 응답
- 인증이 활성화된 경우(`REQUIRE_API_KEY=1`) `/api/*` 요청에 `X-API-Key` 헤더 필수
- JWT 인증이 활성화된 경우(`REQUIRE_JWT=1`) `/api/*` 요청에 `Authorization: Bearer <token>` 헤더 필수
  - `JWT_SECRET`: 최소 32 bytes
  - `JWT_ALGORITHM`: 현재 `HS256`만 지원
  - 필수 클레임: `sub`, `exp`
  - 시간 기반 클레임 검증 허용 오차: `JWT_LEEWAY_SECONDS`
  - `JWT_AUDIENCE`/`JWT_ISSUER` 설정 시 `aud`/`iss` 클레임 검증
  - 메서드별 scope 정책: `JWT_SCOPE_READ`, `JWT_SCOPE_WRITE`, `JWT_SCOPE_DELETE`
  - `JWT_ADMIN_ROLE` role 보유 시 scope 검사 우회
- 운영 strict 모드(`SECURITY_STRICT_MODE=1` 또는 `APP_ENV=production`)에서는 인증/호스트/CORS/rate-limit 가드가 강제됨
- `DEBUG`는 앱 설정 플래그이며 `uvicorn --reload` 모드를 자동 활성화하지 않음
- 요청 제한이 활성화된 경우(`RATE_LIMIT_PER_MINUTE>0`) IP 기준 `429 (RATE_LIMITED)` 응답 가능
  - 백엔드: `RATE_LIMIT_BACKEND=memory|redis` (`redis` 사용 시 `REDIS_URL` 필요)
  - Redis 장애 시 fallback 정책: `RATE_LIMIT_FAIL_OPEN` (`1`=허용, `0`=차단)
  - Redis 장애 재시도 쿨다운: `RATE_LIMIT_REDIS_FAILURE_COOLDOWN_SECONDS`
  - 프록시 환경에서는 `TRUSTED_PROXY_CIDRS`에 지정한 CIDR에서만 `X-Forwarded-For`를 신뢰
- write 요청(`/api/*` + `POST/PUT/PATCH`)은 payload 상한 적용
  - 요청 본문 크기 상한: `MAX_REQUEST_BODY_BYTES` (Content-Length 사전 검증 + 실제 본문 길이 검증, 초과 시 `413 PAYLOAD_TOO_LARGE`)
  - 배치 item 상한: `INGEST_MAX_BATCH_ITEMS` (초과 시 `413 PAYLOAD_TOO_LARGE`)

## 유틸리티 엔드포인트

### GET `/`
- 응답: `"API Server Available"` (plain text)

### GET `/health`
- 응답: `{"status": "ok"}`
- 호환성 alias (`/health/live`와 동일한 의미)

### GET `/health/live`
- 응답: `{"status": "ok"}`

### GET `/health/ready`
- 응답(정상): `200` + `{"status":"ok","checks":{"database":{"ok":true},"rate_limit_backend":{"ok":true}}}`
- 응답(의존성 장애): `503` + `{"status":"degraded","checks":{...}}`
- `checks.database`: DB 연결 상태
- `checks.rate_limit_backend`: rate limiting 백엔드 상태 (`memory`/`redis`)

### GET `/metrics`
- 응답: Prometheus text format

### POST `/api/echo`
- 요청: JSON(본문이 없으면 `{}`)
- 응답: `{"you_sent": <요청 JSON>}`
- 인증 활성화 시 `X-API-Key` 필요
- oversized payload는 `413 (PAYLOAD_TOO_LARGE)` 가능

## 뉴스 (`/api/news`)

### POST `/api/news` (Upsert)
- 필수: `title`, `url`
- 선택: `source`, `published_at`, `author`, `summary`, `content`, `keywords`
- `Content-Type: application/json` 권장 (비JSON 본문은 검증 오류)
- `published_at` 허용 포맷:
  - `YYYY-MM-DDTHH:MM:SSZ`
  - `YYYY-MM-DD HH:MM:SS`
  - `YYYY-MM-DDTHH:MM:SS`
  - `YYYY-MM-DDTHH:MM:SS±HH:MM`
- `published_at`는 UTC-aware(`TIMESTAMPTZ`)로 저장됩니다.
  - timezone 없는 입력은 UTC로 간주하여 저장
  - timezone 포함 입력은 UTC로 변환 후 저장
- 단건 객체/배열(배치) 모두 허용
- 응답: `{"inserted": <int>, "updated": <int>}` (201)
- 중복 기준: `url` UNIQUE + upsert
- 인증 활성화 시 `401 (UNAUTHORIZED)` 가능
- 요청 제한 활성화 시 `429 (RATE_LIMITED)` 가능
- 배치/요청 크기 상한 초과 시 `413 (PAYLOAD_TOO_LARGE)` 가능

### GET `/api/news`
- 쿼리: `q`, `source`, `from`, `to`, `page`, `size`
- 검색(`q`): `title`, `summary`, `content`
  - trigram(`ILIKE` + `pg_trgm`) + FTS(`to_tsvector/websearch_to_tsquery`) 분리 전략 사용
- 날짜 필터: `from`/`to`는 `YYYY-MM-DD` 형식 검증 후 `published_at` 기준 필터
  - `from`: 해당 날짜 00:00:00부터 포함
  - `to`: 해당 날짜 23:59:59까지 포함(일 단위 inclusive)

목록 응답 `items[*]`:
- `id`, `source`, `title`, `url`, `published_at`, `author`, `summary`, `keywords`, `created_at`, `updated_at`

### GET `/api/news/{id}`
상세 응답:
- `id`, `source`, `title`, `url`, `published_at`, `author`, `summary`, `content`, `keywords`, `created_at`, `updated_at`

### DELETE `/api/news/{id}`
- 성공: `{"status": "deleted", "id": <id>}`
- 미존재: `{"code":"NOT_FOUND","message":"Not Found","error":"Not Found","request_id":"..."}` (404)

## 회의록 (`/api/minutes`)

### POST `/api/minutes` (Upsert)
- 필수: `council`, `url`
- 선택: `committee`, `session`, `meeting_no`, `meeting_date`, `content`, `tag`, `attendee`, `agenda`
- `Content-Type: application/json` 필요
- `meeting_date`: `YYYY-MM-DD`만 허용
- 단건 객체/배열(배치) 허용
- 응답: `{"inserted": <int>, "updated": <int>}` (201)
- 중복 기준: `url` UNIQUE + upsert
- 인증 활성화 시 `401 (UNAUTHORIZED)` 가능
- 요청 제한 활성화 시 `429 (RATE_LIMITED)` 가능
- 배치/요청 크기 상한 초과 시 `413 (PAYLOAD_TOO_LARGE)` 가능

`meeting_no` 정규화:
- 문자열이면 그대로 `meeting_no_combined` 저장
- 숫자면 `session`과 결합해 `"{session} {n}차"`
- 응답에서는 `meeting_no_combined`를 `meeting_no`로 반환

### GET `/api/minutes`
- 쿼리: `q`, `council`, `committee`, `session`, `meeting_no`, `from`, `to`, `page`, `size`
- 검색(`q`): `council`, `committee`, `session`, `content`, `agenda::text`
  - trigram(`ILIKE` + `pg_trgm`) + FTS(`to_tsvector/websearch_to_tsquery`) 분리 전략 사용
- 날짜 필터: `from`/`to`는 `YYYY-MM-DD` 형식 검증 후 `meeting_date` 기준 필터

목록 응답 `items[*]`:
- `id`, `council`, `committee`, `session`, `meeting_no`, `url`, `meeting_date`, `tag`, `attendee`, `agenda`, `created_at`, `updated_at`

### GET `/api/minutes/{id}`
상세 응답:
- `id`, `council`, `committee`, `session`, `meeting_no`, `url`, `meeting_date`, `content`, `tag`, `attendee`, `agenda`, `created_at`, `updated_at`

### DELETE `/api/minutes/{id}`
- 성공: `{"status": "deleted", "id": <id>}`
- 미존재: `{"code":"NOT_FOUND","message":"Not Found","error":"Not Found","request_id":"..."}` (404)

## 발언 단락 (`/api/segments`)

### POST `/api/segments` (Insert)
- 필수: `council`
- 선택: `committee`, `session`, `meeting_no`, `meeting_date`, `content`, `summary`, `subject`, `tag`, `importance`, `moderator`, `questioner`, `answerer`, `party`, `constituency`, `department`
- `Content-Type: application/json` 필요
- `meeting_date`: `YYYY-MM-DD`만 허용
- `importance`: `1|2|3` 정수만 허용
- 단건 객체/배열(배치) 허용
- 응답: `{"inserted": <int>}` (201)
- idempotent insert: 동일 정규화 payload는 중복 저장하지 않음
- 중복 기준: 서버 계산 `dedupe_hash` (정규화된 주요 필드 JSON의 SHA-256)
- 인증 활성화 시 `401 (UNAUTHORIZED)` 가능
- 요청 제한 활성화 시 `429 (RATE_LIMITED)` 가능
- 배치/요청 크기 상한 초과 시 `413 (PAYLOAD_TOO_LARGE)` 가능

### GET `/api/segments`
- 쿼리: `q`, `council`, `committee`, `session`, `meeting_no`, `importance`, `party`, `constituency`, `department`, `from`, `to`, `page`, `size`
- 검색(`q`):
  - 텍스트: `council`, `committee`, `session`, `content`, `summary`, `subject`, `party`, `constituency`, `department`
  - JSONB 텍스트화: `tag`, `questioner`, `answerer`
  - trigram(`ILIKE` + `pg_trgm`) + FTS(`to_tsvector/websearch_to_tsquery`) 분리 전략 사용
- 날짜 필터: `from`/`to`는 `YYYY-MM-DD` 형식 검증 후 `meeting_date` 기준 필터

목록 응답 `items[*]`:
- `id`, `council`, `committee`, `session`, `meeting_no`, `meeting_date`, `summary`, `subject`, `tag`, `importance`, `moderator`, `questioner`, `answerer`, `party`, `constituency`, `department`

### GET `/api/segments/{id}`
상세 응답:
- `id`, `council`, `committee`, `session`, `meeting_no`, `meeting_date`, `content`, `summary`, `subject`, `tag`, `importance`, `moderator`, `questioner`, `answerer`, `party`, `constituency`, `department`, `created_at`, `updated_at`

### DELETE `/api/segments/{id}`
- 성공: `{"status": "deleted", "id": <id>}`
- 미존재: `{"code":"NOT_FOUND","message":"Not Found","error":"Not Found","request_id":"..."}` (404)
