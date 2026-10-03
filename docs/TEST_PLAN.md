# Test Plan — 소프트웨어 검증 계획

> **문서 버전**: v1.6 | **작성일**: 2026-03-15 | **최종 수정**: 2026-09-23
> **참조**: SRS v1.6 (요구사항 추적), ICD v1.6, SDD-ECU v1.6, SDD-IVI v2.2, TARA v1.2 (위협 시나리오 → Ablation Study)
> **테스트 프레임워크**: GoogleTest (C++), pytest (Python), Qt Test (C++), Qt Quick Test (QML)
> **커버리지 도구**: gcov / lcov (C++), pytest-cov (Python)  
> **품질 게이트** (프로젝트 승인 기준, S-8=B): C++ Line ≥80%, Fail-safe Branch 100%, cppcheck 0건

---

## 목차

1. [테스트 전략](#1-테스트-전략)
2. [단위 테스트 — Node A (C++)](#2-단위-테스트--node-a-c)
3. [단위 테스트 — 보안 모듈 (Python)](#3-단위-테스트--보안-모듈-python)
4. [단위 테스트 — Node B (C++/Qt)](#4-단위-테스트--node-b-cqt)
5. [통합 테스트 — end-to-end CAN 통신](#5-통합-테스트--end-to-end-can-통신)
6. [보안 실험 테스트 (Ablation Study)](#6-보안-실험-테스트-ablation-study)
7. [성능 테스트](#7-성능-테스트)
8. [CI 품질 게이트 정책](#8-ci-품질-게이트-정책)
9. [변경 이력](#9-변경-이력)

---

## 1. 테스트 전략

2026-09-23 정적 대조: 이 문서는 인수 명세이며 표에 적힌 기대 결과 자체가 실행 결과는 아니다. C++ 파일 `test/`, `data/`는 기본적으로 `adaptive_ecu/` 기준이고 IVI 시험은 명시한 `ivi_platform/test/` 기준이다. `test_can_cdd.cpp`, `test_bms_component.cpp`, 1시간 CSV, 실 CAN 공격/IDS 시험과 CI는 아직 없다. IVI P1~P4 core·Qt·vcan 시험의 실제 결과만 §4의 별도 기록과 CHG-003 증거를 따른다. API를 축약한 assertion은 시험 의도이며 실제 헤더에 없는 메서드를 구현돼 있다고 가정하지 않는다.

### 1.1. 테스트 레벨

| 레벨 | 대상 | 도구 | 실행 환경 |
|------|------|------|-----------|
| 단위 테스트 | 개별 함수/클래스 | GoogleTest, pytest | 현재 호스트 시험 가능 여부 확인; GitHub Actions/QEMU ARM64는 예정 |
| 통합 테스트 | CAN 버스 end-to-end | candump, python-can | 실 RPi4 2대 (물리 CAN 연결) |
| 보안 실험 | 4종 공격 × 3가지 방어 구성 | attack_simulator.py | 실 RPi4 환경 (Ablation Study) |
| 성능 테스트 | 레이턴시, 주기 정확도 | 타임스탬프 측정 스크립트 | 실 RPi4 환경 |

### 1.2. 테스트 ID 체계

```
TC-{모듈}-{번호}
  TC-BSW-001  : BSW 계층 단위 테스트
  TC-BMS-001  : BMS 컴포넌트 단위 테스트
  TC-SEC-001  : 보안 모듈 단위 테스트
  TC-IVI-001  : IVI 플랫폼 단위 테스트
  TC-CI-001   : CI/CD 파이프라인 테스트
  TC-INT-001  : 통합 테스트
  TC-PERF-001 : 성능 테스트
  TC-EXP-001  : 보안 실험 (Ablation Study)
```

---

## 2. 단위 테스트 — Node A (C++)

### TC-BSW-001: CAN CDD 초기화 및 loopback 송수신

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BSW-001 |
| **목적** | SocketCAN PF_CAN/SOCK_RAW 소켓으로 can0 초기화 후 loopback 모드에서 프레임 송수신 확인 |
| **전제조건** | `ip link add dev vcan0 type vcan && ip link set up vcan0` (가상 CAN 인터페이스) |
| **입력** | CAN ID=0x100, DLC=8, Payload=[0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08] |
| **절차** | 1) 실제 API `SocketCanCdd::open("vcan0")`, `registerCallback()`, `startReceive()` → 2) 별도 송신 소켓에서 `send(frame)` → 3) 수신 콜백에서 동일 프레임 확인. 같은 소켓 송신을 직접 수신할 경우 CAN_RAW_RECV_OWN_MSGS를 명시하고 별도 시험으로 기록 |
| **기대 결과** | 수신 프레임의 ID, DLC, payload가 송신과 동일 |
| **성공 기준** | `ASSERT_EQ(rx_frame.can_id, 0x100)` + `ASSERT_EQ(rx_payload, tx_payload)` |
| **파일** | `test/test_can_cdd.cpp` |

### TC-BSW-002: CAN CDD 추상 인터페이스 교체 호환성

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BSW-002 |
| **목적** | `MockCanDriver`로 `SocketCanCdd` 대체 시 상위 조립 코드(`main.cpp`/CanPublisher) 무수정 컴파일 및 동작 확인 |
| **절차** | 1) `CanDriver*` 포인터에 `MockCanDriver` 할당 → 2) CanDriver 의존 코드의 동일 인터페이스로 테스트 실행 |
| **기대 결과** | 컴파일 에러 없음, 테스트 통과 |
| **파일** | `test/test_can_cdd.cpp` |

### TC-BSW-003: 비동기 수신 콜백 호출 횟수 검증

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BSW-003 |
| **목적** | 10개 프레임 전송 시 콜백 정확히 10회 호출 확인 |
| **절차** | 콜백 카운터 등록 → 10회 `send()` → 500ms 대기 → 카운터 확인 |
| **기대 결과** | `callback_count == 10` |
| **파일** | `test/test_can_cdd.cpp` |

### TC-BSW-004: ara::com Publisher 다중 구독자 전달

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BSW-004 |
| **목적** | 3개 Subscriber 등록 후 `Publisher::send()` 한 번 호출 시 전체 수신 확인 |
| **입력** | `BmsStatusData{soc=75.0f, soh=95.0f, voltage=42.0f, current=-2.0f, temperature=25}` |
| **절차** | 구독자 3개 등록 → `send(data)` → 각 구독자의 수신 데이터 검증 |
| **기대 결과** | 3개 구독자 모두 동일 데이터 수신 |
| **파일** | `test/test_publisher.cpp` |

### TC-BSW-005: ara::com 다중 스레드 동시 접근 안전성

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BSW-005 |
| **목적** | 10개 스레드 동시 `send()` 및 `subscribe()` 호출 시 race condition 없음 확인 |
| **절차** | 10개 스레드 각각 100회 `send()` + 구독자 추가 동시 실행 → 데이터 손상 없음 확인 |
| **기대 결과** | sanitizer 에러 없음 (`-fsanitize=thread`) |
| **파일** | `test/test_publisher.cpp` |

### TC-BSW-006: WatchdogManager 태스크 타임아웃 감지 및 복구

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BSW-006, NFR-REL-001, NFR-REL-002 |
| **목적** | 감시 대상 스레드가 3초 이상 무응답 시 WatchdogManager가 타임아웃을 감지하고 해당 스레드를 재시작하는지 확인 |
| **전제조건** | WatchdogManager 1초 주기 감시 활성화 |
| **절차** | 1) BMS 계산 스레드를 의도적으로 4초간 블로킹 → 2) WatchdogManager 타임아웃 감지 확인 → 3) 스레드 재시작 시도 확인 → 4) 재시작 후 정상 동작 복구 확인 |
| **기대 결과** | 3초 초과 시 타임아웃 감지 로그 출력, 스레드 재시작 1회 수행, 재시작 후 정상 heartbeat 수신 |
| **성공 기준** | `ASSERT_TRUE(watchdog.isTimeoutDetected())` + 재시작 후 `ASSERT_TRUE(thread.isRunning())` |
| **파일** | `test/test_watchdog_manager.cpp` |

