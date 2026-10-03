# CHG-013 — 물리 CAN 보안 통합 도구

요청(2026-10-03): 사용자가 ADS1115·SecOC·Fail-safe 물리 시험과 증거 수집을 계속하는 동안, 계획서에 남은 ECU 보안 통합 도구를 구현한다.

범위: FR-SEC-005의 4종 제한형 SocketCAN CLI, IDS 정상 JSONL/manifest 수집, IT-004의 정상 기준→MAC 1비트 변조→같은 counter 복구 fixture, 기존 실시간 IDS의 `0x200` 경보 cooldown 중 상위 Flooding 분류 보존, IT-002 결정적 `failsafe_demo.csv`·manifest와 전이 간격 회귀시험, TC-PERF-002용 `candump -L` 정규화·엄격 판정 도구, 단위시험과 물리 실행 절차.

보존: ICD v1.6의 CAN ID·DLC·payload·HMAC 입력·counter 규칙은 변경하지 않는다. 실제 키를 저장·출력하지 않는다. 공격 도구는 `vcanN`을 기본으로 하고 물리 `canN`은 격리 시험 확인과 실행 상한을 강제한다.

제외: 실장비 공격 실행, 물리 버스 점유율·탐지율·오탐률 주장, 1,200회 Ablation 결과, 미승인 세션 프로토콜, 자동 배선/인터페이스 재설정.
