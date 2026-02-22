# 백로그

이 문서는 앞으로 진행할 작업만 관리합니다.

## 운영 원칙

- 완료 항목은 이 문서에 남기지 않습니다.
- 완료 이력은 기본적으로 `git log`로 관리합니다.
- 릴리스 노트가 필요한 변경은 `docs/CHANGELOG.md`에 기록합니다.
- 각 항목은 상태(`계획`, `진행 중`, `차단`)를 명시합니다.

## 현재 백로그

| 상태 | 우선순위 | 항목 | 근거 | 액션 |
| --- | --- | --- | --- | --- |
| 계획 | Medium | 회의번호 bool 입력 정합성 보강 | `app/utils.py:50-56`에서 bool가 `int()`로 `True->1`, `False->0` 변환되어 `meeting_no`로 수용될 수 있음 | bool 타입 사전 차단 (`isinstance(meeting_no_raw, bool)` 체크 추가 또는 스키마 단에서 타입 검사 강화) |
| 계획 | Medium | DB 연결 URL 평문 노출 점검 | `app/config.py:66-74`의 `database_url`에서 `hide_password=False` 사용 | 현재 운영 로깅/디버그 경로에서 DB URL이 출력되는지 확인 필요(가정/검증 필요). 필요 시 `hide_password=True` 또는 마스킹 처리로 로그 유출 차단 |

## 운영 메모

- 새 작업 추가 시 기존 항목과 중복 여부를 먼저 확인합니다.
- 작업 완료 시 본 문서에서 항목을 제거하고, 필요하면 `docs/CHANGELOG.md`에만 기록합니다.