### TC-BSW-007: WatchdogManager 재시작 최대 횟수 초과 시 Fail-safe 전이

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BSW-006, NFR-REL-002 |
| **목적** | 스레드 재시작 3회 연속 실패 시 Fail-safe WARNING 상태로 전이되는지 확인 |
| **절차** | 1) 감시 대상 스레드를 재시작 후에도 즉시 블로킹되도록 설정 → 2) 3회 재시작 시도 모두 실패 → 3) Fail-safe WARNING 전이 확인 |
| **기대 결과** | 재시작 카운터 == 3, FailSafeStateMachine 상태 == WARNING, 사유 코드 `0x07`로 `0x101` 송신, 로그에 `ERR_WATCHDOG_MAX_RESTART` 출력 |
| **비고** | 재시작 실행 주체는 태스크를 소유한 `main`이며 WatchdogManager는 타임아웃 감지·횟수 집계만 담당한다 (SDD-ECU §3.4.3). 시작 상태가 NORMAL이 아니면 전이가 발생하지 않으므로 본 TC는 NORMAL에서 시작한다 |
| **파일** | `test/test_watchdog_manager.cpp` |

### TC-BSW-008: SensorSimulator 4가지 입력 모드 정상 동작

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BSW-007 |
| **목적** | SensorSimulator의 4가지 입력 모드(CONSTANT, PROFILE_CSV, RANDOM_WALK, ADS1115_HARDWARE)가 각각 올바른 SensorData를 생성하는지 확인 |
| **파일** | `test/test_sensor_simulator.cpp` |

| 케이스 | 모드 | 입력 | 기대 결과 |
|--------|------|------|-----------|
| TC-BSW-008-a | CONSTANT | 기본 파라미터 | `voltage==42.0f`, `current==-2.0f`, `temperature==25` (매 호출 동일) |
| TC-BSW-008-b | PROFILE_CSV | `data/battery_profile.csv` (3행) | `next()` 3회 호출 시 CSV 행 순서대로 반환, 끝 도달 시 마지막 행 유지 |
| TC-BSW-008-c | RANDOM_WALK | 100회 `next()` | voltage ∈ [30.0, 42.0], current ∈ [-10.0, 5.0], temperature ∈ [-10, 70] 범위 내 |
| TC-BSW-008-d | ADS1115_HARDWARE | I2C 0x48 ADS1115 연결 상태에서 `next()` | voltage ∈ [30.0, 42.0] 범위 내 ADC 변환값 반환 |

> **참고**: TC-BSW-008-d (ADS1115_HARDWARE)는 물리 하드웨어(ADS1115 ADC + I2C)가 필요하며, 현재 예정 CI에는 실제 I2C 장치/드라이버/권한이 제공되지 않으므로 CI 자동 테스트에서 제외된다 (CICD_SPEC §4.2 참조). 해당 모드는 실 RPi4 환경에서만 수동 검증한다.

### TC-BMS-001: EKF SOC 추정 — 알려진 입력 시퀀스 검증

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BMS-001 |
| **목적** | 고정 방전 전류(-2A) 100초 시퀀스에서 EKF SOC 추정값이 허용 오차 내에 있는지 확인 |
| **입력** | I=-2.0A, dt=0.1s, Q_capacity=50Ah, 초기 SOC=80%, **1,000타임스텝** (= 100초) |
| **기대 결과** | 1,000타임스텝 후 EKF SOC ≈ 79.89% (이론값 79.8889%), 오차 ≤0.5% |
| **비고** | 관측 전압은 팩 전압으로 `update()`에 전달하고 EKF 내부에서만 10으로 한 번 나눈다(SOC-2=A). 호출부에서 나누지 않는다. 이론 참 SOC에 대응하는 3차 팩 OCV 시퀀스를 사용하며 임의 고정 전압을 관측 정답으로 넣지 않는다 |
| **파일** | `test/test_ekf_soc.cpp` |

### TC-BMS-002: EKF vs 쿨롱 카운팅 장기 누적 오차 비교

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BMS-002 |
| **목적** | 1시간(36,000 타임스텝) 시뮬레이션에서 EKF RMSE < 쿨롱 카운팅 RMSE 확인 |
| **입력** | `PROFILE_CSV` 모드: 사전 고정한 합성 1시간 관측 프로파일 CSV + 별도 참 SOC + 생성 조건 manifest (S-7=A). 초기 상태 t=0, dt=0.1s로 36,000회 update |
| **기대 결과** | `RMSE_EKF < RMSE_CoulombCounting` (구체적 수치는 실험 후 기입) |
| **파일** | `test/test_ekf_soc.cpp`, `data/battery_profile_1h.csv` |

### TC-BMS-003: SOH 추정 정확도

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BMS-003 |
| **목적** | 가상 추정 용량 45Ah에서 SOH = 45/50 × 100 = 90.0% 확인 |
| **입력** | Q_initial=50Ah, Q_current=45Ah (가상 용량 열화 입력) |
| **기대 결과** | `soh == 90.0f` (±0.01%) |
| **파일** | `test/test_soh_estimator.cpp` |

### TC-BMS-004: Fail-safe 상태머신 — 전체 전이 경로 Branch 100%

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BMS-004 |
| **목적** | 모든 상태 전이 경로 단위 테스트 (Branch Coverage 100% 달성) |
| **테스트 케이스** | |

| 케이스 | 입력 | 기대 전이 | 기대 사유 코드 |
|--------|------|-----------|----------------|
| TC-BMS-004-a | SOC=19%, Temp=30°C, State=NORMAL | NORMAL → WARNING | 0x01 |
| TC-BMS-004-b | SOC=4%, Temp=30°C, State=WARNING | WARNING → CRITICAL | 0x02 |
| TC-BMS-004-c | SOC=10%, Temp=61°C, State=CRITICAL | CRITICAL → SHUTDOWN | 0x04 |
| TC-BMS-004-d | SOC=25%, Temp=30°C, State=WARNING | WARNING → NORMAL | 0x05 |
| TC-BMS-004-e | 수동 리셋 명령 수신 | SHUTDOWN → NORMAL | 0x06 |
| TC-BMS-004-f | SOC=60%, Temp=30°C, State=NORMAL | 전이 없음 (NORMAL 유지) | — |
| TC-BMS-004-g | SOC=60%, Temp=56°C, State=NORMAL | NORMAL → WARNING | 0x03 |
| TC-BMS-004-h | Watchdog 재시작 3회 실패, State=NORMAL | NORMAL → WARNING | 0x07 |

