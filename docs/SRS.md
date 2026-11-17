> **문서명**: Software Requirements Specification (SRS)  
> **버전**: v1.7 | **작성일**: 2026-03-01 | **최종 수정**: 2026-11-11
> **작성자**: 팀원A + 팀원B (공동)  
> **참조**: ICD v1.6, ADR-003 (IDS 알고리즘), ADR-005 (EKF), ADR-008 (Ablation Study), ADR-010 (IVI Plan B)
> **표기**: 필수=Must Have / 권장=Should Have / 선택=Nice to Have

---

# 1. 기능 요구사항 (Functional Requirements)

**2026-11-11 프로파일 전환:** 제품 `session-v2`는 [ICD 세션](ICD-CAN-SESSION.md)/[진단](ICD-CAN-DIAGNOSTIC.md)을 따른다. 아래 고정키·래핑/ID 목록은 `legacy-v1` 시험과 구분한다. FR-SEC-001~004는 새 세션의 키·전역 번호/소진·제한 정렬/거부, FR-SEC-006/007은 인증된 유형별 사건/관찰과 IF 준비 상태로 확장한다. FR-IVI-001~004/008은 신규 ID 수신/양방향 송신·상태 동기화·실제 단계/출처를 포함한다.0x200은 참고 경보이며 인증/전체 차단 증거가 아니다. 승인과 실제 구현/인수는 [CHG-029](aidlc/changes/CHG-029/aidlc-state.md)에서 구분한다.

자동 프로그램 복구는 계산/위험/시나리오를 보존하고 명시적 수동 새 시작은 계산/시연만 초기화한다. 인증된 종료 예고 ACK가 없어도 제한 대기 뒤 한 번 진행하며 보호 판단은 기다리지 않는다. 배선 단절 자체로 프로그램을 재시작하지 않는다. 프로그램 복구와 배터리 정상 복귀는 별개다. 유형별 사건의1초 상태 갱신·3초 관찰 손실·5초 연속 정상 관찰 초기 기준, 장기 이력·미측정/모호한 귀속 표시를 검증한다. 2026-11-11 사용자 결정으로 전원 부팅과 명시적 수동 재시작은 fresh 시연으로 계산을 초기화하고, 같은 감독 실행 중 자동 프로그램 재시작은 resume으로 보존한다. 보안 키와 사건 이력은 fresh 초기화 대상이 아니다. 운영 기한/자원 수치는 명시적으로 설정하고 실측 검증한다.

## 1.1. ECU / BSW 계층 (Node A)

| ID | 요구사항 | 우선순위 | 검증 방법 |
| --- | --- | --- | --- |
| FR-BSW-001 | CAN CDD는 Linux SocketCAN API(PF_CAN, SOCK_RAW)를 통해 can0 인터페이스에서 CAN 프레임을 송수신해야 한다. | 필수 | 단위 테스트: loopback 모드에서 송신한 프레임이 수신되는지 확인 |
| FR-BSW-002 | CAN CDD는 추상 인터페이스(CanDriver 클래스)를 제공하여 HW가 교체되어도 상위 코드가 수정되지 않아야 한다. | 필수 | Mock 구현체로 대체 시 상위 코드 컴파일 및 테스트 통과 확인 |
| FR-BSW-003 | CAN CDD는 비동기 수신 스레드를 운영하며, 프레임 도착 시 등록된 콜백을 호출해야 한다. | 필수 | 콜백 호출 횟수 카운터로 검증 |
| FR-BSW-004 | ara::com Publisher<T>는 Send() 호출 시 등록된 모든 Subscriber에게 데이터를 전달해야 한다. | 필수 | 3개 Subscriber 등록 후 Send() 호출, 전체 수신 확인 |
| FR-BSW-005 | ara::com은 다중 스레드에서 동시 접근 시 데이터 손상 없이 동작해야 한다. | 필수 | 10개 스레드 동시 Send()/Subscribe() 호출, race condition 없음 확인 |
| FR-BSW-006 | WatchdogManager는 BSW 태스크(BMS 계산, CAN 수신)의 응답을 1초 주기로 감시하고, 3초 타임아웃 시 해당 스레드 재시작을 시도해야 한다. | 필수 | 의도적 태스크 지연(4초) 주입 → 3초 후 재시작 시도 확인, 최대 3회 재시도 후 Fail-safe WARNING 전이 확인 |
| FR-BSW-007 | SensorSimulator는 CONSTANT, PROFILE_CSV, RANDOM_WALK, ADS1115_HARDWARE 4가지 기존 입력 모드를 지원하고 실행 시 선택할 수 있어야 한다. 선택형 physical 입력은 FR-BMS-009의 별도 취득 경로를 사용하고 Simulator의 `next()`로 가상값을 만들지 않는다. 미지원 모드는 거부한다. | 필수 | 기존 4모드의 `next()` 결과 검증 및 physical의 명시 설정·분리 취득 확인 |

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
| FR-SEC-007 | IDS는 Node A에서 실행하며 결과를 CAN으로 Node B에 전달한다. legacy-v1은0x200, 현행 session-v2는 승인된 인증 IncidentStatus/ObservationStatus 진단 계약을 따른다. | 필수 | legacy의0x200 시험과 session-v2의 완전한 인증 진단·의미 검증 시험을 구분한다. 기존 CAN 형식은 각 ICD를 유지한다 |

