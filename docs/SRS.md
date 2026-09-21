> **문서명**: Software Requirements Specification (SRS)  
> **버전**: v1.5 | **작성일**: 2026-03-01 | **최종 수정**: 2026-09-08  
> **작성자**: 팀원A + 팀원B (공동)  
> **참조**: ICD v1.4, ADR-003 (IDS 알고리즘), ADR-005 (EKF), ADR-008 (Ablation Study)  
> **표기**: 필수=Must Have / 권장=Should Have / 선택=Nice to Have

---

# 1. 기능 요구사항 (Functional Requirements)

## 1.1. ECU / BSW 계층 (Node A)

| ID | 요구사항 | 우선순위 | 검증 방법 |
| --- | --- | --- | --- |
| FR-BSW-001 | CAN CDD는 Linux SocketCAN API(PF_CAN, SOCK_RAW)를 통해 can0 인터페이스에서 CAN 프레임을 송수신해야 한다. | 필수 | 단위 테스트: loopback 모드에서 송신한 프레임이 수신되는지 확인 |
| FR-BSW-002 | CAN CDD는 추상 인터페이스(CanDriver 클래스)를 제공하여 HW가 교체되어도 상위 코드가 수정되지 않아야 한다. | 필수 | Mock 구현체로 대체 시 상위 코드 컴파일 및 테스트 통과 확인 |
| FR-BSW-003 | CAN CDD는 비동기 수신 스레드를 운영하며, 프레임 도착 시 등록된 콜백을 호출해야 한다. | 필수 | 콜백 호출 횟수 카운터로 검증 |
| FR-BSW-004 | ara::com Publisher<T>는 Send() 호출 시 등록된 모든 Subscriber에게 데이터를 전달해야 한다. | 필수 | 3개 Subscriber 등록 후 Send() 호출, 전체 수신 확인 |
| FR-BSW-005 | ara::com은 다중 스레드에서 동시 접근 시 데이터 손상 없이 동작해야 한다. | 필수 | 10개 스레드 동시 Send()/Subscribe() 호출, race condition 없음 확인 |
| FR-BSW-006 | WatchdogManager는 BSW 태스크(BMS 계산, CAN 수신)의 응답을 1초 주기로 감시하고, 3초 타임아웃 시 해당 스레드 재시작을 시도해야 한다. | 필수 | 의도적 태스크 지연(4초) 주입 → 3초 후 재시작 시도 확인, 최대 3회 재시도 후 Fail-safe WARNING 전이 확인 |
| FR-BSW-007 | SensorSimulator는 CONSTANT, PROFILE_CSV, RANDOM_WALK, ADS1115_HARDWARE 4가지 입력 모드를 지원하고, 실행 시 모드를 선택할 수 있어야 한다. 이외의 모드는 정의하지 않는다. | 필수 | 각 모드별 `next()` 호출 시 유효 범위 내 SensorData 반환 확인 |

## 1.2. BMS SW 컴포넌트 (Node A)

