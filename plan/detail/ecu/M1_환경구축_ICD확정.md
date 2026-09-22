# ECU M1 — 환경 구축과 ICD 확정

> **예시 상태**: 코드·명령은 별도 검증 표시가 없으면 작성 골격·예정 절차다. 실행 전 생성할 파일·의존성·플랫폼을 확인한다. [공동 규약](../common/00_협업_규약.md)의 문서·예시 사용 규칙을 따른다.

> 상위 계획: [ECU.md](../../ECU.md) · 공동 절차: [00_협업_규약](../common/00_협업_규약.md) · 인계: [01_연계_의존성](../common/01_연계_의존성.md)
> 원본: `_archive/ECU.md` M1, `_archive/ECU_최종_실행계획서.md` §5

---


<a id="security-integration"></a>
## 현행 과제에 병합한 보안 수행·인수 조건 — Q2 수신 환경 준비

이 절은 2026-09-09 보안 상세 계획을 기존 단계에 반영한 실행 조건이다. 초기 보안 보강 절과 함께 적용하며 제품 실행 완료 기록은 아니다. 상세 규칙은 [메시지·상태 규약](../../../docs/development/security/인증이벤트_메시지_상태규약.md)과 [송신·큐·실패 정책](../../../docs/development/security/인증이벤트_메시지_상태규약.md#planning-final)을 참조한다.

**선행 조건:** 대상 Ubuntu·Python/OpenSSL·적용 profile을 확인하고 IVI M1의 제공 환경과 대조한다. 현재 PC의 TLS 지원 보고를 Node A 장비 인수로 사용하지 않는다.

**수행:** 허용 peer·인증서 신원 매핑, 제한된 listener와 키 읽기 권한을 준비한다. 유선 IP+상호 TLS를 우선안으로 검토하고 정상/잘못된 인증서·재시작의 플랫폼 확인 절차를 기존 환경 점검에 포함한다.

**실패 대응·인계:** 버전·설정 식별·비밀을 제외한 연결 결과를 공동 인계에 제출한다. 지원 불가 시 원인과 대안을 보고하고 평문 전환하지 않는다. 실제 코드가 없는 상태의 모형 검증은 독립 수행 가능하다.

**완료 확인:**

- [ ] 대상 환경·신원/권한 정책·적용 가능/불가 증거를 인계했다.
- [ ] 기존 공식 시험 결과와 추가 보조 시나리오의 실제 증거·미검증 사유를 구분했다.


## 1. 목적과 범위

Node A RPi4에 Ubuntu 22.04와 CAN 인터페이스(MCP2515 물리 또는 `vcan0` 가상)를 준비하고, C++17 빌드 도구와 GoogleTest를 검증한다. `adaptive_ecu/`·`security/` 골격과 핵심 인터페이스 헤더를 확보하고, IVI 담당자와 `docs/ICD.md`를 확정한다.

| 항목 | 값 |
|---|---|
| 연결 요구사항 | FR-BSW-001~007 (CAN 추상화), FR-BMS 골격 |
| 연결 시험 | TC-BSW-001 (M2에서 실행), 본 단계는 환경 sanity |
| 산출물 | CAN 인터페이스 UP, `adaptive_ecu/` 빌드 성공, `can_driver.h`/`publisher.h`/`subscriber.h`, ICD 확정, SRS/ADR 초안 |
| 태그 | `v0.1.0` |

### 주차별 작업

| 주차 | ECU 작업 | 공동/IVI 연계 |
|---|---|---|
| 1주차 | Ubuntu, SSH, MCP2515, CAN loopback | GitHub develop, branch protection, labels ([00_협업_규약](../common/00_협업_규약.md)) |
| 2주차 | CMake/GCC/GTest, 디렉토리 골격 | IVI `IVehicleHal.hal` 초안과 CAN 구조 공유 |
| 3주차 | `can_driver.h`, `publisher.h`, `subscriber.h` | ICD CAN ID/byte layout 리뷰 |
| 4주차 | SRS/ADR 초안, M1 검증 | ICD 확정 미팅, `v0.1.0` |

---

## 2. 선행조건과 현재 구현 상태

**선행조건**: RPi4 Model B 8GB, SanDisk microSD 128GB, 리더기, 이더넷 또는 Wi-Fi, MCP2515-I/SO+TJA1050 8MHz 모듈, 4채널 양방향 레벨 컨버터 2개, 브레드보드, 점퍼선.

**현재 구현 상태 (확인 기준일 2026-09-05, 실제 파일 확인)**

| 대상 | 상태 | 근거 |
|---|---|---|
| `adaptive_ecu/include/can_driver.h` | **구현됨** | `CanFrame{uint32_t id; uint8_t dlc; std::array<uint8_t,8> data;}` + `CanDriver` 순수 가상 6종 |
| `adaptive_ecu/include/publisher.h` | **구현됨** | `Publisher<T>`, `std::mutex` 보호 + 스냅샷 후 콜백 호출 |
| `adaptive_ecu/include/subscriber.h` | **구현됨** | — |
| `adaptive_ecu/CMakeLists.txt` | **구현됨(초안 초과)** | `cmake_minimum_required(3.22)`, `ecu_core` 라이브러리, `ECU_BUILD_TESTS`/`ENABLE_COVERAGE` 옵션, `OpenSSL::Crypto`·`Threads` 링크 |
| `adaptive_ecu/data/battery_profile.csv` | **존재** | 원 계획의 루트 `data/`가 아니라 `adaptive_ecu/data/`에 있음 |
| `docs/ICD.md`, `docs/SRS.md`, `docs/ADR.md` | **존재** | 초안이 아니라 확정본 형태. 아래 3.7~3.8은 재확인 작업으로 수행 |
| RPi4 Ubuntu / MCP2515 / `can0` | **보유 사양·배선 확인, 동작 미검증** | RPi4 8GB·MCP2515-I/SO+TJA1050 8MHz·레벨 컨버터 2개 배선은 확인. OS 부팅·`can0` 검출·CAN 송수신은 실장비에서 확인 |

> 이 표는 소스 파일의 존재를 뜻하며 시험 통과나 하드웨어 동작을 뜻하지 않는다. 3장은 "새로 작성"이 아니라 **현재 파일 확인 → 차이 보완** 순서로 수행한다.

### 통합 시 해소한 충돌

| 항목 | 세대A | 세대B | 채택 |
|---|---|---|---|
| `CanFrame.data` 타입 | `uint8_t data[8]` | `std::array<uint8_t,8>` | **세대B** — 실제 `can_driver.h`와 일치 |
| MCP2515 VCC | Pin 2 (5V) 고정 | 3.3V 또는 5V, 모듈 사양 확인 | **실물 확정** — TJA1050 모듈 VCC/HV 5V, RPi/LV 3.3V, SPI/INT 전 신호 레벨 변환 |
| CMake 최소 버전 | 3.25 | 3.25 | **실제 3.22** — 3.25 설치는 3.4의 선택 절차로 유지 |

---

## 3. 수행 절차

### 3.1 RPi4 Ubuntu 22.04 설치와 SSH

- [ ] Raspberry Pi Imager(<https://www.raspberrypi.com/software/>)로 설치
- [ ] CHOOSE OS → Other general-purpose OS → Ubuntu → **Ubuntu Server 22.04.x LTS (64-bit)**
- [ ] CHOOSE STORAGE → microSD 선택
- [ ] 설정(톱니바퀴): hostname `node-a`, SSH 활성화(password), username/password, Wi-Fi(해당 시)
- [ ] WRITE → microSD 삽입 → 전원 연결

```bash
ssh <username>@<RPi4-IP>
uname -a
# 기대: Linux node-a 5.15.x-raspi #1 SMP ... aarch64 ... GNU/Linux
```

### 3.2 MCP2515 배선과 SocketCAN

> 아래 핀과 8MHz 설정은 사용자 제공 실물 사진과 [기존 배선표](../../../하드웨어%20정보/컨버터O_배선완결판.html)에서 확인했다. 보유 확인은 동작 검증이 아니므로 전원 인가 전 HV/LV·GND·단락을 확인하고 저속 SPI 초기화부터 검증한다. Node B도 Qt Plan B의 Linux 대상이지만 선택 이미지·커널·부팅 경로를 별도 확인한다. Node A 설정을 확인 없이 복사하지 않는다.

| MCP2515 핀 | RPi4 GPIO 핀 | 설명 |
|---|---|---|
| VCC | Pin 2의 5V를 브레드보드 전원 레일로 분배 | MCP2515 VCC와 LC#1·LC#2 HV에 5V |
| GND | Pin 6 (GND) | 공통 접지 |
| CS | Pin 24 (GPIO 8, CE0) → LC#1 LV3/HV3 | SPI chip select |
| SO | LC#1 HV4/LV4 → Pin 21 (GPIO 9, MISO) | SPI MISO |
| SI | Pin 19 (GPIO 10, MOSI) → LC#1 LV2/HV2 | SPI MOSI |
| SCK | Pin 23 (GPIO 11, SCLK) → LC#1 LV1/HV1 | SPI clock |
| INT | LC#2 HV1/LV1 → Pin 22 (GPIO 25) | interrupt |

LC#1 LV는 Pin 1, LC#2 LV는 Pin 17의 3.3V에 연결한다. 두 컨버터와 MCP2515는 공통 GND를 사용한다. 한 노드에 컨버터 2개를 사용하며 전체 보유 5개 중 Node A·B에 4개를 배치하고 1개는 예비로 둔다.

```bash
sudo nano /boot/firmware/config.txt
```

파일 끝에 추가:

```text
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25
# 16MHz 크리스탈이면 oscillator=16000000
```

```bash
sudo reboot
dmesg | grep -i mcp
# 기대: "MCP2515 successfully initialized"

sudo ip link set can0 up type can bitrate 500000
ip link show can0
# 기대: ... state UP ... qlen 10
```

Loopback 테스트:

```bash
sudo ip link set can0 down
sudo ip link set can0 up type can bitrate 500000 loopback on
candump can0 &
cansend can0 100#DEADBEEF
# 기대: can0  100   [4]  DE AD BE EF
kill %1
```

### 3.3 CAN 부팅 시 자동 실행

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

ip link show can0
ip link show vcan0
# 기대: 둘 다 ... state UP ...
```

### 3.4 빌드 도구와 GoogleTest

```bash
sudo apt update
sudo apt install -y build-essential gcc-12 g++-12 git can-utils \
  pkg-config libssl-dev lcov cppcheck python3 python3-venv python3-pip \
  libgtest-dev cmake

sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-12 100
sudo update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-12 100
```

`libgtest-dev`가 정적 라이브러리를 설치하지 않는 배포판이면:

```bash
cd /usr/src/gtest && sudo cmake . && sudo make && sudo cp lib/*.a /usr/lib/
cd ~
```

버전 확인:

```bash
cmake --version   # 기대: 3.22 이상 (현재 CMakeLists 요구는 3.22)
gcc --version     # 기대: gcc (Ubuntu 12...) 12.x.x
g++ --version     # 기대: g++ (Ubuntu 12...) 12.x.x
cansend --help    # 기대: Usage: cansend <device> <can_frame>
```

**(선택) CMake 3.25+ 로 올리기** — 상위 버전 기능이 필요할 때만:

```bash
wget https://github.com/Kitware/CMake/releases/download/v3.28.1/cmake-3.28.1-linux-aarch64.sh
chmod +x cmake-3.28.1-linux-aarch64.sh
sudo ./cmake-3.28.1-linux-aarch64.sh --prefix=/usr/local --skip-license
```

GoogleTest sanity 확인:

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
cmake_minimum_required(VERSION 3.22)
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
# 기대:
# [==========] Running 1 test from 1 test suite.
# [  PASSED  ] 1 test.
# 100% tests passed, 0 tests failed

cd ~ && rm -rf ~/gtest-verify
```

### 3.5 프로젝트 골격 확인

현재 저장소에는 아래 구조가 이미 있다. 없는 항목만 생성한다.

```text
adaptive_ecu/
├── include/          # 헤더 (can_driver.h, publisher.h, subscriber.h, ...)
├── src/bsw/          # BSW (can_cdd, can_publisher, mock_can_driver, secoc_module, watchdog_manager)
├── src/app/          # App (ekf_soc_estimator, failsafe_sm, sensor_simulator, soh_estimator)
├── test/             # GoogleTest 단위 시험 13종
├── data/             # battery_profile.csv
├── CMakeLists.txt
└── main.cpp
security/
├── attacks/          # traffic_gen.py
├── ids/              # feature_extractor, if_detector, rule_baseline, spec_detector
├── analysis/         # measure_can_secoc.py
├── experiments/      # run_eval.py
└── tests/            # pytest
```

```bash
cd ~/Capstone-proj
ls adaptive_ecu/include adaptive_ecu/src/bsw adaptive_ecu/src/app adaptive_ecu/test
ls security/ids security/attacks security/tests
```

### 3.6 핵심 인터페이스 헤더 확인

`adaptive_ecu/include/can_driver.h` — 현재 내용이 아래와 일치하는지 확인한다. 다르면 ICD 영향을 먼저 판단한다.

```cpp
#pragma once

#include <array>
#include <cstdint>
#include <functional>
#include <string>

struct CanFrame {
    uint32_t id = 0;
    uint8_t dlc = 0;
    std::array<uint8_t, 8> data{};
};

using CanCallback = std::function<void(const CanFrame&)>;

class CanDriver {
public:
    virtual ~CanDriver() = default;
    virtual bool open(const std::string& interface_name) = 0;
    virtual void close() = 0;
    virtual bool send(const CanFrame& frame) = 0;
    virtual void registerCallback(CanCallback callback) = 0;
    virtual void startReceive() = 0;
    virtual void stopReceive() = 0;
};
```

컴파일 확인:

```bash
echo '#include "can_driver.h"' > /tmp/test_include.cpp
g++ -std=c++17 -I adaptive_ecu/include -c /tmp/test_include.cpp -o /dev/null
# 에러 없으면 성공
```

`publisher.h`는 `std::mutex`로 구독자 목록을 보호하고 콜백 호출 전 스냅샷을 뜬다. 동시성 조건을 바꾸면 `test_publisher`, `test_can_publisher`를 함께 확인한다.

### 3.7 ICD 확정 (3주차)

`docs/ICD.md`에서 아래를 IVI 담당자와 함께 검토하고 확정한다. **값은 여기 복제하지 않고 ICD를 직접 읽는다.**

1. CAN 메시지 ID 5종: `0x100` BMS_Status, `0x101` BMS_FailSafe, `0x102` BMS_SecOC, `0x103` FailSafe_SecOC, `0x200` IDS_Alert
2. 각 ID의 바이트 레이아웃·스케일·엔디언 (ICD §1.2~1.5)
3. SecOC 프로토콜: HMAC-SHA256, 절단 MAC 4B, 롤링 카운터 (ICD §1.4)
4. HAL API: `IVehicleHal`, `IVehicleHalCallback`, `VehicleData` (ICD HAL 절)

- [ ] IVI 담당자에게 `CanFrame` 구조와 `0x100` 예시 payload를 공유한다.
- [ ] HAL 타입이 `uint8`, `uint16 BE`, `uint32 BE`와 일치하는지 확인한다.
- [ ] 변경이 필요하면 `interface-change` 게이트를 따른다 ([00_협업_규약](../common/00_협업_규약.md)).

### 3.8 SRS / ADR 확인 (4주차)

- [ ] `docs/SRS.md`: FR-BSW-001~007, FR-BMS-001~008, FR-SEC-001~007이 현재 구현 범위와 맞는지 확인
- [ ] `docs/ADR.md` ADR-001 SocketCAN 선택 근거 (vs PEAK PCAN, vs CANopen)
- [ ] `docs/ADR.md` ADR-002 HMAC-SHA256 선택 근거 (vs AES-CMAC, vs RSA)

---

## 4. 검증 명령과 합격 기준

```bash
# CAN 인터페이스
ip link show can0
ip link show vcan0
candump vcan0 &
cansend vcan0 100#DEADBEEF
kill %1

# 빌드와 시험 (AGENTS Verification Baseline)
cmake -S adaptive_ecu -B adaptive_ecu/build -DECU_BUILD_TESTS=ON
cmake --build adaptive_ecu/build
ctest --test-dir adaptive_ecu/build --output-on-failure
```

| 기준 | 합격 조건 |
|---|---|
| CAN 송수신 | `can0` 또는 `vcan0`에서 `cansend`→`candump` 수신 확인 |
| 빌드 | `cmake --build` 에러 0 |
| 헤더 | `can_driver.h`, `publisher.h`, `subscriber.h` 컴파일 성공 |
| 시험 | `ctest` 전 항목 통과 (실패 시 해당 M2~M3 상세로 이동) |
| 계약 | ICD CAN ID 5종 IVI와 합의 완료 |
| 문서 | SRS/ADR 관련 절 PR 머지 |

---

## 5. 실패 시 대응과 우회

**MCP2515 인식 실패** — 가장 흔한 순서로 확인한다.

1. `dmesg | grep spi` 로 SPI 인식 여부 확인
2. 크리스탈 주파수 확인: 모듈에 적힌 수치(8MHz vs 16MHz)에 맞게 `oscillator=` 수정
3. GPIO 25번 INT 핀 점퍼선 접촉 불량 확인 (가장 흔한 원인)
4. 그래도 안 되면 **`vcan0`으로 전환해 개발을 계속하고** 하드웨어는 병렬로 디버깅한다

```bash
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan 2>/dev/null || true
sudo ip link set vcan0 up
candump vcan0 &
cansend vcan0 100#DEADBEEF
kill %1
```

`vcan0` 우회는 M4 물리 통합 전까지만 유효하다. 영향 범위는 [01_연계_의존성](../common/01_연계_의존성.md)의 지연 시나리오를 참조한다.

**SSH 접속 실패**
- RPi4 IP 확인: 공유기 관리 페이지 DHCP 할당 목록
- `ping <RPi4-IP>` 실패 시 이더넷 케이블 직접 연결 후 재시도
- 키 충돌 시 `ssh-keygen -R <RPi4-IP>` 후 재접속

**GTest 링크 에러**
- `find /usr -name "libgtest.a" 2>/dev/null` 로 위치 확인
- 없으면 3.4의 수동 빌드 절차 수행

**CMake 버전/아키텍처 오류**
- `file cmake-3.28.1-linux-aarch64.sh` 로 ARM64 바이너리인지 확인
- x86 파일을 받았으면 `aarch64` 파일로 교체. 대안은 `pip install cmake`

---

## 6. 완료 체크리스트

- [ ] `can0` 또는 `vcan0` 송수신 성공
- [ ] 재부팅 후 CAN 인터페이스 자동 UP
- [ ] `cmake`/`gcc`/`g++`/`cansend` 버전 확인 통과
- [ ] GoogleTest sanity 통과
- [ ] `adaptive_ecu/` 빌드 + `ctest` 통과
- [ ] `can_driver.h`, `publisher.h`, `subscriber.h` 컴파일 성공
- [ ] ICD CAN ID 5종 IVI와 합의
- [ ] SRS/ADR 관련 절 PR 머지
- [ ] `v0.1.0` 태그 생성 ([00_협업_규약](../common/00_협업_규약.md) 마일스톤 절차)


<a id="ecu-env-01"></a>
### ECU-ENV-01 — Plan 승계 과제

원문: [ECU.md](../../_archive/plan_20260908/ECU.md.txt)의 ECU-ENV-01. 실행 상태는 해당 역할의 진행 표·공동 인수 기록을 사용한다. 이 병합은 과제 실행 완료가 아니다.

선행·착수: COM-BASE-01의 착수 확인

보존한 수행·인수 조건: 실제 C++17/CMake/OpenSSL/Threads/GoogleTest·Python 환경과 소스/시험/장비 상태를 분리 기록하고 미구현·차단 항목을 다음 과제로 인계한다.

현재 기준 적용: 현재 13종 등록과 실행 미검증 구분; 구 9종 표기는 대체. 본문의 공식 FR/TC·승인 정책·실패 대응을 함께 적용한다.
