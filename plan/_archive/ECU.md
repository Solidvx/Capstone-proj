# 팀원A 실행 가이드 — 전체 8개월 단계별 수행 절차

> **프로젝트**: AUTOSAR 계층 기반 IVI-ECU 통합 플랫폼  
> **역할**: Node A — RPi4 Ubuntu 22.04 / C++17 / AUTOSAR BSW·BMS·SecOC / Python IDS  
> **참조 문서**: `docs/SDD-ECU.md` · `docs/ICD.md` · `docs/TARA.md` · `docs/TEST_PLAN.md`  
> **목표**: 이 문서의 절차를 순서대로 따라하면 팀원A의 모든 작업을 완수할 수 있다.
>
> **관련 가이드**:
> - 공동 작업 (통합 테스트, 마일스톤 처리, 데모): `PLAN_공동.md`
> - 팀원B 작업과의 의존성 및 연계: `팀간_연계_분석.md`
> - 전체 가이드 네비게이션: `INDEX.md`

---

## 팀원A Issue 라벨 Quick Reference

> Issue 생성 시 아래 조합 사용. 라벨 정의·색상은 `PLAN_공동.md` "수행 절차 2: GitHub Labels 생성" 참조.

| 작업 유형 | 라벨 조합 (담당자 라벨 `ECU` 항상 포함) | 예시 |
|----------|---------------------------------|------|
| 새 기능 구현 | `feat` + `ECU` (+ `security` 해당 시) | `[ECU] EKF SOC 추정기 구현` |
| 보안 모듈 구현 | `feat` + `ECU` + `security` | `[ECU] SecOC HMAC C++ 이식` |
| 버그 수정 | `bug` + `ECU` (+ `interface-change` ICD 영향 시) | `[ECU] BMS 0x100 Reserved 필드 인코딩 오류 수정` |
| 테스트 작성 | `test` + `ECU` | `[ECU] TC-BMS-004 Fail-safe 전이 테스트 추가` |
| 환경/도구 설정 | `chore` + `ECU` | `[ECU] RPi4 Ubuntu 22.04 환경 구축` |
| 동작 변경 없는 정리 | `refactor` + `ECU` | `[ECU] Publisher<T> 템플릿 인터페이스 정리` |
| 문서 작업 | `docs` (+ `ECU` 도메인 한정 시) | `[ECU] SDD-ECU.md §3.4 BMS 모듈 작성` |
| ICD 인터페이스 변경 | `interface-change` + `docs` + `ECU` | `[ICD] 0x100 BMS_Status 레이아웃 변경` — `PLAN_공동.md` 5단계 워크플로 필수 |
| 진행 불가 (블로커) | 기존 라벨 + `blocked` | (블로커 발생 시 의존 Issue 번호 코멘트) |

---

## M1 (6월) — 환경 구축 + 설계

### 목표

RPi4에 Ubuntu 22.04를 설치하고, MCP2515 SPI CAN + vcan0 가상 인터페이스를 설정하고, 개발 도구(CMake, GCC, GoogleTest, can-utils)를 설치한다. 프로젝트 디렉토리 골격을 생성하고 핵심 인터페이스 헤더(`can_driver.h`, `publisher.h`, `subscriber.h`)를 설계한다. ICD.md 초안을 작성하고, SRS.md / ADR 초안을 완성한다.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | RPi4 Ubuntu 22.04 Server 설치 | 30분 | 부팅 + 로그인 성공 |
| 1 | SSH 접속 확인 | 10분 | `ssh user@IP` 성공 |
| 1 | MCP2515 SPI + SocketCAN 설정 | 30분 | `dmesg \| grep mcp251x` 성공 |
| 1 | CAN loopback 테스트 | 10분 | `cansend`→`candump` 수신 확인 |
| 1 | vcan0 가상 인터페이스 세팅 | 5분 | `cansend vcan0` 성공 |
| 1 | CAN 부팅 시 자동 실행 설정 | 10분 | 재부팅 후 can0/vcan0 자동 UP |
| 1 | CMake 3.25+ / GCC-12 / GoogleTest / can-utils 설치 | 20분 | 버전 확인 명령어 통과 |
| 1 | GoogleTest 동작 검증 (hello test) | 10분 | ctest PASSED |
| 2 | `adaptive_ecu/` 디렉토리 골격 + CMakeLists.txt | 1시간 | cmake + make 빌드 성공 |
| 2 | `can_driver.h` CanDriver 추상 클래스 헤더 설계 | 2시간 | SDD-ECU §3.2 일치 |
| 2 | `publisher.h` Publisher<T> 템플릿 헤더 초안 | 2시간 | 컴파일 성공 |
| 3 | `can_driver.h` 완성 + PR (팀원B 리뷰) | 1시간 | PR 오픈 완료 |
| 3 | `subscriber.h` 인터페이스 헤더 | 1시간 | 컴파일 성공 |
| 3 | **ICD.md 초안 작성** | 4시간 | CAN ID 5종 + HIDL API + SecOC 명시 |
| 4 | ICD.md 최종 확정 미팅 참여 | 30분 | 합의 완료 |
| 4 | SRS.md FR-BSW/BMS/SEC 부분 초안 | 2시간 | PR 머지 |
| 4 | ADR-001 (SocketCAN), ADR-002 (HMAC-SHA256) 초안 | 2시간 | PR 머지 |

### 수행 과정

#### 1. RPi4 Ubuntu 22.04 설치

**준비물**: RPi4(4GB+), microSD(32GB+), 리더기, 이더넷/Wi-Fi, MCP2515 모듈

