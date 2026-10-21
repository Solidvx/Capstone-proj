# 실험 증거 감사 보완 결과

대상: [감사 스냅샷](README.md). 사용자 요청에 따라 기존 원본과 INVALID를 보존하고 분석·문서·재현·복구 절차를 보완했다. 추가 하드웨어 시험이나 ICD 변경은 하지 않았다.

## 조치

| 감사 항목 | 조치 | 결과 위치 |
|---|---|---|
| 오래된 현재 상태 | CHG-014를 현재 상태 원본으로 재작성, 누적 상태는 state-history로 분리 | [현재 상태](../../../aidlc/changes/CHG-014/aidlc-state.md) |
| 실험 인덱스 충돌 | 두 README를 탐색 인덱스로 정리, 당시 인덱스는 COLLECTION-HISTORY로 보존 | [통합](../../experiments/ecu-ivi-integration-2026-10-03_04/README.md), [본 실험](../../experiments/physical-ablation-formal-2026-10-04/README.md) |
| 100유효/100시도 정책 차이 | DEV-EXP-001 편차·최초/전체/재시도 분모를 TEST_PLAN 및 운영 절차에 명시 | [방법·TC 추적](../../experiments/physical-ablation-formal-2026-10-04/METHODS-AND-TRACEABILITY.md) |
| 재개 집계 오류 | start_trial 범위 검증, 이전 run 연결·설정·분기·누락·중복 검증 추가 | security/experiments/summarize_live.py |
| 최종 비교 묶음 부재 | 원본 재대조 도구와 12조건/16실행 결과·해시 출처·LaTeX 표 생성 | [재현](../../experiments/physical-ablation-formal-2026-10-04/REPRODUCE.md) |
| 구버전 지연 왜곡 | C3 flooding 001/002 지연·전달률 채택 제외, v8 23회 별도 집계 | publication-policy.json 및 run별 summary |
| 임시 분석기만 존재 | 과거 분석기 38개 바이트/해시 보존, 재실행 위험 표기 | tools/legacy-analysis |
| 연관 문서 drift | TEST_PLAN·SRS·양측 SDD·TARA·ECU/IVI 계획·플레이북·문서/경로 매핑 연결 | 각 문서의 2026-10-04 근거 링크 |
| 장기 보존 | 로컬 복구 ZIP 생성 도구, 전 멤버 해시/구조 검증 및 별도 장치 복사 후 검증 절차 | [백업](../../experiments/physical-ablation-formal-2026-10-04/BACKUP.md) |

## 검증

검증 명령과 최종 결과는 이 폴더의 [validation.json](validation.json)에 기록한다. ZIP 전 멤버 검증 영수증은 생성 후 `backup-receipt.json`으로 별도 보존한다. 분석기는 표준 라이브러리만 사용하며 실제 키를 요구하지 않는다. Linux 회귀는 기존 WSL Python 환경으로 실행했다. 문서 상대 링크·원장 건수·보존 해시·출력 해시·분모와 버전 제외 정책을 검사한다.

`publication`의 최초 시도 표는 1,200번호/1,196 VALID/4 INVALID, 전체 시도 표는 1,201/1,197/4다. 이는 수집/실행기 판정이며 전체 제품 TC 합격 선언이 아니다. 이전 원본 수치·판정을 바꾸지 않았다.

## 근거상 남는 한계

- 이미 미수집인 화면/정확한 프로세스 시각과 구버전 커널 수신 시각은 문서 수정으로 복원할 수 없다. 해당 주장은 제한/미측정으로 명시했다.
- 고정된 IDS 탐지와 유형 분류는 다르며, 비인증 0x200의 주입 경보와 실제 IDS 송신을 분리한다. IF 추가 기여를 임의 주장하지 않는다.
- 원래 유효100회 기준의 미충족과 전용 IT-004 물리 인수 잔여는 편차/잔여로 유지했다. 사용자 요청 없이 재시험하지 않았다.
- 외장/공유 저장 위치는 미제공이다. 로컬 ZIP 검증과 별도 장치 백업 성공은 구분한다. Git commit/push는 실행하지 않았다.

코드·문서·분석으로 보완 가능한 항목의 완료와 새 측정/외부 저장장치가 필요한 항목을 구분한 기록이다.
