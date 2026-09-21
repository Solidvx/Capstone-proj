# ECU M2 — CAN CDD, Mock, Publisher, BMS 송신

> **예시 상태**: 코드·명령은 별도 검증 표시가 없으면 작성 골격·예정 절차다. 실행 전 생성할 파일·의존성·플랫폼을 확인한다. [공동 규약](../common/00_협업_규약.md)의 문서·예시 사용 규칙을 따른다.

> 상위 계획: [ECU.md](../../ECU.md) · 공동 절차: [00_협업_규약](../common/00_협업_규약.md) · 인계: [01_연계_의존성](../common/01_연계_의존성.md)
> 원본: `_archive/ECU.md` M2, `_archive/ECU_최종_실행계획서.md` §6

---

## 1. 목적과 범위

Mock과 SocketCAN을 같은 `CanDriver` 인터페이스로 교체 가능하게 만들고, `0x100` BMS_Status를 100ms 주기로 송신한다. `Publisher<T>` ara::com 패턴과 센서 입력 소스를 확보한다.

| 항목 | 값 |
|---|---|
| 연결 요구사항 | FR-BSW-001~007 |
| 연결 시험 | TC-BSW-001~005, TC-BSW-008-a~c, TC-BMS-007 (TC-BSW-008-d는 M3) |
| 산출물 | `mock_can_driver.cpp`, `can_cdd.cpp`, `publisher.h`, `sensor_simulator.cpp`, `can_publisher.cpp`, 100ms 송신 루프, 배터리 프로파일 CSV |
| 태그 | `v0.2.0` |

### 주차별 작업

| 주차 | ECU 작업 | IVI 연계 |
|---|---|---|
| 1주차 | `MockCanDriver`, `SensorSimulator::Mode::CONSTANT` | HAL Mock에 `0x100` 샘플 제공 |
| 2주차 | SocketCAN CDD, TC-BSW-001~003 | Node B parser 시험 입력 공유 |
| 3주차 | `Publisher<T>`, 배터리 데이터셋 확보·CSV 변환 | Plan A/B 미팅 참여 |
| 4주차 | 100ms 주기 송신, 프로파일 전처리 완료 | `0x100` 해석값 상호 확인 |

---

## 2. 선행조건과 현재 구현 상태

**선행조건**: [M1](M1_환경구축_ICD확정.md) 완료 — CAN 인터페이스 UP, 빌드 도구, `can_driver.h` 확정.

**현재 구현 상태 (확인 기준일 2026-09-05, 실제 파일 확인)**

| 대상 | 상태 | 실제 내용 |
|---|---|---|
| `src/bsw/mock_can_driver.cpp` | **구현됨** | — |
| `src/bsw/can_cdd.cpp` + `include/can_cdd.h` | **구현됨** | `SocketCanCdd : CanDriver`, `receiveLoop()` 별도 스레드, `callback_mutex_` 보호 |
| `include/publisher.h` | **구현됨** | 스냅샷 후 콜백 호출 방식 (세대B판) |
| `src/app/sensor_simulator.cpp` + 헤더 | **구현됨(계획 초과)** | `enum class Mode { CONSTANT, POTENTIOMETER, PROFILE_CSV, RANDOM_WALK, ADS1115_HARDWARE }`, `setAdc*()` 3종, `std::mt19937 rng_{12345}` 고정 seed |
| `src/bsw/can_publisher.cpp` | **구현됨** | 클래스가 아니라 자유 함수 `encodeBmsStatusFrame()`, `encodeFailSafeFrame()` |
| `include/bms_types.h` | **구현됨** | `BmsStatusData`, `FailSafeEvent` |
| **100ms 주기 루프** | **구현됨** | `adaptive_ecu/main.cpp` 안. `sleep_until(cycle_start + 100ms)` |
| `src/app/bms_component.cpp` | **없음** | 세대B가 참조했으나 존재하지 않음. `main.cpp`가 그 역할을 한다 |
| `test/test_can_cdd.cpp` | **없음** | TC-BSW-001~003 자동화 미구현. 아래 3.5 참조 |
| 배터리 프로파일 | **존재** | `adaptive_ecu/data/battery_profile.csv` (변환 스크립트는 저장소에 없음) |