1. Raspberry Pi Imager 설치 (https://www.raspberrypi.com/software/)
2. CHOOSE OS → Other general-purpose OS → Ubuntu → Ubuntu Server 22.04.x LTS (64-bit)
3. CHOOSE STORAGE → microSD 선택
4. 설정(톱니바퀴):
   - Set hostname: `node-a`
   - Enable SSH: 체크 (password)
   - Set username/password
   - Wi-Fi: SSID/비밀번호 (해당 시)
5. WRITE → 완료 대기 → microSD 삽입 → 전원 연결

```bash
# SSH 접속
ssh <username>@<RPi4-IP>
```

**검증:**
```bash
# 로그인 후 확인
uname -a
# 출력 예: Linux node-a 5.15.x-raspi #1 SMP ... aarch64 ... GNU/Linux
```

**트러블슈팅 — SSH 접속 실패:**
- RPi4 IP 확인: 공유기 관리 페이지에서 DHCP 할당 목록 확인
- `ping <RPi4-IP>` 실패 시: 이더넷 케이블 직접 연결 후 재시도
- 키 충돌 시: `ssh-keygen -R <RPi4-IP>` 실행 후 재접속

#### 2. MCP2515 배선 + SocketCAN

| MCP2515 핀 | RPi4 GPIO 핀 | 설명 |
|------------|-------------|------|
| VCC | Pin 2 (5V) | 전원 |
| GND | Pin 6 (GND) | 접지 |
| CS | Pin 24 (GPIO 8, CE0) | SPI Chip Select |
| SO | Pin 21 (GPIO 9, MISO) | SPI 출력 |
| SI | Pin 19 (GPIO 10, MOSI) | SPI 입력 |
| SCK | Pin 23 (GPIO 11, SCLK) | SPI 클럭 |
| INT | Pin 22 (GPIO 25) | 인터럽트 |

```bash
sudo nano /boot/firmware/config.txt
# 맨 끝에 추가:
# dtparam=spi=on
# dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25
# (16MHz 크리스탈이면 oscillator=16000000)

sudo reboot
```

재부팅 후:
```bash
dmesg | grep mcp251x
# 기대 출력: "MCP2515 successfully initialized"

sudo ip link set can0 up type can bitrate 500000
ip link show can0
# 기대 출력: ... state UP ... qlen 10
```

Loopback 테스트:
```bash
sudo ip link set can0 down
sudo ip link set can0 up type can bitrate 500000 loopback on
candump can0 &
cansend can0 100#DEADBEEF
# 기대 출력: can0  100   [4]  DE AD BE EF
kill %1
```

**MCP2515 인식 실패 시 — vcan0으로 우선 개발 진행:**
```bash
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set vcan0 up

# 검증
cansend vcan0 100#DEADBEEF
# 에러 없으면 성공
```

**트러블슈팅 — MCP2515 인식 실패:**
- `dmesg | grep spi` 로 SPI 인식 여부 확인
- 크리스탈 주파수 확인: 모듈에 적힌 수치 (8MHz vs 16MHz) 맞게 `oscillator=` 설정
- GPIO 25번 INT 핀 점퍼선 접촉 불량 확인 (가장 흔한 원인)
- 그래도 안 되면 vcan0으로 진행, 하드웨어는 병렬로 디버깅

#### 3. CAN 부팅 시 자동 실행

```bash
sudo nano /etc/systemd/network/80-can.network
```
```ini
[Match]
Name=can0

[CAN]
BitRate=500000
```

```bash
sudo nano /etc/systemd/network/80-vcan.netdev
```
```ini
[NetDev]
Name=vcan0
Kind=vcan
```

```bash
sudo nano /etc/systemd/network/80-vcan.network
```
```ini
[Match]
Name=vcan0
```

```bash
sudo systemctl enable systemd-networkd
sudo systemctl restart systemd-networkd
sudo reboot
```

**검증:**
```bash
ip link show can0
# 기대 출력: ... state UP ...

ip link show vcan0
# 기대 출력: ... state UP ...
```

#### 4. 빌드 도구 설치

```bash
sudo apt update && sudo apt upgrade -y

# CMake 3.25+ (Ubuntu 22.04 기본은 3.22)
sudo apt install -y wget
wget https://github.com/Kitware/CMake/releases/download/v3.28.1/cmake-3.28.1-linux-aarch64.sh
chmod +x cmake-3.28.1-linux-aarch64.sh
sudo ./cmake-3.28.1-linux-aarch64.sh --prefix=/usr/local --skip-license

# GCC-12
sudo apt install -y gcc-12 g++-12
sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-12 100
sudo update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-12 100

# GoogleTest
sudo apt install -y libgtest-dev
cd /usr/src/gtest && sudo cmake . && sudo make && sudo cp lib/*.a /usr/lib/
cd ~

# can-utils + 기타
sudo apt install -y can-utils git build-essential pkg-config libssl-dev
```

**검증:**
```bash
cmake --version
# 기대 출력: cmake version 3.28.1 (3.25 이상이면 OK)

gcc --version
# 기대 출력: gcc (Ubuntu 12...) 12.x.x

g++ --version
# 기대 출력: g++ (Ubuntu 12...) 12.x.x

cansend --help
# 기대 출력: Usage: cansend <device> <can_frame>
```

**트러블슈팅 — CMake 버전 낮음:**
- ARM64용 바이너리인지 확인: `file cmake-3.28.1-linux-aarch64.sh`
- x86 실수 시: `cmake-3.28.1-linux-x86_64.sh` 말고 `aarch64` 받을 것
- 대안: `pip install cmake` 로 설치

#### 5. GoogleTest 동작 검증

```bash
mkdir -p ~/gtest-verify && cd ~/gtest-verify
```

`hello_test.cpp`:
```cpp
#include <gtest/gtest.h>
TEST(SanityCheck, TrueIsTrue) { EXPECT_TRUE(true); }
int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
```

`CMakeLists.txt`:
```cmake
cmake_minimum_required(VERSION 3.25)
project(gtest_verify LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(GTest REQUIRED)
add_executable(hello_test hello_test.cpp)
target_link_libraries(hello_test GTest::GTest GTest::Main pthread)
enable_testing()
add_test(NAME hello_test COMMAND hello_test)
```

```bash
mkdir build && cd build && cmake .. && make && ctest --output-on-failure
# 기대 출력:
# [==========] Running 1 test from 1 test suite.
# [  PASSED  ] 1 test.
# Test project ...
# 100% tests passed, 0 tests failed

cd ~ && rm -rf ~/gtest-verify
```

**트러블슈팅 — GTest 링크 에러:**
- `libgtest.a` 위치 확인: `find /usr -name "libgtest.a" 2>/dev/null`
- 없으면 수동 빌드: `cd /usr/src/gtest && sudo cmake . && sudo make && sudo cp lib/*.a /usr/lib/`

#### 6. 프로젝트 디렉토리 골격 생성

```bash
cd ~/Capstone-proj  # 프로젝트 루트

mkdir -p adaptive_ecu/include
mkdir -p adaptive_ecu/src/bsw
mkdir -p adaptive_ecu/src/app
mkdir -p adaptive_ecu/test
mkdir -p security/attacks
mkdir -p security/ids
mkdir -p security/tests
mkdir -p data
```

최종 구조:
```
adaptive_ecu/
├── include/          # 헤더 파일
├── src/bsw/          # BSW 레이어 (CAN CDD, SecOC, Watchdog)
├── src/app/          # 애플리케이션 레이어 (BMS, EKF, Fail-safe)
├── test/             # GoogleTest 단위 테스트
├── CMakeLists.txt
└── main.cpp
security/
├── attacks/          # 공격 시뮬레이터 (Python)
├── ids/              # IDS 엔진 + 학습 (Python)
└── tests/            # pytest 테스트
data/                 # 배터리 프로파일 CSV 등
```

#### 7. CMakeLists.txt 초안

`adaptive_ecu/CMakeLists.txt`:
```cmake
cmake_minimum_required(VERSION 3.25)
project(adaptive_ecu LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_executable(adaptive_ecu main.cpp)
enable_testing()
find_package(GTest REQUIRED)
```

**검증:**
```bash
cd adaptive_ecu && mkdir -p build && cd build
cmake ..
# 기대 출력: -- Configuring done / -- Generating done

cd ~/Capstone-proj
```

#### 8. can_driver.h 인터페이스 스케치

`adaptive_ecu/include/can_driver.h`:
```cpp
#pragma once
#include <cstdint>
#include <string>
#include <functional>

struct CanFrame {
    uint32_t id;
    uint8_t  dlc;
    uint8_t  data[8];
};
using CanCallback = std::function<void(const CanFrame&)>;
class CanDriver {
public:
    virtual ~CanDriver() = default;
    virtual bool open(const std::string& interface) = 0;
    virtual void close() = 0;
    virtual bool send(const CanFrame& frame) = 0;
    virtual void registerCallback(CanCallback cb) = 0;
    virtual void startReceive() = 0;
    virtual void stopReceive() = 0;
};
```

**검증:** 해당 헤더를 include하는 빈 cpp 파일로 컴파일 성공 여부 확인
```bash
echo '#include "can_driver.h"' > /tmp/test_include.cpp
g++ -std=c++17 -I adaptive_ecu/include -c /tmp/test_include.cpp -o /dev/null
# 에러 없으면 성공
```

#### 9. ICD.md 초안 작성 (3주차)

작성할 내용:
1. CAN 메시지 ID 할당: 0x100 (BMS_Status), 0x101 (BMS_FailSafe), 0x102 (BMS_SecOC), 0x103 (FailSafe_SecOC), 0x200 (IDS_Alert)
2. 각 CAN ID별 바이트 레이아웃 (ICD.md §1.2~1.5 참조)
3. SecOC 프로토콜: HMAC-SHA256, 절단 MAC 4B, 롤링 카운터 윈도우 100
4. HIDL API: `IVehicleHal`, `IVehicleHalCallback`, `VehicleData` 구조체

**검증:** 팀원B에게 PR 리뷰 요청 → 합의 후 머지

#### 10. SRS.md + ADR 초안 (4주차)

- SRS.md: FR-BSW-001~007, FR-BMS-001~008, FR-SEC-001~007 요구사항 정의
- ADR-001: SocketCAN 선택 근거 (vs PEAK PCAN, vs CANopen)
- ADR-002: HMAC-SHA256 선택 근거 (vs AES-CMAC, vs RSA)

---

## M2 (7월) — CAN CDD 구현 + Mock 레이어

### 목표

CAN CDD (`can_cdd.cpp`)를 SocketCAN raw socket으로 구현하고, 하드웨어 없이 개발 가능한 Mock 레이어를 만든다. `Publisher<T>` ara::com 패턴을 구현하고, NASA Battery Dataset을 확보하여 CAN replay 준비를 완료한다. 0x100 BMS_Status를 100ms 주기로 송신하는 `can_publisher.cpp`를 구현한다.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | `can_driver.h` 최종 완성 | 1시간 | 컴파일 성공 |
| 1 | `mock_can_driver.cpp` Mock 구현 | 2시간 | 단위 테스트 통과 |
| 1 | `sensor_simulator.cpp` CONSTANT 모드 | 2시간 | 고정값 출력 확인 |
| 2 | `can_cdd.cpp` SocketCAN 구현 | 4시간 | socket→bind→rxLoop 동작 |
| 2 | 실물 CAN 송수신 확인 | 1시간 | `cansend`→`candump` 수신 |
| 2 | TC-BSW-001~003 통과 | 3시간 | GoogleTest PASSED |
| 3 | `publisher.h` Publisher<T> 완성 | 3시간 | 다중 구독자 테스트 |
| 3 | `bms_component.cpp` 초안 | 3시간 | BMS 통합 로직 |
| 3 | TC-BSW-004~005 통과 | 2시간 | 멀티스레드 안전성 |
| 3 | NASA Battery Dataset 다운로드 + CSV 파싱 | 3시간 | 데이터 로드 성공 |
| 4 | `can_publisher.cpp` 0x100 100ms 주기 송신 | 3시간 | TC-BMS-007 통과 (표준편차 ≤10ms) |
| 4 | NASA/CALCE 데이터 전처리 완료 | 2시간 | CAN replay 준비 |

### 수행 과정

#### 1. mock_can_driver.cpp 구현 (1주차)

`adaptive_ecu/src/bsw/mock_can_driver.cpp`:
```cpp
#include "can_driver.h"
#include <vector>
#include <mutex>

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
        // loopback: 즉시 콜백 호출
        if (callback_) callback_(frame);
        return true;
    }

    void registerCallback(CanCallback cb) override { callback_ = cb; }
    void startReceive() override { receiving_ = true; }
    void stopReceive() override { receiving_ = false; }

    // 테스트 헬퍼
    std::vector<CanFrame> sent_frames;
private:
    std::string interface_;
    bool opened_ = false;
    bool receiving_ = false;
    CanCallback callback_;
    std::mutex mtx_;
};
```

**검증:**
```bash
cd adaptive_ecu/build && cmake .. && make
# 컴파일 에러 없으면 성공
```

#### 2. sensor_simulator.cpp CONSTANT 모드 (1주차)

```cpp
struct SensorData {
    float voltage;
    float current;
    int8_t temperature;
};

class SensorSimulator {
public:
    enum Mode { CONSTANT, PROFILE_CSV, RANDOM_WALK, ADS1115_HARDWARE };

    explicit SensorSimulator(Mode mode) : mode_(mode) {}

    SensorData next() {
        if (mode_ == CONSTANT) {
            return {42.0f, -2.0f, 25};  // 고정값
        }
        // ... 다른 모드는 이후 구현
        return {};
    }
private:
    Mode mode_;
};
```

**검증:**
```cpp
// test/test_sensor_simulator.cpp
TEST(SensorSimulator, ConstantMode) {
    SensorSimulator sim(SensorSimulator::CONSTANT);
    auto d = sim.next();
    EXPECT_FLOAT_EQ(d.voltage, 42.0f);
    EXPECT_FLOAT_EQ(d.current, -2.0f);
    EXPECT_EQ(d.temperature, 25);
}
```
```bash
cd adaptive_ecu/build && cmake .. && make && ctest --output-on-failure
# [  PASSED  ] 1 test.
```

#### 3. can_cdd.cpp SocketCAN 구현 (2주차)

`adaptive_ecu/src/bsw/can_cdd.cpp` 핵심 흐름:

```cpp
#include <sys/socket.h>
#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <cstring>
#include <thread>
#include <atomic>

class SocketCanCdd : public CanDriver {
public:
    bool open(const std::string& interface) override {
        sock_ = socket(PF_CAN, SOCK_RAW, CAN_RAW);
        if (sock_ < 0) return false;

        struct ifreq ifr;
        std::strncpy(ifr.ifr_name, interface.c_str(), IFNAMSIZ - 1);
        if (ioctl(sock_, SIOCGIFINDEX, &ifr) < 0) return false;

        struct sockaddr_can addr{};
        addr.can_family = AF_CAN;
        addr.can_ifindex = ifr.ifr_ifindex;
        return bind(sock_, (struct sockaddr*)&addr, sizeof(addr)) == 0;
    }

    void close() override {
        stopReceive();
        if (sock_ >= 0) ::close(sock_);
        sock_ = -1;
    }

    bool send(const CanFrame& frame) override {
        struct can_frame cf{};
        cf.can_id = frame.id;
        cf.can_dlc = frame.dlc;
        std::memcpy(cf.data, frame.data, 8);
        return write(sock_, &cf, sizeof(cf)) == sizeof(cf);
    }

    void registerCallback(CanCallback cb) override { callback_ = cb; }

    void startReceive() override {
        running_ = true;
        rx_thread_ = std::thread([this] {
            struct can_frame cf;
            while (running_) {
                auto n = read(sock_, &cf, sizeof(cf));
                if (n == sizeof(cf) && callback_) {
                    CanFrame f{cf.can_id, cf.can_dlc, {}};
                    std::memcpy(f.data, cf.data, 8);
                    callback_(f);
                }
            }
        });
    }

    void stopReceive() override {
        running_ = false;
        if (rx_thread_.joinable()) rx_thread_.join();
    }

private:
    int sock_ = -1;
    std::atomic<bool> running_{false};
    std::thread rx_thread_;
    CanCallback callback_;
};
```

**검증 — 실물 CAN 송수신:**
```bash
# 터미널 1: 프로그램 실행 (수신 대기)
./adaptive_ecu

# 터미널 2: 외부에서 전송
cansend can0 100#DEADBEEF
# 프로그램에서 수신 로그 확인
# 기대 출력: [RX] CAN ID=0x100, DLC=4, data=DE AD BE EF
```

**검증 — vcan0 대체 테스트:**
```bash
# vcan0 인터페이스 사용 시
candump vcan0 &
cansend vcan0 100#0102030405060708
# 기대 출력: vcan0  100   [8]  01 02 03 04 05 06 07 08
kill %1
```

#### 4. TC-BSW-001~003 단위 테스트 (2주차)

`adaptive_ecu/test/test_can_cdd.cpp`:
```cpp
#include <gtest/gtest.h>
#include "can_driver.h"

// TC-BSW-001: loopback 송수신
TEST(CanCdd, LoopbackSendReceive) {
    SocketCanCdd cdd;
    ASSERT_TRUE(cdd.open("vcan0"));
    CanFrame rx{};
    cdd.registerCallback([&rx](const CanFrame& f) { rx = f; });
    cdd.startReceive();

    CanFrame tx{0x100, 8, {0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08}};
    ASSERT_TRUE(cdd.send(tx));
    std::this_thread::sleep_for(std::chrono::milliseconds(100));

    ASSERT_EQ(rx.id, 0x100);
    ASSERT_EQ(rx.dlc, 8);
    ASSERT_EQ(rx.data[0], 0x01);
    cdd.close();
}

// TC-BSW-002: Mock 교체 호환성
TEST(CanCdd, MockSubstitution) {
    MockCanDriver mock;
    CanDriver* driver = &mock;
    ASSERT_TRUE(driver->open("vcan0"));
    CanFrame f{0x100, 8, {}};
    ASSERT_TRUE(driver->send(f));
    ASSERT_EQ(mock.sent_frames.size(), 1u);
}

// TC-BSW-003: 콜백 10회 호출
TEST(CanCdd, CallbackCount) {
    MockCanDriver mock;
    int count = 0;
    mock.registerCallback([&count](const CanFrame&) { count++; });
    mock.startReceive();
    for (int i = 0; i < 10; i++) {
        mock.send(CanFrame{0x100, 8, {}});
    }
    ASSERT_EQ(count, 10);
}
```

**실행:**
```bash
cd adaptive_ecu/build && cmake .. && make && ctest --output-on-failure
# 기대 출력:
# Test project /home/.../adaptive_ecu/build
#     Start 1: test_can_cdd
# 1/1 Test #1: test_can_cdd ...   Passed    0.x sec
# 100% tests passed, 0 tests failed
```

#### 5. Publisher<T> + TC-BSW-004~005 (3주차)

`adaptive_ecu/include/publisher.h`:
```cpp
#pragma once
#include <vector>
#include <functional>
#include <mutex>

template <typename T>
class Publisher {
public:
    using Callback = std::function<void(const T&)>;

    void subscribe(Callback cb) {
        std::lock_guard<std::mutex> lock(mtx_);
        subscribers_.push_back(std::move(cb));
    }

    void send(const T& data) {
        std::lock_guard<std::mutex> lock(mtx_);
        for (auto& cb : subscribers_) {
            cb(data);
        }
    }

private:
    std::vector<Callback> subscribers_;
    std::mutex mtx_;
};
```

**검증 — TC-BSW-004 (다중 구독자):**
```cpp
TEST(Publisher, MultipleSubscribers) {
    Publisher<BmsStatusData> pub;
    int count = 0;
    pub.subscribe([&](const BmsStatusData&) { count++; });
    pub.subscribe([&](const BmsStatusData&) { count++; });
    pub.subscribe([&](const BmsStatusData&) { count++; });
    pub.send(BmsStatusData{75.0f, 95.0f, 42.0f, -2.0f, 25});
    ASSERT_EQ(count, 3);
}
```

**검증 — TC-BSW-005 (멀티스레드 안전성):**
```bash
# 빌드 시 sanitizer 추가
cmake .. -DCMAKE_CXX_FLAGS="-fsanitize=thread"
make && ctest --output-on-failure
# sanitizer 에러 없으면 통과
```

#### 6. NASA Battery Dataset (3주차)

1. NASA PCoE 데이터셋 다운로드:
   - https://www.nasa.gov/content/prognostics-center-of-excellence-data-set-repository
   - Battery Data Set (B0005~B0018) 다운로드

2. MATLAB `.mat` → CSV 변환 (Python):

```python
# convert_nasa.py
from scipy.io import loadmat
import pandas as pd
import numpy as np

mat = loadmat('B0005.mat', squeeze_me=True, struct_as_record=False)
battery = mat['B0005']

rows = []
for cycle in battery.cycle:
    if cycle.type == 'discharge':
        data = cycle.data
        for i in range(len(data.Voltage_measured)):
            rows.append({
                'timestamp': data.Time[i],
                'voltage': data.Voltage_measured[i],
                'current': data.Current_measured[i],
                'temperature': data.Temperature_measured[i],
                'capacity': getattr(data, 'Capacity', [np.nan])[0] if hasattr(data, 'Capacity') else np.nan
            })

df = pd.DataFrame(rows)
df.to_csv('data/battery_profile_1h.csv', index=False)
print(f"생성 완료: {len(df)} 행")
```

```bash
pip install scipy pandas numpy
python convert_nasa.py
# 기대 출력: 생성 완료: XXXX 행

head -5 data/battery_profile_1h.csv
# 기대 출력:
# timestamp,voltage,current,temperature,capacity
# 0.0,4.18,-2.0,24.3,1.856
# ...
```

**트러블슈팅 — .mat 파일 로드 실패:**
- `scipy.io.loadmat` 에러 시 MATLAB 버전 차이 → `mat73` 패키지 시도: `pip install mat73`
- 대안: CALCE Battery Dataset (https://calce.umd.edu/battery-data) CSV 직접 다운로드

#### 7. can_publisher.cpp 주기 송신 (4주차)

`adaptive_ecu/src/bsw/can_publisher.cpp`:
```cpp
#include "can_driver.h"
#include <thread>
#include <chrono>
#include <atomic>

class CanPublisher {
public:
    CanPublisher(CanDriver* driver, BmsComponent* bms)
        : driver_(driver), bms_(bms) {}

    void start() {
        running_ = true;
        thread_ = std::thread([this] { publishLoop(); });
    }

    void stop() {
        running_ = false;
        if (thread_.joinable()) thread_.join();
    }

private:
    void publishLoop() {
        while (running_) {
            auto start = std::chrono::steady_clock::now();

            CanFrame frame{};
            frame.id = 0x100;
            frame.dlc = 8;
            // ICD §1.2: SOC(×0.5), SOH(×0.5), Voltage(BE ×0.01), Current(BE ×0.1), Temp(offset+40)
            frame.data[0] = static_cast<uint8_t>(bms_->getSoc() / 0.5f);
            frame.data[1] = static_cast<uint8_t>(bms_->getSoh() / 0.5f);
            uint16_t v = static_cast<uint16_t>(bms_->getVoltage() / 0.01f);
            frame.data[2] = (v >> 8) & 0xFF;
            frame.data[3] = v & 0xFF;
            int16_t c = static_cast<int16_t>(bms_->getCurrent() / 0.1f);
            frame.data[4] = (c >> 8) & 0xFF;
            frame.data[5] = c & 0xFF;
            frame.data[6] = static_cast<uint8_t>(bms_->getTemperature() + 40);
            frame.data[7] = 0x00; // Reserved

            driver_->send(frame);

            auto elapsed = std::chrono::steady_clock::now() - start;
            auto sleep_time = std::chrono::milliseconds(100) - elapsed;
            if (sleep_time > std::chrono::milliseconds(0)) {
                std::this_thread::sleep_for(sleep_time);
            }
        }
    }

    CanDriver* driver_;
    BmsComponent* bms_;
    std::atomic<bool> running_{false};
    std::thread thread_;
};
```

**검증 — TC-BMS-007 (주기 정확도):**
```bash
# 프로그램 실행 후 candump 으로 타이밍 측정
candump -t d vcan0 | head -20
# 기대 출력: 각 줄 간격이 약 (0.100000) 초
# 표준편차 ≤10ms 확인

# 프로그램 내부 TC-BMS-007 실행
cd adaptive_ecu/build && ctest -R test_bms_component --output-on-failure
# 기대 출력: [  PASSED  ]
```

---

## M3 (8월) — 핵심 로직 (EKF + Fail-safe + SecOC)

### 목표

EKF SOC 추정기를 구현하여 오차 ≤3% (TC-BMS-001: ≤0.5%)를 달성한다. Fail-safe FSM 4상태 전이를 구현하고 Branch Coverage 100%를 확보한다. SecOC HMAC-SHA256을 Python으로 프로토타입한 뒤 C++로 이식한다. ADS1115 I2C 하드웨어 센서를 연결한다.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | `ekf_soc_estimator.h/.cpp` EKF 기초 구현 | 6시간 | 컴파일 + 기초 테스트 |
| 1 | `test_ekf_soc.cpp` TC-BMS-001 | 2시간 | PASSED |
| 2 | NASA 데이터 CAN replay + EKF 정확도 검증 | 4시간 | SOC 오차 ≤3% |
| 2 | TC-BMS-001 (≤0.5%), TC-BMS-002 (RMSE 비교) | 3시간 | PASSED |
| 2 | `soh_estimator.cpp` + TC-BMS-003 | 2시간 | SOH=90% 정확도 |
| 2 | ADS1115 I2C 연결 + ADS1115_HARDWARE 모드 | 2시간 | `i2cdetect` 0x48 확인 |
| 3 | `failsafe_sm.h/.cpp` 4상태 FSM | 4시간 | 전이 로직 동작 |
| 3 | TC-BMS-004 (a~g) 전체 케이스 | 3시간 | Branch Coverage 100% |
| 3 | `watchdog_manager.cpp` | 2시간 | 1초 감시, 3초 타임아웃 |
| 4 | `secoc_module.py` Python HMAC 프로토타입 | 3시간 | TC-SEC-001 Python 통과 |
| 4 | `secoc_module.h/.cpp` C++ 이식 | 4시간 | TC-SEC-001~004 C++ 통과 |

### 수행 과정

#### 1. EKF SOC 추정기 (1~2주차)

**파라미터 (SDD-ECU §3.5):**
- Q_noise = 1e-5 (프로세스 노이즈)
- R_noise = 1e-2 (관측 노이즈)
- P_init = 1.0 (초기 오차 공분산)
- SOC_init = 0.5 (초기 SOC 추정값)
- OCV-SOC 다항식: a3=-1.031, a2=3.685, a1=-0.858, a0=2.374

`adaptive_ecu/include/ekf_soc_estimator.h`:
```cpp
#pragma once

struct EkfParams {
    double Q_noise = 1e-5;
    double R_noise = 1e-2;
    double P_init  = 1.0;
    double SOC_init = 0.5;
    double capacity = 50.0;  // Ah
    // OCV-SOC polynomial: OCV = a3*SOC^3 + a2*SOC^2 + a1*SOC + a0
    double a3 = -1.031;
    double a2 =  3.685;
    double a1 = -0.858;
    double a0 =  2.374;
};

class EkfSocEstimator {
public:
    explicit EkfSocEstimator(const EkfParams& params);
    void update(double voltage, double current, double dt);
    double getSoc() const;
    double getP() const;
private:
    double soc_;
    double P_;
    double Q_;
    double R_;
    double capacity_;
    double a3_, a2_, a1_, a0_;

    double computeOcv(double soc) const;
    double computeJacobian(double soc) const;
};
```

`adaptive_ecu/src/app/ekf_soc_estimator.cpp`:
```cpp
#include "ekf_soc_estimator.h"
#include <cmath>

EkfSocEstimator::EkfSocEstimator(const EkfParams& p)
    : soc_(p.SOC_init), P_(p.P_init), Q_(p.Q_noise), R_(p.R_noise),
      capacity_(p.capacity), a3_(p.a3), a2_(p.a2), a1_(p.a1), a0_(p.a0) {}

double EkfSocEstimator::computeOcv(double soc) const {
    return a3_*std::pow(soc,3) + a2_*std::pow(soc,2) + a1_*soc + a0_;
}

double EkfSocEstimator::computeJacobian(double soc) const {
    return 3*a3_*std::pow(soc,2) + 2*a2_*soc + a1_;
}

void EkfSocEstimator::update(double voltage, double current, double dt) {
    // 예측 단계 (Predict)
    double soc_pred = soc_ - (dt * current) / (capacity_ * 3600.0);
    double P_pred = P_ + Q_;

    // OCV 계산
    double ocv = computeOcv(soc_pred);
    double H = computeJacobian(soc_pred);

    // 업데이트 단계 (Update)
    double S = H * P_pred * H + R_;
    double K = P_pred * H / S;
    soc_ = soc_pred + K * (voltage - ocv);
    P_ = (1.0 - K * H) * P_pred;

    // SOC 클램핑
    if (soc_ < 0.0) soc_ = 0.0;
    if (soc_ > 1.0) soc_ = 1.0;
}

double EkfSocEstimator::getSoc() const { return soc_; }
double EkfSocEstimator::getP() const { return P_; }
```

**TC-BMS-001 검증: 고정 방전(1C) → SOC 오차 ≤0.5%**

```cpp
// test/test_ekf_soc.cpp
TEST(EkfSoc, TC_BMS_001_ConstantDischarge) {
    EkfParams params;
    params.SOC_init = 0.8;   // 80%
    params.capacity = 50.0;  // 50Ah
    EkfSocEstimator ekf(params);

    double current = -2.0;   // 2A 방전
    double dt = 0.1;         // 100ms
    for (int i = 0; i < 100; i++) {
        double true_soc = 0.8 - (2.0 * (i+1) * 0.1) / (50.0 * 3600.0);
        double voltage = ekf.computeOcv(true_soc); // 이상적 전압
        ekf.update(voltage, current, dt);
    }
    double expected = 0.8 - (2.0 * 100 * 0.1) / (50.0 * 3600.0);
    EXPECT_NEAR(ekf.getSoc(), expected, 0.005); // 오차 ≤0.5%
}
```

```bash
cd adaptive_ecu/build && cmake .. && make && ctest -R test_ekf_soc --output-on-failure
# 기대 출력: [  PASSED  ] 1 test.
```

**TC-BMS-002 검증: EKF vs 쿨롱 카운팅 RMSE 비교**

```cpp
TEST(EkfSoc, TC_BMS_002_EkfBetterThanCoulomb) {
    // PROFILE_CSV 모드로 battery_profile_1h.csv 로드
    // 36,000 타임스텝 시뮬레이션
    // RMSE_EKF < RMSE_CoulombCounting 확인
    auto [rmse_ekf, rmse_coulomb] = runComparison("data/battery_profile_1h.csv");
    EXPECT_LT(rmse_ekf, rmse_coulomb);
}
```

**EKF 파라미터 튜닝 워크플로우 (SOC 오차 > 3% 미달 시):**

1. **진단 — 어디서 발산하는지 확인:**
```bash
# 로그 출력 추가 후 실행
./adaptive_ecu --log-ekf 2>&1 | tee ekf_trace.csv
# CSV 형식: timestep,true_soc,ekf_soc,P,K,innovation
```

2. **R (관측 노이즈) 조정:**
   - EKF SOC가 전압 변화에 과민반응 → R 증가 (1e-2 → 5e-2)
   - EKF SOC가 너무 느리게 수렴 → R 감소 (1e-2 → 5e-3)

3. **Q (프로세스 노이즈) 조정:**
   - EKF SOC가 전류 적분 오차 누적 → Q 증가 (1e-5 → 1e-4)
   - 추정값이 너무 불안정 → Q 감소 (1e-5 → 1e-6)

4. **OCV-SOC 다항식 재피팅:**
```python
# fit_ocv.py — NASA 데이터에서 OCV-SOC 관계 재피팅
import numpy as np

# SOC ↔ OCV 실측 데이터 로드
soc_data = np.array([0.0, 0.1, 0.2, ..., 1.0])
ocv_data = np.array([3.0, 3.3, 3.5, ..., 4.2])

coeffs = np.polyfit(soc_data, ocv_data, 3)
print(f"a3={coeffs[0]:.3f}, a2={coeffs[1]:.3f}, a1={coeffs[2]:.3f}, a0={coeffs[3]:.3f}")
# 출력된 계수를 EkfParams에 반영
```

5. **재검증:**
```bash
cd adaptive_ecu/build && cmake .. && make && ctest -R test_ekf_soc --output-on-failure
# SOC 오차 ≤3% 달성 확인
```

#### 2. ADS1115 I2C 연결 (2주차)

```bash
# I2C 활성화
sudo nano /boot/firmware/config.txt
# dtparam=i2c_arm=on 추가
sudo reboot

# I2C 도구 설치 + 확인
sudo apt install -y i2c-tools
i2cdetect -y 1
# 기대 출력:
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 40: -- -- -- -- -- -- -- -- 48 -- -- -- -- -- -- --
# 0x48에 "48" 표시되면 ADS1115 인식 성공
```

**0x48 미검출 시:**
- CONSTANT/PROFILE_CSV 모드로 우선 개발 계속
- 배선 확인: SDA → Pin 3 (GPIO 2), SCL → Pin 5 (GPIO 3), VDD → 3.3V, GND → GND
- ADDR 핀이 GND에 연결되어 있는지 확인 (기본 주소 0x48)
- `sudo apt install -y python3-smbus` 후 Python으로 직접 테스트

#### 3. Fail-safe 상태 머신 (3주차)

4개 상태: NORMAL(0) → WARNING(1) → CRITICAL(2) → SHUTDOWN(3)

`adaptive_ecu/include/failsafe_sm.h`:
```cpp
#pragma once
#include <cstdint>

enum class FailSafeState : uint8_t {
    NORMAL = 0, WARNING = 1, CRITICAL = 2, SHUTDOWN = 3
};

struct FailSafeEvent {
    FailSafeState prev;
    FailSafeState next;
    uint8_t reason;
};

class FailSafeStateMachine {
public:
    FailSafeState evaluate(float soc, int8_t temp);
    void manualReset();
    FailSafeState getState() const { return state_; }
    FailSafeEvent getLastEvent() const { return last_event_; }
private:
    FailSafeState state_ = FailSafeState::NORMAL;
    FailSafeEvent last_event_{};

    void transition(FailSafeState next, uint8_t reason);
};
```

전이 조건 (ICD §1.3):
- SOC<20% || Temp>55C → WARNING (Reason 0x01/0x03)
- SOC<5% → CRITICAL (Reason 0x02)
- Temp>60C → SHUTDOWN (Reason 0x04)
- SOC>=20% && Temp<=55C → NORMAL 복귀 (Reason 0x05)
- 수동 리셋 → NORMAL (Reason 0x06)

**TC-BMS-004 테스트 케이스:**

| 케이스 | 입력 | 기대 전이 | 기대 사유 코드 |
|--------|------|-----------|----------------|
| (a) 정상→경고 | SOC=19%, Temp=30C | NORMAL → WARNING | 0x01 |
| (b) 경고→위험 | SOC=4%, Temp=30C | WARNING → CRITICAL | 0x02 |
| (c) 위험→셧다운 | SOC=10%, Temp=61C | CRITICAL → SHUTDOWN | 0x04 |
| (d) 경고→정상 | SOC=25%, Temp=50C | WARNING → NORMAL | 0x05 |
| (e) 정상 유지 | SOC=80%, Temp=30C | 전이 없음 (NORMAL) | -- |
| (f) 온도 경고 | SOC=50%, Temp=56C | NORMAL → WARNING | 0x03 |
| (g) 수동 리셋 | CRITICAL 상태에서 리셋 | CRITICAL → NORMAL | 0x06 |

**Branch Coverage 100% 확인:**
```bash
# Coverage 플래그로 빌드
cmake .. -DCMAKE_CXX_FLAGS="--coverage -fprofile-arcs -ftest-coverage"
make && ctest --output-on-failure

# lcov 수집
lcov --capture --directory . --output-file coverage.info
lcov --remove coverage.info '/usr/*' --output-file coverage.info
genhtml coverage.info --output-directory cov_report

# 브라우저에서 확인
# cov_report/index.html 열기
# failsafe_sm.cpp 파일의 Branch Coverage = 100% 확인
```

**검증 명령:**
```bash
cd adaptive_ecu/build && ctest -R test_failsafe_sm --output-on-failure
# 기대 출력: [  PASSED  ] 7 tests.
```

**트러블슈팅 — Branch Coverage < 100%:**
- `genhtml` 출력에서 미커버 branch 라인 확인
- 누락된 전이 경로 테스트 케이스 추가
- `if-else` 대신 `switch-case` 사용 시 `default:` 케이스도 테스트

#### 4. Watchdog Manager (3주차)

`adaptive_ecu/src/bsw/watchdog_manager.cpp`:
```cpp
// 핵심 사양:
// - 감시 주기: 1초
// - 타임아웃: 3초 (heartbeat 미수신 시)
// - 최대 재시작 횟수: 3회
// - 3회 초과 시: Fail-safe WARNING 전이
```

**검증:**
```bash
cd adaptive_ecu/build && ctest -R test_watchdog --output-on-failure
# TC-BSW-006: 4초 블로킹 → 타임아웃 감지 → PASSED
# TC-BSW-007: 3회 재시작 실패 → WARNING 전이 → PASSED
```

#### 5. SecOC HMAC (4주차)

**Step 1: Python 프로토타입**

`security/secoc_module.py`:
```python
import hmac
import hashlib

def compute_mac(key: bytes, can_id: int, counter: int, payload: bytes) -> bytes:
    """HMAC-SHA256 절단 MAC 4바이트 생성"""
    msg = can_id.to_bytes(2, 'big') + counter.to_bytes(4, 'big') + payload
    full_mac = hmac.new(key, msg, hashlib.sha256).digest()
    return full_mac[:4]  # 절단 MAC 4바이트

def verify_mac(key: bytes, can_id: int, counter: int, payload: bytes,
               received_mac: bytes) -> bool:
    """타이밍 공격 방지 비교"""
    expected = compute_mac(key, can_id, counter, payload)
    return hmac.compare_digest(expected, received_mac)
```

**TC-SEC-001 Python 검증:**
```python
# security/tests/test_secoc.py
import pytest
from secoc_module import compute_mac, verify_mac

TEST_KEY = b'\x01' * 32  # 32바이트 테스트 키

def test_mac_generation():
    mac = compute_mac(TEST_KEY, 0x0100, 1, b'\x01\x02\x03\x04\x05\x06\x07\x08')
    assert len(mac) == 4
    # 동일 입력 → 동일 출력 (결정론적)
    mac2 = compute_mac(TEST_KEY, 0x0100, 1, b'\x01\x02\x03\x04\x05\x06\x07\x08')
    assert mac == mac2

def test_mac_verification():
    payload = b'\x01\x02\x03\x04\x05\x06\x07\x08'
    mac = compute_mac(TEST_KEY, 0x0100, 1, payload)
    assert verify_mac(TEST_KEY, 0x0100, 1, payload, mac) is True

def test_tampered_mac_rejected():
    payload = b'\x01\x02\x03\x04\x05\x06\x07\x08'
    mac = compute_mac(TEST_KEY, 0x0100, 1, payload)
    tampered = bytes([mac[0] ^ 0xFF]) + mac[1:]  # 1비트 변조
    assert verify_mac(TEST_KEY, 0x0100, 1, payload, tampered) is False
```

```bash
cd security && python -m pytest tests/test_secoc.py -v
# 기대 출력:
# test_secoc.py::test_mac_generation PASSED
# test_secoc.py::test_mac_verification PASSED
# test_secoc.py::test_tampered_mac_rejected PASSED
```

**Step 2: C++ 이식**

`adaptive_ecu/src/bsw/secoc_module.cpp`:
```cpp
#include <openssl/hmac.h>
#include <openssl/crypto.h>
#include <array>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <vector>

class SecOcModule {
public:
    bool loadKey(const std::string& path) {
        std::ifstream f(path, std::ios::binary);
        key_.resize(32);
        f.read(reinterpret_cast<char*>(key_.data()), 32);
        return f.good();
    }

    std::array<uint8_t, 4> computeMac(
        uint16_t canId, uint32_t counter,
        const uint8_t* payload, size_t len) const
    {
        // CAN_ID(2B) || Counter(4B) || Payload(8B) 조립
        uint8_t msg[14];
        msg[0] = (canId >> 8) & 0xFF;
        msg[1] = canId & 0xFF;
        msg[2] = (counter >> 24) & 0xFF;
        msg[3] = (counter >> 16) & 0xFF;
        msg[4] = (counter >> 8) & 0xFF;
        msg[5] = counter & 0xFF;
        std::memcpy(msg + 6, payload, std::min(len, size_t(8)));

        unsigned int hmac_len;
        uint8_t full_mac[32];
        HMAC(EVP_sha256(), key_.data(), key_.size(),
             msg, sizeof(msg), full_mac, &hmac_len);

        std::array<uint8_t, 4> truncated;
        std::copy_n(full_mac, 4, truncated.begin());
        return truncated;
    }

    bool verifyMac(uint16_t canId, uint32_t counter,
                   const uint8_t* payload, size_t len,
                   const uint8_t* receivedMac) const
    {
        auto expected = computeMac(canId, counter, payload, len);
        return CRYPTO_memcmp(expected.data(), receivedMac, 4) == 0;
    }

    bool checkCounter(uint32_t received) {
        if (received <= last_counter_ || received > last_counter_ + 100) {
            return false;  // 윈도우 밖 → 거부
        }
        last_counter_ = received;
        return true;
    }

private:
    std::vector<uint8_t> key_;
    uint32_t last_counter_ = 0;
};
```

**키 파일 생성:**
```bash
# 32바이트 랜덤 키 생성
sudo mkdir -p /etc/secoc
openssl rand -out /etc/secoc/key.bin 32
sudo chmod 400 /etc/secoc/key.bin
sudo chown root:root /etc/secoc/key.bin

# 검증
ls -la /etc/secoc/key.bin
# 기대 출력: -r-------- 1 root root 32 ... key.bin
```

**TC-SEC-001~004 C++ 검증:**
```bash
cd adaptive_ecu/build && cmake .. && make && ctest -R test_secoc --output-on-failure
# 기대 출력:
# TC-SEC-001: 정상 MAC 생성/검증  PASSED
# TC-SEC-002: 변조 MAC 검증 실패  PASSED
# TC-SEC-003: 롤링 카운터 윈도우 밖 거부  PASSED
# TC-SEC-004: Python↔C++ 교차 검증  PASSED
```

**TC-SEC-004 교차 검증 방법:**
```bash
# Python에서 테스트 벡터 생성
python3 -c "
from security.secoc_module import compute_mac
key = b'\\x01' * 32
mac = compute_mac(key, 0x0100, 1, b'\\x01\\x02\\x03\\x04\\x05\\x06\\x07\\x08')
print('Expected MAC:', mac.hex())
"
# 출력된 hex 값을 C++ 테스트의 expected 값에 하드코딩
```

**트러블슈팅 — OpenSSL 링크 에러:**
```bash
# CMakeLists.txt에 추가:
# find_package(OpenSSL REQUIRED)
# target_link_libraries(secoc_module OpenSSL::SSL OpenSSL::Crypto)

# pkg-config 확인
pkg-config --libs openssl
# 기대 출력: -lssl -lcrypto
```

> **의존성 알림**: 팀원B는 이 `secoc_module.cpp` 완성 후 `secoc_verifier.cpp`를 구현한다. 4주차 완성 후 팀원B에게 통보할 것.

---

## M4 (9월) — IDS + 공격 시뮬레이터

### 목표

Python으로 Isolation Forest 기반 IDS를 구현하고, Fuzzy/Flooding 공격 시뮬레이터를 만들어 1차 탐지율 데이터를 수집한다. IDS 탐지 결과를 CAN 0x200 (IDS_Alert)으로 전송하는 alerter를 구현한다. TARA.md v1을 작성한다.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | Python 가상환경 + python-can 설치 | 30분 | `import can` 성공 |
| 1 | `collect_normal.py` 정상 트래픽 30분+ 수집 | 2시간(+30분 실행) | 7차원 특징 벡터 CSV 생성 |
| 2 | `train_model.py` Isolation Forest 학습 | 3시간 | 탐지율 ≥90%, 오탐율 ≤5% (TC-SEC-006) |
| 2 | `fuzzy_attack.py` 구현 | 2시간 | TC-SEC-005-a 통과 |
| 3 | `flooding_attack.py` 구현 | 2시간 | ≥5,000 msg/초 (TC-SEC-005-d) |
| 3 | `ids_alerter.py` CAN 0x200 전송 | 2시간 | TC-SEC-007 통과 |
| 3 | Fuzzy + Flooding 각 100회 → 1차 탐지율 기록 | 4시간 | CSV 기록 완료 |
| 3 | `TARA.md` v1 — 자산 식별 + STRIDE | 4시간 | 초안 완성 |
| 4 | `TARA.md` v1 Feasibility Rating 추가 | 2시간 | 완성 |

### 수행 과정

#### 0. Python 환경 설정 (사전 작업)

```bash
# 가상환경 생성
cd ~/Capstone-proj/security
python3 -m venv venv
source venv/bin/activate

# 패키지 설치
pip install python-can scikit-learn pandas numpy joblib matplotlib pytest

# requirements.txt 생성
pip freeze > requirements.txt
```

**검증:**
```bash
python3 -c "import can; print(can.__version__)"
# 기대 출력: 4.x.x

python3 -c "from sklearn.ensemble import IsolationForest; print('OK')"
# 기대 출력: OK
```

**트러블슈팅 — python-can SocketCAN 권한 오류:**
```bash
# SocketCAN은 root 권한 필요
sudo python3 collect_normal.py
# 또는 capability 설정:
sudo setcap cap_net_raw+eip $(which python3)
```

#### 1. 정상 트래픽 수집 (1주차)

`security/collect_normal.py`:
```python
#!/usr/bin/env python3
"""정상 CAN 트래픽을 수집하여 7차원 특징 벡터 CSV를 생성한다."""
import can
import time
import csv
import numpy as np
import argparse

def extract_features(msgs):
    """1초 윈도우 내 메시지에서 7차원 특징 벡터 추출"""
    if not msgs:
        return None

    ids = [m.arbitration_id for m in msgs]
    timestamps = [m.timestamp for m in msgs]
    payloads = [int.from_bytes(m.data, 'big') if m.data else 0 for m in msgs]

    intervals = np.diff(timestamps) if len(timestamps) > 1 else [0.0]

    return [
        np.mean(ids),           # id_mean
        np.std(ids),            # id_std
        np.mean(intervals),     # interval_mean
        np.std(intervals),      # interval_std
        len(msgs),              # msg_count
        np.mean(payloads),      # payload_mean
        np.std(payloads),       # payload_std
    ]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--channel', default='vcan0')
    parser.add_argument('--duration', type=int, default=1800, help='수집 시간(초)')
    parser.add_argument('--output', default='normal_traffic.csv')
    args = parser.parse_args()

    bus = can.interface.Bus(channel=args.channel, bustype='socketcan')
    features = []

    window_msgs = []
    window_start = time.time()
    start = time.time()

    print(f"정상 트래픽 수집 시작 ({args.duration}초)...")

    while time.time() - start < args.duration:
        msg = bus.recv(timeout=1.0)
        if msg:
            window_msgs.append(msg)

        if time.time() - window_start >= 1.0:
            vec = extract_features(window_msgs)
            if vec:
                features.append(vec)
            window_msgs = []
            window_start = time.time()

    # CSV 저장
    with open(args.output, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'id_mean', 'id_std', 'interval_mean', 'interval_std',
            'msg_count', 'payload_mean', 'payload_std'
        ])
        writer.writerows(features)

    print(f"수집 완료: {len(features)} 윈도우 → {args.output}")
    bus.shutdown()

if __name__ == '__main__':
    main()
```

**실행:**
```bash
# 사전에 adaptive_ecu가 정상 BMS 데이터를 송신 중이어야 함
# 터미널 1: ECU 실행
./adaptive_ecu --secoc=off --ids=off

# 터미널 2: 수집
cd security
source venv/bin/activate
sudo python3 collect_normal.py --channel vcan0 --duration 1800 --output normal_traffic.csv
# 30분 후 완료
```

**검증:**
```bash
wc -l normal_traffic.csv
# 기대 출력: 1801 (헤더 1줄 + 1800 윈도우)

head -3 normal_traffic.csv
# 기대 출력:
# id_mean,id_std,interval_mean,interval_std,msg_count,payload_mean,payload_std
# 256.0,0.0,0.099...,0.001...,10,...,...
```

**트러블슈팅 — 수집 윈도우 0개:**
- ECU 프로그램이 CAN 메시지를 실제 송신 중인지 `candump vcan0 | head -5`로 확인
- channel이 맞는지 확인 (`vcan0` vs `can0`)

#### 2. Isolation Forest 학습 (2주차)

`security/train_model.py`:
```python
#!/usr/bin/env python3
"""Isolation Forest IDS 모델 학습"""
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='normal_traffic.csv')
    parser.add_argument('--output', default='ids/ids_model.pkl')
    parser.add_argument('--contamination', type=float, default=0.01)
    parser.add_argument('--threshold', type=float, default=-0.5)
    args = parser.parse_args()

    data = pd.read_csv(args.input)
    print(f"학습 데이터: {len(data)} 샘플, {data.shape[1]} 특징")

    model = IsolationForest(
        contamination=args.contamination,
        random_state=42,
        n_estimators=100,
    )
    model.fit(data)
    joblib.dump(model, args.output)
    print(f"모델 저장: {args.output}")

    # 자체 검증: 정상 데이터 오탐율 확인
    scores = model.decision_function(data)
    false_positives = (scores < args.threshold).sum() / len(scores)
    print(f"자체 오탐율: {false_positives:.2%} (목표: ≤5%)")
    print(f"score 통계: min={scores.min():.4f}, max={scores.max():.4f}, "
          f"mean={scores.mean():.4f}, std={scores.std():.4f}")

    if false_positives > 0.05:
        print("WARNING: 오탐율 5% 초과! threshold 조정 필요")

if __name__ == '__main__':
    main()
```

**실행:**
```bash
cd security
source venv/bin/activate
python3 train_model.py --input normal_traffic.csv --output ids/ids_model.pkl
# 기대 출력:
# 학습 데이터: 1800 샘플, 7 특징
# 모델 저장: ids/ids_model.pkl
# 자체 오탐율: 1.00% (목표: ≤5%)
```

**TC-SEC-006 검증:**
```bash
cd security && python3 -m pytest tests/test_ids_engine.py -v
# 기대 출력: test_ids_engine.py::test_detection_accuracy PASSED
```

**트러블슈팅 — 탐지율 <90%:**
- contamination 감소: 0.01 → 0.005 (모델이 더 민감해짐)
- 특징 벡터 차원 추가: entropy, unique_id_count 등
- 학습 데이터 불충분: 30분 → 60분으로 수집 시간 확대

#### 3. 공격 스크립트 (2~3주차)

**fuzzy_attack.py** — 랜덤 CAN ID + 랜덤 페이로드:

`security/attacks/fuzzy_attack.py`:
```python
#!/usr/bin/env python3
"""Fuzzy Attack: 랜덤 CAN ID + 랜덤 페이로드 주입"""
import can
import random
import argparse
import time

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--channel', default='vcan0')
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--delay', type=float, default=0.01, help='메시지 간 딜레이(초)')
    args = parser.parse_args()

    bus = can.interface.Bus(channel=args.channel, bustype='socketcan')
    print(f"Fuzzy Attack 시작: {args.count}회")

    for i in range(args.count):
        msg = can.Message(
            arbitration_id=random.randint(0, 0x7FF),
            data=[random.randint(0, 255) for _ in range(8)],
            is_extended_id=False
        )
        bus.send(msg)
        time.sleep(args.delay)

    print(f"Fuzzy Attack 완료: {args.count}개 전송")
    bus.shutdown()

if __name__ == '__main__':
    main()
```

**flooding_attack.py** — 동일 ID 대량 전송 (>=5,000 msg/sec):

`security/attacks/flooding_attack.py`:
```python
#!/usr/bin/env python3
"""Flooding Attack: 동일 CAN ID 대량 전송 (≥5,000 msg/sec)"""
import can
import time
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--channel', default='vcan0')
    parser.add_argument('--target-id', type=lambda x: int(x, 0), default=0x100)
    parser.add_argument('--duration', type=float, default=10.0, help='공격 지속시간(초)')
    args = parser.parse_args()

    bus = can.interface.Bus(channel=args.channel, bustype='socketcan')
    msg = can.Message(
        arbitration_id=args.target_id,
        data=[0xFF] * 8,
        is_extended_id=False
    )

    count = 0
    start = time.time()
    print(f"Flooding Attack 시작 (target=0x{args.target_id:03X}, duration={args.duration}s)")

    while time.time() - start < args.duration:
        bus.send(msg)
        count += 1

    elapsed = time.time() - start
    rate = count / elapsed
    print(f"Flooding Attack 완료: {count}개 / {elapsed:.1f}초 = {rate:.0f} msg/sec")
    print(f"{'PASS' if rate >= 5000 else 'FAIL'}: 목표 ≥5,000 msg/sec")
    bus.shutdown()

if __name__ == '__main__':
    main()
```

**실행 + 검증:**
```bash
cd security
source venv/bin/activate

# Fuzzy Attack
sudo python3 attacks/fuzzy_attack.py --channel vcan0 --count 100
# 기대 출력: Fuzzy Attack 완료: 100개 전송

# Flooding Attack (TC-SEC-005-d)
sudo python3 attacks/flooding_attack.py --channel vcan0 --duration 10
# 기대 출력: ... = 5XXX msg/sec
# PASS: 목표 ≥5,000 msg/sec
```

**트러블슈팅 — Flooding 속도 <5,000 msg/sec:**
- vcan0은 실제 CAN보다 빠르므로 보통 문제 없음
- 실제 CAN에서 느릴 경우: `can0` bitrate 500000 확인
- `sleep` 제거 확인 (flooding에는 delay 없어야 함)

#### 4. ids_alerter.py (3주차)

`security/ids/ids_alerter.py`:
```python
#!/usr/bin/env python3
"""IDS 탐지 결과를 CAN 0x200 (IDS_Alert)으로 전송"""
import can
import struct
import time

# ICD §1.5 IDS_Alert 레이아웃
ATTACK_TYPES = {'none': 0, 'fuzzy': 1, 'replay': 2, 'spoofing': 3, 'flooding': 4}

def send_alert(bus, attack_type: str, anomaly_score: float,
               suspect_can_id: int = 0xFFFF):
    """CAN 0x200 IDS_Alert 프레임 전송"""
    type_code = ATTACK_TYPES.get(attack_type, 0)
    score_raw = min(int(anomaly_score / 0.01), 255)
    timestamp = int(time.time()) & 0xFFFFFFFF

    data = struct.pack('>BBHi',
                       type_code,        # Byte 0: AttackType
                       score_raw,        # Byte 1: AnomalyScore (×0.01)
                       suspect_can_id,   # Byte 2-3: SuspectCANID
                       timestamp)        # Byte 4-7: Timestamp

    alert = can.Message(
        arbitration_id=0x200,
        data=data,
        is_extended_id=False
    )
    bus.send(alert)
```

**TC-SEC-007 검증:**
```bash
cd security && python3 -m pytest tests/test_ids_alerter.py -v
# 기대 출력:
# test_ids_alerter.py::test_alert_frame_format PASSED
# test_ids_alerter.py::test_flooding_alert PASSED
```

**pytest 테스트 구조:**

`security/tests/test_ids_alerter.py`:
```python
import can
import pytest
from ids.ids_alerter import send_alert

@pytest.fixture
def vbus():
    bus = can.interface.Bus(channel='test', bustype='virtual')
    yield bus
    bus.shutdown()

def test_alert_frame_format(vbus):
    reader = can.interface.Bus(channel='test', bustype='virtual')
    send_alert(vbus, 'flooding', 2.55, 0x0100)
    msg = reader.recv(timeout=1.0)
    assert msg is not None
    assert msg.arbitration_id == 0x200
    assert msg.data[0] == 4  # AttackType = Flooding
    reader.shutdown()
```

#### 5. 1차 탐지율 기록 (3주차)

```bash
# Fuzzy 100회 × 탐지 기록
for i in $(seq 1 100); do
    sudo python3 attacks/fuzzy_attack.py --channel vcan0 --count 50 &
    sleep 2  # IDS가 1초 윈도우로 탐지
    # IDS 로그에서 탐지 여부 기록
done

# Flooding 100회 × 탐지 기록
for i in $(seq 1 100); do
    sudo python3 attacks/flooding_attack.py --channel vcan0 --duration 3 &
    sleep 5
done
```

결과를 CSV로 기록:
```csv
config,attack_type,trial,detected,latency_ms
baseline,fuzzy,1,true,850
baseline,fuzzy,2,true,920
...
baseline,flooding,100,true,1200
```

#### 6. TARA.md v1 작성 (3~4주차)

ISO 21434 기반 구조:

1. **자산 식별 (Asset Identification)**
   - CAN 버스 통신 데이터
   - BMS SOC/SOH/전압/전류/온도 데이터
   - SecOC 공유 키 (`/etc/secoc/key.bin`)
   - IDS 학습 모델 (`ids_model.pkl`)
   - Fail-safe 상태 제어 권한

2. **STRIDE 위협 모델링**
   - **S**poofing: 가짜 BMS 데이터 주입 (CAN ID 0x100)
   - **T**ampering: 전송 중 페이로드 변조
   - **R**epudiation: 공격 출처 부인
   - **I**nformation Disclosure: CAN 트래픽 도청
   - **D**enial of Service: Flooding으로 버스 마비
   - **E**levation: Fail-safe 상태 우회

3. **Feasibility Rating**: 공격 난이도 × 영향도 매트릭스
4. **위협 처리 방안**: SecOC(인증), IDS(탐지), Fail-safe(완화)

**검증:** PR 오픈 → 팀원B 리뷰 → 합의 후 머지

---

## M5 (10월) — Ablation Study

### 목표

Replay/Spoofing 공격 스크립트를 추가 구현한다. SecOC on/off, IDS on/off CLI 스위치로 3가지 방어 구성(Config 1~3)을 만들고, 4종 공격 x 3 Config x 100회 = 총 1,200회 실험을 수행하여 결과를 CSV로 기록한다. IDS contamination 튜닝 + ROC 커브 분석으로 최적 threshold를 결정한다.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | `replay_attack.py` 구현 | 3시간 | TC-SEC-005-b 통과 |
| 1 | `spoofing_attack.py` 구현 | 2시간 | TC-SEC-005-c 통과 |
| 1 | Ablation Study 환경 구성 (CLI 스위치) | 3시간 | `--secoc=on/off --ids=on/off` 동작 |
| 1 | 실험 자동화 스크립트 작성 | 3시간 | `run_ablation.sh` 동작 |
| 2 | **Config 1** (방어 없음): 4종 x 100회 | 6시간 | 공격 성공률 기록 |
| 3 | **Config 2** (SecOC only): 4종 x 100회 | 6시간 | 차단율 기록 |
| 4 | **Config 3** (SecOC+IDS): 4종 x 100회 | 6시간 | 탐지율/오탐율/지연 기록 |
| 4 | TC-EXP-005: 정상 100윈도우 오탐율 ≤5% | 1시간 | PASSED |
| 4 | IDS contamination 튜닝 + ROC 커브 | 3시간 | 최적 threshold 결정 |
| 4 | ADR-001~003, 005, 008~009, 011~012 최종화 | 4시간 | PR 머지 |

### 수행 과정

#### 1. replay_attack.py (1주차)

`security/attacks/replay_attack.py`:
```python
#!/usr/bin/env python3
"""Replay Attack: 정상 CAN 프레임 캡처 후 재전송"""
import can
import time
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--channel', default='vcan0')
    parser.add_argument('--capture-count', type=int, default=10)
    parser.add_argument('--replay-delay', type=float, default=1.0,
                        help='캡처 후 재전송까지 대기 시간(초)')
    args = parser.parse_args()

    bus = can.interface.Bus(channel=args.channel, bustype='socketcan')

    # 1단계: 정상 프레임 캡처
    print(f"캡처 시작: {args.capture_count}개 프레임...")
    captured = []
    while len(captured) < args.capture_count:
        msg = bus.recv(timeout=5.0)
        if msg and msg.arbitration_id == 0x100:
            captured.append(msg)
    print(f"캡처 완료: {len(captured)}개")

    # 2단계: 대기 (카운터가 진행되도록)
    print(f"대기 {args.replay_delay}초...")
    time.sleep(args.replay_delay)

    # 3단계: 캡처된 프레임 재전송 (동일 MAC + 카운터)
    print("Replay 공격 시작...")
    for msg in captured:
        bus.send(msg)
    print(f"Replay 완료: {len(captured)}개 재전송")
    # SecOC 롤링 카운터로 인해 차단되어야 함

    bus.shutdown()

if __name__ == '__main__':
    main()
```

**TC-SEC-005-b 검증:**
```bash
cd security
source venv/bin/activate
python3 -m pytest tests/test_attack_simulator.py::test_replay -v
# 기대 출력: PASSED (캡처된 프레임과 재전송 프레임이 바이트 동일)
```

#### 2. spoofing_attack.py (1주차)

`security/attacks/spoofing_attack.py`:
```python
#!/usr/bin/env python3
"""Spoofing Attack: 가짜 SOC=100% (raw=200, x0.5=100%) CAN 주입"""
import can
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--channel', default='vcan0')
    parser.add_argument('--count', type=int, default=10)
    args = parser.parse_args()

    bus = can.interface.Bus(channel=args.channel, bustype='socketcan')

    for i in range(args.count):
        # ICD §1.2: SOC raw=200 → 200 × 0.5 = 100.0%
        fake = can.Message(
            arbitration_id=0x100,
            data=[200,   # SOC = 100% (200 × 0.5)
                  0xC8,  # SOH = 100% (200 × 0.5)
                  0x0E, 0x10,  # Voltage = 36.00V
                  0x00, 0x14,  # Current = 2.0A
                  0x41,  # Temp = 25°C (25 + 40 = 65 = 0x41)
                  0x00],  # Reserved
            is_extended_id=False
        )
        bus.send(fake)

    print(f"Spoofing Attack 완료: {args.count}개 가짜 BMS_Status 전송")
    bus.shutdown()

if __name__ == '__main__':
    main()
```

**TC-SEC-005-c 검증:**
```bash
python3 -m pytest tests/test_attack_simulator.py::test_spoofing -v
# 기대 출력: PASSED (payload[0] == 200 확인)
```

#### 3. Ablation Study 환경 구성 (1주차)

**CLI 스위치 — `main.cpp` 수정:**
```cpp
int main(int argc, char* argv[]) {
    bool secoc_enabled = true;
    bool ids_enabled = true;

    for (int i = 1; i < argc; i++) {
        std::string arg(argv[i]);
        if (arg == "--secoc=off") secoc_enabled = false;
        if (arg == "--secoc=on")  secoc_enabled = true;
        if (arg == "--ids=off")   ids_enabled = false;
        if (arg == "--ids=on")    ids_enabled = true;
    }
    // ...
}
```

**실행 확인:**
```bash
# Config 1: 방어 없음
./adaptive_ecu --secoc=off --ids=off

# Config 2: SecOC only
./adaptive_ecu --secoc=on --ids=off

# Config 3: SecOC + IDS
./adaptive_ecu --secoc=on --ids=on
```

#### 4. 실험 자동화 스크립트 (1주차)

`security/run_ablation.sh`:
```bash
#!/bin/bash
# Ablation Study 자동화 스크립트
# Usage: ./run_ablation.sh <config> <attack_type> <trials>
# Example: ./run_ablation.sh 1 spoofing 100

CONFIG=$1
ATTACK=$2
TRIALS=${3:-100}
CHANNEL="vcan0"
OUTPUT="results/config${CONFIG}_${ATTACK}.csv"

mkdir -p results

# ECU 실행 옵션 결정
case $CONFIG in
    1) SECOC="off"; IDS="off" ;;
    2) SECOC="on";  IDS="off" ;;
    3) SECOC="on";  IDS="on"  ;;
    *) echo "Invalid config: $CONFIG"; exit 1 ;;
esac

echo "=== Config $CONFIG ($SECOC/$IDS) × $ATTACK × $TRIALS ==="

# ECU 백그라운드 실행
./adaptive_ecu --secoc=$SECOC --ids=$IDS &
ECU_PID=$!
sleep 3  # 초기화 대기

# CSV 헤더
echo "config,attack_type,trial,success,detected,latency_ms" > $OUTPUT

for i in $(seq 1 $TRIALS); do
    START_MS=$(date +%s%3N)

    # 공격 실행
    case $ATTACK in
        spoofing) sudo python3 attacks/spoofing_attack.py --channel $CHANNEL --count 10 ;;
        replay)   sudo python3 attacks/replay_attack.py --channel $CHANNEL ;;
        flooding) sudo python3 attacks/flooding_attack.py --channel $CHANNEL --duration 3 ;;
        fuzzy)    sudo python3 attacks/fuzzy_attack.py --channel $CHANNEL --count 50 ;;
    esac

    sleep 2  # IDS 탐지 대기

    END_MS=$(date +%s%3N)
    LATENCY=$((END_MS - START_MS))

    # 결과 판정 (IDS 로그 파싱)
    DETECTED=$(grep -c "ALERT" /tmp/ids_latest.log 2>/dev/null || echo "0")
    SUCCESS=$( [ "$DETECTED" = "0" ] && echo "true" || echo "false" )

    echo "$CONFIG,$ATTACK,$i,$SUCCESS,$( [ "$DETECTED" -gt 0 ] && echo true || echo false),$LATENCY" >> $OUTPUT

    echo "  Trial $i/$TRIALS: detected=$DETECTED, latency=${LATENCY}ms"
done

kill $ECU_PID 2>/dev/null
echo "=== 완료: $OUTPUT ==="
```

```bash
chmod +x run_ablation.sh

# 전체 12세트 실행
for config in 1 2 3; do
    for attack in spoofing replay flooding fuzzy; do
        ./run_ablation.sh $config $attack 100
    done
done
```

#### 5. Config별 실험 수행 (2~4주차)

**Config 1 — 방어 없음 (2주차):**
```bash
./run_ablation.sh 1 spoofing 100
./run_ablation.sh 1 replay 100
./run_ablation.sh 1 flooding 100
./run_ablation.sh 1 fuzzy 100
```

**Config 2 — SecOC only (3주차):**
```bash
./run_ablation.sh 2 spoofing 100
./run_ablation.sh 2 replay 100
./run_ablation.sh 2 flooding 100
./run_ablation.sh 2 fuzzy 100
```

**Config 3 — SecOC+IDS (4주차):**
```bash
./run_ablation.sh 3 spoofing 100
./run_ablation.sh 3 replay 100
./run_ablation.sh 3 flooding 100
./run_ablation.sh 3 fuzzy 100
```

#### 6. 결과 CSV 통합

`security/merge_results.py`:
```python
#!/usr/bin/env python3
"""12세트 실험 결과 통합"""
import pandas as pd
import glob

files = glob.glob('results/config*_*.csv')
dfs = [pd.read_csv(f) for f in sorted(files)]
merged = pd.concat(dfs, ignore_index=True)
merged.to_csv('results/results_summary.csv', index=False)

# 요약 통계
summary = merged.groupby(['config', 'attack_type']).agg(
    total=('trial', 'count'),
    attack_success=('success', lambda x: (x == True).sum()),
    detected=('detected', lambda x: (x == True).sum()),
    avg_latency=('latency_ms', 'mean'),
).reset_index()

summary['success_rate'] = summary['attack_success'] / summary['total'] * 100
summary['detection_rate'] = summary['detected'] / summary['total'] * 100

print(summary.to_string(index=False))
summary.to_csv('results/results_summary_stats.csv', index=False)
```

```bash
python3 merge_results.py
# 기대 출력:
# config attack_type  total  attack_success  detected  avg_latency  success_rate  detection_rate
#      1    spoofing    100             100         0          ...        100.0             0.0
#      2    spoofing    100               0       ...          ...          0.0            ...
#      3    spoofing    100               0       100          ...          0.0           100.0
# ...
```

#### 7. TC-EXP-005: 정상 오탐율 ≤5% (4주차)

```bash
# ECU를 Config 3 (SecOC+IDS)로 실행, 공격 없이 100초 대기
./adaptive_ecu --secoc=on --ids=on &
sleep 100

# IDS 로그에서 false positive 횟수 확인
grep -c "ALERT" /tmp/ids_latest.log
# 기대 출력: ≤5 (100윈도우 중 5개 이하)
```

#### 8. ROC 커브 분석 (4주차)

`security/analyze_roc.py`:
```python
#!/usr/bin/env python3
"""ROC 커브 분석 + 최적 threshold 결정"""
import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc

# 정상 + 공격 데이터 로드
normal = pd.read_csv('normal_traffic.csv')
attack = pd.read_csv('attack_traffic.csv')  # 공격 중 수집한 특징 벡터

X = pd.concat([normal, attack], ignore_index=True)
y_true = np.array([0]*len(normal) + [1]*len(attack))  # 0=정상, 1=공격

model = joblib.load('ids/ids_model.pkl')
scores = -model.decision_function(X)  # 부호 반전 (높을수록 이상)

fpr, tpr, thresholds = roc_curve(y_true, scores)
roc_auc = auc(fpr, tpr)

# ROC 커브 그래프
plt.figure(figsize=(8, 6))
plt.plot(fpr, tpr, 'b-', linewidth=2, label=f'Isolation Forest (AUC = {roc_auc:.3f})')
plt.plot([0, 1], [0, 1], 'k--', linewidth=1, label='Random')
plt.xlabel('False Positive Rate', fontsize=12)
plt.ylabel('True Positive Rate', fontsize=12)
plt.title('ROC Curve - CAN IDS', fontsize=14)
plt.legend(fontsize=11)
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('results/roc_curve.png', dpi=150)
print(f"ROC 커브 저장: results/roc_curve.png")

# 최적 threshold 결정: TPR ≥90% AND FPR ≤5%
for i, (fp, tp, th) in enumerate(zip(fpr, tpr, thresholds)):
    if tp >= 0.90 and fp <= 0.05:
        print(f"최적 threshold: {th:.4f} (TPR={tp:.2%}, FPR={fp:.2%})")
        break
else:
    print("WARNING: TPR≥90% AND FPR≤5% 동시 만족 점 없음 — contamination 재조정 필요")
    # 가장 가까운 점 찾기
    best_idx = np.argmax(tpr - fpr)
    print(f"차선: threshold={thresholds[best_idx]:.4f} "
          f"(TPR={tpr[best_idx]:.2%}, FPR={fpr[best_idx]:.2%})")
```

```bash
python3 analyze_roc.py
# 기대 출력:
# ROC 커브 저장: results/roc_curve.png
# 최적 threshold: -0.3500 (TPR=92.00%, FPR=3.00%)
```

**contamination 튜닝 가이드:**

| 현상 | 조치 |
|------|------|
| FPR > 5% (정상을 공격으로 오판) | contamination 감소: 0.01 → 0.005 |
| TPR < 90% (공격 놓침) | contamination 증가: 0.01 → 0.02 |
| 둘 다 나쁨 | 특징 벡터 차원 추가 (entropy, unique_id_ratio) |
| 특정 공격만 TPR 낮음 | 해당 공격의 특징이 정상과 유사 → 공격 강도 조절 |

#### 9. ADR 최종화 (4주차)

최종화할 ADR 목록:
- ADR-001: SocketCAN 선택 (vs PEAK PCAN)
- ADR-002: HMAC-SHA256 선택 (vs AES-CMAC)
- ADR-003: Isolation Forest 선택 (vs Autoencoder, vs LSTM)
- ADR-005: EKF SOC 추정 (vs UKF, vs 쿨롱 카운팅)
- ADR-008: Ablation Study 설계 (3 Config x 4 Attack)
- ADR-009: IDS Node A 위치 (vs Node B, vs 별도 노드)
- ADR-011: Python IDS (vs C++ 구현)
- ADR-012: SecOC 분리 프레임 (vs Authenticated PDU)

각 ADR에 Ablation Study 실험 결과 수치를 근거로 반영한다.

---

## M6 (11월) — 문서 + 분석

### 목표

Ablation Study 12세트 결과를 종합 분석하여 그래프와 표를 생성한다. EKF vs 쿨롱 카운팅 RMSE 비교 그래프를 만든다. `docs/SDD-ECU.md`를 전체 완성하고, `docs/TARA.md`를 ISO 21434 기반으로 최종화한다.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | Ablation 12세트 결과 종합 분석 (Excel/CSV) | 4시간 | 통계 테이블 완성 |
| 1 | Ablation 결과 비교 막대 그래프 생성 | 3시간 | `ablation_results.png` 생성 |
| 1 | EKF vs 쿨롱 카운팅 RMSE 비교 그래프 | 3시간 | `ekf_accuracy.png` 생성 |
| 2 | `docs/SDD-ECU.md` §1~§2 (개요, 아키텍처) | 4시간 | PR draft 작성 |
| 2 | `docs/SDD-ECU.md` §3 BSW 모듈 (CAN CDD, Publisher, Watchdog) | 4시간 | TC 매핑 포함 |
| 2 | `docs/SDD-ECU.md` §3 BMS 모듈 (EKF, SOH, Fail-safe) | 4시간 | TC 매핑 포함 |
| 3 | `docs/SDD-ECU.md` §3 SecOC 모듈 + IDS 모듈 | 3시간 | TC 매핑 포함 |
| 3 | `docs/SDD-ECU.md` §4~§5 (인터페이스, 데이터 모델) | 2시간 | 전체 완성 |
| 3 | `docs/TARA.md` ISO 21434 구조 최종화 | 4시간 | Risk Level 확정 |
| 4 | 전체 문서 자기 검토 + PR 머지 | 3시간 | PR 머지 완료 |

### 수행 과정

#### 1. Ablation 결과 분석 그래프 (1주차)

`security/plot_ablation.py`:
```python
#!/usr/bin/env python3
"""Ablation Study 결과 비교 그래프 생성"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# 한글 폰트 설정 (RPi4 Ubuntu)
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

df = pd.read_csv('results/results_summary_stats.csv')

configs = ['No Defense', 'SecOC Only', 'SecOC+IDS']
attacks = ['Spoofing', 'Replay', 'Flooding', 'Fuzzy']
config_labels = {1: 'No Defense', 2: 'SecOC Only', 3: 'SecOC+IDS'}
attack_labels = {'spoofing': 'Spoofing', 'replay': 'Replay',
                 'flooding': 'Flooding', 'fuzzy': 'Fuzzy'}

# === 그래프 1: 공격 성공률 비교 (Grouped Bar) ===
fig, ax = plt.subplots(figsize=(10, 6))
x = np.arange(len(attacks))
width = 0.25

for i, config in enumerate([1, 2, 3]):
    rates = []
    for attack in ['spoofing', 'replay', 'flooding', 'fuzzy']:
        row = df[(df['config'] == config) & (df['attack_type'] == attack)]
        rates.append(row['success_rate'].values[0] if len(row) > 0 else 0)
    ax.bar(x + i*width, rates, width, label=config_labels[config])

ax.set_xlabel('Attack Type', fontsize=12)
ax.set_ylabel('Attack Success Rate (%)', fontsize=12)
ax.set_title('Ablation Study: Attack Success Rate by Defense Configuration', fontsize=14)
ax.set_xticks(x + width)
ax.set_xticklabels(attacks)
ax.legend()
ax.set_ylim(0, 105)
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig('results/ablation_success_rate.png', dpi=150)
print("저장: results/ablation_success_rate.png")

# === 그래프 2: 탐지율 비교 (Config 3) ===
fig, ax = plt.subplots(figsize=(8, 5))
detection_rates = []
for attack in ['spoofing', 'replay', 'flooding', 'fuzzy']:
    row = df[(df['config'] == 3) & (df['attack_type'] == attack)]
    detection_rates.append(row['detection_rate'].values[0] if len(row) > 0 else 0)

colors = ['#4CAF50' if r >= 90 else '#F44336' for r in detection_rates]
ax.bar(attacks, detection_rates, color=colors)
ax.axhline(y=90, color='red', linestyle='--', label='Target: 90%')
ax.set_ylabel('Detection Rate (%)', fontsize=12)
ax.set_title('IDS Detection Rate (SecOC+IDS Config)', fontsize=14)
ax.legend()
ax.set_ylim(0, 105)
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig('results/ablation_detection_rate.png', dpi=150)
print("저장: results/ablation_detection_rate.png")

# === 그래프 3: 평균 탐지 지연 ===
fig, ax = plt.subplots(figsize=(8, 5))
latencies = []
for attack in ['spoofing', 'replay', 'flooding', 'fuzzy']:
    row = df[(df['config'] == 3) & (df['attack_type'] == attack)]
    latencies.append(row['avg_latency'].values[0] if len(row) > 0 else 0)

ax.bar(attacks, latencies, color='#2196F3')
ax.axhline(y=3000, color='red', linestyle='--', label='Target: 3000ms')
ax.set_ylabel('Average Detection Latency (ms)', fontsize=12)
ax.set_title('IDS Detection Latency (SecOC+IDS Config)', fontsize=14)
ax.legend()
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig('results/ablation_latency.png', dpi=150)
print("저장: results/ablation_latency.png")
```

**실행:**
```bash
cd security
source venv/bin/activate
python3 plot_ablation.py
# 기대 출력:
# 저장: results/ablation_success_rate.png
# 저장: results/ablation_detection_rate.png
# 저장: results/ablation_latency.png

ls -la results/*.png
# 3개 PNG 파일 존재 확인
```

#### 2. EKF 정확도 그래프 (1주차)

`security/plot_ekf.py`:
```python
#!/usr/bin/env python3
"""EKF vs 쿨롱 카운팅 SOC 추정 비교 그래프"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# EKF 실험 결과 로드 (test_ekf_soc에서 출력한 CSV)
df = pd.read_csv('data/ekf_comparison.csv')
# 컬럼: time_s, true_soc, coulomb_soc, ekf_soc

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), height_ratios=[3, 1])

# === 상단: SOC 추정 비교 ===
ax1.plot(df['time_s']/60, df['true_soc']*100, 'k-', linewidth=2, label='True SOC')
ax1.plot(df['time_s']/60, df['coulomb_soc']*100, 'r--', linewidth=1.5,
         label='Coulomb Counting')
ax1.plot(df['time_s']/60, df['ekf_soc']*100, 'b-.', linewidth=1.5, label='EKF')
ax1.set_ylabel('SOC (%)', fontsize=12)
ax1.set_title('SOC Estimation: EKF vs Coulomb Counting (1-hour profile)', fontsize=14)
ax1.legend(fontsize=11)
ax1.grid(True, alpha=0.3)

# === 하단: 오차 비교 ===
err_coulomb = np.abs(df['coulomb_soc'] - df['true_soc']) * 100
err_ekf = np.abs(df['ekf_soc'] - df['true_soc']) * 100
ax2.plot(df['time_s']/60, err_coulomb, 'r-', alpha=0.7, label='Coulomb Error')
ax2.plot(df['time_s']/60, err_ekf, 'b-', alpha=0.7, label='EKF Error')
ax2.set_xlabel('Time (minutes)', fontsize=12)
ax2.set_ylabel('Absolute Error (%)', fontsize=12)
ax2.legend(fontsize=10)
ax2.grid(True, alpha=0.3)

# RMSE 계산
rmse_coulomb = np.sqrt(np.mean(err_coulomb**2))
rmse_ekf = np.sqrt(np.mean(err_ekf**2))
ax2.text(0.02, 0.95, f'RMSE Coulomb: {rmse_coulomb:.4f}%\nRMSE EKF: {rmse_ekf:.4f}%',
         transform=ax2.transAxes, fontsize=10, va='top',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

plt.tight_layout()
plt.savefig('results/ekf_accuracy.png', dpi=150)
print(f"저장: results/ekf_accuracy.png")
print(f"RMSE Coulomb: {rmse_coulomb:.4f}%")
print(f"RMSE EKF: {rmse_ekf:.4f}%")
print(f"EKF 우위: {'YES' if rmse_ekf < rmse_coulomb else 'NO'}")
```

**EKF 비교 데이터 생성 (C++ 테스트에서 CSV 출력):**

`adaptive_ecu/test/test_ekf_soc.cpp` 에 추가:
```cpp
TEST(EkfSoc, GenerateComparisonCSV) {
    // PROFILE_CSV 모드로 1시간 프로파일 실행
    // 결과를 data/ekf_comparison.csv 로 출력
    std::ofstream out("data/ekf_comparison.csv");
    out << "time_s,true_soc,coulomb_soc,ekf_soc\n";

    EkfSocEstimator ekf(params);
    double coulomb_soc = params.SOC_init;

    for (auto& row : profile_data) {
        ekf.update(row.voltage, row.current, row.dt);
        coulomb_soc -= (row.current * row.dt) / (params.capacity * 3600.0);
        out << row.time << "," << row.true_soc << ","
            << coulomb_soc << "," << ekf.getSoc() << "\n";
    }
}
```

```bash
# C++ 테스트 실행하여 CSV 생성
cd adaptive_ecu/build && ctest -R GenerateComparisonCSV --output-on-failure

# Python 그래프 생성
cd ~/Capstone-proj/security
python3 plot_ekf.py
# 기대 출력:
# 저장: results/ekf_accuracy.png
# RMSE EKF: 0.xxxx%
# EKF 우위: YES
```

#### 3. SDD-ECU.md 전체 작성 (2~3주차)

**SDD-ECU.md 섹션별 작성 가이드:**

| 섹션 | 내용 | 참조 |
|------|------|------|
| §1 개요 | 시스템 목적, 범위, 용어 정의 | SRS.md FR 목록 |
| §2 아키텍처 | 레이어 다이어그램 (BSW/App), 모듈 의존성 | ROADMAP.md 디렉토리 구조 |
| §3.1 CAN CDD | SocketCAN 설계, MockCanDriver, 상태 다이어그램 | TC-BSW-001~003 |
| §3.2 Publisher/Subscriber | ara::com 경량 구현, 멀티스레드 안전성 | TC-BSW-004~005 |
| §3.3 Watchdog Manager | 감시 주기 1초, 타임아웃 3초, 재시작 로직 | TC-BSW-006~007 |
| §3.4 Sensor Simulator | 4가지 모드 (CONSTANT/CSV/RANDOM/HW) | TC-BSW-008 |
| §3.5 EKF SOC Estimator | EKF 파라미터, OCV-SOC 다항식, 정확도 | TC-BMS-001~002 |
| §3.6 SOH Estimator | 누적 방전량 기반 계산 | TC-BMS-003 |
| §3.7 Fail-safe FSM | 4상태 전이 다이어그램, 조건 표 | TC-BMS-004~006 |
| §3.8 CAN Publisher | 100ms 주기 송신, ICD §1.2 매핑 | TC-BMS-007 |
| §3.9 SecOC Module | HMAC-SHA256, 절단 MAC, 롤링 카운터 | TC-SEC-001~004 |
| §3.10 IDS Module | Isolation Forest, 7차원 특징 벡터, threshold | TC-SEC-005~007 |
| §4 인터페이스 | CAN ID 요약, ara::com 토픽 | ICD.md |
| §5 데이터 모델 | CanFrame, BmsStatusData, FailSafeEvent 등 | 소스 코드 헤더 |

**각 모듈 섹션 템플릿:**
```markdown
### §3.X [모듈명]

#### 목적
[한 문장으로 모듈의 존재 이유]

#### 설계 결정
- [ADR-XXX 참조: 선택 근거]

#### 클래스/함수 구조
[클래스 다이어그램 또는 핵심 API 목록]

#### 동작 흐름
[시퀀스 다이어그램 또는 상태 다이어그램]

#### 테스트 매핑
| TC ID | 검증 대상 | 파일 |
|-------|----------|------|
| TC-XXX-YYY | ... | test/... |

#### 제약사항/한계
[알려진 제한 사항]
```

**검증:**
- 모든 TC-BSW, TC-BMS, TC-SEC가 하나 이상의 SDD 모듈 섹션에 매핑되어 있는지 확인
- `grep -c "TC-" docs/SDD-ECU.md` → TEST_PLAN.md의 팀원A 담당 TC 개수와 일치

#### 4. TARA.md 최종화 (3주차)

**ISO 21434 기반 구조:**

```markdown
# TARA — Threat Analysis and Risk Assessment

## 1. 자산 식별 (Asset Identification)
| ID | 자산 | 유형 | 기밀성 | 무결성 | 가용성 |
|----|------|------|--------|--------|--------|
| A-01 | CAN 버스 데이터 | 통신 | M | H | H |
| A-02 | BMS SOC/SOH | 데이터 | L | H | H |
| A-03 | SecOC 공유 키 | 보안 자산 | H | H | M |
| A-04 | IDS 모델 | SW 자산 | M | H | M |

## 2. 위협 시나리오 (STRIDE)
[위협별 시나리오 + Ablation Study 실험 결과 연결]

## 3. Feasibility Rating
[공격 난이도: Elapsed Time, Expertise, Knowledge, Window, Equipment]

## 4. Risk Level
[Impact × Feasibility 매트릭스 → Risk Level 1~5]

## 5. 위협 처리 방안
| 위협 | 처리 유형 | 방어 메커니즘 | 실험 결과 |
|------|----------|-------------|-----------|
| Spoofing | Mitigate | SecOC HMAC | Config 2: 차단율 XX% |
| Replay | Mitigate | Rolling Counter | Config 2: 차단율 XX% |
| Flooding | Detect | IDS Isolation Forest | Config 3: 탐지율 XX% |
| Fuzzy | Detect+Mitigate | SecOC + IDS | Config 3: 탐지율 XX% |
```

**검증:**
```bash
# 모든 위협이 처리 방안에 매핑되어 있는지 확인
grep -c "위협" docs/TARA.md
# 최소 4개 (Spoofing, Replay, Flooding, Fuzzy)

# Ablation 결과 수치가 포함되어 있는지 확인
grep -c "Config" docs/TARA.md
# 최소 3개 (Config 1, 2, 3)
```

---

## M7 (12월) — 최종 검증

### 목표

Ablation Study 12세트를 재실행하여 재현성(편차 ≤5%)을 검증한다. 탐지율 미달 공격 유형을 보완한다. 최종 실험 보고서를 완성하고, `results_summary.csv`를 확정한다. IDS 모델 재현 방법 문서(`how_to_train.md`)를 작성한다.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | RPi4 CPU 클럭 고정 (governor=performance) | 15분 | 클럭 고정 확인 |
| 1 | Ablation 12세트 재실행 | 8시간 | 12세트 CSV 생성 |
| 1 | 재현성 검증 (편차 ≤5%) | 2시간 | 모든 세트 편차 ≤5% |
| 2 | 탐지율 미달 공격 유형 분석 | 3시간 | 원인 파악 |
| 2 | 보완 실험 수행 | 4시간 | 추가 데이터 수집 |
| 2 | 최종 실험 보고서 초안 | 4시간 | 초안 완성 |
| 3 | 최종 실험 보고서 본문 작성 | 6시간 | 그래프+표 포함 |
| 4 | `results_summary.csv` 최종 업데이트 | 1시간 | CSV 확정 |
| 4 | `how_to_train.md` 재현 방법 문서 | 2시간 | 문서 완성 |
| 4 | 재현성 검증 스크립트 최종 확인 | 1시간 | 스크립트 동작 확인 |

### 수행 과정

#### 1. CPU 클럭 고정 (1주차)

실험 재현성을 위해 RPi4 CPU를 성능 모드로 고정한다:

```bash
# cpufreq 유틸 설치
sudo apt install -y cpufrequtils

# 현재 governor 확인
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
# 기대 출력: ondemand (기본값)

# performance 모드 고정
sudo cpufreq-set -g performance

# 모든 코어에 적용
for cpu in /sys/devices/system/cpu/cpu[0-3]; do
    echo performance | sudo tee $cpu/cpufreq/scaling_governor
done

# 검증
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
# 기대 출력:
# performance
# performance
# performance
# performance

# 현재 클럭 확인
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
# 기대 출력: 1500000 (1.5GHz 고정)
```

**트러블슈팅 — cpufreq-set 명령 없음:**
```bash
# 직접 sysfs 제어
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

#### 2. Ablation 12세트 재실행 (1주차)

```bash
cd ~/Capstone-proj/security

# 이전 결과 백업
cp -r results results_backup_m5

# CAN 버스 다른 트래픽 차단
sudo ip link set can0 down 2>/dev/null
# vcan0만 사용

# 12세트 재실행 (random_state=42 고정)
for config in 1 2 3; do
    for attack in spoofing replay flooding fuzzy; do
        echo "=== Re-run: Config $config × $attack ==="
        ./run_ablation.sh $config $attack 100
        sleep 5  # 세트 간 안정화
    done
done

echo "12세트 재실행 완료"
```

#### 3. 재현성 검증 (1주차)

`security/verify_reproducibility.py`:
```python
#!/usr/bin/env python3
"""Ablation Study 재현성 검증 — 편차 ≤5% 확인"""
import pandas as pd
import sys

prev = pd.read_csv('results_backup_m5/results_summary_stats.csv')
curr = pd.read_csv('results/results_summary_stats.csv')

merged = prev.merge(curr, on=['config', 'attack_type'],
                    suffixes=('_prev', '_curr'))

print("=== 재현성 검증 결과 ===\n")
print(f"{'Config':>8} {'Attack':>10} {'Prev SR%':>10} {'Curr SR%':>10} "
      f"{'Diff%':>8} {'Status':>8}")
print("-" * 60)

all_pass = True
for _, row in merged.iterrows():
    prev_val = row['success_rate_prev']
    curr_val = row['success_rate_curr']
    if prev_val == 0:
        diff_pct = 0.0 if curr_val == 0 else 100.0
    else:
        diff_pct = abs(curr_val - prev_val) / prev_val * 100

    status = "PASS" if diff_pct <= 5.0 else "FAIL"
    if status == "FAIL":
        all_pass = False

    print(f"{row['config']:>8} {row['attack_type']:>10} {prev_val:>10.1f} "
          f"{curr_val:>10.1f} {diff_pct:>8.1f} {status:>8}")

print()
if all_pass:
    print("RESULT: ALL PASS — 모든 세트 편차 ≤5%")
else:
    print("RESULT: FAIL — 편차 >5% 세트 있음, 원인 분석 필요")
    sys.exit(1)
```

```bash
python3 verify_reproducibility.py
# 기대 출력:
# === 재현성 검증 결과 ===
# Config     Attack   Prev SR%   Curr SR%    Diff%   Status
# ----------------------------------------------------------
#        1   spoofing      100.0      100.0      0.0     PASS
#        1     replay      100.0      100.0      0.0     PASS
# ...
# RESULT: ALL PASS — 모든 세트 편차 ≤5%
```

**편차 >5% 시 대응:**
1. CAN 버스에 다른 프로세스가 트래픽 발생시키고 있는지 확인: `candump vcan0 | head`
2. CPU governor가 performance인지 재확인
3. `random_state=42` 고정 확인 (IDS 모델 재학습 시)
4. 네트워크 부하 확인: `top` 으로 CPU 사용률 체크

#### 4. 탐지율 미달 공격 유형 보완 (2주차)

탐지율 <90%인 공격 유형 분석:

```python
# 미달 공격 유형 파악
df = pd.read_csv('results/results_summary_stats.csv')
low = df[(df['config'] == 3) & (df['detection_rate'] < 90)]
print("탐지율 <90% 공격 유형:")
print(low[['attack_type', 'detection_rate']])
```

**보완 방법:**

| 문제 | 원인 | 해결 |
|------|------|------|
| Spoofing 탐지 낮음 | 정상과 유사한 패턴 | Spoofing 강도 강화 (비정상 SOC 범위 확대) |
| Replay 탐지 낮음 | 캡처→재전송 간격이 짧음 | replay_delay 증가 (1초 → 5초) |
| 특정 공격 FPR 높음 | threshold 과민 | ROC 커브에서 해당 공격 최적점 재탐색 |

```bash
# 보완 실험: 수정된 파라미터로 재실행
./run_ablation.sh 3 <미달공격> 100
```

#### 5. 최종 실험 보고서 (2~3주차)

**보고서 구조:**

```
1. 실험 개요
   - 목적: SecOC + IDS 방어 효과 정량 분석
   - 환경: RPi4 Ubuntu 22.04, vcan0/can0, Python 3.10

2. 실험 설계
   - 3가지 방어 구성 (Config 1/2/3)
   - 4종 공격 (Spoofing, Replay, Flooding, Fuzzy)
   - 각 100회 반복 (총 1,200회)

3. 실험 결과
   - Config별 공격 성공률 표
   - Config별 탐지율/오탐율/지연 표
   - 비교 막대 그래프 (ablation_results.png)
   - ROC 커브 (roc_curve.png)

4. 분석
   - SecOC의 Spoofing/Replay 차단 효과
   - IDS의 Flooding/Fuzzy 탐지 효과
   - 결합 방어의 시너지 효과

5. EKF 정확도 분석
   - 쿨롱 카운팅 vs EKF RMSE 비교
   - ekf_accuracy.png

6. 결론
   - 주요 발견사항
   - 한계점 및 향후 개선 방향

부록
   - 실험 환경 상세 (HW/SW 사양)
   - 재현 방법 (how_to_train.md 참조)
   - 전체 데이터 (results_summary.csv)
```

#### 6. results_summary.csv 최종 업데이트 (4주차)

```bash
# 최종 결과 통합
cd security
python3 merge_results.py

# CSV 파일 확인
head -5 results/results_summary.csv
wc -l results/results_summary.csv
# 기대: 1201 (헤더 1 + 1200 데이터)

# Git에 추가
cp results/results_summary.csv ../security/ids/results_summary.csv
```

#### 7. how_to_train.md 재현 방법 문서 (4주차)

`security/ids/how_to_train.md`:
```markdown
# IDS 모델 재현 방법

## 전제조건
- Python 3.10+
- 패키지: `pip install python-can scikit-learn pandas numpy joblib matplotlib`
- CAN 인터페이스: `vcan0` 활성화

## 재현 절차

### 1. 정상 트래픽 수집 (30분+)
```bash
cd security
source venv/bin/activate
# ECU가 정상 BMS 데이터를 vcan0으로 송신 중이어야 함
sudo python3 collect_normal.py --channel vcan0 --duration 1800 --output normal_traffic.csv
```

### 2. 모델 학습
```bash
python3 train_model.py --input normal_traffic.csv --output ids/ids_model.pkl \
    --contamination 0.01
# 기대: 오탐율 ≤5%
```

### 3. 실시간 탐지 실행
```bash
sudo python3 ids/ids_engine.py --channel vcan0 --model ids/ids_model.pkl \
    --threshold -0.5
```

### 4. 검증
```bash
python3 -m pytest tests/ -v
# 모든 테스트 통과 확인
```

## 핵심 파라미터
| 파라미터 | 값 | 근거 |
|---------|---|------|
| contamination | 0.01 | ADR-003, ROC 분석 결과 |
| threshold | -0.5 | ROC 커브 최적점 |
| random_state | 42 | 재현성 보장 |
| n_estimators | 100 | 기본값, 충분한 성능 |
| window_size | 1초 | IDS 응답 시간 요구사항 |

## 특징 벡터 (7차원)
id_mean, id_std, interval_mean, interval_std, msg_count, payload_mean, payload_std
```

**검증:**
```bash
# how_to_train.md 의 절차를 처음부터 따라 실행
# 최종: pytest 전체 통과 확인
cd security && python3 -m pytest tests/ -v
# 기대 출력: X passed, 0 failed
```

---

## M8 (1월) — 발표 준비

### 목표

데모 시나리오 A/B 리허설에 참여한다. 팀원A 직무 어필 슬라이드(BSW/CDD, BMS EKF, SecOC HMAC, IDS)를 작성한다. EKF 정확도 그래프와 Ablation Study 결과 표를 발표 자료에 삽입한다. 최종 보고서의 ECU/보안 섹션을 작성한다.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | 데모 시나리오 A 리허설 참여 (1회차) | 2시간 | 정상 동작 확인 |
| 1 | 데모 시나리오 B 리허설 참여 (1회차) | 2시간 | 공격→탐지→경보 확인 |
| 1 | 발표 자료 — 팀원A 직무 어필 슬라이드 초안 | 4시간 | 초안 완성 |
| 2 | EKF 정확도 그래프 발표 자료 삽입 | 1시간 | 삽입 완료 |
| 2 | Ablation Study 결과 표 발표 자료 삽입 | 1시간 | 삽입 완료 |
| 2 | 최종 보고서 — ECU/보안 섹션 작성 | 6시간 | 초안 완성 |
| 2 | 리허설 2회차 참여 | 2시간 | 피드백 반영 |
| 3 | 최종 보고서 수정 + 완성 | 3시간 | 최종본 제출 |
| 3 | 발표 자료 최종 수정 | 2시간 | 최종본 완성 |
| 3 | 리허설 3회차 (최종) | 2시간 | 발표 준비 완료 |

### 수행 과정

#### 1. 데모 시나리오 참여 (1주차)

**시나리오 A — 정상 동작 (팀원A 역할):**
1. Node A ECU 실행: `./adaptive_ecu --secoc=on --ids=on`
2. BMS가 SOC/전압/전류/온도를 CAN 0x100으로 주기적 전송 확인
3. 팀원B의 Node B 대시보드에서 실시간 SOC 게이지 표시 확인
4. SOC 저하 시뮬레이션 → Fail-safe 전이 확인:
```bash
# CONSTANT 모드에서 SOC 강제 변경
./adaptive_ecu --secoc=on --ids=on --sensor-mode=CONSTANT --soc=19
# NORMAL → WARNING 전이 → 팀원B 대시보드 경고 확인
```

**시나리오 B — 보안 공격 (팀원A 역할):**
1. SecOC off 상태에서 Spoofing 시연:
```bash
./adaptive_ecu --secoc=off --ids=off &
sudo python3 security/attacks/spoofing_attack.py --channel vcan0 --count 5
# 팀원B IVI에 가짜 SOC=100% 표시됨
```

2. SecOC on 상태에서 공격 차단 시연:
```bash
./adaptive_ecu --secoc=on --ids=off &
sudo python3 security/attacks/spoofing_attack.py --channel vcan0 --count 5
# 차단됨: 팀원B IVI에 영향 없음
```

3. IDS 탐지 시연:
```bash
./adaptive_ecu --secoc=on --ids=on &
sudo python3 security/attacks/flooding_attack.py --channel vcan0 --duration 5
# IDS 탐지 → CAN 0x200 → 팀원B AlertBanner 등장
```

**트러블슈팅 — 데모 당일 하드웨어 장애:**
- vcan0 fallback 데모 준비: 모든 시나리오를 vcan0에서도 실행 가능하게 확인
- 사전 녹화 영상 백업: `ffmpeg` 또는 스마트폰으로 정상 동작 영상 촬영

#### 2. 팀원A 직무 어필 슬라이드 (1주차)

**슬라이드 구성 (4~5장):**

**슬라이드 1: "BSW/CDD — AUTOSAR 기반 CAN 통신 계층"**
- 핵심 메시지: SocketCAN raw socket으로 AUTOSAR CDD 계층 직접 구현
- 보여줄 것: 추상 인터페이스 설계 (can_driver.h), Mock 교체 호환성
- 수치: TC-BSW-001~005 전체 통과, 멀티스레드 안전성 검증

**슬라이드 2: "BMS — EKF SOC 추정기"**
- 핵심 메시지: Extended Kalman Filter로 배터리 잔량 추정, 쿨롱 카운팅 대비 정확도 우위
- 보여줄 것: EKF 정확도 그래프 (`ekf_accuracy.png`)
- 수치: RMSE EKF vs 쿨롱 카운팅, SOC 오차 ≤0.5% (TC-BMS-001)

**슬라이드 3: "SecOC — HMAC-SHA256 CAN 인증"**
- 핵심 메시지: Python 프로토타입 → C++ 이식, Timing-safe 비교
- 보여줄 것: 인증 플로우 다이어그램 (ICD §6.1)
- 수치: Spoofing/Replay 차단율 (Ablation Config 2)

**슬라이드 4: "IDS — ML 기반 CAN 침입 탐지"**
- 핵심 메시지: Isolation Forest로 이상 탐지, 7차원 특징 벡터
- 보여줄 것: ROC 커브 (`roc_curve.png`)
- 수치: 탐지율 ≥90%, 오탐율 ≤5% (TC-SEC-006)

**슬라이드 5: "Ablation Study — 방어 효과 정량 분석"**
- 핵심 메시지: 3 Config x 4 Attack x 100회 = 1,200회 실험으로 방어 효과 입증
- 보여줄 것: Ablation 결과 표 + 막대 그래프 (`ablation_success_rate.png`)
- 수치: Config 1 → 3 공격 성공률 변화

**각 슬라이드 핵심 토킹 포인트:**

| 슬라이드 | 토킹 포인트 (30초) |
|---------|-------------------|
| BSW/CDD | "SocketCAN raw socket으로 AUTOSAR CDD를 직접 구현했습니다. 추상 인터페이스 설계로 Mock 교체가 가능하여 하드웨어 없이도 단위 테스트를 수행할 수 있었습니다." |
| BMS EKF | "Extended Kalman Filter로 배터리 SOC를 추정합니다. 쿨롱 카운팅 대비 RMSE가 X% 낮아 장시간 운행에서 누적 오차가 적습니다." |
| SecOC | "HMAC-SHA256 기반 메시지 인증으로 위변조 공격을 차단합니다. Python으로 프로토타입한 뒤 C++로 이식하여 교차 검증을 수행했습니다." |
| IDS | "Isolation Forest 기반 이상 탐지로 Flooding, Fuzzy 공격을 실시간 탐지합니다. 탐지율 90% 이상, 오탐율 5% 이하를 달성했습니다." |
| Ablation | "방어 없음, SecOC만, SecOC+IDS 3가지 구성으로 총 1,200회 실험을 수행했습니다. SecOC로 위변조를 차단하고 IDS로 DoS를 탐지하는 결합 방어의 효과를 정량적으로 입증했습니다." |

#### 3. 그래프/표 삽입 (2주차)

발표 자료에 삽입할 파일 목록:
1. `results/ekf_accuracy.png` — EKF vs 쿨롱 카운팅 비교
2. `results/ablation_success_rate.png` — 공격 성공률 비교 막대 그래프
3. `results/ablation_detection_rate.png` — IDS 탐지율 그래프
4. `results/roc_curve.png` — ROC 커브
5. Ablation 결과 요약 표 (Config x Attack 매트릭스)

**고해상도 그래프 재생성 (발표용):**
```bash
cd security
source venv/bin/activate

# DPI 300으로 재생성
python3 plot_ablation.py  # 내부에서 dpi=300으로 수정
python3 plot_ekf.py       # 내부에서 dpi=300으로 수정
python3 analyze_roc.py    # 내부에서 dpi=300으로 수정
```

#### 4. 최종 보고서 — ECU/보안 섹션 (2~3주차)

**팀원A 담당 보고서 섹션:**

1. **ECU 하드웨어 구성** (1페이지)
   - RPi4 사양, MCP2515 CAN 인터페이스, ADS1115 ADC

2. **BSW 설계 및 구현** (2~3페이지)
   - CAN CDD 구현 (SocketCAN raw socket)
   - ara::com Publisher/Subscriber 패턴
   - Watchdog Manager

3. **BMS 구현** (3~4페이지)
   - EKF SOC 추정기 (알고리즘, 파라미터, 정확도)
   - SOH 추정기
   - Fail-safe 상태 머신

4. **보안 모듈** (3~4페이지)
   - SecOC HMAC-SHA256 (설계, 구현, 검증)
   - IDS Isolation Forest (모델, 특징 벡터, 성능)

5. **Ablation Study** (3~4페이지)
   - 실험 설계 (3 Config x 4 Attack)
   - 실험 결과 (표 + 그래프)
   - 분석 및 결론

6. **TARA 요약** (1~2페이지)
   - 위협 분석 주요 발견
   - Risk Level 판정 결과

**작성 팁:**
- SDD-ECU.md 내용을 보고서 형식으로 재구성 (중복 작성 방지)
- 그래프와 표는 M6에서 생성한 것을 그대로 재사용
- 실험 결과 수치는 `results_summary.csv`에서 직접 인용

#### 5. 리허설 (2~3주차)

**리허설 체크리스트:**
- [ ] 리허설 1회차: 데모 시나리오 A/B 정상 동작 확인
- [ ] 리허설 2회차: 발표 시간 측정 (팀원A 파트 5~7분 목표)
- [ ] 리허설 3회차: 최종 리허설, Q&A 예상 질문 준비

**예상 질문 + 답변 준비:**

| 질문 | 답변 핵심 |
|------|----------|
| EKF 파라미터를 어떻게 결정했나요? | NASA 배터리 데이터에서 OCV-SOC 다항식 피팅, Q/R은 그리드 서치로 최적화 |
| SecOC MAC 4바이트로 충분한가요? | 차량 CAN은 DLC=8바이트 제약, 4B MAC은 2^32 brute force 필요 → 100ms 주기 감안 시 실용적 |
| IDS 오탐률을 어떻게 관리하나요? | contamination 파라미터 + ROC 커브 분석으로 TPR≥90% AND FPR≤5% 만족점 선택 |
| Ablation Study 재현성은? | random_state=42, CPU governor=performance, 12세트 재실행 편차 ≤5% 검증 |

---

## 부록 A: 월별 총 예상 시간 요약

| 월 | 예상 시간 | 주요 산출물 |
|----|----------|-----------|
| M1 (6월) | 16~20시간 | RPi4 환경, CAN loopback, can_driver.h, ICD.md 초안, ADR 초안 |
| M2 (7월) | 29~32시간 | MockCanDriver, can_cdd.cpp, Publisher, SensorSimulator, NASA 데이터 |
| M3 (8월) | 38~44시간 | EKF SOC, Fail-safe FSM, SecOC (Python+C++), Watchdog, 단위 테스트 |
| M4 (9월) | 24~28시간 | IDS 모델, Fuzzy/Flooding 공격, ids_alerter, TARA v1 |
| M5 (10월) | 37~42시간 | Replay/Spoofing 공격, Ablation 1,200회, ROC 분석, ADR 최종화 |
| M6 (11월) | 34~38시간 | Ablation 그래프, EKF 그래프, SDD-ECU.md, TARA.md 최종화 |
| M7 (12월) | 31~36시간 | Ablation 재현성 검증, 보완 실험, 실험 보고서, how_to_train.md |
| M8 (1월) | 25~29시간 | 데모 참여, 직무 어필 슬라이드, 보고서 ECU/보안 섹션, 리허설 |

**8개월 총 예상: 약 234~269시간** (주당 약 7~8시간)

---

## 부록 B: 파일 경로 종합

### C++ (adaptive_ecu/)

| 파일 | 경로 | 구현 시점 |
|------|------|-----------|
| `can_driver.h` | `include/` | M1 |
| `publisher.h` / `subscriber.h` | `include/` | M1~M2 |
| `mock_can_driver.cpp` | `src/bsw/` | M2 |
| `can_cdd.cpp` | `src/bsw/` | M2 |
| `can_publisher.cpp` | `src/bsw/` | M2 |
| `sensor_simulator.cpp` | `src/app/` | M2 |
| `ekf_soc_estimator.h/.cpp` | `include/` + `src/app/` | M3 |
| `soh_estimator.cpp` | `src/app/` | M3 |
| `failsafe_sm.h/.cpp` | `include/` + `src/app/` | M3 |
| `secoc_module.h/.cpp` | `include/` + `src/bsw/` | M3 |
| `watchdog_manager.cpp` | `src/bsw/` | M3 |
| `bms_component.cpp` | `src/app/` | M2~M3 |
| `main.cpp` | `adaptive_ecu/` | M3 |

### Python (security/)

| 파일 | 경로 | 구현 시점 |
|------|------|-----------|
| `secoc_module.py` | `security/` | M3 |
| `collect_normal.py` | `security/` | M4 |
| `train_model.py` | `security/` | M4 |
| `fuzzy_attack.py` | `attacks/` | M4 |
| `flooding_attack.py` | `attacks/` | M4 |
| `replay_attack.py` | `attacks/` | M5 |
| `spoofing_attack.py` | `attacks/` | M5 |
| `ids_alerter.py` | `ids/` | M4 |
| `ids_engine.py` | `ids/` | M4 |
| `run_ablation.sh` | `security/` | M5 |
| `merge_results.py` | `security/` | M5 |
| `verify_reproducibility.py` | `security/` | M7 |
| `plot_ablation.py` | `security/` | M6 |
| `plot_ekf.py` | `security/` | M6 |
| `analyze_roc.py` | `security/` | M5 |
| `how_to_train.md` | `ids/` | M7 |
| `results_summary.csv` | `ids/` | M7 |

### 테스트

| 테스트 파일 | TC ID | 구현 시점 |
|------------|-------|-----------|
| `test/test_can_cdd.cpp` | TC-BSW-001~003 | M2 |
| `test/test_publisher.cpp` | TC-BSW-004~005 | M2 |
| `test/test_sensor_simulator.cpp` | TC-BSW-008 | M2 |
| `test/test_ekf_soc.cpp` | TC-BMS-001~002 | M3 |
| `test/test_bms_component.cpp` | TC-BMS-003, 005~007 | M3 |
| `test/test_failsafe_sm.cpp` | TC-BMS-004 | M3 |
| `test/test_watchdog_manager.cpp` | TC-BSW-006~007 | M3 |
| `test/test_secoc.cpp` | TC-SEC-001~004 | M3 |
| `tests/test_attack_simulator.py` | TC-SEC-005 | M4~M5 |
| `tests/test_ids_engine.py` | TC-SEC-006 | M4 |
| `tests/test_ids_alerter.py` | TC-SEC-007 | M4 |
