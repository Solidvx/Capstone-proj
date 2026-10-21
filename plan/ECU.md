# ECU 실행 계획 — Node A

> 2026-10-04 실장비 증거 연결: [실행 상태·시험 추적](../docs/aidlc/changes/CHG-014/aidlc-state.md). 계획/설계의 존재와 시험 인수를 구분하며 INVALID·버전 편차·미수집 화면·비인증 0x200 경보의 제한을 적용한다. 아래 요구/계약 목표를 실험 결과에 맞춰 낮추지 않는다.


> **2026-09-09 보안 후속 계획:** [공동 적용 규약](detail/common/00_협업_규약.md#security-adoption)에 따라 기존 과제에 [M3 입력·보안 시작](detail/ecu/M3_EKF_Failsafe_SecOC.md#security-adoption), [M4 IDS·공격·이벤트](detail/ecu/M4_IDS_공격_물리통합.md#security-adoption), [M5 평가](detail/ecu/M5_Ablation.md#security-adoption), [M6 추적성](detail/ecu/M6_문서_품질.md#security-adoption)의 추가 조건을 적용한다. 단계 순서·공식 계약은 유지하며 구현 완료를 뜻하지 않는다.

> **담당**: ECU / BSW / BMS / SecOC / IDS · **플랫폼**: RPi4 Ubuntu 22.04, C++17, Python
> **짝 계획**: [IVI.md](IVI.md) · **공동 절차**: [detail/common/](detail/common/)
> **갱신 기준일**: 2026-09-09 (문서 안내 정정; 구현 스냅샷 날짜와 별개)

---


<a id="security-integration"></a>
## 보안 상세 계획 병합 적용 — 2026-09-09

기존 단계별 과제에 보안 상세 계획의 최신 수행·실패 대응·인수 조건을 반영했다. [M1](detail/ecu/M1_환경구축_ICD확정.md#security-integration) · [M3](detail/ecu/M3_EKF_Failsafe_SecOC.md#security-integration) · [M4](detail/ecu/M4_IDS_공격_물리통합.md#security-integration) · [M5](detail/ecu/M5_Ablation.md#security-integration) · [M6](detail/ecu/M6_문서_품질.md#security-integration) · [M7](detail/ecu/M7_최종검증_재현성.md#security-integration)의 병합 절을 기존 본문과 함께 적용한다. [공동 인계](detail/common/01_연계_의존성.md#security-integration)와 [공동 시험](detail/common/02_통합시험.md#security-integration)이 양측 제공물·동일 run 증거를 관리한다.

M1 환경 확인→M3/M4 구현→M5 계측→M6 검토→M7 재현→기존 M8 제출 순서를 유지한다. 새 단계·중복 과제를 추가하지 않는다. 상세 규약은 설계 참조이며 실제 계약 채택·제품 실행 상태는 각 과제의 증거로 판단한다. 문서 병합 완료만으로 실행 체크박스를 완료하지 않는다.


## 0. 이 문서 사용법

IVI의 현행 플랫폼·실행 순서는 [Qt Plan B](IVI_PLAN_B_전환계획.md)를 따른다. 개발 착수 판정은 [종합 검토](../docs/development/reviews/문서_종합정합성_검토.md#2026-09-09-개발-기준본-진입점-정정)를 따른다. 요구·설계·역할별 절차는 개발 방향으로 사용할 수 있지만, G1의 세션 상세 전환을 포함한 미결 항목을 전체 확정으로 해석하지 않는다. [이전 계획 인수 보고서](../docs/development/reviews/계획_검토.md#part2-verdict)는 당시 검토 기록이다.

공통 목표는 가상 배터리 기반 Node A BMS·Fail-safe → SecOC 적용 CAN → Node B HAL·Service·대시보드 전달과 Node A IDS 탐지·경보를 end-to-end로 검증하는 것이다. 실제 배터리 제어·표준 VHAL·외부 안전 인증을 필수 범위로 추가하지 않는다.

**개발 착수: 승인된 범위에서 가능. 현행 SecOC 문구 충돌: 승인 정정 완료. 세션 상세 전환: 별도 관문.** [공동 규약](detail/common/00_협업_규약.md)과 [확인사항](../docs/development/governance/의사결정_기록.md#part2-confirmed)의 기존 결정을 적용하고, 종합 검토의 G/E별 차단 범위와 종료 증거를 확인한다. 제품 시험·장비 인수는 후속 실행 과제이며 모든 시험 완료를 문서 계획 완성의 선행조건으로 삼지 않는다.

이 문서는 **무엇을·왜·언제·무엇으로 판정하는가**를 담는다. **어떻게 하는가**(명령·코드·기대 출력)는 [detail/ecu/](detail/ecu/)의 단계별 문서에 있다.

1. §2에서 현재 구현 상태를 확인한다. 계획서의 "작성한다"를 **이미 있는 파일에 대해 다시 하지 않는다**.
2. §4 표에서 해당 단계 행을 찾아 상세 문서로 들어간다.
3. 상세 문서의 6블록(목적 / 선행조건·현재상태 / 수행 절차 / 검증 / 실패 대응 / 완료 체크)을 순서대로 수행한다.
4. 공동 작업(브랜치·PR·마일스톤·통합 시험·발표)은 [detail/common/](detail/common/)을 따른다.

**원천 우선순위와 검증 명령은 [AGENTS.md](../AGENTS.md)의 Source of Truth·Verification Baseline을 따른다.** 이 문서에 복제하지 않는다.
계약 값(CAN ID·레이아웃·스케일·HMAC 입력)은 요약본을 만들지 않고 [docs/ICD.md](../docs/ICD.md)를 직접 읽는다.

> 이 계획은 진행 기준이며 **구현 완료의 증거가 아니다.** 파일이 있다는 이유로 시험 통과를 표시하지 않는다.

---

**확정 결정과 후속 작업:** [공동 규약](detail/common/00_협업_규약.md)의 Q/R 정책을 따른다. [확인사항](../docs/development/governance/의사결정_기록.md#part2-confirmed)은 사용자 결정·미결정의 기록이며, [요구·원천 매핑](detail/common/01_연계_의존성.md) §10~11은 담당·시험·Plan 비교 위치를 연결한다. 개발자는 승인된 과제의 구현·시험을 진행하고 미승인 계약 적용은 해당 관문에서 멈춘다. 2026-09-08 사용자 명시 지시에 따른 Plan 통합과 재검사를 반영했다. 과제 ID별 주관 위치는 공동 규약의 Plan 병합 기록을 따른다. 개발 재개 순서는 종합 검토의 2026-09-23 정정된 「개발자가 다음에 수행할 순서」와 IVI Qt Plan B를 따른다. 공동 연계의 과거 문서 검토 범위를 제품 개발 금지로 해석하지 않는다.

## 1. 최종 목표와 완료 판정

Node A를 실제 차량 ECU처럼 동작시키고, Node B IVI와 CAN 버스로 end-to-end 통합한다.

**시험 범위 (사용자 확인):** 주 계획은 가변저항으로 가상 배터리를 모사하는 방식이다. 모델의 직렬수·용량은 가상 설정이며 실제 배터리 팩 사양·정확도 검증으로 주장하지 않는다. 실제 보조배터리 시험은 시간적 여유가 있을 때 목적·계측 방법을 별도 확인하는 선택 확장이다. 장비 상세와 후속 확인은 [확인사항](../docs/development/governance/의사결정_기록.md#part2-confirmed)에 기록한다.

- [ ] RPi4 Ubuntu 22.04에서 SocketCAN 기반 ECU 프로세스를 실행한다
- [ ] `0x100` BMS_Status를 100ms 주기로 송신한다
- [ ] `0x101` BMS_FailSafe를 상태 전이 시 즉시 송신한다
- [ ] `0x102`, `0x103` SecOC 인증 프레임을 원본 직후 송신한다
- [ ] IDS가 Fuzzy / Replay / Spoofing / Flooding을 탐지하고 `0x200`을 송신한다
- [ ] Ablation Study 4종 공격 × 3 Config × 100회 = 1,200 시행을 수행한다
- [ ] `docs/SDD-ECU.md`, `docs/TARA.md`, `docs/TEST_PLAN.md`, `docs/ADR.md`에 구현과 실험 결과를 반영한다
- [ ] 데모, 발표 슬라이드, 보고서, Release 증적을 완성한다

### 완료 판정 기준

| 영역 | 기준 |
|---|---|
| CAN | `0x100` 주기 100ms ±10ms, `0x101` 이벤트 즉시 송신 |
| BMS | TC-BMS-001~007 통과. EKF SOC 오차 핵심 시험 ≤0.5%, 프로젝트 최소 기준 ≤3% |
| Fail-safe | 상태 전이 Branch Coverage 100% |
| SecOC | Python·C++ 동일 MAC, 변조·Replay 차단율 100% |
| IDS | 공격별 탐지율 ≥90%, 정상 오탐율 ≤5%, 탐지 응답 ≤3초 |
| 통합 | IT-001~005 전부 Pass, TC-INT-001~004 결과 기록 |
| 실험 | 실제 CAN 4공격×3방어 구성×유효 100시행, 전체 시도 원장 및 정상 평가; 상세 인수는 M5 |
| 문서 | SDD-ECU / TARA / TEST_PLAN / ADR / 발표 자료 최신 |
| 릴리즈 | `v0.1.0`~`v1.0.0` 태그와 단계별 Release 존재 |

> **수치 규칙**: 위 값은 **목표**다. 문서·발표에는 목표값과 실측값을 구분해 적고, 실행하지 않은 항목을 통과로 적지 않는다.

---

## 2. 현재 구현 상태 스냅샷

**확인 기준일 2026-09-06.** 실제 파일을 읽어 작성했다. 소스 존재와 시험 통과는 다르다.

| 영역 | 상태 | 근거 |
|---|---|---|
| C++ BSW·App 모듈 | **구현됨** | `can_cdd`, `can_publisher`, `mock_can_driver`, `secoc_module`, `watchdog_manager`, `ekf_soc_estimator`, `failsafe_sm`, `sensor_simulator`, `soh_estimator` |
| 100ms 주기 ECU 루프 | **구현됨** | `adaptive_ecu/main.cpp`. `sleep_until` 기반, SecOC 동반 송신 포함 |
| C++ 단위 시험 | **13종 등록됨** | CTest: `test_ads1115_conversion`, `test_sensor_quality`, `test_adc_acquisition_gate`, `test_ads1115_registers`, `test_publisher`, `test_mock_can_driver`, `test_sensor_simulator`, `test_can_publisher`, `test_ekf_soc`, `test_soh_estimator`, `test_failsafe_sm`, `test_watchdog_manager`, `test_secoc` |
| SecOC | **Python·C++ 양쪽 구현** | 입력 14B, 절단 MAC 4B, 카운터 윈도우 100, 상수시간 비교 |
| IDS 오프라인 평가 | **구현됨** | `traffic_gen`(공격 5종), `feature_extractor`(7차원), `rule_baseline`, `spec_detector`, `if_detector`, `run_eval` |
| IDS 실시간 경로 | **미구현** | 수집·학습·`0x200` 송신 스크립트 없음 |
| Ablation 하네스 | **미구현** | Config 1/2/3 비교 러너 없음 |
| 그래프·재현성 도구 | **미구현** | plot / verify 스크립트 없음 |
| RPi4·MCP2515·물리 CAN | **보유 사양·배선 확인, 동작 미검증** | RPi4 8GB 2대, MCP2515-I/SO+TJA1050 8MHz 모듈 2개, 레벨 컨버터 5개와 기존 배선표 확인. `can0`·양방향 CAN은 실장비에서 검증 필요 |

### 문서·구현 차이와 해소 상태

| # | 내용 | 처리 |
|---|---|---|
| D1 | IDS 특징 벡터의 문서·구현 불일치 해소: 7개 특징 이름·순서 일치 확인(2026-09-10) | [M6](detail/ecu/M6_문서_품질.md)에서 특징·전처리·threshold와 실행 증거를 대조한다. 정적 일치는 IDS 실행 인수 완료가 아님 |
| D2 | SDD의 EKF가 3차 OCV·50Ah 전제, 제품은 3차 OCV·50Ah로 수정됐으나 실행 미검증 | SOC-2=A 적용 소스의 C++ 시험 실행 ([M3](detail/ecu/M3_EKF_Failsafe_SecOC.md)); 현 구현과 목표를 구분 |
| D3 | `SensorSimulator` 모드가 문서 4개, 구현 5개(`POTENTIOMETER` 추가) | **해소(2026-10-03, [CHG-011](../docs/aidlc/changes/CHG-011/aidlc-state.md))**: POTENTIOMETER와 setter 3종을 제거하고 시험을 ADS1115 모드·모드 이름 검증으로 이관했다. 미지원 모드는 종료 코드 2. 이전 계획: I-5=B에 따라 [M3 §3.11.1](detail/ecu/M3_EKF_Failsafe_SecOC.md)에서 사용처·필요 시험 이관 후 추가 모드를 제거하고 소스·CLI·시험을 공식 4모드에 맞춘다. [M6](detail/ecu/M6_문서_품질.md)에서 정합성과 증거 확인; SDD를 5모드로 확대하지 않음 |
| D4 | TC-BSW-007(Watchdog 재시작 3회 연속 실패 → WARNING) 로직 없음 | 재시작·실패 집계·reason 0x07 구현 과제 ([M3](detail/ecu/M3_EKF_Failsafe_SecOC.md) 3.6) |
| D5 | Fail-safe에 CRITICAL → NORMAL 복귀 경로 없음 | SRS와 대조 후 결론 기록 ([M3](detail/ecu/M3_EKF_Failsafe_SecOC.md) 3.5) |
| D6 | TC-SEC-005-d의 과거 fps 기준은 버스 점유율 ≥50%로 정정 완료. 약 3,700fps는 특정 프레임 길이 가정의 계산값이며 보편적 물리 상한이 아님 | [M4](detail/ecu/M4_IDS_공격_물리통합.md) §3.4와 TEST_PLAN에 따라 실제 물리 CAN 캡처·계측으로 점유율을 인수한다. 합성/vcan은 사전 검증이며 실측 인수는 별도 |
| D7 | S-21 7조건 제품 시험은 추가됐으나 미실행. TC-BMS-001의 전체 인수도 미완료 | 기존 시험과 공식 TC 범위를 대조하고 C++17 환경에서 실행·증거 인수 ([M3](detail/ecu/M3_EKF_Failsafe_SecOC.md) 3.3) |

---

## 3. 지켜야 할 계약

값은 [docs/ICD.md](../docs/ICD.md)에서 직접 읽는다. 여기에는 **어느 절을 봐야 하는지만** 둔다.

| 대상 | 참조 |
|---|---|
| CAN ID 5종·방향·주기·DLC | ICD §1.1 |
| `0x100` BMS_Status 레이아웃 | ICD §1.2 |
| `0x101` BMS_FailSafe 레이아웃·Reason 코드 | ICD §1.3 |
| `0x102`/`0x103` SecOC 레이아웃·HMAC 입력·키 관리 | ICD §1.4 |
| `0x200` IDS_Alert 레이아웃 | ICD §1.5 |

**ICD를 바꿔야 한다고 판단되면 코드를 먼저 고치지 않는다.** 영향 범위(CAN ID·필드·HAL API·양 노드·SecOC·시험)를 제시하고 승인받은 뒤, ICD·SRS·양측 SDD·TEST_PLAN·구현·시험을 한 변경 단위로 갱신한다. 절차는 [detail/common/00_협업_규약.md](detail/common/00_협업_규약.md).

**보안 규칙**: SecOC 키·토큰·장비 주소를 코드·시험·문서·로그·커밋에 남기지 않는다. 시험에는 명시적 더미(`b'\x01' * 32`)를 쓴다.

---

## 4. 단계별 실행 과제

| 단계 | 주제 | 선행 | 핵심 산출물 | 연결 TC | 상세 |
|---|---|---|---|---|---|
| **M1** | 환경 구축·ICD 확정 | — | CAN 인터페이스, 빌드 환경, 인터페이스 헤더, ICD 합의 | TC-BSW 환경 sanity | [M1](detail/ecu/M1_환경구축_ICD확정.md) |
| **M2** | CAN CDD·Publisher·센서 | M1 | Mock/SocketCAN 교체 가능성, `0x100` 100ms 송신 | TC-BSW-001~005, TC-BSW-008-a~c / TC-BMS-007 | [M2](detail/ecu/M2_CAN_CDD_Publisher.md) |
| **M3** | EKF·Fail-safe·Watchdog·SecOC | M2 | SOC/SOH 추정, 4상태 FSM, HMAC 인증 | TC-BMS-001~006 / TC-BSW-006~007, TC-BSW-008-d / TC-SEC-001~004 | [M3](detail/ecu/M3_EKF_Failsafe_SecOC.md) |
| **M4** | IDS·공격·물리 통합 | M3 | 탐지 성능, `0x200` 송신, 물리 CAN 양방향 | TC-SEC-005~007 / TC-INT-001~004 | [M4](detail/ecu/M4_IDS_공격_물리통합.md) |
| **M5** | Ablation Study | M4 | 1,200 시행 결과, ROC, 확정 임계 | TC-EXP-001~005 | [M5](detail/ecu/M5_Ablation.md) |
| **M6** | 문서·그래프·품질 | M5 | 그래프 4종, SDD-ECU·TARA 최종화, Coverage | 전 TC 결과 기록 | [M6](detail/ecu/M6_문서_품질.md) |
| **M7** | 최종 검증·재현성 | M6 | 재현성 차이 ≤5%p, ICD 교차 검토, 성능 측정 | TC-PERF-001~003 | [M7](detail/ecu/M7_최종검증_재현성.md) |
| **M8** | 데모·발표·제출 | M7 | 데모 A/B, 슬라이드, 보고서, Release | — | [M8](detail/ecu/M8_데모_제출.md) |

명령·경로·셀프 QA 조회는 [ref_명령모음](detail/ecu/ref_명령모음.md).

> **일정 표기 규칙**: M1~M8 표는 **의존성 순서**를 나타내며 과거 절대 날짜를 적용하지 않는다. 사용자 확정 마감 2026-09-18과 D1~D10 배분은 공동 규약의 최신 일정 입력을 따른다. 원본 계획의 2026-06 ~ 2027-01 날짜는 [_archive/](_archive/)에 남아 있으며 현재 기준이 아니다.

---

## 5. 단계 게이트와 산출물

각 단계는 아래를 모두 만족해야 다음으로 넘어간다.

| 단계 | 태그 | 게이트 조건 |
|---|---|---|
| M1 | `v0.1.0` | CAN 송수신 성공, 빌드·시험 통과, ICD 5종 합의, SRS/ADR 관련 절 머지 |
| M2 | `v0.2.0` | TC-BSW-001~005 및 TC-BSW-008-a~c 통과(-d는 M3 실취득 인수), `0x100` 100ms ±10ms, IVI가 동일 payload 파싱 |
| M3 | `v0.3.0` | M3 상세 인수 조건·담당 공식 TC 적용, TC-BSW-008-d 실취득·품질 인수, Fail-safe 브랜치 100%, SecOC Python·C++ 동일 MAC, **IVI에 SecOC 벡터 인계** |
| M4 | `v0.4.0` | TC-SEC-005~007, IT-001~005 수행·기록, 물리 CAN 양방향, TARA 실측 반영 |
| M5 | `v0.5.0` | [M5 §4](detail/ecu/M5_Ablation.md)의 실제 CAN 유효 조합·전체 시도 원장, 공격별 탐지율·정상 FPR 인수. 임계 선정과 독립 평가 분리, 실제 비교를 수행한 ADR에만 증거 연결 |
| M6 | `v0.6.0` | 그래프 4종, SDD-ECU 최종화·D1~D7의 최신 해소/실행 인수 상태 대조, cppcheck 0건, Coverage ≥80% |
| M7 | `v0.7.0` | 재현성 차이 ≤5%p, ICD 불일치 0건, TC-PERF-001~003 측정, 재현 문서 |
| M8 | `v1.0.0` | 데모 A/B 재현, 발표·보고서 완성, Release 증적 첨부 |

태그·Milestone·Release 처리 절차는 [detail/common/00_협업_규약.md](detail/common/00_협업_규약.md).

---

## 6. IVI 인계 지점

ECU가 **제공**해야 상대가 움직일 수 있는 지점이다. 늦으면 곧바로 상대 일정이 밀린다. 전체 의존 관계와 지연 시나리오는 [detail/common/01_연계_의존성.md](detail/common/01_연계_의존성.md).

인계 시점·산출물·제공자·수신자는 [공동 인계 정본 §2](detail/common/01_연계_의존성.md#2-인계-지점-전체-테이블)에서 한 번만 관리한다. 이곳에 별도 축약 표를 복제하지 않는다. M3 이벤트 포맷 제공과 M4 실제 전이/경보 통합, M5 임계 변경 사전 통지와 측정 시간대 분리, M7 최종 빌드/데이터·재현성·안정성, M8 스크립트/실행/영상 인수를 각각 구분한다.

ECU 담당은 계약·더미 벡터·송신/공격 도구·검증된 빌드와 재현 자료를 제공하고 IVI 파서/검증·UI·측정 결과를 확인한다. 파일 존재만으로 인수를 닫지 않으며 수신자가 실행 환경·공식 TC·hash·미통과 조건을 확인한다. SecOC 벡터가 없으면 Mock의 독립 작업은 가능하되 인증 통합을 완료 처리하지 않는다.

---

## 7. 위험과 우회

| 위험 | 즉시 조치 | 최종 조치 |
|---|---|---|
| MCP2515 인식 실패 | `vcan0`으로 개발 지속 | 배선·oscillator·INT·종단저항 점검. M4 물리 통합 전까지 해결 |
| SecOC C++ 이식 지연 | Python 벡터를 먼저 IVI에 공유 | C++ 완료 후 Config 2/3 재실험 |
| IDS 탐지율 미달 | 임계 재선정, 사양기반 탐지기 병용 | 특징 추가·ROC 재분석. **미달이면 미달로 보고** |
| Coverage 미달 | 위험 모듈(Fail-safe·SecOC) 시험 우선 추가 | 라인 ≥80%, Fail-safe 브랜치 100% |
| ICD 불일치 발견 | 구현을 ICD에 맞춤 | ICD가 틀렸으면 `interface-change` 게이트 |
| 물리 통합 실패 | Mock/`vcan0` 논리 통합 유지 | 하드웨어 집중 디버깅. IT-001~005는 미완료로 표기 |
| sklearn 미설치 | 규칙·사양기반 탐지기로 진행 | IF 비교 SKIPPED를 문서에 명시 |
| 데모 당일 장애 | `vcan0` 백업 경로 | 사전 녹화 영상, 녹화본임을 밝힘 |

**금지**: 목표 미달을 기준 완화·공격 강도 하향·측정 지점 변경으로 통과 처리하지 않는다.

---

## 8. 진행 기록과 차단 요인

| 단계 | 상태 | 검증 결과 | 차단 요인 | 갱신일 |
|---|---|---|---|---|
| M1 | | | | |
| M2 | | | | |
| M3 | | | | |
| M4 | | | | |
| M5 | | | | |
| M6 | | | | |
| M7 | | | | |
| M8 | | | | |

기록 규칙: 상태는 `미착수 / 진행 / 검증대기 / 완료`. 검증 결과에는 **실행한 명령과 결과**를 적는다. 차단 요인에는 의존 대상과 필요한 조치를 적는다.


Plan 승계 과제 색인: [공동 병합 기록](detail/common/00_협업_규약.md#plan-merge-20260908). 기존 Plan 링크는 새 주관 위치로 연결되며 구현·시험 완료 상태를 별도로 부여하지 않는다.

## IDS 독립 브랜치 인계 (CHG-007)

`feat/ecu-can-ids`에 스트리밍 규칙·IF·독립 SecOC 관찰·replay/SocketCAN 경로를 추가했다. 위 기존 현황의 “실시간 경로 미구현”은 이 브랜치에서 소스 구현/소프트웨어 시험으로 갱신하며 장비 인수는 미완료다. [실행 방법](../security/ids/README.md), [증거](../docs/aidlc/changes/CHG-007/audit.md). 물리 통합·인증 이벤트 채널·세션·M5 실험은 별도 과제다.
