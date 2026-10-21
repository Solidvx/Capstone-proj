# CHG-014 — 실시간 보안 시험 준비와 실행 증거

> 현재 상태는 [aidlc-state](aidlc-state.md), 감사 조치/검증은 [보완 기록](../../../development/reviews/experiment-evidence-audit-2026-10-04/REMEDIATION.md)을 따른다. 이하 v2~v8의 미적용·대기 표기는 기록 당시 시점이며 현재 상태를 덮어쓰지 않는다.


- 요청: EXQ-1~11 결정을 유지하여 정상 캡처·IF·물리 Ablation 하네스·IT-004·IT-002 프로파일·집계를 구현하고 검증한다.
- 기준: ICD v1.6, TEST_PLAN TC-SEC-005 / TC-EXP-001~005 / TC-PERF-003, ECU M5, 공동 IT-001~005.
- 브랜치: `feat/security-live-validation`, 시작 `118cc9e`.
- 사용자 기존 미추적 `live_receiver.py`, `live_trial.py`를 보존 후 보완한다. 원본 사본은 `tmp/live-validation-original/`.
- wire·HAL·제품 counter 정책을 변경하지 않는다. 참조 수신기와 IVI 제품 증거, 합성·vcan·물리 등급을 분리한다.
- 실행 분담: 2026-10-03 사용자 답변에 따라 실장비 명령은 사용자가 실행하고 로그를 전달한다. 소프트웨어 구현·로컬 검증·절차·분석은 에이전트가 담당한다.
- 추가 답변: IVI 시험 전용 SecOC OFF·수신 관측은 IVI 담당자가 구현한다. 에이전트는 인계 명세만 작성한다.
- 2026-10-04 후속 승인: 사용자가 송신률 부족과 IF 오탐 개선을 수행하도록 요청했다. 기존 IF 보류를 해제한다. 송신 상한·격리 버스 확인은 유지하고 sub-ms 수신 대기 및 송신 처리시간 포함 스케줄을 수정한다. IF 학습은 실행과 같은 윈도우 경계를 사용하며 독립 정상 보정 세트의 상위 1% 유한표본 순위로 임계를 정한다. 최종 평가 세트와 분리하며 물리 오탐 5% 기준이나 부하 50% 기준을 낮추지 않는다.
- 검증: Python 회귀, C++ 프로파일 실제 알고리즘 시험, CLI 오류/중단·실행 원장 검증. vcan·물리는 환경이 있을 때만 수행한다.

## IDS 수신 시각 보완 v4

수신 후 처리 시각으로 주기를 계산하던 경로를 커널 수신 timestamp로 교정한다. monotonic 변환, idle 타이머 순서, 시각 데이터 실패 처리와 회귀 시험을 포함한다. 기존 CAN/임계/학습 보정은 유지한다. 완료 기준은 로컬 회귀 통과와 RPi Config 3 재확인으로 구분한다.

## 송신 재시도 v5 보완

ENOBUFS/EAGAIN 유한 재시도와 새 run ID에서 시행 번호 재개를 구현했다. 최종 미완료는 INVALID로 중단하며 syscall 실패는 모두 보존한다. 기존 7번 INVALID는 유지한다. WSL Python 74개 통과, Pi 적용·물리 검증 미실행. 상세 방법 변경과 한계: [TX-RETRY-V5](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/TX-RETRY-V5.md).

## v6 계획 시행 계속 수집

사용자 확정: 유효100회 보충이 아닌 계획100회 기록 수집. --continue-invalid로 판정된 INVALID를 보존 후 다음 번호 진행, 실행 불가능 예외는 중단. 종료 경계 미호출의 TX_ERRORS 오집계 수정. WSL 77개 통과, Pi 미적용. [상세 및 002 터미널 근거](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/CONTINUE-INVALID-V6.md).

## C3 flooding IDS 송신 버퍼 부족 보완 v7

001 시행1·2 VALID, 시행3 INVALID ERROR, IDS errno105 종료(사용자 출력). 일시 송신 오류를 ALERT_TX_FAILED로 보존하고 탐지 지속, 실패 포함100ms 간격, 비일시 오류 종료. ICD 및 탐지 임계 불변. Linux 관련16개·전체83개 통과. Pi 적용·물리 검증 및 양측 원본 대조 대기. [보고서](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C3-FLOOD-001.md).

## C3 장기 실행 및 시각 집계 v8

002는 시행4~76 VALID·77 INVALID ERROR, IDS END(사용자 출력). 836초 lifetime 경로와 누적 로그 전체 스캔/수신 dequeue 시각 집계 결함을 보완. 부모 수명 연동·증분 로그 읽기·커널 수신 시각을 적용, Linux88 passed10.29s. Pi 미적용, 과거 C3 전달률 재분석 필요. [근거 및 제한](../../../development/experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C3-FLOOD-002.md).

## 증거 감사 후 보완 범위

사용자의 전체 보완 요청에 따라 오프라인 집계·분모 편차·연관 문서·재현 도구·로컬 복구 묶음을 보완한다. 기존 원본/INVALID/계약/공격 조건은 수정하지 않는다. 검증과 잔여 근거 한계는 [보완 기록](../../../development/reviews/experiment-evidence-audit-2026-10-04/REMEDIATION.md)에 둔다.

## 논문용 종합 보고서 추가

사용자 승인에 따라 실험 설계·실행 과정·결과·비교 분석·한계 및 논문 절별 활용 방법을 [최종 실험 결과 보고서](../../../development/experiments/최종실험_결과_보고서.md)로 작성한다. 보존된 집계를 사용하며 원본·계약·실험 판정을 변경하거나 추가 장비 시험을 수행하지 않는다.
