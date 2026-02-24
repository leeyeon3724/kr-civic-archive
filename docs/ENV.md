# 환경 변수

이 문서는 애플리케이션 실행에 필요한 환경 변수의 기본값과 용도를 정리합니다.

## 시작

로컬 Python 실행(`uvicorn`, `alembic`)은 `.env`를 사용합니다.
Docker Compose 실행은 `--env-file`로 환경별 파일을 지정합니다.

```bash
# 로컬 앱/스크립트용(.env)
cp .env.example .env

# Docker Compose 개발용
cp .env.dev.example .env.dev
docker compose --env-file .env.dev up --build

# Docker Compose 운영용
cp .env.prod.example .env.prod
docker compose --env-file .env.prod up -d --build --scale api=3
```

애플리케이션과 Alembic은 프로젝트 루트의 `.env`를 자동 로드합니다.

## 데이터베이스

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

## 애플리케이션 런타임

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DEBUG` | `0` | 앱 디버그 플래그 (`uvicorn --reload`는 실행 옵션으로 제어) |
| `APP_ENV` | `development` | 실행 환경 (`development`/`staging`/`production`) |
| `PORT` | `8000` | 서버 포트 |
| `BOOTSTRAP_TABLES_ON_STARTUP` | `0` | 정책상 항상 `0` (수동 DDL 금지) |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |
| `LOG_JSON` | `1` | JSON 구조화 로그 사용 여부 |

## Compose 실행 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `UVICORN_WORKERS` | `1` | 컨테이너 내부 Uvicorn worker 수 |
| `API_PUBLISH_BIND` | `0.0.0.0` | 게이트웨이(host) bind IP |
| `API_PUBLISH_PORT` | `8000` | 게이트웨이(host) 공개 포트 |
| `DB_PUBLISH_BIND` | `127.0.0.1` | PostgreSQL(host) bind IP |
| `DB_PUBLISH_PORT` | `5432` | PostgreSQL(host) 공개 포트 |
| `REDIS_PUBLISH_BIND` | `127.0.0.1` | Redis(host) bind IP |
| `REDIS_PUBLISH_PORT` | `6379` | Redis(host) 공개 포트 |
| `REDIS_APPENDONLY` | `no` | Redis AOF 설정 (`yes`/`no`) |

## 보안 및 인증

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

### 보안 시크릿 생성

`JWT_SECRET`와 `API_KEY`는 충분한 엔트로피가 보장된 값이어야 합니다.
최소 32바이트(256비트) 이상의 무작위 값을 사용하십시오.

```bash
# JWT_SECRET 생성 (권장)
openssl rand -hex 32

# API_KEY 생성 (URL-safe Base64)
openssl rand -base64 32

# Python으로 생성
python -c "import secrets; print(secrets.token_hex(32))"
```

생성한 값을 실행 환경 파일(`.env`, `.env.prod`)에 설정합니다:

```dotenv
JWT_SECRET=<openssl rand -hex 32 결과>
API_KEY=<openssl rand -base64 32 결과>
```

> **주의**: 시크릿을 소스 코드나 버전 관리에 커밋하지 마십시오.
> `.env`는 `.gitignore`에 포함되어야 합니다.

- `REQUIRE_API_KEY=1`과 `REQUIRE_JWT=1`을 동시에 사용하면 `/api/*` 인증은 AND 정책으로 동작하며 두 헤더를 모두 요구합니다.

## 읽기 캐시 (Redis)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `READ_CACHE_TTL_SECONDS` | `0` | 읽기 쿼리 결과 캐시 TTL(초). `0`이면 비활성화 |

- `READ_CACHE_TTL_SECONDS > 0`이면 `REDIS_URL`도 함께 설정해야 합니다.
  캐시는 TTL 만료 방식으로만 무효화됩니다(쓰기 시 자동 무효화 없음).
  쓰기 빈도가 높은 환경에서는 낮은 TTL 값을 사용하십시오.
- 캐시 키는 `civic_archive:read:<domain>:<파라미터>` 형식입니다.
  도메인 단위 무효화(`invalidate_prefix`)가 필요하면 쓰기 핸들러에서 직접 호출합니다.

## 요청 제한 및 프록시

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

## CORS 및 호스트

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `CORS_ALLOW_ORIGINS` | `*` | 허용 Origin 목록(쉼표 구분) |
| `CORS_ALLOW_METHODS` | `GET,POST,DELETE,OPTIONS` | 허용 HTTP 메서드(쉼표 구분) |
| `CORS_ALLOW_HEADERS` | `*` | 허용 헤더(쉼표 구분) |
| `ALLOWED_HOSTS` | `*` | Trusted Host 목록(쉼표 구분) |

## 적재 가드레일

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `INGEST_MAX_BATCH_ITEMS` | `200` | `POST /api/*` 최대 batch item 수 |
| `MAX_REQUEST_BODY_BYTES` | `1048576` | `/api/*` write 요청 최대 payload(bytes) |

## 엄격 모드 요구사항

`SECURITY_STRICT_MODE=1` 또는 `APP_ENV=production`이면 아래 항목이 강제됩니다.

- 인증 필수 (`REQUIRE_API_KEY=1` 또는 `REQUIRE_JWT=1`)
- `ALLOWED_HOSTS` wildcard 금지
- `CORS_ALLOW_ORIGINS` wildcard 금지
- `RATE_LIMIT_PER_MINUTE > 0`