**등록된 CTest 이름 13종** (`adaptive_ecu/CMakeLists.txt`):
`test_ads1115_conversion`, `test_sensor_quality`, `test_adc_acquisition_gate`, `test_ads1115_registers`, `test_publisher`, `test_mock_can_driver`, `test_sensor_simulator`, `test_can_publisher`, `test_ekf_soc`, `test_soh_estimator`, `test_failsafe_sm`, `test_watchdog_manager`, `test_secoc`

> 원본 계획의 `ctest -R test_can_cdd`, `ctest -R test_bms_component`는 **존재하지 않는 대상**이다. 4장의 명령을 사용한다.

### 통합 시 해소한 충돌

| 항목 | 세대A | 세대B | 채택 |
|---|---|---|---|
| `0x100` 인코딩 | `static_cast<uint8_t>(soc/0.5f)` — 절삭, 범위 검사 없음 | `std::lround` + `std::clamp(0,200)` | **세대B** — 실제 `can_publisher.cpp`와 일치. 절삭 방식은 0.5% 단위에서 최대 1 LSB 오차 |
| `Publisher::send` | 락을 잡은 채 콜백 호출 | 스냅샷 복사 후 락 해제하고 호출 | **세대B** — 실제 구현과 일치. 콜백 안에서 `subscribe()` 호출 시 데드락 회피 |
| 주기 송신 구조 | `CanPublisher` 클래스 + 스레드 + `sleep_for(100ms - elapsed)` | 루프 + `sleep_until(start + 100ms)` | **세대B** — 실제 `main.cpp`와 일치. `sleep_until`이 누적 드리프트에 강함 |
| 온도 인코딩 상한 | 명시 없음 | `clamp(temp+40, 0, 255)` | **실제 구현** — `clamp(temp+40, 0, 165)`. ICD 유효 범위 -40~125°C에 맞춤 |

---

## 3. 수행 절차

### 3.1 MockCanDriver 확인

`adaptive_ecu/src/bsw/mock_can_driver.cpp` — 아래 계약을 만족하는지 확인한다.

```cpp
#include "can_driver.h"
#include <mutex>
#include <vector>

class MockCanDriver : public CanDriver {
public:
    bool open(const std::string& interface) override {
        interface_ = interface;
        opened_ = true;
        return true;
    }
    void close() override { opened_ = false; }
    bool send(const CanFrame& frame) override {
        std::lock_guard<std::mutex> lock(mtx_);
        sent_frames.push_back(frame);
        if (callback_) callback_(frame);   // loopback: 즉시 콜백
        return opened_;
    }
    void registerCallback(CanCallback cb) override { callback_ = cb; }
    void startReceive() override { receiving_ = true; }
    void stopReceive() override { receiving_ = false; }

    std::vector<CanFrame> sent_frames;     // 테스트 헬퍼

private:
    std::string interface_;
    bool opened_ = false;
    bool receiving_ = false;
    CanCallback callback_;
    std::mutex mtx_;
};
```

핵심은 `send()`가 **열려 있을 때만 true**를 반환하고 loopback 콜백을 호출하는 것이다. `sent_frames`는 시험에서 송신 내용을 검사하는 통로다.

### 3.2 SensorSimulator 모드

SRS FR-BSW-007이 규정하는 모드는 **4개**다.

