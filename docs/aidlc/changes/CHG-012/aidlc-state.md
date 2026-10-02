# CHG-012 — SecOC RollingCounter 인증 CAN ID별 독립

- 요청과 결정: [spec](spec.md). 검증: [evidence](evidence.md).
- 대상 브랜치: `fix/secoc-counter-per-id` (기준 `develop` `919db40`), PR base `develop`.
- 상태(2026-10-03): ICD v1.6 문구, ECU·Python 송신 counter의 인증 ID별 독립, 시험 추가 완료. ECU CTest 14/14, pytest 25/25. IVI 담당 리뷰·승인(계약 합의) 대기.
- 병합 참고: SDD-ECU 머리말의 ICD 참조 버전(3행)은 CHG-011 브랜치가 같은 머리말을 바꾸므로 이 브랜치에서 고치지 않았다. 두 브랜치가 모두 병합된 뒤 v1.6으로 맞춘다. 작업 기록 인덱스 3개 파일은 두 브랜치가 각각 끝에 항목을 추가하므로, 나중에 병합하는 쪽에서 양쪽 항목을 모두 유지한다.
- 다음 행동: 병합 후 ECU RPi 재빌드, IVI와 IT-002에서 간격이 긴 Fail-safe 이벤트 수락 확인.
