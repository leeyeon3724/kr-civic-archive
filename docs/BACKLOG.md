# 백로그

이 문서는 앞으로 진행할 작업만 관리합니다.

## 운영 원칙

- 완료 항목은 이 문서에 남기지 않습니다.
- 완료 이력은 기본적으로 `git log`로 관리합니다.
- 릴리스 노트가 필요한 변경은 `docs/CHANGELOG.md`에 기록합니다.
- 각 항목은 상태(`계획`, `진행 중`, `차단`)를 명시합니다.

## 현재 백로그

- 상태: 계획
- 항목: `/api/segments` 배치 삽입 payload의 dedupe 키 누락 수정  
  - 위험: `dedupe_rows_by_key(..., key=\"dedupe_hash\")` 미적용으로 `dedupe_hash`가 없는 입력을 `None`으로 판단해 중복 제거가 과도하게 발생(다건 손실)
  - 산출: `segments_repository.insert_segments` 입력 payload dedupe 복원 + 회귀 테스트 추가
- 상태: 계획
- 항목: 애플리케이션 종료 시 DB 엔진 정리 누락  
  - 위험: FastAPI 재시작/종료/리로드 시 커넥션 풀이 `dispose()`되지 않아 커넥션 누수 가능
  - 산출: `create_app`에 shutdown 이벤트 핸들러 추가, 종료 동작 검증 테스트 추가
- 상태: 계획
- 항목: `/api/echo` 요청 Body 스키마 정합성 보완  
  - 위험: 기존 `dict` 타입 고정으로 JSON 배열/숫자/문자열 반사 실패 및 OpenAPI/요청 스키마 불일치
  - 산출: `Any` 바인딩/기본값 정합성 보완 + 배열 요청 회귀 테스트 추가

## 운영 메모

- 새 작업 추가 시 기존 항목과 중복 여부를 먼저 확인합니다.
- 작업 완료 시 본 문서에서 항목을 제거하고, 필요하면 `docs/CHANGELOG.md`에만 기록합니다.