> CRITICAL → NORMAL 직접 복귀 경로는 설계상 존재하지 않는다 (SDD-ECU §3.4.3). SHUTDOWN을 거쳐 수동 리셋(`0x06`)으로만 해제되므로 해당 전이는 시험 대상이 아니다.

| **파일** | `test/test_failsafe_sm.cpp` |

### TC-BMS-005: SOC < 5% 시 CRITICAL 상태 CAN 통보

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BMS-005 |
| **목적** | SOC=4.5% 입력 시 WARNING→CRITICAL 전이 + CAN ID 0x101 메시지 전송 확인 |
| **절차** | MockCanDriver 등록 → SOC=4.5% 입력 → `MockCanDriver::sent_frames` 확인 |
| **기대 결과** | 송신 목록에서 0x101/0x103 쌍을 찾아 NewState=0x02와 인증값을 확인. 인증 프레임이 뒤따르므로 마지막 프레임이 0x101이라고 가정하지 않음 |
| **파일** | `test/test_bms_component.cpp` |

### TC-BMS-006: 온도 > 60°C 시 SHUTDOWN 전이 + CAN 전송

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BMS-006 |
| **목적** | Temp=61°C 입력 시 SHUTDOWN 전이 + CAN ID 0x101 전송 확인 |
| **기대 결과** | NewState=0x03 (SHUTDOWN), Reason=0x04 |
| **파일** | `test/test_bms_component.cpp` |

### TC-BMS-007: BMS 100ms 주기 CAN 전송 타이밍 검증

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BMS-008 |
| **목적** | 1초 동안 CAN ID 0x100 전송 횟수 = 10±1회, 간격 편차 ±10ms 이내 확인 |
| **절차** | `std::chrono` 타임스탬프로 10회 전송 간격 기록, 평균/표준편차 계산 |
| **기대 결과** | 모든 유효 0x100 연속 간격이 90~110ms. 횟수·평균·표준편차는 보조 통계이며 수집 시작/끝 경계와 손실도 기록 |
| **파일** | `test/test_bms_component.cpp` |

### TC-SEC-001: SecOC HMAC-SHA256 MAC 생성 정확도

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-SEC-001 |
| **목적** | 알려진 입력에 대해 HMAC-SHA256 앞 4바이트가 수동 계산값과 일치하는지 확인 |
| **입력** | Key=0x(32바이트 고정 테스트 키), CAN_ID=0x0100, Counter=0x00000001, Payload=8바이트 |
| **기대 결과** | `TruncatedMAC == 수동 계산 참조값` |
| **파일** | `test/test_secoc.cpp` |

### TC-SEC-002: HMAC 검증 실패 시 메시지 폐기

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-SEC-002, NFR-SEC-001 |
| **목적** | 변조된 MAC 100회 전송 시 전량 폐기 확인 (차단율 100%) |
| **절차** | 정상 MAC에서 1비트 뒤집은 가짜 MAC 전송 100회 → 콜백 호출 횟수 = 0 확인 |
| **기대 결과** | `accepted_count == 0` |
| **파일** | `test/test_secoc.cpp` |

### TC-SEC-003: 롤링 카운터 Replay 방어

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-SEC-003, NFR-SEC-002 |
| **목적** | 동일 카운터 메시지 재전송 시 폐기 확인 |
| **절차** | Counter=5 메시지 정상 수신 → Counter=5 동일 메시지 재전송 → 폐기 확인 |
| **기대 결과** | 두 번째 수신 시 ERR_COUNTER_MISMATCH, 콜백 호출 없음 |
| **추가 확인** | ICD v1.6 §2.4 인증 CAN ID별 독립 counter: 두 `0x103` 인증 사이에 `0x102`가 150회 있어도 두 번째 `0x103`의 counter는 1이며 수락된다 |
| **파일** | `test/test_secoc.cpp`, `security/tests/test_secoc.py` |

### TC-SEC-004: Constant-time MAC 비교 코드 검토

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-SEC-004 |
| **검증 방법** | 코드 리뷰 — `secoc_module.cpp` / `secoc_verifier.cpp`에서 `hmac.compare_digest()` 또는 `CRYPTO_memcmp()` 사용 확인 |
| **기대 결과** | 단순 `memcmp()` 또는 `==` 비교 없음 |
| **파일** | `adaptive_ecu/src/bsw/secoc_module.cpp`, `ivi_platform/hal/secoc_verifier.cpp` |

---

## 3. 단위 테스트 — 보안 모듈 (Python)

### TC-SEC-005: 공격 시뮬레이터 CLI 실행 및 패턴 검증

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-SEC-005 |
| **파일** | `security/tests/test_attack_tools.py`, `security/attack_simulator.py` |

| 케이스 | 공격 유형 | 검증 방법 | 기대 결과 |
|--------|-----------|-----------|-----------|
| TC-SEC-005-a | Fuzzy | python-can 가상 버스에서 10개 수신, ID/payload 랜덤성 확인 | ID 표준편차 > 100 |
| TC-SEC-005-b | Replay | 캡처 → 재전송 메시지가 원본과 동일한지 확인 | payload 바이트 일치 |
| TC-SEC-005-c | Spoofing | 전송된 CAN ID=0x100, SOC raw=200 확인 | payload[0]==200 |
| TC-SEC-005-d | Flooding | 1초 내 **버스 점유율(bus load) ≥ 50%** 확인 | bus_load ≥ 50% |

버스 점유율 ≥50%는 프로젝트 시험 목표다. DLC·ID·stuffing·오류/재전송에 따라 프레임 길이가 달라지므로 fps만으로 합격을 판정하지 않는다. 500kbps/DLC=8의 3,704fps는 특정 최악 stuffing 모델에서의 계산값이며 모든 프레임의 물리 상한이 아니다. `measure_can_secoc.py`의 고정 비트 수·부하 출력은 가정 기반 계산, HMAC 시간만 실행 호스트 측정이다. 실제 버스 캡처/계측의 프레임·DLC·기간·비트레이트·손실·산정법을 기록하고 vcan/합성 결과와 분리한다. 기존 81%/55%/0.54% 표를 실측으로 사용하지 않는다.

### TC-SEC-006: Isolation Forest IDS 탐지 정확도

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-SEC-006 |
| **목적** | 정상 트래픽 학습 후 공격 트래픽 주입 시 이상 점수 분리 확인 |
| **절차** | 1) 정상 트래픽 1000윈도우로 모델 학습 → 2) Flooding 패턴 100윈도우 주입 → 3) 이상 점수 확인 |
| **기대 결과** | 정상 점수 평균 > 공격 점수 평균 (즉, 공격 점수가 더 낮은 값) |
| **파일** | `security/tests/test_ids_engine.py` |

