# CHG-013 — 보안 실험 도구와 Ablation 합성 사전검증

- 요청과 범위: [spec](spec.md). 검증: [evidence](evidence.md).
- 대상 브랜치: `feat/ecu-ablation` (기준 `develop` `6bf9688`), PR base `develop`.
- 상태(2026-10-03): 공격 도구 4종, Ablation 하네스·집계·ROC 도구와 신규 시험 9개 완료. 합성 등급 1,200 매트릭스와 정상 오탐(1.1%, 분모 180) 생성. pytest 34/34. 물리 등급 최종 판정은 장비 실행 대기.
- 결과(합성 등급): 무방어 spoofing·replay 성공 100%, SecOC 차단 100%(성공 0%), Config 3 탐지 100%. flooding은 차단 0%·탐지 100%(탐지≠차단). flooding·fuzzy 가용성은 합성 미측정.
- 변경 없음: IVI·IDS 제품 코드, ICD. 공격 도구는 vcan 또는 확인된 테스트 버스에서만 실행.
- 다음 행동: 물리 CAN에서 attack_simulator로 실제 주입·수신 관측, 실시간 IDS(0x200)→IVI 경보(IT-005), TC-PERF-003 지연. 등급은 synthetic→vcan→물리로 표기한다.
- 후속 후보: matplotlib 설치 시 ROC PNG, masquerade 포함 탐지기 비교(규칙↔사양기반↔IF)는 기존 run_eval.py에서 별도 축으로 유지.
