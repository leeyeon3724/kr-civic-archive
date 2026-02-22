# 변경 이력

이 파일은 프로젝트의 주요 변경 사항을 기록합니다.

형식은 Keep a Changelog를 기반으로 하며, 버전 정책은 Semantic Versioning을 따릅니다.

## [Unreleased]

### 추가
- 환경 변수 가이드 문서(`docs/ENV.md`)를 중앙화했습니다.
- 품질 게이트 체크리스트(`docs/QUALITY_GATES.md`)를 중앙화했습니다.
- 품질 지표 정책 문서(`docs/QUALITY_METRICS.md`)와 기준선 검증기(`scripts/check_quality_metrics.py`)를 추가했습니다.
- 기존 파일명을 대체하는 백로그 경로(`docs/BACKLOG.md`)를 추가했습니다.
- `scripts/check_docs_routes.py`에 `docs/ENV.md`, `docs/BACKLOG.md` 문서 계약 검증을 추가했습니다.
- 태그/버전/변경이력 정합성을 강제하는 릴리스 태그 워크플로우(`.github/workflows/release-tag.yml`)를 추가했습니다.

### 변경
- `README.md`의 문서 맵과 빠른 이동 구성을 정리했습니다.
- 운영/SLO/기여 문서의 중복 품질 게이트 명령을 `docs/QUALITY_GATES.md` 참조 방식으로 통합했습니다.
- 리포지토리 목록 조회에 인덱스 친화 정렬 경로(`date DESC NULLS LAST, id DESC`)를 적용했습니다.
- `docs/BACKLOG.md` 정책을 미래 작업 전용으로 변경하고, 완료 이력은 `git log`로 관리하도록 정리했습니다.
- `docs/BACKLOG.md` 항목을 전진형 로드맵 기준으로 갱신했습니다.
- 의존성 보안 기준을 강화했습니다: `requests>=2.32.4`, `urllib3>=2.6.3,<3`, `starlette>=0.49.1,<1.0`.

### 수정
- 런타임 설정/품질 점검/프로세스 가이드를 전용 문서로 분리해 문서 구조 가독성을 개선했습니다.

## [0.1.0] - 2026-02-17

### 추가
- FastAPI + PostgreSQL 기반 초기 API 릴리스를 제공했습니다.
- 뉴스/회의록/발언 단락 도메인 API(수집/목록/상세/삭제)를 추가했습니다.
- Alembic 마이그레이션 워크플로우와 CI 품질/정책 게이트를 추가했습니다.
- 표준 에러 스키마와 request-id 기반 관측성을 도입했습니다.
