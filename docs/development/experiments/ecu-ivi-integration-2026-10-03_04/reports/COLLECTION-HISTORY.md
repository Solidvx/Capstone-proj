# 수집 당시 인덱스 이력

이하 내용은 감사 보완 전 인덱스의 원문이다. 미시작·미완료·최신 표기는 당시 시점이며 현재 상태는 CHG-014와 상위 README를 따른다.

# ECU–IVI 실장비 시험 결과 보존 기록

기록일: 2026-10-04. 정상 인증 시험부터 공식 성능 시험까지 수령한 증거를 보존한다. **최신 PERF-FORMAL-002는 1000표본의 Qt 표시 경로 지연과 BMS 주기 기준을 충족했고 양측 CAN 불일치·인증 거부가 없다. 이전 001의 보류 기록은 보존한다. 물리 픽셀 표시 시각을 측정한 것은 아니다.**


## 최신 전체 위치와 시행착오 요약

공식 물리 Ablation 1,200회는 아직 시작하지 않았다. Config 1/2/3 기능 pilot, 정상 IF 독립 평가, 고부하 조건 조정을 수행했다. 최신 부하 조건은 ECU SPI2MHz·IVI SPI1MHz·CAN500kbps·ECU qlen10·요청2800fps이며 Config2 1회에서60%·송신오류0을 확인했다. 이 결과를 모든 구성·반복의 통과로 일반화하지 않는다.

| 작업/시행착오 | 결과 및 해결 범위 | 근거 |
|---|---|---|
| IF 정상 학습/보정/평가 분리 | 규칙0/298·규칙+IF1/298. constant 정상 자료 범위 | [정상 IF](../reports/NORMAL-IF-20261004-064946_결과.md) |
| Config3 수신 처리 시각 오탐 | 커널 timestamp v4 적용 후4종완료, baseline 주기오탐 미재발. IF 이상1건은 남음 | [이전 중단](../reports/PHYSICAL-PILOT-IF-001_결과.md), [수정 후](../reports/PHYSICAL-PILOT-IF-002_결과.md) |
| 고부하 송신 오류 판정 누락 | v3에서TX_ERRORS를INVALID 처리, errno보존 | [초기 부하](../reports/LOAD-CHECK-V2-001_결과.md), [v3진단](../reports/LOAD-DIAG-V3-001_결과.md) |
| 큐10→100 확대 | ENOBUFS1796·45%, 미해결. 큐10복구를 사용자 출력으로 확인 | [큐 비교](../reports/LOAD-QUEUE-001_결과.md) |
| SPI1→2MHz, 요청3000fps | 62%이나ENOBUFS12, INVALID유지 | [SPI2MHz 001](../reports/LOAD-SPI2M-001_결과.md) |
| 요청2600fps | 오류0이나48%로부하기준미달 | [002](../reports/LOAD-SPI2M-002_결과.md) |
| 요청2800fps | 60%·송신오류0·정상30/30·양측통계일치, 이번부하조건충족 | [003](../reports/LOAD-SPI2M-003_결과.md) |

보존 구조: raw/는 수령 원본과 시험별 추출 파일, analysis/는 기계 집계, reports/는 방법·결과·제한, tools/는 재사용 분석 도구, inventory.json은 파일별 출처·크기·SHA256이다. 실패/중단/INVALID 자료도 삭제하지 않는다. raw/는 Git 제외 대상으로 로컬 보존이며 원격 백업 완료를 의미하지 않는다. 대화에서만 제공된 출력·화면 관측은 해당 보고서의 사용자 제공 근거로 구분하며 미수령 원본을 보유했다고 주장하지 않는다.

## 시험별 결과

| 시험 | 확인한 결과 | 판정과 남은 사항 | 상세 기록 |
|---|---|---|---|
| TEAM-NORMAL-001 | 인증 성공 225건, 화면 반영 확인. IVI CAN·앱 기록 450프레임 일치 | 정상 경로 동작 확인. 사용자가 조기 종료했으므로 30초 완료 시험으로 간주하지 않음 | [보고서](../reports/TEAM-NORMAL-001_인수분석.md) |
| PERF-PRE-001 | 완료 300표본, 평균 8.943716ms, 최대 66.210985ms | 별도 MAC_FAIL 1건. 원인 미확정 | [보고서](../reports/PERF-PRE-001_결과.md) |
| PERF-PRE-002 | 완료 300표본, 평균 9.386113ms, 최대 86.162014ms. 관측 인증 거부 없음 | 예비 계측 확인. IVI CAN 파일은 ECU 파일의 앞 844프레임과 일치하지만 전체 수집 구간은 다름. 이전 이상 원인이 해결된 것은 아님 | [보고서](../reports/PERF-PRE-002_결과.md) |
| PERF-FORMAL-001 | 완료 1,000표본, 평균 9.158719ms, 최대 65.740385ms. 미렌더·판정 불가 각각 0 | **전체 인수 보류.** 양측 2,998프레임 중 인증 payload 4개 불일치. MAC_FAIL 1건·COUNTER_BACKWARD 3건 | [보고서](../reports/PERF-FORMAL-001_결과.md) |

