# ECU 담당자 최종 실행계획서

> **대상**: 팀원A (Node A — ECU / BSW / BMS / SecOC / IDS 담당자)  
> **기준일**: 2026-05-27  
> **프로젝트**: AUTOSAR 계층 기반 IVI-ECU 통합 플랫폼  
> **역할**: RPi4 Ubuntu 22.04 / C++17 / SocketCAN / BMS / SecOC / Python IDS  
> **기간**: 2026-06 ~ 2027-01 (8개월, M1~M8)  
> **이 문서의 성공 기준**: 이 문서를 위에서 아래로 그대로 따라가면 ECU 담당자의 구현, 검증, 실험, 문서화, IVI 연계, 최종 데모를 완수할 수 있어야 한다.
>
> **원천 문서 우선순위**: `.claude/project-overview.md`, `docs/ROADMAP.md`, `Plan/ECU.md`, `Plan/INDEX.md`, `Plan/공동.md`, `Plan/팀간_연계_분석.md`, `docs/ICD.md`, `docs/SRS.md`, `docs/SDD-ECU.md`, `docs/TEST_PLAN.md`, `docs/ADR.md`, `docs/TARA.md`, `docs/CICD_SPEC.md`

---

## 0. 최종 목표

ECU 담당자는 Node A를 실제 차량 ECU처럼 동작시키고, Node B IVI와 CAN 버스로 end-to-end 통합한다.

- [ ] RPi4 Ubuntu 22.04에서 SocketCAN 기반 ECU 프로세스를 실행한다.
- [ ] `0x100` BMS_Status를 100ms 주기로 송신한다.
- [ ] `0x101` BMS_FailSafe를 상태 전이 이벤트 시 즉시 송신한다.
- [ ] `0x102`, `0x103` SecOC 인증 프레임을 원본 메시지 직후 송신한다.
- [ ] Python IDS가 Fuzzy/Replay/Spoofing/Flooding 공격을 탐지하고 `0x200` IDS_Alert를 송신한다.
- [ ] Ablation Study로 4종 공격 x 3 Config x 100회, 총 1,200회 실험을 수행한다.
- [ ] `docs/SDD-ECU.md`, `docs/TARA.md`, `docs/TEST_PLAN.md`, `docs/ADR.md`에 구현과 실험 결과를 반영한다.
- [ ] 최종 데모, 발표 슬라이드, 보고서, GitHub Release 증적을 완성한다.

### 완료 판정 기준

| 영역 | 완료 기준 |
|---|---|
| CAN | `0x100` 주기 `100ms ±10ms`, `0x101` 이벤트 즉시 송신 |
| BMS | `TC-BMS-001~007` 통과, EKF SOC 오차 핵심 테스트 `≤0.5%`, 최소 프로젝트 기준 `≤3%` |
| Fail-safe | 상태 전이 Branch Coverage `100%` |
| SecOC | Python/C++ 동일 MAC, 변조 및 Replay 차단율 `100%` |
| IDS | 공격별 탐지율 `≥90%`, 정상 오탐율 `≤5%`, 탐지 응답 `≤3초` |
| 통합 | `IT-001~005` 전부 Pass, 공식 `TC-INT-001~004` 결과 기록 |
| 실험 | `security/ids/results_summary.csv`에 1,200개 데이터 row |
| 문서 | SDD-ECU, TARA, TEST_PLAN, ADR, 발표 자료 최신화 |
| 릴리즈 | `v0.1.0~v1.0.0` 태그와 월별 Release 존재 |

### 월별 태그 계획

| 월 | 태그 | Due Date | ECU 핵심 완료 조건 |
|---|---|---:|---|
| M1 | `v0.1.0` | 2026-06-30 | RPi4/CAN 환경, `adaptive_ecu/`, ICD 확정 |
| M2 | `v0.2.0` | 2026-07-31 | CAN CDD, Mock, Publisher, `0x100` 100ms 송신 |
| M3 | `v0.3.0` | 2026-08-31 | EKF, SOH, Fail-safe, Watchdog, SecOC |
| M4 | `v0.4.0` | 2026-09-30 | IDS, 공격 스크립트, 물리 통합, IT-001~005 |
| M5 | `v0.5.0` | 2026-10-31 | Ablation 12세트, IDS 튜닝, ROC |
| M6 | `v0.6.0` | 2026-11-30 | SDD-ECU/TARA 완성, 그래프, Coverage |
| M7 | `v0.7.0` | 2026-12-31 | 재현성, ICD 교차 검토, 최종 성능 |
| M8 | `v1.0.0` | 2027-01-31 | 최종 데모, 발표, 보고서, Release |

---

## 1. 작업 위치와 표준 구조

현재 구현 기준은 다음과 같다.

| 영역 | 표준 경로 | ECU 담당 규칙 |
|---|---|---|
| ECU C++ | `adaptive_ecu/` | BSW, BMS, SecOC C++ 구현 |
| 보안/IDS | `security/` | Python SecOC prototype, IDS, 공격, 실험 |
| IVI | `ivi_platform/` | 팀원B 영역, 단 ICD/검증 연계 필요 |
| 문서 | `docs/` | SDD-ECU, TARA, TEST_PLAN, ADR 갱신 |
| 계획 | `Plan/` | 실행 계획 참조 |
| 임시 산출물 | `tmp/` | 임시 문서, gitignore 대상 |
| legacy stub | `CAR-ECU/` | 신규 구현 루트로 사용하지 않음 |

권장 최종 구조:

```text
adaptive_ecu/
├── include/
│   ├── can_driver.h
│   ├── can_cdd.h
│   ├── publisher.h
│   ├── subscriber.h
│   ├── bms_component.h
│   ├── ekf_soc_estimator.h
│   ├── soh_estimator.h
│   ├── failsafe_sm.h
│   ├── secoc_module.h
│   ├── watchdog_manager.h
│   ├── sensor_simulator.h
│   └── can_publisher.h
├── src/
│   ├── bsw/
│   │   ├── can_cdd.cpp
│   │   ├── can_publisher.cpp
│   │   ├── mock_can_driver.cpp
│   │   ├── secoc_module.cpp
│   │   └── watchdog_manager.cpp
│   └── app/
│       ├── bms_component.cpp
│       ├── ekf_soc_estimator.cpp
│       ├── soh_estimator.cpp
│       ├── failsafe_sm.cpp
│       └── sensor_simulator.cpp
├── test/
├── data/
├── CMakeLists.txt
└── main.cpp

security/
├── secoc_module.py
├── attack_simulator.py
├── collect_normal.py
├── train_model.py
├── run_ablation.sh
├── merge_results.py
├── analyze_roc.py
├── plot_ablation.py
├── plot_ekf.py
├── verify_reproducibility.py
├── attacks/
├── ids/
└── tests/
```

