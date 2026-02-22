# SLO Policy

This document defines service-level indicators (SLI), objectives (SLO), error budget policy, and alert policy for `civic-archive-api`.

## Scope

- Service: `civic-archive-api`
- Environment: production (`APP_ENV=production`)
- Request scope: `/api/*` endpoints
- Observation source: Prometheus metrics (`civic_archive_http_requests_total`, `civic_archive_http_request_duration_seconds`)

## SLI Definitions

### Availability SLI

- Definition: ratio of successful requests over total requests for `/api/*`
- Success: HTTP status code `< 500`
- Formula:
  - `availability = 1 - (5xx_requests / total_requests)`

### Latency SLI

- Definition: p95 request latency for `/api/*`
- Source: `civic_archive_http_request_duration_seconds` histogram
- Formula:
  - `histogram_quantile(0.95, sum(rate(civic_archive_http_request_duration_seconds_bucket{path=~"/api/.*"}[5m])) by (le))`

## SLO Targets

- Availability SLO (30-day rolling): `>= 99.9%`
- Latency SLO (5m window p95): `<= 250ms`
- Readiness SLO:
  - `/health/live` = `200`
  - `/health/ready` = `200`

## Error Budget Policy

- Availability SLO 99.9% yields monthly error budget:
  - ~43m 12s per 30 days

Burn policy:

- 2-hour burn > 10% budget: page on-call immediately, stop non-critical deploys
- 24-hour burn > 25% budget: require incident review before feature rollout
- 30-day burn > 50% budget: reliability freeze for non-critical changes
- 30-day burn > 80% budget: only incident, security, and reliability changes allowed

## Alert Policy

### Page Alerts (high urgency)

- `5xx error ratio > 5%` for 5 minutes
- `p95 latency > 500ms` for 10 minutes
- `/health/ready != 200` for 3 consecutive checks

### Warning Alerts (medium urgency)

- `5xx error ratio > 1%` for 15 minutes
- `p95 latency > 300ms` for 15 minutes
- error budget burn > 25% in 24h

## Deployment Guardrails

Before deploying to production:

1. Run quality gates in `docs/QUALITY_GATES.md`.
2. Run DB migration check:
   - `python -m alembic upgrade head`
3. Run pre-deploy runtime checks (target environment):
   - `python scripts/check_runtime_health.py --base-url <target-base-url>`
4. Run benchmark regression checks:
   - `BENCH_PROFILE=staging BENCH_FAIL_THRESHOLD_MS=250 BENCH_FAIL_P95_THRESHOLD_MS=400 python scripts/benchmark_queries.py`

## Incident Handling Linkage

- Incident response checklist and rollback guidance: `docs/OPERATIONS.md`
