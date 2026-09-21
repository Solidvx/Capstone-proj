# IVI 담당자 최종 실행계획서

> **대상**: 팀원B (Node B — IVI / HAL / Service / Dashboard / CI/CD 담당자)  
> **기준일**: 2026-05-27  
> **프로젝트**: AUTOSAR 계층 기반 IVI-ECU 통합 플랫폼  
> **역할**: RPi4 Android/AOSP 또는 Plan B Ubuntu / HIDL HAL / SystemService / Dashboard / CI/CD  
> **기간**: 2026-06 ~ 2027-01 (8개월, M1~M8)  
> **이 문서의 성공 기준**: 이 문서를 위에서 아래로 그대로 따라가면 IVI 담당자의 구현, 검증, CI/CD, ECU 연계, 최종 데모를 완수할 수 있어야 한다.
>
> **원천 문서 우선순위**: `.claude/project-overview.md`, `docs/ROADMAP.md`, `Plan/IVI.md`, `Plan/INDEX.md`, `Plan/공동.md`, `Plan/팀간_연계_분석.md`, `docs/ICD.md`, `docs/SRS.md`, `docs/SDD-IVI.md`, `docs/TEST_PLAN.md`, `docs/ADR.md`, `docs/CICD_SPEC.md`

---

## 0. 최종 목표

IVI 담당자는 Node B를 차량 IVI 플랫폼처럼 구성하고, ECU가 송신하는 CAN/SecOC/IDS 데이터를 HAL -> Service -> UI까지 전달한다. 또한 CI/CD 파이프라인으로 전체 프로젝트 품질을 보증한다.

- [ ] AOSP Plan A를 시도하고, M2 말까지 실패 시 Plan B로 전환한다.
- [ ] `ivi_platform/`에 HAL, parser, service, dashboard 구조를 만든다.
- [ ] CAN ID `0x100`, `0x101`, `0x102`, `0x103`, `0x200`을 ICD대로 파싱한다.
- [ ] SecOC verifier가 ECU test vector와 동일하게 HMAC을 검증한다.
- [ ] Dashboard가 SOC/SOH/전압/전류/온도, fail-safe, IDS alert를 표시한다.
- [ ] GitHub Actions Stage 1~4를 구축한다: cppcheck -> ARM64 build -> QEMU test -> SSH deploy/health check.
- [ ] `docs/SDD-IVI.md`, `docs/CICD_SPEC.md`, `README.md`, 발표 자료를 완성한다.
- [ ] ECU 담당자와 `IT-001~005`를 통과시키고 최종 데모를 완성한다.

### 완료 판정 기준

| 영역 | 완료 기준 |
|---|---|
| HAL/parser | `TC-IVI-001~002` 통과, CAN ID 5종 파싱 정확 |
| Service/UI | `TC-IVI-003~008` 통과, dashboard/alert 동작 |
| SecOC | ECU vector와 동일 MAC, 변조 MAC 폐기 |
| CI/CD | Stage 1~4 녹색, ARM64 artifact, health check pass |
| 통합 | `IT-001~005` 전부 Pass, 공식 `TC-INT-001~004` 기록 |
| 성능 | e2e 평균 `≤50ms`, 최대 `≤100ms`, UI 반영 목표 만족 |
| 안정성 | 24시간 또는 합의된 단축 안정성 테스트 pass |
| 문서 | SDD-IVI, CICD_SPEC, README, Release note 완성 |

### 월별 태그 계획

| 월 | 태그 | Due Date | IVI 핵심 완료 조건 |
|---|---|---:|---|
| M1 | `v0.1.0` | 2026-06-30 | AOSP sync, Docker ARM64, HIDL 초안, CI Stage 1 |
| M2 | `v0.2.0` | 2026-07-31 | HAL Mock, AOSP boot 시도, Plan A/B 결정 |
| M3 | `v0.3.0` | 2026-08-31 | CAN parser, HAL impl, service, dashboard 기본 UI, SecOC verifier |
| M4 | `v0.4.0` | 2026-09-30 | Dashboard/Alert UI, CI Stage 4, IT-001~005 |
| M5 | `v0.5.0` | 2026-10-31 | Latency 측정/최적화, UI 개선, ADR 보완 |
| M6 | `v0.6.0` | 2026-11-30 | SDD-IVI, CICD_SPEC, README, Coverage |
| M7 | `v0.7.0` | 2026-12-31 | 안정성, CI 최종 점검, 교차 검토 |
| M8 | `v1.0.0` | 2027-01-31 | 최종 데모, 발표, 보고서, GitHub 정리 |

---

## 1. 작업 위치와 표준 구조

| 영역 | 표준 경로 | IVI 담당 규칙 |
|---|---|---|
| IVI 구현 | `ivi_platform/` | HAL, service, dashboard, Plan B UI |
| CI/CD | `.github/workflows/`, `Dockerfile.arm64`, `toolchain-aarch64.cmake` | ARM64 build/test/deploy |
| ECU 연계 | `adaptive_ecu/`, `security/` | 직접 구현하지 않지만 parser/vector/test 연계 |
| 문서 | `docs/` | SDD-IVI, CICD_SPEC, README, TEST_PLAN |
| 계획 | `Plan/` | 월별 실행 참조 |

권장 최종 구조:

