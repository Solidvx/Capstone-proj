# 프로젝트 실행 가이드 총괄 INDEX

> **최종 갱신**: 2026-05-27  
> **프로젝트**: AUTOSAR 계층 기반 IVI-ECU 통합 플랫폼 (캡스톤디자인)  
> **팀 구성**: 팀원A (Node A -- ECU/BSW/BMS/SecOC/IDS) + 팀원B (Node B -- IVI/AOSP/HAL/CI/CD)  
> **기간**: 2026-06 ~ 2027-01 (8개월, M1~M8)

---

## 1. 이 문서의 목적

이 문서는 `tmp/` 디렉토리에 존재하는 4개 실행 가이드 파일의 **최상위 진입점(Entry Point)**이다.

**사용 방법:**

1. 이 INDEX.md에서 현재 월(M1~M8)에 해당하는 Quick Reference를 확인한다.
2. 자신의 역할에 맞는 개별 파일을 열어 해당 월의 상세 절차를 수행한다.
3. 공동 작업은 `PLAN_공동.md`를, 발표 준비는 `팀간_연계_분석.md`를 참조한다.
4. 의존성 충돌이나 일정 지연 발생 시 본 문서의 "Critical Path 요약" 및 "비상 대응" 섹션을 참조한다.

---

## 2. 파일 구조 및 역할

| 파일명 | 분량 | 대상 | 핵심 내용 | 참조 시점 |
|--------|------|------|----------|----------|
| `PLAN_팀원A.md` | 2,990줄 | 팀원A | RPi4 Ubuntu + C++17 BSW/BMS/SecOC + Python IDS. 팀원A Issue 라벨 Quick Reference, M1~M8 전체 수행 절차, 코드 예제, 검증 명령 포함 | 팀원A가 매 작업 시 |
| `PLAN_팀원B.md` | 3,605줄 | 팀원B | RPi4 AOSP/Ubuntu + Java/Kotlin HAL/Service/Dashboard + Docker/CI. 팀원B Issue 라벨 Quick Reference, M1~M8 전체 수행 절차, Plan A/B 전환 포함 | 팀원B가 매 작업 시 |
| `PLAN_공동.md` | 2,076줄 | 양측 | GitHub 인프라 설정, ICD.md 확정 미팅, `interface-change` 워크플로, 통합 테스트(IT-001~005), 매월 마일스톤 완료 처리(절차 A~D), 발표/보고서 | 공동 작업, 마일스톤 처리 시 |
| `팀간_연계_분석.md` | 1,235줄 | 양측 | 월별 의존성 흐름도, 데이터 플로우 다이어그램, 지연 시나리오 분석, 발표 슬라이드 구성, Q&A 대비 | 발표 준비, 의존성 분석 시 |

**읽기 우선순위:**

```
[시작] INDEX.md (본 문서)
   |
   +---> 자기 역할 PLAN (팀원A 또는 팀원B)  -- 매일 참조
   |
   +---> PLAN_공동.md                       -- 공동 작업/마일스톤 처리 시
   |
   +---> 팀간_연계_분석.md                   -- 발표 준비/의존성 확인 시
```

---

## 3. 월별 Quick Reference (M1~M8)

### M1 (6월) -- 환경 구축 + 설계

| 항목 | 내용 |
|------|------|
| **월 목표** | ICD.md 확정 + 개발 환경 동작 + CI Stage 1 cppcheck 녹색 + SRS.md 초안 --> 이후 ICD 계약 기반 독립 개발 시작 |
| **팀원A 핵심 작업** | RPi4 Ubuntu 설치, MCP2515/vcan0 CAN 설정, CMake/GCC/GTest 설치, `can_driver.h`/`publisher.h` 설계, ICD.md 초안 |
| **팀원A 참조** | `PLAN_팀원A.md` M1 섹션 (33~390행) |
| **팀원B 핵심 작업** | AOSP 빌드 서버 구성, Docker 설치, `repo sync`, `Dockerfile.arm64`/`toolchain-aarch64.cmake`, `IVehicleHal.hal` 초안, CI Stage 1(cppcheck) |
| **팀원B 참조** | `PLAN_팀원B.md` M1 섹션 (33~466행) |
| **공동 핵심 작업** | GitHub 인프라 설정(브랜치 보호, Labels, Milestones), 디렉토리 골격 PR, ICD.md 리뷰 + 최종 확정 미팅, SRS.md/ADR 초안 |
| **공동 참조** | `PLAN_공동.md` 사전 준비 + M1 섹션 (103~711행) |
| **핵심 산출물** | `v0.1.0` 태그, ICD.md 확정, SRS.md 초안, ADR-001~004, `can_driver.h`, `IVehicleHal.hal`, CI Stage 1 녹색 |
| **완료 판정 기준** | (1) 양쪽에서 `cansend`/`candump` 성공 (RPi4 can0 또는 vcan0 fallback 허용) (2) ICD.md PR 머지 완료 (3) CI Stage 1 cppcheck 녹색 (4) SRS.md FR 초안 PR 머지 (5) `v0.1.0` 태그 존재 |

### M2 (7월) -- CAN CDD + HAL Mock + Plan B 판단

| 항목 | 내용 |
|------|------|
| **월 목표** | Mock 레이어로 독립 개발 시작, Plan A/B 전환 결정 |
| **팀원A 핵심 작업** | `mock_can_driver.cpp`, `can_cdd.cpp` SocketCAN 구현, `Publisher<T>` 완성, NASA Battery Dataset 확보, `can_publisher.cpp` 100ms 주기 송신 |
| **팀원A 참조** | `PLAN_팀원A.md` M2 섹션 (391~836행) |
| **팀원B 핵심 작업** | `VehicleHalMock.java`, `VehicleRepository.kt`, AOSP RPi4 부팅 시도, Plan A/B 전환 결정, `Dockerfile.arm64` Stage 2 빌드 |
| **팀원B 참조** | `PLAN_팀원B.md` M2 섹션 (467~758행) |
| **공동 핵심 작업** | Plan A/B 전환 결정 미팅 (7월 4주차), (Plan B 시) ADR-010 작성 |
| **공동 참조** | `PLAN_공동.md` M2 섹션 (712~811행) |
| **핵심 산출물** | `v0.2.0` 태그, CAN CDD 동작, Mock HAL, Plan A/B 결정 기록, NASA CSV |
| **완료 판정 기준** | (1) TC-BSW-001~005 PASSED (2) `can_publisher.cpp` 100ms 주기 편차 <=10ms (3) Plan A/B 결정 완료 (4) `v0.2.0` 태그 |

### M3 (8월) -- 핵심 로직 (EKF + SecOC + HAL 구현)

