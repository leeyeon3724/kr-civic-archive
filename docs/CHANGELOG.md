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
- 리팩터링 PR에서 API 계약/메트릭/벤치마크 회귀를 빠르게 확인할 수 있도록
  회귀 템플릿 테스트(`tests/test_refactor_regression_template.py`)를 추가했습니다.

### 변경
- `README.md`의 문서 맵과 빠른 이동 구성을 정리했습니다.
- 운영/SLO/기여 문서의 중복 품질 게이트 명령을 `docs/QUALITY_GATES.md` 참조 방식으로 통합했습니다.
- 리포지토리 목록 조회에 인덱스 친화 정렬 경로(`date DESC NULLS LAST, id DESC`)를 적용했습니다.
- `docs/BACKLOG.md` 정책을 미래 작업 전용으로 변경하고, 완료 이력은 `git log`로 관리하도록 정리했습니다.
- `docs/BACKLOG.md` 항목을 전진형 로드맵 기준으로 갱신했습니다.
- 의존성 보안 기준을 강화했습니다: `requests>=2.32.4`, `urllib3>=2.6.3,<3`, `starlette>=0.49.1,<1.0`.
- `/api/news`, `/api/minutes`, `/api/segments` 라우트의 공통 패턴(배치 입력 처리, 404/delete 가드)을
  `app/routes/common.py` 헬퍼 중심으로 통일했습니다.
- 서비스 계층 정규화 흐름을 `app/services/common.py`로 통합해 페이지네이션/필터/날짜 정규화 일관성을 강화했습니다.
- 리포지토리 계층 날짜 필터 조립을 공통 빌더로 정리해 도메인별 목록 쿼리 조건 구성을 표준화했습니다.
- 관측성 라우트 템플릿 캐시 접근에 락을 적용해 동시 요청 환경에서 라벨 해상도 안정성을 보강했습니다.
- 요청 바디 가드 정책을 상수/헬퍼 기반으로 정리하고 `POST/PUT/PATCH` 경계 검증을 테스트로 고정했습니다.

### 수정
- 런타임 설정/품질 점검/프로세스 가이드를 전용 문서로 분리해 문서 구조 가독성을 개선했습니다.
- 보안 프록시/XFF 기반 client key 판별의 IPv4/IPv6/비정상 헤더 경계 시나리오 테스트를 보강했습니다.
- `segments` 서비스에서 사용하지 않는 중요도 파서 경로를 제거해 정책 단일성과 유지보수성을 개선했습니다.

## [0.1.0] - 2026-02-17

### 추가
- FastAPI + PostgreSQL 기반 초기 API 릴리스를 제공했습니다.
- 뉴스/회의록/발언 단락 도메인 API(수집/목록/상세/삭제)를 추가했습니다.
- Alembic 마이그레이션 워크플로우와 CI 품질/정책 게이트를 추가했습니다.
- 표준 에러 스키마와 request-id 기반 관측성을 도입했습니다.
