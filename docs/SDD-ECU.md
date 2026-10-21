> **문서명**: Software Design Document — Node A (ECU) (SDD-ECU)  
> **버전**: v1.8 | **작성일**: 2026-03-15 | **최종 수정**: 2026-10-03 | **작성자**: 팀원A  
> **참조**: ICD v1.6, SRS v1.6 (FR-BSW-*, FR-BMS-*, FR-SEC-*), ADR-001/002/003/005/008/009/011/012

---

# 1. 문서 개요

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

2026-09-08: 아래 구조도·API 골격은 설계 설명이다. `BmsComponent` 독립 파일은 없고 현재 조립·주기 실행은 `adaptive_ecu/main.cpp`가 담당한다. 실제 API는 각 `include/*.h`가 근거이며 아래 축약 이름으로 호출 코드를 복사하지 않는다. Python 실시간 도구의 현재 경로는 §3.8을 따른다. 실험 당시 버전과 인수 제한은 [실측 추적](development/experiments/physical-ablation-formal-2026-10-04/METHODS-AND-TRACEABILITY.md)에 연결한다. AUTOSAR를 참고한 교육용 구조이며 표준 구현·인증을 주장하지 않는다.

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

```cpp
template <typename T>
class Publisher {
private:
    std::vector<std::function<void(const T&)>> subscribers_;
    mutable std::mutex mtx_;

public:
    void subscribe(std::function<void(const T&)> callback) {
        std::lock_guard<std::mutex> lock(mtx_);
        subscribers_.push_back(std::move(callback));
    }

    void send(const T& data) {
        std::lock_guard<std::mutex> lock(mtx_);
        for (auto& sub : subscribers_) {
            sub(data);
        }
    }

    size_t subscriberCount() const {
        std::lock_guard<std::mutex> lock(mtx_);
        return subscribers_.size();
    }
};
```

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

### 3.4.2. SOH 추정 로직

```
Q_current = supplied_estimated_capacity
SOH = (Q_current / Q_initial) * 100.0
```

- S-4=A: Q_current는 가상 용량 열화 시나리오가 제공하는 추정 용량(Ah)이다. 50Ah에서 45Ah로 변경하면 SOH는 90%다. 실제 배터리 수명 추정의 검증을 뜻하지 않는다.
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
                                     │ 수동 리셋
                                     ▼
                                  NORMAL