```text
ivi_platform/
├── hal/
│   ├── IVehicleHal.hal
│   ├── IVehicleHalCallback.hal
│   ├── vehicle_hal_impl.h
│   ├── vehicle_hal_impl.cpp
│   ├── can_parser.h
│   ├── can_parser.cpp
│   ├── secoc_verifier.h
│   ├── secoc_verifier.cpp
│   └── mock/
│       └── VehicleHalMock.java
├── service/
│   ├── IVehicleDataService.aidl
│   ├── VehicleDataService.java
│   └── VehicleDataManager.java
├── app/
│   ├── DashboardActivity.kt
│   ├── DashboardViewModel.kt
│   ├── DashboardScreen.kt
│   ├── SocGauge.kt
│   ├── FailSafeIndicator.kt
│   ├── AlertBanner.kt
│   ├── LogPanel.kt
│   └── data/
│       └── VehicleRepository.kt
├── plan_b/
│   ├── dbus_vehicle_service.py
│   ├── grpc_vehicle_service.py
│   └── flutter_dashboard/
├── test/
│   ├── test_can_parser.cpp
│   ├── test_secoc_verifier.cpp
│   └── test_vehicle_service.java
├── app/test/
│   ├── SocGaugeTest.kt
│   ├── DashboardScreenTest.kt
│   └── DashboardViewModelTest.kt
└── scripts/
    └── measure_latency.py

scripts/                          # 루트 레벨 공용 스크립트 (ROADMAP 기준)
└── health_check.sh
```

---

## 2. 반드시 지켜야 할 ICD 계약

IVI는 ECU 데이터를 해석하는 수신자다. ECU가 보내는 byte layout을 임의로 재해석하면 통합이 실패한다.

### 2.1 CAN ID 계약

| CAN ID | 방향 | 메시지 | 주기 | DLC | IVI 담당 작업 |
|---|---|---|---:|---:|---|
| `0x100` | Node A -> Node B | BMS_Status | 100ms | 8 | HAL parser -> VehicleData |
| `0x101` | Node A -> Node B | BMS_FailSafe | 이벤트 | 8 | Fail-safe state/reason 표시 |
| `0x102` | Node A -> Node B | BMS_SecOC | 100ms | 8 | `0x100` MAC 검증 |
| `0x103` | Node A -> Node B | FailSafe_SecOC | 이벤트 | 8 | `0x101` MAC 검증 |
| `0x200` | Node A -> Node B | IDS_Alert | 이벤트 | 8 | AlertBanner 표시 |

### 2.2 Parser 규칙

| CAN ID | Byte | IVI 해석 |
|---|---:|---|
| `0x100` | 0 | `soc = raw * 0.5` |
| `0x100` | 1 | `soh = raw * 0.5` |
| `0x100` | 2-3 | `voltage = uint16_be * 0.01` |
| `0x100` | 4-5 | `current = int16_be * 0.1` |
| `0x100` | 6 | `temperature = raw - 40` |
| `0x101` | 0-2 | previous/new state, reason |
| `0x102/0x103` | 0-3 | TruncatedMAC |
| `0x102/0x103` | 4-7 | RollingCounter |
| `0x200` | 0 | AttackType |
| `0x200` | 1 | `anomalyScore = raw * 0.01` |
| `0x200` | 2-3 | suspect CAN ID |
| `0x200` | 4-7 | timestamp |

SecOC:

```text
HMAC_Input = CAN_ID(2B, BE) || RollingCounter(4B, BE) || Payload(8B)
MAC = HMAC-SHA256(SharedKey, HMAC_Input)
TruncatedMAC = MAC[0:4]
```

키 파일:

```bash
sudo mkdir -p /etc/secoc
sudo install -o root -g root -m 400 key.bin /etc/secoc/key.bin
sudo ls -l /etc/secoc/key.bin
```

### 2.3 통합 테스트 이름 매핑

| 프로젝트 시나리오 | 공식 TEST_PLAN ID | IVI 성공 기준 |
|---|---|---|
| `IT-001` | `TC-INT-001` | dashboard에 `0x100` 값 표시 |
| `IT-002` | `TC-INT-003` | CRITICAL/SHUTDOWN dialog |
| `IT-003` | `TC-INT-002` | SecOC verify success |
| `IT-004` | `TC-INT-002` | 변조 MAC 거부, 데이터 갱신 없음 |
| `IT-005` | `TC-INT-004` | 3초 내 AlertBanner |

---

## 3. 공통 작업 방식

### 브랜치와 PR

```bash
git switch develop
git pull origin develop
git switch -c feat/ivi-m3-can-parser

git status
git add ivi_platform docs .github Dockerfile.arm64 toolchain-aarch64.cmake
git commit -m "feat(ivi): implement CAN parser and vehicle data pipeline"
git push -u origin feat/ivi-m3-can-parser
# GitHub PR: base=develop, 팀원A 리뷰 요청
```

| 작업 | 라벨 |
|---|---|
| IVI 기능 | `feat`, `IVI` |
| HAL/parser | `feat`, `IVI` |
| CI/CD | `chore`, `IVI` 또는 `test`, `IVI` |
| 문서 | `docs`, `IVI` |
| CAN/HAL 계약 변경 | `interface-change`, `docs`, `ECU`, `IVI` |
| 블로커 | `blocked` (다른 이슈/PR에 의존하여 진행 불가) |

### 커밋 메시지 컨벤션

```text
<type>(<scope>): <한 줄 요약>
```

| type | 상황 | scope 예시 |
|---|---|---|
| `feat` | 새 기능 | `hal` `service` `dashboard` `ci` |
| `fix` | 버그 수정 | |
| `test` | 테스트 추가/수정 | |
| `docs` | 문서 수정 | |
| `chore` | 빌드·CI 변경 | |
| `refactor` | 동작 변경 없는 정리 | |

### PR 본문 템플릿

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

### 매월 마일스톤 처리

```bash
# GitHub 웹: develop -> main PR 생성 후 CI 전체 통과 확인
git switch main
git pull origin main
git tag -a v0.N.0 -m "MN: 완료 내용 요약"
git push origin v0.N.0
# GitHub Milestone close, Release 작성
```

---

## 4. 지금 당장 할 일 (M1 시작 전 착수 즉시)

M1 정식 시작 전에 반드시 완료해야 할 항목이다.