### TC-SEC-007: IDS 경보 CAN 0x200 전송 확인

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-SEC-007 |
| **목적** | 공격 탐지 시 CAN ID 0x200 경보 프레임 즉시 전송 확인 |
| **절차** | 가상 CAN 버스에서 Flooding 패턴 주입 → 탐지 후 0x200 프레임 수신 확인 |
| **기대 결과** | `alert_frame.arbitration_id == 0x200`, `AttackType == 4 (Flooding)` |
| **파일** | `security/tests/test_ids_alerter.py` |

---

## 4. 단위 테스트 — Node B (C++/Qt)

> 2026-09-23 현재 P3 core·Qt 소스와 시험 8개가 있다. 아래 공식 TC의 전체 합격은 아직 아니며, 실제 확인한 부분 범위만 다음 기록과 CHG-003 증거를 따른다.

### P1 core 회귀 실행 기록

macOS arm64에서 CMake Debug와 Release를 각각 구성해 `test_can_parser`, `test_secoc_verifier`, `test_vehicle_data_service`를 실행했고 양쪽 모두 3/3 통과했다. ECU 공개 더미 벡터, signed current, 변조 MAC, counter `+100/+101`·replay·wrap, 인증 전 미게시, 인증 실패 후 last-good 유지, BMS/Fail-safe counter 분리, BMS 갱신 후 IDS 상태 유지를 확인했다.

이 결과는 TC-IVI-002의 core 범위와 TC-IVI-003의 일부 범위만 증명한다. pending timeout/stale, Linux 수신, Qt property/UI, `vcan0`, 물리 CAN은 미실행이므로 해당 TC를 PASS로 표시하지 않는다. 실제 명령과 환경은 [CHG-003 P1 증거](aidlc/changes/CHG-003/construction/build-and-test/evidence.md)에 있다.

### P2 CAN·SecOC 회귀 실행 기록

macOS arm64에서 `-Wall -Wextra -Wpedantic -Werror`를 적용한 CMake Debug와 Release를 각각 실행했고 양쪽 모두 6/6 통과했다. 정확한 DLC 8/SFF/허용 ID, RTR·ERR·EFF 거부, retry 3회 경계, pending 99ms 허용·100ms 만료, 최신 원본 교체, orphan auth, BMS/Fail-safe 교차 순서, last-good 유지와 SecOC 실패 복구를 확인했다.

이 결과는 TC-IVI-001의 플랫폼 독립 frame/retry 정책, TC-IVI-002 core 범위와 TC-IVI-003의 pending/observer 범위를 증명한다. Linux kernel filter·실제 poll/read, 300ms stale, Qt와 vcan은 미실행이다. 상세 결과는 [P2 구현 결과](aidlc/changes/CHG-003/construction/P2_구현_결과.md)와 [P2 증거](aidlc/changes/CHG-003/construction/build-and-test/P2_빌드_시험_증거.md)에 있다.

### P3 상태·Qt 실행 기록

macOS arm64와 Qt 6.11.2에서 Werror를 적용한 Debug/Release 앱 빌드와 CTest가 각각 8/8 통과했다. 299/300ms stale 경계, Fail-safe가 BMS age를 갱신하지 않는 조건, last-good 보존, IDS sequence 확인 경쟁, reason `0x07`, ViewModel GUI thread 전환, SOC 색상 경계와 8개 QML demo 상태를 확인했다.

Release T2→T3 ViewModel queued 갱신 100표본은 평균 0.0194079ms, p99 0.030958ms였다. 이 값은 macOS host property signal까지만 포함하며 CAN과 실제 display render는 제외한다. 상세 결과는 [P3 구현 결과](aidlc/changes/CHG-003/construction/P3_구현_결과.md)와 [P3 증거](aidlc/changes/CHG-003/construction/build-and-test/P3_빌드_시험_증거.md)에 있다. Linux vcan 통합은 아래 P4 기록에서 별도로 판정한다.

### P4 Linux vcan·계측 실행 기록

Lima Ubuntu 26.04 aarch64 VM에서 실제 `vcan0` PF_CAN filter·DLC/flag·wake 종료와 정상 SecOC, 변조 MAC, replay, 100ms pending timeout을 검증했다. Qt Release 전체 CTest는 9/9 통과했다. 100ms BMS 주기 T1→T4 1,000표본은 평균 6.037ms, p99 8.028ms, 최대 10.827ms, 누락 0이었다. 상세 환경과 과부하 사전 실행은 [P4 구현 결과](aidlc/changes/CHG-003/construction/P4_구현_결과.md)와 [P4 증거](aidlc/changes/CHG-003/construction/build-and-test/P4_빌드_시험_증거.md)에 있다. T4는 Qt offscreen `frameSwapped`이며 RPi4 HDMI scanout은 P5에서 검증한다.

### TC-IVI-001: SocketCAN 수신 콜백과 종료

| 항목 | 내용 |
| --- | --- |
| **요구사항** | FR-IVI-001 |
| **절차** | `vcan0`에 허용 ID, 미등록 ID, 잘못된 DLC, RTR/ERR 프레임을 전송하고 콜백 수와 종료 시간을 기록 |
| **기대 결과** | 허용된 DLC 8 데이터 프레임만 1회 전달되고 receiver가 대기 없이 종료 |
| **파일** | 정책 시험 `test_can_frame_validator.cpp`, `test_receive_retry_policy.cpp`; Linux 수신 통합 `test_socketcan_receiver.cpp` |

### TC-IVI-002: CAN 파싱과 SecOC 인증

| 항목 | 내용 |
| --- | --- |
| **요구사항** | FR-IVI-002, FR-SEC-002, FR-SEC-003 |
| **절차** | ICD 정상 벡터와 음수 전류·온도 경계, 변조 MAC, 같은 counter, +100/+101, uint32 wrap을 입력 |
| **기대 결과** | 정상/허용 경계만 게시되고 실패 MAC은 counter와 last-good를 변경하지 않음 |
| **파일** | `ivi_platform/test/test_can_parser.cpp`, `ivi_platform/test/test_secoc_verifier.cpp` |

### TC-IVI-003: VehicleDataService snapshot/observer

| 항목 | 내용 |
| --- | --- |
| **요구사항** | FR-IVI-003 |
| **절차** | 최초 상태, 인증 성공, timeout, 재수신과 observer 등록/해제를 순서대로 주입 |
| **기대 결과** | 최초 `valid=false`, 성공 시 원자적 snapshot, timeout 시 last-good+`stale=true`, 해제 observer 미호출 |
| **파일** | `ivi_platform/test/test_vehicle_data_service.cpp`, `test_vehicle_data_service_security.cpp`, `test_vehicle_data_service_state.cpp` |

### TC-IVI-004: Service에서 DashboardViewModel 전달

| 항목 | 내용 |
| --- | --- |
| **요구사항** | FR-IVI-004 |
| **절차** | worker thread에서 snapshot을 발행하고 `QSignalSpy`로 property 변경 signal과 실행 thread를 확인 |
| **기대 결과** | queued signal로 GUI thread에서 한 번에 갱신되고 혼합 snapshot이 없음 |
| **파일** | `test_dashboard_view_model.cpp` |