| SPI-CHECK-001 / DIAG-SPI1M-001 | 2398프레임 일치, 인증 1199건, 오류 증가 0 | SPI 변경·재부팅 후 오류 미재현 1회; 원인 단정 안 함 | [보고서](../reports/SPI-CHECK-001_결과.md) |
| IT002-KNOB-001 | 2118프레임 일치, BMS 1057건·전이 2건 인증, 간격 32.626초 | 노브 기능 확인; 화면은 사용자 관측, 파일 미첨부. 프로파일 별도 | [보고서](../reports/IT002-KNOB-001_결과.md) |
| PERF-FORMAL-002 | 유효 1000표본, 평균 6.473276ms·최대 65.029527ms, 오류 0 | Qt 표시 경로 지연·관측 주기 기준 충족 | [보고서](../reports/PERF-FORMAL-002_결과.md) |
| VCAN-PILOT-001 | 세 구성 12시행 VALID, 실행 COMPLETE | 실행 경로 확인; replay 귀속 지표 검토, IF·물리 미완료 | [보고서](../reports/VCAN-PILOT-001_결과.md) |

지연은 인증 성공 표본의 T1→T4이며 T4는 Qt `frameSwapped` 신호다. 물리 디스플레이 픽셀 표시 지연이 아니다. 합격 기준 원본은 [TEST_PLAN](../../../../TEST_PLAN.md), 구현·잔여 작업 기록은 [CHG-014](../../../../aidlc/changes/CHG-014/aidlc-state.md)다. 노브 경로와 프로파일 경로, vcan과 물리 Ablation, 규칙 IDS와 IF의 완료 범위를 구분한다.

## 보관 구조와 사용법

| 위치 | 내용 | 보관 정책 |
|---|---|---|
| `reports/` | 시험별 상세 판정, IVI 004 인수 확인, 기존 IF 진단 | Git에 포함할 수 있는 보고서 |
| `analysis/` | 기존 분석 JSON, 이상 프레임 발췌 | Git에 포함할 수 있는 분석 증거 |
| `tools/` | 이번 분석에 사용한 도구와 회귀 시험 스냅샷 | 분석 재현용. 제품 코드 변경 아님 |
| `raw/received/` | 팀원이 전달한 원본 폴더·압축파일·manifest | 원본 바이트 유지, 로컬 보존·Git 제외 |
| `raw/PERF-*/ivi/` | 전달 압축파일에서 이미 추출한 IVI 기록 | 로컬 보존·Git 제외 |
| `raw/PERF-*/ecu/` | 수령한 ECU 로그·종료코드·CAN 전후 통계 | 로컬 보존·Git 제외 |
| [inventory.json](../inventory.json) | 원래 경로·보존 경로·크기·SHA256 | 원본과 보존본의 추적·무결성 확인 |

기존 `tmp/` 및 `IVI측에서받아온파일들/`은 삭제하거나 이동하지 않았다. 최초 66개에서 후속 자료를 추가하여 현재 inventory에 197개 파일을 기록했으며 보고서 링크와 보존본 테스트의 입력 경로만 정정했다. inventory의 `sha256`은 원본, `preserved_sha256`은 정정 후 보존본 기준이다. 저장소 전체의 과거 임시 파일을 무차별 복사한 것은 아니다.

**`raw/`는 tmp 밖에 있지만 Git 백업 대상은 아니다.** 다른 PC로 넘기거나 장기 백업할 때는 이 디렉터리 전체를 별도로 복사해야 한다. Git만 clone하면 원본 로그는 복구되지 않는다. 아직 커밋·원격 업로드하지 않았다.

ECU의 최초 정상 시험과 예비 001은 이 보존본에 독립 ECU 원본 파일이 없다. 대화에서 받은 출력과 원본 파일을 구분한다. IVI 공식 001의 사전 CAN 통계도 미수집 상태이며 사후 오류 12건을 이번 시험 증가량이라고 해석하지 않는다.

## 분석 재현

저장소 루트에서 Python 표준 라이브러리만으로 실행한다. 출력은 기존 증거를 덮어쓰지 않도록 새 파일을 지정한다.

```text
python docs/development/experiments/ecu-ivi-integration-2026-10-03_04/tools/analyze_ivi004.py docs/development/experiments/ecu-ivi-integration-2026-10-03_04/raw/PERF-FORMAL-001/ivi/perf-formal-001/latency.csv --expected 1000 --out tmp/perf-formal-001-recheck.json
python docs/development/experiments/ecu-ivi-integration-2026-10-03_04/tools/test_analyze_ivi004.py
python docs/development/experiments/ecu-ivi-integration-2026-10-03_04/tools/test_compare_ivi_can.py
```

