# Environment Variables

이 문서는 애플리케이션 실행에 필요한 환경 변수의 기본값과 용도를 정리합니다.

## 시작

`.env.example`을 복사해 환경에 맞게 값을 설정합니다.

```bash
# Bash
cp .env.example .env

# PowerShell
Copy-Item .env.example .env
```

애플리케이션과 Alembic은 프로젝트 루트의 `.env`를 자동 로드합니다.

## Database

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `POSTGRES_HOST` | `127.0.0.1` | DB 호스트 |
| `POSTGRES_PORT` | `5432` | DB 포트 |
| `POSTGRES_USER` | `app_user` | DB 사용자 |
| `POSTGRES_PASSWORD` | `change_me` | DB 비밀번호 |
| `POSTGRES_DB` | `civic_archive` | DB 이름 |
| `DB_POOL_SIZE` | `10` | 커넥션 풀 기본 크기 |
| `DB_MAX_OVERFLOW` | `20` | 풀 초과 허용 커넥션 수 |
| `DB_POOL_TIMEOUT_SECONDS` | `30` | 풀 커넥션 획득 대기 시간(초) |
| `DB_POOL_RECYCLE_SECONDS` | `3600` | 유휴 커넥션 재생성 주기(초) |
| `DB_CONNECT_TIMEOUT_SECONDS` | `3` | DB TCP 연결 타임아웃(초) |
| `DB_STATEMENT_TIMEOUT_MS` | `5000` | PostgreSQL statement timeout(ms) |

## App Runtime

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DEBUG` | `0` | 앱 디버그 플래그 (`uvicorn --reload`는 실행 옵션으로 제어) |
| `APP_ENV` | `development` | 실행 환경 (`development`/`staging`/`production`) |
| `PORT` | `8000` | 서버 포트 |
| `BOOTSTRAP_TABLES_ON_STARTUP` | `0` | 정책상 항상 `0` (수동 DDL 금지) |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |
| `LOG_JSON` | `1` | JSON 구조화 로그 사용 여부 |

## Security and Auth

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `SECURITY_STRICT_MODE` | `0` | `1`이면 운영 보안 가드 강제 |
| `REQUIRE_API_KEY` | `0` | `1`이면 `/api/*`에 `X-API-Key` 필수 |
| `API_KEY` | `` | API 키 값 (`REQUIRE_API_KEY=1`일 때 필수) |
| `REQUIRE_JWT` | `0` | `1`이면 `/api/*`에 `Authorization: Bearer <JWT>` 필수 |
| `JWT_SECRET` | `` | JWT HMAC secret (`REQUIRE_JWT=1`일 때 필수, 최소 32 bytes) |
| `JWT_ALGORITHM` | `HS256` | 현재 `HS256`만 지원 |
| `JWT_LEEWAY_SECONDS` | `0` | `exp`/`nbf` 허용 오차(초) |
| `JWT_AUDIENCE` | `` | 지정 시 `aud` 클레임 검증 |
| `JWT_ISSUER` | `` | 지정 시 `iss` 클레임 검증 |
| `JWT_SCOPE_READ` | `archive:read` | 읽기 권한 scope |
| `JWT_SCOPE_WRITE` | `archive:write` | 쓰기 권한 scope |
| `JWT_SCOPE_DELETE` | `archive:delete` | 삭제 권한 scope |
| `JWT_ADMIN_ROLE` | `admin` | role 보유 시 scope 검사 우회 |

## Rate Limit and Proxy

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `RATE_LIMIT_PER_MINUTE` | `0` | IP 기준 분당 요청 제한 (`0`이면 비활성) |
| `RATE_LIMIT_BACKEND` | `memory` | 저장소 (`memory` 또는 `redis`) |
| `REDIS_URL` | `` | Redis URL (`RATE_LIMIT_BACKEND=redis`일 때 필수) |
| `RATE_LIMIT_REDIS_PREFIX` | `civic_archive:rate_limit` | Redis 키 prefix |
| `RATE_LIMIT_REDIS_WINDOW_SECONDS` | `65` | Redis 고정 윈도우 TTL(초) |
| `RATE_LIMIT_REDIS_FAILURE_COOLDOWN_SECONDS` | `5` | Redis 장애 재시도 쿨다운(초) |
| `RATE_LIMIT_FAIL_OPEN` | `1` | Redis 장애 시 허용 여부 (`1` 허용 / `0` 차단) |
| `TRUSTED_PROXY_CIDRS` | `` | 신뢰할 프록시 CIDR 목록(쉼표 구분) |

## CORS and Host

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `CORS_ALLOW_ORIGINS` | `*` | 허용 Origin 목록(쉼표 구분) |
| `CORS_ALLOW_METHODS` | `GET,POST,DELETE,OPTIONS` | 허용 HTTP 메서드(쉼표 구분) |
| `CORS_ALLOW_HEADERS` | `*` | 허용 헤더(쉼표 구분) |
| `ALLOWED_HOSTS` | `*` | Trusted Host 목록(쉼표 구분) |

## Ingest Guardrails

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `INGEST_MAX_BATCH_ITEMS` | `200` | `POST /api/*` 최대 batch item 수 |
| `MAX_REQUEST_BODY_BYTES` | `1048576` | `/api/*` write 요청 최대 payload(bytes) |

## Strict Mode Requirements

`SECURITY_STRICT_MODE=1` 또는 `APP_ENV=production`이면 아래 항목이 강제됩니다.

- 인증 필수 (`REQUIRE_API_KEY=1` 또는 `REQUIRE_JWT=1`)
- `ALLOWED_HOSTS` wildcard 금지
- `CORS_ALLOW_ORIGINS` wildcard 금지
- `RATE_LIMIT_PER_MINUTE > 0`