### TC-IVI-005: SOC 게이지 색상

| 입력 SOC | 기대 색상 |
| --- | --- |
| 50.0, 100.0 | 초록 |
| 20.0, 49.5 | 주황 |
| 0.0, 19.5 | 빨강 |

initial/invalid/stale에는 정상 SOC 색상만 표시하지 않고 상태 표식도 함께 확인한다. 색상 경계는 `test_dashboard_view_model.cpp`, QML 로드·표시는 `Main.qml`의 demo/offscreen smoke로 확인한다.

### TC-IVI-006: IDS 경보 표시와 확인

경보 발생 즉시 유형 전체가 표시되고 확인 전까지 유지되는지, 확인과 동시에 들어온 새 경보가 소실되지 않는지, 확인이 stale·센서 오류·Fail-safe를 해제하지 않는지 Qt Quick Test로 확인한다.

### TC-IVI-007: CRITICAL/SHUTDOWN 전체 화면 경고

NORMAL/WARNING에는 overlay가 없고 CRITICAL과 SHUTDOWN 각각에 전체 화면 경고가 나타나는지 확인한다.

### TC-IVI-008: Qt property 반영 레이턴시

Service snapshot 발행(T2)부터 DashboardViewModel property 변경(T3)까지 100회 측정한다. 평균 20ms 이하, 99퍼센타일 50ms 이하를 목표로 하며 전체 CAN→렌더 성능은 TC-PERF-001에서 별도로 측정한다.

## 5. 통합 테스트 — end-to-end CAN 통신

> **전제조건**: Node A + Node B 물리 CAN 연결 완료 (MCP2515 × 2, 120Ω 종단 저항)

### TC-INT-001: Node A → Node B BMS 데이터 end-to-end 전달

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-IVI-001, FR-IVI-002, FR-IVI-004 |
| **목적** | Node A BMS 데이터가 CAN → SocketCanReceiver → VehicleDataService → DashboardViewModel까지 정확히 전달되는지 확인 |
| **절차** | 1) Node A ECU 실행 → 2) Node B 구조화 로그와 Qt 대시보드 모니터링 → 3) SOC/전압 값 확인 |
| **기대 결과** | Node B 로그에서 0x100/0x102 인증·파싱 성공 + Qt 대시보드 SOC 표시 확인 |
| **증적** | 동작 영상 녹화 |

### TC-INT-002: SecOC 인증 포함 end-to-end 검증

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-SEC-001, FR-SEC-002, FR-SEC-003 |
| **목적** | SecOC 활성화 시 Node B SecOcVerifier에서 검증 성공 후 데이터 전달 확인 |
| **절차** | 동일 공유 키 양 노드 배포 → 정상 통신 확인 → Node A 키 변경 → Node B 수신 거부 확인 |
| **기대 결과** | 키 불일치 시 ERR_HMAC_VERIFY_FAIL 로그 + 데이터 갱신 없음 |

### TC-INT-003: Fail-safe 이벤트 Node B 전달 및 UI 반영

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-BMS-007, FR-IVI-007 |
| **목적** | Node A에서 SOC=4.5% 트리거 → CRITICAL 전이 → Node B 풀스크린 경고 표시 |
| **절차** | 시험용 estimator/상태 입력 fixture에서 SOC 4.5% 주입(현재 CONSTANT CLI는 SOC 강제 옵션이 아님) → 0x101 전송 → Node B Dialog 표시 확인 |
| **증적** | 화면 스크린샷 |

### TC-INT-004: 공격 시뮬레이션 → IDS 탐지 → Node B 경보

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-SEC-006, FR-SEC-007, FR-IVI-006 |
| **목적** | Flooding 공격 시작 → IDS 탐지 → 0x200 전송 → Node B AlertBanner 표시 end-to-end 확인 |
| **절차** | 격리 시험버스에서 `python -m security.attack_simulator --type flooding --channel can0 --duration 10 --run-id IT005-PHYSICAL-001 --confirm-isolated-test-bus` → Node B 경보 배너 등장 확인. 첫 주입 시각·실제 송신 수·물리 부하를 별도 기록 |
| **기대 결과** | 공격 시작 후 ≤3초 내 AlertBanner "⚠ Flooding Attack Detected!" 표시 |

---

## 6. 보안 실험 테스트 (Ablation Study)

> M5 단계에서 수행하며 현 시연 마감은 2026-09-18이다. 각 실험 100회 반복 기준과 REP 승인 수행 단위는 ECU M5 및 공동 규약을 따른다. 실행 결과는 CSV로 기록한다.

**집계 해석(2026-09-09 보완):** 4종×3구성×100개의 유효 공격 시행과 전체 시도 원장을 보존한다. TC-EXP-001~004의 IDS 탐지율은 각 공격의 고정 평가 구간에서 탐지가 있었던 유효 시행 수/해당 공격의 유효 시행 수로 보고한다. 여러 경보가 발생해도 같은 시행은 한 번만 센다. 전체 공격을 합친 TPR이나 보조 윈도우 ROC로 공격별 ≥90%를 대신하지 않는다. 시행의 인증 거부 발생 여부와 공격 프레임 전량 차단은 다른 지표이며, NFR-SEC-001/002의 100%는 대응 TC-SEC-002/003에서 별도로 확인한다. 미탐지·기한 초과는 결과에 포함하고, 계측 불능·INVALID·재시도는 원장에서 구분하며 조용히 제거하지 않는다. 물리 CAN 최종 평가와 합성/vcan 사전 결과는 별도 표다.

### TC-EXP-001: Spoofing 공격 실험 (3가지 방어 구성)

연결 요구: NFR-SEC-003. 4종 각각의 탐지율을 실제 CAN Config-3에서 판정하며 합성 탐지기 비교로 대체하지 않는다.

| 구성 | SecOC | IDS | 성공 횟수/100 | 차단 횟수/100 | 탐지 횟수/100 |
|------|:-----:|:---:|:-------------:|:-------------:|:-------------:|
| Config-1 | ✗ | ✗ | (실측) | — | — |
| Config-2 | ✓ | ✗ | (실측) | (실측) | — |
| Config-3 | ✓ | ✓ | (실측) | (실측) | (실측) |

### TC-EXP-002: Replay 공격 실험 (3가지 방어 구성)

연결 요구: NFR-SEC-003. 4종 각각의 탐지율을 실제 CAN Config-3에서 판정하며 합성 탐지기 비교로 대체하지 않는다.

| 구성 | SecOC | IDS | 재생 성공률 | 차단 횟수/100 | 탐지 횟수/100 |
|------|:-----:|:---:|:----------:|:-------------:|:-------------:|
| Config-1 | ✗ | ✗ | (실측) | — | — |
| Config-2 | ✓ | ✗ | (실측) | (실측) | — |
| Config-3 | ✓ | ✓ | (실측) | (실측) | (실측) |

### TC-EXP-003: Flooding 공격 실험 (3가지 방어 구성)

연결 요구: NFR-SEC-003. 4종 각각의 탐지율을 실제 CAN Config-3에서 판정하며 합성 탐지기 비교로 대체하지 않는다.