```

> CRITICAL에서 NORMAL로 직접 복귀하는 경로는 **의도적으로 두지 않는다**. SOC 5% 미만까지 떨어진 배터리는 자동 복구 대상이 아니며, SHUTDOWN을 거쳐 수동 리셋으로만 해제한다 (ICD §1.3 사유 코드 `0x05`는 WARNING → NORMAL 전용).

**Watchdog 실패에 의한 전이** (FR-BSW-006, NFR-REL-001/002): WatchdogManager가 감시 대상 태스크의 재시작을 3회 연속 실패하면 NORMAL → WARNING으로 전이하고 ICD §1.3의 사유 코드 `0x07`로 `0x101`을 송신한다. 재시작 실행 주체는 태스크를 소유한 `main`이며, WatchdogManager는 타임아웃 감지와 횟수 집계만 담당한다.

**상태별 동작:**

| 상태 | 동작 |
| --- | --- |
| NORMAL | 정상 운전, 100ms 주기 BMS 데이터 전송 |
| WARNING | 경고 상태 0x101/0x103 인증 통보; 승인된 취득 요청 간격 유지 |
| CRITICAL | CRITICAL 상태 전이 0x101/0x103 인증 통보; 승인된 취득 요청 간격 유지 |
| SHUTDOWN | SHUTDOWN 상태 전이 0x101/0x103 인증 통보; 실제 전원 차단은 필수 범위 밖 |

## 3.4.4. CAN Publisher (BMS → CAN 전송 브릿지)

**파일**: `adaptive_ecu/src/bsw/can_publisher.cpp`

BmsComponent의 Publisher 이벤트를 구독하여 CAN 프레임으로 변환·전송하는 BSW 모듈이다. Application 계층(BMS)과 CAN 드라이버 사이의 데이터 흐름을 연결한다.

```cpp
class CanPublisher {
private:
    CanDriver& driver_;
    SecOcModule& secoc_;
    std::atomic<bool> running_{false};
    std::thread tx_thread_;
    static constexpr int TX_PERIOD_MS = 100;

public:
    CanPublisher(CanDriver& driver, SecOcModule& secoc);
    void start();
    void stop();
    void onBmsStatus(const BmsStatusData& data);
    void onFailSafeEvent(const FailSafeEvent& event);
private:
    CanFrame encodeBmsStatus(const BmsStatusData& data);
    CanFrame encodeFailSafe(const FailSafeEvent& event);
};
```

**동작**:
1. `Publisher<BmsStatusData>`를 구독하여 `onBmsStatus()` 콜백 수신
2. ICD §1.2 레이아웃으로 8바이트 CAN 프레임 인코딩
3. `SecOcModule::sign()`으로 인증 프레임(0x102) 생성
4. `CanDriver::send()`로 원본(0x100) + 인증(0x102) 순차 전송
5. Fail-safe 이벤트는 이벤트 기반으로 0x101 + 0x103 즉시 전송

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

아래 트리는 초기 목표 배치로 현재 파일 목록이 아니다. 현재 공격 CLI는 `security/attacks/attack_simulator.py`, 실시간 IDS는 `security/ids/runtime.py`와 `runtime_detector.py`, 실험은 `security/experiments/{can_capture,evaluate_normal,live_ablation,summarize_live,publication}.py`다. 별도 pickle 저장 모델을 읽는 경로는 사용하지 않는다. 실제 파일과 테스트/실측 인수는 구분하며 [CHG-014](aidlc/changes/CHG-014/aidlc-state.md)를 따른다.

```
security/
├── secoc_module.py           # SecOC HMAC-SHA256 인증 모듈 (C++ 이식 전 프로토타입)
├── attack_simulator.py       # CLI 엔트리포인트
├── attacks/
│   ├── __init__.py
│   ├── fuzzy_attack.py       # Fuzzy Attack 구현
│   ├── replay_attack.py      # Replay Attack 구현
│   ├── spoofing_attack.py    # Spoofing Attack 구현
│   └── flooding_attack.py    # Flooding Attack 구현
├── ids/
│   ├── __init__.py
│   ├── feature_extractor.py  # 1초 슬라이딩 윈도우 특징 추출
│   ├── ids_engine.py         # Isolation Forest 학습/탐지
│   └── ids_alerter.py        # 탐지 결과 CAN 0x200 전송
├── data/
│   ├── normal_traffic.csv    # 정상 트래픽 학습 데이터
│   └── models/
│       └── isolation_forest.pkl  # 학습 완료 모델
├── collect_normal.py         # 정상 트래픽 수집 스크립트
├── train_model.py            # IDS 모델 학습 스크립트
├── tests/
│   ├── test_attack_simulator.py  # 공격 시뮬레이터 단위 테스트
│   ├── test_ids_engine.py        # IDS 엔진 단위 테스트
│   └── test_ids_alerter.py       # IDS 경보 전송 단위 테스트
└── requirements.txt          # python-can, scapy, scikit-learn, numpy, pandas
```

### 3.8.2. CLI 인터페이스

현재 `python -m security.attacks.attack_simulator --help`의 `--type` 선택 CLI가 존재한다. 실제 캠페인은 `security.experiments.live_ablation`을 사용했으며 수신·송신 소유권, 유한 재시도, 결과 원장을 함께 기록한다. 구체적 옵션과 재현은 [실행 플레이북](development/playbooks/live-security-validation.md)을 따른다.

### 3.8.3. 공격별 핵심 로직

현재 시험 구현의 경로는 `security/attacks/attack_simulator.py`와 `security/experiments/live_ablation.py`다. 초기 제안의 무한 송신/고정 캡처 절차와 구분한다.

| 공격 | 현재 프레임 생성/선택 | 실행 구분 |
| --- | --- | --- |
| Fuzzy | seeded RNG의 11-bit ID와 8-byte payload | seed와 실제 송신·오류를 원장에 보존 |
| Replay | 단독 도구는 고정 예시 BMS; 물리 Ablation은 관측·수용된 BMS/auth 쌍 선택 | SecOC ON은 실제 관측 쌍, OFF는 원본 BMS 사용 |
| Spoofing | 0x100, SOC raw=200과 고정 변조 payload | 인증 없는 주입이며 정상 인증 프레임과 결합한 게시를 별도 해석 |
| Flooding | 0x000, 8-byte zero payload | 기한·요청률·유한 송신 재시도와 실제 점유율 측정 |


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

### 3.9.3. 실시간 탐지 흐름

CAN 수집 → 1초 윈도우 확정 → §3.9.1 특징 → 학습된 IF 점수 → 사전 고정한 임계 판정 → ICD §1.5의 0x200 경보 순서다. 수집·학습·경보 전송은 `security/ids/runtime.py`에 구현되어 있으며 실행 시 검증한 정상 입력에서 학습한다. 외부 직렬화 모델 역직렬화는 사용하지 않는다. 단위 시험과 실제 공격 인수는 [실측 추적](development/experiments/physical-ablation-formal-2026-10-04/METHODS-AND-TRACEABILITY.md)에서 구분한다.

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

### 3.9.5. 실시간 IDS 규칙 임계 확정과 정상 오탐 (EXQ-11)

Config 3의 탐지는 `security/ids/runtime_detector.py`의 규칙으로 판정한다(스트리밍 탐지기). 사용자 결정 [EXQ-11=A](development/governance/보안실험_통합시험_진행결정.md#answers-applied)에 따라 아래 기본 임계를 **확정 동작점**으로 쓰고, 정상 트래픽만 넣은 오탐을 먼저 측정했다. 이 임계는 ROC로 고른 값이 아니라 공학적 기본값이며, 규칙 베이스라인 ROC(`rule_baseline.py`)와는 다른 탐지기다.

| 규칙 | 확정값 | `Config` 필드 |
| --- | --- | --- |
| 최소 주기 | 50 ms | `min_period_s=0.050` |
| 메시지 누락 | 300 ms | `missing_s=0.300` |
| 인증 대기 만료 | 100 ms | `pending_s=0.100` |
| 초당 프레임 | 100 | `max_frames_per_second=100` |
| 1초 내 실패 반복 | 3 | `failure_repeat_count=3` |
| SOC 변화 | 20 %p | `max_soc_step=20.0` |
| 온도 변화 | 20 °C | `max_temperature_step=20.0` |
| 전류 변화 | 100 A | `max_current_step=100.0` |

**정상 오탐 측정(합성, 사전검증).** `security/experiments/measure_runtime_fpr.py`로 Node A 정상 트래픽(0x100 10 Hz + 0x102, seed 20261003, 149.918 s, 2998프레임)을 위 임계의 탐지기에 넣었다. 완료 1초 창 **149개 중 오탐 0개, FPR 0.00%** 로 TC-EXP-005 기준(≤5%)을 합성 등급에서 충족했다. 단위 시험은 `security/tests/test_measure_runtime_fpr.py`다.

> 이 수치는 **합성(grade 1)** 사전검증이다. 잘 짜인 정상 트래픽에 대한 느슨한 규칙 임계의 결과이며, 실제 버스의 기동 과도·지터·다른 ID 혼입은 반영하지 않는다. **TC-EXP-005 최종 오탐은 물리 CAN 정상 캡처로 판정**하고 그 결과를 이 표와 별도로 기록한다. 측정 환경이 바뀌어 오탐이 5%를 넘으면 임계를 EXQ-11 B안(선정용/평가용 분리 보정)으로 다시 정한다.

---

# 4. 데이터 흐름도

```
[센서 입력: 전압, 전류, 온도]
        │
        ▼
  BmsComponent.update()
        │
        ├─▶ EkfSocEstimator.estimate() → SOC
        ├─▶ SohEstimator.update() → SOH
        ├─▶ FailSafeStateMachine.evaluate() → 상태 전이 판단
        │
        ▼
  Publisher<BmsStatusData>.send()   → 구독자 통지
  Publisher<FailSafeEvent>.send()   → (전이 시만)
        │
        ▼  (구독자: CanPublisher)
  CanPublisher.onBmsData() / onFailSafeEvent()
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
| AttackSimulator | TC-SEC-005 (a~d) | FR-SEC-005 | 예정: `security/tests/test_attack_simulator.py` |
| IdsEngine | TC-SEC-006 | FR-SEC-006 | 예정: `security/tests/test_ids_engine.py` |
| IdsAlerter | TC-SEC-007 | FR-SEC-007 | 예정: `security/tests/test_ids_alerter.py` |

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
| v1.8 | 2026-10-03 | §3.9.5 추가 — 실시간 IDS 규칙 임계 확정값(EXQ-11=A)과 정상 오탐 합성 사전검증(149창 중 0건, FPR 0.00%). 최종 오탐은 물리 CAN에서 판정 | 사용자 |
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
