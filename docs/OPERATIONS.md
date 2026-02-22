# Operations Runbook

## Objectives

- Reduce mean time to detect (MTTD)
- Reduce mean time to recover (MTTR)
- Keep production changes within SLO/error budget policy

## Severity Levels

- SEV-1: complete outage or critical data integrity risk
- SEV-2: major degradation affecting key workflows
- SEV-3: partial degradation with workaround

## Incident Response Checklist

1. Triage
- Confirm impact scope (`/api/*`, specific endpoints, auth, DB, Redis)
- Capture start time and affected versions

2. Stabilize
- If active rollout: pause or rollback deploy
- If dependency issue: switch to degrade mode as documented
- Protect database from overload (throttle or temporarily reduce write pressure)
- For ingest surge: temporarily lower `INGEST_MAX_BATCH_ITEMS` and `MAX_REQUEST_BODY_BYTES` via config rollout

3. Diagnose
- Check health endpoints (`/health/live`, `/health/ready`)
- Check metrics (request error ratio, p95 latency, request volume)
- Check logs using `X-Request-Id`

4. Recover
- Apply fix or rollback
- Verify readiness/liveness and key API paths
- Confirm alerts resolved and traffic normalized

5. Post-Incident
- Write incident report (timeline, root cause, preventive actions)
- Update SLO/error budget status and backlog priorities
- If incident is release-impacting, summarize externally visible changes in `docs/CHANGELOG.md` `Unreleased` section.

## Incident Scenario Templates

모든 시나리오는 아래 공통 필수 항목을 같은 순서로 기록합니다.

- 영향 (Impact): 사용자/엔드포인트/시간대 영향 범위
- 원인 (Cause): 추정 원인과 확정 원인 구분
- 임시조치 (Mitigation): 즉시 완화 조치 및 리스크
- 복구검증 (Recovery Validation): 복구 확인 지표와 확인 시각

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

## SEV Report Format

- SEV-1 보고:
  - 현재 영향 범위, 고객 영향, 우회 불가 여부
  - 15분 간격 업데이트, 임시조치 ETA, 최종 복구 ETA
- SEV-2 보고:
  - 주요 기능 영향 범위, 우회 가능 여부
  - 30분 간격 업데이트, 완화/복구 ETA
- SEV-3 보고:
  - 부분 영향 범위, 임시 우회 경로
  - 60분 간격 업데이트, 영구 조치 일정

## Rollback Strategy

- Application rollback:
  - Redeploy previous known-good image/tag
- Schema rollback:
  - Only if migration is explicitly reversible and data-safe
  - `python -m alembic downgrade -1`
- Configuration rollback:
  - Revert environment variable changes first when issue is config-induced

## Operational Checks

공통 품질/정책 검증은 `docs/QUALITY_GATES.md`를 기준으로 실행합니다.

Runtime checks:

- `python scripts/check_runtime_health.py --base-url http://localhost:8000`
- 장애/강등 모드 점검 시 readiness 503 허용:
  - `python scripts/check_runtime_health.py --base-url http://localhost:8000 --allow-ready-degraded`
- Verify oversized payload guard:
  - confirm `413 PAYLOAD_TOO_LARGE` is returned for request size violations
  - confirm batch ingest limit blocks oversized list payloads

Production compose baseline:

- `docker compose -f docker-compose.prod.yml up -d --build`
- required secrets/env:
  - `POSTGRES_PASSWORD`
  - `API_KEY`
  - `JWT_SECRET` (minimum 32 bytes)

Performance regression:

- `BENCH_PROFILE=staging BENCH_FAIL_THRESHOLD_MS=250 BENCH_FAIL_P95_THRESHOLD_MS=400 python scripts/benchmark_queries.py`
