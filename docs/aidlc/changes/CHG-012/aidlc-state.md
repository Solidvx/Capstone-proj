# CHG-012 — SecOC RollingCounter 인증 CAN ID별 독립

- 요청과 결정: [spec](spec.md). 검증: [evidence](evidence.md).
- 대상 브랜치: `fix/secoc-counter-per-id` (기준 `develop` `919db40`), PR base `develop`.
- 상태(2026-10-03): ICD v1.6 문구, ECU·Python 송신 counter의 인증 ID별 독립, 시험 추가 완료. ECU CTest 14/14, pytest 25/25. IVI 담당 리뷰·승인(계약 합의) 대기.
- 병합 정리(2026-10-03): CHG-011(#16) 병합 후 `develop`을 이 브랜치에 합쳐 작업 기록 인덱스 3개 파일의 충돌을 양쪽 항목 유지로 해결했다. SDD-ECU 머리말의 ICD 참조를 v1.6으로 맞추고 변경 이력 v1.7에 §3.5.1 갱신을 덧붙였다. `document-map`의 CHG-011 결정 ID 표기(D1~D4)를 ADS-1~ADS-6으로 정정했다.
- 계약 합의(2026-10-03): 사용자 답변 [EXQ-9](../../../development/governance/보안실험_통합시험_진행결정.md#answers-applied)=A, IVI 담당 승인을 받았다. 승인 방식과 ICD §5의 `interface-change` Issue 유무는 사용자 확인 대기다.
- 다음 행동: 병합 후 ECU RPi 재빌드, IVI와 IT-002에서 간격이 긴 Fail-safe 이벤트 수락 확인.