---

## 2. 반드시 지켜야 할 ICD 계약

ECU 담당자는 CAN byte layout, scaling, direction, DLC를 임의로 바꾸면 안 된다. 변경이 필요하면 `interface-change` Issue + PR + 양측 리뷰를 거쳐야 한다.

### 2.1 CAN ID 계약

| CAN ID | 방향 | 메시지 | 주기 | DLC | ECU 담당 작업 |
|---|---|---|---:|---:|---|
| `0x100` | Node A -> Node B | BMS_Status | 100ms | 8 | SOC/SOH/전압/전류/온도 인코딩 |
| `0x101` | Node A -> Node B | BMS_FailSafe | 이벤트 | 8 | Fail-safe 전이 이벤트 인코딩 |
| `0x102` | Node A -> Node B | BMS_SecOC | 100ms | 8 | `0x100` payload MAC + counter |
| `0x103` | Node A -> Node B | FailSafe_SecOC | 이벤트 | 8 | `0x101` payload MAC + counter |
| `0x200` | Node A -> Node B | IDS_Alert | 이벤트 | 8 | IDS 탐지 경보 |

### 2.2 `0x100` BMS_Status

| Byte | 필드 | 타입 | 스케일링 | 구현 규칙 |
|---:|---|---|---|---|
| 0 | SOC | `uint8` | `x 0.5%` | `raw = clamp(round(soc_percent / 0.5), 0, 200)` |
| 1 | SOH | `uint8` | `x 0.5%` | `raw = clamp(round(soh_percent / 0.5), 0, 200)` |
| 2-3 | Voltage | `uint16 BE` | `x 0.01V` | `raw = round(voltage_v / 0.01)` |
| 4-5 | Current | `int16 BE` | `x 0.1A` | 양수=충전, 음수=방전, 2의 보수 |
| 6 | Temperature | `uint8` | offset `+40` | `raw = temp_c + 40` |
| 7 | Reserved | `uint8` | 없음 | 항상 `0x00` |

예시 payload:

```text
SOC=75.0%, SOH=95.0%, Voltage=42.00V, Current=-2.0A, Temp=25°C
0x100 payload = 96 BE 10 68 FF EC 41 00
```

### 2.3 `0x101` BMS_FailSafe

| Byte | 필드 | 값 |
|---:|---|---|
| 0 | PrevState | `0=NORMAL`, `1=WARNING`, `2=CRITICAL`, `3=SHUTDOWN` |
| 1 | NewState | 동일 코드 |
| 2 | Reason | 전이 사유 코드 |
| 3 | SOC_AtEvent | SOC `x 0.5%` raw |
| 4 | Temp_AtEvent | `temp_c + 40` |
| 5-7 | Reserved | `0x00` |

| Reason | 의미 | 전이 |
|---:|---|---|
| `0x01` | SOC < 20% | NORMAL -> WARNING |
| `0x02` | SOC < 5% | WARNING -> CRITICAL |
| `0x03` | Temperature > 55°C | NORMAL -> WARNING |
| `0x04` | Temperature > 60°C | WARNING/CRITICAL -> SHUTDOWN |
| `0x05` | SOC >= 20% and Temperature <= 55°C | WARNING -> NORMAL |
| `0x06` | Manual reset | SHUTDOWN -> NORMAL |

### 2.4 SecOC HMAC

`0x102`, `0x103` layout:

| Byte | 필드 | 타입 | 규칙 |
|---:|---|---|---|
| 0-3 | TruncatedMAC | `uint32 BE` | HMAC-SHA256 앞 4바이트 |
| 4-7 | RollingCounter | `uint32 BE` | 메시지마다 +1, overflow 시 wrap |

```text
HMAC_Input = CAN_ID(2B, BE) || RollingCounter(4B, BE) || Payload(8B)
MAC = HMAC-SHA256(SharedKey, HMAC_Input)
TruncatedMAC = MAC[0:4]
```

키 파일:

```bash
sudo mkdir -p /etc/secoc
openssl rand -out key.bin 32
sudo install -o root -g root -m 400 key.bin /etc/secoc/key.bin
sudo ls -l /etc/secoc/key.bin
# 기대: -r-------- 1 root root 32 ... /etc/secoc/key.bin
```

### 2.5 `0x200` IDS_Alert

| Byte | 필드 | 타입 | 규칙 |
|---:|---|---|---|
| 0 | AttackType | `uint8` | `0=None`, `1=Fuzzy`, `2=Replay`, `3=Spoofing`, `4=Flooding` |
| 1 | AnomalyScore | `uint8` | `score x 0.01`, 범위 `0.00~2.55` |
| 2-3 | SuspectCANID | `uint16 BE` | 없으면 `0xFFFF` |
| 4-7 | Timestamp | `uint32 BE` | Unix epoch seconds 하위 32비트 |

---

## 3. 공통 작업 방식

### 3.1 브랜치와 PR

```bash
git switch develop
git pull origin develop
git switch -c feat/ecu-m2-can-cdd

# 작업 후
git status
git add adaptive_ecu security docs
git commit -m "feat(ecu): implement CAN CDD and BMS status publisher"
git push -u origin feat/ecu-m2-can-cdd
# GitHub: base=develop, compare=feat/ecu-m2-can-cdd, 팀원B 리뷰 요청
```

| 작업 | 라벨 |
|---|---|
| ECU 기능 | `feat`, `ECU` |
| 보안 | `feat`, `ECU`, `security` |
| 버그 | `bug`, `ECU` |
| 테스트 | `test`, `ECU` |
| 문서 | `docs`, `ECU` |
| ICD 변경 | `interface-change`, `docs`, `ECU`, `IVI` |
| 블로커 | `blocked` (다른 이슈/PR에 의존하여 진행 불가) |

### 3.2 커밋 메시지 컨벤션

```text
<type>(<scope>): <한 줄 요약>
```

