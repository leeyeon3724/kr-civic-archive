# 시빅 아카이브 API

한국 지방의회 시민 아카이브 데이터 수집/조회 API.
FastAPI + PostgreSQL 기반으로 뉴스, 회의록, 발언 단락 저장/검색을 제공합니다.

## 퀵스타트

```bash
# 1) 환경 변수 파일 준비
cp .env.example .env

# 파워셸
Copy-Item .env.example .env

# 2) 의존성 설치
pip install -r requirements-dev.txt

# 3) DB 마이그레이션 적용 (필수)
python scripts/bootstrap_db.py

# 4) 기본 테스트 (단위/계약)
python -m pytest

# 5) 로컬 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Docker 실행:

```bash
docker compose up --build
```

운영 안전 기본값 Compose:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

## 환경 변수

전체 환경 변수 목록/기본값/운영 권장 설정은 `docs/ENV.md`를 참고하세요.

## 운영 정책

- 스키마 변경은 Alembic만 사용합니다.
- 앱 런타임 수동 DDL(`CREATE/ALTER/DROP TABLE`)은 금지합니다.
- 배포 파이프라인에서 `python -m alembic upgrade head`를 필수로 실행합니다.

## 마이그레이션

```bash
# 최신 버전 적용
python -m alembic upgrade head

# 새 리비전 생성
python -m alembic revision -m "describe change"

# 1단계 롤백
python -m alembic downgrade -1
```

## 품질 게이트

공통 검증 명령 모음은 `docs/QUALITY_GATES.md`를 참고하세요.

## 문서 맵

- API 상세: [docs/API.md](docs/API.md)
- 아키텍처/설계: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 환경 변수: [docs/ENV.md](docs/ENV.md)
- 품질 게이트: [docs/QUALITY_GATES.md](docs/QUALITY_GATES.md)
- 문맥별 가드 정책: [docs/GUARDRAILS.md](docs/GUARDRAILS.md)
- 품질 지표: [docs/QUALITY_METRICS.md](docs/QUALITY_METRICS.md)
- 성능 정책: [docs/PERFORMANCE.md](docs/PERFORMANCE.md)
- SLO 정책: [docs/SLO.md](docs/SLO.md)
- 운영 런북: [docs/OPERATIONS.md](docs/OPERATIONS.md)
- 버전 정책: [docs/VERSIONING.md](docs/VERSIONING.md)
- 변경 이력: [docs/CHANGELOG.md](docs/CHANGELOG.md)
- 기여 가이드: [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)
- 백로그: [docs/BACKLOG.md](docs/BACKLOG.md)

## 통합 테스트 (PostgreSQL)

```bash
docker compose up -d db
python -m alembic upgrade head
RUN_INTEGRATION=1 python -m pytest -m integration
```

## E2E 테스트 (라이브 서버)

```bash
# 로컬/수동 실행: 대상 서버 미도달 시 건너뜀
python -m pytest -q -m e2e --base-url http://localhost:8000

# CI/강제 실행: 대상 서버 미도달 시 실패
E2E_REQUIRE_TARGET=1 python -m pytest -q -m e2e --base-url http://localhost:8000
```
