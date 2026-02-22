# 백로그

이 문서는 앞으로 진행할 작업만 관리합니다.

## 운영 원칙

- 완료 항목은 이 문서에 남기지 않습니다.
- 완료 이력은 기본적으로 `git log`로 관리합니다.
- 릴리스 노트가 필요한 변경은 `docs/CHANGELOG.md`에 기록합니다.
- 각 항목은 상태(`계획`, `진행 중`, `차단`)를 명시합니다.

## 현재 백로그

- 상태: 계획
- 항목: 인증 정책 AND/OR 정합성 확정 및 코드/문서 동기화
  - 근거: `app/security.py`의 `build_metrics_access_dependencies` 및 API 보호 dependency 구성은 `REQUIRE_API_KEY`+`REQUIRE_JWT` 동시 설정 시 AND 동작
  - 리스크: 운영 기대가 OR일 경우 인증 실패율 증가 및 클라이언트 호환성 저하
  - 산출: 정책 결정(AND 또는 OR) 문서화 + `docs/API.md`/`docs/ENV.md` 정렬 + 계약 테스트 추가
- 상태: 계획
- 항목: 목록 API 조회/카운트 2쿼리 패턴 성능 검증 및 최적화안 도출
  - 근거: `app/repositories/common.py`의 `execute_paginated_query`가 list + count를 별도 실행
  - 리스크: 고트래픽 구간에서 DB CPU/latency(p95) 악화 가능
  - 산출: 실제 부하 프로파일링(`scripts/benchmark_queries.py`) 기반 임계치 점검 + 필요 시 최소 변경 최적화안 제시
- 상태: 계획
- 항목: `meeting_no` 문자열 숫자 처리 정책 명확화
  - 근거: `app/utils.py`의 `coerce_meeting_no_int`는 문자열 입력을 정수로 변환하지 않음
  - 리스크: 수집 소스 포맷(`\"3\"` vs `3`)에 따라 검색/정렬 기대치 불일치 가능
  - 산출: 정책 확정 후 minutes/segments 정규화 경로 및 테스트 케이스 정렬

## 운영 메모

- 새 작업 추가 시 기존 항목과 중복 여부를 먼저 확인합니다.
- 작업 완료 시 본 문서에서 항목을 제거하고, 필요하면 `docs/CHANGELOG.md`에만 기록합니다.
