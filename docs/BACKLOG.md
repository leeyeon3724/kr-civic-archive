# 백로그

이 문서는 앞으로 진행할 작업만 관리합니다.

## 운영 원칙

- 완료 항목은 이 문서에 남기지 않습니다.
- 완료 이력은 기본적으로 `git log`로 관리합니다.
- 릴리스 노트가 필요한 변경은 `docs/CHANGELOG.md`에 기록합니다.
- 각 항목은 상태(`계획`, `진행 중`, `차단`)를 명시합니다.

## 현재 백로그

- 상태: 진행 중
- 항목: 목록 API total 산출의 window/CTE 단일 쿼리 전환 타당성 검토
  - 근거: 현재는 첫 페이지 미만 결과에서만 count 생략 최적화가 적용되며, 고부하 구간에서는 여전히 list/count 분리 실행
  - 리스크: 대규모 데이터셋 + 복합 필터에서 count query가 p95 병목으로 남을 수 있음
  - 산출: `scripts/analyze_total_strategy.py` 결과를 기반으로 offset별 split/window 전략 비교 리포트 작성
- 상태: 진행 중
- 항목: 테스트 디렉토리 구조 정리 및 초대형 테스트 파일 분할(2차)
  - 근거: `tests/security/test_auth_runtime.py`, `tests/security/test_rate_limit_runtime.py`로 인증/요청제한 시나리오를 분리했지만, `tests/test_app_baseline.py`는 여전히 499라인
  - 리스크: 단일 파일 내 회귀 분석 난이도와 변경 충돌 위험이 여전히 높음
  - 산출: `tests/test_app_baseline.py`의 payload-guard/observability/DB runtime 튜닝 블록을 도메인 테스트 파일로 추가 분할

## 운영 메모

- 새 작업 추가 시 기존 항목과 중복 여부를 먼저 확인합니다.
- 작업 완료 시 본 문서에서 항목을 제거하고, 필요하면 `docs/CHANGELOG.md`에만 기록합니다.
