# CHG-014 — 실시간 보안 시험 준비와 실행 증거

- 요청: EXQ-1~11 결정을 유지하여 정상 캡처·IF·물리 Ablation 하네스·IT-004·IT-002 프로파일·집계를 구현하고 검증한다.
- 기준: ICD v1.6, TEST_PLAN TC-SEC-005 / TC-EXP-001~005 / TC-PERF-003, ECU M5, 공동 IT-001~005.
- 브랜치: `feat/security-live-validation`, 시작 `118cc9e`.
- 사용자 기존 미추적 `live_receiver.py`, `live_trial.py`를 보존 후 보완한다. 원본 사본은 `tmp/live-validation-original/`.
- wire·HAL·제품 counter 정책을 변경하지 않는다. 참조 수신기와 IVI 제품 증거, 합성·vcan·물리 등급을 분리한다.
- 실행 분담: 2026-10-03 사용자 답변에 따라 실장비 명령은 사용자가 실행하고 로그를 전달한다. 소프트웨어 구현·로컬 검증·절차·분석은 에이전트가 담당한다.
- 추가 답변: IVI 시험 전용 SecOC OFF·수신 관측은 IVI 담당자가 구현한다. 에이전트는 인계 명세만 작성한다.
- 검증: Python 회귀, C++ 프로파일 실제 알고리즘 시험, CLI 오류/중단·실행 원장 검증. vcan·물리는 환경이 있을 때만 수행한다.
