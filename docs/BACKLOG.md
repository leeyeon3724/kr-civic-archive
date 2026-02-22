# 백로그

이 문서는 앞으로 진행할 작업만 관리합니다.

## 운영 원칙

- 완료 항목은 이 문서에 남기지 않습니다.
- 완료 이력은 기본적으로 `git log`로 관리합니다.
- 릴리스 노트가 필요한 변경은 `docs/CHANGELOG.md`에 기록합니다.
- 각 항목은 상태(`계획`, `진행 중`, `차단`)를 명시합니다.

## 평가 기준

- 대상: `/api/news`, `/api/minutes`, `/api/segments` 도메인 전체.
- 우선순위 기준:
  - 상: 운영 영향이 크거나 중복 제거 효과가 큰 과제
  - 중: 유지보수성/검증성 개선이 중요한 과제
  - 하: 정리/명세 보완 중심 과제
- 완료 기준(공통):
  - API 계약, 에러 코드, 기존 동작(상태 코드/응답 구조) 비변경
  - `python -m pytest` 기본 선호 테스트 범주 통과
  - 기존 회귀/성능 테스트와 새로운 과제별 체크리스트 항목 반영
  - `docs/QUALITY_GATES.md`의 필수 검증 항목 정합

## 현재 백로그

- 상태: 계획 / 우선순위: 중
  - 항목: 요청 바디 가드에서 음수 `Content-Length` 차단
  - 대상:
    - `app/bootstrap/middleware.py`
    - `tests/bootstrap/test_runtime_limits.py`
  - 과제: `Content-Length` 파싱 후 음수 값(`-1` 등)을 `400 BAD_REQUEST`로 일관 처리
  - 산출 기준:
    - 음수/비정상 `Content-Length` 요청이 모두 `400`과 동일 에러 메시지로 응답
    - 기존 `413`(payload too large) 경로와 충돌 없이 회귀 테스트 통과

- 상태: 계획 / 우선순위: 중
  - 항목: 리소스 존재 확인 가드의 falsy 오판정 제거
  - 대상:
    - `app/routes/common.py`
    - `app/routes/news.py`
    - `app/routes/minutes.py`
    - `app/routes/segments.py`
    - `tests/test_bootstrap_boundaries.py`
  - 과제: `ensure_resource_found` 판정 조건을 `None` 전용으로 변경해 빈 dict/list/0 오탐을 제거
  - 산출 기준:
    - `None`만 `404`를 반환하고, 기타 falsy 값은 `NOT_FOUND`로 강제 변환되지 않음
    - 라우트 상세 조회/삭제의 기존 정상·404 계약 테스트 유지

- 상태: 계획 / 우선순위: 중
  - 항목: `request.client` 부재 시 rate-limit client key 안정화
  - 대상:
    - `app/security_proxy.py`
    - `app/security.py`
    - `tests/test_security_modules.py`
    - `tests/security/test_rate_limit_runtime.py`
  - 과제: `request.client` 미존재 시 `request_id` 기반 임시 키 대신 안정적인 fallback 규칙을 도입
  - 산출 기준:
    - 동일 요청자 조건에서 client key가 요청 간 불필요하게 변하지 않음
    - XFF/신뢰 프록시/비정상 헤더 기존 경계 테스트와 신규 fallback 테스트 통과

## 운영 메모

- 새 작업 추가 시 기존 항목과 중복 여부를 먼저 확인합니다.
- 작업 완료 시 본 문서에서 항목을 제거하고, 필요하면 `docs/CHANGELOG.md`에만 기록합니다.