| 담당 | 작업 |
|---|---|
| 팀원B | **AOSP `repo sync` 즉시 시작** — 70GB+, 4~8시간 소요, 가장 먼저 착수 |
| 공동 | GitHub `develop` 브랜치 생성 + push |
| 공동 | `main` / `develop` 브랜치 보호 규칙 설정 (PR 필수, Force push 차단) |
| 공동 | 팀원 collaborator 초대 |
| 공동 | GitHub Milestones M1~M8 생성, Labels 생성 |
| 공동 | 디렉토리 골격 PR 생성 (`adaptive_ecu/`, `ivi_platform/`, `security/`, `docs/`) |

---

## 5. M1 (6월) — AOSP 환경, Docker, HIDL 초안, CI Stage 1

### 목표

AOSP 빌드 환경을 준비하고, ARM64 크로스컴파일 Docker와 CI Stage 1을 만든다. ECU 담당자와 ICD를 확정하여 M2부터 독립 개발 가능하게 한다.

### 주차별 작업

| 주차 | IVI 작업 | ECU/공동 연계 |
|---|---|---|
| 1주차 | AOSP build server, Docker, repo sync | GitHub 인프라 |
| 2주차 | `Dockerfile.arm64`, toolchain, `ivi_platform/` 골격 | 디렉토리 골격 PR |
| 3주차 | `IVehicleHal.hal` 초안, CI Stage 1 | ICD review |
| 4주차 | FR-IVI/FR-CI, ADR-004/007 | ICD 확정, `v0.1.0` |

### 관련 파일

| 파일 | 목적 |
|---|---|
| `Dockerfile.arm64` | ARM64 cross build image |
| `toolchain-aarch64.cmake` | CMake ARM64 toolchain |
| `.github/workflows/ci.yml` | CI Stage 1~4 |
| `ivi_platform/hal/IVehicleHal.hal` | HAL contract |
| `docs/SRS.md` | FR-IVI, FR-CI |
| `docs/ADR.md` | HIDL/Docker 선택 근거 |

### 세부 수행 절차

#### 5.1 AOSP 빌드 서버 요구 사항

| 항목 | 권장 |
|---|---|
| OS | Ubuntu 22.04 LTS |
| Disk | 200GB 이상 |
| RAM | 16GB 이상 권장 |
| Network | 안정적인 유선 권장 |
| 시간 | initial sync 4~8시간 이상 |

```bash
sudo apt update
sudo apt install -y git-core gnupg flex bison build-essential zip curl zlib1g-dev \
  libc6-dev-i386 x11proto-core-dev libx11-dev lib32z1-dev libgl1-mesa-dev \
  libxml2-utils xsltproc unzip fontconfig python3 python3-pip repo
```

#### 5.2 Docker 설치

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker run hello-world
```

#### 5.3 AOSP repo sync

```bash
mkdir -p ~/aosp-rpi4 && cd ~/aosp-rpi4
repo init -u https://android.googlesource.com/platform/manifest -b android-13.0.0_r3 --depth=1
repo sync -c -j$(nproc) --no-tags
du -sh .
```

실패 시:

```bash
repo sync -c -j4 --no-tags --fail-fast
# 네트워크 오류는 같은 명령 재실행. repo는 이어받기 가능.
```

#### 5.4 Dockerfile.arm64

```dockerfile
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    build-essential cmake ninja-build git pkg-config \
    gcc-aarch64-linux-gnu g++-aarch64-linux-gnu \
    qemu-user-static libssl-dev cppcheck lcov \
    python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
```

```bash
docker build -f Dockerfile.arm64 -t capstone-arm64 .
```

`toolchain-aarch64.cmake`:

```cmake
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)
set(CMAKE_C_COMPILER aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)
set(CMAKE_FIND_ROOT_PATH /usr/aarch64-linux-gnu)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
```

#### 5.5 IVehicleHal.hal 초안

```hal
package vendor.capstone.vehicle@1.0;

interface IVehicleHal {
    getLatestData() generates (VehicleData data);
    subscribe(IVehicleHalCallback callback);
};

struct VehicleData {
    float soc;
    float soh;
    float voltage;
    float current;
    int32_t temperature;
    int32_t failSafePrevState;
    int32_t failSafeState;
    int32_t failSafeReason;
    float socAtEvent;
    int32_t tempAtEvent;
    int32_t attackType;
    float anomalyScore;
    uint16_t suspectCanId;
};

interface IVehicleHalCallback {
    onVehicleDataChanged(VehicleData data);
};
```

#### 5.6 CI Stage 1

```yaml
name: CI

on:
  push:
    branches: [develop, main]
  pull_request:
    branches: [develop, main]

jobs:
  stage1-static-analysis:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - name: Install cppcheck
        run: sudo apt-get update && sudo apt-get install -y cppcheck
      - name: cppcheck ECU/IVI native code
        run: |
          cppcheck --enable=all --error-exitcode=1 \
            --suppress=missingIncludeSystem \
            -I adaptive_ecu/include adaptive_ecu/src ivi_platform/hal
```

### M1 ECU 연계

- [ ] ECU 담당자에게 HIDL `VehicleData` 타입 리뷰를 요청한다.
- [ ] `docs/ICD.md`의 byte layout과 parser type을 대조한다.
- [ ] `0x200`은 Node A IDS가 송신하고 Node B가 표시한다는 ADR-009를 문서화한다.

### M1 완료 기준

- [ ] AOSP repo sync 시작/완료
- [ ] Docker image build 성공
- [ ] `ivi_platform/` 골격 생성
- [ ] HIDL 초안 작성
- [ ] CI Stage 1 녹색
- [ ] ICD 확정 리뷰 참여
- [ ] `v0.1.0` 태그 생성

---

## 6. M2 (7월) — HAL Mock, AOSP 부팅 시도, Plan A/B 결정

### 목표

실제 CAN 없이도 UI/service 개발이 가능한 HAL Mock을 만들고, AOSP RPi4 부팅 가능성을 M2 말까지 판단한다.

### 주차별 작업

| 주차 | IVI 작업 | ECU/공동 연계 |
|---|---|---|
| 1주차 | `VehicleHalMock`, repository | ECU `0x100` 샘플 수신 |
| 2주차 | AOSP build attempt | Mock payload parser 검증 |
| 3주차 | Docker Stage 2 ARM64 build | ECU C++ cross-build 협업 |
| 4주차 | Plan A/B 결정 | ADR-010 필요 여부 확정 |

### HAL Mock 예시

```java
public final class VehicleHalMock {
    private final List<VehicleCallback> callbacks = new ArrayList<>();