| 모드 | 용도 | CLI 인자 |
|---|---|---|
| `CONSTANT` | 기본. 42.0V / -2.0A / 25°C 고정 | `--sensor-mode constant` |
| `PROFILE_CSV` | CSV 프로파일 재생 | `--sensor-mode profile_csv --profile <path>` |
| `RANDOM_WALK` | 랜덤 워크. `mt19937` seed **12345 고정**이라 재현 가능 | `--sensor-mode random_walk` |
| `ADS1115_HARDWARE` | 실제 I2C ADC. 가변저항으로 SOC를 실시간 조작 ([M3](M3_EKF_Failsafe_SecOC.md) 3.11) | `--sensor-mode ads1115` |

> **구현에 있는 5번째 모드 `POTENTIOMETER`는 삭제 대상이다.** SRS에 없고, 값 주입 경로가 없어 기본값만 반환하며, `ADS1115_HARDWARE`와 역할이 중복된다. 제거 절차는 [M3](M3_EKF_Failsafe_SecOC.md) 3.11.1.

```cpp
struct SensorData {
    float voltage_v = 42.0f;
    float current_a = -2.0f;
    int8_t temperature_c = 25;
};
```

> 필드명은 `voltage`/`current`/`temperature`가 아니라 **`voltage_v`/`current_a`/`temperature_c`**다. 원본 계획의 예제 코드와 다르다.

M2에서는 TC-BSW-008-a~c의 CONSTANT / PROFILE_CSV / RANDOM_WALK를 검사한다. TC-BSW-008-d의 ADS1115 실취득과 품질·복구 인수는 M3에서 수행하며, M2의 세 모드 성공을 TC-BSW-008 전체 통과로 기록하지 않는다.

### 3.3 SocketCAN CDD

`adaptive_ecu/include/can_cdd.h`의 실제 선언:

```cpp
class SocketCanCdd : public CanDriver {
public:
    SocketCanCdd() = default;
    ~SocketCanCdd() override;

    bool open(const std::string& interface_name) override;
    void close() override;
    bool send(const CanFrame& frame) override;
    void registerCallback(CanCallback callback) override;
    void startReceive() override;
    void stopReceive() override;

private:
    void receiveLoop();

    int socket_fd_ = -1;
    std::atomic<bool> running_{false};
    std::thread receive_thread_;
    std::mutex callback_mutex_;
    CanCallback callback_;
};
```

`open()`의 표준 흐름 — 구현을 수정할 때 이 순서를 유지한다.

```cpp
sock_ = socket(PF_CAN, SOCK_RAW, CAN_RAW);
if (sock_ < 0) return false;

struct ifreq ifr;
std::strncpy(ifr.ifr_name, interface.c_str(), IFNAMSIZ - 1);
if (ioctl(sock_, SIOCGIFINDEX, &ifr) < 0) return false;

struct sockaddr_can addr{};
addr.can_family = AF_CAN;
addr.can_ifindex = ifr.ifr_ifindex;
return bind(sock_, (struct sockaddr*)&addr, sizeof(addr)) == 0;
```

수신 루프는 별도 스레드에서 `read(sock_, &cf, sizeof(cf))`가 프레임 크기와 같을 때만 콜백을 호출한다. `stopReceive()`는 `running_ = false` 후 `join()` 한다.

**실물 확인:**

```bash
# 터미널 1: ECU 실행 (수신 대기 + 송신)
./adaptive_ecu/build/adaptive_ecu --interface can0

# 터미널 2: 외부에서 전송
cansend can0 100#DEADBEEF
# 기대: 프로그램 수신 로그
```

```bash
# vcan0 대체 경로
candump vcan0 &
cansend vcan0 100#0102030405060708
# 기대: vcan0  100   [8]  01 02 03 04 05 06 07 08
kill %1
```

### 3.4 `0x100` 인코딩 — ICD §1.2 계약

실제 `can_publisher.cpp` 구현이다. **인코딩 규칙을 바꾸면 ICD 변경 게이트를 거쳐야 한다.**

