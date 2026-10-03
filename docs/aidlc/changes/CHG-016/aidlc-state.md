# CHG-016 — 사용자 없이 가능한 실험 준비 보완

- 날짜: 2026-10-03
- 요청: Pi 조작/사용자 자료 없이 먼저 할 수 있는 일을 완료.
- 범위: 실제 wire 정상 FPR 수집/판정·손실/중단 검증, ROC SVG/혼동지표/요약 CSV, REP-1 비교, 학습 문서/계획 drift, ASan 설정/시험, 새 전달 snapshot.
- 상태: 해당 독립 준비 구현·로컬 검증 완료. 물리 TC/정책 결정은 미완료 유지.
- 현황: [독립 준비 완료표](../../../development/playbooks/pre-hardware-readiness.md), [검증 기록](evidence.md).
- 경계: 사용자 Pi/키/CAN 설정 변경·서비스 종료·외부 게시·Git stage/commit/push 없음. ICD/HAL/제품 방어·IF wire 정책 유지.