| 항목 | 내용 |
|------|------|
| **월 목표** | EKF SOC 오차 <=3%, SecOC HMAC Python-->C++ 이식, HAL 파싱/Service/UI 기본 완성 |
| **팀원A 핵심 작업** | `ekf_soc_estimator.cpp` EKF 구현, `failsafe_sm.cpp` 4상태 FSM, `secoc_module.py` Python 프로토타입, `secoc_module.cpp` C++ 이식, ADS1115 I2C 연결 |
| **팀원A 참조** | `PLAN_팀원A.md` M3 섹션 (837~1316행) |
| **팀원B 핵심 작업** | `can_parser.cpp` CAN 파싱, `vehicle_hal_impl.cpp` CAN rx_thread, `VehicleDataService.java` Binder IPC, `SocGauge.kt` 대시보드 UI, `secoc_verifier.cpp`, CI Stage 2~3 추가 |
| **팀원B 참조** | `PLAN_팀원B.md` M3 섹션 (759~1816행) |
| **공동 핵심 작업** | 중간 통합 테스트(CAN 0x100 수신 + ICD 레이아웃 일치), SDD-ECU/IVI S3 초안 |
| **공동 참조** | `PLAN_공동.md` M3 섹션 (812~969행) |
| **핵심 산출물** | `v0.3.0` 태그, EKF(TC-BMS-001), SecOC(TC-SEC-001~004), Fail-safe(TC-BMS-004), CAN Parser(TC-IVI-002), CI Stage 2~3 녹색 |
| **완료 판정 기준** | (1) EKF SOC 오차 <=3% (2) SecOC Python/C++ 교차 검증 통과 (3) Fail-safe Branch Coverage 100% (4) `v0.3.0` 태그 |

### M4 (9월) -- 물리 통합 + IDS + 1차 통합 테스트

| 항목 | 내용 |
|------|------|
| **월 목표** | end-to-end 전체 시스템 동작, IT-001~005 Pass, 공격 탐지 1차 데이터, 동작 영상 |
| **팀원A 핵심 작업** | Python IDS(`collect_normal.py`, `train_model.py`, `ids_engine.py`), 공격 시뮬레이터 4종(`fuzzy/flooding/replay/spoofing`), `ids_alerter.py` CAN 0x200, TARA.md v1 |
| **팀원A 참조** | `PLAN_팀원A.md` M4 섹션 (1317~1762행) |
| **팀원B 핵심 작업** | `AlertBanner.kt` 공격 경보 UI, CI Stage 4 SSH 배포, e2e 레이턴시 측정 환경 |
| **팀원B 참조** | `PLAN_팀원B.md` M4 섹션 (1817~2280행) |
| **공동 핵심 작업** | MCP2515 x2 물리 CAN 연결, SecOC 전체 플로우 검증, IT-001~005 전체 통합 테스트, e2e 동작 영상 촬영, 레이턴시 측정(1,000 샘플) |
| **공동 참조** | `PLAN_공동.md` M4 섹션 (970~1379행) |
| **핵심 산출물** | `v0.4.0` 태그, 동작 영상(`demo_M4.mp4`), `latency_results.csv`, IT 결과 기록, TARA.md v1, IDS 1차 탐지율 |
| **완료 판정 기준** | (1) IT-001~005 전부 Pass (2) avg 레이턴시 <=50ms, max <=100ms (3) IDS Flooding 탐지 <=3초 (4) `v0.4.0` 태그 |

### M5 (10월) -- Ablation Study + IDS 최적화

| 항목 | 내용 |
|------|------|
| **월 목표** | 4종 공격 x 3 Config = 12세트 Ablation Study, IDS 파라미터 튜닝, 레이턴시 분석 |
| **팀원A 핵심 작업** | Ablation Study 12세트 실험 수행 (Config-1 무방어/Config-2 SecOC only/Config-3 SecOC+IDS), IDS contamination/threshold 튜닝, ROC 커브 분석 |
| **팀원A 참조** | `PLAN_팀원A.md` M5 섹션 (1763~2149행) |
| **팀원B 핵심 작업** | 레이턴시 P95/P99 분석 + 병목 구간 식별, 대시보드 UX 개선, ADR 문서 업데이트 |
| **팀원B 참조** | `PLAN_팀원B.md` M5 섹션 (2281~2654행) |
| **공동 핵심 작업** | TARA.md Ablation 1차 결과 반영, ADR-001~012 실험 기반 최종 검토 |
| **공동 참조** | `PLAN_공동.md` M5 섹션 (1380~1469행) |
| **핵심 산출물** | `v0.5.0` 태그, `results_summary.csv` (12세트), TARA.md 갱신, ADR 갱신 |
| **완료 판정 기준** | (1) 12세트 실험 완료 (2) IDS 탐지율 >=90% (3) TARA.md 실측값 반영 (4) `v0.5.0` 태그 |

### M6 (11월) -- 문서 완성 + CI 최종화

| 항목 | 내용 |
|------|------|
| **월 목표** | SDD 2종 최종화, CI 4단계 전체 녹색, Coverage >=80% |
| **팀원A 핵심 작업** | SDD-ECU.md 전체 완성, TARA.md 최종화, 실험 재현성 검증 |
| **팀원A 참조** | `PLAN_팀원A.md` M6 섹션 (2150~2451행) |
| **팀원B 핵심 작업** | SDD-IVI.md 전체 완성, CICD_SPEC.md, README.md 초안, 24시간 안정성 테스트 준비 |
| **팀원B 참조** | `PLAN_팀원B.md` M6 섹션 (2655~2905행) |
| **공동 핵심 작업** | CI 전체 녹색 최종 확인 (cppcheck 0건, ARM64 빌드, Coverage >=80%, SSH Health Check), ADR 최종 검토 |
| **공동 참조** | `PLAN_공동.md` M6 섹션 (1470~1582행) |
| **핵심 산출물** | `v0.6.0` 태그, SDD-ECU.md, SDD-IVI.md, CICD_SPEC.md, TARA.md 최종 |
| **완료 판정 기준** | (1) CI 4단계 전체 녹색 (2) Statement Coverage >=80% (3) Fail-safe Branch 100% (4) `v0.6.0` 태그 |

### M7 (12월) -- 최종 검증 + 교차 검토

| 항목 | 내용 |
|------|------|
| **월 목표** | 문서-구현 일치 확인, 최종 통합 테스트 재검증, 성능 수치 최종 기록 |
| **팀원A 핵심 작업** | 팀원B 구현 교차 검토(SecOC 롤링 카운터, HIDL API, IDS Alert 파싱), 실험 재현성 검증(12세트 재실행) |
| **팀원A 참조** | `PLAN_팀원A.md` M7 섹션 (2452~2742행) |
| **팀원B 핵심 작업** | 팀원A 구현 교차 검토(CAN 바이트 오프셋, 스케일링, SecOC HMAC 입력), 24시간 안정성 테스트 실행 |
| **팀원B 참조** | `PLAN_팀원B.md` M7 섹션 (2906~3133행) |
| **공동 핵심 작업** | ICD.md <-> 구현 교차 검토(10항목), SRS.md FR 추적 매트릭스, TC 전체 실행, IT-001~005 재검증, TC-PERF-001~003 최종 수치 |
| **공동 참조** | `PLAN_공동.md` M7 섹션 (1583~1752행) |
| **핵심 산출물** | `v0.7.0` 태그, FR 추적 매트릭스, TC 결과 기록, 최종 레이턴시 CSV, 불일치 수정 PR |
| **완료 판정 기준** | (1) IT-001~005 재검증 전부 Pass (2) ICD <-> 구현 불일치 0건 (3) TC-PERF-001~003 목표 달성 (4) `v0.7.0` 태그 |

