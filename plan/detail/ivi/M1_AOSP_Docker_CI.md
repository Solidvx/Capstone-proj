# IVI M1 — AOSP 환경, Docker ARM64, HIDL 초안, CI Stage 1

> **상태(2026-09-22)**: ADR-010의 Qt Plan B 활성화로 이 문서의 Android/AOSP 실행 절차는 현 제출 범위에서 superseded된 역사 자료다. 현재 작업은 [IVI 계획](../../IVI.md)과 [Plan B 전환 계획](../../IVI_PLAN_B_전환계획.md)을 따른다.


## 현재 실행 진입점 — Qt Plan B

이 파일의 이전 M단계 절차·명령·체크리스트는 역사 자료이며 현재 완료 판정에 직접 사용하지 않는다. 현행 작업은 [IVI M1~M8 매핑](../../IVI.md#4-m1m8-마일스톤)과 [Qt P0~P6 실행 계획](../../IVI_PLAN_B_전환계획.md#3-단계별-실행-계획)을 따른다. Qt 관련 과거 대안도 현재 채택 구조와 다를 수 있으므로 D-Bus/Flutter를 추가 요구하지 않는다. 공식 요구·계약·시험은 SRS/ICD/TEST_PLAN이 원본이다.

---


> **예시 상태**: 코드·명령은 별도 검증 표시가 없으면 작성 골격·예정 절차다. 실행 전 생성할 파일·의존성·플랫폼을 확인한다. [공동 규약](../common/00_협업_규약.md)의 문서·예시 사용 규칙을 따른다.

> 상위 계획: [IVI.md](../../IVI.md) · 공동 절차: [00_협업_규약](../common/00_협업_규약.md) · 인계: [01_연계_의존성](../common/01_연계_의존성.md)
> 원본: `_archive/IVI.md` M1, `_archive/IVI_최종_실행계획서.md` §5

---


<a id="security-integration"></a>
## 현행 과제에 병합한 보안 수행·인수 조건 — Q2 송신 환경 준비

이 절은 2026-09-09 보안 상세 계획을 기존 단계에 반영한 실행 조건이다. 초기 보안 보강 절과 함께 적용하며 제품 실행 완료 기록은 아니다. 상세 규칙은 [메시지·상태 규약](../../../docs/development/security/인증이벤트_메시지_상태규약.md)과 [송신·큐·실패 정책](../../../docs/development/security/인증이벤트_메시지_상태규약.md#planning-final)을 참조한다.

**선행 조건:** 기존 AOSP 후보 revision·HAL 빌드 경로와 ECU M1 수신 환경을 확인한다. 서버 소스 가져오기는 기존 사용자 담당 범위를 유지한다.

**수행:** 선택 AOSP에서 native TLS 링크·HAL 도메인의 소켓/키 읽기 권한과 양측 유선 연결을 검증할 환경을 준비한다. 정상·인증서 오류·권한 거부·시각 준비 실패를 기존 환경 인수에 포함한다.

**실패 대응·인계:** 빌드/접근 결과·설정 버전·한계를 공동 인계와 IVI M3에 전달한다. SELinux나 인증서 검증을 끄지 않으며 장비 부재는 미검증으로 기록한다.

**완료 확인:**

- [ ] 대상 revision·TLS/권한 가능성·ECU 연결 인계 조건을 기록했다.
- [ ] 기존 공식 시험 결과와 추가 보조 시나리오의 실제 증거·미검증 사유를 구분했다.


## 1. 목적과 범위

AOSP 빌드 환경을 준비하고, ARM64 크로스컴파일 Docker 이미지와 CI Stage 1을 만든다. `ivi_platform/` 골격과 HIDL 인터페이스 초안을 세우고, ECU 담당자와 ICD를 확정해 M2부터 독립 개발이 가능하게 한다.

| 항목 | 값 |
|---|---|
| 연결 요구사항 | FR-IVI-001~007 초안, FR-CI-001~002 |
| 연결 시험 | TC-CI-001, TC-CI-002 |
| 산출물 | AOSP 소스, `Dockerfile.arm64`, `toolchain-aarch64.cmake`, `ivi_platform/` 골격, `IVehicleHal.hal`, CI Stage 1 |
| 태그 | `v0.1.0` |

### 주차별 작업

**일정 재산정 (2026-09-08):** A-1~A-13 답변 접수 완료. 개인 Windows PC는 편집·앱 개발·장비 연결, 내부망 서버는 전체 AOSP 빌드를 담당한다. 서버 자원은 충분하다는 사용자 확인을 채택하며 사양 재질문은 종료한다. 서버 OS·도구/다운로드 조건은 실제 착수 점검이다. 전체 시연 마감 2026-09-18과 9/9~18 D1~D10 배분은 [Android 환경설정 §4](../../../docs/development/environment/안드로이드_환경설정.md)를 따른다. 사용자 정의 HIDL을 대상으로 하며 표준 VHAL·CarService는 요구하지 않는다. 아래 기존 주차표를 10일 일정의 달성 근거로 사용하지 않는다.

| 주차 | IVI 작업 | ECU/공동 연계 |
|---|---|---|
| 1주차 | 빌드 서버 준비, Docker 설치, `repo sync` 시작 | GitHub 인프라 ([00_협업_규약](../common/00_협업_규약.md)) |
| 2주차 | `Dockerfile.arm64`, toolchain, `ivi_platform/` 골격 PR | 골격 리뷰 |
| 3주차 | `IVehicleHal.hal` 초안, CI Stage 1 | ICD 리뷰 |
| 4주차 | FR-IVI/FR-CI, ADR-004/007 | ICD 확정, `v0.1.0` |

---

## 2. 선행조건과 현재 구현 상태

**현재 구현 상태 (확인 기준일 2026-09-05, 실제 파일 확인)**

| 대상 | 상태 |
|---|---|
| `ivi_platform/` | **README 골격만 존재, 제품 소스 없음** |
| `Dockerfile.arm64`, `toolchain-aarch64.cmake` | **없음** |
| `.github/workflows/` | **없음** |
| AOSP 소스 | 저장소 밖. 확인 불가 |
| `docs/ICD.md` §3 HAL API | **존재** — HIDL 정본이 여기 있다 |
| `docs/SRS.md`, `docs/ADR.md`, `docs/CICD_SPEC.md` | **존재** |

> **IVI 영역은 전부 신규 구현이다.** ECU와 달리 "이미 있는지 확인"할 코드가 없다. 다만 `docs/CICD_SPEC.md`가 4단계 CI를 이미 기술하므로, 구현은 그 명세에 맞춘다. 명세와 다르게 만들 거라면 명세를 먼저 고친다.

**하드웨어·환경 요구**

| 항목 | 최소 |
|---|---|
| OS | Ubuntu 22.04 LTS (64-bit) |
| 디스크 | **200GB 이상** (AOSP 소스 ~80GB + 빌드 산출물 ~80GB + 여유) |
| RAM | 16GB 이상 (32GB 권장) |
| CPU | 8코어 이상 권장 |
| 네트워크 | 안정적 유선 (70GB+ 다운로드) |
| 초기 sync | 4~8시간 이상 |

```bash
lsb_release -a
nproc
free -h
df -h /home        # 200GB 이상 여유 확인
```

> 스펙이 부족하면 학교 서버나 클라우드 VM(예: GCP n2-standard-8)을 검토한다. 여기서 막히면 [M2](M2_HALMock_PlanAB.md)의 Plan A/B 판단이 앞당겨진다.

### 통합 시 해소한 충돌

| 항목 | 세대A | 세대B | 채택 |
|---|---|---|---|
| HIDL 패키지·구조체 | `package vehicle.hal@1.0`, `VehicleData` 11필드 | `vendor.capstone.vehicle@1.0`, 13필드 | **세대A** — `docs/ICD.md` §3.1이 정본이고 세대A와 일치한다 |
| HAL 인터페이스 | `getVehicleData()` / `registerCallback()` / `unregisterCallback()` | `getLatestData()` / `subscribe()` | **세대A** (ICD §3.1) |
| 콜백 | 3종(`onVehicleDataChanged`, `onSecurityAlert`, `onFailSafeTransition`) | 1종 | **세대A** (ICD §3.1) |
| Dockerfile 내용 | arm64 아키텍처 등록 + GoogleTest 크로스빌드 | `qemu-user-static` + cppcheck + lcov | **병합** — 3.4에 둘 다 반영 |
| CI cppcheck 대상 | 파일 존재 여부를 `find`로 확인 후 실행 | `ivi_platform/hal` 포함 (**현재 없는 경로**) | **세대A의 가드 방식** — 없는 경로를 넣으면 CI가 바로 실패한다 |
| AOSP 경로 | `~/aosp` | `~/aosp-rpi4` | 하나로 통일. 아래는 `~/aosp-rpi4` |

---

### 대상 환경 확인 게이트

Android 환경 인터뷰는 종료됐고 서버를 주 빌드 장비로 사용한다. [환경설정 §6](../../../docs/development/environment/안드로이드_환경설정.md)에 Raspberry Vanilla Android 16 후보와 소스 고정·HIDL·CAN·DSI 검증 순서를 기록했다. 아래 Android 13 revision·JDK·용량·lunch·device tree·flash 명령은 과거 예시이며 현재 선정 결과가 아니다. 후보의 실제 도구와 대조하며 최종 채택이나 Plan B 전환은 자동 확정하지 않는다.

선택 환경의 manifest/revision·kernel/device tree·toolchain/JDK/SDK·저장공간·빌드/flash 방법·artifact hash를 확보한다. 대상 디스크와 이미지 종류는 실제 환경에서 확인한다. 부팅→ADB→can0→HAL 등록/VINTF/init/권한→Service Binder→앱 표시를 순차 검증한다. can0 존재만으로 HAL 송수신·앱 접근을 합격시키지 않는다.

host Linux 코어, Node A Linux ARM64, Node B Android HAL/framework/app의 산출물·sysroot·라이브러리 ABI를 구분한다. Linux ARM64 빌드 성공은 Android 실행 성공이 아니다. Mock은 실제 HAL 등록·권한·렌더링의 대체 증거가 아니다.

## 3. 수행 절차

### 3.1 필수 패키지

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git-core gnupg flex bison build-essential \
  zip curl zlib1g-dev libc6-dev-i386 x11proto-core-dev \
  libx11-dev lib32z1-dev libgl1-mesa-dev libxml2-utils \
  xsltproc unzip fontconfig python3 python3-pip openjdk-11-jdk
```

`repo` 도구:

```bash
mkdir -p ~/bin
curl https://storage.googleapis.com/git-repo-downloads/repo > ~/bin/repo
chmod a+x ~/bin/repo
echo 'export PATH=~/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
repo version

git config --global user.name "<이름>"
git config --global user.email "<이메일>"
```

### 3.2 Docker 설치

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

docker --version        # 기대: Docker version 24.x.x 이상
docker run hello-world  # 기대: "Hello from Docker!"
```

### 3.3 AOSP repo sync

소스 확보는 사용자 담당이다. 실행 정본은 [Android 환경설정 §7](../../../docs/development/environment/안드로이드_환경설정.md)의 고정 후보 manifest/revision·lunch·kernel 절차다. 과거 Android 13 tag와 임의 device tree를 섞는 명령은 사용하지 않는다. 실제 repo 종료 코드·resolved manifest·빌드 로그·이미지 hash를 인계받는다. 다운로드 용량이나 `Syncing ... 100%` 한 줄만으로 성공을 판정하지 않는다. 사용자 정의 HIDL과 MCP2515·키 권한 검증은 기본 이미지 빌드 후 별도 인수한다.

### 3.4 Dockerfile.arm64 + toolchain

`Dockerfile.arm64` (프로젝트 루트):

```dockerfile
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# ARM64 패키지 소스 (기본 미러에는 arm64 바이너리가 없다)
RUN dpkg --add-architecture arm64 && \
    sed -i 's|^deb |deb [arch=amd64] |g' /etc/apt/sources.list && \
    echo "deb [arch=arm64] http://ports.ubuntu.com/ubuntu-ports jammy main restricted universe multiverse" \
      >> /etc/apt/sources.list && \
    echo "deb [arch=arm64] http://ports.ubuntu.com/ubuntu-ports jammy-updates main restricted universe multiverse" \
      >> /etc/apt/sources.list

RUN apt-get update && apt-get install -y \
    build-essential cmake ninja-build git pkg-config \
    gcc-aarch64-linux-gnu g++-aarch64-linux-gnu binutils-aarch64-linux-gnu \
    qemu-user-static cppcheck lcov python3 python3-pip \
    libssl-dev:arm64 \
    && rm -rf /var/lib/apt/lists/*

COPY toolchain-aarch64.cmake /opt/toolchain-aarch64.cmake

# GoogleTest ARM64 크로스빌드 (CI Stage 3에서 시험 실행에 필요)
RUN git clone --depth=1 https://github.com/google/googletest /tmp/googletest && \
    cmake -S /tmp/googletest -B /tmp/gtest_build \
          -DCMAKE_TOOLCHAIN_FILE=/opt/toolchain-aarch64.cmake \
          -DCMAKE_INSTALL_PREFIX=/usr/aarch64-linux-gnu && \
    cmake --build /tmp/gtest_build && \
    cmake --install /tmp/gtest_build && \
    rm -rf /tmp/googletest /tmp/gtest_build

WORKDIR /workspace
```

`toolchain-aarch64.cmake` (프로젝트 루트):

```cmake
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

set(CMAKE_C_COMPILER   aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)
set(CMAKE_AR           aarch64-linux-gnu-ar)
set(CMAKE_RANLIB       aarch64-linux-gnu-ranlib)

set(CMAKE_FIND_ROOT_PATH /usr/aarch64-linux-gnu)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
```

빌드와 검증:

```bash
docker build -f Dockerfile.arm64 -t capstone-arm64 .

docker run --rm -v "$(pwd)":/workspace capstone-arm64 bash -c "
  cmake -S /workspace/adaptive_ecu -B /workspace/build-arm64 \
        -DCMAKE_TOOLCHAIN_FILE=/opt/toolchain-aarch64.cmake \
        -DECU_BUILD_TESTS=ON &&
  cmake --build /workspace/build-arm64"

file build-arm64/adaptive_ecu
# 기대: ELF 64-bit LSB executable, ARM aarch64, ...
```

> ECU 빌드는 `OpenSSL::Crypto`와 `Threads`를 요구한다. `libssl-dev:arm64`가 반드시 들어가야 링크된다.

### 3.5 ivi_platform 골격

디렉토리 생성만으로 이 작업을 완료하지 않는다. 다음 파일은 모두 **신규 생성 과제**이며 현재 존재한다고 가정하지 않는다.

| 산출물 | 책임·수행 | 검증 |
|---|---|---|
| `ivi_platform/CMakeLists.txt` | IVI: host에서 빌드 가능한 parser/core 라이브러리·CTest·GoogleTest 등록; Android 의존 코어와 분리 | 빈 폴더가 아닌 최소 parser 시험 1개 빌드·실행, 시험 수 0이면 실패 |
| `ivi_platform/app/settings.gradle.kts`, `build.gradle.kts`, Gradle wrapper·manifest·소스셋 | IVI: 실제 도구 버전 조합·Compose·coroutines·JUnit·기기 시험 의존성 기록, wrapper 생성 | 저장소 루트 기준 app에서 `./gradlew tasks`, `test`와 최소 앱 assemble 성공 |
| HIDL `.hal`, `Android.bp`, 서비스 진입점·init rc·VINTF 항목 | IVI: ICD 정본에서 타입 생성, 빌드 모듈·인스턴스 이름·시작 경로 명시 | 대상 AOSP 트리에서 모듈 빌드, HAL 등록 확인 |
| 프레임워크 서비스·manager·등록 변경 | IVI: SystemServer 생명주기, SystemServiceRegistry의 `vehicle_data`, 권한·sepolicy·죽은 Binder 재연결 구현 | 실제 테스트 앱의 getSystemService 성공과 재부팅 후 자동 연결 |
| 개발 환경 manifest | IVI: AOSP revision·device tree·도구/SDK/JDK·의존성·재현 명령과 변경 파일 경로 | 새 checkout에서 같은 생성·빌드 순서 재현 |

M1에서는 host core와 최소 앱을 빌드하고 Android 등록 파일의 생성 위치·작업 경계를 확정한다. 실제 HAL→Service→앱 연결은 M3에서 검증한다. AOSP 전용 서비스 시험은 host Gradle 시험으로 대체하지 않는다. M2의 Plan B 전환 승인 시 Qt용 빌드·D-Bus adapter·기동 시험을 별도로 인수한다.


```bash
mkdir -p ivi_platform/{hal/mock,service,app/{data,test},test}
```

```text
ivi_platform/
├── hal/              # HAL 레이어 (C++)
│   ├── IVehicleHal.hal
│   ├── IVehicleHalCallback.hal
│   └── mock/         # VehicleHalMock
├── service/          # Android SystemService (Java)
├── app/              # Jetpack Compose 앱 (Kotlin)
│   ├── data/         # VehicleRepository
│   └── test/         # Compose UI 시험
└── test/             # HAL/Service 단위 시험
```

```bash
git switch develop && git pull origin develop
git switch -c feat/ivi-skeleton
git add ivi_platform/
git commit -m "feat(ivi): ivi_platform 디렉토리 골격 생성"
git push origin feat/ivi-skeleton
# GitHub PR (base=develop) → ECU 담당자 리뷰 요청
```

### 3.6 HIDL 인터페이스 초안

**`docs/ICD.md` §3.1이 정본이다.** 아래는 그것을 그대로 옮긴 것이며, 임의로 필드를 바꾸면 ICD 변경 게이트 대상이다.

`ivi_platform/hal/IVehicleHal.hal`:

```
package vehicle.hal@1.0;

struct VehicleData {
    float soc;              // 배터리 잔량 (%), 0.0 ~ 100.0
    float soh;              // 배터리 건강도 (%), 0.0 ~ 100.0
    float voltage;          // 팩 전압 (V)
    float current;          // 충방전 전류 (A), 양수=충전
    int8_t temperature;     // 셀 온도 (°C)
    uint8_t failSafeState;  // 0=NORMAL, 1=WARNING, 2=CRITICAL, 3=SHUTDOWN
    uint8_t failSafeReason; // Fail-safe 전이 사유 코드 (ICD §1.3)
    bool attackDetected;    // IDS 공격 탐지 여부
    uint8_t attackType;     // 0=None, 1=Fuzzy, 2=Replay, 3=Spoofing, 4=Flooding
    float anomalyScore;     // IDS 이상 점수 (0.00 ~ 2.55)
    uint32_t timestamp;     // 데이터 수신 시각 (Unix epoch)
};

interface IVehicleHal {
    getVehicleData() generates (VehicleData data);
    registerCallback(IVehicleHalCallback callback) generates (bool success);
    unregisterCallback(IVehicleHalCallback callback) generates (bool success);
};
```

`ivi_platform/hal/IVehicleHalCallback.hal`:

```
package vehicle.hal@1.0;

interface IVehicleHalCallback {
    onVehicleDataChanged(VehicleData data);
    onSecurityAlert(uint8_t attackType, float anomalyScore, uint16_t suspectCanId);
    onFailSafeTransition(uint8_t prevState, uint8_t newState, uint8_t reason);
};
```

**ECU와 대조할 것** — 타입 폭과 부호가 CAN 레이아웃과 맞는지 확인한다.

- [ ] `temperature`는 `int8_t`. CAN에서는 offset +40된 `uint8`이므로 파서가 `raw - 40`으로 되돌린다
- [ ] `current`는 양수=충전. CAN은 int16 BE 2의 보수
- [ ] `suspectCanId`는 `uint16_t` BE
- [ ] `anomalyScore`는 CAN raw × 0.01

### 3.7 CI Stage 1 — 정적 분석

Stage 1: 정적 분석. 최초 저장소 연결·이벤트 기동과 분석 실패 전파를 TC-CI-001~002로 확인한다. 전체 설정·산출물·실패 조건은 [CI 참조](ref_CI파이프라인_명령모음.md) §1만 유지한다. 이 단계에서는 해당 Stage를 구현하고 실행 증적을 인계한다.

### 3.8 Android Studio (선택)

에뮬레이터로 Compose UI를 미리 확인하려면 설치한다. AOSP 빌드 자체에는 필요 없다.

```bash
tar -xzf android-studio-*.tar.gz -C ~/
~/android-studio/bin/studio.sh
```

1. Android SDK 13 (API 33) 설치
2. Kotlin 플러그인 활성화 확인
3. AVD Manager에서 Pixel 4a API 33 생성 후 실행 확인

### 3.9 SRS / ADR 초안

`docs/SRS.md`에 추가할 요구사항:

```markdown
## FR-IVI: IVI 플랫폼 기능 요구사항
| ID | 요구사항 | 검증 TC |
|---|---|---|
| FR-IVI-001 | Vehicle HAL이 CAN 프레임 수신 시 콜백 호출 | TC-IVI-001 |
| FR-IVI-002 | CAN ID별 파싱 정확도 (ICD §1.2~1.5) | TC-IVI-002 |
| FR-IVI-003 | VehicleDataService getSystemService 접근 | TC-IVI-003 |
| FR-IVI-004 | Binder IPC StateFlow 업데이트 | TC-IVI-004 |
| FR-IVI-005 | SOC 게이지 색상 로직 | TC-IVI-005 |
| FR-IVI-006 | 공격 탐지 AlertBanner 표시 | TC-IVI-006 |
| FR-IVI-007 | CRITICAL/SHUTDOWN 풀스크린 경고 | TC-IVI-007 |

## FR-CI: CI/CD 기능 요구사항
| ID | 요구사항 | 검증 TC |
|---|---|---|
| FR-CI-001 | PR/Push 시 자동 파이프라인 기동 | TC-CI-001 |
| FR-CI-002 | cppcheck 정적 분석 (Error 시 중단) | TC-CI-002 |
| FR-CI-003 | ARM64 크로스컴파일 산출물 | TC-CI-003 |
| FR-CI-004 | 커버리지 품질 게이트 (≥80%) | TC-CI-004 |
| FR-CI-005 | SSH 자동 배포 | TC-CI-005 |
| FR-CI-006 | Health Check | TC-CI-006 |
```

`docs/ADR.md`에 추가할 결정:

- **ADR-004 (HIDL vs AIDL)** — 결정과 근거의 정본은 [ADR-004](../../../docs/ADR.md#adr-004)다. 기존 HIDL 계약을 유지하며, 선택한 AOSP revision에서 `IVehicleHal.hal` 생성·서비스 등록·클라이언트 연결의 지원 여부를 M1에서 확인한다. 문서의 채택 결정과 대상 이미지의 빌드·동작 검증은 구분한다.
- **ADR-007 (Docker ARM64 크로스컴파일)** — 결정: Docker + `aarch64-linux-gnu` 툴체인. 근거: CI와 로컬 환경 일치, GitHub Actions `ubuntu-22.04` 러너에서 바로 사용 가능. 결과: `Dockerfile.arm64` + `toolchain-aarch64.cmake`

### 3.10 ICD 확정 참여

- [ ] ECU 담당자에게 HIDL `VehicleData` 타입 리뷰를 요청한다
- [ ] `docs/ICD.md`의 바이트 레이아웃과 파서 타입을 대조한다
- [ ] `0x200`은 Node A IDS가 송신하고 Node B가 표시한다는 ADR-009를 확인한다

---

## 4. 검증 명령과 합격 기준

```bash
docker --version && docker run hello-world
repo version
du -sh ~/aosp-rpi4

docker build -f Dockerfile.arm64 -t capstone-arm64 .
docker run --rm -v "$(pwd)":/workspace capstone-arm64 bash -c \
  "cmake -S /workspace/adaptive_ecu -B /workspace/build-arm64 \
     -DCMAKE_TOOLCHAIN_FILE=/opt/toolchain-aarch64.cmake && \
   cmake --build /workspace/build-arm64"
file build-arm64/adaptive_ecu

ls ivi_platform/hal/IVehicleHal.hal
```

| 기준 | 합격 조건 |
|---|---|
| AOSP | `repo sync` 완료, 에러 없음, ~80GB |
| Docker | 이미지 빌드 성공, ARM64 산출물 `file` 확인 |
| 골격 | `ivi_platform/` PR 머지 |
| HIDL | ICD §3.1과 필드·인터페이스 1:1 일치 |
| CI | Stage 1 녹색, required check 등록 |
| 문서 | FR-IVI/FR-CI, ADR-004/007 머지 |
| 태그 | `v0.1.0` |

---

## 5. 실패 시 대응과 우회

**Docker 권한 오류** (`permission denied ... docker daemon socket`)
```bash
sudo usermod -aG docker $USER
newgrp docker      # 또는 터미널 재시작
```

**repo sync 중 네트워크 끊김**
```bash
cd ~/aosp-rpi4
repo sync -c -j4 --no-tags --force-sync    # 이어받기 가능
```
스레드 수를 줄이면 성공률이 올라간다.

**디스크 용량 부족**
```bash
df -h /home
```
`--depth=1`은 이미 적용돼 있다. 더 줄일 방법이 없으므로 외부 디스크 마운트나 VM 디스크 증설이 필요하다. **여기서 막히면 [M2](M2_HALMock_PlanAB.md)의 Plan B 판단을 앞당긴다.**

**`libssl-dev:arm64` 설치 실패**
- `ports.ubuntu.com` 소스가 등록됐는지 확인한다 (3.4 Dockerfile 상단)
- 기존 `sources.list`의 amd64 항목에 `[arch=amd64]`를 붙이지 않으면 arm64 미러에서 amd64 패키지를 찾다가 실패한다

**GoogleTest 크로스빌드 실패**
```bash
docker run --rm -it capstone-arm64 bash
cmake -S /tmp/googletest -B /tmp/gtest_build -DCMAKE_TOOLCHAIN_FILE=/opt/toolchain-aarch64.cmake
```
오류 메시지에서 툴체인 경로와 컴파일러 이름을 확인해 수정한다.

**CI Stage 1 실패**
- `ivi_platform/hal`이 없으면 가드의 생략을 명시적으로 기록한다. 소스 없는 단계의 생략을 HAL 품질 검증 통과로 보고하지 않는다. 해당 단계 인수에서는 실제 대상 소스와 검사 결과가 필요하다.
- cppcheck 경고가 대량이면 지점 한정 억제(`--suppress=<id>:<file>`)를 쓴다. 전역 억제로 넓히지 않는다

---

## 6. 완료 체크리스트

- [ ] 빌드 서버 사양 확인 (디스크 200GB+)
- [ ] Docker 설치, `hello-world` 성공
- [ ] `repo sync` 완료, `~/aosp-sync.log` 에러 없음
- [ ] `Dockerfile.arm64` 빌드 성공
- [ ] ARM64 산출물 `file` 확인 (ELF 64-bit ARM aarch64)
- [ ] `ivi_platform/` 골격 PR 머지
- [ ] `IVehicleHal.hal` / `IVehicleHalCallback.hal` 작성, ICD §3.1과 일치
- [ ] CI Stage 1 녹색, `develop` required check 등록
- [ ] FR-IVI / FR-CI 초안 머지
- [ ] ADR-004 / ADR-007 머지
- [ ] ICD 확정 리뷰 참여
- [ ] `v0.1.0` 태그 생성


## 하드웨어·Android 실행 조건 검토 — 2026-09-07

현재 작업 폴더의 `ivi_platform/`에는 목적 안내 README만 있으며 AOSP 외부 트리와 대상 부팅은 확인하지 않았다. 보유 장비는 확인사항 §1에 RPi4 8GB·SanDisk 128GB·MCP2515/TJA1050 8MHz·레벨 컨버터·Touch Display 2로 기록됐다. Android A-1~14 답변은 접수 완료했다. 최신 후보·환경은 [Android 환경설정](../../../docs/development/environment/안드로이드_환경설정.md) §6~7을 따르며 장비 인수는 미완료다. 이 문서의 revision·빌드 명령·기동 경로는 해당 정보와 대조하기 전 확정 절차가 아니다.

| 순서 | 수행·증거 | 다음 단계 조건 |
|---|---|---|
| 1 환경 고정 | 선택 이미지/revision, 커널/device tree, build variant, ABI, 도구 버전, 이미지 hash와 빌드/설치 방법 기록 | 선택 환경 정보 확보; 다른 이미지나 Qt로 자동 전환하지 않음 |
| 2 부팅·접속 | 대상 보드 부팅·화면·ADB 식별·재부팅 상태 확인 | 빌드 성공과 보드 부팅 성공을 별도 기록 |
| 3 CAN 드라이버 | 해당 커널의 CAN raw·SPI 컨트롤러·MCP2515 지원과 실제 모듈 설정 확인 | can0의 존재뿐 아니라 반대 노드 수신·에러 상태 확인 |
| 4 HAL 빌드·등록 | ICD의 HIDL 타입과 승인된 다음 목표 필드, 모듈/인스턴스 이름, init·VINTF·설치 파티션·의존 라이브러리 대조 | 호스트 Mock 통과와 대상 ABI 빌드/등록을 구분 |
| 5 서비스 권한 | 실제 HAL 실행 UID/GID·SELinux 도메인에서 CAN 수신/송신, 필요한 키 접근, Binder 호출 확인 | shell에서 성공한 것을 서비스 성공으로 대체하지 않음 |
| 6 앱 연결 | HAL→Service→콜백→화면, 서비스 종료/재연결과 stale·sensorState 확인 | 단순 프로세스 생존이 아닌 실제 값·상태 반영 확인 |
| 7 통합 인수 | 공동 통합시험의 계약 버전·정상/변조/유실·재부팅 시험에 연결 | 세션 후보 최종 승인·양측 구현 전 새 세션 합격 주장 금지 |

VINTF의 제공/요구 manifest·matrix 정합은 [AOSP VINTF 문서](https://source.android.com/docs/core/architecture/vintf)를 참조하되 선택 Android 버전의 검사 도구를 확인한다. HIDL을 AIDL로 임의 전환하지 않는다. 선택 버전과 ICD의 HIDL이 충돌하면 실제 오류·영향·대안을 제시해 인터뷰한다.

Android는 [SELinux 정책](https://source.android.com/docs/security/features/selinux)을 적용한다. Node A root 서비스 승인을 Node B root 승인으로 확대하지 않는다. 서비스 권한·키 전달·도메인 정책은 선택 환경 확인 후 구체안으로 제시한다. permissive 전환이나 광범위 권한 부여로 실패를 숨기고 합격시키지 않는다. 로그에는 키·장비 접근 비밀을 기록하지 않는다.

이 단계에서는 flash·장비 명령·AOSP 빌드·의존성 설치를 실행하지 않았다. 장비별 명령과 대상 저장장치는 정보를 받은 뒤 검토한다. 미확정 정보를 이유로 문서 전체 정리를 중단하지 않고 Mock·계약·시험 설계는 진행한다.


### 보유 장비와 선택 Android의 호환성 인수표

| 확인된 장비 | Android에서 대조할 항목 | 미확인 시 보류 범위 |
|---|---|---|
| RPi4 Model B 8GB·microSD 128GB | 선택 이미지/revision의 보드 지원, 실제 부팅·저장장치 인식 | 이미지 기록·대상 부팅 완료 판정 |
| MCP2515/TJA1050 8MHz·SPI0 CE0·GPIO25 INT | 커널 CAN/SPI/MCP2515·device tree 설정, 실제 HAL 권한의 양방향 송수신 | CAN 및 새 세션 통합 인수 |
| 레벨 컨버터 노드당 2개 | 실제 SPI clock·IRQ·배선·오류 카운터 | 부하/시간/안정성 인수 |
| Touch Display 2 | 선택 커널의 DSI 표시·터치 입력·화면 방향, 실제 UI 렌더 | 화면/터치/e2e 지연 인수 |
| Node B Android | HIDL 생성·VINTF·SELinux·키 공급·앱 배포 | HAL/서비스 호환성 최종 판정 |

Node A Ubuntu의 config.txt/서비스 권한을 Android 실행 명령으로 복사하지 않는다. 128GB microSD 보유가 AOSP 빌드 환경을 뜻하지 않는다. 답변 완료된 Android 환경설정 §6~7의 후보·빌드 환경과 이 표를 대조하며 새 이미지를 임의 선정하지 않는다. 서버 자원 충분이라는 사용자 확인은 유지한다. 현재 판정은 장비 보유 확인, Android 호환성 미확인이다.


<a id="ivi-env-01"></a>
### IVI-ENV-01 — Plan 승계 과제

원문: [IVI.md](../../_archive/plan_20260908/IVI.md.txt)의 IVI-ENV-01. 실행 상태는 해당 역할의 진행 표·공동 인수 기록을 사용한다. 이 병합은 과제 실행 완료가 아니다.

선행·착수: COM-BASE-01의 착수 확인

보존한 수행·인수 조건: 소스/BSP/커널·manifest·타깃을 고정하고 이미지 빌드/부팅·ADB·CAN·화면/권한을 검증한다. 실패 원인·해결 시도·일정 영향으로 M2 플랫폼 관문에 인계하며 자동 전환하지 않는다.

현재 기준 적용: Android 13 고정/과거 M2 날짜 대신 승인된 후보·9/18 일정과 환경설정 적용. 본문의 공식 FR/TC·승인 정책·실패 대응을 함께 적용한다.
