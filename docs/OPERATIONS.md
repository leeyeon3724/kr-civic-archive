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