### M8 (1월) -- 발표 준비 + 최종 제출

| 항목 | 내용 |
|------|------|
| **월 목표** | 데모 리허설 3회, 발표 자료, 최종 보고서, v1.0.0 릴리즈 |
| **팀원A 핵심 작업** | 직무 어필 슬라이드(BSW/CDD, BMS EKF, SecOC, IDS, TARA), 보고서 4/5/8장, 데모 시나리오 A/B Node A 실행 |
| **팀원A 참조** | `PLAN_팀원A.md` M8 섹션 (2743~2990행) |
| **팀원B 핵심 작업** | 직무 어필 슬라이드(IVI SW, HIDL HAL, CI/CD, Docker), 보고서 6/7장, 데모 시나리오 Node B 실행 |
| **팀원B 참조** | `PLAN_팀원B.md` M8 섹션 (3134~3605행) |
| **공동 핵심 작업** | 데모 시나리오 A(정상)/B(공격) 구성, 리허설 3회, 최종 보고서 작성(10장+부록), 발표 자료 최종화, GitHub 정리, `v1.0.0` 태그 |
| **공동 참조** | `PLAN_공동.md` M8 섹션 (1753~2076행) |
| **핵심 산출물** | `v1.0.0` 태그, 발표 자료(PDF), 최종 보고서, 데모 영상, GitHub Release v1.0.0 |
| **완료 판정 기준** | (1) 리허설 3회 완료 (2) 발표 자료 + 보고서 제출 (3) 8개 Release(v0.1.0~v1.0.0) 확인 (4) 모든 Milestone Closed |

---

## 4. 의존성 타임라인 통합 뷰

아래 텍스트 Gantt 차트는 양 팀원의 작업 스트림을 병렬로 표시한다.
`>>>` 화살표는 의존성, `[CP]`는 Critical Path 항목을 나타낸다.

```
월      M1 (6월)          M2 (7월)          M3 (8월)          M4 (9월)          M5 (10월)         M6 (11월)         M7 (12월)         M8 (1월)
주   1  2  3  4        1  2  3  4        1  2  3  4        1  2  3  4        1  2  3  4        1  2  3  4        1  2  3  4        1  2  3  4

팀원A ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
     [RPi4 설치 ]  [can_driver.h][ICD초안  ][ICD확정]  [MockCAN][can_cdd.cpp ][Publisher][NASA CSV]  [EKF SOC 구현    ][Fail-safe][secoc.py][secoc.cpp]  [IDS환경][수집+학습][공격4종  ][ids_alerter]  [Ablation 12세트       ][IDS튜닝]  [SDD-ECU 작성     ][TARA최종]  [교차검토][재현검증 ][최종IT ]  [데모준비][보고서  ][리허설 ][정리   ]
      CAN설정       설계   >>>                                CDD    TC-BSW       Pub/Sub  can_pub   EKF    TC-BMS-001   FSM     Python>>>C++[CP]    Python환경 정상트래픽 fuzzy/flood alerter     Config1/2/3             ROC분석   ECU문서          TARA완성   B구현검토 12세트재실행 Pass확인  슬라이드A 4/5/8장  최종리허설 v1.0.0
      도구설치                  |                                                                                 |                      |                               |                                                                    |
                               |                                                                                 |                      |                               |                                                                    |
                               v                                                                                 v                      v                               v                                                                    v
팀원B ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
     [AOSP서버  ][Docker설치 ][Dockerfile][repo sync]  [HAL HIDL][VehicleHalMock][AOSP부팅시도    ][PlanA/B]  [can_parser ][HAL impl   ][Service  ][SocGauge][secoc_ver]  [AlertBanner][CI Stage4][레이턴시환경]  [레이턴시분석    ][UX개선  ]  [SDD-IVI 작성     ][CICD_SPEC] [교차검토][24h안정성][최종IT ]  [데모준비][보고서  ][리허설 ][정리   ]
      빌드서버    Docker  arm64  toolchain   sync완료    HIDL완성 Mock100ms주기   RPi4빌드>>>판정[CP]       파싱 TC-IVI   rx_thread    Binder    UI구현   verifier[CP]  경보UI     SSH배포   측정스크립트    P95/P99          최적화    IVI문서          CI문서     A구현검토 장시간테스트 Pass확인  슬라이드B 6/7장   최종리허설 v1.0.0
                                                                                  |                                              |                                                                                           |
                                                                                  |                                              |                                                                                           |
                                                                                  v                                              v                                                                                           v
공동  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
     [GitHub설정][Labels/MS ][ICD리뷰   ][ICD확정]                        [PlanA/B미팅]                [중간통합][SDD초안]  [물리CAN][SecOC검증][IT-001~005][영상+레이턴시]  [TARA결과반영 ][ADR검토  ]  [CI녹색확인     ][ADR최종]  [ICD교차검토][FR매트릭스][TC전체][PERF] [시나리오][보고서  ][리허설3회        ][v1.0.0 ]
      브랜치보호   생성      리뷰사이클[CP] 확정미팅      `v0.1.0`          결정미팅    `v0.2.0`        vcan테스트        MCP2515x2 전체플로우 5시나리오    촬영+측정    TARA업데이트 12개ADR      4단계전부Pass  Coverage    10항목검토  추적표     재검증 최종수치 데모구성  10장+부록 최종 타이밍 확인  GitHub정리
```

**Critical Path 경로 (지연 시 전체 일정에 직접 영향):**

```
M1 ICD.md 확정 --->>> M2 Mock 독립 개발 --->>> M3 SecOC 3단계 체인 --->>> M4 물리 통합 + IT --->>> M5 Ablation Study
      |                                              |                          |
   [4주차]                                   secoc_module.py (2주)         ids_alerter.py (3주)
                                             secoc_module.cpp (3주)        AlertBanner.kt (3주)
                                             secoc_verifier.cpp (4주)     IT-005 e2e (4주)

Critical Path 총 길이: 약 15주 / 프로젝트 총 기간: 32주 / 여유(Float): 17주
```

---

## 5. Critical Path 요약 -- 5대 핵심 의존성

프로젝트 전체 일정을 지연시킬 수 있는 5가지 핵심 의존성과 완화 방안이다.