    public void subscribe(VehicleCallback callback) {
        callbacks.add(callback);
    }

    public void emitBmsStatus() {
        VehicleData data = new VehicleData();
        data.soc = 75.0f;
        data.soh = 95.0f;
        data.voltage = 42.0f;
        data.current = -2.0f;
        data.temperature = 25;
        for (VehicleCallback cb : callbacks) {
            cb.onVehicleDataChanged(data);
        }
    }
}
```

Kotlin repository:

```kotlin
class VehicleRepository(private val hal: VehicleHalMock) {
    private val _vehicleData = MutableStateFlow(VehicleData())
    val vehicleData: StateFlow<VehicleData> = _vehicleData

    fun start() {
        hal.subscribe { data -> _vehicleData.value = data }
    }
}
```

### AOSP build attempt

```bash
cd ~/aosp-rpi4
source build/envsetup.sh
lunch aosp_arm64-eng
m -j$(nproc)
ls out/target/product/*/{system.img,boot.img,vendor.img} 2>/dev/null
```

실패 시 swap:

```bash
sudo fallocate -l 16G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
free -h
```

### Plan A/B 판단 기준

| 조건 | 결정 |
|---|---|
| AOSP 이미지 생성 + RPi4 shell 진입 + CAN 접근 가능 | Plan A 유지 |
| 7월 말까지 부팅 실패, device tree/kernel 이슈 지속 | Plan B 전환 |
| AOSP는 되지만 UI 개발이 과도하게 지연 | Plan B 또는 Hybrid 검토 |

Plan B 기본 스택:

| 계층 | Plan B 기술 |
|---|---|
| CAN reader | Ubuntu SocketCAN C++/Python |
| Middleware | D-Bus 또는 gRPC |
| UI | Qt 또는 Flutter desktop |
| 원칙 | HAL -> Service -> UI 계층 분리 유지 |

Plan B 패키지:

```bash
sudo apt update
sudo apt install -y python3-dbus python3-gi qtbase5-dev qtcreator protobuf-compiler
```

### M2 완료 기준

- [ ] HAL Mock으로 dashboard prototype 업데이트 가능
- [ ] ECU `0x100` sample payload를 mock input으로 사용
- [ ] AOSP boot attempt 결과 기록
- [ ] Plan A/B 결정 미팅 완료
- [ ] 필요 시 ADR-010 작성
- [ ] ARM64 Docker build 동작
- [ ] `v0.2.0` 태그 생성

---

## 7. M3 (8월) — CAN Parser, HAL, Service, Dashboard, SecOC Verifier

### 목표

CAN frame을 VehicleData로 파싱하고, HAL -> Service -> UI 흐름을 완성한다.

### 주차별 작업

| 주차 | IVI 작업 | ECU 연계 |
|---|---|---|
| 1주차 | `can_parser.h/cpp`, HAL receive loop | ECU `0x100/0x101` samples |
| 2주차 | Binder/AIDL or HIDL service, Manager | service contract 리뷰 |
| 3주차 | Compose dashboard, ViewModel | 실시간 값 범위 확인 |
| 4주차 | `secoc_verifier.cpp`, CI Stage 2/3 | ECU test vector 검증 |

### 관련 파일

| 파일 | 테스트 |
|---|---|
| `ivi_platform/hal/can_parser.cpp` | TC-IVI-002 |
| `ivi_platform/hal/vehicle_hal_impl.cpp` | TC-IVI-001 |
| `ivi_platform/hal/secoc_verifier.cpp` | TC-INT-002 |
| `ivi_platform/service/VehicleDataService.java` | TC-IVI-003~004 |
| `ivi_platform/app/DashboardViewModel.kt` | TC-IVI-004, TC-IVI-008 |
| `ivi_platform/app/SocGauge.kt` | TC-IVI-005 |

### CAN parser 예시

```cpp
#include <array>
#include <cstdint>

struct VehicleData {
    float soc = 0;
    float soh = 0;
    float voltage = 0;
    float current = 0;
    int temperature = 0;
    int failSafePrevState = 0;
    int failSafeState = 0;
    int failSafeReason = 0;
    float socAtEvent = 0;
    int tempAtEvent = 0;
    int attackType = 0;
    float anomalyScore = 0;
    uint16_t suspectCanId = 0xFFFF;
};

static uint16_t u16be(const uint8_t* p) {
    return static_cast<uint16_t>((p[0] << 8) | p[1]);
}

static int16_t i16be(const uint8_t* p) {
    return static_cast<int16_t>(u16be(p));
}

bool parseCanFrame(uint32_t id, const std::array<uint8_t, 8>& d, VehicleData& out) {
    switch (id) {
    case 0x100:
        out.soc = d[0] * 0.5f;
        out.soh = d[1] * 0.5f;
        out.voltage = u16be(&d[2]) * 0.01f;
        out.current = i16be(&d[4]) * 0.1f;
        out.temperature = static_cast<int>(d[6]) - 40;
        return true;
    case 0x101:
        out.failSafePrevState = d[0];
        out.failSafeState = d[1];
        out.failSafeReason = d[2];
        out.socAtEvent = d[3] * 0.5f;
        out.tempAtEvent = static_cast<int>(d[4]) - 40;
        return true;
    case 0x200:
        out.attackType = d[0];
        out.anomalyScore = d[1] * 0.01f;
        out.suspectCanId = u16be(&d[2]);
        return true;
    default:
        return false;
    }
}
```

Parser test sample:

```cpp
TEST(CanParser, BmsStatus) {
    std::array<uint8_t, 8> d{150, 190, 0x10, 0x68, 0xFF, 0xEC, 65, 0};
    VehicleData v;
    ASSERT_TRUE(parseCanFrame(0x100, d, v));
    EXPECT_FLOAT_EQ(v.soc, 75.0f);
    EXPECT_FLOAT_EQ(v.soh, 95.0f);
    EXPECT_FLOAT_EQ(v.voltage, 42.0f);
    EXPECT_FLOAT_EQ(v.current, -2.0f);
    EXPECT_EQ(v.temperature, 25);
}
```

### HAL receive loop

```cpp
while (running_) {
    struct can_frame frame{};
    int nbytes = read(socket_fd_, &frame, sizeof(frame));
    if (nbytes != sizeof(frame)) continue;

    std::array<uint8_t, 8> data{};
    std::copy(frame.data, frame.data + 8, data.begin());

    VehicleData parsed;
    if (parseCanFrame(frame.can_id, data, parsed)) {
        notifySubscribers(parsed);
    }
}
```

### SecOC verifier

```cpp
#include <openssl/hmac.h>
#include <openssl/crypto.h>
#include <array>
#include <cstdint>

bool verifySecOc(const std::array<uint8_t, 32>& key,
                 uint16_t can_id,
                 uint32_t counter,
                 const std::array<uint8_t, 8>& payload,
                 const std::array<uint8_t, 4>& received_mac,
                 uint32_t last_counter) {
    if (!(last_counter < counter && counter <= last_counter + 100)) {
        return false;
    }

    std::array<uint8_t, 14> input{};
    input[0] = static_cast<uint8_t>((can_id >> 8) & 0xFF);
    input[1] = static_cast<uint8_t>(can_id & 0xFF);
    input[2] = static_cast<uint8_t>((counter >> 24) & 0xFF);
    input[3] = static_cast<uint8_t>((counter >> 16) & 0xFF);
    input[4] = static_cast<uint8_t>((counter >> 8) & 0xFF);
    input[5] = static_cast<uint8_t>(counter & 0xFF);
    std::copy(payload.begin(), payload.end(), input.begin() + 6);

    unsigned int len = 0;
    unsigned char mac[EVP_MAX_MD_SIZE];
    HMAC(EVP_sha256(), key.data(), key.size(), input.data(), input.size(), mac, &len);
    return CRYPTO_memcmp(mac, received_mac.data(), 4) == 0;
}
```

### Dashboard ViewModel

```kotlin
class DashboardViewModel(
    private val repository: VehicleRepository
) : ViewModel() {
    val vehicleData: StateFlow<VehicleData> = repository.vehicleData
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), VehicleData())
}
```

### SocGauge

```kotlin
@Composable
fun SocGauge(soc: Float) {
    val color = when {
        soc < 20f -> Color(0xFFF44336)   // Red: 위험
        soc < 50f -> Color(0xFFFF9800)   // Orange: 주의
        else -> Color(0xFF4CAF50)         // Green: 정상
    }
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(text = "${soc.format1()}%", color = color)
        LinearProgressIndicator(progress = soc / 100f, color = color)
    }
}

private fun Float.format1(): String = String.format("%.1f", this)
```

### M3 검증 명령

```bash
cd ivi_platform
mkdir -p build && cd build
cmake ..
make
ctest -R test_can_parser --output-on-failure
ctest -R test_secoc_verifier --output-on-failure

# Android/Gradle 계열이면
./gradlew test
```

CI Stage 2/3:

```yaml
  stage2-arm64-build:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - run: docker build -f Dockerfile.arm64 -t capstone-arm64 .
      - run: |
          docker run --rm -v $PWD:/workspace capstone-arm64 \
            bash -lc "cmake -S adaptive_ecu -B build-arm64 -DCMAKE_TOOLCHAIN_FILE=toolchain-aarch64.cmake && cmake --build build-arm64"

  stage3-qemu-test:
    runs-on: ubuntu-22.04
    needs: stage2-arm64-build
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get update && sudo apt-get install -y qemu-user-static
      - run: echo "Run ARM64 tests under qemu when artifacts are available"
```

### M3 완료 기준

- [ ] TC-IVI-001~005 통과
- [ ] TC-IVI-008 통과 (DashboardViewModel StateFlow CAN 데이터 반영 레이턴시 ≤20ms)
- [ ] `0x100`, `0x101`, `0x200` parser test 통과
- [ ] ECU SecOC vector로 verifier 통과
- [ ] Dashboard 기본 UI 동작
- [ ] CI Stage 2/3 녹색
- [ ] `v0.3.0` 태그 생성

---

## 8. M4 (9월) — Dashboard 완성, Alert UI, CI Stage 4, 통합 테스트

### 목표

Dashboard 전체 UI와 배포/health check를 완성하고 ECU와 물리 CAN 통합을 수행한다.

### 주차별 작업

| 주차 | IVI 작업 | ECU 연계 |
|---|---|---|
| 1주차 | DashboardScreen, FailSafeIndicator | `0x101` 이벤트 확인 |
| 2주차 | AlertBanner | `0x200` IDS_Alert 연결 |
| 3주차 | systemd, SSH deploy, health check | Node A service 재시작 |
| 4주차 | IT-001~005, SDD-IVI app section | 공동 통합 테스트 |

### DashboardScreen

```kotlin
@Composable
fun DashboardScreen(viewModel: DashboardViewModel) {
    val data by viewModel.vehicleData.collectAsState()
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        SocGauge(data.soc)
        Text("SOH: ${data.soh.format1()}%")
        Text("Voltage: ${data.voltage.format2()} V")
        Text("Current: ${data.current.format1()} A")
        Text("Temperature: ${data.temperature} °C")
        FailSafeIndicator(data.failSafeState, data.failSafeReason)
        AlertBanner(data.attackType, data.anomalyScore)
    }
}

private fun Float.format2(): String = String.format("%.2f", this)
```

### AlertBanner

```kotlin
@Composable
fun AlertBanner(attackType: Int, score: Float) {
    if (attackType == 0) return
    val label = when (attackType) {
        1 -> "Fuzzy Attack Detected"
        2 -> "Replay Attack Detected"
        3 -> "Spoofing Attack Detected"
        4 -> "Flooding Attack Detected"
        else -> "Unknown Attack"
    }
    Surface(color = Color(0xFFD32F2F), modifier = Modifier.fillMaxWidth()) {
        Text("$label / score=${score.format2()}", color = Color.White, modifier = Modifier.padding(12.dp))
    }
}
```

### Node A service unit

`/etc/systemd/system/ecu-node-a.service`:

```ini
[Unit]
Description=Capstone Node A ECU
After=network-online.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/Capstone-proj
ExecStart=/home/deploy/Capstone-proj/adaptive_ecu/build/adaptive_ecu --interface can0 --secoc=on --ids=on --sensor-mode profile_csv
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable ecu-node-a.service
sudo systemctl start ecu-node-a.service
systemctl is-active ecu-node-a.service
journalctl -u ecu-node-a.service -f
```

### SSH deploy

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ./deploy_key
ssh-copy-id -i deploy_key.pub deploy@<RPi4-IP>
ssh deploy@<RPi4-IP> "echo ok"
```

`/etc/sudoers.d/deploy-ecu`:

```text
deploy ALL=(root) NOPASSWD: /bin/systemctl restart ecu-node-a.service, /bin/systemctl status ecu-node-a.service
```

### CI Stage 4

```yaml
  stage4-ssh-deploy:
    runs-on: ubuntu-22.04
    needs: [stage1-static-analysis, stage2-arm64-build, stage3-qemu-test]
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Configure SSH
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.RPI_SSH_KEY }}" > ~/.ssh/id_ed25519
          chmod 600 ~/.ssh/id_ed25519
          ssh-keyscan -H "${{ secrets.RPI_HOST }}" >> ~/.ssh/known_hosts
      - name: Deploy and restart
        run: |
          rsync -avz ./ deploy@${{ secrets.RPI_HOST }}:/home/deploy/Capstone-proj/
          ssh deploy@${{ secrets.RPI_HOST }} "sudo systemctl restart ecu-node-a.service"
          ssh deploy@${{ secrets.RPI_HOST }} "systemctl is-active ecu-node-a.service"
```

### health_check.sh

```bash
#!/usr/bin/env bash
set -euo pipefail
SERVICE="${1:-ecu-node-a.service}"
for i in 1 2 3 4 5; do
  if systemctl is-active --quiet "$SERVICE"; then
    echo "PASS: $SERVICE is active (attempt $i)"
    exit 0
  fi
  sleep 2
done
echo "FAIL: $SERVICE is not active"
systemctl status "$SERVICE" --no-pager
exit 1
```

### IT-001~005

| IT | 공식 TC | IVI 수행 |
|---|---|---|
| IT-001 | TC-INT-001 | Node B dashboard에서 BMS data 표시 확인 |
| IT-002 | TC-INT-003 | Fail-safe CRITICAL dialog 확인 |
| IT-003 | TC-INT-002 | SecOC verify SUCCESS 로그 |
| IT-004 | TC-INT-002 | `ERR_HMAC_VERIFY_FAIL`, 데이터 갱신 없음 |
| IT-005 | TC-INT-004 | 3초 내 AlertBanner |

### M4 완료 기준

- [ ] DashboardScreen/FailSafeIndicator/AlertBanner 완성
- [ ] TC-IVI-006 (AlertBanner 공격 유형 텍스트 표시) 통과
- [ ] TC-IVI-007 (CRITICAL 풀스크린 Dialog) 통과
- [ ] CI Stage 4 배포와 health check 성공
- [ ] IT-001~005 전부 Pass
- [ ] M4 동작 영상 촬영
- [ ] `latency_results.csv` 1차 생성
- [ ] `v0.4.0` 태그 생성

---

## 9. M5 (10월) — 성능 최적화와 UI 개선

### 목표

e2e latency를 측정하고 UI/파이프라인 병목을 줄인다. ECU Ablation 실험과 충돌하지 않게 측정 시간을 분리한다.

### latency 측정

```python
#!/usr/bin/env python3
import argparse
import csv
import statistics
import time

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="latency_raw.csv")
    parser.add_argument("--output", default="latency_results.csv")
    args = parser.parse_args()

    samples = []
    with open(args.input, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            samples.append(float(row["latency_ms"]))

    avg = statistics.mean(samples)
    p95 = statistics.quantiles(samples, n=100)[94]
    p99 = statistics.quantiles(samples, n=100)[98]
    mx = max(samples)

    with open(args.output, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["samples", "avg_ms", "p95_ms", "p99_ms", "max_ms"])
        w.writerow([len(samples), avg, p95, p99, mx])

    print(f"avg={avg:.2f}ms p95={p95:.2f}ms p99={p99:.2f}ms max={mx:.2f}ms")

if __name__ == "__main__":
    main()
```

측정 절차:

```bash
# Node A 정상 ECU 실행
./adaptive_ecu --interface can0 --secoc=on --ids=on --sensor-mode profile_csv

# Node B에서 10분 이상 capture
python3 ivi_platform/scripts/measure_latency.py --input latency_raw.csv --output latency_results.csv
cat latency_results.csv
```

### 최적화 체크리스트

| 병목 | 조치 |
|---|---|
| CAN read thread 지연 | blocking read + 전용 thread 유지 |
| parser allocation | frame별 동적 할당 제거 |
| Binder update 과다 | 같은 값 반복 update debounce |
| Compose recomposition 과다 | UI state 최소화 |
| 로그 과다 | release/demo 모드에서 debug log 축소 |
| CPU governor | RPi4 performance mode |

```bash
sudo apt install -y cpufrequtils
sudo cpufreq-set -g performance
```

### M5 완료 기준

- [ ] latency avg `≤50ms`, max `≤100ms` 목표 확인
- [ ] AlertBanner 공격 유형별 표시 개선
- [ ] SocGauge warning/critical 색상 확정
- [ ] ECU Ablation 실험 시간과 IVI latency 측정 시간 분리
- [ ] IVI 담당 ADR 최종화: ADR-004(HIDL vs AIDL), ADR-006(QEMU user-mode), ADR-007(Docker 크로스컴파일), ADR-010(Plan B 전환 근거)
- [ ] `v0.5.0` 태그 생성

---

## 10. M6 (11월) — SDD-IVI, README, Coverage, CICD_SPEC

### 목표

IVI 설계 문서와 CI/CD 문서를 최종화하고, 프로젝트 README를 작성한다.

### SDD-IVI 구성

```markdown
# SDD-IVI: IVI Software Design Document

## 1. 문서 개요
목적, 범위, 참조 문서

## 2. 시스템 아키텍처
CAN -> HAL -> Service -> ViewModel -> Compose Dashboard

## 3. 모듈 상세 설계
### 3.1 HAL Layer
### 3.2 Service Layer
### 3.3 App Layer
### 3.4 SecOC Verifier

## 4. 데이터 흐름
0x100/0x101/0x102/0x103/0x200 처리 흐름

## 5. 에러 처리
CAN timeout, HMAC fail, replay, service death

## 6. 테스트 케이스 매핑
TC-IVI, TC-INT, TC-PERF
```

### README 템플릿

```markdown
# AUTOSAR 계층 기반 IVI-ECU 통합 플랫폼

## 프로젝트 개요
RPi4 2대를 Node A ECU와 Node B IVI로 구성하고 CAN/SecOC/IDS를 end-to-end 구현한다.

## 시스템 아키텍처
Node A ECU -> CAN Bus -> Node B HAL -> Service -> Dashboard

## 빌드 방법
### Node A
cmake -S adaptive_ecu -B adaptive_ecu/build && cmake --build adaptive_ecu/build

### Node B
./gradlew build

## 실험 결과
SecOC + IDS Ablation Study, e2e latency

## 문서
ICD, SRS, SDD-ECU, SDD-IVI, TEST_PLAN, TARA, CICD_SPEC
```

### Coverage/CI 확인

```bash
# C++ native/hal tests
cd ivi_platform/build
ctest --output-on-failure

# Android/Kotlin tests
cd ivi_platform
./gradlew test

# GitHub Actions: Stage 1~4 녹색 확인
```

### M6 완료 기준

- [ ] `docs/SDD-IVI.md` 완성
- [ ] `docs/CICD_SPEC.md` 완성 또는 최신화
- [ ] README에 architecture/build/result/document 링크 포함
- [ ] CI Stage 1~4 전체 녹색
- [ ] coverage gate 통과
- [ ] `v0.6.0` 태그 생성

---

## 11. M7 (12월) — 안정성, CI 최종 점검, 교차 검토

### 목표

장시간 운행 안정성을 확인하고 문서/구현/ICD 불일치를 제거한다.

### AddressSanitizer

```cmake
option(ENABLE_ASAN "Enable AddressSanitizer" OFF)
if(ENABLE_ASAN)
  add_compile_options(-fsanitize=address -fno-omit-frame-pointer)
  add_link_options(-fsanitize=address)
endif()
```

```bash
cmake -S ivi_platform -B ivi_platform/build-asan -DENABLE_ASAN=ON
cmake --build ivi_platform/build-asan
ctest --test-dir ivi_platform/build-asan --output-on-failure
```

### 24시간 안정성 테스트

```bash
# Node A
./adaptive_ecu --interface can0 --secoc=on --ids=on --sensor-mode profile_csv

# Node B
# Dashboard 실행 후 별도 terminal
while true; do
  date
  ps -eo pid,comm,rss,%cpu,%mem | grep -E "vehicle|dashboard|adaptive_ecu" || true
  ip -details -statistics link show can0 | grep -E "errors|dropped|overruns" || true
  sleep 3600
done | tee stability_24h.log
```

확인:

- [ ] 프로세스 생존
- [ ] RSS 단조 증가 없음
- [ ] service restart 없음
- [ ] CAN error count 과도 증가 없음
- [ ] dashboard 값 갱신 지속

### 문서 교차 검토

| 검토 항목 | 담당 |
|---|---|
| ICD byte layout과 `can_parser.cpp` 일치 | 팀원A가 IVI 코드 리뷰 |
| `secoc_verifier.cpp`와 ECU `secoc_module.cpp` input 일치 | 양측 |
| SDD-IVI와 실제 service/UI 구조 일치 | 팀원B |
| TEST_PLAN TC와 실제 test 이름 추적 가능 | 양측 |
| README 실행 명령이 최신 | 팀원B |

### 최종 통합 테스트

```bash
# IT-001
# Node A ECU 실행, Node B logcat/dashboard 확인

# IT-002
# Node A에서 SOC=4.5% 시뮬레이션, Node B CRITICAL dialog 확인

# IT-003
# 동일 key 배포, SecOC verify SUCCESS 확인

# IT-004
# Node A key mismatch 또는 가짜 0x102 주입, ERR_HMAC_VERIFY_FAIL 확인

# IT-005
# Flooding 공격, 3초 내 AlertBanner 확인
```

### M7 완료 기준

- [ ] 24시간 또는 합의된 안정성 테스트 pass
- [ ] CI Stage 1~4 최종 녹색
- [ ] ICD↔parser 불일치 0건
- [ ] IT-001~005 재검증 pass
- [ ] TC-PERF-001~003 최종 수치 기록
- [ ] `v0.7.0` 태그 생성

---

## 12. M8 (1월) — 데모, 발표, 최종 제출

### 데모 사전 준비

```bash
# Node A
ip link show can0
systemctl is-active ecu-node-a.service || sudo systemctl start ecu-node-a.service

# Node B
adb devices            # Plan A
adb logcat -s VehicleHAL
# 또는 Plan B dashboard 실행
```

### 데모 시나리오 A: 정상 동작

| 단계 | 설명 | IVI 확인 |
|---|---|---|
| 1 | ECU profile_csv 실행 | dashboard 값 갱신 |
| 2 | SOC/전압/전류/온도 표시 | 100ms 주기 update |
| 3 | SOC 15% | warning color |
| 4 | SOC 3~4.5% | CRITICAL dialog |

### 데모 시나리오 B: 공격과 방어

| 단계 | 설명 | IVI 확인 |
|---|---|---|
| 1 | SecOC off + spoofing | 가짜 SOC 표시 위험성 |
| 2 | SecOC on + spoofing | HMAC fail, 데이터 갱신 없음 |
| 3 | Flooding attack | AlertBanner 3초 내 표시 |
| 4 | 공격 중단 | 정상 상태 복귀 |

### IVI 발표 슬라이드

| 슬라이드 | 핵심 메시지 | 증적 |
|---|---|---|
| IVI 아키텍처 | HAL -> Service -> Dashboard | 구조도 |
| CAN parser | ICD 기반 byte-level parser | TC-IVI-002 |
| SecOC verifier | ECU vector 검증 | HMAC test |
| Dashboard UI | SOC/fail-safe/alert 표시 | demo screenshot |
| CI/CD | Stage 1~4 pipeline | Actions green |
| 안정성/성능 | latency, 24h test | CSV/log |

### GitHub 최종 정리

```bash
git tag --list
# 기대:
# v0.1.0
# v0.2.0
# v0.3.0
# v0.4.0
# v0.5.0
# v0.6.0
# v0.7.0
# v1.0.0
```

Release `v1.0.0` 첨부:

- [ ] 발표 자료 PDF
- [ ] 최종 보고서
- [ ] demo video link
- [ ] `results_summary.csv`
- [ ] latency results
- [ ] 주요 그래프

### M8 완료 기준

- [ ] 정상/공격 데모 모두 재현
- [ ] IVI 발표 슬라이드 완성
- [ ] README/SDD-IVI/CICD_SPEC 최신
- [ ] 리허설 3회 완료
- [ ] `v1.0.0` Release 작성

---

## 13. ECU 팀 연계 지점 총정리

| 시점 | IVI가 받을 것 | IVI가 제공할 것 |
|---|---|---|
| M1 | ICD CAN layout | HIDL/HAL 타입 피드백 |
| M2 | `0x100` sample payload | HAL Mock parser 결과 |
| M3 | SecOC test vector | verifier 결과 |
| M4 | `0x101`, `0x200` live frame | Dialog/Alert UI |
| M5 | Ablation 실험 일정 | latency 측정 시간 분리 |
| M6 | SDD-ECU 초안 | IVI 관점 리뷰 |
| M7 | 최종 ECU build | parser/ICD 교차 검토 |
| M8 | demo script | 화면/로그/영상 증적 |

---

## 14. 실패 시 우회 전략

| 문제 | 즉시 조치 | 최종 조치 |
|---|---|---|
| AOSP sync 실패 | `repo sync -j4` 재시도 | 네트워크/디스크 확인 |
| AOSP boot 실패 | M2 말 Plan B 전환 | ADR-010 작성 |
| HAL parser 불일치 | ICD 기준 parser 수정 | ECU와 sample payload 재검증 |
| SecOC MAC 불일치 | Python vector로 비교 | input order/key/counter 확인 |
| AlertBanner 미표시 | `candump`으로 `0x200` 수신 확인 | HAL -> Service -> UI 경로 분리 디버깅 |
| CI ARM64 실패 | Docker 안에서 수동 빌드 | toolchain path 수정 |
| SSH 배포 실패 | ssh/known_hosts/secret 확인 | deploy user 권한 수정 |
| latency 초과 | 병목 구간 측정 | parser/log/UI update 최적화 |

---

## 15. 최종 셀프 QA

### 코드/플랫폼

- [ ] `ivi_platform/`가 표준 구조로 존재한다.
- [ ] Plan A 또는 Plan B가 명확히 결정되어 문서화되어 있다.
- [ ] CAN parser가 `0x100`, `0x101`, `0x102`, `0x103`, `0x200`을 ICD대로 처리한다.
- [ ] SecOC verifier가 ECU vector를 통과한다.
- [ ] Service와 dashboard가 reconnect/restart 상황을 견딘다.

### 테스트

- [ ] TC-IVI-001~008 결과 기록
- [ ] TC-INT-001~004 결과 기록
- [ ] TC-PERF-001~003 결과 기록
- [ ] TC-CI-001~006 결과 기록
- [ ] IT-001~005 결과 표 작성

### CI/CD

- [ ] Stage 1 cppcheck 녹색
- [ ] Stage 2 ARM64 build 녹색
- [ ] Stage 3 QEMU test 녹색
- [ ] Stage 4 SSH deploy/health check 녹색
- [ ] required check가 branch protection에 등록됨

### 문서/데모

- [ ] SDD-IVI 최신
- [ ] CICD_SPEC 최신
- [ ] README 최신
- [ ] latency/stability 결과 보관
- [ ] 정상/공격 데모 영상 백업

---

## 16. 한 줄 실행 순서

```text
GitHub 인프라
-> M1 AOSP/Docker/HIDL/CI Stage 1
-> M2 HAL Mock/AOSP boot/Plan A-B
-> M3 Parser/HAL/Service/Dashboard/SecOC verifier
-> M4 Alert UI/CI Stage 4/IT-001~005
-> M5 Latency/UI 최적화
-> M6 SDD-IVI/CICD_SPEC/README
-> M7 안정성/교차검토/최종성능
-> M8 데모/발표/v1.0.0
```
