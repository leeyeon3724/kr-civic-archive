## Summary
- What changed:
- Why now:

## Backlog linkage
- Related backlog item in `docs/BACKLOG.md`:

## Quality Metrics (docs/QUALITY_METRICS.md)
- [ ] Performance impact (`/api/news`, `/api/minutes`, `/api/segments`, benchmark avg/p95 delta)
- [ ] Stability impact (4xx/5xx ratio, readiness degradation, MTTR signal)
- [ ] Reliability impact (`/health/live`, `/health/ready`, request trace completeness)
- [ ] Maintainability impact (coverage, mypy, docs policy/script regression risk)
- [ ] Refactoring priority rationale (P0-P3) and why now

## Policy Alignment (docs/GUARDRAILS.md)
- [ ] Security/runtime policy docs sync (`docs/API.md`, `docs/ENV.md`, `docs/ARCHITECTURE.md`, `docs/OPERATIONS.md`)
- [ ] Contextual guard command set reviewed (local/PR/release/incident)

## Validation
- [ ] `python -m ruff check app tests scripts`
- [ ] `python scripts/check_mypy.py`
- [ ] `python -m pytest -q -m "not e2e and not integration" --cov=app --cov-report=term --cov-fail-under=85`
- [ ] `python scripts/check_docs_routes.py`
- [ ] `python scripts/check_schema_policy.py`
- [ ] `python scripts/check_version_consistency.py`
- [ ] `python scripts/check_slo_policy.py`
- [ ] `python scripts/check_quality_metrics.py`