| type | 상황 | scope 예시 |
|---|---|---|
| `feat` | 새 기능 | `bsw` `bms` `secoc` `ids` |
| `fix` | 버그 수정 | |
| `test` | 테스트 추가/수정 | |
| `docs` | 문서 수정 | |
| `chore` | 빌드·CI 변경 | |
| `refactor` | 동작 변경 없는 정리 | |

### 3.3 PR 본문 템플릿

```markdown
## 변경 내용
- 구현한 것을 bullet로 나열

## 완료 기준 확인
- [ ] 단위 테스트 통과 (TC-XXX)
- [ ] cppcheck 오류 0건
- [ ] 관련 문서(ICD/SDD/ADR) 업데이트 여부 확인

## 관련 Issue
Closes #이슈번호
```

머지 조건: 상대방 Approve 1개 이상 + CI 전체 통과. `feature/*` → `develop`은 **Squash Merge**, `develop` → `main`은 **Merge Commit**.

### 3.4 매월 마일스톤 완료 절차

```bash
# A. develop -> main PR은 GitHub 웹에서 생성
# base: main, compare: develop, title: "MN: 완료 내용 요약"

# B. main 최신화 후 tag
git switch main
git pull origin main
git tag -a v0.N.0 -m "MN: 완료 내용 요약"
git push origin v0.N.0

# C. GitHub Issues -> Milestones -> MN -> Close
# D. GitHub Releases -> Draft a new release -> tag v0.N.0
```

### 3.5 통합 테스트 이름 매핑

| 프로젝트 시나리오 | 공식 TEST_PLAN ID | 의미 |
|---|---|---|
| `IT-001` | `TC-INT-001` | Node A `0x100` -> Node B dashboard |
| `IT-002` | `TC-INT-003` | Fail-safe event -> Node B full-screen alert |
| `IT-003` | `TC-INT-002` | 정상 SecOC 인증 end-to-end |
| `IT-004` | `TC-INT-002` | 변조 MAC 폐기 |
| `IT-005` | `TC-INT-004` | Flooding -> IDS -> `0x200` -> AlertBanner |

---

## 4. 지금 당장 할 일 (M1 시작 전 착수 즉시)

M1 정식 시작 전에 반드시 완료해야 할 항목이다.

| 담당 | 작업 |
|---|---|
| 팀원A | RPi4 Ubuntu 22.04 Server 이미지 굽기 + SSH 접속 확인 |
| 공동 | GitHub `develop` 브랜치 생성 + push |
| 공동 | `main` / `develop` 브랜치 보호 규칙 설정 (PR 필수, Force push 차단) |
| 공동 | 팀원 collaborator 초대 |
| 공동 | GitHub Milestones M1~M8 생성, Labels 생성 |
| 공동 | 디렉토리 골격 PR 생성 (`adaptive_ecu/`, `ivi_platform/`, `security/`, `docs/`) |

---

## 5. M1 (6월) — 환경 구축 + ICD 확정

### 목표

Node A RPi4 환경을 준비하고, SocketCAN 또는 `vcan0`으로 CAN 송수신을 검증한다. `adaptive_ecu/`, `security/` 골격과 핵심 인터페이스를 만들고, IVI 담당자와 ICD를 확정한다.

### 주차별 작업

| 주차 | ECU 작업 | 공동/IVI 연계 |
|---|---|---|
| 1주차 | Ubuntu, SSH, MCP2515, CAN loopback | GitHub develop, branch protection, labels |
| 2주차 | CMake/GCC/GTest, 디렉토리 골격 | IVI `IVehicleHal.hal` 초안과 CAN 구조 공유 |
| 3주차 | `can_driver.h`, `publisher.h`, `subscriber.h` | ICD CAN ID/byte layout 리뷰 |
| 4주차 | SRS/ADR 초안, M1 검증 | ICD 확정 미팅, `v0.1.0` |

### 관련 파일

| 파일 | 목적 |
|---|---|
| `adaptive_ecu/include/can_driver.h` | CAN 추상 인터페이스 |
| `adaptive_ecu/include/publisher.h` | ara::com-like publisher |
| `adaptive_ecu/include/subscriber.h` | subscriber 초안 |
| `adaptive_ecu/CMakeLists.txt` | C++ 빌드 |
| `docs/ICD.md` | CAN/SecOC/HAL 계약 |
| `docs/SRS.md` | FR-BSW/BMS/SEC 요구사항 |
| `docs/ADR.md` | SocketCAN/HMAC 결정 근거 |

### 세부 수행 절차

#### 5.1 RPi4 Ubuntu 설치와 SSH

- [ ] Raspberry Pi Imager로 Ubuntu Server 22.04.x LTS 64-bit 설치
- [ ] hostname을 `node-a`로 설정
- [ ] SSH 활성화, Wi-Fi 또는 Ethernet 설정
- [ ] 부팅 후 접속 확인

```bash
ssh <username>@<RPi4-IP>
uname -a
# 기대: Linux node-a ... aarch64 GNU/Linux
```

#### 5.2 MCP2515 배선과 SocketCAN

| MCP2515 | RPi4 GPIO | 설명 |
|---|---|---|
| VCC | 3.3V 또는 5V | 모듈 사양 확인 |
| GND | GND | 공통 접지 |
| CS | GPIO8 CE0 | SPI chip select |
| SO | GPIO9 MISO | SPI MISO |
| SI | GPIO10 MOSI | SPI MOSI |
| SCK | GPIO11 SCLK | SPI clock |
| INT | GPIO25 | interrupt |

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
sudo ip link set can0 up type can bitrate 500000
ip link show can0
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

물리 CAN 실패 시 즉시 `vcan0`으로 개발 지속:

```bash
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan 2>/dev/null || true
sudo ip link set vcan0 up
candump vcan0 &
cansend vcan0 100#DEADBEEF
kill %1
```

#### 5.3 CAN 자동 실행

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
```

#### 5.4 빌드 도구와 GoogleTest

```bash
sudo apt update
sudo apt install -y build-essential gcc-12 g++-12 git can-utils \
  pkg-config libssl-dev lcov cppcheck python3 python3-venv python3-pip \
  libgtest-dev cmake

sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-12 100
sudo update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-12 100

