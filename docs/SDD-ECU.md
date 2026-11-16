> **문서명**: Software Design Document — Node A (ECU) (SDD-ECU)  
> **버전**: v1.8 | **작성일**: 2026-03-15 | **최종 수정**: 2026-11-11 | **작성자**: 팀원A
> **참조**: ICD v1.6, SRS v1.6 (FR-BSW-*, FR-BMS-*, FR-SEC-*), ADR-001/002/003/005/008/009/011/012

---

# 1. 문서 개요

**2026-11-11 승인된 제품 전환 설계:** [ICD session-v2](ICD-CAN-SESSION.md)/[진단](ICD-CAN-DIAGNOSTIC.md)에 따라 Pub/Sub bridge 뒤에 세션 송신 게이트를 연결한다. 수신 callback은 시각/메타데이터를 보존한 유한 큐로 main 소유 경계에 넘기고 키/번호·상태/수신·송신을 직렬화한다. Python IDS는 로컬 IPC로 인증 발행자에 관찰/사건을 전달하고 노드 간에는 CAN만 쓴다. 관리자는 프로세스 회수/시작 의도·snapshot 검증/복구/시도 기록을 담당한다. 부팅·수동 시작은 fresh, 감독 중 자동 복구는 resume이다. 프로세스 감독자는 비차단 로컬 pipe의 제어 루프 작업 완료를 확인한다. 이 신호는 노드 간 통신이나 정상 배터리·수신 완료의 증거가 아니다. 실제 연결 상태는 [CHG-029](aidlc/changes/CHG-029/aidlc-state.md)를 따르며 설계/승인을 구현 증거로 쓰지 않는다.

원천 역할: ICD는 계약, SRS는 요구, 본 문서는 설계다. plan/development 링크는 승인 답변·선정 근거·실행 절차의 위치이며 상위 계약을 변경하는 권한 위임이 아니다. 충돌 시 AGENTS Source of Truth와 사용자 승인 범위를 우선한다.

## 1.1. 목적

Node A(ECU) 소프트웨어의 모듈 구조, 클래스 설계, 알고리즘, 데이터 흐름을 상세히 기술하여 구현자가 코드를 작성할 수 있는 수준의 설계 문서를 제공한다.

## 1.2. 참조 문서

- ICD v1.6 (CAN 메시지 규격, Node B C++ Service API, SecOC 시퀀스 다이어그램)
- SRS v1.5 (FR-BSW-*, FR-BMS-*, FR-SEC-*)
- ADR.md (주요 기술 선택 근거)
- AUTOSAR Adaptive Platform Specification R22-11

---

# 2. ECU SW 계층 구조

2026-09-08: 아래 구조도·API 골격은 설계 설명이다. `BmsComponent` 독립 파일은 없고 현재 조립·주기 실행은 `adaptive_ecu/main.cpp`가 담당한다. 실제 API는 각 `include/*.h`가 근거이며 아래 축약 이름으로 호출 코드를 복사하지 않는다. Python 실시간 도구·모델·시험 경로는 §3.8의 예정 항목이다. AUTOSAR를 참고한 교육용 구조이며 표준 구현·인증을 주장하지 않는다.

```
┌───────────────────────────────────┐
│  Application Layer                  │
│  ┌─────────────────────────────┐  │
│  │  BmsComponent               │  │
│  │  └─ EkfSocEstimator          │  │
│  │  └─ SohEstimator             │  │
│  │  └─ FailSafeStateMachine     │  │
│  └─────────────────────────────┘  │
├───────────────────────────────────┤
│  RTE Layer (ara::com)               │
│  ┌─────────────────────────────┐  │
│  │  Publisher<BmsStatusData>  │  │
│  │  Publisher<FailSafeEvent>  │  │
│  └─────────────────────────────┘  │
├───────────────────────────────────┤
│  BSW Layer                          │
│  ┌─────────────────────────────┐  │
│  │  CanCdd (SocketCAN)        │  │
│  │  SecOcModule (HMAC)        │  │
│  │  WatchdogManager           │  │
│  └─────────────────────────────┘  │
├───────────────────────────────────┤
│  Linux SocketCAN (can0)             │
└───────────────────────────────────┘
```

**의존 방향 원칙**: 상위 계층은 하위 계층의 추상 인터페이스만 참조한다. Application은 CanCdd의 구체 구현을 알지 못한다.

---

# 3. 모듈 상세 설계

## 3.1. 디렉토리 구조

```
adaptive_ecu/
├── include/
│   ├── can_driver.h           // CanDriver 추상 인터페이스
│   ├── can_cdd.h              // SocketCAN 구현체 헤더
│   ├── publisher.h            // Publisher<T> 템플릿
│   ├── subscriber.h           // Subscriber 인터페이스
│   ├── bms_component.h        // BMS 전체 컴포넌트
│   ├── ekf_soc_estimator.h    // EKF SOC 추정기
│   ├── soh_estimator.h        // SOH 추정기
│   ├── failsafe_sm.h          // Fail-safe 상태머신
│   ├── secoc_module.h         // SecOC HMAC 모듈
│   ├── watchdog_manager.h     // Watchdog 관리자
│   ├── sensor_simulator.h     // 센서 시뮬레이터
│   └── can_publisher.h        // CAN 퍼블리셔
├── src/
│   ├── bsw/
│   │   ├── can_cdd.cpp            // CAN CDD 구현
│   │   ├── can_publisher.cpp      // CAN 퍼블리셔 구현
│   │   ├── mock_can_driver.cpp    // HW 없이 개발용 Mock 구현
│   │   ├── secoc_module.cpp       // SecOC 구현
│   │   └── watchdog_manager.cpp   // Watchdog 구현
│   ├── rte/
│   │   └── (header-only: publisher.h, subscriber.h)
│   └── app/
│       ├── bms_component.cpp      // BMS 전체 로직
│       ├── ekf_soc_estimator.cpp  // EKF 구현
│       ├── soh_estimator.cpp      // SOH 구현
│       ├── failsafe_sm.cpp        // Fail-safe 구현
│       └── sensor_simulator.cpp  // 센서 시뮬레이터 구현
├── test/
│   ├── test_can_cdd.cpp
│   ├── test_publisher.cpp
│   ├── test_ekf_soc.cpp
│   ├── test_failsafe_sm.cpp
│   ├── test_secoc.cpp
│   ├── test_bms_component.cpp
│   ├── test_watchdog_manager.cpp
│   └── test_sensor_simulator.cpp
├── data/
│   ├── battery_profile.csv       // PROFILE_CSV 모드용 시뮬레이션 데이터
│   └── battery_profile_1h.csv    // EKF vs 쿨롱 카운팅 1시간 비교 실험용
├── CMakeLists.txt
└── main.cpp
```

## 3.2. CAN CDD 모듈

### 3.2.1. 클래스 다이어그램

```
┌───────────────────────────────────┐
│  «interface» CanDriver             │
├───────────────────────────────────┤
│  + init(ifname: string): bool       │
│  + send(frame: CanFrame): bool      │
│  + registerCallback(cb): void       │
│  + shutdown(): void                  │
└───────────────────────────────────┘
                    △
                    │ implements
┌───────────────────────────────────┐
│  SocketCanCdd                       │
├───────────────────────────────────┤
│  - sock_fd_: int                     │
│  - rx_thread_: std::thread           │
│  - running_: std::atomic<bool>       │
│  - callbacks_: vector<Callback>      │
│  - mtx_: std::mutex                  │
├───────────────────────────────────┤
│  + init(ifname): bool                │
│  + send(frame): bool                 │
│  + registerCallback(cb): void        │
│  + shutdown(): void                  │
│  - rxLoop(): void  [rx_thread_]      │
└───────────────────────────────────┘
```

### 3.2.2. 초기화 시퀀스

1. `socket(PF_CAN, SOCK_RAW, CAN_RAW)` → `sock_fd_` 획득
2. `ioctl(SIOCGIFINDEX)` → can0 인터페이스 인덱스 획득
3. `bind(sock_fd_, &addr)` → can0에 바인드
4. `running_ = true`, `rx_thread_` 시작
5. `rxLoop()`에서 `read(sock_fd_, &frame)` 대기 → 프레임 도착 시 콜백 호출

### 3.2.3. 비동기 수신 스레드 (`rxLoop`)

```
while (running_) {
    int nbytes = read(sock_fd_, &frame, sizeof(frame));
    if (nbytes > 0) {
        lock_guard<mutex> lock(mtx_);
        for (auto& cb : callbacks_) {
            cb(frame);
        }
    }
}
```

### 3.2.4. 에러 처리

- `socket()` 실패: `ERR_CAN_INIT_FAIL` 로그 후 false 반환
- `read()` 실패: 로그 기록, 100ms 후 재시도 (최대 3회)
- `shutdown()` 호출 시: `running_ = false`, `rx_thread_.join()`, `close(sock_fd_)`

## 3.3. ara::com Pub/Sub 모듈

### 3.3.1. Publisher<T> 템플릿 설계

실제 구현은 `include/publisher.h`와 `include/subscriber.h`다. Publisher는 구독 콜백 snapshot을 mutex 안에서 복사하고 락을 해제한 뒤 호출한다. 따라서 콜백 안의 추가 구독이 락 재진입으로 교착되지 않으며 새 구독자는 다음 발행부터 참여한다.

2026-11-10 제품 연결: `include/bms_middleware.h`의 `BmsMiddleware`가 BMS와 Fail-safe Publisher를 소유한다. 구독 시 Subscriber를 값으로 보관하고 발행 시 `Subscriber::onReceive()`를 호출한다. CAN 브릿지 구독자는 생성 시 연결하며 추가 로컬 구독도 지원한다. middleware는 자기 참조 콜백을 소유하므로 복사/이동을 금지한다. 발행 중 파괴하지 않고 생산자를 종료한 후 정리한다.