| # | 의존성 | 시점 | 지연 시 영향 | 완화 방안 |
|---|--------|------|-------------|----------|
| 1 | **ICD.md 확정 지연** | M1 4주차 | M2 독립 개발 시작 불가, 전체 일정 1:1 지연 | ICD S1~S2(CAN 규격)를 먼저 90% 확정하고, S3(HAL API)은 팀원B가 병렬 작성. TODO로 미확정 항목 관리 |
| 2 | **AOSP 부팅 실패 (Plan B 전환)** | M2 4주차 | 팀원B HAL/UI 스택 전면 재설계 (3~4주 추가). 단, 팀원A 영향 0건 | M2 2주차 AOSP 첫 빌드 시도 후 조기 Go/No-Go 판단. Plan B(Ubuntu + D-Bus/gRPC + Qt/Flutter) 대안 아키텍처 사전 설계 |
| 3 | **SecOC C++ 이식 지연** | M3 3주차 | 팀원B의 `secoc_verifier.cpp` 작성 불가 --> M4 SecOC 통합 불가 --> Ablation Config-2/3 불가 | Python 테스트 벡터를 M3 2주차에 먼저 공유하여 팀원B가 검증 로직 선행 구현. SecOC 없이 Config-1 baseline 먼저 진행 |
| 4 | **물리 CAN 통합 실패** | M4 1주차 | end-to-end 검증 지연, 동작 영상 촬영 불가 | vcan0 브릿지로 논리적 통합 먼저 검증. 물리 CAN은 MCP2515 배선/종단저항 점검 후 재시도 |
| 5 | **IDS 탐지율 90% 미달** | M5 | Ablation Study 신뢰도 저하, TARA 예측-실측 불일치 | contamination 0.01-->0.05 조정, 특징 벡터 7차원-->확장(payload entropy, DLC 분포), 결과를 투명 보고 + 개선 방향 제시 |

---

## 6. 월별 산출물 체크리스트

### M1 (6월) -- v0.1.0

| 분류 | 산출물 | 파일/위치 | 담당 |
|------|--------|----------|------|
| 코드 | `adaptive_ecu/` 디렉토리 골격 + CMakeLists.txt | `adaptive_ecu/` | 팀원A |
| 코드 | `ivi_platform/` 디렉토리 골격 | `ivi_platform/` | 팀원B |
| 코드 | `can_driver.h` CanDriver 추상 클래스 | `adaptive_ecu/include/` | 팀원A |
| 코드 | `publisher.h` 템플릿 헤더 초안, `subscriber.h` 인터페이스 | `adaptive_ecu/include/` | 팀원A |
| 코드 | `IVehicleHal.hal`, `IVehicleHalCallback.hal` HIDL 초안 | `ivi_platform/hal/` | 팀원B |
| 코드 | `Dockerfile.arm64` + `toolchain-aarch64.cmake` | 프로젝트 루트 | 팀원B |
| CI | `.github/workflows/ci.yml` (Stage 1 cppcheck) | `.github/workflows/` | 팀원B |
| 문서 | `docs/ICD.md` 확정본 | `docs/` | 공동 |
| 문서 | `docs/SRS.md` 초안 (FR-BSW/BMS/SEC/IVI/CI) | `docs/` | 공동 |
| 문서 | `docs/ADR.md` ADR-001~004 | `docs/` | 공동 |
| 인프라 | `.gitignore`, `.github/PULL_REQUEST_TEMPLATE.md` | 루트, `.github/` | 공동 |
| 인프라 | GitHub Labels 11개, Milestones M1~M8, 브랜치 보호 규칙 | GitHub Settings | 공동 |
| 태그 | `v0.1.0` | Git | 공동 |

### M2 (7월) -- v0.2.0

| 분류 | 산출물 | 파일/위치 | 담당 |
|------|--------|----------|------|
| 코드 | `mock_can_driver.cpp` | `adaptive_ecu/src/bsw/` | 팀원A |
| 코드 | `can_cdd.cpp` SocketCAN 구현 | `adaptive_ecu/src/bsw/` | 팀원A |
| 코드 | `publisher.h` Publisher<T> 템플릿 완성 | `adaptive_ecu/include/` | 팀원A |
| 코드 | `sensor_simulator.cpp` CONSTANT/PROFILE 모드 | `adaptive_ecu/src/app/` | 팀원A |
| 코드 | `bms_component.cpp` BMS 통합 로직 초안 | `adaptive_ecu/src/app/` | 팀원A |
| 코드 | `can_publisher.cpp` 100ms 주기 | `adaptive_ecu/src/bsw/` | 팀원A |
| 코드 | `VehicleHalMock.java` | `ivi_platform/hal/mock/` | 팀원B |
| 코드 | `VehicleRepository.kt` | `ivi_platform/app/data/` | 팀원B |
| 테스트 | TC-BSW-001~005, TC-BMS-007 (100ms 주기 표준편차 ≤10ms) | `adaptive_ecu/test/` | 팀원A |
| 데이터 | `data/battery_profile_1h.csv` (NASA) | `data/` | 팀원A |
| 문서 | ADR-010 (Plan B 전환 시) | `docs/ADR.md` | 공동 |
| 태그 | `v0.2.0` | Git | 공동 |

### M3 (8월) -- v0.3.0

| 분류 | 산출물 | 파일/위치 | 담당 |
|------|--------|----------|------|
| 코드 | `ekf_soc_estimator.h/.cpp` | `adaptive_ecu/include/`, `src/app/` | 팀원A |
| 코드 | `soh_estimator.cpp` (SOH 추정) | `adaptive_ecu/src/app/` | 팀원A |
| 코드 | `failsafe_sm.h/.cpp` | `adaptive_ecu/include/`, `src/app/` | 팀원A |
| 코드 | `secoc_module.py` | `security/` | 팀원A |
| 코드 | `secoc_module.cpp` | `adaptive_ecu/src/bsw/` | 팀원A |
| 코드 | `watchdog_manager.cpp` | `adaptive_ecu/src/bsw/` | 팀원A |
| 코드 | `sensor_simulator.cpp` ADS1115_HARDWARE 모드 (SDD-ECU §3.7.3) | `adaptive_ecu/src/app/` | 팀원A |
| 코드 | `can_parser.h/.cpp` | `ivi_platform/hal/` | 팀원B |
| 코드 | `vehicle_hal_impl.cpp` | `ivi_platform/hal/` | 팀원B |
| 코드 | `IVehicleDataService.aidl` (Binder IPC 인터페이스) | `ivi_platform/service/` | 팀원B |
| 코드 | `VehicleDataService.java` | `ivi_platform/service/` | 팀원B |
| 코드 | `VehicleDataManager.java` (앱 클라이언트 API) | `ivi_platform/service/` | 팀원B |
| 코드 | `SocGauge.kt`, `DashboardViewModel.kt` | `ivi_platform/app/` | 팀원B |
| 코드 | `secoc_verifier.cpp` | `ivi_platform/hal/` | 팀원B |
| CI | CI Stage 2 (ARM64 빌드) + Stage 3 (QEMU 테스트) | `.github/workflows/ci.yml` | 팀원B |
| 테스트 | TC-BMS-001~004 (EKF/SOH/Fail-safe), TC-SEC-001~004 | `adaptive_ecu/test/` | 팀원A |
| 테스트 | TC-IVI-001~005 | `ivi_platform/test/` | 팀원B |
| 문서 | SDD-ECU.md S3 초안, SDD-IVI.md S3 초안 | `docs/` | 각자 |
| 태그 | `v0.3.0` | Git | 공동 |

