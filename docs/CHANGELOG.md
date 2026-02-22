# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

### Added
- Centralized environment variable guide (`docs/ENV.md`).
- Centralized quality gate checklist (`docs/QUALITY_GATES.md`).
- Quality metrics policy document (`docs/QUALITY_METRICS.md`) and baseline validator (`scripts/check_quality_metrics.py`).
- Backlog alias path (`docs/BACKLOG.md`) replacing the previous filename.
- Documentation contract coverage for `docs/ENV.md` and `docs/BACKLOG.md` in `scripts/check_docs_routes.py`.
- Release tag workflow (`.github/workflows/release-tag.yml`) to enforce tag/version/changelog consistency.

### Changed
- Project documentation map and quick navigation cleaned up in `README.md`.
- Repeated quality gate command blocks consolidated by referencing `docs/QUALITY_GATES.md` from operations/SLO/contributing docs.
- Index-friendly list ordering path (`date DESC NULLS LAST, id DESC`) applied to repository list queries.
- `docs/BACKLOG.md` policy changed to future-only tracking; completed work is managed via `git log`.
- `docs/BACKLOG.md` entries refreshed as forward-only roadmap items.
- Security baseline for dependencies strengthened: `requests>=2.32.4`, `urllib3>=2.6.3,<3`, `starlette>=0.49.1,<1.0`.

### Fixed
- Documentation structure clarity by separating runtime config, quality checks, and process guidance into dedicated documents.

## [0.1.0] - 2026-02-17

### Added
- Initial FastAPI + PostgreSQL API release.
- Domain APIs for news, council minutes, and speech segments (ingest/list/detail/delete).
- Alembic migration workflow and CI quality/policy gates.
- Standardized error schema and request-id based observability.
