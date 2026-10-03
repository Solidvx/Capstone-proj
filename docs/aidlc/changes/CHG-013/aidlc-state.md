# CHG-013 — 초기 합성 실험·후속 물리 보안 통합

- 초기 PR #21의 합성 실행/ROC 기록과 후속 물리 도구 기록을 구분해 보존한다.
- 요청·범위: [spec](spec.md)
- 검증 결과: [evidence](evidence.md)
- 상태: 소스·로컬 검증 완료. 공식 물리 Ablation 1,200회 및 IT-002/공격 시험 인수 대기.
- 초기 합성 CLI: `security/experiments/run_ablation_synthetic.py`, `summarize_ablation_synthetic.py`, `analyze_roc_synthetic.py`. 초기 수치는 합성이며 후속 IF/물리 평가와 같은 결과가 아니다.
- 사용자 장비 절차: [물리 CAN 보안 통합](../../../development/playbooks/security-can-integration.md)
- 후속 검증: [CHG-014](../CHG-014/aidlc-state.md), [CHG-016](../CHG-016/aidlc-state.md), [전체 진행 보고](../../../development/reviews/전체계획_진행보고_20261003.md)