CSV 분석만으로 전체 시험 PASS를 판정하지 않는다. receiver·양측 CAN·수집 구간·오류 기록을 함께 검토한다. 기존 IF 진단은 합성 실험이며 사용자 요청대로 개선 작업을 보류한다. 이전 합성 Ablation 결과는 기존 [CHG-013 증거](../../../../aidlc/changes/CHG-013/evidence.md)를 참조한다.

## 환경·실행 기록과 진단

- [양측 커널·CAN·SPI 진단](../reports/PERF-FORMAL-001_IVI진단.md): 이전 이상, 설정 비교, 원인 미확정 범위.
- [RPi 실행기 준비와 vcan 실행 방법](../reports/ABLATION_실행환경과절차.md): 전달 버전, 빌드·시험, 의존성 및 pilot 명령.
- [물리 pilot 준비](../reports/PHYSICAL-PILOT_준비.md): Config 1 실행 스크립트, IVI 수령 자료, 버스 부하·IF 범위 확인.
- 시험별 보고서의 초기 대기 문구는 당시 이력이며, 이후 수령 절의 최종 판정을 따른다.

## 현재 위치와 다음 작업

최신 물리 결과: [정상 IF 평가](../reports/NORMAL-IF-20261004-064946_결과.md)는 규칙 0/298, 규칙+IF 1/298창 오탐으로 이번 운전 조건에서 기준 충족. 다음은 물리 부하 확인 및 Config 3 규칙+IF pilot이다. 아래 IF 평가 대기 문구보다 이 결과를 우선한다.

최신 소프트웨어 후속: [pilot 보완 v2](../reports/PILOT_보완_v2.md)의 송신률·IF 변경과 Python 59개 회귀를 완료했다. IF 개선은 사용자 요청으로 재개했고 독립 합성 3세트 모두 5% 이하다. 물리 부하와 IF 오탐 인수는 ECU에서 확인해야 하며 본 실험은 아직 시작하지 않았다. 아래 보류·대기 문구는 이전 이력이다.

최신: Config 2 IVI 대조까지 완료했다. ECU 원본 7,483프레임은 IVI 앞부분과 일치하며 IVI 추가 정상 한 쌍까지 총 7,485프레임이다. receiver 4,427건도 필터 적용 후 일치한다. 과거 counter 거부 1,177건, spoofing MAC_FAIL 1건, 동일 payload/정상 인증 결합 게시 1건을 확인했다. flooding 부하 최대 표시 13%로 TC-SEC-005-d의 50% 기준 미충족. 아래 대기 문구는 이전 수령 이력이며 현재 대기는 Config 3 및 공식 부하 인수·본 실험이다.

[물리 Config 2 ECU 결과](../reports/PHYSICAL-PILOT-001-C2_결과.md)도 수령·검증했다. 4시행 VALID, COMPLETE·종료코드 0. replay 동일 payload/정상 인증 결합 게시 1건을 원시 로그로 확인했으며 IVI 제품 결과와 점유율 대조는 대기다. 원장 최신 파일 수는 238개다. 아래 Config 1의 223개는 해당 수령 시점 수량이다.

[물리 Config 1 양측 결과](../reports/PHYSICAL-PILOT-001-C1_결과.md) 대조를 완료했다. 네 시행 VALID·COMPLETE, 양측 CAN 6,417프레임 일치, IVI replay 1,545건·spoofing 1,539건 게시를 확인했다. 수신 필터를 적용하면 receiver 3,364건도 모두 일치한다. 부하 계측은 미수집이다. inventory는 후속 자료 포함 223개다.

정상 통신·노브 기능·Qt 성능 확인 및 vcan 실행 경로 검증을 마쳤다. 물리 Ablation 본 실험은 아직 시작하지 않았다.

1. Config 2 replay의 동일 payload/정상 인증 결합을 과거 인증 재수용과 구분하는 판정·보고 기준을 검토한다.
2. 물리 pilot의 IVI OFF/ON 수신·관측, 공격 강도 및 버스 부하 계측을 준비한다. Config 3의 최종 IDS 구성도 확정한다. 규칙 pilot을 IF 완료로 간주하지 않는다.
3. 물리 pilot 인수 후 4공격×3구성×유효100회 본 실험을 수행한다.
4. IF 오탐 개선은 사용자 요청대로 보류다. 프로파일 경로·MAC fixture·ADC 끝점 측정 등 전체 계획 잔여 항목도 별도로 남아 있다.

- [PHYSICAL-PILOT-IF-002 ECU 결과 및 IVI 대조 대기](../reports/PHYSICAL-PILOT-IF-002_결과.md)

- [LOAD-QUEUE-001 큐 변경 비교 ECU 결과](../reports/LOAD-QUEUE-001_결과.md)

- [LOAD-SPI2M-001 ECU 분석](../reports/LOAD-SPI2M-001_결과.md)

- [LOAD-SPI2M-002 ECU 검증 및 IVI 대조 대기](../reports/LOAD-SPI2M-002_결과.md)

- [LOAD-SPI2M-003 ECU 검증 및 IVI 대조 대기](../reports/LOAD-SPI2M-003_결과.md)