| 구성 | SecOC | IDS | BMS 전달 성공률 | IDS 탐지율 | 탐지 지연(ms) |
|------|:-----:|:---:|:---------------:|:----------:|:-------------:|
| Config-1 | ✗ | ✗ | (실측) | — | — |
| Config-2 | ✓ | ✗ | (실측) | — | — |
| Config-3 | ✓ | ✓ | (실측) | (실측) | (실측) |

### TC-EXP-004: Fuzzy 공격 실험 (3가지 방어 구성)

연결 요구: NFR-SEC-003. 4종 각각의 탐지율을 실제 CAN Config-3에서 판정하며 합성 탐지기 비교로 대체하지 않는다.

| 구성 | SecOC | IDS | 비정상 데이터 수용률 | SecOC 차단율 | IDS 탐지율 |
|------|:-----:|:---:|:-------------------:|:------------:|:----------:|
| Config-1 | ✗ | ✗ | (실측) | — | — |
| Config-2 | ✓ | ✗ | (실측) | (실측) | — |
| Config-3 | ✓ | ✓ | (실측) | (실측) | (실측) |

### TC-EXP-005: IDS 오탐율 측정

연결 요구: NFR-SEC-004. 실제 CAN 최종 평가의 정상 입력 분모와 경계·빈 윈도우 처리를 고정하며 합성 준비 결과를 별도로 보고한다.

| 항목 | 내용 |
|------|------|
| **목적** | 정상 트래픽 100윈도우 입력 시 공격으로 잘못 판정되는 비율 측정 |
| **목표** | 오탐율 ≤5% |
| **절차** | 실제 CAN의 공격 없는 정상 구간에서 사전 고정한 길이/이동폭으로 완전한 평가 윈도우 100개 이상을 확보해 각 윈도우의 오탐 여부를 기록한다. 길이=이동폭=1초인 경우 100윈도우는 100초 분량이지만 수집 시작/끝 경계·워밍업은 별도로 확보한다. 빈 윈도우·부분 윈도우·수집 손실 처리를 기록하고 100초 명령 실행만으로 분모 충족을 선언하지 않는다 |

---

## 7. 성능 테스트

### TC-PERF-001: CAN 수신 → Qt/QML UI 반영 end-to-end 레이턴시

| 항목 | 내용 |
|------|------|
| **요구사항** | NFR-PERF-001 |
| **목표** | 평균 ≤50ms, 최대 ≤100ms |
| **측정 구간** | **시작(T1)** = Node B가 원본 CAN 프레임을 수신한 시각 / **종료(T4)** = 해당 값이 화면에 그려진 시각. SecOC 인증 대기 시간은 T1 이후에 포함된다 |
| **측정 방법** | 두 시각의 차이를 1,000회 이상 샘플링. **Node B 단독 단조 시계**를 사용하므로 노드 간 시계 동기가 필요 없다 |
| **진단 측정** | Node A 송신(T0) → Node B 원본 수신(T1) 구간, 인증→Service 게시(T1→T2), Service→ViewModel property(T2→T3), QML 렌더(T3→T4)는 병목 분석용 **진단값**이며 본 TC의 합격 판정에는 쓰지 않는다. 서로 다른 노드의 monotonic 값을 직접 빼지 않는다 |
| **유효성** | 렌더되지 않은 표본·수집 손실을 분모에 포함해 보고한다. 손실이 있으면 PASS를 보류하고 재측정한다 |

> **측정 구간 정정 이력**: 본 TC의 제목은 SRS NFR-PERF-001("CAN 수신 → UI 반영")과 일치하나, 이전 측정 방법은 "Node A 전송 → 콜백 수신"으로 서술되어 상위 요구와 구간이 달랐다. 상위 문서인 SRS를 기준으로 T1→T4로 통일하고, ECU→HAL 구간은 진단값으로 분리했다.

### TC-PERF-002: BMS CAN 전송 주기 정확도

| 항목 | 내용 |
|------|------|
| **요구사항** | NFR-PERF-002 |
| **목표** | 100ms ± 10ms |
| **측정 방법** | 0x100을 필터링한 절대시각 캡처에서 연속 100개 유효 간격(최소 101프레임)을 산출해 모두 90~110ms인지 판정. 인증/경보 프레임을 섞어 간격을 계산하지 않으며 손실·시계·시작/끝 경계를 기록. 평균·표준편차는 보조 통계 |

### TC-PERF-003: IDS 탐지 응답 시간

| 항목 | 내용 |
|------|------|
| **요구사항** | NFR-PERF-003 |
| **목표** | ≤3초 (공격 시작 → 0x200 수신) |
| **측정 방법** | 동일 관측 호스트/시계에서 실제 공격 송신 시작과 0x200 수신을 식별해 차이를 계산한다. 노드가 다르면 동기 오차/공통 계측을 증명하며 CAN payload의 초 단위 timestamp로 ms 지연을 계산하지 않는다. 미탐지·수집 손실·기한 초과도 시행 분모에 포함한다 |
| **범위 구분** | 본 TC의 종료 시점은 **`0x200` 수신**이다. 화면 AlertBanner 표시까지를 포함한 시간은 **TC-INT-004**에서 별도로 판정한다. 두 값을 같은 지표로 합산·대체하지 않는다 |

---

## 8. CI 품질 게이트 정책

### TC-CI-001: GitHub Actions 자동 기동

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-CI-001 |
| **검증** | PR 생성 후 Actions 탭에서 파이프라인 자동 기동 확인 |

### TC-CI-002: cppcheck 정적 분석 실패 시 중단

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-CI-002, NFR-QA-003 |
| **검증** | 의도적 메모리 누수 코드 커밋 → Stage 1에서 파이프라인 빨간 상태 확인 |

### TC-CI-003: ARM64 크로스컴파일 산출물 확인

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-CI-003 |
| **검증** | CI 산출물 다운로드 후 `file ./adaptive_ecu` → `ELF 64-bit LSB executable, ARM aarch64` 확인 |

### TC-CI-004: 커버리지 품질 게이트

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-CI-004, NFR-QA-001, NFR-QA-002 |
| **검증** | Codecov 리포트에서 C++ Line ≥80%, Fail-safe Branch=100% 확인 |
| **실패 시** | PR merge 차단 |

### TC-CI-005: 자동 배포

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-CI-005 |
| **검증** | main 브랜치 머지 후 RPi4에 SSH 자동 배포 완료 확인 |

### TC-CI-006: Health Check

| 항목 | 내용 |
|------|------|
| **요구사항** | FR-CI-006 |
| **검증** | 서비스 active와 함께 승인 설정·artifact 해시·새 정상 CAN/인증 데이터·오류 상태를 확인. active만으로 통과하지 않으며 실패 시 rollback 후 이전 버전 복구도 확인(CICD_SPEC §6) |

---