## 1.4. IVI 플랫폼 (Node B)

| ID | 요구사항 | 우선순위 | 검증 방법 |
| --- | --- | --- | --- |
| FR-IVI-001 | `SocketCanReceiver`는 CAN 수신 worker를 운영하고 0x100/101/102/103/200의 정상 Classic CAN 프레임을 등록된 콜백에 전달해야 한다. | 필수 | vcan 전송 후 콜백 횟수와 종료 동작 확인 |
| FR-IVI-002 | `CanParser`와 `SecOcVerifier`는 ICD에 따라 ID별 payload를 해석하고, 0x100/101은 대응 0x102/103의 MAC·counter 검증에 성공한 경우에만 게시해야 한다. | 필수 | 알려진 벡터, 변조 MAC, replay, wrap 경계 시험 |
| FR-IVI-003 | `VehicleDataService`는 최신 일관 snapshot 조회와 observer 등록/해제를 C++ API로 제공해야 한다. | 필수 | 서비스 단위 시험에서 snapshot과 observer 호출 확인 |
| FR-IVI-004 | 서비스는 Qt queued signal을 통해 `DashboardViewModel`의 `Q_PROPERTY`를 갱신해야 하며 수신 worker가 UI 객체를 직접 변경해서는 안 된다. | 필수 | thread affinity와 property 변경 signal 확인 |
| FR-IVI-005 | QML 대시보드는 SOC를 원형 게이지로 표시하며 50% 이상=초록, 20% 이상 50% 미만=주황, 20% 미만=빨강으로 표시해야 한다. | 필수 | Qt Quick UI 시험과 캡처로 확인 |
| FR-IVI-006 | 공격 탐지 보고 시 공격 유형을 중앙 경고로 표시하고, 닫으면 팝업만 사라지며 탐지 결과와 이력을 유지해야 한다. 새 경보 재표시와 같은 유형 반복 보고의 구분 기준을 인수해야 한다. | 필수 | QML 경보·ack 경쟁 시험 |
| FR-IVI-007 | CRITICAL/SHUTDOWN 상태 시 화면 위 중앙 위험 경고를 표시하고, 닫은 뒤에도 전체 화면 위험 테두리와 상태 카드를 유지해야 한다. 알림 닫기로 ECU 위험 상태를 해제하지 않는다. | 필수 | 상태 전이 주입 후 QML overlay 확인 |
| FR-IVI-008 | 대시보드는 100ms 주기 인증 데이터를 Qt property binding으로 반영하고 initial/invalid/stale 상태를 정상 측정값과 구분해야 한다. | 필수 | property 갱신 지연과 상태별 UI 시험 |

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
| NFR-PERF-001 | CAN 수신 → Qt/QML UI 반영 end-to-end 레이턴시 | 평균 50ms 이하, 최대 100ms 이하 | 타임스탬프 차이 측정 (1000회 샘플링) |
| NFR-PERF-002 | BMS 데이터 CAN 전송 주기 정확도 | 100ms ± 10ms | candump 타임스탬프 편차 분석 |
| NFR-PERF-003 | IDS 탐지 응답 시간 (프로토콜별 정의) | 3초 이하 | session-v2: IVI 최초 식별 가능한 공격 관찰→같은 유형/새 IncidentStatus 인증·의미 검증 완료. 같은 IVI boot/monotonic 시계로 측정. legacy-v1: 기존 공격 시작→0x200 수신을 별도 유지 |

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