```cpp
namespace {
uint8_t encodePercent(float percent) {
    const int raw = static_cast<int>(std::lround(percent / 0.5f));
    return static_cast<uint8_t>(std::clamp(raw, 0, 200));
}

uint8_t encodeTemperature(int8_t temperature_c) {
    return static_cast<uint8_t>(std::clamp(static_cast<int>(temperature_c) + 40, 0, 165));
}
}

CanFrame encodeBmsStatusFrame(const BmsStatusData& data) {
    CanFrame frame{};
    frame.id = 0x100;
    frame.dlc = 8;

    const auto voltage_raw = static_cast<uint16_t>(
        std::clamp(static_cast<int>(std::lround(data.voltage_v / 0.01f)), 0, 65535));
    const auto current_raw = static_cast<int16_t>(
        std::clamp(static_cast<int>(std::lround(data.current_a / 0.1f)), -32768, 32767));
    const auto current_wire = static_cast<uint16_t>(current_raw);

    frame.data[0] = encodePercent(data.soc_percent);
    frame.data[1] = encodePercent(data.soh_percent);
    frame.data[2] = static_cast<uint8_t>((voltage_raw >> 8) & 0xFF);
    frame.data[3] = static_cast<uint8_t>(voltage_raw & 0xFF);
    frame.data[4] = static_cast<uint8_t>((current_wire >> 8) & 0xFF);
    frame.data[5] = static_cast<uint8_t>(current_wire & 0xFF);
    frame.data[6] = encodeTemperature(data.temperature_c);
    frame.data[7] = 0x00;   // Reserved

    return frame;
}
```

- SOC/SOH: `×0.5` 스케일, raw 0~200
- Voltage: uint16 BE, `×0.01` V
- Current: int16 BE, `×0.1` A (양수=충전, 음수=방전). 와이어에는 2의 보수 비트열을 그대로 싣는다
- Temperature: offset `+40`, raw 상한 165 (= 125°C)
- Byte 7: Reserved, `0x00` 고정

### 3.5 100ms 주기 송신

`main.cpp`의 실제 루프 구조다. 별도 `CanPublisher` 스레드 클래스는 없다.

```cpp
while (running) {
    const auto cycle_start = std::chrono::steady_clock::now();
    watchdog.kick();

    const auto sample = sensor.next();
    const float soc_percent =
        soc_estimator.update(0.1f, sample.current_a, sample.voltage_v) * 100.0f;
    const float soh_percent = soh_estimator.soh() * 100.0f;

    failsafe.evaluate(soc_percent, sample.temperature_c);

    const auto status_frame = encodeBmsStatusFrame({
        soc_percent, soh_percent,
        sample.voltage_v, sample.current_a, sample.temperature_c,
    });
    driver.send(status_frame);
    if (secoc_enabled) {
        driver.send(secoc.sign(0x102, 0x100, status_frame.data));
    }

    std::this_thread::sleep_until(cycle_start + std::chrono::milliseconds(100));
}
```

`sleep_until`을 쓰는 이유는 처리 시간이 변해도 주기 시작점이 밀리지 않기 때문이다. `sleep_for(100ms - elapsed)`로 바꾸면 TC-BMS-007의 각 유효 전송 간격 90~110ms 조건을 벗어날 수 있다. 표준편차는 보조 통계다.

**실행 인자** (`main.cpp` 파싱 기준):

| 인자 | 기본값 | 설명 |
|---|---|---|
| `--interface` | `vcan0` | CAN 인터페이스 |
| `--sensor-mode` | `constant` | `constant`/`profile_csv`/`random_walk`/`ads1115` (`potentiometer`는 삭제 대상) |
| `--profile` | `adaptive_ecu/data/battery_profile.csv` | PROFILE_CSV 입력 |
| `--secoc` | `off` | `on`이면 `0x102`/`0x103` 인증 프레임 동반 송신 |
| `--key` | `/etc/secoc/key.bin` | SecOC 키 경로 |

### 3.6 배터리 프로파일 데이터