cmake --version
gcc --version
g++ --version
cansend --help
```

GoogleTest sanity:

```bash
mkdir -p ~/gtest-verify && cd ~/gtest-verify
nano hello_test.cpp
```

```cpp
#include <gtest/gtest.h>
TEST(SanityCheck, TrueIsTrue) { EXPECT_TRUE(true); }
int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
```

```bash
nano CMakeLists.txt
```

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
mkdir build && cd build
cmake ..
make
ctest --output-on-failure
cd ~ && rm -rf ~/gtest-verify
```

#### 5.5 프로젝트 골격과 핵심 인터페이스

```bash
cd ~/Capstone-proj
mkdir -p adaptive_ecu/include adaptive_ecu/src/bsw adaptive_ecu/src/app adaptive_ecu/test adaptive_ecu/data
mkdir -p security/attacks security/ids security/tests
```

`adaptive_ecu/CMakeLists.txt` 초안:

```cmake
cmake_minimum_required(VERSION 3.25)
project(adaptive_ecu LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(include)
add_executable(adaptive_ecu main.cpp)

find_package(GTest REQUIRED)
enable_testing()
```

`adaptive_ecu/include/can_driver.h`:

```cpp
#pragma once
#include <array>
#include <cstdint>
#include <functional>
#include <string>

struct CanFrame {
    uint32_t id;
    uint8_t dlc;
    std::array<uint8_t, 8> data;
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

컴파일 확인:

```bash
echo '#include "can_driver.h"' > /tmp/test_include.cpp
g++ -std=c++17 -I adaptive_ecu/include -c /tmp/test_include.cpp -o /dev/null
```

### M1 IVI 연계

- [ ] 팀원B에게 `CanFrame` 구조와 `0x100` 예시 payload를 공유한다.
- [ ] `docs/ICD.md`의 CAN ID, byte layout, SecOC input을 같이 리뷰한다.
- [ ] HIDL/HAL 쪽 타입이 `uint8`, `uint16 BE`, `uint32 BE`와 일치하는지 확인한다.

### M1 검증 명령

```bash
ip link show can0
ip link show vcan0
candump vcan0 &
cansend vcan0 100#DEADBEEF
cd adaptive_ecu && mkdir -p build && cd build
cmake ..
make
ctest --output-on-failure
```

### M1 완료 기준

- [ ] `can0` 또는 `vcan0` 송수신 성공
- [ ] `adaptive_ecu/` 기본 빌드 성공
- [ ] `can_driver.h`, `publisher.h`, `subscriber.h` 컴파일 성공
- [ ] ICD CAN ID 5종 팀원B와 합의
- [ ] SRS/ADR 초안 PR 머지
- [ ] `v0.1.0` 태그 생성

---

## 6. M2 (7월) — CAN CDD, Mock, Publisher, BMS 송신

### 목표

Mock과 SocketCAN을 같은 `CanDriver` 인터페이스로 교체 가능하게 만들고, `0x100` BMS_Status를 100ms 주기로 송신한다.

### 주차별 작업

| 주차 | ECU 작업 | IVI 연계 |
|---|---|---|
| 1주차 | `MockCanDriver`, `SensorSimulator::CONSTANT` | HAL Mock에 `0x100` 샘플 제공 |
| 2주차 | SocketCAN CDD, TC-BSW-001~003 | Node B parser test input 공유 |
| 3주차 | `Publisher<T>`, NASA Battery Dataset 다운로드 + CSV 파싱 | Plan A/B 미팅 참여 |
| 4주차 | `CanPublisher`, 100ms 주기, NASA/CALCE 전처리 완료 | `0x100` 해석값 확인 |

### 관련 파일

| 파일 | 테스트 |
|---|---|
| `adaptive_ecu/src/bsw/mock_can_driver.cpp` | TC-BSW-002 |
| `adaptive_ecu/src/bsw/can_cdd.cpp` | TC-BSW-001~003 |
| `adaptive_ecu/include/publisher.h` | TC-BSW-004~005 |
| `adaptive_ecu/src/app/sensor_simulator.cpp` | TC-BSW-008 |
| `adaptive_ecu/src/bsw/can_publisher.cpp` | TC-BMS-007 |
| `adaptive_ecu/src/app/bms_component.cpp` | TC-BMS-005~007 |

### 세부 수행 절차

#### 6.1 MockCanDriver

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
        if (callback_) callback_(frame);
        return opened_;
    }
    void registerCallback(CanCallback cb) override { callback_ = cb; }
    void startReceive() override { receiving_ = true; }
    void stopReceive() override { receiving_ = false; }

    std::vector<CanFrame> sent_frames;

private:
    std::string interface_;
    bool opened_ = false;
    bool receiving_ = false;
    CanCallback callback_;
    std::mutex mtx_;
};
```

#### 6.2 Publisher

```cpp
#pragma once
#include <functional>
#include <mutex>
#include <vector>

template <typename T>
class Publisher {
public:
    using Callback = std::function<void(const T&)>;
    void subscribe(Callback cb) {
        std::lock_guard<std::mutex> lock(mtx_);
        subscribers_.push_back(std::move(cb));
    }
    void send(const T& value) {
        std::vector<Callback> copy;
        {
            std::lock_guard<std::mutex> lock(mtx_);
            copy = subscribers_;
        }
        for (const auto& cb : copy) cb(value);
    }
private:
    std::mutex mtx_;
    std::vector<Callback> subscribers_;
};
```

#### 6.3 `0x100` 인코딩

```cpp
static uint8_t encodePercent(float percent) {
    int raw = static_cast<int>(std::lround(percent / 0.5f));
    return static_cast<uint8_t>(std::clamp(raw, 0, 200));
}

CanFrame encodeBmsStatus(float soc, float soh, float voltage, float current, int temp_c) {
    CanFrame f{};
    f.id = 0x100;
    f.dlc = 8;
    f.data[0] = encodePercent(soc);
    f.data[1] = encodePercent(soh);

    uint16_t v = static_cast<uint16_t>(std::lround(voltage / 0.01f));
    int16_t i = static_cast<int16_t>(std::lround(current / 0.1f));
    f.data[2] = static_cast<uint8_t>((v >> 8) & 0xFF);
    f.data[3] = static_cast<uint8_t>(v & 0xFF);
    f.data[4] = static_cast<uint8_t>((static_cast<uint16_t>(i) >> 8) & 0xFF);
    f.data[5] = static_cast<uint8_t>(static_cast<uint16_t>(i) & 0xFF);
    f.data[6] = static_cast<uint8_t>(std::clamp(temp_c + 40, 0, 255));
    f.data[7] = 0x00;
    return f;
}
```