## 9. 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| v1.0 | 2026-03-15 | 초안 작성 (TC-BSW/BMS/SEC/IVI/INT/PERF/CI 전체) | 팀원A, 팀원B |
| v1.1 | 2026-04-01 | TC-EXP-001~005 Ablation Study 실험 케이스 추가 | 팀원A |
| v1.2 | 2026-05-09 | TC-BSW-006~008 추가 (WatchdogManager, SensorSimulator), TC-BSW-008-d (ADS1115_HARDWARE) + CI 제외 사유 명시. 참조 문서 SRS v1.3, SDD-ECU v1.4, SDD-IVI v1.3 반영 | 팀원A |
| v1.3 | 2026-05-09 | TC-IVI-008 레이턴시 목표 수정 (≤20ms/≤50ms), TC-EXP-002·004 실험 테이블 보완, 참조 SRS v1.4·SDD-ECU v1.5 반영 | 팀원A |
| v1.5 | 2026-09-22 | Node B 시험을 C++/Qt Test/Qt Quick Test 기준으로 전환 | 팀원B |
| v1.6 | 2026-09-23 | P3 stale·IDS ack·ViewModel·QML demo 실행 기록과 실제 Qt 시험 경로 반영 | 팀원B |
| v1.4 | 2026-09-06 | TC-PERF-001 측정 구간을 상위 요구(SRS NFR-PERF-001)에 맞춰 T1(CAN 수신)→T4(UI 반영)로 통일하고 ECU→HAL 구간은 진단값으로 분리, TC-BMS-001 입력 100→1,000 타임스텝 정정, TC-SEC-005-d 기준을 프레임 수→버스 점유율 ≥50%로 변경, TC-PERF-003과 TC-INT-004의 측정 범위 구분 명시, TC-BSW-007 사유 코드 `0x07` 반영 | 팀원A, 팀원B |


## S 답변 반영 시험 보완 — 승인된 목표, 실행 결과 아님

| 공식 시험 | 추가 인수 조건 |
|---|---|
| TC-BMS-005/006, TC-INT-003 | 임계 입력→해당 상태/사유→0x101/0x103 인증→IVI 경고 연결. 단위 Mock 상태 전송과 양측 인증 통합을 구분. 실제 전류 차단/제한 성공을 합격 조건으로 주장하지 않음 |
| TC-IVI-006, TC-PERF-001 | 첫 경고 반영에서 배너·문구 완전 표시. 장식 효과가 경고 표시를 지연/가림하지 않는지 렌더 증적 확인. 텍스트 존재 검사만으로 표시 시점·효과 조건을 통과시키지 않음 |
| TC-IVI-006 | 사용자 확인까지 유지, 같은 유형의 새 경보 재표시, 확인 경쟁에서 새 경보 소실 없음. 확인으로 stale·센서 오류·Fail-safe를 해제하지 않음 |
| TC-BSW-008, TC-IVI-002/004/008 | ICD §8 목표의 초기 1→2, 오류 3/4→복구 5/6→2, 중간 오류 재시작, 미지원 코드·구형 0 처리. 서로 다른 새 ADC 3회만 인수하며 실제 코드 전환 후 시험 |
| TC-SEC-002, TC-INT-002 | 품질 바이트 변조도 인증 실패. 값·품질을 함께 한 번만 반영하고 기존 혼합 버전은 정상 인수하지 않음 |

센서/HAL 동시 전환 전에는 기존 계약 시험과 목표 계약 시험을 실행 구성별로 분리한다. 목표 형식 시험이 작성됐다는 이유로 현행 송수신기가 호환된다고 표시하지 않는다. 상세 byte 표는 ICD §8을 참조하고 복제하지 않는다.


## 요구 의미 대조에 따른 시험 해석 보강

- TC-BSW-006에는 CAN 수신 작업의 이상 종료→회수→재시작→새 프레임 수신 재개를 포함한다. TC-BSW-007의 수신 재시도 실패 하위 사례에서는 최대 3회 후 실패 로그·중복 작업 부재를 확인한다. BMS 작업 복구만으로 NFR-REL-002를 인수하지 않는다.
- TC-BMS-007/TC-PERF-002는 모든 유효 측정 간격의 100ms±10ms 조건을 검사한다. 표준편차는 보조 통계이며 일정하게 잘못된 주기로 송신하는 경우를 통과시키지 않는다.
- TC-SEC-006의 점수 방향은 raw decision_function에 적용한다. 부호 반전 anomaly·정규화 wire_score는 표현 종류를 구분해 보고한다. 점수 평균 분리만으로 NFR-SEC-003/004 탐지율·오탐율 합격을 주장하지 않는다.
- TC-IVI-007은 CRITICAL뿐 아니라 SHUTDOWN도 검사한다. 기존 NORMAL 비표시 조건과 승인된 오류/확인 정책을 함께 확인한다.

S-4=A에 따라 TC-BMS-003은 가상 용량비를 검증한다. 누적 방전 5Ah만 입력하고 추정 용량을 바꾸지 않는 경우 SOH가 자동으로 90%가 되지 않는 것도 확인한다. 내부 비율 0.9와 출력 백분율 90.0을 구분한다. S-5=A에 따라 합성은 준비·분석용이며 4종 공격×3방어 구성의 최종 평가는 §1.1의 실제 CAN 환경에서 수행한다. 이 문서 수정은 제품 시험 실행 완료가 아니다.


### S-7=A — TC-BMS-002 평가 구성과 NASA 검증 분리

TC-BMS-002는 합성 참 상태에 대한 비교 시험이다. NASA 입력을 이 시험의 SOC 정답으로 사용하지 않는다. 두 추정기는 같은 관측·초기 조건을 받으며 참 상태는 평가기만 읽는다. 관측 오차를 넣기 전의 참 전류·상태와 관측 전류를 구분한다. 생성 모델·부하·초기 오차·잡음/바이어스·seed·반복·튜닝/평가 분리·합격 대상 시나리오를 실행 전에 근거와 함께 확정한다. 최초 S-7 답변에서 미정이던 조건은 아래 S-21=A로 고정됐다. 제품 설정은 SOC-1/2와 SDD-ECU를 따른다.

기존 `RMSE_EKF < RMSE_CoulombCounting` 기준은 유지한다. 최대 절대 오차도 별도 보고하고 모든 오차 단위를 SOC 백분율 포인트로 명시한다. 참조를 읽거나 평가 결과를 보고 관측/잡음을 바꾸는 시험은 무효다. 무오차 대조군도 보고하되 개선을 주장할 평가 조건과 구분하며 대조군을 사후에 제외하지 않는다. 조건이 미확정이거나 기준을 충족하지 못하면 합격으로 표시하지 않는다.

NASA 자료는 별도 재생·데이터 검증 증거로 유지한다. 원시 단셀 단위·시각·배열 길이·결측·전처리·적분 보존·해시·예상 로더 결과를 확인한다. 단셀 전압을 가상 10직렬/50Ah EKF에 그대로 넣고 정확도 결과를 내지 않는다. 0.1초 재표본화가 10Hz 실측을 뜻하지 않는다. NASA 검증 통과를 TC-BMS-002 정확도 통과로 대체하지 않는다.

