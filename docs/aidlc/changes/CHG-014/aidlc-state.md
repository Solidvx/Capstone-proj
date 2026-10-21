# CHG-014 현재 상태

## 2026-10-04 증거 감사 후 보완

실장비 수집: 3구성×4공격의 계획 번호 1~100 자료를 수령했다. 전체 원장 1,201시도(VALID 1,197, INVALID 4), C1 flooding 7번 재시도 1개 포함. 최초 시도 기준 1,200번호 중 VALID 1,196, INVALID 4이며 재시도로 INVALID를 덮지 않는다. 수집 완료와 전체 TC PASS는 별개다.

- 정상·성능·노브·pilot·진단: [보존 인덱스](../../../development/experiments/ecu-ivi-integration-2026-10-03_04/README.md).
- 본 실험: [독립 보존 인덱스](../../../development/experiments/physical-ablation-formal-2026-10-04/README.md).
- 분석 및 문서 보완: [재현 절차](../../../development/experiments/physical-ablation-formal-2026-10-04/REPRODUCE.md), [논문 표](../../../development/experiments/physical-ablation-formal-2026-10-04/publication/TABLES.md), [TC 추적/편차](../../../development/experiments/physical-ablation-formal-2026-10-04/METHODS-AND-TRACEABILITY.md).
- 감사 발견과 조치: [감사](../../../development/reviews/experiment-evidence-audit-2026-10-04/README.md), [조치 기록](../../../development/reviews/experiment-evidence-audit-2026-10-04/REMEDIATION.md).

현재 남은 것은 근거상 한계다. C3 flooding 구버전 지연·전달률은 채택 제외, 화면 미수집·Qt 경고 영향은 미확인, 0x200 비인증 경보의 출처를 분리한다. IT-004 전용 fixture의 완전한 물리 인수는 현재 Ablation 자료로 대체하지 않는다. 외부 백업 위치/성공 여부는 BACKUP 기록을 따른다. 요청받지 않은 하드웨어 재시험·계약 변경은 진행하지 않았다.

## 이력과 검증

- [이전 시점별 상태](state-history.md): 당시 미시작/보류 문구를 보존하며 현재 상태로 사용하지 않는다.
- [요구·변경 범위](spec.md), [검증 증거](evidence.md), [운영 절차](../../../development/playbooks/live-security-validation.md).
- 현재 작업은 기존 dirty worktree에 추가한 미커밋 변경이다. 이전 실험 당시 버전은 raw manifest가 원천이며 현재 소스로 소급 대체하지 않는다.

## 논문 활용 문서

[최종 실험 결과 보고서](../../../development/experiments/최종실험_결과_보고서.md)에 설계·과정·비교·한계·논문 절별 활용을 종합했다. 수치는 publication 집계에 연결하며 현재 상태 원본은 이 파일로 유지한다. 사용자가 기존 외부 백업의 Google Drive 업로드를 보고했으며 원격 재다운로드 해시는 미검증이다. 이번 새 보고서는 기존 백업 이후 생성되어 다음 백업에 포함해야 한다.