### M4 (9월) -- v0.4.0

| 분류 | 산출물 | 파일/위치 | 담당 |
|------|--------|----------|------|
| 코드 | `collect_normal.py`, `train_model.py` | `security/ids/` | 팀원A |
| 코드 | `ids_engine.py`, `ids_alerter.py` | `security/ids/` | 팀원A |
| 코드 | `fuzzy_attack.py` v1, `flooding_attack.py` v1 (TC-SEC-005-a/d) | `security/attacks/` | 팀원A |
| 코드 | `DashboardScreen.kt` 전체 레이아웃 | `ivi_platform/app/` | 팀원B |
| 코드 | `AlertBanner.kt`, `FailSafeIndicator.kt` | `ivi_platform/app/` | 팀원B |
| CI | CI Stage 4 (SSH 배포 + Health Check), `scripts/health_check.sh` | `.github/workflows/`, `scripts/` | 팀원B |
| 테스트 | IT-001~005 통합 테스트 결과 기록 (TC-INT-001~004) | `docs/TEST_PLAN.md` | 공동 |
| 테스트 | TC-SEC-006 (IDS 탐지율 ≥90%, 오탐율 ≤5%), TC-IVI-006/007 | `adaptive_ecu/test/`, `ivi_platform/test/` | 각자 |
| 데이터 | `latency_results.csv` (1,000 샘플) | 프로젝트 루트 | 공동 |
| 데이터 | IDS 1차 탐지율 CSV (Fuzzy + Flooding) | `security/ids/` | 팀원A |
| 미디어 | `demo_M4_YYYYMMDD.mp4` 동작 영상 | Release 첨부 | 공동 |
| 문서 | `docs/TARA.md` v1 (자산 식별, STRIDE, Feasibility) | `docs/` | 팀원A |
| 태그 | `v0.4.0` | Git | 공동 |

### M5 (10월) -- v0.5.0

| 분류 | 산출물 | 파일/위치 | 담당 |
|------|--------|----------|------|
| 코드 | `replay_attack.py` v2 정밀화 (TC-SEC-005-b) | `security/attacks/` | 팀원A |
| 코드 | `spoofing_attack.py` v2 정밀화 (TC-SEC-005-c) | `security/attacks/` | 팀원A |
| 데이터 | `results_summary.csv` (12세트 Ablation: 4종 공격 × 3 Config) | `security/ids/` | 팀원A |
| 데이터 | ROC 커브 그래프 (IDS 최적화) | `security/ids/` | 팀원A |
| 데이터 | 레이턴시 P95/P99 분석 결과 | `security/` | 팀원B |
| 테스트 | TC-EXP-001~005 (Ablation), TC-PERF-001~002 측정 | `docs/TEST_PLAN.md` | 각자 |
| 문서 | TARA.md Ablation 결과 반영 (실측 탐지율/차단율) | `docs/TARA.md` | 공동 |
| 문서 | ADR-001~012 실험 기반 갱신 (결과 섹션 보강) | `docs/ADR.md` | 공동 |
| 태그 | `v0.5.0` | Git | 공동 |

### M6 (11월) -- v0.6.0

| 분류 | 산출물 | 파일/위치 | 담당 |
|------|--------|----------|------|
| 문서 | SDD-ECU.md 완성 | `docs/` | 팀원A |
| 문서 | SDD-IVI.md 완성 | `docs/` | 팀원B |
| 문서 | CICD_SPEC.md 완성 | `docs/` | 팀원B |
| 문서 | TARA.md 최종화 | `docs/` | 팀원A |
| CI | CI 4단계 전체 녹색 | GitHub Actions | 팀원B |
| 태그 | `v0.6.0` | Git | 공동 |

### M7 (12월) -- v0.7.0

| 분류 | 산출물 | 파일/위치 | 담당 |
|------|--------|----------|------|
| 문서 | SRS.md FR 추적 매트릭스 | `docs/SRS.md` | 공동 |
| 문서 | TEST_PLAN.md TC 전체 결과 기록 (Skip 항목 사유 포함) | `docs/TEST_PLAN.md` | 공동 |
| 문서 | ICD <-> 구현 교차 검토 결과 (불일치 수정) | `docs/ICD.md` | 공동 |
| 문서 | `how_to_train.md` IDS 재현 방법 문서 | `security/ids/` | 팀원A |
| 데이터 | 최종 `latency_results.csv` | Release 첨부 | 공동 |
| 데이터 | `results_summary.csv` 재현성 검증 결과 (편차 ≤5%) | `security/ids/` | 팀원A |
| 데이터 | 24시간 안정성 테스트 로그 | `security/` | 팀원B |
| 테스트 | IT-001~005 재검증, TC-PERF-001~003 최종 수치 | `docs/TEST_PLAN.md` | 공동 |
| 태그 | `v0.7.0` | Git | 공동 |

### M8 (1월) -- v1.0.0

| 분류 | 산출물 | 파일/위치 | 담당 |
|------|--------|----------|------|
| 발표 | 발표 자료 (15~20 슬라이드 PDF) | Release 첨부 | 공동 |
| 보고서 | 최종 보고서 (10장 + 부록) | 제출용 | 공동 |
| 미디어 | 데모 영상 (사전 녹화 백업 포함) | Release 첨부 | 공동 |
| 코드 | README.md 최종화 | 프로젝트 루트 | 팀원B |
| 인프라 | GitHub 정리 (stale 브랜치, Issue, PR Close) | GitHub | 공동 |
| 인프라 | 8개 Release(v0.1.0~v1.0.0) 확인 | GitHub Releases | 공동 |
| 태그 | `v1.0.0` | Git | 공동 |

---

## 7. 발표 스토리라인 가이드 (15 슬라이드)

아래는 캡스톤 디펜스 발표 시 권장하는 슬라이드별 구성이다.
각 항목에서 참조하는 `팀간_연계_분석.md` 섹션 번호를 표기하였다.