#### 6.4 100ms 송신

```cpp
while (running) {
    const auto start = std::chrono::steady_clock::now();
    auto sample = simulator.next();
    auto frame = encodeBmsStatus(soc, soh, sample.voltage, sample.current, sample.temperature);
    driver.send(frame);
    std::this_thread::sleep_until(start + std::chrono::milliseconds(100));
}
```

### M2 검증 명령

```bash
cd adaptive_ecu/build
cmake ..
make
ctest -R test_can_cdd --output-on-failure
ctest -R test_publisher --output-on-failure
ctest -R test_sensor_simulator --output-on-failure
ctest -R test_bms_component --output-on-failure

sudo modprobe vcan
sudo ip link add dev vcan0 type vcan 2>/dev/null || true
sudo ip link set vcan0 up
candump -t d vcan0 | head -20
```

### M2 완료 기준

- [ ] TC-BSW-001~005 통과
- [ ] TC-BSW-008 CONSTANT/PROFILE_CSV/RANDOM_WALK 통과
- [ ] TC-BMS-007 `100ms ±10ms` 통과
- [ ] 팀원B가 `0x100` mock payload를 동일하게 파싱
- [ ] `v0.2.0` 태그 생성

---

## 7. M3 (8월) — EKF, Fail-safe, Watchdog, SecOC

### 목표

BMS 핵심 로직과 보안 인증을 완성한다.

### 주차별 작업

| 주차 | ECU 작업 | IVI 연계 |
|---|---|---|
| 1주차 | EKF SOC, SOH | `0x100` 정상 범위 공유 |
| 2주차 | Sensor profile, ADS1115 선택 구현 | parser 경계값 공유 |
| 3주차 | Fail-safe FSM, Watchdog | `0x101` reason code 공유 |
| 4주차 | SecOC Python/C++, vector 공유 | `secoc_verifier.cpp` 기준 제공 |

### 핵심 구현

#### 7.1 EKF 튜닝 기준

- [ ] 전류 단위는 A, 시간은 seconds, capacity는 Ah로 통일한다.
- [ ] 전압 관측값에 과민하면 R을 키운다.
- [ ] SOC 추정이 느리면 R을 줄인다.
- [ ] 누적 오차가 크면 Q를 키운다.
- [ ] 최종 Q/R 값은 `docs/SDD-ECU.md`에 기록한다.

검증:

```bash
cd adaptive_ecu/build
ctest -R test_ekf_soc --output-on-failure
# TC-BMS-001: 100 step 후 이론 SOC와 오차 ≤0.5%
# TC-BMS-002: RMSE_EKF < RMSE_CoulombCounting
```

#### 7.2 Fail-safe 상태 머신

| TC | 입력 | 기대 전이 | Reason |
|---|---|---|---|
| TC-BMS-004-a | SOC=19%, Temp=30, NORMAL | WARNING | `0x01` |
| TC-BMS-004-b | SOC=4%, Temp=30, WARNING | CRITICAL | `0x02` |
| TC-BMS-004-c | SOC=10%, Temp=61, CRITICAL | SHUTDOWN | `0x04` |
| TC-BMS-004-d | SOC=25%, Temp=30, WARNING | NORMAL | `0x05` |
| TC-BMS-004-e | manual reset, SHUTDOWN | NORMAL | `0x06` |
| TC-BMS-004-f | SOC=60%, Temp=30, NORMAL | no transition | none |
| TC-BMS-004-g | SOC=60%, Temp=56, NORMAL | WARNING | `0x03` |

Coverage:

```bash
cd adaptive_ecu/build
cmake .. -DCMAKE_BUILD_TYPE=Debug -DENABLE_COVERAGE=ON
make
ctest -R test_failsafe_sm --output-on-failure
lcov --capture --directory . --output-file cov.info
lcov --extract cov.info '*/failsafe_sm.cpp' --output-file fs.info
genhtml fs.info --output-directory cov_report
# cov_report/index.html에서 Branch Coverage 100% 확인
```

#### 7.3 SecOC Python prototype

```python
import hmac
import hashlib
import struct

def sign_frame(key: bytes, can_id: int, counter: int, payload: bytes) -> bytes:
    assert len(key) == 32
    assert len(payload) == 8
    hmac_input = struct.pack(">HI8s", can_id, counter, payload)
    mac = hmac.new(key, hmac_input, hashlib.sha256).digest()
    return mac[:4] + struct.pack(">I", counter)

def verify_frame(key: bytes, can_id: int, counter: int, payload: bytes, auth: bytes) -> bool:
    expected = sign_frame(key, can_id, counter, payload)[:4]
    return hmac.compare_digest(expected, auth[:4])
```

#### 7.4 ADS1115 하드웨어 센서 모드 (선택)

ROADMAP M3 체크포인트에 포함된 항목이다. ADS1115 I2C ADC를 사용하면 실제 아날로그 전압을 읽어 센서 입력을 대체할 수 있다.

- [ ] RPi4 I2C 활성화: `/boot/firmware/config.txt`에 `dtparam=i2c_arm=on` 추가
- [ ] `sudo reboot` 후 `i2cdetect -y 1`로 0x48 주소 확인
- [ ] `adaptive_ecu/src/app/sensor_simulator.cpp`에 `ADS1115_HARDWARE` 모드 추가

```bash
sudo apt install -y i2c-tools
i2cdetect -y 1
# 기대: 0x48 위치에 디바이스 표시
```

ADS1115 미인식 시 `CONSTANT`/`PROFILE_CSV` 모드로 우선 개발을 지속한다.

#### 7.5 C++ OpenSSL 이식 규칙

- [ ] `find_package(OpenSSL REQUIRED)`를 CMake에 추가한다.
- [ ] `OpenSSL::Crypto`를 링크한다.
- [ ] MAC 비교는 `CRYPTO_memcmp()` 또는 constant-time equivalent를 사용한다.
- [ ] Python vector와 C++ vector가 동일해야 한다.

```cmake
find_package(OpenSSL REQUIRED)
target_link_libraries(adaptive_ecu OpenSSL::Crypto)
```

### M3 검증 명령