2026-09-22 파일 대조. 아래 경로는 **존재**와 **예정**을 구분한다. 소스 존재는 요구 충족/시험 통과가 아니다. 49개 요구의 역할 과제·인계 연결은 [공동 의존성 §10](../plan/detail/common/01_연계_의존성.md#10-공식-요구사항에서-수행검증까지의-매핑)을 따른다.

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
| FR-SEC-005 | SDD-ECU 3.8 공격 시뮬레이터 | 존재: `security/attacks/traffic_gen.py`(합성), `security/attack_simulator.py`(제한형 실 CAN CLI) | TC-SEC-005 |
| FR-SEC-006 | SDD-ECU 3.9 IDS 엔진 | 존재: `security/ids/if_detector.py`, `security/ids/feature_extractor.py`, `security/ids/runtime.py`, `security/capture_normal.py` | TC-SEC-006 |
| FR-SEC-007 | SDD-ECU 3.9.4 IDS 실행 환경·현행 인증 진단 | 존재: legacy runtime의0x200, session의 `security/ids/incident_status.py`→ECU 진단 발행→IVI 인증/의미 검증 | TC-SEC-007 (legacy), TC-PERF-003 (session-v2) |
| FR-IVI-001 | SDD-IVI 3.1 SocketCanReceiver | 예정: `ivi_platform/hal/socketcan_receiver.cpp` | TC-IVI-001 |
| FR-IVI-002 | SDD-IVI 3.2~3.3 인증·파싱 | 예정: `ivi_platform/hal/can_parser.cpp`, `secoc_verifier.cpp` | TC-IVI-002 |
| FR-IVI-003 | SDD-IVI 3.4 Service | 예정: `ivi_platform/service/vehicle_data_service.cpp` | TC-IVI-003 |
| FR-IVI-004 | SDD-IVI 3.5 ViewModel | 예정: `ivi_platform/ui_qml/dashboard_view_model.cpp` | TC-IVI-004 |
| FR-IVI-005 | SDD-IVI 3.6 QML | 존재: `ivi_platform/ui_qml/qml/SocGauge.qml`, `ivi_platform/test/test_dashboard_security.cpp` | TC-IVI-005 |
| FR-IVI-006 | SDD-IVI 3.6 QML | 존재: `ivi_platform/ui_qml/qml/Main.qml`, `dashboard_view_model.cpp` | TC-IVI-006 |
| FR-IVI-007 | SDD-IVI 3.6 QML | 존재: `ivi_platform/ui_qml/qml/Main.qml`, `dashboard_view_model.cpp` | TC-IVI-007 |
| FR-IVI-008 | SDD-IVI 3.4~3.6 | 예정: `ivi_platform/ui_qml/dashboard_view_model.cpp`, `qml/Main.qml` | TC-IVI-008 |
| FR-CI-001 | CICD_SPEC §2.1 | 예정: `.github/workflows/ci.yml` | TC-CI-001 |
| FR-CI-002 | CICD_SPEC §2.2 | 예정: `.github/workflows/ci.yml` | TC-CI-002 |
| FR-CI-003 | CICD_SPEC §2.3 | `Dockerfile.arm64`, `toolchain-aarch64.cmake`, `tools/quality/cross_build.py` (remote acceptance pending) | TC-CI-003 |
| FR-CI-004 | CICD_SPEC §2.4 | 예정: `.github/workflows/ci.yml` | TC-CI-004 |
| FR-CI-005 | CICD_SPEC §2.5 | `tools/deployment/release.py` (local transaction; main SSH deployment pending) | TC-CI-005 |
| FR-CI-006 | CICD_SPEC §6 | `scripts/health_check.sh`, `tools/deployment/health.py` (Pi acceptance pending) | TC-CI-006 |
| FR-BSW-006 | SDD-ECU 3.6 Watchdog | 존재: `adaptive_ecu/src/bsw/watchdog_manager.cpp` | TC-BSW-006, TC-BSW-007 |
| FR-BSW-007 | SDD-ECU 3.7 SensorSimulator | 존재: `adaptive_ecu/src/app/sensor_simulator.cpp` | TC-BSW-008 |

## 3.1. 비기능 요구사항 추적 매트릭스

| NFR ID | 검증 방법 | 테스트 케이스 ID |
|--------|-----------|-----------------|
| NFR-PERF-001 | end-to-end 레이턴시 측정 (1000회) | TC-PERF-001 |
| NFR-PERF-002 | candump 타임스탬프 편차 분석 | TC-PERF-002 (직접), TC-BMS-007 (송신 통합) |
| NFR-PERF-003 | session-v2 IVI 동일 시계의 식별 가능한 공격 관찰→새 사건 의미 검증; legacy0x200은 별도 | TC-PERF-003 (프로토콜별), TC-INT-004 (UI 별도) |
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

## 선택형 실측 입력 요구사항 — 2026-11-17

- **FR-BMS-009:** 명시적으로 선택한 `physical` 모드는 INA219 전압/전류와 DS18B20 온도를 별도 프로세스에서 취득하고 실제 시간 간격으로 누적Ah/Wh·명시 초기값 기반SOC를 계산한다. 초기SOC/독립 용량시험이 없으면SOC/SOH를 미산정으로 유지한다. 오류/공백/신선도를 분리하며 가상10셀/50Ah로 대체하지 않는다. 기존 FR-BMS-008의100ms/0x100 송신은 기존 가상/ADS1115 경로에 유지하고 새 모드는 승인된 인증 진단 종류9를 따른다.
- **FR-IVI-009:** 동일 앱이 현재 인증 세션·NodeStatus instance·설정·순번·채널 나이를 확인한 종류9를 소비한다. 전압/전류/온도와SOC/SOH를 독립적으로 표시하며 미산정·무효 채널은 `--`다. 현재 실측 모드의 미구성 보호를NORMAL/자동 차단 완료로 표현하지 않는다.
- 추적: FR-BMS-009→SDD-ECU의CHG-031 후속 연결→TC-PHYS-001/002/003/005; FR-IVI-009→SDD-IVI의단셀 표시→TC-PHYS-003/004/005. 물리 정확도·배선 재현성·실제 부하 종료 인수는TC-PHYS-006이며 소프트웨어 시험으로 대체하지 않는다.

# 4. 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| v1.0 | 2026-03-01 | 초안 작성 — FR-BSW/BMS/SEC/IVI/CI 전체, NFR-PERF/SEC/QA/REL | 팀원A, 팀원B |
| v1.1 | 2026-03-15 | FR-SEC-007 수정 — "IDS는 Node A에서 실행, 0x200을 Node B로 전송" 명시 (ADR-009 반영) | 팀원A |
| v1.2 | 2026-04-01 | NFR §2.5 목표값 근거 섹션 추가 | 팀원A |
| v1.3 | 2026-05-09 | FR-BSW-006 (WatchdogManager), FR-BSW-007 (SensorSimulator) 추가 + 추적 매트릭스 업데이트 | 팀원A, 팀원B |
| v1.4 | 2026-05-09 | FR-BSW-006 추적 매트릭스에 TC-BSW-007 추가, §3.1 NFR 추적 매트릭스 신규 작성 | 팀원A, 팀원B |
| v1.6 | 2026-09-22 | FR-IVI-001~008과 추적 경로를 C++/Qt Plan B로 전환 | 팀원B |
| v1.5 | 2026-09-06 | NFR-QA-003 검증 TC를 TC-CI-001→TC-CI-002로 정정 (TC-CI-001은 Actions 자동 기동, cppcheck는 TC-CI-002). FR-BSW-007에 모드 4종 한정 명시 | 팀원A, 팀원B |

## 승인된 범위 정합화 — S 서면 답변

2026-09-06 S-1=A·S-2=A에 따라 FR-IVI-006의 즉시 표시와 장식 효과, FR-BMS-005/006의 가상 배터리 상태 통보 범위를 정합화했다. 기존 ID와 임계값은 유지한다. 구현·실측 완료를 의미하지 않는다. 실제 보조배터리의 선택 시험은 별도 목적·계측 확인 후 수행한다.

S-3=A의 sensorState·stale 목표 계약은 [ICD §8](ICD.md#8-승인된-다음-전환-목표--s-3a-제품-반영-전)을 따른다. FR-BSW-007의 센서 취득, FR-IVI-002/004/008의 파싱·전달·표시에 품질 상태와 최초/복구 인수 시험을 연결한다. 현 구현과 목표 계약의 전환은 동기화 과제로 남아 있다.

2026-09-08 종합 정합성 검토: 현재/예정 경로, 승인 상태, 단위·측정·실행 예제를 대조·정정했다. 세부 변경과 보류 관문은 [종합 검토](development/reviews/문서_종합정합성_검토.md)에 기록한다. 기존 요구/TC ID와 ICD 계약 본문은 보존했다.


## 2026-09-09 승인된 SecOC 현행 규칙 정정

현행 고정키 수신 규칙은 [ICD §2.3~2.5](ICD.md#23-수신-검증-절차-node-b)를 따른다. 단순 대소 비교나 범위 밖 유효 MAC만으로 counter를 재동기화하는 이전 설명은 적용하지 않는다. 실제 C++/Python verify는 이 정정과 일치하며 알고리즘 변경은 없다. 첫 수신 MAC 성공은 새 부팅을 증명하지 못하고, 수신기 재부팅 후 과거 메시지 수락 위험이 남는다. 요구사항의 replay 방어 기준을 낮추거나 전체 보안 인수를 완료 처리하지 않는다.

인증 세션 자동 복구의 승인된 방향은 유지한다. 세션 상세 계약·양측 전환·재부팅 보안 시험은 [세션 설계안](development/security/CAN_세션인증_설계안.md)의 별도 관문이다. 새 wire·키 파생·HAL 변경을 이번 정정 승인으로 포함하지 않는다.

2026-11-10 사용자 앱형 UI 결정에 따라 FR-IVI-006/007의 표시 방식을 중앙 팝업·닫기 후 상태/이력 유지로 갱신했다. [CHG-028](aidlc/changes/CHG-028/evidence.md). 실제 새 공격 사건 식별/같은 유형 재알림 인수는 추가 연결 결정사항으로 남는다. CAN/SecOC 계약은 변경하지 않는다.


### 2026-11-11 FR-BMS-006 과열 보호 복귀 정책 변경

과열 SHUTDOWN은 ECU 프로그램 재시작을 유발하지 않는다. 실행과 입력 감시를 유지하고 유효 온도≤55°C가 5초 연속 확인되면 과열 보호를 해제한다. 오류·관찰 공백·시각 역행·재상승 시 연속 구간을 무효화하며 저전압 CRITICAL 이력과 현재 SOC 위험은 보존한다. 자동 재시작은 프로그램 비정상 종료/정체에 대한 별도 복구다. 기준은 가상 배터리 시연 정책이며 실제 셀 안전 인증을 의미하지 않는다. 전이와 간격 정의는 ICD를 따른다.

### 2026-11-14 재시작 전후 보호 사건 연결

자동 프로그램 복구 시 계산 상태와 보호 사건 식별정보를 마지막 저장 완료 checkpoint에서 함께 복원하고, 새 인증 세션으로 전달해 IVI의 기존 사건 이력을 잇는다. 수동 fresh는 새 계산 계보를 시작하며 이전 사건을 정상 종료로 만들지 않는다. 기존 기록 복원/현재 위험 표시만으로 동일 사건 연결을 완료 처리하지 않는다. 세부 계약은 [종류8 ProtectionStatus](ICD-CAN-DIAGNOSTIC.md)이며 과열 대기/복귀·프로그램 복구 분리 정책은 유지한다. 구현/검증 현황은 CHG-029를 따르며 승인 자체는 제품 인수 증거가 아니다.


2026-11-16 R03=A 적용: session-v2 응답 계측의 미탐지·3초 초과·시계/관찰 손실·모호한 Replay 시작을 보존한다. 화면 렌더 완료는 인증 사건 검증과 별도로 평가한다. 새 정의의 채택이 물리 Pi 성능 합격을 뜻하지 않는다. R04=A의 저장/종료·확인 대기는 실제 Pi 계측 후 기존 명세 안에서 산정·기록하며, 기존 태스크1초/3초/1초/3회·배터리 기준·보안 계약을 바꾸지 않는다.