| 슬라이드 | 제목 | 핵심 메시지 | 근거 자료/그래프 | 담당 | Talking Point |
|----------|------|-----------|----------------|------|--------------|
| 1 | 표지 | 과제명, 팀원, 지도교수 | -- | 공동 | -- |
| 2 | 프로젝트 배경 + 동기 | 차량 CAN 보안 위협, AUTOSAR 기반 방어의 필요성 | TARA.md 위협 시나리오 표 | 공동 | "CAN 버스는 인증 메커니즘이 없어 Spoofing/Replay 공격에 취약합니다" |
| 3 | 시스템 아키텍처 | ICD.md 계약 기반 2노드 독립 개발 | `팀간_연계_분석.md` S1.1 구조도 | 공동 | "AUTOSAR 실무 OEM-Tier1 방식과 동일하게 ICD 계약으로 병렬 개발 체제를 확립했습니다" |
| 4 | Node A -- BSW/CDD | SocketCAN CDD 추상화 + ara::com Pub/Sub | `can_driver.h` 인터페이스 다이어그램 | 팀원A | "CanDriver 추상 클래스로 Mock/실물 교체가 무변경 가능합니다" |
| 5 | Node A -- BMS EKF | Coulomb Counting 대비 EKF SOC 추정 정확도 개선 | EKF vs Coulomb RMSE 비교 그래프 (TC-BMS-002) | 팀원A | "1D EKF로 SOC 추정 RMSE를 X% 개선, NASA 배터리 데이터로 검증했습니다" |
| 6 | Node A -- SecOC | Python-->C++ 이식, 교차 검증 벡터로 HMAC 일관성 보장 | `팀간_연계_분석.md` S2 M3 SecOC 3단계 체인 다이어그램 | 팀원A | "3개 언어/플랫폼에서 동일 MAC 출력을 교차 검증했습니다" |
| 7 | Node B -- IVI 플랫폼 | HIDL HAL --> SystemService --> Dashboard App 3계층 | `팀간_연계_분석.md` S3 데이터 플로우 다이어그램 | 팀원B | "CAN 수신부터 UI 렌더링까지 50ms 이내 처리를 달성했습니다" |
| 8 | Node B -- CI/CD | 4단계 파이프라인: cppcheck-->Docker-->QEMU-->SSH | `팀간_연계_분석.md` S8 CI/CD 구조도 | 팀원B | "팀원A가 push하면 4단계 CI가 자동으로 품질을 보증합니다" |
| 9 | 보안 -- IDS | Isolation Forest 7차원 특징, 4종 공격 탐지 | IDS 아키텍처 다이어그램 + `팀간_연계_분석.md` S4 공격 탐지 플로우 | 팀원A | "비지도 학습으로 정상 트래픽만으로 학습, 미지 공격 탐지가 가능합니다" |
| 10 | 보안 -- Ablation Study | 3가지 방어 구성별 차단율/탐지율 비교 | Config 1/2/3 x 4종 공격 결과 표 + 막대 그래프 | 팀원A | "SecOC만으로 Spoofing/Replay 100% 차단, IDS가 Flooding을 보완하는 계층적 방어를 수치로 입증했습니다" |
| 11 | 통합 테스트 결과 | IT-001~005 Pass, e2e 동작 검증 | IT 결과 표 + 성능 수치 표 (TC-PERF-001~003) | 공동 | "5개 통합 시나리오 전부 Pass, e2e 레이턴시 avg Xms 달성" |
| 12 | e2e 레이턴시 | avg/P95/P99/max 분포 | 레이턴시 히스토그램 (`latency_results.csv` 기반) | 공동 | "1,000 샘플 측정, 100ms CAN 주기 내 처리 완료" |
| 13 | 라이브 데모 | 시나리오 A(정상) + B(공격+방어) | 사전 녹화 영상 또는 라이브 | 공동 | "EKF SOC --> CAN --> 대시보드 표시, Flooding --> IDS 탐지 --> AlertBanner 3초 이내" |
| 14 | 협업 구조 + 성과 요약 | ICD 계약 + Mock 독립 + 교차 검토 + CI 품질 보증 | `팀간_연계_분석.md` S10 4대 기둥 다이어그램 + 핵심 수치 표 | 공동 | `팀간_연계_분석.md` S9.6 핵심 수치 9개 제시 |
| 15 | 한계점 + 향후 과제 + Q&A | OTA 키 교환, 다중 ECU, AIDL 전환 | -- | 공동 | `팀간_연계_분석.md` S9.5 예상 Q&A 7문항 참조 |

**슬라이드별 참조 데이터:**

| 슬라이드 | 필요 그래프/표 | 데이터 출처 |
|----------|--------------|-----------|
| 5 | EKF vs Coulomb RMSE 비교 막대 그래프 | `adaptive_ecu/test/` TC-BMS-002 결과 |
| 10 | Ablation Study 4x3 결과 표 + 막대 그래프 | `results_summary.csv` |
| 11 | IT-001~005 Pass/Fail 표 | `docs/TEST_PLAN.md` |
| 12 | 레이턴시 히스토그램 (1,000 샘플) | `latency_results.csv` |
| 14 | 핵심 수치 9개 요약 표 | `팀간_연계_분석.md` S9.6 |

**강조할 핵심 수치** (참조: `팀간_연계_분석.md` S9.6):

| 수치 | 항목 | 의미 |
|------|------|------|
| <=50ms | e2e 레이턴시 | 100ms CAN 주기 내 처리 완료 |
| <=3초 | IDS 탐지-->경보 표시 | 1초 윈도우 + 처리, 여유 마진 ~1.9초 |
| 100% | Spoofing/Replay 차단율 | SecOC HMAC + 롤링 카운터 |
| >=90% | Flooding 탐지율 | Isolation Forest IDS |
| >=80% | Statement Coverage | CI Stage 3 자동 검증 |
| 12세트 | Ablation Study 실험 수 | 4종 공격 x 3 Config |
| 5개 언어 | IDS-->AlertBanner 파이프라인 | Python-->CAN-->C++-->Java-->Kotlin |
| 4단계 | CI/CD 파이프라인 | cppcheck-->Docker-->QEMU-->SSH |
| 0건 | ICD 인터페이스 불일치 | 계약 기반 개발의 효과 |

---

## 8. Quick Command Reference -- 월별 필수 명령어

각 월에서 반드시 성공해야 하는 핵심 bash/git 명령어를 정리한다.

### M1 (6월)

```bash
# 1. CAN 인터페이스 확인 (Node A)
sudo ip link set can0 up type can bitrate 500000 && ip link show can0

# 2. vcan0 Fallback
sudo modprobe vcan && sudo ip link add dev vcan0 type vcan && sudo ip link set vcan0 up

# 3. 빌드 도구 확인
cmake --version && gcc --version && cansend --help

# 4. GoogleTest 동작 확인
mkdir -p /tmp/gt && cd /tmp/gt && cmake /path/to/gtest-verify && make && ctest

# 5. Docker 확인 (Node B)
docker run hello-world
```

### M2 (7월)

```bash
# 1. CAN CDD 단위 테스트
cd adaptive_ecu/build && cmake .. && make && ctest --output-on-failure

# 2. CAN 100ms 주기 확인
candump -t d vcan0 | head -20  # 각 줄 간격 ~0.100s

# 3. ARM64 크로스컴파일 확인
docker run --rm -v $(pwd):/workspace capstone-arm64 bash -c \
  "cmake -DCMAKE_TOOLCHAIN_FILE=/workspace/toolchain-aarch64.cmake ..." && \
  file build/ecu_node_a  # ELF 64-bit ARM aarch64

# 4. AOSP 빌드 (Node B)
cd ~/aosp && source build/envsetup.sh && lunch rpi4-eng && make -j$(nproc)
```