| ID | 요구사항 | 우선순위 | 검증 방법 |
| --- | --- | --- | --- |
| FR-BMS-001 | EKF 기반 SOC 추정은 관측 모델(OCV-SOC 관계식)과 예측 모델(쿨롱 카운팅)을 칼만 필터로 융합하여 계산해야 한다. | 필수 | 알려진 입력 시퀀스로 SOC 출력값 검증 |
| FR-BMS-002 | EKF SOC 추정은 단순 쿨롱 카운팅 대비 1시간 누적 오차가 감소해야 한다. | 필수 | 참 상태를 별도로 생성한 1시간 합성 시뮬레이션에서 동일 관측을 받은 두 방법의 RMSE·최대 오차 비교. NASA 재생·데이터 검증 및 실제 ADC/전달 시험과 분리(S-7=A) |
| FR-BMS-003 | SOH는 초기 용량 대비 현재 추정 용량 비율을 백분율로 산출해야 한다. 가상 용량 열화 입력으로 검증하며 누적 방전량은 별도 기록한다. | 필수 | 알려진 용량 열화 시나리오로 SOH 출력값 검증 |
| FR-BMS-004 | Fail-safe 상태머신은 4단계(NORMAL → WARNING → CRITICAL → SHUTDOWN) 전이를 지원해야 한다. | 필수 | 모든 상태 전이 경로 단위 테스트 (Branch 100%) |
| FR-BMS-005 | SOC < 5% 조건에서 WARNING → CRITICAL 전이를 0x101/0x103으로 인증하여 Node B에 통보해야 한다. 필수 범위는 가상 배터리 상태 통보이며 실제 방전 차단을 요구하지 않는다. | 필수 | SOC=4.5% 입력 시 전이 발생 + CAN 메시지 송신 확인 |
| FR-BMS-006 | 온도 > 60°C 조건에서 SHUTDOWN 전이를 0x101/0x103으로 인증하여 Node B에 통보해야 한다. 필수 범위는 가상 배터리 상태 통보이며 실제 전류 제한을 요구하지 않는다. | 필수 | 온도=61°C 입력 시 전이 발생 + CAN 메시지 송신 확인 |
| FR-BMS-007 | Fail-safe 상태 전이 이벤트는 CAN ID 0x101로 Node B에 실시간 통보되어야 한다. | 필수 | 전이 발생 후 candump으로 0x101 수신 확인 |
| FR-BMS-008 | BMS 상태 데이터는 100ms 주기로 CAN ID 0x100으로 전송되어야 한다. | 필수 | candump 타임스탬프로 주기 편차 ±10ms 이내 확인 |

## 1.3. 보안 통신 (Node A ↔ Node B)