```bash
cd adaptive_ecu/build
cmake ..
make
ctest -R test_ekf_soc --output-on-failure
ctest -R test_failsafe_sm --output-on-failure
ctest -R test_watchdog_manager --output-on-failure
ctest -R test_secoc --output-on-failure

cd ../../security
python3 -m venv .venv
. .venv/bin/activate
pip install pytest
python3 -m pytest tests/test_secoc.py -v
```

### M3 완료 기준

- [ ] TC-BMS-001~007 통과
- [ ] TC-BSW-006~007 Watchdog 통과
- [ ] TC-SEC-001~004 통과
- [ ] Python/C++ SecOC vector를 팀원B에게 공유
- [ ] `v0.3.0` 태그 생성

---

## 8. M4 (9월) — IDS, 공격 시뮬레이터, 물리 통합

### 목표

정상 CAN 트래픽을 학습하고, 공격을 탐지하여 `0x200`을 Node B AlertBanner까지 연결한다.

### 세부 수행 절차

#### 8.1 Python 환경

```bash
cd security
python3 -m venv .venv
. .venv/bin/activate
pip install python-can pandas numpy scikit-learn pytest matplotlib joblib scapy
pip freeze > requirements.txt
```

SocketCAN 권한:

```bash
sudo usermod -aG dialout $USER
# 필요 시 Python 실행 명령에 sudo 사용
```

#### 8.2 정상 트래픽 수집

```bash
# Terminal 1
./adaptive_ecu/build/adaptive_ecu --interface vcan0 --secoc=on --ids=off --sensor-mode profile_csv

# Terminal 2
cd security
. .venv/bin/activate
python3 collect_normal.py --channel vcan0 --duration 1800 --output normal_traffic.csv
```

Feature vector 최소 7개:

| Feature | 설명 |
|---|---|
| `id_mean` | 1초 window CAN ID 평균 |
| `id_std` | CAN ID 표준편차 |
| `interval_mean` | 메시지 간격 평균 |
| `interval_std` | 메시지 간격 표준편차 |
| `msg_count` | 1초 메시지 수 |
| `payload_mean` | payload byte 평균 |
| `payload_std` | payload byte 표준편차 |

#### 8.3 IDS 학습

```bash
python3 train_model.py --input normal_traffic.csv --output ids/ids_model.pkl --contamination 0.01
python3 -m pytest tests/test_ids_engine.py -v
```

#### 8.4 공격 스크립트

개별 공격 스크립트 외에 통합 CLI `attack_simulator.py`를 작성하여 터미널 인자로 공격 유형을 선택할 수 있게 한다.

```bash
# 개별 실행
python3 attacks/fuzzy_attack.py --channel vcan0 --count 100
python3 attacks/flooding_attack.py --channel vcan0 --duration 10 --target-id 0x100

# 통합 CLI (ROADMAP 파일 목록 참조)
python3 attack_simulator.py --type fuzzy --channel vcan0 --count 100
```

`ids_alerter.py` 핵심:

```python
import can
import struct
import time

ATTACK_TYPES = {"none": 0, "fuzzy": 1, "replay": 2, "spoofing": 3, "flooding": 4}

def send_alert(bus, attack_type, anomaly_score, suspect_can_id=0xFFFF):
    type_code = ATTACK_TYPES.get(attack_type, 0)
    score_raw = max(0, min(int(round(anomaly_score / 0.01)), 255))
    timestamp = int(time.time()) & 0xFFFFFFFF
    data = struct.pack(">BBHI", type_code, score_raw, suspect_can_id, timestamp)
    msg = can.Message(arbitration_id=0x200, data=data, is_extended_id=False)
    bus.send(msg)
```

#### 8.5 물리 CAN 통합

```bash
# Node B
candump can0

# Node A
cansend can0 100#DEADBEEF

# Node A
candump can0

# Node B
cansend can0 200#CAFEBABE
```

### IT-001~005 수행

| IT | 공식 TC | 절차 | 성공 기준 |
|---|---|---|---|
| IT-001 | TC-INT-001 | Node A ECU 실행 -> Node B dashboard | SOC/전압/전류/온도 표시 |
| IT-002 | TC-INT-003 | SOC 4.5% -> `0x101` | Node B full-screen critical |
| IT-003 | TC-INT-002 | 동일 key로 SecOC on | verify SUCCESS |
| IT-004 | TC-INT-002 | 변조 MAC 주입 | `ERR_HMAC_VERIFY_FAIL`, 데이터 갱신 없음 |
| IT-005 | TC-INT-004 | Flooding -> IDS -> `0x200` | 3초 내 AlertBanner |

### M4 완료 기준

- [ ] TC-SEC-005-a/d 통과
- [ ] TC-SEC-006 IDS 정확도 목표 통과
- [ ] TC-SEC-007 `0x200` 송신 통과
- [ ] IT-001~005 결과 `docs/TEST_PLAN.md` 기록
- [ ] M4 동작 영상 촬영
- [ ] `v0.4.0` 태그 생성

---

## 9. M5 (10월) — Ablation Study

### 목표

4종 공격 x 3 Config x 100회 실험으로 SecOC와 IDS의 효과를 정량화한다.

### 공격/Config 매트릭스

| Config | SecOC | IDS | 목적 |
|---:|---|---|---|
| 1 | off | off | 무방어 baseline |
| 2 | on | off | SecOC 단독 효과 |
| 3 | on | on | SecOC + IDS 계층 방어 |

| 공격 | 스크립트 | 검증 |
|---|---|---|
| Fuzzy | `attacks/fuzzy_attack.py` | ID/payload 랜덤성 |
| Replay | `attacks/replay_attack.py` | payload byte 동일성 |
| Spoofing | `attacks/spoofing_attack.py` | `0x100`, SOC raw=200 |
| Flooding | `attacks/flooding_attack.py` | `≥5,000 msg/sec` |

### 실행 옵션

```bash
./adaptive_ecu --interface vcan0 --secoc=off --ids=off
./adaptive_ecu --interface vcan0 --secoc=on  --ids=off
./adaptive_ecu --interface vcan0 --secoc=on  --ids=on
```

### `run_ablation.sh` 최소 형태