데이터 준비와 정확도 인수의 정본은 [ECU M3](M3_EKF_Failsafe_SecOC.md) §3.12다. 여러 NASA cycle의 timestamp를 단순 연결하고 셀 전압 CSV를 가상 팩 입력으로 바로 쓰던 변환 예시는 제거한다.

TC-BMS-002용 파일을 만들기 전에 원본 cycle·시간축·샘플 간격·전류 부호·온도·셀/팩 변환·capacity·독립 기준 SOC를 확정한다. 공식 NASA 입력을 CALCE나 전압 램프로 자동 대체하지 않는다. 시간축 재시작·중복·보간·누락을 검증하고, raw 원본과 실제 SensorSimulator가 읽는 voltage,current,temperature 입력 및 평가용 메타데이터를 분리한다.

현재 battery_profile.csv는 parser/순서 시험용 기존 입력이다. 행수·헤더·EOF 동작을 실제 파일과 대조하며 공식 시험에 적힌 예시 행수와 다르면 fixture 조건으로 기록한다. 장기 정확도 평가가 완료됐다고 표시하지 않는다.

### 3.7 TC-BSW-001~003 자동화 (미구현 과제)

`test_can_cdd`는 현재 없다. 추가하려면 `vcan0` 의존성 때문에 CI에서 조건부 실행이 필요하다.

```cpp
// adaptive_ecu/test/test_can_cdd.cpp (신규)
#include <gtest/gtest.h>
#include "can_cdd.h"
#include "mock_can_driver.h"
#include <chrono>
#include <thread>

// TC-BSW-001: loopback 송수신 (vcan0 필요)
TEST(CanCdd, LoopbackSendReceive) {
    SocketCanCdd cdd;
    ASSERT_TRUE(cdd.open("vcan0"));
    CanFrame rx{};
    cdd.registerCallback([&rx](const CanFrame& f) { rx = f; });
    cdd.startReceive();

    CanFrame tx{0x100, 8, {0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08}};
    ASSERT_TRUE(cdd.send(tx));
    std::this_thread::sleep_for(std::chrono::milliseconds(100));

    EXPECT_EQ(rx.id, 0x100u);
    EXPECT_EQ(rx.dlc, 8);
    EXPECT_EQ(rx.data[0], 0x01);
    cdd.close();
}

// TC-BSW-002: Mock 교체 호환성 (하드웨어 불필요)
TEST(CanCdd, MockSubstitution) {
    MockCanDriver mock;
    CanDriver* driver = &mock;
    ASSERT_TRUE(driver->open("vcan0"));
    CanFrame f{0x100, 8, {}};
    ASSERT_TRUE(driver->send(f));
    EXPECT_EQ(mock.sent_frames.size(), 1u);
}

// TC-BSW-003: 콜백 10회 호출 (하드웨어 불필요)
TEST(CanCdd, CallbackCount) {
    MockCanDriver mock;
    int count = 0;
    mock.registerCallback([&count](const CanFrame&) { count++; });
    mock.startReceive();
    mock.open("vcan0");
    for (int i = 0; i < 10; i++) {
        mock.send(CanFrame{0x100, 8, {}});
    }
    EXPECT_EQ(count, 10);
}
```

추가 시 `CMakeLists.txt`의 `ECU_TESTS` 목록에 `test_can_cdd`를 넣는다. TC-BSW-001은 `vcan0`이 없으면 실패하므로, CI에서는 건너뛰거나 러너에 `vcan0`을 올린다.

### 3.8 TC-BSW-004~005 — Publisher 다중 구독자와 스레드 안전성

```cpp
TEST(Publisher, MultipleSubscribers) {
    Publisher<BmsStatusData> pub;
    int count = 0;
    pub.subscribe([&](const BmsStatusData&) { count++; });
    pub.subscribe([&](const BmsStatusData&) { count++; });
    pub.subscribe([&](const BmsStatusData&) { count++; });
    pub.send(BmsStatusData{75.0f, 95.0f, 42.0f, -2.0f, 25});
    EXPECT_EQ(count, 3);
}
```