이는 동일 프로세스의 동기식 경량 Pub/Sub다. 숨겨진 큐·IPC·AUTOSAR 표준 런타임은 없다. 콜백은 짧고 비블로킹으로 유지해야 하며, 콜백 예외는 발행자에게 전파된다. 전송 실패는 결과 callback으로 보고한다. callback을 동시 발행에서 사용하는 추가 구독자는 자체 공유 상태를 동기화해야 한다.

별도 Python IDS의 진단 제출은 ECU 내부 Unix datagram `CID2` 형식이다. magic 4바이트, kind 1바이트, 본문 길이 1바이트, 관찰 시점의 호스트 단조시각(ms, uint64 big-endian) 8바이트, 검증된 본문으로 구성하며 최대 118바이트다. 런타임은 로그/전달 지연 전의 관찰 시각을 넣는다. ECU는 UID/PID·소유 프로세스 생존 확인 뒤 미래 시각 또는 수신 시점 기준 3,000ms 이상 지난 제출을 첫 메시지부터 거부한다. 이후 source/tick 순서 검증과 CAN 발행 예산은 별도로 적용한다. 이는 동일 호스트 IPC 계약이며 CAN ID/DLC/진단 본문을 바꾸지 않는다. `CID1`은 거부하므로 Python IDS와 ECU 바이너리는 함께 갱신해야 한다. 신뢰된 로컬 생산자가 거짓 시각을 만드는 경우까지 방어한다고 주장하지 않는다.

### 3.3.2. Classic vs Adaptive 대응 설계 선택

| 항목 | Classic AUTOSAR | Adaptive AUTOSAR (본 프로젝트) |
| --- | --- | --- |
| 연결 시점 | 컴파일 타임 (정적) | 런타임 (동적) |
| 통신 방식 | Signal 기반 | Service 기반 (Pub/Sub, RPC) |
| 구현 대응 | 함수 포인터 직접 연결 | Publisher<T> 템플릿 + 콜백 등록 |

## 3.4. BMS SW 컴포넌트

### 3.4.1. EKF SOC 추정 알고리즘

**상태 변수:**

- x = SOC (0.0 ~ 1.0)

**예측 단계 (Prediction):**

```
SOC_pred = SOC_prev + (I * dt) / (Q_capacity * 3600.0)
P_pred = P_prev + Q_noise
```

- I: 측정 전류 (A), 양수=충전, 음수=방전
- dt: 샘플링 주기 (0.1s)
- Q_capacity: 배터리 총 용량 (Ah)
- Q_noise: 프로세스 노이즈 공분산 (tuning parameter)

**업데이트 단계 (Update):**

```
y = V_measured - OCV(SOC_pred)     // 관측 잔차
H = dOCV/dSOC(SOC_pred)            // 야코비안
S = H * P_pred * H + R_noise       // 혁신 공분산
K = P_pred * H / S                 // 칼만 게인
SOC_new = SOC_pred + K * y          // SOC 보정
P_new = (1 - K * H) * P_pred       // 오차 공분산 갱신
```

**OCV-SOC 관계식** (3차 다항식 근사):

```
OCV(SOC) = a3*SOC^3 + a2*SOC^2 + a1*SOC + a0
```

- 현재 계수 a0~a3는 가상 모델 상수다. 배터리 데이터시트에서 도출한 실측 피팅으로 주장하지 않는다. 채택 계수와 제약 조건은 §3.7.2 참조
- **V_measured는 팩 전압이므로 `CELLS_IN_SERIES`로 나눈 단셀 전압을 관측값으로 사용한다** (§3.7.2)

**튜닝 파라미터 초기값:**

| 파라미터 | 초기값 | 설명 |
| --- | --- | --- |
| Q_noise | 1e-5 | 프로세스 노이즈 (너무 작으면 보정 부족, 너무 크면 진동) |
| R_noise | 0.02 | 관측 노이즈의 초기 설정; 실측 센서 정밀도 확정값 아님 |
| P_init | 0.01 | 초기 오차 공분산 |
| SOC_init | 0.75 | 일반 초기 SOC 추정값 (75%) |

SOC-1=B 사용자 답변에 따라 M3 계획 예제와 일반 초기 설정을 통일했다(2026-09-08). S-21 합성 시험에서는 승인된 초기 SOC 80%를 명시적으로 설정하며 일반 기본값으로 대체하지 않는다. Q=1e-5는 유지한다. 이는 계획 기준의 선택이며 실장비 최적값·제품 시험 합격을 뜻하지 않는다. 측정 후 튜닝은 별도 검토한다. 비교 결과는 [SOC 합성실험 결과](development/experiments/SOC_합성실험_결과.md)에 보존한다.

2026-11-11 고정 CSV 검증 경로: evaluate_soc_profile은 실제 SensorSimulator PROFILE_CSV와 EkfSocEstimator를 호출하며 S-21의초기80%/50Ah/dt0.1초를 명시한다. 관측 전압은 팩 단위로 한 번 전달하고, 같은 float 관측 전류/dt/초기값의 적분 결과를 함께 출력한다. 정답 SOC는 native 인수나 추정기 입력에 없고 별도 Python 평가기만 읽는다. 실제 프로파일 행 수가 요청 횟수와 다르면 마지막 행 유지로 채우지 않고 거부한다.