```bash
#!/usr/bin/env bash
set -euo pipefail

CONFIG="$1"
ATTACK="$2"
TRIALS="${3:-100}"
CHANNEL="${CHANNEL:-vcan0}"
OUT_DIR="results"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/config${CONFIG}_${ATTACK}.csv"

case "$CONFIG" in
  1) SECOC=off; IDS=off ;;
  2) SECOC=on; IDS=off ;;
  3) SECOC=on; IDS=on ;;
  *) echo "invalid config"; exit 1 ;;
esac

../adaptive_ecu/build/adaptive_ecu --interface "$CHANNEL" --secoc="$SECOC" --ids="$IDS" &
ECU_PID=$!
sleep 3

echo "config,attack_type,trial,attack_success,blocked,detected,latency_ms,timestamp" > "$OUT"
for i in $(seq 1 "$TRIALS"); do
  START_MS=$(date +%s%3N)
  case "$ATTACK" in
    spoofing) python3 attacks/spoofing_attack.py --channel "$CHANNEL" --count 10 ;;
    replay) python3 attacks/replay_attack.py --channel "$CHANNEL" ;;
    flooding) python3 attacks/flooding_attack.py --channel "$CHANNEL" --duration 3 ;;
    fuzzy) python3 attacks/fuzzy_attack.py --channel "$CHANNEL" --count 50 ;;
    *) echo "invalid attack"; kill "$ECU_PID"; exit 1 ;;
  esac
  sleep 2
  END_MS=$(date +%s%3N)
  LATENCY=$((END_MS - START_MS))
  DETECTED=$(grep -c "ALERT" /tmp/ids_latest.log 2>/dev/null || true)
  echo "$CONFIG,$ATTACK,$i,false,false,$([ "$DETECTED" -gt 0 ] && echo true || echo false),$LATENCY,$(date +%s)" >> "$OUT"
done

kill "$ECU_PID" 2>/dev/null || true
```

### 전체 실행

```bash
cd security
chmod +x run_ablation.sh
for config in 1 2 3; do
  for attack in spoofing replay flooding fuzzy; do
    ./run_ablation.sh "$config" "$attack" 100
  done
done

python3 merge_results.py --input results/ --output ids/results_summary.csv
python3 analyze_roc.py --input ids/results_summary.csv --model ids/ids_model.pkl
```

### M5 완료 기준

- [ ] TC-SEC-005-b/c 통과
- [ ] TC-EXP-001~004 각 100회 기록
- [ ] TC-EXP-005 정상 오탐율 `≤5%`
- [ ] `results_summary.csv` 데이터 row 1,200개
- [ ] ROC curve와 최적 threshold 저장
- [ ] TARA/ADR에 실험 결과 반영
- [ ] ECU 담당 ADR 최종화: ADR-001(SocketCAN), ADR-002(HMAC-SHA256), ADR-003(Isolation Forest), ADR-005(EKF), ADR-008(Ablation Study), ADR-009(IDS Node A 위치), ADR-011(Python 보안 코드), ADR-012(SecOC 분리 프레임)
- [ ] `v0.5.0` 태그 생성

---

## 10. M6 (11월) — 문서, 그래프, 품질

### 목표

실험 결과를 그래프로 만들고, ECU 설계/보안 문서를 최종화한다.

### 그래프 생성

```bash
cd security
python3 plot_ablation.py --input ids/results_summary.csv --output results/
python3 plot_ekf.py --input ../adaptive_ecu/build/ekf_comparison.csv --output results/ekf_accuracy.png

ls results/
# 기대: ablation_success_rate.png, ablation_detection_rate.png, ablation_latency.png, ekf_accuracy.png
```

### SDD-ECU 작성 매핑

| SDD-ECU 섹션 | 포함 내용 | TC |
|---|---|---|
| CAN CDD | SocketCAN, Mock, rxLoop | TC-BSW-001~003 |
| Publisher | ara::com-like Pub/Sub | TC-BSW-004~005 |
| Watchdog | 1초 감시, 3초 timeout | TC-BSW-006~007 |
| SensorSimulator | CONSTANT/CSV/RANDOM/ADS1115 | TC-BSW-008 |
| BMS/EKF/SOH | SOC/SOH 알고리즘 | TC-BMS-001~003 |
| Fail-safe | 4상태 FSM, reason code | TC-BMS-004~006 |
| CAN Publisher | `0x100`, `0x101` 송신 | TC-BMS-007 |
| SecOC | HMAC, counter, key | TC-SEC-001~004 |
| IDS | feature, IF model, `0x200` | TC-SEC-005~007 |

### 품질 확인

```bash
cd adaptive_ecu/build
ctest --output-on-failure

cppcheck --enable=all --error-exitcode=1 --suppress=missingIncludeSystem \
  -I ../include ../src

lcov --capture --directory . --output-file cov.info
lcov --summary cov.info
# lines >= 80.0%, fail-safe branches = 100.0%
```

### M6 완료 기준

- [ ] Ablation 그래프 3개 생성
- [ ] EKF 정확도 그래프 생성
- [ ] `docs/SDD-ECU.md` 완성
- [ ] `docs/TARA.md`에 Ablation 실측 수치 반영
- [ ] `docs/TEST_PLAN.md` 결과/Skip 사유 기록
- [ ] Coverage `≥80%`, Fail-safe branch `100%`
- [ ] `v0.6.0` 태그 생성

---

## 11. M7 (12월) — 최종 검증과 재현성

### 목표

ICD와 구현을 교차 검토하고, 실험 재현성과 최종 성능을 확인한다.

### CPU governor 고정

```bash
sudo apt install -y cpufrequtils
for cpu in /sys/devices/system/cpu/cpu[0-3]; do
  echo performance | sudo tee "$cpu/cpufreq/scaling_governor"
done
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

### Ablation 재현성

```bash
cd security
cp ids/results_summary.csv ids/results_summary_previous.csv
for config in 1 2 3; do
  for attack in spoofing replay flooding fuzzy; do
    ./run_ablation.sh "$config" "$attack" 100
  done
done
python3 verify_reproducibility.py \
  --previous ids/results_summary_previous.csv \
  --current ids/results_summary.csv \
  --threshold 5
```

### ICD 교차 검토

- [ ] `0x100` SOC/SOH scaling `x0.5`
- [ ] `0x100` voltage/current big-endian
- [ ] current signed int16 two's complement
- [ ] temperature offset `+40`
- [ ] `0x101` state/reason code 일치
- [ ] `0x102/0x103` `CAN_ID || Counter || Payload`
- [ ] RollingCounter replay 방어
- [ ] `0x200` `>BBHI` equivalent layout
- [ ] Node B parser와 동일 해석
- [ ] SecOC key path/permission 양 노드 동일

### 최종 성능

```bash
cd adaptive_ecu/build
ctest --output-on-failure --timeout 60