TC-BSW-005는 sanitizer로 확인한다.

```bash
cmake -S adaptive_ecu -B adaptive_ecu/build-tsan -DECU_BUILD_TESTS=ON \
      -DCMAKE_CXX_FLAGS="-fsanitize=thread -g"
cmake --build adaptive_ecu/build-tsan
ctest --test-dir adaptive_ecu/build-tsan -R test_publisher --output-on-failure
# sanitizer 경고 0건이면 통과
```

---

## 4. 검증 명령과 합격 기준

```bash
cmake -S adaptive_ecu -B adaptive_ecu/build -DECU_BUILD_TESTS=ON
cmake --build adaptive_ecu/build

# M2 대상 시험 (실제 등록된 이름)
ctest --test-dir adaptive_ecu/build -R test_mock_can_driver --output-on-failure
ctest --test-dir adaptive_ecu/build -R test_publisher       --output-on-failure
ctest --test-dir adaptive_ecu/build -R test_sensor_simulator --output-on-failure
ctest --test-dir adaptive_ecu/build -R test_can_publisher   --output-on-failure

# 100ms 주기 실측
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan 2>/dev/null || true
sudo ip link set vcan0 up
./adaptive_ecu/build/adaptive_ecu --interface vcan0 &
candump -t a vcan0
# 수집 후 Ctrl+C. 위 명령은 원시 캡처이며 그 자체로 합격 판정하지 않는다.
# 공동 통합시험 §6에 따라 표준 데이터 프레임 0x100만 선별하고 연속 절대시각 차이를 계산한다.
# TC-BMS-007의 표본·관측 구간과 손실을 기록한다. 실제 물리 CAN 최종 인수는 별도다.
kill %1
```

| 기준 | 합격 조건 |
|---|---|
| TC-BSW-002~005 | `ctest` 통과 |
| TC-BSW-001 | `vcan0` loopback 수신 확인 (시험 자동화는 3.7 과제) |
| TC-BSW-008-a~c | CONSTANT / PROFILE_CSV / RANDOM_WALK 통과; -d는 M3 실취득 인수 |
| TC-BMS-007 | 모든 유효 0x100 연속 간격 90~110ms. 횟수·평균·표준편차는 보조 통계이며 관측 경계·손실·환경을 기록 |
| 인계 | IVI가 `0x100` mock payload를 같은 값으로 파싱 |
| 태그 | `v0.2.0` |

---

## 5. 실패 시 대응과 우회

**`open()` 실패 (`CAN open failed`)**
- 인터페이스가 UP인지: `ip link show <iface>`
- 물리 CAN 미동작 시 `--interface vcan0`으로 전환 ([M1](M1_환경구축_ICD확정.md) 5장)

**주기 허용 범위 이탈**
- `sleep_for` 방식으로 바뀌지 않았는지 확인. `sleep_until(cycle_start + 100ms)`가 기준이다
- 루프 내부에 blocking I/O(파일 로그, 동기 출력)가 들어가면 지터가 커진다. 로그는 주기 밖으로 뺀다
- 공동 통합시험 §6의 절대시각·표준 데이터 0x100 선별·손실 검사로 재확인한다. 전체 버스의 줄 간격이나 표준편차만으로 판정하지 않는다

**`.mat` 파일 로드 실패**
- MATLAB 버전 차이면 `pip install mat73` 후 `mat73.loadmat` 시도
- 대안: CALCE Battery Data의 CSV를 직접 사용

**IVI와 파싱 값 불일치**
- 반올림 규칙(`lround`)과 clamp 상한을 먼저 대조한다. 절삭 방식이면 1 LSB 차이가 난다
- 그래도 다르면 ICD §1.2를 함께 읽고 `interface-change` 게이트로 처리한다 ([00_협업_규약](../common/00_협업_규약.md))

---

## 6. 완료 체크리스트