| ID | 요구사항 | 우선순위 | 검증 방법 |
| --- | --- | --- | --- |
| FR-SEC-001 | SecOC 모듈은 CAN 메시지 전송 시 HMAC-SHA256 서명을 4바이트로 절단하여 첨부해야 한다. | 필수 | 송신 MAC과 수동 계산 MAC 일치 확인 |
| FR-SEC-002 | 수신측은 HMAC 검증 실패 시 해당 메시지를 100% 폐기해야 한다. | 필수 | 변조된 MAC 전송 → 수신측 폐기 확인 (100회 전량 폐기) |
| FR-SEC-003 | 롤링 카운터의 수신 허용 여부는 [ICD §2.3~2.5](ICD.md#23-수신-검증-절차-node-b)의 현행 규칙으로 판정하고, 허용 범위 밖의 메시지는 폐기해야 한다 (Replay 방어). | 필수 | 동일 카운터 메시지 재전송 → 폐기 확인 |
| FR-SEC-004 | MAC 비교는 `hmac.compare_digest()` 또는 등가 방식을 사용하여 타이밍 공격을 방지해야 한다. | 필수 | 코드 리뷰로 constant-time 비교 사용 확인 |
| FR-SEC-005 | 4종 CAN 공격 시뮬레이터(Fuzzy/Replay/Spoofing/Flooding)를 구현하여 CLI로 공격 유형을 선택 실행할 수 있어야 한다. | 필수 | 각 공격 유형 실행 후 candump으로 공격 패턴 확인 |
| FR-SEC-006 | Isolation Forest IDS는 1초 슬라이딩 윈도우 기반으로 CAN 트래픽의 이상 점수를 실시간 계산해야 한다. | 필수 | 정상/공격 트래픽 혼합 입력 시 이상 점수 분리 확인 |
| FR-SEC-007 | IDS 공격 탐지 결과는 CAN ID 0x200으로 **Node B**에 전송되어야 한다. (IDS는 Node A에서 실행, ADR-009 참조) | 필수 | 공격 탐지 시 candump으로 0x200 수신 확인 |

## 1.4. IVI 플랫폼 (Node B)

| ID | 요구사항 | 우선순위 | 검증 방법 |
| --- | --- | --- | --- |
| FR-IVI-001 | Vehicle HAL은 CAN 수신 스레드를 상시 운영하며 새 프레임 도착 시 등록된 콜백을 호출해야 한다. | 필수 | CAN 전송 후 HAL 콜백 로그 확인 |
| FR-IVI-002 | Vehicle HAL은 CAN ID별(0x100, 0x101, 0x102, 0x103, 0x200)로 VehicleData를 정확히 파싱해야 한다. | 필수 | 알려진 페이로드 전송 후 파싱 결과 값 비교 |
| FR-IVI-003 | VehicleDataService는 `getSystemService("vehicle_data")`로 앱에서 접근 가능해야 한다. | 필수 | 테스트 앱에서 getSystemService 호출 성공 확인 |
| FR-IVI-004 | VehicleDataService는 HAL 콜백 → Binder IPC → 앱 ViewModel의 StateFlow 경로로 실시간 데이터를 전달해야 한다. | 필수 | 앱에서 StateFlow 수신 확인 |
| FR-IVI-005 | 대시보드 앱은 SOC를 원형 게이지로 표시하며 50% 이상=초록, 20~50%=주황, 20% 미만=빨강으로 표시해야 한다. | 필수 | UI 스크린샷으로 색상 코드 확인 |
| FR-IVI-006 | 공격 탐지 시 상단의 빨간 경보 배너와 공격 유형을 즉시 완전히 표시해야 한다. 효과는 장식 요소에만 허용하며 경고 인지를 지연시키지 않는다. 사용자 확인까지 유지하고 새 경보는 다시 표시한다. | 필수 | 공격 시뮬레이션 중 UI 스크린샷 확인 |
| FR-IVI-007 | CRITICAL/SHUTDOWN 상태 시 풀스크린 경고 팝업이 표시되어야 한다. | 필수 | Fail-safe 전이 시뮬레이션 후 팝업 표시 확인 |
| FR-IVI-008 | 대시보드 앱은 StateFlow + collectAsState()로 100ms 주기 CAN 데이터를 지연 없이 반영해야 한다. | 필수 | 레이턴시 측정 테스트 |

## 1.5. CI/CD 파이프라인

| ID | 요구사항 | 우선순위 | 검증 방법 |
| --- | --- | --- | --- |
| FR-CI-001 | main/develop 브랜치 Push 또는 PR 생성 시 GitHub Actions 파이프라인이 자동 실행되어야 한다. | 필수 | PR 생성 후 파이프라인 자동 기동 확인 |
| FR-CI-002 | Stage 1: cppcheck 정적 분석에서 Critical/Error 발견 시 파이프라인이 즉시 중단되어야 한다. | 필수 | 의도적 버그 코드 커밋 후 중단 확인 |
| FR-CI-003 | Stage 2: Docker 컨테이너에서 ARM64 크로스컴파일 빌드가 성공해야 한다. | 필수 | 빌드 산출물이 ARM64 바이너리인지 `file` 명령어로 확인 |
| FR-CI-004 | Stage 3: GoogleTest 단위 테스트 + lcov 커버리지 측정이 자동 실행되어야 한다. | 필수 | Codecov 리포트 자동 생성 확인 |
| FR-CI-005 | Stage 4: main 브랜치 머지 시 SCP/SSH로 라즈베리파이에 자동 배포되어야 한다. | 필수 | 머지 후 RPi에서 새 바이너리 실행 확인 |
| FR-CI-006 | 배포 후 Health Check로 서비스 정상 기동이 자동 확인되어야 한다. | 필수 | 배포 로그에서 health check 결과 확인 |

---

# 2. 비기능 요구사항 (Non-Functional Requirements)

## 2.1. 성능 (Performance)

| ID | 요구사항 | 목표값 | 측정 방법 |
| --- | --- | --- | --- |
| NFR-PERF-001 | CAN 수신 → Android UI 반영 end-to-end 레이턴시 | 평균 50ms 이하, 최대 100ms 이하 | 타임스탬프 차이 측정 (1000회 샘플링) |
| NFR-PERF-002 | BMS 데이터 CAN 전송 주기 정확도 | 100ms ± 10ms | candump 타임스탬프 편차 분석 |
| NFR-PERF-003 | IDS 탐지 응답 시간 (공격 시작 → 경보 전송) | 3초 이하 | 공격 시작 시점 ~ 0x200 수신 시점 차이 |

## 2.2. 보안 (Security)

| ID | 요구사항 | 목표값 |
| --- | --- | --- |
| NFR-SEC-001 | HMAC 검증 실패 메시지 폐기율 | 100% |
| NFR-SEC-002 | Replay 공격(동일 카운터 재전송) 차단율 | 100% |
| NFR-SEC-003 | IDS 공격별 탐지율 (Fuzzy/Replay/Spoofing/Flooding) | 각 90% 이상 (요구 목표 유지, 실측은 별도 결과에 기록) |
| NFR-SEC-004 | IDS 오탐율 (정상 트래픽 오탐지) | 5% 이하 (목표) |

## 2.3. 품질 (Quality)

| ID | 요구사항 | 목표값 |
| --- | --- | --- |
| NFR-QA-001 | C++ 실행 가능 소스 줄 커버리지 (Line Coverage) | 80% 이상 |
| NFR-QA-002 | Fail-safe 상태머신 Branch Coverage | 100% |
| NFR-QA-003 | cppcheck Critical/Error 건수 | 0건 |
| NFR-QA-004 | 코드 리뷰 완료율 (PR 기준) | 100% (merge 전 반드시 리뷰 완료) |

## 2.4. 신뢰성 (Reliability)

| ID | 요구사항 | 설명 |
| --- | --- | --- |
| NFR-REL-001 | WatchdogManager는 BSW 태스크 응답 타임아웃을 감시하고, 타임아웃 시 복구 절차를 실행해야 한다. | 감시 주기 1초, 타임아웃 3초 |
| NFR-REL-002 | CAN 수신 스레드 이상 종료 시 자동 재시작되어야 한다. | 최대 3회 재시도 후 실패 로그 |

## 2.5. NFR 목표값 근거

| NFR ID | 목표값 | 설정 근거 |
|--------|--------|-----------|
| NFR-PERF-001 | 평균 50ms / 최대 100ms | CAN 100ms 주기를 기준으로 정한 프로젝트 UI 응답 목표. 인간 인지 한계를 실측한 값이 아님 |
| NFR-PERF-002 | 100ms ± 10ms | 프로젝트가 정한 공칭 주기 대비 ±10% 목표. 외부 표준의 의무 수치로 주장하지 않음 |
| NFR-PERF-003 | ≤3초 | 1초 윈도우 기반 탐지·송수신에 할당한 프로젝트 응답 목표. 3회 관측을 필수로 뜻하지 않으며 실측으로 판정 |
| NFR-SEC-003 | ≥90% | 프로젝트 공격별 탐지 목표. 특정 논문의 실측이나 학술대회 공통 합격선으로 주장하지 않음 |
| NFR-SEC-004 | ≤5% | 정상 CAN 트래픽에서 100개 윈도우 중 5개 이하 오탐 허용 (운전자 경보 피로도 최소화) |
| NFR-QA-001 | ≥80% | S-8=B로 승인한 프로젝트 C++ Line Coverage 목표; 외부 표준이 이 수치를 의무화한다고 주장하지 않음 |
| NFR-QA-002 | 100% | 프로젝트 Fail-safe 로직의 전체 분기 검증 목표. ISO 26262 인증·ASIL 충족을 뜻하지 않음 |

---

# 3. 요구사항 추적 매트릭스 (Traceability Matrix)

2026-09-08 파일 대조. 아래 경로는 **존재**와 **예정**을 구분한다. 소스 존재는 요구 충족/시험 통과가 아니다. 49개 요구의 역할 과제·인계 연결은 [공동 의존성 §10](../plan/detail/common/01_연계_의존성.md#10-공식-요구사항에서-수행검증까지의-매핑)을 따른다.

| 요구사항 ID | SDD 섹션 | 소스 코드 모듈 | 테스트 케이스 ID |
| --- | --- | --- | --- |
| FR-BSW-001 | SDD-ECU 3.2 CAN CDD | 존재: `adaptive_ecu/src/bsw/can_cdd.cpp` | TC-BSW-001 |
| FR-BSW-002 | SDD-ECU 3.2 CAN CDD | 존재: `adaptive_ecu/include/can_driver.h` | TC-BSW-002 |
| FR-BSW-003 | SDD-ECU 3.2 CAN CDD | 존재: `adaptive_ecu/src/bsw/can_cdd.cpp` | TC-BSW-003 |
| FR-BSW-004 | SDD-ECU 3.3 ara::com | 존재: `adaptive_ecu/include/publisher.h` | TC-BSW-004 |
| FR-BSW-005 | SDD-ECU 3.3 ara::com | 존재: `adaptive_ecu/include/publisher.h` | TC-BSW-005 |
| FR-BMS-001 | SDD-ECU 3.4 BMS | 존재: `adaptive_ecu/src/app/ekf_soc_estimator.cpp` | TC-BMS-001 |
| FR-BMS-002 | SDD-ECU 3.4 BMS | 존재: `adaptive_ecu/src/app/ekf_soc_estimator.cpp` | TC-BMS-002 |
| FR-BMS-003 | SDD-ECU 3.4 BMS | 존재: `adaptive_ecu/src/app/soh_estimator.cpp` | TC-BMS-003 |
| FR-BMS-004 | SDD-ECU 3.4 BMS | 존재: `adaptive_ecu/src/app/failsafe_sm.cpp` | TC-BMS-004 |
| FR-BMS-005 | SDD-ECU 3.4 BMS | 존재: `adaptive_ecu/main.cpp`, `adaptive_ecu/src/app/failsafe_sm.cpp`, `adaptive_ecu/src/bsw/can_publisher.cpp` | TC-BMS-005 |
| FR-BMS-006 | SDD-ECU 3.4 BMS | 존재: `adaptive_ecu/main.cpp`, `adaptive_ecu/src/app/failsafe_sm.cpp`, `adaptive_ecu/src/bsw/can_publisher.cpp` | TC-BMS-006 |
| FR-BMS-007 | SDD-ECU 3.4 BMS | 존재: `adaptive_ecu/main.cpp`, `adaptive_ecu/src/app/failsafe_sm.cpp`, `adaptive_ecu/src/bsw/can_publisher.cpp` | TC-INT-003 |
| FR-BMS-008 | SDD-ECU 3.4.4 CAN Publisher | 존재: `adaptive_ecu/src/bsw/can_publisher.cpp` | TC-BMS-007 |
| FR-SEC-001 | SDD-ECU 3.5 SecOC | 존재: `adaptive_ecu/src/bsw/secoc_module.cpp` | TC-SEC-001 |
| FR-SEC-002 | SDD-ECU 3.5 SecOC | 존재: `adaptive_ecu/src/bsw/secoc_module.cpp`; 수신 통합 예정: `ivi_platform/hal/secoc_verifier.cpp` | TC-SEC-002 |
| FR-SEC-003 | SDD-ECU 3.5 SecOC | 존재: `adaptive_ecu/src/bsw/secoc_module.cpp`; 수신 통합 예정: `ivi_platform/hal/secoc_verifier.cpp` | TC-SEC-003 |
| FR-SEC-004 | SDD-ECU 3.5 SecOC | 존재: `adaptive_ecu/src/bsw/secoc_module.cpp`; 수신 통합 예정: `ivi_platform/hal/secoc_verifier.cpp` | TC-SEC-004 |
| FR-SEC-005 | SDD-ECU 3.8 공격 시뮬레이터 | 존재: `security/attacks/traffic_gen.py` (합성); 예정: `security/attack_simulator.py`, 실 CAN 공격 CLI | TC-SEC-005 |
| FR-SEC-006 | SDD-ECU 3.9 IDS 엔진 | 존재: `security/ids/if_detector.py`, `security/ids/feature_extractor.py`; 예정: 실시간 수집·모델 로드 루프 | TC-SEC-006 |
| FR-SEC-007 | SDD-ECU 3.9.4 IDS 실행 환경 | 예정: `security/ids/ids_alerter.py` | TC-SEC-007 |
| FR-IVI-001 | SDD-IVI 4.2 HAL | 예정: `ivi_platform/hal/vehicle_hal_impl.cpp` | TC-IVI-001 |
| FR-IVI-002 | SDD-IVI 4.2 HAL | 예정: `ivi_platform/hal/can_parser.cpp` | TC-IVI-002 |
| FR-IVI-003 | SDD-IVI 4.3 Service | 예정: `ivi_platform/service/VehicleDataService.java` | TC-IVI-003 |
| FR-IVI-004 | SDD-IVI 4.3 Service | 예정: `ivi_platform/service/VehicleDataService.java` | TC-IVI-004 |
| FR-IVI-005 | SDD-IVI 4.4 App | 예정: `ivi_platform/app/SocGauge.kt` | TC-IVI-005 |
| FR-IVI-006 | SDD-IVI 4.4 App | 예정: `ivi_platform/app/AlertBanner.kt` | TC-IVI-006 |
| FR-IVI-007 | SDD-IVI 4.4 App | 예정: `ivi_platform/app/DashboardScreen.kt` | TC-IVI-007 |
| FR-IVI-008 | SDD-IVI 4.4 App | 예정: `ivi_platform/app/DashboardViewModel.kt` | TC-IVI-008 |
| FR-CI-001 | CICD_SPEC §2.1 | 예정: `.github/workflows/ci.yml` | TC-CI-001 |
| FR-CI-002 | CICD_SPEC §2.2 | 예정: `.github/workflows/ci.yml` | TC-CI-002 |
| FR-CI-003 | CICD_SPEC §2.3 | 예정: `Dockerfile.arm64`, `toolchain-aarch64.cmake` | TC-CI-003 |
| FR-CI-004 | CICD_SPEC §2.4 | 예정: `.github/workflows/ci.yml` | TC-CI-004 |
| FR-CI-005 | CICD_SPEC §2.5 | 예정: `.github/workflows/ci.yml`, `scripts/health_check.sh` | TC-CI-005 |
| FR-CI-006 | CICD_SPEC §6 | 예정: `scripts/health_check.sh` | TC-CI-006 |
| FR-BSW-006 | SDD-ECU 3.6 Watchdog | 존재: `adaptive_ecu/src/bsw/watchdog_manager.cpp` | TC-BSW-006, TC-BSW-007 |
| FR-BSW-007 | SDD-ECU 3.7 SensorSimulator | 존재: `adaptive_ecu/src/app/sensor_simulator.cpp` | TC-BSW-008 |

## 3.1. 비기능 요구사항 추적 매트릭스

| NFR ID | 검증 방법 | 테스트 케이스 ID |
|--------|-----------|-----------------|
| NFR-PERF-001 | end-to-end 레이턴시 측정 (1000회) | TC-PERF-001 |
| NFR-PERF-002 | candump 타임스탬프 편차 분석 | TC-PERF-002 (직접), TC-BMS-007 (송신 통합) |
| NFR-PERF-003 | 공격 시작 ~ 0x200 수신 시점 차이 측정 | TC-PERF-003 (직접), TC-INT-004 (UI 통합) |
| NFR-SEC-001 | 변조 MAC 100회 전송 → 폐기 확인 | TC-SEC-002 |
| NFR-SEC-002 | 동일 카운터 재전송 → 폐기 확인 | TC-SEC-003 |
| NFR-SEC-003 | Ablation Study 4종 공격별 탐지율 | TC-EXP-001 ~ TC-EXP-004 |
| NFR-SEC-004 | 정상 트래픽 100윈도우 오탐율 | TC-EXP-005 |
| NFR-QA-001 | lcov C++ Line Coverage 리포트 | TC-CI-004 |
| NFR-QA-002 | Fail-safe Branch Coverage 100% | TC-BMS-004 |
| NFR-QA-003 | cppcheck Critical/Error 0건 | TC-CI-002 |
| NFR-QA-004 | PR 머지 전 리뷰 완료 확인 | (프로세스 검증) |
| NFR-REL-001 | Watchdog 타임아웃 → 복구 절차 실행 | TC-BSW-006, TC-BSW-007 |
| NFR-REL-002 | CAN 수신 스레드 이상 종료 → 재시작 | TC-BSW-006 (수신 복구), TC-BSW-007 (재시도 실패 하위 사례) |

---

# 4. 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| v1.0 | 2026-03-01 | 초안 작성 — FR-BSW/BMS/SEC/IVI/CI 전체, NFR-PERF/SEC/QA/REL | 팀원A, 팀원B |
| v1.1 | 2026-03-15 | FR-SEC-007 수정 — "IDS는 Node A에서 실행, 0x200을 Node B로 전송" 명시 (ADR-009 반영) | 팀원A |
| v1.2 | 2026-04-01 | NFR §2.5 목표값 근거 섹션 추가 | 팀원A |
| v1.3 | 2026-05-09 | FR-BSW-006 (WatchdogManager), FR-BSW-007 (SensorSimulator) 추가 + 추적 매트릭스 업데이트 | 팀원A, 팀원B |
| v1.4 | 2026-05-09 | FR-BSW-006 추적 매트릭스에 TC-BSW-007 추가, §3.1 NFR 추적 매트릭스 신규 작성 | 팀원A, 팀원B |
| v1.5 | 2026-09-06 | NFR-QA-003 검증 TC를 TC-CI-001→TC-CI-002로 정정 (TC-CI-001은 Actions 자동 기동, cppcheck는 TC-CI-002). FR-BSW-007에 모드 4종 한정 명시 | 팀원A, 팀원B |

## 승인된 범위 정합화 — S 서면 답변

2026-09-06 S-1=A·S-2=A에 따라 FR-IVI-006의 즉시 표시와 장식 효과, FR-BMS-005/006의 가상 배터리 상태 통보 범위를 정합화했다. 기존 ID와 임계값은 유지한다. 구현·실측 완료를 의미하지 않는다. 실제 보조배터리의 선택 시험은 별도 목적·계측 확인 후 수행한다.

S-3=A의 sensorState·stale 목표 계약은 [ICD §8](ICD.md#8-승인된-다음-전환-목표--s-3a-제품-반영-전)을 따른다. FR-BSW-007의 센서 취득, FR-IVI-002/004/008의 파싱·전달·표시에 품질 상태와 최초/복구 인수 시험을 연결한다. 현 구현과 목표 계약의 전환은 동기화 과제로 남아 있다.

2026-09-08 종합 정합성 검토: 현재/예정 경로, 승인 상태, 단위·측정·실행 예제를 대조·정정했다. 세부 변경과 보류 관문은 [종합 검토](development/reviews/문서_종합정합성_검토.md)에 기록한다. 기존 요구/TC ID와 ICD 계약 본문은 보존했다.


## 2026-09-09 승인된 SecOC 현행 규칙 정정

현행 고정키 수신 규칙은 [ICD §2.3~2.5](ICD.md#23-수신-검증-절차-node-b)를 따른다. 단순 대소 비교나 범위 밖 유효 MAC만으로 counter를 재동기화하는 이전 설명은 적용하지 않는다. 실제 C++/Python verify는 이 정정과 일치하며 알고리즘 변경은 없다. 첫 수신 MAC 성공은 새 부팅을 증명하지 못하고, 수신기 재부팅 후 과거 메시지 수락 위험이 남는다. 요구사항의 replay 방어 기준을 낮추거나 전체 보안 인수를 완료 처리하지 않는다.

인증 세션 자동 복구의 승인된 방향은 유지한다. 세션 상세 계약·양측 전환·재부팅 보안 시험은 [세션 설계안](development/security/CAN_세션인증_설계안.md)의 별도 관문이다. 새 wire·키 파생·HAL 변경을 이번 정정 승인으로 포함하지 않는다.