가변저항·ADS1115 실장비 시험은 취득·품질 상태·Fail-safe 통보·IVI 전달을 검증한다. 별도 실제 SOC 정답이 없는 상태에서 물리적 잔량 정확도나 배터리 수명 검증을 주장하지 않는다. 기존 관련 TC와 NASA 검증 증적을 별도 연결하며 새 TC ID는 임의로 만들지 않는다.



### 복구 시간 관측과 성공 판정 보강

TC-BSW-006의 3초는 마지막 처리 완료 heartbeat 이후의 무응답 임계다. 1초 주기 감시이므로 실제 감지 시각을 정확히 3초로 가정하지 않는다. 마지막 heartbeat·임계 도달·감지·정지 요청·종료 확인·복원·새 처리 완료 시각을 각각 기록한다. 이상적인 감시 위상 지연과 실제 스케줄링/블로킹 지연을 구분하고, 실측 없는 4초 상한을 새 합격 기준으로 추가하지 않는다.

기존의 실행 여부 assertion만으로 성공 판정하지 않는다. 기존 작업 회수·중복 작업 부재·유효 전체 상태 복원·새 작업의 처리 완료 heartbeat를 함께 확인한다. 센서 품질과 SOC 정확도 재인수는 별도이며 기존 Fail-safe·세션·counter의 임의 초기화가 없어야 한다. snapshot 허용 노후도와 종료 대기 상한은 R-5=A의 측정 후 인터뷰를 거쳐 확정하며 시험 상수도 그 이후 결정한다.

TC-BSW-007의 3회는 실제 복구 시도의 연속 실패 횟수다. Watchdog timeout 콜백 3회를 재시작 3회로 대체하지 않는다. 회수되지 않은 작업이 남으면 Q-6=A대로 운영자 재시작 필요를 보고하고 중복 작업 생성 없이 실패 처리한다. 이 경우를 3회 재시작 완료로 표시하지 않는다. 구체 수행·경계 목록은 ECU M3의 복구 조건·제한 시간 검토를 따른다.



### S-8=B — TC-CI-004 지표와 증거

합격 기준은 C++ 실행 가능 소스 줄 중 실행된 줄의 비율 80% 이상이며, Statement 지표로 보고하지 않는다. C++ 계측 대상과 제외 경로·이유, 도구 버전, 실행 시험 수, 원시 lcov와 요약 결과를 함께 보존한다. Python 또는 Qt UI의 별도 지표로 C++ 기준을 대신하지 않는다. Fail-safe Branch 100%와 cppcheck 0건은 유지한다. 시험 0개·빈 보고서·비유한 수치·분모 0·파싱 실패는 INVALID/실패로 처리한다. Codecov 업로드 성공만으로 품질 게이트 통과로 판정하지 않는다.


### S-21=A — TC-BMS-002 고정 시나리오와 합격 적용

사용자 서면 선택에 따라 가상 50Ah·초기 SOC 80%·참 전류 -2A·dt=0.1초·1시간(36,000 update), SDD 목표 3차 OCV·10직렬을 합성 조건으로 고정한다. 참 상태는 관측 바이어스 적용 전 전류로 독립 계산하고 추정기에 정답을 제공하지 않는다. 결정적 입력으로 seed는 사용하지 않는다.

| 구분 | 관측 오차 | 합격·보고 조건 |
|---|---|---|
| 무오차 대조군 1개 | 전류·전압 오차 0 | 단위·시각·참 상태 정합 확인, RMSE 0인 적분보다 더 작은 오차를 요구하지 않음 |
| 필수 주 비교 2개 | 전류 +0.1A 또는 -0.1A, 전압 오차 0 | 각 조건에서 RMSE_EKF < RMSE_CoulombCounting, 두 조건 모두 통과 필요 |
| 민감도 4개 | 전류 ±0.1A × 단셀 전압 ±0.01V | 불리한 결과·역전도 전부 보고, 엄격 우위의 필수 합격 대상은 아님 |

동일 관측·초기 조건, t=0과 update 후 표본 구분, SOC 백분율 포인트 단위, 최대 절대 오차·manifest/hash를 기록한다. SOC-2=A로 제품 3차/팩 입력 코드와 시험 파일을 수정했으나 실제 C++ 실행 증거는 별도다. 제품 실행과 정확도 합격은 아직 확인하지 않았으며 이 합성 오차는 실제 센서 오차를 뜻하지 않는다.

2026-09-08 종합 정합성 검토: 현재/예정 경로, 승인 상태, 단위·측정·실행 예제를 대조·정정했다. 세부 변경과 보류 관문은 [종합 검토](development/reviews/문서_종합정합성_검토.md)에 기록한다. 기존 요구/TC ID와 ICD 계약 본문은 보존했다.


## 2026-09-09 SecOC 경계·재부팅 시험 보완

TC-SEC-003에 ICD §2.3~2.5의 동일 counter 거부, +1/+100 허용, +101 거부, uint32 래핑, 과거 유효 MAC·송신기 재부팅 0 거부를 연결한다. TC-SEC-002에는 윈도우 안 변조 MAC 거부 후 동일 counter의 정상 MAC 수락을 추가해 실패 시 상태 보존을 확인한다. TC-SEC-004의 constant-time 비교 기준은 유지한다.

양측 언어의 `adaptive_ecu/test/test_secoc.cpp`와 `security/tests/test_secoc.py`에 같은 공개 더미 고정 벡터를 사용한다. 수신 이력이 없는 수신기가 과거 42 또는 0의 유효 MAC을 수락하는 사례는 현행 고정키 한계 재현이며 보안 합격 사례가 아니다. 최종 재부팅 replay 방어는 세션 상세 승인·교차 구현 시험으로 판정한다. 실제 IVI 콜백·에러 로그는 아직 없는 수신 통합 구현 후 검증하며 bool 단위 결과로 대체하지 않는다.

## CHG-006 소프트웨어 회귀 연결

FR-SEC-002/003/004, TC-SEC-002/003/004 및 TC-IVI-008 관련 보조 시험으로 `test_secoc_runtime`과 `test_dashboard_security`를 추가했다. 변조 100회·재사용 100회 거부/last-good 보존, +100/+101·wrap·두 쌍 독립, 99/100ms 무수신 만료, 299/300ms stale, 10회 실패 경고와 복구를 확인한다. 테스트용 더미 키만 사용한다. [CHG-006 증거](aidlc/changes/CHG-006/audit.md)는 물리 CAN과 공식 성능 목표의 인수를 대신하지 않는다.

## CHG-007 IDS 소프트웨어 보조 시험

FR-SEC-006/007, TC-SEC-006/007 관련: `test_runtime_ids.py`는 정상 서명 스트림, 형식/범위/변화, 누락/만료, counter 경계·wrap, 실패 집계, 경보 바이트와 피드백 방지를 검사한다. `test_runtime_cli.py`는 실제 IF 학습/재생, 로그 보존, 잘못된 입력, SocketCAN 모의 codec/오류/종료를 검사한다. 결정적 입력과 더미 키만 사용한다. [CHG-007](aidlc/changes/CHG-007/audit.md)의 결과를 공식 물리 송신/수신 TC 전체 합격이나 탐지율 목표 달성으로 확대하지 않는다.