### M3 (8월)

```bash
# 1. EKF SOC 테스트
cd adaptive_ecu/build && ctest -R test_ekf_soc --output-on-failure

# 2. Fail-safe Coverage 100% 확인
cmake .. -DCMAKE_CXX_FLAGS="--coverage" && make && ctest && \
  lcov --capture --directory . --output-file cov.info && \
  lcov --extract cov.info '*/failsafe_sm.cpp' --output-file fs.info && \
  lcov --summary fs.info  # branches: 100.0%

# 3. SecOC Python 테스트
cd security && python -m pytest tests/test_secoc.py -v

# 4. SecOC C++ 교차 검증
cd adaptive_ecu/build && ctest -R test_secoc --output-on-failure
```

### M4 (9월)

```bash
# 1. 물리 CAN 양방향 통신
# Node B: candump can0 &
# Node A: cansend can0 100#DEADBEEF
# Node A: candump can0 &
# Node B: cansend can0 200#CAFEBABE

# 2. IDS 환경 + 모델 학습
cd security && source venv/bin/activate && \
  python3 collect_normal.py --channel vcan0 --duration 1800 && \
  python3 train_model.py

# 3. Flooding 공격 + IDS 탐지
python3 ids/ids_engine.py --interface can0 &
python3 attacks/flooding_attack.py --interface can0 --duration 10

# 4. e2e 레이턴시 측정
python3 scripts/measure_latency.py can0  # avg <=50ms, max <=100ms
```

### M5 (10월)

```bash
# 1. Ablation Config-1 (무방어)
./adaptive_ecu --interface can0 --secoc-disabled  # SecOC OFF, IDS OFF

# 2. Ablation Config-2 (SecOC only)
./adaptive_ecu --interface can0 --secoc-enabled    # SecOC ON, IDS OFF

# 3. Ablation Config-3 (SecOC + IDS)
./adaptive_ecu --interface can0 --secoc-enabled &
python3 security/ids/ids_engine.py --interface can0 &
```

### M6 (11월)

```bash
# 1. cppcheck 0건 확인
cppcheck --enable=all --error-exitcode=1 --suppress=missingIncludeSystem \
  --suppress=unusedFunction -I adaptive_ecu/include adaptive_ecu/src/

# 2. Coverage >= 80% 확인
lcov --summary coverage_filtered.info  # lines: >=80.0%

# 3. SSH Health Check 확인
ssh deploy@<RPI_HOST> "systemctl is-active ecu-node-a.service"  # active
```

### M7 (12월)

```bash
# 1. C++ 전체 테스트
cd build_test && ctest --output-on-failure --timeout 60

# 2. Python 전체 테스트
cd security && pytest tests/ -v --tb=short

# 3. TC-PERF-001~003 최종 측정
python3 scripts/measure_latency.py can0       # PERF-001
candump -t d can0 | head -110                  # PERF-002
python3 security/attacks/flooding_attack.py --interface can0 --duration 10  # PERF-003
```

### M8 (1월)

```bash
# 1. 데모 시나리오 A (정상)
./adaptive_ecu --interface can0 --secoc-enabled --sensor-mode profile_csv \
  --profile data/battery_profile_demo.csv

# 2. 데모 시나리오 B (공격)
python3 security/attacks/flooding_attack.py --interface can0 --duration 10

# 3. v1.0.0 태그 생성
git switch main && git pull origin main
git tag -a v1.0.0 -m "M8: 최종 발표 준비 완료"
git push origin --tags

# 4. 전체 태그 확인
git tag -l  # v0.1.0 ~ v1.0.0 (8개)
```

### 매월 반복 -- 마일스톤 완료 처리 (절차 A~D)

```bash
# A. develop --> main PR 생성 + Merge (GitHub 웹)
git switch develop && git pull origin develop
# GitHub: New PR, base=main, compare=develop, Title="MN: (요약)"

# B. Tag 생성
git switch main && git pull origin main
git tag -a v0.N.0 -m "MN: 완료 내용 요약"
git push origin --tags

# C. Milestone Close (GitHub 웹)
# Issues --> Milestones --> MN --> Close milestone

# D. Release 작성 (GitHub 웹)
# Releases --> Draft a new release --> Tag: v0.N.0
```

---

## 9. 비상 대응 Quick Reference

### 시나리오 1: AOSP 부팅 실패 --> Plan B 전환

| 항목 | 내용 |
|------|------|
| **발생 시점** | M2 4주차 (7월 말) |
| **판단 기준** | 3항목 중 1개라도 미충족: (1) 홈 화면 미표시 (2) `adb shell` 접속 불가 (3) `ip link show can0` 실패 |
| **즉시 조치** | ADR-010 작성 + Plan B 전환 결정 기록 |
| **팀원A 영향** | **코드 변경 0건** -- CAN 프레임 동일 |
| **팀원B 조치** | Ubuntu 22.04 설치, HIDL-->D-Bus/gRPC, Jetpack-->Qt/Flutter. HAL C++ 코드 재사용 |
| **ICD 영향** | S1~S2 CAN 규격 무변경, S3 HAL API만 D-Bus 인터페이스로 교체 |
| **참조** | `PLAN_팀원B.md` M2 S4~S5, `팀간_연계_분석.md` S6 시나리오 3 |

### 시나리오 2: CAN 물리 연결 실패 --> vcan0 우회

| 항목 | 내용 |
|------|------|
| **발생 시점** | M1 또는 M4 |
| **증상** | `dmesg | grep mcp251x` 출력 없음, `cansend can0` 실패 |
| **즉시 조치** | vcan0 가상 인터페이스로 전환하여 개발/테스트 계속 |
| **명령어** | `sudo modprobe vcan && sudo ip link add dev vcan0 type vcan && sudo ip link set vcan0 up` |
| **병렬 디버깅** | GPIO 25번 INT 핀 접촉 확인, 크리스탈 주파수(8/16MHz) 확인, SPI 활성화 확인 |
| **참조** | `PLAN_팀원A.md` M1 S2 트러블슈팅 |

### 시나리오 3: SecOC MAC 불일치

| 항목 | 내용 |
|------|------|
| **발생 시점** | M3 4주차 또는 M4 |
| **증상** | Node B 로그: `ERR_HMAC_VERIFY_FAIL` (정상 통신에서 발생) |
| **원인 후보** | (1) Python/C++ HMAC 입력 바이트 순서 불일치 (2) 키 파일 불일치 (3) 롤링 카운터 동기화 실패 |
| **즉시 조치** | |
| | 1. 양 노드 키 파일 해시 비교: `md5sum /etc/secoc/key.bin` |
| | 2. Python 테스트 벡터로 C++ 출력 교차 검증: `ctest -R test_secoc` |
| | 3. HMAC 입력 덤프: `CAN_ID(2B) || Counter(4B) || Payload(8B)` 바이트 순서 확인 |
| **참조** | `PLAN_팀원A.md` M3 S5, `팀간_연계_분석.md` S2 M3 SecOC 3단계 |