- [ ] `MockCanDriver`가 `CanDriver`로 교체 가능하고 loopback 콜백이 동작한다
- [ ] `SocketCanCdd`가 `vcan0`/`can0`에서 송수신한다
- [ ] `Publisher<T>` 다중 구독자·스레드 안전성 통과 (TC-BSW-004~005)
- [ ] `SensorSimulator` 세 모드 통과(TC-BSW-008-a~c), ADS1115(-d)는 M3 담당·실행 상태로 인계
- [ ] `encodeBmsStatusFrame()`을 ICD §1.2 및 적용 시 §8과 대조하고 IVI 파싱 시험(TC-IVI-002)에 벡터를 인계한다. TC-BMS-005~006의 Fail-safe 전이 인수는 M3에서 별도로 수행
- [ ] `0x100`의 모든 유효 연속 간격 90~110ms, 표본·관측 경계·손실·실행 환경 기록(TC-BMS-007)
- [ ] 배터리 프로파일 CSV로 PROFILE_CSV 모드 재생 성공
- [ ] IVI가 같은 payload를 동일하게 파싱
- [ ] `v0.2.0` 태그 생성


### CAN 수신 작업 복구 요구의 별도 인수

[SRS](../../../docs/SRS.md)의 NFR-REL-002는 CAN 수신 스레드 이상 종료 시 자동 재시작과 최대 3회 재시도 후 실패 로그를 요구한다. BMS 계산 작업의 복구 시험으로 대체하지 않는다. 원천의 TC-BSW-007 연결과 그 TC 본문의 차이는 [공동 매핑](../common/01_연계_의존성.md) MAP-01에서 관리한다.

- [ ] 수신 작업의 소유자와 소켓·콜백 수명을 명세하고 정상 서비스 종료를 장애로 오인해 재시작하지 않도록 한다.
- [ ] 수신 작업 장애를 주입하여 회수→재시작→새 프레임 처리 재개를 확인한다. 스레드 생성만으로 성공 판정하지 않는다.
- [ ] 실제 재시도별 실패를 집계하고 최대 3회 이후 실패 로그를 확인한다. 작업 중복·콜백 중복·자원 누수가 없어야 한다.
- [ ] ECU의 Watchdog 감시 범위와 IVI 수신 스레드 수명 관리를 양측 설계에서 대조한다. BMS에 대해 승인한 snapshot 정책을 CAN 수신기에 자동 적용하지 않는다.
- [ ] 수신 재개만으로 세션/counter를 초기화하거나 센서 품질을 정상으로 바꾸지 않는다. 회수 불가·세션 영향의 구체 처리에 판단이 필요하면 인터뷰한다.

공식 TC의 연결/하위 시험은 계약·시험 검토 단계에서 확정한다. 현재는 누락 방지를 위한 수행 계획이며 구현·시험 통과가 아니다.


<a id="ecu-can-01"></a>
### ECU-CAN-01 — Plan 승계 과제

원문: [ECU.md](../../_archive/plan_20260908/ECU.md.txt)의 ECU-CAN-01. 실행 상태는 해당 역할의 진행 표·공동 인수 기록을 사용한다. 이 병합은 과제 실행 완료가 아니다.

선행·착수: [ECU-ENV-01](M1_환경구축_ICD확정.md#ecu-env-01), 승인 계약

보존한 수행·인수 조건: 드라이버/Mock 교체·비동기 수신/종료·다중 구독·동시 접근·인코딩을 시험한다. 기존 battery_profile.csv는 회귀 입력으로 보존하고 장기 입력의 출처·변환·단위·길이는 별도 기록한다. 센서 실취득은 ECU M3에서 인수한다. IVI-HAL-01에 송신 샘플/Mock 입력을 제공한다.

현재 기준 적용: 센서 입력 과제는 M2 경계 확인과 M3 실제 취득으로 분담. 본문의 공식 FR/TC·승인 정책·실패 대응을 함께 적용한다.
