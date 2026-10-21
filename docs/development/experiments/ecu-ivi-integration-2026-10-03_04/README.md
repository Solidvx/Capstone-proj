# ECU–IVI 통합·예비·진단 증거

진행 상태 원본: [CHG-014](../../../aidlc/changes/CHG-014/aidlc-state.md). 이 인덱스는 결과 위치를 안내하며 시험 PASS를 중복 선언하지 않는다.

- `raw/`: 수령 압축파일·추출 원본. 실패/중단/INVALID도 보존.
- `inventory.json`: 원본 출처·보존 SHA256.
- `analysis/`: 당시 케이스별 분석 결과.
- `reports/`: 해석·예외·미수집 자료.
- `tools/`: 당시 분석 도구.

원본은 Git 제외 로컬 보존이다. 커밋·원격 백업 완료를 뜻하지 않는다. 대화만으로 제공된 화면 관측은 파일 증거와 구분한다.

본 실험은 [공식 Ablation 증거](../physical-ablation-formal-2026-10-04/README.md)에 분리되어 있다.

## 케이스별 보고서

- [ABLATION_실행환경과절차](reports/ABLATION_실행환경과절차.md)
- [chg014-if-diagnosis](reports/chg014-if-diagnosis.md)
- [COLLECTION-HISTORY](reports/COLLECTION-HISTORY.md)
- [IT002-KNOB-001_결과](reports/IT002-KNOB-001_결과.md)
- [IVI-004_인수확인](reports/IVI-004_인수확인.md)
- [LOAD-CHECK-V2-001_결과](reports/LOAD-CHECK-V2-001_결과.md)
- [LOAD-DIAG-V3-001_결과](reports/LOAD-DIAG-V3-001_결과.md)
- [LOAD-QUEUE-001_결과](reports/LOAD-QUEUE-001_결과.md)
- [LOAD-SPI2M-001_결과](reports/LOAD-SPI2M-001_결과.md)
- [LOAD-SPI2M-002_결과](reports/LOAD-SPI2M-002_결과.md)
- [LOAD-SPI2M-003_결과](reports/LOAD-SPI2M-003_결과.md)
- [LOAD_진단_v3](reports/LOAD_진단_v3.md)
- [NORMAL-IF-20261004-064946_결과](reports/NORMAL-IF-20261004-064946_결과.md)
- [PERF-FORMAL-001_IVI진단](reports/PERF-FORMAL-001_IVI진단.md)
- [PERF-FORMAL-001_결과](reports/PERF-FORMAL-001_결과.md)
- [PERF-FORMAL-002_결과](reports/PERF-FORMAL-002_결과.md)
- [PERF-PRE-001_결과](reports/PERF-PRE-001_결과.md)
- [PERF-PRE-002_결과](reports/PERF-PRE-002_결과.md)
- [PHYSICAL-PILOT-001-C1_결과](reports/PHYSICAL-PILOT-001-C1_결과.md)
- [PHYSICAL-PILOT-001-C2_결과](reports/PHYSICAL-PILOT-001-C2_결과.md)
- [PHYSICAL-PILOT-IF-001_결과](reports/PHYSICAL-PILOT-IF-001_결과.md)
- [PHYSICAL-PILOT-IF-002_결과](reports/PHYSICAL-PILOT-IF-002_결과.md)
- [PHYSICAL-PILOT_준비](reports/PHYSICAL-PILOT_준비.md)
- [PILOT_보완_v2](reports/PILOT_보완_v2.md)
- [SPI-CHECK-001_결과](reports/SPI-CHECK-001_결과.md)
- [TEAM-NORMAL-001_인수분석](reports/TEAM-NORMAL-001_인수분석.md)
- [VCAN-PILOT-001_결과](reports/VCAN-PILOT-001_결과.md)
- [VCAN-READINESS-V2-001_결과](reports/VCAN-READINESS-V2-001_결과.md)

- [최종 실험 결과 보고서](../최종실험_결과_보고서.md): 정상 통합·성능·본 실험의 종합 해석과 논문 활용 안내.
