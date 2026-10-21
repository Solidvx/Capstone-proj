# CHG-015 — 사용자 수동 Pi 시험을 위한 사전 분석 준비

- 날짜: 2026-10-03
- 요청: 사용자가 Pi 실행을 담당하는 동안 나머지 준비를 구현하고 루트 `임시_할일.md`에 쉽고 상세한 행동 순서를 작성.
- 상태: 로컬 구현·검증 완료. 사용자 Pi 환경·물리 시험 반환 자료 대기.
- 구현: M5 argv 설정 템플릿/검증, 학습·calibration·evaluation 분리 IF 점수/ROC, 원본 해시·주기·독립 counter·MAC 차단/복구 자료 판정.
- 안내: [사용자 할 일](../../../../임시_할일.md), [분석 도구](../../../development/playbooks/experiment-analysis.md).
- 검증: [evidence](evidence.md).
- 경계: ICD/HAL/제품 ECU·IVI 방어 정책/IDS 임계 변경 없음. SSH/Pi 실행·배선 조작·Git commit/push 없음.
