# 운영 런북

## 목표

- 평균 탐지 시간(MTTD) 단축
- 평균 복구 시간(MTTR) 단축
- 프로덕션 변경을 SLO/오류 예산 정책 범위 내에서 운영

## 심각도 수준

- SEV-1: 전체 장애 또는 치명적 데이터 무결성 위험
- SEV-2: 핵심 기능에 영향을 주는 중대 성능 저하
- SEV-3: 우회 가능한 부분 장애

## 인시던트 대응 체크리스트

1. 초기 분류(트리아지)
- 영향 범위 확인 (`/api/*`, 특정 엔드포인트, 인증, DB, Redis)
- 시작 시각과 영향 받은 버전 기록

2. 안정화(스태빌라이즈)
- 배포 진행 중이면 배포 중단 또는 롤백
- 의존성 장애면 문서화된 강등 모드(degraded mode) 전환
- DB 과부하 보호(스로틀링 또는 쓰기 압력 임시 완화)
- ingest 급증 시 `INGEST_MAX_BATCH_ITEMS`, `MAX_REQUEST_BODY_BYTES` 임시 하향 롤아웃

3. 진단(다이애그노즈)
- 헬스 엔드포인트 확인 (`/health/live`, `/health/ready`)
- 메트릭 확인(요청 오류율, p95 지연, 요청량)
- `X-Request-Id` 기반 로그 추적

4. 복구(리커버리)
- 수정 반영 또는 롤백 적용
- readiness/liveness 및 핵심 API 경로 검증
- 알림 해소 및 트래픽 정상화 확인

5. 사후 처리(포스트 인시던트)
- 인시던트 보고서 작성(타임라인, 근본 원인, 예방 조치)
- SLO/오류 예산 상태와 백로그 우선순위 갱신
- 릴리스 영향 장애인 경우 `docs/CHANGELOG.md` `Unreleased` 섹션에 외부 영향 변경 요약

## 인시던트 시나리오 템플릿

모든 시나리오는 아래 공통 필수 항목을 같은 순서로 기록합니다.

- 영향: 사용자/엔드포인트/시간대 영향 범위
- 원인: 추정 원인과 확정 원인 구분
- 임시조치: 즉시 완화 조치 및 리스크
- 복구검증: 복구 확인 지표와 확인 시각

### DB 장애 템플릿

- 영향:
- 원인:
- 임시조치:
- 복구검증:
- 후속조치:

### Redis/rate_limit_backend 장애 템플릿

- 영향:
- 원인:
- 임시조치:
- 복구검증:
- 후속조치:

### 배포/릴리스 장애 템플릿

- 영향:
- 원인:
- 임시조치:
- 복구검증:
- 롤백/재배포 기록:

### 과부하(트래픽 급증) 템플릿

- 영향:
- 원인:
- 임시조치:
- 복구검증:
- 용량/성능 후속조치:

## SEV 보고 형식

- SEV-1 보고:
  - 현재 영향 범위, 고객 영향, 우회 불가 여부
  - 15분 간격 업데이트, 임시조치 ETA, 최종 복구 ETA
- SEV-2 보고:
  - 주요 기능 영향 범위, 우회 가능 여부
  - 30분 간격 업데이트, 완화/복구 ETA
- SEV-3 보고:
  - 부분 영향 범위, 임시 우회 경로
  - 60분 간격 업데이트, 영구 조치 일정

## 롤백 전략

- 애플리케이션 롤백:
  - 직전 정상 이미지/태그 재배포
- 스키마 롤백:
  - 마이그레이션이 명시적으로 가역적이고 데이터 안전성이 보장될 때만 수행
  - `python -m alembic downgrade -1`
- 설정 롤백:
  - 설정 기인 장애면 환경 변수 변경부터 우선 원복

## 운영 점검

공통 품질/정책 검증은 `docs/QUALITY_GATES.md`를 기준으로 실행합니다.

런타임 점검:

- `python scripts/check_runtime_health.py --base-url http://localhost:8000`
- 장애/강등 모드 점검 시 readiness 503 허용:
  - `python scripts/check_runtime_health.py --base-url http://localhost:8000 --allow-ready-degraded`
- oversized payload 가드 점검:
  - 요청 크기 위반 시 `413 PAYLOAD_TOO_LARGE` 반환 확인
  - 배치 ingest 상한이 초과 목록 payload를 차단하는지 확인

프로덕션 compose 기준:

- `docker compose -f docker-compose.prod.yml up -d --build`
- 필수 시크릿/환경 변수:
  - `POSTGRES_PASSWORD`
  - `API_KEY`
  - `JWT_SECRET` (최소 32 bytes)

성능 회귀 점검:

- `BENCH_PROFILE=staging BENCH_FAIL_THRESHOLD_MS=250 BENCH_FAIL_P95_THRESHOLD_MS=400 python scripts/benchmark_queries.py`