tools/quality/bms_profile.py가 사전 고정7조건의 관측36,000행/분리된 참 SOC36,001행(t0 포함)/조건 manifest를 생성한다. 시각/단위/실제 양자화 관측·전후 입력/소스/실행 파일 hash를 검증하며 주 비교2개는 각각 엄격한 RMSE 우위, 민감도4개는 역전까지 보존한다. [실제 결과·원본 해시](aidlc/changes/CHG-029/bms-profile-20261111.json), [재현 절차](../tools/quality/README.md#tc-bms-002-고정-csv-재현)를 따른다. 이는 합성 계산 모듈 인수이며 main의 wall-clock 주기/CAN/실물 OCV·센서 정확도를 입증하지 않는다.

### 3.4.2. SOH 추정 로직

```
Q_current = supplied_estimated_capacity
SOH = (Q_current / Q_initial) * 100.0
```

- S-4=A: Q_current는 가상 용량 열화 시나리오가 제공하는 추정 용량(Ah)이다. 50Ah에서 45Ah로 변경하면 SOH는 90%다. 실제 배터리 수명 추정의 검증을 뜻하지 않는다.

**2026-11-10 제품 연결:** `virtual_battery.h`의 50Ah 공통 상수를 EKF와 SOH 기본 초기 용량에 사용한다. `SohCapacityScenario`가 별도 `--soh-profile` CSV를 시작 시 전부 검증·적재하고 main의 유효 센서 처리 주기에 `recordCycle(capacityAt(elapsed))`를 공급한다. 결과는 BmsMiddleware→Publisher→Subscriber→CanPublisher→0x100/0x102→IVI 인증 서비스에 전달된다. 기존 CAN/HAL 계약은 유지한다.

CSV 헤더는 `elapsed_s,estimated_capacity_ah`다. 첫 시각은 0, 이후 엄격한 증가, 시각은 유한한 비음수, 용량은 유한한 (0,50]Ah여야 한다. 열 누락/추가·비수치·NaN/Inf·범위 초과·중복/역순·빈 파일은 CAN 초기화 전 exit 2로 거부한다. 잘못된 시나리오를 clamp나 100% 기본값으로 대체하지 않는다. 기존 estimator API의 단독 clamp 동작은 별개이며 시나리오 입력이 그곳에 도달하기 전에 검증한다.

시간은 ECU 실행 루프 시작 기준 monotonic 경과 초다. 계단식 적용이며 보간·반복하지 않고 끝값을 유지한다. 명시적 fresh(전원 부팅·수동 시연 재시작)는 시나리오를0초부터 재생한다. session-v2 recovery를 설정한 자동 resume은 검증한 checkpoint의 SOH/시나리오 경과 시간을 복원한다. recovery 미설정의 기존 실행은 영속 SOH 복구를 하지 않는다. ADC 무효 동안 기존 정책대로 계산/송신을 보류하되 시계는 계속 흐른다. 다음 유효 처리에서 그 시각에 해당하는 최신 용량을 적용한다. 시나리오 미지정은 명시적인 가상 완전 건강(50Ah,100%) 입력이다.

예제 `adaptive_ecu/data/soh_demo.csv`: 0초 50Ah(100%), 10초 47.5Ah(95%), 20초 45Ah(90%). 빠른 변화는 기능 시연용이며 실제 열화 속도가 아니다. 센서 profile/가변저항과 독립적이고 nominal SOC 용량을 시간마다 바꾸지 않는다. 실행 로그는 시나리오 출처·단계 수·기준 용량·변경 시각/용량을 기록한다. 재현 보고에는 CSV hash도 남긴다. [CHG-025](aidlc/changes/CHG-025/evidence.md).

- 누적 방전량은 별도 상태로 기록한다. 방전 5Ah를 용량 열화 5Ah로 자동 환산하지 않는다. 초기 추정 용량은 초기 용량이며 누적 방전량은 0에서 시작한다.

### 3.4.3. Fail-safe 상태머신

**상태 전이 다이어그램:**

```
       SOC<20% || Temp>55°C          SOC<5%
       || Watchdog 3회 실패
NORMAL ──────────────────▶ WARNING ──────────▶ CRITICAL
  ◀─────────────────────    │                      │
  SOC≥20% && Temp≤55°C     │ Temp>60°C            │ Temp>60°C
                            └────────┬─────────────┘
                                     ▼
                                 SHUTDOWN
                                     │ 유효 온도≤55°C 5초 유지
                                     ▼
                        NORMAL / WARNING / CRITICAL
                        (저전압 상태·이력에 따라 선택)
```

> 저전압 CRITICAL의 자동 해제 경로는 두지 않는다. 과열 SHUTDOWN에 진입해도 저전압 latch를 보존하며 냉각 확인 후 CRITICAL로 돌아간다. 과열만 있었고 SOC도 정상인 경우에는 5초 연속 냉각 확인 후 NORMAL/0x05로 복귀한다. 수동 reset은 별도 기존 API이며 UI 닫기와 무관하다.

**Watchdog 실패에 의한 전이** (FR-BSW-006, NFR-REL-001/002): WatchdogManager가 감시 대상 태스크의 재시작을 3회 연속 실패하면 NORMAL → WARNING으로 전이하고 ICD §1.3의 사유 코드 `0x07`로 `0x101`을 송신한다. 재시작 실행 주체는 태스크를 소유한 `main`이며, WatchdogManager는 타임아웃 감지와 횟수 집계만 담당한다.

현재 CAN 수신 제품 연결은 main 소유 `CanReceiveRecovery`가 담당한다. 1초마다 실제 수신 loop 진행을 확인하고, 3초 무진행 또는 작업 오류를 회수→재시작 경로로 전달한다. timeout으로 정상 대기하는 수신기는 배선 단절/무트래픽만으로 실패 횟수를 소모하지 않는다. 복구 성공은 새 프레임의 callback 완료로 확인하며 스레드 시작만으로 성공 처리하지 않는다. 소켓·보안 세션/counter는 owner에 보존한다. 실제 복구3회 연속 실패 후 회수 완료면 기존 Fail-safe WARNING 처리와 checkpoint를 호출한다. 회수 불가면 중복 수신 작업을 만들지 않고 점검 필요로 표시한다. 원격 연결 복구 여부는 기존 CAN 인증 세션 흐름에서 별도로 판단한다. 드라이버/관리자 vcan 시험과 제품 오류 주입·물리 인수의 범위는 TEST_PLAN을 따른다.

**상태별 동작:**

| 상태 | 동작 |
| --- | --- |
| NORMAL | 정상 운전, 100ms 주기 BMS 데이터 전송 |
| WARNING | 경고 상태 0x101/0x103 인증 통보; 승인된 취득 요청 간격 유지 |
| CRITICAL | CRITICAL 상태 전이 0x101/0x103 인증 통보; 승인된 취득 요청 간격 유지 |
| SHUTDOWN | 실행·온도 감시·상태 전송 유지. 과열로 재시작하지 않음. 연속 냉각 확인 후 위험별 복귀; 실제 전원 차단은 필수 범위 밖 |

## 3.4.4. CAN Publisher (BMS → CAN 전송 브릿지)

**파일**: `adaptive_ecu/src/bsw/can_publisher.cpp`

`BmsMiddleware`의 Publisher/Subscriber를 통해 BMS 상태와 Fail-safe 이벤트를 받는 BSW 브릿지다. Application 계산은 `main.cpp`에 남아 있으며 CAN 인코딩·서명·송신 책임은 `CanPublisher`에 모은다.

- 실제 API: `CanPublisher(driver, secoc, secoc_enabled)`, `onBmsStatus(data)`, `onFailSafeEvent(event)`.
- BMS는 main의 기존 100ms `sleep_until` 루프에서 발행하고 전이 이벤트는 FSM callback에서 즉시 발행한다. 별도 TX 스레드나 주기적 재송신을 추가하지 않는다.
- 원본/auth의 ID·바이트·독립 counter 계약은 ICD를 유지한다. mutex로 두 종류의 동시 발행도 쌍 단위로 직렬화한다.
- 원본 송신 실패 시 sign/auth 송신을 생략하고 counter도 소비하지 않는다. auth 송신 실패 시 이미 발급한 counter를 되돌리지 않는다. 자동 재시도는 하지 않는다.
- 결과는 `Sent`, `OriginalSendFailed`, `AuthenticationSendFailed`이며 main이 실패 단계와 원본 ID를 기록한다. 송신 성공은 드라이버 제출 성공이며 상대 노드 수신 보장이 아니다.

검증: `test_can_publisher`의 BmsMiddleware 시험은 동일 제품 wiring으로 다중 구독·FSM 전이·원본/auth 순서·MAC·독립 counter·OFF·원본/auth 실패·동시 발행을 검사한다. 물리 주기/수신/Qt 화면 인수는 별도다.

#### 선택형 송신 시도 기록

`SocketCanCdd`의 내부 `CanTxTrace`는 기본 비활성이다. 감독자 `--trace-can-tx`를 선택하면 감독자가 개인 소유 비차단 pipe를 만들고 ECU에 `--tx-trace-fd`로 전달한다. `CanDriver::send()`의 bool API와 CAN 계약은 유지한다. 별도 TX 스레드나 재전송을 추가하지 않는다.

한 시도마다 실행 UUID·순번·호스트 monotonic 시작/종료 ns·ID/DLC/공개 프레임 바이트·인증 counter·실제 syscall 여부/반환 바이트/errno를 고정512B 미만 JSON 한 번의 write로 기록한다. pipe 포화/단절은 기록 누락 누적으로 남기며 파일/네트워크 대기나 기록 재시도를 송신 경로에서 하지 않는다. 사전검사 오류는 syscall 오류와 구분한다. `kernel_accepted=true`는 classic CAN의16바이트 구조체 제출 성공이며 버스 전송·IVI 인증/게시의 증거가 아니다. 시간 차이도 드라이버 시도 경계이며 순수 syscall/물리 전송 지연이 아니다.

감독자는 길이·형식·실행 UUID·순번/누락·counter/bytes·종료 원수를 검사하고 기존 manager 로그로 전달한다. trace 읽기/형식 오류는 trace만 닫으며 건강 감시 실패로 바꾸지 않는다. `ECU_CAN_TX_CAPTURE_END.COMPLETE`는 종료 기록/EOF와 원수의 정합성이다. 명시적 기록 drop이 있어도 스트림은 COMPLETE일 수 있으므로 `records_dropped`를 함께 확인한다. SIGKILL 등 종료 기록 부재는 INCOMPLETE다. [실행/해석](development/playbooks/session-campaign.md#선택형-ecu-송신-시도-기록)과 [검증 근거](aidlc/changes/CHG-029/can-tx-trace-20261113.json)를 따른다.

---

## 3.5. SecOC HMAC 모듈

### 3.5.1. 송신 플로우

```
CanFrame 원본 생성
    │
    ▼
rolling_counter++ (인증 CAN ID별 독립: 0x102·0x103, ICD §2.4)
    │
    ▼
HMAC_Input 구성: CAN_ID(2B) || Counter(4B) || Payload(8B)
    │
    ▼
HMAC-SHA256(키, HMAC_Input) → 32바이트 해시
    │
    ▼
앞 4바이트 추출 → TruncatedMAC
    │
    ▼
원본 CAN 전송 (0x100)
인증 CAN 전송 (0x102): TruncatedMAC(4B) + Counter(4B)
```

### 3.5.2. 키 로딩

```cpp
std::vector<uint8_t> loadKey(const std::string& path) {
    std::ifstream file(path, std::ios::binary);
    // /etc/secoc/key.bin 읽기 (32바이트)
    // 파일 없음/크기 부적합 시 예외 발생
}
```

## 3.6. WatchdogManager 모듈

| 항목 | 사양 |
| --- | --- |
| 감시 대상 | BMS 계산 스레드, CAN CDD 수신 스레드 |
| 감시 주기 | 1초 |
| 타임아웃 | 3초 (무응답 시) |
| 복구 동작 | 해당 스레드 재시작 시도 (최대 3회), 실패 시 로그 기록 + Fail-safe WARNING 전이 |

## 3.7. 센서 시뮬레이터 (가상 입력 소스)

> 본 프로젝트는 소프트웨어 시뮬레이션 모드를 기본으로 하며, ADS1115 ADC 모듈 + 가변저항을 예비비로 추가 구매하여 실 하드웨어 입력 모드도 지원할 수 있다. 현재 ADS1115 보유와 ADC-1/2 시험 방향은 확정됐다. 취득·품질·전달 시험을 수행하며 장비 인수 완료는 아니다(확인사항 §1).
> 

### 3.7.1. 시뮬레이션 모드 설계

**파일**: `adaptive_ecu/src/app/sensor_simulator.cpp`

```cpp
struct SensorData {
    float voltage;      // V
    float current;      // A (양수=충전, 음수=방전)
    int8_t temperature; // °C
};

class SensorSimulator {
public:
    enum class Mode { CONSTANT, PROFILE_CSV, RANDOM_WALK, ADS1115_HARDWARE };
    SensorSimulator(Mode mode, const std::string& profilePath = "");
    SensorData next();  // dt(0.1s) 마다 호출
    static std::optional<Mode> parseMode(const std::string& name);  // 미지원 이름은 거부
    void setHardwareVoltage(float packV);  // ADS1115 모드: 검증된 새 변환값만
private:
    Mode mode_;
    std::vector<SensorData> profile_;  // CSV 모드용
    size_t idx_ = 0;
    // Random Walk 파라미터
    float voltage_ = 42.0f;
    float current_ = -2.0f;
    int8_t temp_ = 25;
};
```

**소프트웨어 시뮬레이션 3가지 모드** (4번째 하드웨어 모드는 §3.7.3 참조):

| 모드 | 설명 | 용도 |
| --- | --- | --- |
| `CONSTANT` | 고정값 (V=42.0, I=-2.0A, T=25°C) | 단위 테스트, 초기 동작 확인 |
| `PROFILE_CSV` | CSV 파일에서 시간순 데이터 읽기 | EKF 정확도 비교 실험 (기준값 대비 오차 측정) |
| `RANDOM_WALK` | 이전 값에 가우시안 노이즈 추가하여 변화 | 장시간 운행 시뮬레이션, Fail-safe 전이 테스트 |

**CSV 프로파일 포맷** (`data/battery_profile.csv`):

```
timestamp_ms,voltage,current,temperature
0,42.00,-2.0,25
100,41.98,-2.1,25
200,41.95,-2.0,26
...
```

**Random Walk 파라미터:**

| 파라미터 | 초기값 | 노이즈 σ | 범위 |
| --- | --- | --- | --- |
| voltage | 42.0V | 0.05V | 30.0~42.0V |
| current | -2.0A | 0.3A | -10.0~5.0A |
| temperature | 25°C | 0.5°C | -10~70°C |

### 3.7.2. OCV-SOC 다항식 계수

가상 시뮬레이션용 기본 계수. 실제 18650 NMC 셀의 피팅 원자료·잔차·독립 검증 근거는 현재 확인되지 않았다. 따라서 아래 계수를 실측 셀 피팅 결과나 실제 보조배터리의 특성으로 해석하지 않는다. 합성 모델 내부 검증과 실제 셀 모델 검증을 분리한다.

```cpp
// OCV(SOC) = a3*SOC^3 + a2*SOC^2 + a1*SOC + a0
// SOC: 0.0 ~ 1.0, OCV: V (단셀 기준, 팩 전압 = OCV × 셀 직렬수)
constexpr double a3 =  2.1667;
constexpr double a2 = -3.7321;
constexpr double a1 =  2.7655;
constexpr double a0 =  3.0000;
constexpr int CELLS_IN_SERIES = 10;  // 팩 전압 = 단셀 OCV × 10
constexpr double Q_CAPACITY_AH = 50.0;  // 배터리 총 용량
```

**계수 제약 조건** — 아래 두 조건을 확인한 가상 계수다. 실측 자료에 피팅했다는 근거는 없다. 계수를 재산출할 때도 이 조건을 검증해야 한다.

| 조건 | 이유 | 현재 값 |
| --- | --- | --- |
| **단조 증가** — 전 구간에서 `dOCV/dSOC > 0` | EKF는 OCV 곡선을 역산해 SOC를 추정한다. 기울기가 음수인 구간에서는 칼만 보정 방향이 반대로 뒤집혀 SOC가 발산한다 | 기울기 최솟값 `+0.6227` (SOC 57%) |
| **끝점 근사 정합** — `OCV(0)×10 = 30.0V`, `OCV(1)×10 ≈ 42.0V` | §3.7.3 ADS1115 매핑 범위(팩 30.0~42.0V)에 대응하는 가상 모델. 소수 4자리 계수의 끝점 잔차와 센서 오차를 구분한다 | 실제 계수 계산 `30.000V ~ 42.001V`; 소수 둘째 자리 표시는 `30.00V ~ 42.00V` |

**곡선 값** (검증용):

| SOC | 단셀 OCV | 팩 전압 | dOCV/dSOC |
| --- | --- | --- | --- |
| 0% | 3.000V | 30.00V | +2.766 |
| 5% | 3.129V | 31.29V | +2.409 |
| 20% | 3.421V | 34.21V | +1.533 |
| 50% | 3.721V | 37.21V | +0.658 |
| 60% | 3.784V | 37.84V | +0.627 |
| 80% | 3.933V | 39.33V | +0.954 |
| 100% | 4.200V | 42.00V | +1.801 |

Fail-safe 임계인 SOC 5%(팩 31.29V)와 20%(팩 34.21V)가 모두 곡선의 단조 구간 안에 있으므로 단조성 조건은 만족한다. EKF 수렴·정확도는 별도 실행 시험으로 검증한다.

**dOCV/dSOC (야코비안):**

```cpp
double dOCV_dSOC(double soc) {
    return 3*a3*soc*soc + 2*a2*soc + a1;
}
```

> **구현 주의**: 야코비안은 SOC에 의존하므로 상수를 반환해서는 안 된다. 센서·호출부·`0x100`은 **팩 전압**을 유지한다. `EkfSocEstimator::update()` 내부에서 관측식을 계산할 때만 `CELLS_IN_SERIES`로 한 번 나눠 단셀 전압으로 변환한다. 호출부에서는 나누지 않는다. SOC-2=A에 따라 2026-09-08 제품 소스에 이 경계와 3차 모델을 적용했으며 C++ 실행 시험은 아직 미검증이다.

### 3.7.3. ADS1115_HARDWARE 모드 — 실 하드웨어 입력 설계

**하드웨어 구성**: 10K 가변저항 → ADS1115 AIN0 핀 → I2C(주소 0x48) → Node A(RPi4)

**동작 방식**:

1. ADC-1=A에 따라 `0x01(Config)`에서 AIN0 단일변환을 요청하고 완료 상태를 확인한다. 기존 연속변환 계획을 변경했다.
2. 해당 요청의 완료를 확인한 뒤 `0x00(Conversion)`에서 16-bit 원시값을 한 번 인수한다. 같은 숫자가 나와도 새 요청 완료라면 새 측정이며 단순 재조회는 새 측정으로 세지 않는다.
3. PGA ±4.096V, AIN0 단일종단 설정에서 원시값 → 전압(V) 변환: `V = raw * 4.096 / 32768.0`. 이상적인 0~3.3V 입력에 해당하는 코드는 0~26400이며 실측 허용오차를 뜻하지 않는다.
4. 전압값(0~3.3V)을 배터리 팩 전압 범위(30.0~42.0V)로 선형 매핑
5. 가변저항을 돌리면 전압이 변하고 → EKF SOC 추정값이 실시간 변화

```cpp
// ADS1115_HARDWARE 모드 핵심 로직
SensorData SensorSimulator::nextFromHardware() {
    // I2C 읽기 (wiringPiI2C 또는 linux i2c-dev)
    int16_t raw = i2c_read_word_swapped(ads_fd_, 0x00);
    float v_adc = static_cast<float>(raw) * 4.096f / 32768.0f;
    // 유효한 0~3.3V 입력 → 가상 팩 전압 30.0~42.0V 선형 매핑
    float voltage = 30.0f + (v_adc / 3.3f) * 12.0f;
    return { voltage, -2.0f, 25 };  // 전류·온도는 가상 고정값(ADS-2=A, 2026-10-03)
}
```

**의존성**: `libi2c-dev` 패키지, `/dev/i2c-1` 활성화 (`dtparam=i2c_arm=on` in config.txt)

**제품 연결(2026-10-03, CHG-011)**: `Ads1115AcquisitionWorker`가 별도 스레드에서 `Ads1115Acquirer::tick()`을 1ms마다 호출해 아래 ADC-2=A 시간 조건으로 요청·조회·마감을 수행하고, 끝난 요청마다 순번을 올려 최신 결과를 게시한다. 100ms BMS 루프의 `HardwareSampleFeed`는 순번으로만 새 결과를 세며(같은 값의 재조회는 새 측정 아님), 최초와 오류 뒤 새 유효 결과 3회(R-3=A) 후에만 팩 전압을 넘긴다. 마지막 유효 결과가 200ms(요청 간격 2회, 실측 후 재검토할 설계값)보다 오래되면 오류로 본다. 준비·오류·지연 중에는 EKF 갱신, Fail-safe 평가, `0x100`/`0x102` 송신을 모두 보류하고(ADS-1) IVI는 ICD §2.5.1의 stale로 표시한다. 복구 뒤 EKF는 공백을 적분하지 않고 마지막 추정값에서 재개한다(ADS-3). 전류 -2A·온도 25°C는 가상 고정값이라 Fail-safe 전이는 가변저항(SOC)만으로 일어난다(ADS-2). byte 7은 ICD §8 동시 전환 전까지 0이다. `--i2c-device`(기본 `/dev/i2c-1`)를 열지 못하거나 모드 이름이 공식 4개가 아니면 다른 모드로 대체하지 않고 종료 코드 2로 끝낸다.

**끝점 허용 범위(B안, 2026-10-03, CHG-011)**: 실측에서 노브 0V 쪽 끝의 원시값이 0 아래로 흔들려(100회 중 -4·-1 각 1회, 나머지 2~6) 범위 밖 오류와 송신 보류가 평균 약 5초마다 반복됐다. 3.3V 쪽 끝은 26342~26364로 상한 안이었다. 사용자 결정 B에 따라 0~26400 바깥 허용 폭 이내는 끝점 잡음으로 보고 가장 가까운 끝값(가상 30.0V 또는 42.0V)으로 읽는다. 처음 폭은 ±16코드(1코드 125µV, 약 2mV)였으나, 0V 끝을 오래 둔 시험에서 단발 오류가 나 1000회를 추가 측정한 결과 -20~19, -16 미만 2회(-20·-18)였다. 재검토 결과 **±32코드(약 4mV, 관측 최대 이탈의 약 1.6배)**로 넓혔다. -33 이하와 26433 이상은 계속 오류이며 출력값을 바꾸지 않는다. 이 폭은 ECU RPi 1대의 실측(0V 끝 100회+1000회, 3.3V 끝 100회)에 근거한 **설계값이며 데이터시트 한계가 아니다. 추가 측정 후 재검토한다.** 순간 잡음의 하드웨어 저감(예: A0 입력 필터 커패시터)은 후속 후보다. 진단 도구 `ads1115_can_smoke`도 같은 변환 함수를 쓴다. 오류로 바뀔 때 제품 로그는 원인(`reason=range raw=…`, `late …ms`, `timeout`, `i2c-start`, `i2c-read`, `stale age=…ms`)을 함께 출력한다. 로그만 추가하며 동작은 같다.

ADC-2=A의 첫 시험 설정(2026-09-08): 내부 128SPS, 요청 사이 최소 100ms, 완료 조회 간격 최소 1ms, 요청 시작 후 20ms 미만에 반환한 유효 결과만 인수한다. 20ms에 도달하면 만료로 처리한다. 같은 요청 구간에서 재시도하지 않으며 I2C 호출이 남아 있으면 다음 요청도 겹치지 않는다. 실제 구현에서 감시·CAN 처리를 취득 대기와 분리한다. 이 값은 승인된 시험 후보이며 커널 호출의 종료 상한이나 실측 보장이 아니다. 실측 후 재검토한다.

위 예제는 변환식 설명이며 I2C 실패·범위 이탈·변환 준비 상태·센서 오류 복구 처리를 생략한 제품 코드가 아니다. 실제 구현은 [ECU M3](../plan/detail/ecu/M3_EKF_Failsafe_SecOC.md)의 승인된 센서 오류 정책을 적용한다. 전원·실제 입력은 3.3V/0~3.3V이고 PGA ±4.096V가 입력 허용 전압을 확대하지 않는다. 기준은 [확인사항 §1](development/governance/의사결정_기록.md#part2-confirmed)과 [TI 데이터시트](https://www.ti.com/product/ADS1115)다.

변환식 단위 시험의 이상적 입력/기대값은 raw=0 → 0V → 가상 30V, raw=13200 → 1.65V → 가상 36V, raw=26400 → 3.3V → 가상 42V다. 이는 계산 검증 벡터이며 장비 측정이나 SOC 정확도 증거가 아니다. 실제 드라이버 시험과 음수·범위 이탈·I2C 실패 시험은 구현 단계에서 수행한다.

**검증 후 보고 범위**: ADS1115 전압 취득·가상 상태 변화·ECU/IVI 전달은 실제 실행 증거가 있을 때 보고한다. 가변저항 입력만으로 독립 SOC 정답이나 쿨롱 카운팅 대비 RMSE 개선을 입증했다고 주장하지 않는다. 정확도 비교는 별도 기준 SOC와 평가 인수가 필요하다.

> ⚠️ **주의**: ADS1115는 기본 I2C 주소 0x48. RPi4 `/boot/firmware/config.txt`에 `dtparam=i2c_arm=on` 추가 후 재부팅 필요. `i2cdetect -y 1`로 0x48 주소 확인.
> 

## 3.8. 공격 시뮬레이터 (Python)

> 4종 CAN 공격을 CLI에서 선택 실행할 수 있는 Python 도구.
> 

### 3.8.1. 디렉토리 구조

현행 구현은 합성 생성기와 실 CAN 도구를 분리한다. `attack_simulator.py`는 물리 `canN`에서 격리 시험 확인·10초 상한을 강제하고, `capture_normal.py`는 학습 JSONL과 manifest를 새 파일로만 만든다. `secoc_tamper_fixture.py`는 IT-004의 정상 기준→MAC 1비트 변조→같은 counter 정상 복구를 통제한다. 모델 pickle은 로드하지 않으며 `ids/runtime.py`가 명시적으로 제공된 정상 캡처를 학습한다.

```
security/
├── secoc_module.py           # SecOC HMAC-SHA256 인증 모듈 (C++ 이식 전 프로토타입)
├── can_socket.py             # 표준 라이브러리 Classical SocketCAN 경계
├── attack_simulator.py       # 4종 제한형 실 CAN CLI
├── capture_normal.py         # IDS 정상 JSONL + manifest 수집
├── secoc_tamper_fixture.py   # IT-004 통제형 변조/복구 fixture
├── attacks/
│   └── traffic_gen.py        # 결정적 합성 입력(실 CAN 송신 아님)
├── ids/
│   ├── feature_extractor.py  # 1초 슬라이딩 윈도우 특징 추출
│   ├── if_detector.py        # Isolation Forest 학습/점수
│   ├── runtime_detector.py   # 규칙·SecOC·IF 스트리밍 판정
│   └── runtime.py            # JSONL/SocketCAN 실행과 0x200 송신
├── tests/
│   ├── test_attack_tools.py  # 공격·변조 fixture 단위 테스트
│   ├── test_runtime_ids.py   # 스트리밍 IDS·경보 시험
│   └── test_runtime_cli.py   # CLI·SocketCAN 모의 시험
└── requirements.txt
```

### 3.8.2. CLI 인터페이스

공통 `attack_simulator.py`는 `--type fuzzy|replay|spoofing|flooding`, `--channel`, `--duration`, `--rate`, `--seed`, `--run-id`, `--log`를 제공한다. `vcanN` 이외의 물리 인터페이스는 `--confirm-isolated-test-bus` 없이는 거부하고 실행시간 10초·요청률 4,000fps 상한을 둔다. Replay는 표준 `0x100` raw 또는 `--replay-mode authenticated-pair`의 과거 `0x100/0x102` 쌍을 사용한다. 인증 쌍 모드에서 rate는 쌍/초이며 상한은 두 프레임을 포함한 fps로 검증한다. 실행 JSON과 journal은 소켓 송신 수락 시각·성공 송신 수·중단 상태를 보존한다. 실제 버스 주입/수신 시각은 별도 Node B 관측기로 기록하고 버스 점유율은 추정값으로 채우지 않는다.

키 없는 `security.experiments.can_attack_worker`의 Replay 관찰은 별도 경로다. 기존1초 관찰 전체를 순차 소비하며 첫 유효 원본/auth 쌍과 최신 원본만 유지한다. 인증 쌍 모드는 기존0..100ms 간격의 첫 쌍, 비인증 모드는 마지막 원본을 선택한다. 쌍을 일찍 찾더라도 전체 관찰의 제어 단절/예상 밖 명령·CAN 오류를 계속 확인하고 실패 시 송신하지 않는다. 새 프레임 개수 상한·키·MAC 검증·운영 임계를 추가하지 않는다. 이 고정된 live-frame 상태는 전체 worker RSS/커널 수신 큐/외부 로그 용량의 상한을 뜻하지 않는다. [합성 할당/실제 worker 검증](aidlc/changes/CHG-029/replay-streaming-20261113.json).

### 3.8.3. 공격별 핵심 로직

| 공격 | 핵심 파라미터 | python-can 호출 |
| --- | --- | --- |
| Fuzzy | `random.randint(0,0x7FF)`, `os.urandom(8)` | `bus.send(Message(arbitration_id, data, is_extended_id=False))` |
| Replay | 사전 캡처된 메시지 큐 (FIFO) | 캡처: `Listener` 10초, 재전송: 원본 그대로 `bus.send()` |
| Spoofing | target_id=0x100, 가짜 SOC raw=200 (=100%) | `bus.send(Message(0x100, [200, 190, ...]))` |
| Flooding | target_id=0x100, 최대 속도 전송 | `while True: bus.send(msg)` (종료 기한·송신 timeout·오류 집계를 구현; 실제 속도/부하는 측정) |

## 3.9. Isolation Forest IDS 엔진 (Python)

### 3.9.1. 특징 벡터 설계

**윈도우**: 길이 1초. 현재 오프라인 `raw_windows()` 기본 이동폭도 1초이고 빈 윈도우를 생략한다. 실시간 구현은 무수신·윈도우 종료를 별도 처리해야 한다. 0x100+0x102 정상 주기 쌍만으로도 약 20프레임/초이며 전체 CAN을 10프레임으로 가정하지 않는다.

사용자 선택대로 실제 `security/ids/feature_extractor.py`의 순서를 채택한다. 기존 7차원 ID/바이트 평균 모델과 호환되지 않으므로 저장 모델에는 특징명·순서·단위·윈도우/이동폭·전처리 버전을 기록하고 다르면 로드를 거부한다.

| 순서 | 특징명 | 현재 계산·단위 |
|---|---|---|
| 1 | msg_rate | 윈도우의 프레임 수. 1초에서만 수치상 fps와 같음 |
| 2 | mean_iat | 시간 오름차순 인접 프레임 간격 평균, 초 |
| 3 | std_iat | 위 간격의 모집단 표준편차, 초 |
| 4 | unique_ids | 고유 CAN ID 개수 |
| 5 | id_entropy | ID 빈도의 Shannon entropy, bit |
| 6 | payload_change | 동일 ID 연속 payload에서 바뀐 바이트 개수의 평균; 현재 zip 비교여서 DLC 길이 변화 자체는 별도 탐지 필요 |
| 7 | max_id_burst | 한 ID의 윈도우 내 최대 프레임 수 |

특징만으로 공격 유형별 성능을 보장하지 않는다. 4종 필수 공격과 추가 masquerade 결과를 분리한다.

### 3.9.2. 모델 학습 파이프라인

현재 모델 클래스는 `security/ids/if_detector.py`의 `IsolationForestDetector`다. 기본 n_estimators=100, contamination=0.05, random_state=42는 **현재 코드 설정**이며 최종 성능을 보장하는 운영값이 아니다. 정상 학습·튜닝·평가 입력을 분리하고 모델·정규화 범위·설정·의존 버전·해시를 함께 보존하는 저장/로드 경로는 구현 과제다. 별도 `train_model.py`는 아직 없다.

session-v2 정상 IF 평가 경로는 `security/experiments/evaluate_session_if.py`다. 세 캡처 manifest의 프로토콜/환경·해시/run-id·수집 시간 중복을 검사하고 동일 runtime 특징 추출기로 IF 단독 정상 오탐 창을 평가한다. 모델 저장/로드나 공격 기여 분석을 구현했다는 뜻은 아니다. runtime의 `MODEL_EVALUATION`은 실제 모델 호출 결과, `MODEL_SKIPPED`는 무입력 생략 근거이며 CAN 경보가 아닌 로컬 계측이다. 실행/해석은 [IDS 안내](../security/ids/README.md)를 따른다.

N07 선택 계측은 `resource_metrics.py`와 runtime의 `--measure-resources`/관리형 `measure_resources` 설정을 사용한다. 실제 모델 준비/SocketCAN open 후 host 경과·현재 프로세스 CPU·Linux RSS endpoint/생애 peak·입력/처리/drop·고정 크기 단계별 시간 원수를 같은 세대 로그에 남긴다. 프레임/모델 윈도우와 anomaly/wire scoring 호출은 별도 단위이며 추가 추론은 없다. 중첩 단계 시간을 합산하지 않고 학습/자식 CPU·없는 모델 파일 크기를 만들지 않는다. 기본은 비활성이고 선택 여부를 startup identity에 포함한다. 정상/오류/인터럽트 요약과 최종 없음의 부분 sample을 구분하며 owner의 종료 상한을 보존한다. `summarize_resources.py`/PC collect_ids는 세대별 source hash·기간/분모·부분 상태를 보존하며 시행별 지표로 임의 분배하지 않는다. [실행/수집·한계](aidlc/changes/CHG-029/n07-resources-20261113.json)를 따른다. 운영 임계/CAN·IF 효과·최대 처리량/물리 인수는 변경하거나 완료 처리하지 않는다.

### 3.9.3. 실시간 탐지 흐름

CAN 수집 → 1초 윈도우 확정 → §3.9.1 특징 → 학습된 IF 점수 → 사전 고정한 임계 판정 → ICD §1.5의 0x200 경보 순서다. 수집·저장/로드·경보 전송은 [ECU M4](../plan/detail/ecu/M4_IDS_공격_물리통합.md)에서 구현한다.

`decision_function`은 낮을수록 이상이고 기본 predict 경계는 0이다. 현재 `anomaly()`는 그 부호를 반전하여 높을수록 이상이다. `wire_score()`의 0~255 raw를 다시 물리 점수처럼 100배 인코딩하지 않는다. 전송 wrapper에는 raw/표현값 중 어느 입력을 받는지 명시한다. 임계 -0.5나 미검증 유형 추론 규칙을 운영 기본값으로 복사하지 않는다. Unknown/masquerade에 새 wire 유형 코드를 임의 할당하지 않으며 유형 미확정의 송신 정책은 ICD 변경 게이트 또는 기존 코드 의미를 보존하는 구현 판단으로 정리한다.

contamination은 학습 분포에서 이상치로 둘 비율에 따라 offset을 정한다. 낮추면 기본 predict에서 더 적은 학습 표본을 이상으로 분류하도록 바뀌며, 더 민감해진다는 설명은 잘못이다. 독립 평가에서 TPR/FPR와 지연을 다시 측정한다. 근거: [scikit-learn IsolationForest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html).

### 3.9.4. IDS 실행 환경

> **중요**: IDS 엔진은 **Node A (Ubuntu)**에서 Python 프로세스로 실행된다. Node B(Qt IVI)가 아닌 Node A에서 CAN 트래픽을 모니터링하고, 탐지 결과를 CAN ID 0x200으로 전송하면 Node B의 HAL이 이를 수신하여 대시보드에 경보를 표시한다.
> 

| 항목 | 사양 |
| --- | --- |
| 실행 위치 | Node A (Ubuntu 22.04) |
| 실행 방식 | 예정 별도 프로세스. CLI 정본은 ECU M4, 실 CAN 공격 채널 옵션은 `--channel` |
| CAN 수신 | python-can `Bus('can0', bustype='socketcan')` |
| 경보 전송 | CAN ID 0x200, ICD §1.5 포맷 |
| 모델 로드 | `joblib.load('data/models/isolation_forest.pkl')` |
| 의존성 | python-can, scikit-learn, numpy, pandas |

---

# 4. 데이터 흐름도

```
[센서 입력: 전압, 전류, 온도]
        │
        ▼
  main의 센서 취득·BMS 계산
        │
        ├─▶ EkfSocEstimator.update() → SOC
        ├─▶ SohCapacityScenario → SohEstimator.recordCycle()/soh() → SOH
        ├─▶ FailSafeStateMachine.evaluate() → 상태 전이 판단
        │
        ▼
  Publisher<BmsStatusData>.send()   → 구독자 통지
  Publisher<FailSafeEvent>.send()   → (전이 시만)
        │
        ▼  Subscriber<T>.onReceive() → CAN 브릿지
  CanPublisher.onBmsStatus() / onFailSafeEvent()
        │
        ├─▶ SecOcModule.sign(payload) → MAC 생성
        │
        ▼
  CanCdd.send(0x100, payload)       → CAN 버스 전송
  CanCdd.send(0x102, mac_frame)     → HMAC 인증 전송
```

---

# 5. 테스트 케이스 매핑

C++ `test/`는 `adaptive_ecu/` 기준이다. 파일 존재와 공식 TC 전체 구현·통과는 구분한다. 현재/예정 구분은 아래와 같다.

| 모듈 | 테스트 케이스 ID | SRS 요구사항 | 파일 |
|------|----------------|-------------|------|
| CanCdd | TC-BSW-001 ~ TC-BSW-003 | FR-BSW-001~003 | 예정: `test/test_can_cdd.cpp`; 존재: `test/test_mock_can_driver.cpp` (Mock만) |
| Publisher\<T\> | TC-BSW-004 ~ TC-BSW-005 | FR-BSW-004~005 | `test/test_publisher.cpp` |
| EkfSocEstimator | TC-BMS-001 ~ TC-BMS-002 | FR-BMS-001~002 | `test/test_ekf_soc.cpp` |
| SohEstimator | TC-BMS-003 | FR-BMS-003 | 존재: `test/test_soh_estimator.cpp` |
| FailSafeStateMachine | TC-BMS-004 (a~g) | FR-BMS-004~006 | `test/test_failsafe_sm.cpp` |
| BmsComponent | TC-BMS-005~007 | FR-BMS-005~008 | 예정 통합 시험; 존재 단위 기반: `test/test_can_publisher.cpp`, `test/test_failsafe_sm.cpp` |
| WatchdogManager | TC-BSW-006 ~ TC-BSW-007 | FR-BSW-006, NFR-REL-001~002 | `test/test_watchdog_manager.cpp` |
| SensorSimulator | TC-BSW-008 | FR-BSW-007 | `test/test_sensor_simulator.cpp` |
| SecOcModule | TC-SEC-001 ~ TC-SEC-004 | FR-SEC-001~004 | `test/test_secoc.cpp` |
| AttackSimulator | TC-SEC-005 (a~d) | FR-SEC-005 | `security/tests/test_attack_tools.py`; 물리 부하는 별도 실측 필요 |
| IdsEngine | TC-SEC-006 | FR-SEC-006 | `security/tests/test_runtime_ids.py`, `security/tests/test_runtime_cli.py` |
| IdsAlerter | TC-SEC-007 | FR-SEC-007 | `security/tests/test_runtime_ids.py`, `security/tests/test_runtime_cli.py`; 실 CAN은 미검증 |

---

# 6. 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| v1.0 | 2026-03-15 | 초안 작성 — 전체 모듈 설계 (CAN CDD, ara::com, BMS, SecOC, Watchdog, 센서 시뮬레이터, 공격 시뮬레이터, IDS) | 팀원A |
| v1.1 | 2026-03-15 | ADR-009 반영 — IDS 실행 환경 §3.9.4 "Node A에서 실행" 명시 | 팀원A |
| v1.2 | 2026-04-01 | ADS1115 하드웨어 입력 모드 §3.7.3 추가 | 팀원A |
| v1.3 | 2026-04-15 | 테스트 케이스 매핑 §5 추가 | 팀원A |
| v1.4 | 2026-05-09 | §3.1 디렉토리 구조에 `data/` 디렉토리 추가, §5 테스트 매핑에 WatchdogManager·SensorSimulator 추가, 참조 문서 버전 ICD/SRS v1.3 반영 | 팀원A |
| v1.5 | 2026-05-09 | §4 데이터 흐름도에 CanPublisher 모듈 명시, 참조 문서 SRS v1.3→v1.4 반영 | 팀원A |
| v1.7 | 2026-10-03 | §3.7.3 ADS1115 제품 연결: 별도 취득 worker, 순번 기반 새 측정, 3회 확인·200ms 신선도, 오류·준비 중 송신 보류(ADS-1), 가상 고정 전류·온도(ADS-2), EKF 재개(ADS-3), 끝점 ±32코드 허용(B안, ±16에서 1000회 재측정 후 확대, 실측 기반 설계값·추가 측정 후 재검토), 오류 원인 로그. §3.7.1 모드 이름 검증·`setHardwareVoltage` 추가, POTENTIOMETER 제거(I-5=B). §3.5.1 송신 counter를 인증 CAN ID별 독립으로 갱신(ICD v1.6, CHG-012) | 팀원A |
| v1.6 | 2026-09-06 | §3.7.2 OCV-SOC 3차 계수 교체 — 기존 계수는 SOC 12.3% 아래에서 단조성이 깨져 EKF 보정 방향이 반전되고 §3.7.3 ADS1115 범위(팩 30~42V)와도 불일치했다. 단조 증가·끝점 정합 제약의 가상 계수로 교체하고 검증표를 추가(실측 피팅 근거 없음). §3.4.1에 팩→단셀 변환 명시. §3.4.3에 Watchdog 실패 전이(ICD 사유 코드 `0x07`)와 CRITICAL 복귀 경로 부재 근거 추가 | 팀원A |

## 승인된 센서·상태 통보 설계 보완

S-2=A에 따라 ECU는 가상 배터리 위험 상태를 인증해 IVI로 통보한다. 실제 부하를 차단하는 명령/액추에이터를 이 상태 메시지의 구현으로 간주하지 않는다. 이전 50/25ms 모니터링 제안은 채택된 취득 요구가 아니다. ADC-2 요청 간격 최소 100ms와 0x100 전송 주기 100ms를 각각 지키고 취득 대기로 송신·감시를 막지 않는다.

S-3=A의 다음 전환 목표는 [ICD §8](ICD.md#8-승인된-다음-전환-목표--s-3a-제품-반영-전)이다. 취득 결과→최초/복구 3회 확인→값·품질의 원자적 게시→0x100 전체 payload 인증 순서를 구현 과제로 둔다. 오류 동안 마지막 확정 Fail-safe를 유지하며 무효 센서값으로 위험 전이나 정상 복귀를 판단하지 않는다. 실제 범위 밖 입력을 clamp하여 센서 정상으로 숨기지 않는다. 복구 heartbeat와 공백 후 추정 정확도 인수는 별개다. 상세 수행·snapshot 목록은 plan ECU M3를 따른다.


### S-7=A 평가 경계

가상 10직렬/50Ah 장비 모델은 ADC 취득·상태 통보·IVI 전달 검증에 사용한다. NASA 단셀 자료는 원시 단위의 재생·데이터 검증으로 유지한다. FR-BMS-002/TC-BMS-002의 정량 비교는 별도 참 상태와 동일 관측을 사용하는 합성 시험으로 분리한다. 상세 인수는 TEST_PLAN의 S-7=A 절을 따른다. 합성 생성기의 모델·관측 오차는 TEST_PLAN의 S-21=A, 제품 설정은 SOC-1/2 승인과 실제 `include/ekf_soc_estimator.h`를 따른다. 제품 기본 초기 SOC 75%와 시험 초기 SOC 80%를 구분한다. 이 계획 변경으로 실제 코드·모델 유효성·장비 인수를 완료했다고 해석하지 않는다.


2026-09-08 종합 정합성 검토: 현재/예정 경로, 승인 상태, 단위·측정·실행 예제를 대조·정정했다. 세부 변경과 보류 관문은 [종합 검토](development/reviews/문서_종합정합성_검토.md)에 기록한다. 기존 요구/TC ID와 ICD 계약 본문은 보존했다.


## 2026-09-09 승인된 SecOC 현행 규칙 정정

현행 고정키 수신 규칙은 [ICD §2.3~2.5](ICD.md#23-수신-검증-절차-node-b)를 따른다. 단순 대소 비교나 범위 밖 유효 MAC만으로 counter를 재동기화하는 이전 설명은 적용하지 않는다. 실제 C++/Python verify는 이 정정과 일치하며 알고리즘 변경은 없다. 첫 수신 MAC 성공은 새 부팅을 증명하지 못하고, 수신기 재부팅 후 과거 메시지 수락 위험이 남는다. 요구사항의 replay 방어 기준을 낮추거나 전체 보안 인수를 완료 처리하지 않는다.

인증 세션 자동 복구의 승인된 방향은 유지한다. 세션 상세 계약·양측 전환·재부팅 보안 시험은 [세션 설계안](development/security/CAN_세션인증_설계안.md)의 별도 관문이다. 새 wire·키 파생·HAL 변경을 이번 정정 승인으로 포함하지 않는다.

## CAN IDS 소프트웨어 실행 경로 (CHG-007)

`security/ids/runtime_detector.py`와 `runtime.py`에 시간 주입 탐지·규칙·독립 SecOC 관찰·기존 IF 연동·JSONL replay·SocketCAN 수신/0x200 송신을 구현했다. 0x200/7차원 특징/기존 오프라인 평가 계약은 유지한다. 원인 미확정 이상은 로컬 진단으로만 남기고 wire 공격 종류를 추가하지 않는다. 임계·버퍼·IF 모드·전송 제한·키 부재 동작은 [IDS README](../security/ids/README.md)에 명시한다. 승인 대기인 Node B 인증 이벤트 전송과 세션 프로토콜은 구현하지 않았다. [시험 증거](aidlc/changes/CHG-007/audit.md).


### 센서 오류·회복 보완 (2026-11-11)

기존 인증 NodeStatus의 입력 품질을 ECU 오류 경로에서도 전달한다. IVI는 최근 입력 오류 보고와 통신 단절을 구분하고, 정상 품질 보고에 더해 새 BMS 수신을 확인한 뒤 stale을 해제한다. 상세 구현·호스트 시험·물리 미검증 범위는 [CHG-029 추가 증거](aidlc/changes/CHG-029/evidence.md)의 센서 오류 전달·회복 절을 따른다.


### 과열 복귀 구현 — 2026-11-11

FailSafeStateMachine의 monotonic evaluate overload가 5초 연속 구간과 최대200ms 관찰 간격을 검사한다. main은 ADC 오류/준비/회복 gate에서 inputUnavailable을 호출하여 냉각 시간을 초기화한다. 오래된 ADC 값을 재사용하여 5초를 채우는 것을 HardwareSampleFeed freshness gate로 막는다. Fail-safe snapshot v2는 critical_latched를 보존하지만 냉각 시각은 저장하지 않는다. 이전 v1 SHUTDOWN 저장본은 저전압 이력 미상이므로 보수적으로 CRITICAL 이력이 있는 것으로 복원한다. 새 v2 checkpoint는 이전 바이너리에 그대로 되돌려 사용하는 형식이 아니다. ADS1115 모드의 온도는 기존 가상25°C이며 과열 검증에는 온도 profile을 사용한다.


### 관리형 IDS 세대별 로그 수집

관리형 IDS의 실행별 로그는 별도 UUID generation과 `owned-ids-<generation>` run_id로 귀속한다. 준비 확인 시 `OWNED_IDS_READY` JSON에 generation/PID/mode/protocol/분류 버전만 알린다. 키·설정·경로는 이 메시지에 넣지 않는다. 개인 로그 디렉터리의 owner.lock은 관리자와 IDS child가 함께 보유하고 종료 뒤 닫는다. session_ids_log 수집기는 활성 잠금을 거부하고 선택한 실행의 events.jsonl/process.log만 권한·형식·길이·hash와 함께 수집한다. 수집 완료는 실험 유효 판정과 구분하며 PC 전체 제어기 연결은 아직 진행 중이다.

### BMS 계산 작업 복구 제품 연결 — 2026-11-11

recovery/checkpoint 실행에서 BmsCalculationTask를 실제 main에 연결했다. 1초 감시·3초 무진행·1초 회수 기한·최대3회 실제 실패를 사용한다. 메모리 상태 나이는 기존 명시적 checkpoint 정책을 적용한다. sensor/EKF/SOH 복사본의 정상 결과만 owner가 반영하며 Fail-safe와 세션 소유권은 owner에 유지한다. 기존 작업을 회수하지 못하면 운영자 확인으로 전환하고 중복 생성/자동 전체 재시작하지 않는다. ADC 입력 대기는 계산 작업 실패로 세지 않는다. 상세 증거와 CAN 수신 작업 미완료 범위는 CHG-029의 재개1단계 기록을 따른다.


### 인증된 IVI 거부 진단의 IDS 소비 — 2026-11-12

session-v2에서 IVI가 명시적으로 활성화한 RejectionRecord를0x303으로 보내면 ECU Exchange가 인증/세션/순번을 검증한다. 이 결과를 로그만 남기던 경로에서 supervisor 소유의 별도 비차단 pipe→PeerDiagnostics 소비까지 연결했다. --ids-peer-fd/--peer-rejection-fd는 private 상속 FD이며 공격 Pi3나 외부 네트워크에 전달하지 않는다. 기존 context pipe와 구별하고 두 writer/reader 수명은 해당 ECU/IDS 세대에 묶는다.

로컬CPR1/144B는 세대/현재 세션/기존80B본문・ECU수신/검증/발행 시각・envelope 순번・누적로컬drop을 보존한다. ECU수신/검증은ms 원시값을ns 단위로 표현한 것이며1ns 측정 해상도가 아니다. IDS는 현재context・64칸 미수신 역순 허용/중복 배제・검증 후3초 로컬 상한・본문 의미를 검사한다. 같은거부UUID의 같은 내용은 중복, 다른 내용은 모순으로 보존한다. 한poll8개/UUID256개/최근1초 집계256개 제한과 집계 불완전을 기록한다. 미래/잘못된 형식/EOF는 이 채널만 불가로 표시하며 raw/IF 경로를 닫지 않는다.

PEER_REJECTION_CONSUMED는 별도 진단이다. Rule/IF 특징·모델·네 유형 분류·새 경보 임계를 바꾸지 않는다. 원래 IVI 이벤트 생성 시각이나 노드 간 지연/공격자 신원은 이 메시지만으로 알 수 없다. IVI의 거부 송신 옵션이 없으면 해당 CAN 보고가 전송되지 않으며 소비0개를 거부0개/전체 방어 성공으로 해석하지 않는다. 실제 연결/회귀 근거는 [CHG-029 상태](aidlc/changes/CHG-029/aidlc-state.md)를 따른다.


### 시험 전용 sender 제어 경계

A5/A6 보완에는 Linux/ECU_BUILD_TESTS에서만 생성하는 ecu_sender_control_fixture를 사용한다. main의 BMS middleware publish 직전 compile-time gate이며 원본/auth를 함께 보류하고 계산/Fail-safe/진단은 유지한다. 상속 전용 read pipe·반복 연장 없는2초 개발 guard·EOF/오류 재개를 검사한다. 제품 target/설치/ICD API에 제어 옵션을 추가하지 않는다. 상세/실행 경계는 [보완 절차](development/playbooks/session-campaign.md#a5a6-보완-시험-정상-송신-중단복구)를 따른다.


### 실제 태스크 성공 복구 관찰

main의 BMS/RX 복구 로그는 owner의 실제 작업 세대/단조시각을 기록한다. RX frames는 callback 완료 뒤 증가한 값이며 thread start 자체를 완료로 쓰지 않는다. CanReceiveRecovery의 내부 generation 읽기만 추가했고 CanDriver/HAL 인터페이스와 CAN 본문은 유지한다. 시험 전용 ecu_bms_recover_fixture는 한 번의 계산 실패 후 정상 계산을 허용하며 설치하지 않는다. 기존 WARNING을 유지한 실제 새 작업/인증 IVI 입력의 성공 검증은 [TC-BSW-006 하위 근거](aidlc/changes/CHG-029/task-recovery-success-20261112.json)를 따른다.

### N03 기존 규칙의 판단 근거 출력

기존 RuntimeDetector/SessionDetector의 판단 지점이 RuleEvent.finding에 관찰/기대/단위・규칙/profile 버전・로컬 식별/수신 epoch·로컬 인증 검사 여부를 기록한다. 기존 Event 인수/분류·임계·IF7특징·CAN 본문은 유지한다. ModelEvaluation도 실제 score/특징과 단위를 보존하고 replay/live logger가 이 필드를 저장한다. severity는 미보정/null이며 기존 anomaly_score와 별개다. [스키마/원인별 한계](../security/ids/README.md#n03-로컬-판단-근거-ids-finding-v1)와 [실행 근거](aidlc/changes/CHG-029/rule-findings-20261112.json)를 따른다. 추가 규칙/IF 효과·긴 실험 로그 수집 용량은 별도 인수다.

### N02 기존 제품 입력의 출처 기록

제품 시작의 ECU_INPUT_LINEAGE/ecu-input-lineage-v1은 로컬 로그이며 CAN/HAL을 확장하지 않는다. configuration은 입력 방식/단위/실제 변환/파일 내용 SHA256·바이트 수/고정seed/SOH 정책, state는 현재 CSV 위치/복원된 SOH 경과시간/난수 상태 hash, instance_id와 start_intent는 이번 프로세스·standalone/fresh/resume을 기록한다. 생성 함수는 입력을 소비하거나 난수 엔진을 진행하지 않는다.

SensorSimulator와 SohCapacityScenario는 실제 파싱할 바이트를 한 번 읽어 raw hash와 기존 복원 prefix hash를 함께 만든다. 기존 복원16MiB 상한을 standalone CSV에도 적용한다. 파싱 완료 후 내용/지문을 함께 게시하며 main은 CAN/worker 시작 전에 센서 CSV를 검증한다. 파일 경로를 다시 열어 따로 만든 hash를 실제 파싱 입력인 것처럼 기록하지 않는다. 파일 교체 후 이미 로드한 입력은 유지하고 다음 실행은 새 내용으로 식별한다. 비유한 CSV 전압/전류/온도는 거부하고 유한 온도는 기존 반올림/clamp 결과를 유지하면서 정수 overflow를 피한다.

| 모드 | 기록하는 실제 의미 |
|---|---|
| constant | 가상42V/-2A/25°C. 실제 배터리 정상 상태를 입증하지 않음 |
| profile_csv | 첫3개 관측 V/A/°C, float 변환·온도 반올림/[-10,70] clamp, 행 위치·끝값 유지. 기존 빈 자료 nominal fallback도 명시하며 정상 캡처로 인증하지 않음 |
| random_walk | 고정seed12345/mt19937·normal_distribution<float>/범위와 복원된 엔진 상태 hash. 다른 표준 라이브러리 간 bit 단위 재현을 보장하지 않음 |
| ads1115 | A0 ADC·고정0x48, 선택 device 문자열의 hash/원문 미출력, ADC 단위·±32code 끝점/선형 가상30..42V·가상-2A/25°C·새3회/200ms 조건. 실제 팩 측정이나 시동 시 유효 ADC 취득을 입증하지 않음 |
| 별도 SOH | 가상50Ah와 선택 CSV hash/step 수/초·Ah·이전 step/끝값 유지·복원 경과시간. 실제 열화 실증이 아님 |

ground_truth_label=unattested로 기록하여 소스 선택과 정상/결함/공격 정답 라벨을 구분한다. PC는 이 로그의 재현 가능한 configuration을 실행 형상에 보존하고 요청 모드·pilot·방어 구성 사이의 일치를 검사한다. 프로세스마다 바뀌는 UUID/복원 위치를 같은 configuration hash인 것처럼 비교하지 않는다. 새 freeze/plausibility·fault 생성기/실험 정답 라벨·severity calibration·IF 추가 효과와 물리 인수는 별도다.

N02 후속 합성 생성기는 tools.quality.sensor_scenarios다. 기존 S-21 궤적과 허용 고정 입력 대조군에 명시적 drift/jump/freeze·전압/전류 불일치를 적용하며, source-fault 라벨은 native/IDS에 전달하지 않는다. 분석용 evaluate_soc_profile의 --emit-bms만 기존5열 뒤 실제 encodeBmsStatusFrame의8B를 덧붙인다. 기본 출력/제품 main/CAN 형식은 유지한다. 기존 legacy/session raw 규칙 관찰은 공개 더미 인증 fixture이며 실제 IVI 판정이 아니다. 소스 고장과 동일한 CAN 입력을 만들 수 있는 정상 대조군을 보존하고, 임계 보정/운영 범위 결정 전에 새 freeze/plausibility 유형으로 송신하지 않는다. [재현과 결과](aidlc/changes/CHG-029/sensor-source-supplement-20261112.json).

### 2026-11-14 보호 사건 계보·CAN 전달 설계

계산 상태 계보와 보호 사건 UUID/revision을 기존 복원 상태에 함께 보존한다. 자동 resume은 검증된 저장본을 사용하고 구형 식별자 없는 snapshot은 연속성 미상/새 계보로 구분한다. 세션 키/counter는 저장하지 않는다. 상태 변경/정상 복귀는 동일 사건 revision, 이후 재발은 새 사건이며 번호 소진 시 자동 순환하지 않는다. [CAN 진단 종류8](ICD-CAN-DIAGNOSTIC.md)에 현재 instance/계보/사건을 담고 진단 송신이 BMS/보호를 기다리게 하지 않는다.2026-11-14 승인된 설계이며 checkpoint·실제 발행·IVI 제품 연결은 단계별 구현/검증 후 완료한다.

저장·복원 단계 구현: `ProtectionHistory`는 owner 스레드에서 위험 상태를 관찰하며 `RecoveryCheckpoint` payload v2의 선택적 보호 snapshot으로 보존한다. 파일 integrity envelope `CAPSTONE-CHECKPOINT-V1`/SHA256/원자 교체·상한은 유지하고 payload v1도 읽는다. v2는 기존 rng 행 뒤 `protection 0` 또는 `protection 1`과 version/lineage/incident/state/reason/phase/revision을 기록한다. v1에 새 메타데이터를 넣거나 계산 상태와 다른 사건 상태를 복원하지 않는다. 기존 수신 프로그램은 payload v2를 읽을 수 없으며 자동 하향 저장하지 않는다. 메타데이터 소진/실패는 v2의 명시적 정보 없음으로 저장하고 계산/보호는 계속한다. 구형 NORMAL/복귀 사유에서 확인되지 않은 종료 사건을 생성하지 않는다. 실제 CAN 발행·IVI 연결은 후속이며 [현재 검증](aidlc/changes/CHG-029/protection-checkpoint-20261114.json)을 따른다.

CAN 발행 연결: `ProtectionPublisher`는 owner의 상태 갱신에서 최신 본문을 받고 대기 메시지1개/한 pump당1프레임으로 송신한다. main은 기존 NodeStatus1초 갱신을 공유하고 큐 만료는 명시한 `diagnostic_assembly_ms`를 사용한다. 고정 큐/프레임 상한은 구조 제한이며 실제 Pi 지연/처리량 보장이 아니다. 세션 변경/메타데이터 없음은 이전 대기를 지우고, 실패한 프레임/메시지를 그대로 재시도하거나 순번을 되돌리지 않는다. 다음 갱신은 새 순번이다. 시각 역행/codec 실패는 발행기를 격리하며 새 인증 세션 전에는 실패를 숨겨 초기화하지 않는다. 일반 BMS/위험 판단과 별도인 진단 경로다.


### 2026-11-16 — R02/R03/R05 구현 경계

R02 센서 추가 검사는 알려진 합성 프로필과 native 관측을 비교하는 상세 로그 도구로 우선 구현한다. 자유 조작 ADS/실제 배터리의 운영 임계나 CAN 공격 분류를 추가하지 않는다. R03은 IVI 동일 boot/monotonic 시계에서 식별 가능한 최초 공격 관찰부터 새 사건의 완전한 인증·의미 검증까지 평가하며 목표3초·화면 지연 별도를 유지한다. MAC/본문 인증과 사건 revision/관찰 순서 수용을 구분하고 의미 수용 플래그·완료 시각을 제품 관찰 로그에 남긴다. R05는 동일 QML/실행본 분리를 유지하고 데스크톱 소유권·협조 종료·PC stdin 수명의 실험 lease·단일 Wayland 화면·종료 후 기존 앱 복원을 연결한다. 관리되지 않은 앱이나 회수/복원 불명은 성공으로 처리하지 않는다. 계약 바이트는 변경하지 않는다. 정의/합격 기준은 [TC-PERF-003](TEST_PLAN.md#tc-perf-003-ids-탐지-응답-시간), 운영 절차는 [session campaign](development/playbooks/session-campaign.md)을 따른다.


### 2026-11-17 수신 순서 보완과 Fail-safe 시간 변환

live IDS의 OrderedSocketCan은 커널 수신시각 자체를 바꾸지 않고 최대4096개/1ms의 제한된 재정렬 구간에서 순서를 정리한다. 뒤늦은 프레임이 이미 공개한 watermark보다 앞서면 상세 시각/ID와 함께 epoch 오류로 처리하고, 용량 초과도 관찰 공백으로 남긴다. 기존10ms realtime→monotonic 매핑 변화·잘린 프레임·드롭/처리 지연 검사는 유지한다. 1ms는 로컬 순서 정리 예산이지 물리Pi 운용값 인수나 시계 오류 허용치 완화가 아니다. 실제Pi는 별도 검증한다.

FailSafeStateMachine의 시간 단위 변환만 로컬 noexcept 함수로 분리한다. 계산/임계·상태 전이·냉각5초·콜백 예외 전파를 유지하며 전체 FSM 함수를 noexcept로 바꾸지 않는다. gcov 예외 필터/분모 제외 없이 새 객체로 커버리지를 검증한다. [진행](aidlc/changes/CHG-030/aidlc-state.md).
