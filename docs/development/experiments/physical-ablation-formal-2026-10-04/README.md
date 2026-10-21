# 공식 물리 Ablation 증거

진행 상태 원본: [CHG-014](../../../aidlc/changes/CHG-014/aidlc-state.md). 이 인덱스는 결과 위치를 안내하며 시험 PASS를 중복 선언하지 않는다.

- `raw/`: 수령 압축파일·추출 원본. 실패/중단/INVALID도 보존.
- `inventory.json`: 원본 출처·보존 SHA256.
- `analysis/`: 당시 케이스별 분석 결과.
- `reports/`: 해석·예외·미수집 자료.
- `tools/`: 당시 분석 도구.

원본은 Git 제외 로컬 보존이다. 커밋·원격 백업 완료를 뜻하지 않는다. 대화만으로 제공된 화면 관측은 파일 증거와 구분한다.

- [논문용 재현 절차](REPRODUCE.md)
- [최종 비교표](publication/TABLES.md)
- [케이스·버전별 기계 집계](publication/summary.json)
- [판정·요구사항 추적 및 제한](METHODS-AND-TRACEABILITY.md)
- [백업·복구](BACKUP.md)
- [통합·예비 근거](../ecu-ivi-integration-2026-10-03_04/README.md)

## 케이스별 보고서

- [ABLATION-FORMAL-C1-FLOOD-001](reports/ABLATION-FORMAL-C1-FLOOD-001.md)
- [ABLATION-FORMAL-C1-FLOOD-002-003](reports/ABLATION-FORMAL-C1-FLOOD-002-003.md)
- [ABLATION-FORMAL-C1-FUZZY-001](reports/ABLATION-FORMAL-C1-FUZZY-001.md)
- [ABLATION-FORMAL-C1-REPLAY-001](reports/ABLATION-FORMAL-C1-REPLAY-001.md)
- [ABLATION-FORMAL-C1-SPOOF-001](reports/ABLATION-FORMAL-C1-SPOOF-001.md)
- [ABLATION-FORMAL-C2-FLOOD-001](reports/ABLATION-FORMAL-C2-FLOOD-001.md)
- [ABLATION-FORMAL-C2-FUZZY-001](reports/ABLATION-FORMAL-C2-FUZZY-001.md)
- [ABLATION-FORMAL-C2-REPLAY-001](reports/ABLATION-FORMAL-C2-REPLAY-001.md)
- [ABLATION-FORMAL-C2-SPOOF-001](reports/ABLATION-FORMAL-C2-SPOOF-001.md)
- [ABLATION-FORMAL-C3-FLOOD-001](reports/ABLATION-FORMAL-C3-FLOOD-001.md)
- [ABLATION-FORMAL-C3-FLOOD-002](reports/ABLATION-FORMAL-C3-FLOOD-002.md)
- [ABLATION-FORMAL-C3-FLOOD-003](reports/ABLATION-FORMAL-C3-FLOOD-003.md)
- [ABLATION-FORMAL-C3-FUZZY-001](reports/ABLATION-FORMAL-C3-FUZZY-001.md)
- [ABLATION-FORMAL-C3-REPLAY-001](reports/ABLATION-FORMAL-C3-REPLAY-001.md)
- [ABLATION-FORMAL-C3-SPOOF-001](reports/ABLATION-FORMAL-C3-SPOOF-001.md)
- [COLLECTION-HISTORY](reports/COLLECTION-HISTORY.md)
- [CONTINUE-INVALID-V6](reports/CONTINUE-INVALID-V6.md)
- [TX-RETRY-V5](reports/TX-RETRY-V5.md)

- [최종 실험 결과 보고서](../최종실험_결과_보고서.md): 12조건 비교·최초 시도 분모·계측 한계·논문 활용 안내.