### 시나리오 4: IDS 탐지율 90% 미달

| 항목 | 내용 |
|------|------|
| **발생 시점** | M5 |
| **증상** | Ablation Config-3에서 Flooding 탐지율 < 90% |
| **즉시 조치** | |
| | 1. `contamination` 파라미터 조정: 0.01 --> 0.05 |
| | 2. `threshold` 재설정: decision_function 분포 분석 후 최적값 탐색 |
| | 3. 특징 벡터 확장: 7차원 --> payload entropy, DLC 분포 추가 |
| | 4. 정상 트래픽 수집량 증가: 30분 --> 60분+ |
| **발표 대응** | 결과를 투명 보고하되, "추가 튜닝으로 X% 개선 가능" 전망 제시. 분석 부재가 탐지율 미달보다 큰 문제 |
| **참조** | `팀간_연계_분석.md` S6 시나리오 4 |

### 시나리오 5: CI Coverage 80% 미달

| 항목 | 내용 |
|------|------|
| **발생 시점** | M4~M6 |
| **증상** | CI Stage 3 품질 게이트 실패, PR 머지 차단 |
| **즉시 조치** | |
| | 1. `lcov --list coverage_filtered.info` 로 미커버 파일 식별 |
| | 2. `genhtml` HTML 리포트에서 빨간 줄(미커버 라인) 확인 |
| | 3. 우선순위: Fail-safe Branch 100% --> 핵심 모듈 80% --> 유틸 코드 |
| | 4. Dead code 발견 시 삭제 (합의 후) |
| | 5. 외부 라이브러리 코드는 `lcov --remove`로 제외 |
| **참조** | `PLAN_공동.md` M6 S2, `팀간_연계_분석.md` S6 시나리오 5 |

---

## 부록 A. 전체 태그 & 릴리즈 계획

| Milestone | 월 | 태그 | Due Date | 핵심 완료 조건 |
|-----------|---|------|----------|---------------|
| M1: 환경 구축 | 6월 | `v0.1.0` | 2026-06-30 | ICD.md 확정, 개발 환경 동작, CI Stage 1, SRS.md 초안 |
| M2: CAN + HAL 기초 | 7월 | `v0.2.0` | 2026-07-31 | CAN CDD 실 송수신 (TC-BSW-001), HAL 뼈대, Plan A/B 결정 |
| M3: 핵심 로직 | 8월 | `v0.3.0` | 2026-08-31 | EKF 오차 <=3%, HMAC C++ 완성, Fail-safe Branch 100%, QEMU CI 녹색 |
| M4: 1차 통합 | 9월 | `v0.4.0` | 2026-09-30 | IT-001~005 전부 Pass, e2e 동작 영상, avg 레이턴시 <=50ms, 공격 탐지 1차 |
| M5: 보안 실험 | 10월 | `v0.5.0` | 2026-10-31 | Ablation Study 12세트 (4종 공격 × 3 Config), IDS 탐지율 >=90% |
| M6: 문서 완성 | 11월 | `v0.6.0` | 2026-11-30 | SDD 2종 최종화, TARA 최종화, CI 4단계 전체 녹색, Coverage >=80% |
| M7: 최종 검증 | 12월 | `v0.7.0` | 2026-12-31 | IT-001~005 재검증 Pass, ICD↔구현 불일치 0건, 실험 보고서 완성 |
| M8: 발표 준비 | 1월 | `v1.0.0` | 2027-01-31 | 최종 보고서, 발표 자료, 리허설 3회, GitHub 정리 완료 |

## 부록 B. 문서 참조 매트릭스

프로젝트의 주요 설계 문서와 각 파일의 참조 관계를 정리한다.

| 문서 | 위치 | 주 작성자 | 참조하는 PLAN |
|------|------|----------|-------------|
| `ICD.md` | `docs/` | 팀원A 초안, 공동 확정 | 4개 파일 모두 |
| `SRS.md` | `docs/` | 공동 | `PLAN_공동.md` M1 S4 |
| `SDD-ECU.md` | `docs/` | 팀원A | `PLAN_팀원A.md` M6 |
| `SDD-IVI.md` | `docs/` | 팀원B | `PLAN_팀원B.md` M6 |
| `ADR.md` | `docs/` | 공동 | `PLAN_공동.md` M1/M5/M6 |
| `TARA.md` | `docs/` | 팀원A | `PLAN_팀원A.md` M4/M5 |
| `TEST_PLAN.md` | `docs/` | 공동 | `PLAN_공동.md` M7 |
| `CICD_SPEC.md` | `docs/` | 팀원B | `PLAN_팀원B.md` M6 |
| `ROADMAP.md` | `docs/` | 공동 | 월별/주차별 마스터 체크리스트, 마일스톤 & 태그 계획, 주별 동기화 미팅 로그 — `tmp/` 4개 파일의 권위 있는 일정 소스 |

## 부록 C. 프로젝트 성공의 4대 기둥

참조: `팀간_연계_분석.md` S10

```
+---------------------------------------------------------+
|            프로젝트 성공의 4대 기둥                         |
|                                                         |
|  (1) ICD-First           (2) Mock/Stub                  |
|  +------------+          +------------+                  |
|  | 계약을 먼저 |          | 독립 개발  |                  |
|  | 확정하여    |          | 가능하게   |                  |
|  | 병렬 개발   |          | 하는 추상  |                  |
|  | 기반 마련   |          | 화 레이어  |                  |
|  +------------+          +------------+                  |
|                                                         |
|  (3) Cross-Review        (4) CI/CD Safety Net           |
|  +------------+          +-----------------+             |
|  | 상호 검증  |          | 자동 빌드/테스트 |             |
|  | 으로 품질  |          | /배포로 통합    |             |
|  | 보증       |          | 품질을 객관적   |             |
|  |            |          | 으로 보증       |             |
|  +------------+          +-----------------+             |
+---------------------------------------------------------+
```

(1) **ICD-First**: M1에서 CAN 바이트 레벨 규격 확정 --> 3개월 독립 개발 기반  
(2) **Mock/Stub**: MockCanDriver(A) + VehicleHalMock(B)로 상대 코드 없이 100% 테스트  
(3) **Cross-Review**: 모든 PR + 설계 문서를 상대방이 리뷰. 본인 PR 직접 머지 금지  
(4) **CI/CD Safety Net**: 4단계 파이프라인으로 Coverage 80%+ 자동 보증

---

> **이 가이드 시스템의 사용 원칙**: 매일 작업 전 본 INDEX.md의 해당 월 Quick Reference를 확인하고, 자신의 PLAN 파일에서 상세 절차를 따른다. 공동 작업이나 마일스톤 처리는 `PLAN_공동.md`를, 발표 준비는 `팀간_연계_분석.md`를 참조한다. 의존성 문제 발생 시 Critical Path 요약과 비상 대응을 먼저 참조한다.