cd ../../security
python3 -m pytest tests -v

# TC-PERF-002: BMS 주기
candump -t d can0 | head -110

# TC-PERF-003: IDS 응답
python3 attacks/flooding_attack.py --channel can0 --duration 10
```

### M7 완료 기준

- [ ] Ablation 재현성 편차 `≤5%`
- [ ] ICD 불일치 0건
- [ ] IT-001~005 재검증 Pass
- [ ] TC-PERF-001 평균 `≤50ms`, 최대 `≤100ms`
- [ ] TC-PERF-002 `100ms ±10ms`
- [ ] TC-PERF-003 `≤3초`
- [ ] `security/ids/how_to_train.md`만 보고 재학습 가능
- [ ] `v0.7.0` 태그 생성

---

## 12. M8 (1월) — 데모, 발표, 최종 제출

### 데모 시나리오 A: 정상 동작

```bash
./adaptive_ecu --interface can0 --secoc=on --ids=on --sensor-mode profile_csv
```

- [ ] Node B dashboard에서 SOC/전압/전류/온도 실시간 표시
- [ ] SOC 15% -> WARNING 표시
- [ ] SOC 3~4.5% -> CRITICAL 표시
- [ ] `0x100`, `0x101`, `0x102`, `0x103` candump 증적 저장

### 데모 시나리오 B: 공격과 방어

```bash
# 무방어
./adaptive_ecu --interface can0 --secoc=off --ids=off &
python3 security/attacks/spoofing_attack.py --channel can0 --count 5

# SecOC 방어
./adaptive_ecu --interface can0 --secoc=on --ids=off &
python3 security/attacks/spoofing_attack.py --channel can0 --count 5

# IDS 탐지
./adaptive_ecu --interface can0 --secoc=on --ids=on &
python3 security/attacks/flooding_attack.py --channel can0 --duration 5
```

### ECU 발표 슬라이드

| 슬라이드 | 핵심 메시지 | 증적 |
|---|---|---|
| BSW/CDD | SocketCAN CDD + Mock 교체 | TC-BSW 통과 |
| BMS | EKF vs Coulomb counting | RMSE 그래프 |
| Fail-safe | 상태 전이와 branch 100% | coverage |
| SecOC | Python -> C++ -> IVI verifier | test vector |
| IDS | Isolation Forest, 7 features | 탐지율/오탐율 |
| Ablation | 3 Config x 4 Attack | 1,200회 결과 |

### M8 완료 기준

- [ ] 정상/공격 데모 모두 재현
- [ ] 발표 자료와 보고서 ECU 파트 완성
- [ ] `results_summary.csv`, 그래프, 영상 링크 Release 첨부
- [ ] 리허설 3회 완료
- [ ] `v1.0.0` 태그 생성

---

## 13. IVI 팀 연계 지점 총정리

| 시점 | ECU가 제공할 것 | IVI가 확인할 것 |
|---|---|---|
| M1 | CAN ID/byte layout, `CanFrame` | HIDL/HAL 타입 일치 |
| M2 | `0x100` 샘플 payload | HAL mock parser |
| M3 | SecOC Python/C++ vector | `secoc_verifier.cpp` 동일 MAC |
| M4 | `0x200` IDS_Alert | AlertBanner |
| M4 | 물리 CAN 송신 | dashboard/logcat |
| M5 | Ablation 일정 | latency 측정과 시간 분리 |
| M6 | SDD-ECU 초안 | IVI 관점 리뷰 |
| M7 | ICD 구현 체크리스트 | Node B parser 교차 확인 |
| M8 | 데모 A/B 실행 | 화면/로그/영상 증적 |

---

## 14. 실패 시 우회 전략

| 문제 | 즉시 조치 | 최종 조치 |
|---|---|---|
| MCP2515 인식 실패 | `vcan0`으로 개발 지속 | 배선, oscillator, INT, 종단저항 점검 |
| SecOC C++ 지연 | Python vector 먼저 공유 | C++ 이식 후 Config 2/3 재실험 |
| IDS 탐지율 미달 | contamination/threshold 조정 | feature 추가, ROC 재분석 |
| Coverage 미달 | 위험 모듈 테스트 우선 추가 | Fail-safe branch 100%, 전체 80% |
| ICD 불일치 | 구현을 ICD에 맞춤 | ICD가 틀리면 interface-change PR |
| 물리 통합 실패 | Mock/vcan 논리 통합 유지 | M4 전 CAN 하드웨어 집중 디버깅 |

---

## 15. 최종 셀프 QA

### 코드

- [ ] `adaptive_ecu/`와 `security/`가 표준 구조로 존재한다.
- [ ] `CAR-ECU/`를 신규 구현 루트로 쓰지 않는다.
- [ ] Mock/SocketCAN이 `CanDriver`로 교체 가능하다.
- [ ] `0x100`, `0x101`, `0x102`, `0x103`, `0x200` 인코딩이 ICD와 일치한다.
- [ ] 실행 옵션 `--interface`, `--secoc`, `--ids`, `--sensor-mode`가 동작한다.

### 테스트

- [ ] TC-BSW-001~008 결과 기록
- [ ] TC-BMS-001~007 결과 기록
- [ ] TC-SEC-001~007 결과 기록
- [ ] TC-EXP-001~005 결과 기록
- [ ] TC-PERF-001~003 결과 기록
- [ ] IT-001~005 결과 기록

### 실험/문서/데모

- [ ] `normal_traffic.csv`, `ids_model.pkl`, `results_summary.csv` 보관
- [ ] ROC, Ablation, EKF 그래프 생성
- [ ] SDD-ECU/TARA/ADR/TEST_PLAN 최신
- [ ] `how_to_train.md`로 IDS 재학습 가능
- [ ] 정상/공격 데모 영상 백업

---

## 16. 한 줄 실행 순서

```text
GitHub 인프라
-> M1 환경/ICD
-> M2 CAN CDD/Mock/100ms
-> M3 EKF/Fail-safe/SecOC
-> M4 IDS/공격/물리 통합
-> M5 Ablation 1,200회
-> M6 문서/그래프/Coverage
-> M7 재현성/교차검토/성능
-> M8 데모/발표/v1.0.0
```
