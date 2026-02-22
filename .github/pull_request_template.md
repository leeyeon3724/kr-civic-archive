## 요약
- 무엇이 변경되었는가:
- 왜 지금 필요한가:

## 백로그 연계
- `docs/BACKLOG.md`의 연관 항목:

## 품질 지표 (docs/QUALITY_METRICS.md)
- [ ] 성능 영향 (`/api/news`, `/api/minutes`, `/api/segments`, benchmark avg/p95 delta)
- [ ] 안정성 영향 (4xx/5xx 비율, readiness 강등, MTTR 신호)
- [ ] 신뢰성 영향 (`/health/live`, `/health/ready`, 요청 추적 완결성)
- [ ] 유지보수성 영향 (coverage, mypy, 문서 정책/스크립트 회귀 위험)
- [ ] 리팩토링 우선순위 근거(P0-P3) 및 지금 수행하는 이유

## 정책 정합성 (docs/GUARDRAILS.md)
- [ ] 보안/런타임 정책 문서 동기화 (`docs/API.md`, `docs/ENV.md`, `docs/ARCHITECTURE.md`, `docs/OPERATIONS.md`)
- [ ] 문맥별 가드 명령 세트 검토 (로컬/PR/릴리스/인시던트)

## 검증
- [ ] `python -m ruff check app tests scripts`
- [ ] `python scripts/check_mypy.py`
- [ ] `python -m pytest -q -m "not e2e and not integration" --cov=app --cov-report=term --cov-fail-under=85`
- [ ] `python scripts/check_docs_routes.py`
- [ ] `python scripts/check_schema_policy.py`
- [ ] `python scripts/check_version_consistency.py`
- [ ] `python scripts/check_slo_policy.py`
- [ ] `python scripts/check_quality_metrics.py`
