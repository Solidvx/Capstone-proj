# 팀원B 실행 가이드 — 전체 8개월 단계별 수행 절차

> **프로젝트**: AUTOSAR 계층 기반 IVI-ECU 통합 플랫폼  
> **역할**: Node B — RPi4 Android 13 AOSP (또는 Plan B Ubuntu) / Java·Kotlin / IVI SW 플랫폼 / CI·CD  
> **참조 문서**: `docs/SDD-IVI.md` · `docs/ICD.md` · `docs/CICD_SPEC.md` · `docs/TEST_PLAN.md`  
> **목표**: 이 문서의 절차를 순서대로 따라하면 팀원B의 모든 작업을 완수할 수 있다.
>
> **관련 가이드**:
> - 공동 작업 (통합 테스트, 마일스톤 처리, 데모): `PLAN_공동.md`
> - 팀원A 작업과의 의존성 및 연계: `팀간_연계_분석.md`
> - 전체 가이드 네비게이션: `INDEX.md`

---

## 팀원B Issue 라벨 Quick Reference

> Issue 생성 시 아래 조합 사용. 라벨 정의·색상은 `PLAN_공동.md` "수행 절차 2: GitHub Labels 생성" 참조.

| 작업 유형 | 라벨 조합 (담당자 라벨 `IVI` 항상 포함) | 예시 |
|----------|---------------------------------|------|
| 새 기능 구현 (HAL/Service/UI) | `feat` + `IVI` | `[IVI] vehicle_hal_impl.cpp CAN 수신 스레드 구현` |
| HAL 보안 검증 모듈 | `feat` + `IVI` + `security` | `[IVI] secoc_verifier.cpp HAL 내부 HMAC 검증` |
| 버그 수정 | `bug` + `IVI` (+ `interface-change` ICD 영향 시) | `[IVI] AlertBanner 애니메이션 누락 수정` |
| 테스트 작성 | `test` + `IVI` | `[IVI] TC-IVI-005 SocGauge 색상 코드 테스트` |
| AOSP/Docker/CI 환경 | `chore` + `IVI` | `[IVI] AOSP repo sync + 빌드 환경 구성` |
| 동작 변경 없는 정리 | `refactor` + `IVI` | `[IVI] DashboardScreen.kt Composable 분리` |
| 문서 작업 | `docs` (+ `IVI` 도메인 한정 시) | `[IVI] SDD-IVI.md §3.5 Service 모듈 작성` |
| HIDL/D-Bus 인터페이스 변경 | `interface-change` + `docs` + `IVI` | `[ICD] §3 HAL API 변경 (Plan B 시 D-Bus 교체)` — `PLAN_공동.md` 5단계 워크플로 필수 |
| 진행 불가 (블로커) | 기존 라벨 + `blocked` | (블로커 발생 시 의존 Issue 번호 코멘트) |

---

## M1 (6월) — AOSP 환경 + Docker + CI

### 목표

AOSP 빌드 서버 구성, Docker 크로스컴파일 환경 구축, IVI 플랫폼 디렉토리 골격 생성, HIDL 인터페이스 초안 작성, GitHub Actions Stage 1(cppcheck) CI 파이프라인 설정.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | AOSP 빌드 서버 Ubuntu 22.04 준비 | 1시간 | SSH 접속 + `df -h` 200GB+ |
| 1 | 필수 패키지 설치 (repo, JDK 11 등) | 15분 | `repo version` + `java -version` |
| 1 | **Docker 설치** | 15분 | `docker run hello-world` 성공 |
| 1 | `repo init` + `repo sync` 시작 | 4~8시간 | sync 완료 후 80GB+ |
| 1 | Android Studio 설치 | 30분 | AVD 실행 성공 |
| 2 | AOSP sync 완료 확인 | — | `~/aosp-sync.log` 에러 없음 |
| 2 | `Dockerfile.arm64` 초안 | 1시간 | `docker build` 성공 |
| 2 | `toolchain-aarch64.cmake` 작성 | 30분 | Docker 내 ARM64 빌드 성공 |
| 2 | `ivi_platform/` 디렉토리 골격 생성 | 30분 | PR 생성 + 팀원A 리뷰 |
| 3 | `Dockerfile.arm64` 빌드 검증 | 1시간 | `file` → ARM aarch64 |
| 3 | `IVehicleHal.hal` HIDL 초안 | 3시간 | ICD.md §3.1 HIDL 인터페이스와 일치 |
| 3 | 팀원A ICD.md 리뷰 + 피드백 | 1시간 | PR 코멘트 완료 |
| 4 | GitHub Actions Stage 1 (cppcheck) ci.yml | 1시간 | PR 트리거 녹색 |
| 4 | ICD.md 최종 확정 미팅 참여 | 30분 | 합의 완료 |
| 4 | SRS.md FR-IVI/CI 부분 초안 | 2시간 | PR 머지 |
| 4 | ADR-004 (HIDL vs AIDL), ADR-007 (Docker) 초안 | 2시간 | PR 머지 |

**M1 총 예상 시간: 약 18~22시간**

### 수행 과정

#### 1. AOSP 빌드 서버 요구 사항

| 항목 | 최소 사양 |
|------|----------|
| OS | Ubuntu 22.04 LTS (64-bit) |
| 디스크 | **200GB 이상** (AOSP 소스 80GB + 빌드 산출물 80GB + 여유) |
| RAM | 16GB 이상 (32GB 권장) |
| CPU | 8코어 이상 권장 |
| 네트워크 | 안정적인 유선 (70GB+ 다운로드) |

> PC 스펙 부족 시 대학교 서버 또는 클라우드 VM(GCP n2-standard-8) 고려.

확인 명령:
```bash
lsb_release -a        # Ubuntu 22.04 확인
nproc                  # CPU 코어 수
free -h                # RAM 확인
df -h /home            # 디스크 여유 확인 (200GB+ 필요)
```

#### 2. Docker 설치

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io
sudo usermod -aG docker $USER
newgrp docker
docker run hello-world  # 성공 확인
```

검증:
```bash
docker --version
# 기대 출력: Docker version 24.x.x (또는 그 이상)
docker run hello-world
# 기대 출력: "Hello from Docker!" 메시지
```

**트러블슈팅 — Docker 권한 오류**:
```
Got permission denied while trying to connect to the Docker daemon socket
```
해결:
```bash
sudo usermod -aG docker $USER
# 터미널 재시작 또는:
newgrp docker
```

#### 3. 필수 패키지 + repo sync

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git-core gnupg flex bison build-essential \
  zip curl zlib1g-dev libc6-dev-i386 x11proto-core-dev \
  libx11-dev lib32z1-dev libgl1-mesa-dev libxml2-utils \
  xsltproc unzip fontconfig python3 python3-pip openjdk-11-jdk

mkdir -p ~/bin
curl https://storage.googleapis.com/git-repo-downloads/repo > ~/bin/repo
chmod a+x ~/bin/repo
echo 'export PATH=~/bin:$PATH' >> ~/.bashrc
source ~/.bashrc

git config --global user.name "이름"
git config --global user.email "이메일"

mkdir -p ~/aosp && cd ~/aosp
repo init -u https://android.googlesource.com/platform/manifest \
  -b android-13.0.0_r3 --depth=1
nohup repo sync -c -j$(nproc) --no-tags > ~/aosp-sync.log 2>&1 &
tail -f ~/aosp-sync.log
```

sync 완료 확인:
```bash
tail -20 ~/aosp-sync.log
# 기대 출력: "Syncing work tree: 100%" (에러 없음)
du -sh ~/aosp
# 기대 출력: ~80GB+
```

**sync 실패 시**: `repo sync -c -j4 --no-tags` 재실행 (이어서 받음)

**트러블슈팅 — sync 중 네트워크 끊김**:
```bash
# 스레드 수를 줄여서 재시도 (이어서 받음)
cd ~/aosp
repo sync -c -j4 --no-tags --force-sync
```

**트러블슈팅 — 디스크 용량 부족**:
```bash
df -h /home
# 200GB 미만이면 외부 디스크 마운트 또는 VM 디스크 증설 필요
# 임시 방편: --depth=1 이미 적용됨. 이외 줄일 방법 없음
```

#### AOSP RPi4 디바이스 트리 참고

> **중요**: vanilla AOSP는 RPi4를 기본 지원하지 않음. 커뮤니티 device tree 필요.
> - **android-rpi**: `https://github.com/nicknumb/device_arpi_rpi4`
> - M2(7월)에서 부팅 시도 시 `device/arpi/rpi4/` 경로에 클론

#### 4. Android Studio 설치

```bash
# Android Studio 다운로드 (공식 사이트에서 최신 tar.gz)
wget https://redirector.gvt1.com/edgedl/android/studio/ide-zips/2024.2.2.13/android-studio-2024.2.2.13-linux.tar.gz
tar -xzf android-studio-*.tar.gz -C ~/
cd ~/android-studio/bin && ./studio.sh
```

초기 설정 단계:
1. Android SDK 13 (API 33) 선택 설치
2. Kotlin plugin 활성화 확인
3. AVD Manager에서 Pixel 4a API 33 에뮬레이터 생성 → 실행 성공 확인

검증:
```bash
~/android-studio/bin/studio.sh --version
# 또는 Android Studio > Help > About에서 버전 확인
```

#### 5. Dockerfile.arm64 + toolchain

**Dockerfile.arm64** (프로젝트 루트에 생성):

```dockerfile
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# ARM64 크로스컴파일 아키텍처 등록
RUN dpkg --add-architecture arm64

RUN apt-get update && apt-get install -y \
    cmake \
    ninja-build \
    gcc-aarch64-linux-gnu \
    g++-aarch64-linux-gnu \
    binutils-aarch64-linux-gnu \
    libssl-dev:arm64 \
    googletest \
    libgtest-dev \
    lcov \
    && rm -rf /var/lib/apt/lists/*

# 툴체인 파일을 이미지 내부에 복사
COPY toolchain-aarch64.cmake /opt/toolchain-aarch64.cmake

# GoogleTest 빌드 (ARM64 타겟용)
RUN cmake -S /usr/src/googletest \
          -B /tmp/gtest_build \
          -DCMAKE_TOOLCHAIN_FILE=/opt/toolchain-aarch64.cmake \
          -DCMAKE_INSTALL_PREFIX=/usr/aarch64-linux-gnu && \
    cmake --build /tmp/gtest_build && \
    cmake --install /tmp/gtest_build

WORKDIR /workspace
```

**toolchain-aarch64.cmake** (프로젝트 루트에 생성):

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

빌드 테스트:
```bash
docker build -f Dockerfile.arm64 -t capstone-arm64 .
docker run --rm -v $(pwd):/workspace capstone-arm64 \
  bash -c "mkdir -p build && cd build && \
    cmake -DCMAKE_TOOLCHAIN_FILE=/workspace/toolchain-aarch64.cmake /workspace/adaptive_ecu && \
    make"
file build/ecu_node_a
# 기대 출력: ELF 64-bit LSB executable, ARM aarch64, ...
```

**트러블슈팅 — Docker build 실패 (dpkg --add-architecture arm64)**:
```
E: Unable to locate package libssl-dev:arm64
```
해결: Ubuntu 22.04 이미지에 arm64 패키지 소스 추가 필요
```dockerfile
# Dockerfile에 추가
RUN echo "deb [arch=arm64] http://ports.ubuntu.com/ubuntu-ports jammy main restricted universe multiverse" >> /etc/apt/sources.list
```

**트러블슈팅 — GoogleTest 크로스빌드 실패**:
```bash
# Docker 내부에서 수동 확인
docker run --rm -it capstone-arm64 bash
cmake -S /usr/src/googletest -B /tmp/gtest_build \
  -DCMAKE_TOOLCHAIN_FILE=/opt/toolchain-aarch64.cmake
# 오류 메시지 확인 후 toolchain 경로/컴파일러 이름 수정
```

#### 6. ivi_platform/ 디렉토리 골격 생성

```bash
mkdir -p ivi_platform/{hal/mock,service,app/{data,test},test}
```

결과 구조:
```
ivi_platform/
├── hal/              # HIDL HAL 레이어 (C++)
│   └── mock/         # VehicleHalMock.java
├── service/          # Android SystemService (Java)
├── app/              # Jetpack Compose 앱 (Kotlin)
│   ├── data/         # VehicleRepository.kt
│   └── test/         # Compose UI 테스트
└── test/             # HAL/Service 단위 테스트 (C++/Java)
```

PR 생성:
```bash
git switch develop
git switch -c feature/ivi-skeleton
git add ivi_platform/
git commit -m "feat(hal): ivi_platform 디렉토리 골격 생성"
git push origin feature/ivi-skeleton
# GitHub에서 PR 생성 (base: develop) → 팀원A 리뷰 요청
```

#### 7. IVehicleHal.hal HIDL 초안

`ivi_platform/hal/IVehicleHal.hal`:

```
// IVehicleHal.hal
package vehicle.hal@1.0;

struct VehicleData {
    float soc;              // 배터리 잔량 (%), 0.0 ~ 100.0
    float soh;              // 배터리 건강도 (%), 0.0 ~ 100.0
    float voltage;          // 팩 전압 (V)
    float current;          // 충방전 전류 (A), 양수=충전
    int8_t temperature;     // 셀 온도 (°C)
    uint8_t failSafeState;  // 0=NORMAL, 1=WARNING, 2=CRITICAL, 3=SHUTDOWN
    uint8_t failSafeReason; // Fail-safe 전이 사유 코드 (ICD §1.3 참조)
    bool attackDetected;    // ML IDS 공격 탐지 여부
    uint8_t attackType;     // 공격 유형 (0=None, 1=Fuzzy, 2=Replay, 3=Spoofing, 4=Flooding)
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
// IVehicleHalCallback.hal
package vehicle.hal@1.0;

interface IVehicleHalCallback {
    onVehicleDataChanged(VehicleData data);
    onSecurityAlert(uint8_t attackType, float anomalyScore, uint16_t suspectCanId);
    onFailSafeTransition(uint8_t prevState, uint8_t newState, uint8_t reason);
};
```

검증: ICD.md §3.1의 `VehicleData` 구조체 필드와 1:1 대응하는지 확인.

#### 8. GitHub Actions Stage 1 — cppcheck

`.github/workflows/ci.yml`:

```yaml
name: CI Pipeline
on:
  push:
    branches: [develop, main]
  pull_request:
    branches: [develop, main]

jobs:
  stage1-static-analysis:
    name: "Stage 1: cppcheck"
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4

      - name: Install cppcheck
        run: sudo apt-get install -y cppcheck

      - name: Run cppcheck
        run: |
          if find adaptive_ecu/src/ adaptive_ecu/include/ -name '*.cpp' -o -name '*.h' 2>/dev/null | grep -q .; then
            cppcheck \
              --enable=all \
              --error-exitcode=1 \
              --suppress=missingIncludeSystem \
              --suppress=unusedFunction \
              -I adaptive_ecu/include \
              --std=c++17 \
              adaptive_ecu/src/ adaptive_ecu/include/
          else
            echo "No C++ source files found — skipping cppcheck"
          fi
```

CI 동작 확인:
```bash
# 1. ci.yml 커밋 + push
git add .github/workflows/ci.yml
git commit -m "chore(ci): Stage 1 cppcheck 정적 분석 워크플로우 추가"
git push origin feature/cicd-pipeline

# 2. GitHub Actions 탭에서 녹색 확인
# 3. Settings → Branches → develop 보호 규칙에 stage1-static-analysis required check 추가
```

검증:
```
GitHub → Actions 탭 → 최신 워크플로우 실행 → "Stage 1: cppcheck" 녹색 체크
```

#### 9. SRS.md FR-IVI/CI 초안

작성할 섹션 (SRS.md에 추가):

```markdown
## FR-IVI: IVI 플랫폼 기능 요구사항

| ID | 요구사항 | 검증 TC |
|----|---------|--------|
| FR-IVI-001 | Vehicle HAL이 CAN 프레임 수신 시 콜백 호출 | TC-IVI-001 |
| FR-IVI-002 | CAN ID별 파싱 정확도 (ICD §1.2~1.5) | TC-IVI-002 |
| FR-IVI-003 | VehicleDataService getSystemService 접근 | TC-IVI-003 |
| FR-IVI-004 | Binder IPC StateFlow 업데이트 | TC-IVI-004 |
| FR-IVI-005 | SOC 게이지 색상 로직 (Green/Orange/Red) | TC-IVI-005 |
| FR-IVI-006 | 공격 탐지 AlertBanner 표시 | TC-IVI-006 |
| FR-IVI-007 | CRITICAL/SHUTDOWN 풀스크린 경고 | TC-IVI-007 |

## FR-CI: CI/CD 기능 요구사항

| ID | 요구사항 | 검증 TC |
|----|---------|--------|
| FR-CI-001 | PR/Push 시 자동 파이프라인 기동 | TC-CI-001 |
| FR-CI-002 | cppcheck 정적 분석 (Error 시 중단) | TC-CI-002 |
| FR-CI-003 | ARM64 크로스컴파일 산출물 | TC-CI-003 |
| FR-CI-004 | 커버리지 품질 게이트 (≥80%) | TC-CI-004 |
| FR-CI-005 | SSH 자동 배포 | TC-CI-005 |
| FR-CI-006 | Health Check | TC-CI-006 |
```

#### 10. ADR 초안 작성

**ADR-004 (HIDL vs AIDL)**:
```markdown
# ADR-004: HIDL vs AIDL 선택

## 상태: Accepted
## 맥락: Android 13 HAL 인터페이스 정의 방식 선택
## 결정: HIDL 사용
## 근거:
- Android 13까지 HIDL 지원 유지
- Vehicle HAL은 HIDL 기반 참조 구현이 풍부
- AIDL은 Android 14+에서 권장되나 현 프로젝트 범위 밖
## 결과: IVehicleHal.hal HIDL 파일로 인터페이스 정의
```

**ADR-007 (Docker 크로스컴파일)**:
```markdown
# ADR-007: Docker ARM64 크로스컴파일 환경

## 상태: Accepted
## 맥락: x86_64 개발 PC에서 ARM64 바이너리 빌드 방법 선택
## 결정: Docker 컨테이너 + aarch64-linux-gnu 툴체인 사용
## 근거:
- 일관된 빌드 환경 보장 (CI와 로컬 동일)
- GitHub Actions ubuntu-22.04 러너에서 바로 사용 가능
- 네이티브 ARM 빌드 대비 환경 구축 용이
## 결과: Dockerfile.arm64 + toolchain-aarch64.cmake 작성
```

---

## M2 (7월) — HAL Mock + AOSP 부팅 시도

### 목표

HIDL 인터페이스 완성, VehicleHalMock 더미 HAL 구현, AOSP RPi4 부팅 시도, Plan A/B 전환 결정.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | `IVehicleHal.hal` HIDL 인터페이스 완성 | 2시간 | ICD.md §3.1과 필드 완전 일치 |
| 1 | `IVehicleHalCallback.hal` 콜백 인터페이스 | 1시간 | 3개 콜백 메서드 정의 완료 |
| 1 | `VehicleHalMock.java` 더미 HAL | 3시간 | 더미 데이터 100ms 주기 출력 |
| 2 | `VehicleRepository.kt` 구현 | 3시간 | Repository Pattern 데이터 플로우 동작 |
| 2 | AOSP RPi4 첫 빌드 + 부팅 시도 | 8~12시간 | 빌드 결과 기록 (성공/실패 로그) |
| 3 | AOSP RPi4 마지막 빌드 시도 + 로그 분석 | 4~8시간 | 성공 여부 최종 판정 |
| 3 | `Dockerfile.arm64` Stage 2 빌드 확인 | 2시간 | ARM64 바이너리 생성 확인 |
| 4 | **Plan A/B 전환 결정 미팅** | 1시간 | 3가지 기준 확인 후 결정 기록 |
| 4 | ADR-010 작성 (Plan B 전환 시) | 2시간 | 전환 근거 + 아키텍처 변경점 기록 |

**M2 총 예상 시간: 약 26~34시간**

### 수행 과정

#### 1. VehicleHalMock.java (1주차)

`ivi_platform/hal/mock/VehicleHalMock.java`:

```java
package com.capstone.vehicle.hal.mock;

import java.util.Timer;
import java.util.TimerTask;

public class VehicleHalMock {
    private Timer timer = new Timer();
    private IVehicleHalCallback callback;
    private float socValue = 80.0f;  // 점진적 감소 시뮬레이션

    public void start(IVehicleHalCallback callback) {
        this.callback = callback;
        timer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                VehicleData data = new VehicleData();
                data.soc = socValue;
                data.soh = 95.0f;
                data.voltage = 42.0f + (socValue - 50.0f) * 0.1f;
                data.current = -2.0f;
                data.temperature = 35;
                data.failSafeState = 0; // NORMAL
                data.failSafeReason = 0;
                data.attackDetected = false;
                data.attackType = 0;
                data.anomalyScore = 0.0f;
                data.timestamp = (int)(System.currentTimeMillis() / 1000);
                callback.onVehicleDataChanged(data);

                // SOC 서서히 감소 시뮬레이션
                socValue = Math.max(0.0f, socValue - 0.05f);
            }
        }, 0, 100); // 100ms 주기
    }

    public void stop() {
        timer.cancel();
    }
}
```

검증:
```
Android Studio에서 VehicleHalMock 단독 실행 →
logcat 출력에서 100ms 주기로 VehicleData 확인
SOC 값이 80.0 → 79.95 → 79.90 순차 감소 확인
```

#### 2. VehicleRepository.kt (2주차)

`ivi_platform/app/data/VehicleRepository.kt`:

```kotlin
package com.capstone.vehicle.app.data

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

data class VehicleUiState(
    val soc: Float = 0f,
    val soh: Float = 0f,
    val voltage: Float = 0f,
    val current: Float = 0f,
    val temperature: Int = 0,
    val failSafeState: Int = 0,   // 0=NORMAL, 1=WARNING, 2=CRITICAL, 3=SHUTDOWN
    val failSafeReason: Int = 0,
    val attackDetected: Boolean = false,
    val attackType: Int = 0,      // 0=None, 1=Fuzzy, 2=Replay, 3=Spoofing, 4=Flooding
    val anomalyScore: Float = 0f,
    val timestamp: Long = 0L,
    val stale: Boolean = false    // CAN 통신 타임아웃 시 true (ICD §2.5.1)
)

class VehicleRepository {
    private val _vehicleState = MutableStateFlow(VehicleUiState())
    val vehicleState: Flow<VehicleUiState> = _vehicleState.asStateFlow()

    fun updateVehicleData(data: VehicleUiState) {
        _vehicleState.value = data
    }

    fun markStale() {
        _vehicleState.value = _vehicleState.value.copy(stale = true)
    }

    fun clearStale() {
        _vehicleState.value = _vehicleState.value.copy(stale = false)
    }
}
```

#### 3. AOSP RPi4 빌드 (2~3주차)

```bash
cd ~/aosp

# 디바이스 트리 추가
git clone https://github.com/nicknumb/device_arpi_rpi4 device/arpi/rpi4

# 빌드 환경 초기화
source build/envsetup.sh
lunch rpi4-eng  # 또는 해당 타겟명 확인

# 빌드 (시간 오래 걸림, 4~8시간)
make -j$(nproc) 2>&1 | tee ~/aosp-build.log
```

빌드 완료 후:
```bash
# 이미지 생성 확인
ls out/target/product/rpi4/*.img
# 기대 출력: system.img, boot.img, vendor.img 등

# SD 카드에 이미지 플래시 (16GB+ microSD)
# RPi4에 SD 카드 삽입 → HDMI + 키보드 연결 → 전원 ON
```

검증: 부팅 후 ADB 접속 시도:
```bash
adb connect <RPi4_IP>:5555
adb shell
# 기대 출력: rpi4:/ $

ip link show can0
# 기대 출력: can0 인터페이스 존재
```

**트러블슈팅 — AOSP 빌드 실패 (out of memory)**:
```bash
# swap 추가
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
# 다시 make -j$(nproc)
```

**트러블슈팅 — RPi4 부팅 안 됨 (HDMI 출력 없음)**:
1. SD 카드 이미지 플래시 재확인 (`dd` 또는 `bmaptool`)
2. 커뮤니티 디바이스 트리 버전 확인 (android-13 브랜치)
3. `config.txt`에 `hdmi_force_hotplug=1` 추가
4. UART 콘솔 연결하여 커널 로그 확인

#### 4. Plan A/B 전환 결정 (4주차)

**Plan A 유지 조건** (7월 말 전부 충족 시):

| # | 조건 | 확인 명령 | 결과 |
|---|------|----------|------|
| 1 | Android 13 홈 화면 표시 | HDMI 직접 확인 | [ ] 충족 / [ ] 미충족 |
| 2 | `adb shell` 접속 가능 | `adb shell whoami` | [ ] 충족 / [ ] 미충족 |
| 3 | `ip link show can0` 출력 확인 | `adb shell ip link show can0` | [ ] 충족 / [ ] 미충족 |

**하나라도 미충족 → Plan B 전환**

#### 5. Plan B 상세 아키텍처 (전환 시)

Plan B는 AOSP 대신 **Ubuntu 22.04 + D-Bus/gRPC + Qt/Flutter** 조합을 사용한다.

**Plan B 아키텍처 비교**:

| 계층 | Plan A (AOSP) | Plan B (Ubuntu) |
|------|---------------|-----------------|
| HAL | HIDL C++ | 동일 C++ (SocketCAN 직접) |
| IPC | Binder | D-Bus (sd-bus) 또는 gRPC |
| Service | Android SystemService (Java) | systemd service + D-Bus daemon (C++/Python) |
| UI | Jetpack Compose (Kotlin) | Qt6 QML 또는 Flutter (Dart) |
| 배포 | AOSP flashable image | apt/deb 패키지 또는 직접 바이너리 |

**Plan B 전환 시 마이그레이션 절차**:

1. Node B RPi4에 Ubuntu 22.04 Server 설치 (팀원A와 동일 OS)
2. SocketCAN + MCP2515 설정 (팀원A 설정과 동일)
3. `can_parser.cpp`, `vehicle_hal_impl.cpp` → 그대로 재사용 (HAL 계층은 C++이므로)
4. HIDL 인터페이스 → D-Bus 인터페이스로 교체
5. VehicleDataService.java → D-Bus daemon (C++ 또는 Python)
6. Jetpack Compose → Qt6 QML 또는 Flutter 대시보드
7. ADR-010 작성 (전환 사유, 영향 범위, 아키텍처 변경점)

**Plan B D-Bus IPC 설정 (전환 시 참고)**:

```bash
# Ubuntu 22.04에 D-Bus 개발 환경
sudo apt install -y libdbus-1-dev libsystemd-dev
```

D-Bus 인터페이스 정의 예시 (`com.capstone.VehicleData.xml`):
```xml
<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node>
  <interface name="com.capstone.VehicleData">
    <signal name="VehicleDataChanged">
      <arg name="soc" type="d"/>
      <arg name="voltage" type="d"/>
      <arg name="current" type="d"/>
      <arg name="temperature" type="i"/>
      <arg name="failSafeState" type="y"/>
    </signal>
    <signal name="SecurityAlert">
      <arg name="attackType" type="y"/>
      <arg name="anomalyScore" type="d"/>
    </signal>
  </interface>
</node>
```

**Plan B Flutter 대시보드 대안 (전환 시 참고)**:
```bash
# Flutter 설치 (Linux desktop)
sudo snap install flutter --classic
flutter doctor
flutter create ivi_dashboard
cd ivi_dashboard
flutter run -d linux
```

**ADR-010 작성 시 포함할 내용**:
```markdown
# ADR-010: AOSP → Ubuntu Plan B 전환

## 상태: Accepted (7월 말 결정)
## 맥락: AOSP RPi4 부팅 실패 — [구체적 실패 사유 기록]
## 결정: Ubuntu 22.04 + D-Bus + Qt/Flutter로 전환
## 근거:
- AOSP RPi4 부팅 [실패 사유]
- 커뮤니티 디바이스 트리의 Android 13 지원 불완전
- 프로젝트 일정상 AOSP 디버깅에 추가 1개월 투자 불가
## 영향:
- HAL 계층(C++) 변경 없음 — CAN 파싱, SecOC 검증 로직 재사용
- IPC: Binder → D-Bus 전환
- UI: Jetpack Compose → Qt/Flutter 전환
- 핵심 계층 분리 아키텍처는 동일 유지
## 위험 완화:
- D-Bus/gRPC 튜토리얼 1주 내 완료
- Qt/Flutter 대시보드 M3 내 완성 가능
```

#### 6. Dockerfile.arm64 Stage 2 빌드 (3주차)

CICD_SPEC.md §2.3의 Stage 2 빌드를 로컬에서 먼저 확인:

```bash
docker build -f Dockerfile.arm64 -t ecu-builder:arm64 .

docker run --rm \
  -v $(pwd):/workspace \
  ecu-builder:arm64 \
  bash -c "
    cmake -S /workspace/adaptive_ecu \
          -B /workspace/build \
          -DCMAKE_TOOLCHAIN_FILE=/workspace/toolchain-aarch64.cmake \
          -DCMAKE_BUILD_TYPE=Release && \
    cmake --build /workspace/build -j\$(nproc)
  "

file build/ecu_node_a
# 기대 출력: ELF 64-bit LSB executable, ARM aarch64
```

---

## M3 (8월) — HAL 구현 + Service + 대시보드 UI

### 목표

CAN 파서 구현, Vehicle HAL CAN 수신 스레드 완성, Binder IPC Service 계층 구축, Jetpack Compose 대시보드 기본 UI (SocGauge + DashboardViewModel), SecOC 검증 로직 연동, GitHub Actions Stage 2~3 추가.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | `can_parser.h/.cpp` CAN ID 파싱 구현 | 4시간 | TC-IVI-002-a/b/c 전체 통과 |
| 1 | `vehicle_hal_impl.cpp` CAN rx_thread_ | 6시간 | rx_thread_ 가동, 콜백 호출 확인 |
| 1 | TC-IVI-001 (HAL 콜백 호출) 테스트 | 2시간 | PASSED |
| 2 | `IVehicleDataService.aidl` Binder IPC | 3시간 | 인터페이스 정의 + 빌드 성공 |
| 2 | `VehicleDataService.java` SystemService | 6시간 | TC-IVI-003 통과 |
| 2 | `VehicleDataManager.java` 클라이언트 API | 3시간 | TC-IVI-004 통과 |
| 3 | `DashboardViewModel.kt` StateFlow | 3시간 | 데이터 바인딩 동작 확인 |
| 3 | `SocGauge.kt` 원형 게이지 Composable | 4시간 | TC-IVI-005 색상 6케이스 통과 |
| 3 | Jetpack Compose 프로젝트 셋업 | 2시간 | Compose Preview 동작 확인 |
| 4 | `secoc_verifier.cpp` HAL HMAC 검증 | 4시간 | 팀원A secoc_module.cpp 완성 후 |
| 4 | CI Stage 2 (ARM64 빌드) ci.yml 추가 | 2시간 | ARM64 바이너리 artifact 생성 |
| 4 | CI Stage 3 (QEMU 테스트) ci.yml 추가 | 3시간 | CTest QEMU 실행 녹색 |

**M3 총 예상 시간: 약 42시간**

### 수행 과정

#### 1. can_parser.h / can_parser.cpp (1주차)

`ivi_platform/hal/can_parser.h`:

```cpp
#pragma once
#include <cstdint>
#include <linux/can.h>

// ICD.md §1.2 — 0x100 BMS_Status
struct BmsStatus {
    float soc;      // Byte0 × 0.5
    float soh;      // Byte1 × 0.5
    float voltage;  // (Byte2<<8|Byte3) × 0.01
    float current;  // (Byte4<<8|Byte5) × 0.1 - 3276.8
    int8_t temp;    // Byte6 - 40
};

// ICD.md §1.3 — 0x101 BMS_FailSafe
struct FailSafeEvent {
    uint8_t prevState;
    uint8_t newState;
    uint8_t reason;
    float socAtEvent;   // Byte3 × 0.5
    int8_t tempAtEvent; // Byte4 - 40
};

// ICD.md §1.4 — 0x102/0x103 SecOC
struct SecOcAuth {
    uint32_t truncatedMac;     // Byte0~3 BE
    uint32_t rollingCounter;   // Byte4~7 BE
};

// ICD.md §1.5 — 0x200 IDS_Alert
struct IdsAlert {
    uint8_t attackType;        // 0=None, 1=Fuzzy, 2=Replay, 3=Spoofing, 4=Flooding
    float anomalyScore;        // Byte1 × 0.01
    uint16_t suspectCanId;     // Byte2~3 BE
    uint32_t timestamp;        // Byte4~7 BE
};

class CanParser {
public:
    BmsStatus parseBmsStatus(const uint8_t* data);
    FailSafeEvent parseFailSafe(const uint8_t* data);
    SecOcAuth parseSecOcAuth(const uint8_t* data);
    IdsAlert parseIdsAlert(const uint8_t* data);
};
```

`ivi_platform/hal/can_parser.cpp`:

```cpp
#include "can_parser.h"

BmsStatus CanParser::parseBmsStatus(const uint8_t* data) {
    BmsStatus s;
    s.soc = data[0] * 0.5f;
    s.soh = data[1] * 0.5f;
    s.voltage = ((data[2] << 8) | data[3]) * 0.01f;
    s.current = ((data[4] << 8) | data[5]) * 0.1f - 3276.8f;
    s.temp = static_cast<int8_t>(data[6]) - 40;
    return s;
}

FailSafeEvent CanParser::parseFailSafe(const uint8_t* data) {
    FailSafeEvent e;
    e.prevState = data[0];
    e.newState = data[1];
    e.reason = data[2];
    e.socAtEvent = data[3] * 0.5f;
    e.tempAtEvent = static_cast<int8_t>(data[4]) - 40;
    return e;
}

SecOcAuth CanParser::parseSecOcAuth(const uint8_t* data) {
    SecOcAuth a;
    a.truncatedMac = (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3];
    a.rollingCounter = (data[4] << 24) | (data[5] << 16) | (data[6] << 8) | data[7];
    return a;
}

IdsAlert CanParser::parseIdsAlert(const uint8_t* data) {
    IdsAlert alert;
    alert.attackType = data[0];
    alert.anomalyScore = data[1] * 0.01f;
    alert.suspectCanId = (data[2] << 8) | data[3];
    alert.timestamp = (data[4] << 24) | (data[5] << 16) | (data[6] << 8) | data[7];
    return alert;
}
```

단위 테스트 `ivi_platform/test/test_can_parser.cpp`:

```cpp
#include <gtest/gtest.h>
#include "can_parser.h"

TEST(CanParserTest, TC_IVI_002_a_BmsStatus) {
    // ICD §1.2 테스트 벡터: SOC=75%, SOH=95%, V=42.00V, I=2.0A, T=25°C
    uint8_t data[] = {150, 190, 0x10, 0x68, 0x00, 0x14, 65, 0x00};
    CanParser parser;
    auto s = parser.parseBmsStatus(data);
    EXPECT_FLOAT_EQ(s.soc, 75.0f);
    EXPECT_FLOAT_EQ(s.soh, 95.0f);
    EXPECT_NEAR(s.voltage, 42.00f, 0.01f);
    EXPECT_NEAR(s.current, 2.0f, 0.1f);
    EXPECT_EQ(s.temp, 25);
}

TEST(CanParserTest, TC_IVI_002_b_FailSafe) {
    // PrevState=NORMAL(0), NewState=WARNING(1), Reason=0x01, SOC=75%, Temp=25°C
    uint8_t data[] = {0x00, 0x01, 0x01, 150, 65, 0, 0, 0};
    CanParser parser;
    auto e = parser.parseFailSafe(data);
    EXPECT_EQ(e.prevState, 0);
    EXPECT_EQ(e.newState, 1);
    EXPECT_EQ(e.reason, 0x01);
    EXPECT_FLOAT_EQ(e.socAtEvent, 75.0f);
    EXPECT_EQ(e.tempAtEvent, 25);
}

TEST(CanParserTest, TC_IVI_002_c_IdsAlert) {
    // AttackType=Flooding(4), AnomalyScore=2.55, SuspectCANID=0x0001
    uint8_t data[] = {0x04, 0xFF, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00};
    CanParser parser;
    auto a = parser.parseIdsAlert(data);
    EXPECT_EQ(a.attackType, 4);
    EXPECT_NEAR(a.anomalyScore, 2.55f, 0.01f);
    EXPECT_EQ(a.suspectCanId, 0x0001);
}
```

빌드 및 실행:
```bash
cd ivi_platform/test
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Debug
make
./test_can_parser
# 기대 출력:
# [  PASSED  ] 3 tests.
```

#### 2. vehicle_hal_impl.cpp CAN 수신 (1주차)

`ivi_platform/hal/vehicle_hal_impl.h`:

```cpp
#pragma once
#include <thread>
#include <atomic>
#include <mutex>
#include <vector>
#include "can_parser.h"

class IVehicleHalCallback {
public:
    virtual void onVehicleDataChanged(const BmsStatus& data) = 0;
    virtual void onSecurityAlert(uint8_t attackType, float anomalyScore, uint16_t suspectCanId) = 0;
    virtual void onFailSafeTransition(uint8_t prevState, uint8_t newState, uint8_t reason) = 0;
    virtual ~IVehicleHalCallback() = default;
};

class VehicleHalImpl {
public:
    bool init(const std::string& canInterface);
    void registerCallback(IVehicleHalCallback* cb);
    void unregisterCallback(IVehicleHalCallback* cb);
    void start();
    void stop();
    ~VehicleHalImpl();

private:
    void rxLoop();

    int sock_ = -1;
    std::atomic<bool> running_{false};
    std::thread rx_thread_;
    CanParser parser_;
    std::mutex cb_mutex_;
    std::vector<IVehicleHalCallback*> callbacks_;
};
```

`ivi_platform/hal/vehicle_hal_impl.cpp`:

```cpp
#include "vehicle_hal_impl.h"
#include <sys/socket.h>
#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <cstring>
#include <android/log.h>

#define LOG_TAG "VehicleHAL"
#define LOG_INFO(...)  __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOG_WARN(...)  __android_log_print(ANDROID_LOG_WARN, LOG_TAG, __VA_ARGS__)
#define LOG_ERR(...)   __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

bool VehicleHalImpl::init(const std::string& canInterface) {
    sock_ = socket(PF_CAN, SOCK_RAW, CAN_RAW);
    if (sock_ < 0) {
        LOG_ERR("ERR_CAN_INIT_FAIL: socket() failed");
        return false;
    }

    struct ifreq ifr;
    std::strncpy(ifr.ifr_name, canInterface.c_str(), IFNAMSIZ - 1);
    if (ioctl(sock_, SIOCGIFINDEX, &ifr) < 0) {
        LOG_ERR("ERR_CAN_INIT_FAIL: ioctl() failed for %s", canInterface.c_str());
        close(sock_);
        return false;
    }

    struct sockaddr_can addr;
    std::memset(&addr, 0, sizeof(addr));
    addr.can_family = AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;

    if (bind(sock_, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        LOG_ERR("ERR_CAN_INIT_FAIL: bind() failed");
        close(sock_);
        return false;
    }

    LOG_INFO("CAN interface %s initialized", canInterface.c_str());
    return true;
}

void VehicleHalImpl::registerCallback(IVehicleHalCallback* cb) {
    std::lock_guard<std::mutex> lock(cb_mutex_);
    if (callbacks_.size() >= 10) {
        LOG_ERR("ERR_CALLBACK_FULL: max 10 callbacks");
        return;
    }
    callbacks_.push_back(cb);
}

void VehicleHalImpl::unregisterCallback(IVehicleHalCallback* cb) {
    std::lock_guard<std::mutex> lock(cb_mutex_);
    callbacks_.erase(
        std::remove(callbacks_.begin(), callbacks_.end(), cb),
        callbacks_.end());
}

void VehicleHalImpl::start() {
    running_ = true;
    rx_thread_ = std::thread(&VehicleHalImpl::rxLoop, this);
}

void VehicleHalImpl::stop() {
    running_ = false;
    if (rx_thread_.joinable()) {
        rx_thread_.join();
    }
    if (sock_ >= 0) {
        close(sock_);
        sock_ = -1;
    }
}

VehicleHalImpl::~VehicleHalImpl() {
    stop();
}

void VehicleHalImpl::rxLoop() {
    struct can_frame frame;
    while (running_) {
        int nbytes = read(sock_, &frame, sizeof(frame));
        if (nbytes < 0) {
            LOG_ERR("ERR_CAN_READ_FAIL");
            continue;
        }
        if (nbytes < static_cast<int>(sizeof(frame))) {
            continue;
        }

        std::lock_guard<std::mutex> lock(cb_mutex_);
        switch (frame.can_id) {
            case 0x100: {
                auto status = parser_.parseBmsStatus(frame.data);
                LOG_INFO("BMS_Status: SOC=%.1f%%, V=%.2fV, T=%d°C",
                         status.soc, status.voltage, status.temp);
                for (auto* cb : callbacks_) {
                    cb->onVehicleDataChanged(status);
                }
                break;
            }
            case 0x101: {
                auto event = parser_.parseFailSafe(frame.data);
                LOG_INFO("BMS_FailSafe: %d->%d reason=0x%02X",
                         event.prevState, event.newState, event.reason);
                for (auto* cb : callbacks_) {
                    cb->onFailSafeTransition(event.prevState, event.newState, event.reason);
                }
                break;
            }
            case 0x102:
            case 0x103: {
                auto auth = parser_.parseSecOcAuth(frame.data);
                // SecOC 검증은 secoc_verifier에서 처리
                LOG_INFO("SecOC auth: MAC=0x%08X CTR=%u", auth.truncatedMac, auth.rollingCounter);
                break;
            }
            case 0x200: {
                auto alert = parser_.parseIdsAlert(frame.data);
                LOG_WARN("IDS_Alert: type=%d score=%.2f suspect=0x%04X",
                         alert.attackType, alert.anomalyScore, alert.suspectCanId);
                for (auto* cb : callbacks_) {
                    cb->onSecurityAlert(alert.attackType, alert.anomalyScore, alert.suspectCanId);
                }
                break;
            }
            default:
                LOG_INFO("Unknown CAN ID: 0x%03X (ignored)", frame.can_id);
                break;
        }
    }
}
```

#### 3. IVehicleDataService.aidl — Binder IPC (2주차)

`ivi_platform/service/IVehicleDataService.aidl`:

```aidl
package com.capstone.vehicle.service;

import com.capstone.vehicle.service.VehicleDataParcel;
import com.capstone.vehicle.service.IVehicleDataListener;

interface IVehicleDataService {
    VehicleDataParcel getLatestData();
    void registerListener(IVehicleDataListener listener);
    void unregisterListener(IVehicleDataListener listener);
}
```

`ivi_platform/service/IVehicleDataListener.aidl`:

```aidl
package com.capstone.vehicle.service;

import com.capstone.vehicle.service.VehicleDataParcel;

oneway interface IVehicleDataListener {
    void onDataChanged(in VehicleDataParcel data);
    void onSecurityAlert(int attackType, float anomalyScore, int suspectCanId);
    void onFailSafeTransition(int prevState, int newState, int reason);
}
```

`ivi_platform/service/VehicleDataParcel.java` (Parcelable):

```java
package com.capstone.vehicle.service;

import android.os.Parcel;
import android.os.Parcelable;

public class VehicleDataParcel implements Parcelable {
    public float soc;
    public float soh;
    public float voltage;
    public float current;
    public int temperature;
    public int failSafeState;
    public int failSafeReason;
    public boolean attackDetected;
    public int attackType;
    public float anomalyScore;
    public long timestamp;

    public VehicleDataParcel() {}

    protected VehicleDataParcel(Parcel in) {
        soc = in.readFloat();
        soh = in.readFloat();
        voltage = in.readFloat();
        current = in.readFloat();
        temperature = in.readInt();
        failSafeState = in.readInt();
        failSafeReason = in.readInt();
        attackDetected = in.readBoolean();
        attackType = in.readInt();
        anomalyScore = in.readFloat();
        timestamp = in.readLong();
    }

    @Override
    public void writeToParcel(Parcel dest, int flags) {
        dest.writeFloat(soc);
        dest.writeFloat(soh);
        dest.writeFloat(voltage);
        dest.writeFloat(current);
        dest.writeInt(temperature);
        dest.writeInt(failSafeState);
        dest.writeInt(failSafeReason);
        dest.writeBoolean(attackDetected);
        dest.writeInt(attackType);
        dest.writeFloat(anomalyScore);
        dest.writeLong(timestamp);
    }

    @Override
    public int describeContents() { return 0; }

    public static final Creator<VehicleDataParcel> CREATOR = new Creator<VehicleDataParcel>() {
        @Override
        public VehicleDataParcel createFromParcel(Parcel in) { return new VehicleDataParcel(in); }
        @Override
        public VehicleDataParcel[] newArray(int size) { return new VehicleDataParcel[size]; }
    };
}
```

#### 4. VehicleDataService.java — SystemService (2주차)

`ivi_platform/service/VehicleDataService.java`:

```java
package com.capstone.vehicle.service;

import android.content.Context;
import android.os.RemoteCallbackList;
import android.os.RemoteException;
import android.util.Log;

public class VehicleDataService extends IVehicleDataService.Stub {
    private static final String TAG = "VehicleDataService";
    private final Context context;
    private final RemoteCallbackList<IVehicleDataListener> listeners = new RemoteCallbackList<>();
    private VehicleDataParcel latestData = new VehicleDataParcel();

    public VehicleDataService(Context context) {
        this.context = context;
    }

    @Override
    public VehicleDataParcel getLatestData() {
        return latestData;
    }

    @Override
    public void registerListener(IVehicleDataListener listener) {
        listeners.register(listener);
        Log.i(TAG, "Listener registered");
    }

    @Override
    public void unregisterListener(IVehicleDataListener listener) {
        listeners.unregister(listener);
        Log.i(TAG, "Listener unregistered");
    }

    /**
     * HAL 콜백에서 호출 — 새 데이터를 등록된 모든 리스너에게 전파
     */
    public void dispatchDataChanged(VehicleDataParcel data) {
        latestData = data;
        int n = listeners.beginBroadcast();
        for (int i = 0; i < n; i++) {
            try {
                listeners.getBroadcastItem(i).onDataChanged(data);
            } catch (RemoteException e) {
                Log.e(TAG, "Failed to dispatch to listener", e);
            }
        }
        listeners.finishBroadcast();
    }

    public void dispatchSecurityAlert(int attackType, float anomalyScore, int suspectCanId) {
        int n = listeners.beginBroadcast();
        for (int i = 0; i < n; i++) {
            try {
                listeners.getBroadcastItem(i).onSecurityAlert(attackType, anomalyScore, suspectCanId);
            } catch (RemoteException e) {
                Log.e(TAG, "Failed to dispatch security alert", e);
            }
        }
        listeners.finishBroadcast();
    }

    public void dispatchFailSafeTransition(int prevState, int newState, int reason) {
        int n = listeners.beginBroadcast();
        for (int i = 0; i < n; i++) {
            try {
                listeners.getBroadcastItem(i).onFailSafeTransition(prevState, newState, reason);
            } catch (RemoteException e) {
                Log.e(TAG, "Failed to dispatch fail-safe transition", e);
            }
        }
        listeners.finishBroadcast();
    }
}
```

#### 5. VehicleDataManager.java — 클라이언트 API (2주차)

`ivi_platform/service/VehicleDataManager.java`:

```java
package com.capstone.vehicle.service;

import android.content.Context;
import android.os.IBinder;
import android.os.RemoteException;
import android.util.Log;

/**
 * 앱에서 context.getSystemService("vehicle_data")로 접근하는 클라이언트 API.
 * VehicleDataService의 Binder 프록시를 감싸서 편의 메서드 제공.
 */
public class VehicleDataManager {
    private static final String TAG = "VehicleDataManager";
    private final IVehicleDataService service;

    public VehicleDataManager(IVehicleDataService service) {
        this.service = service;
    }

    public VehicleDataParcel getLatestData() {
        try {
            return service.getLatestData();
        } catch (RemoteException e) {
            Log.e(TAG, "getLatestData failed", e);
            return new VehicleDataParcel();
        }
    }

    public void registerListener(IVehicleDataListener listener) {
        try {
            service.registerListener(listener);
        } catch (RemoteException e) {
            Log.e(TAG, "registerListener failed", e);
        }
    }

    public void unregisterListener(IVehicleDataListener listener) {
        try {
            service.unregisterListener(listener);
        } catch (RemoteException e) {
            Log.e(TAG, "unregisterListener failed", e);
        }
    }
}
```

TC-IVI-003 검증:
```java
// 테스트 코드 의사 예시
VehicleDataManager manager = (VehicleDataManager) context.getSystemService("vehicle_data");
assertNotNull(manager);
assertTrue(manager instanceof VehicleDataManager);
```

TC-IVI-004 검증:
```java
// Mock HAL에서 데이터 주입 → ViewModel의 StateFlow 값 변경 확인
mockHal.dispatchData(new VehicleDataParcel(75.0f, ...));
assertEquals(75.0f, viewModel.getVehicleState().getValue().getSoc(), 0.01f);
```

#### 6. Jetpack Compose 프로젝트 셋업 (3주차)

`ivi_platform/app/build.gradle.kts` 핵심 의존성:

```kotlin
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    compileSdk = 33
    defaultConfig {
        minSdk = 33
        targetSdk = 33
    }
    buildFeatures {
        compose = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.3"
    }
}

dependencies {
    implementation("androidx.compose.ui:ui:1.5.4")
    implementation("androidx.compose.material3:material3:1.1.2")
    implementation("androidx.compose.ui:ui-tooling-preview:1.5.4")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.6.2")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.6.2")

    // 테스트
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4:1.5.4")
    debugImplementation("androidx.compose.ui:ui-test-manifest:1.5.4")
}
```

#### 7. DashboardViewModel.kt (3주차)

`ivi_platform/app/DashboardViewModel.kt`:

```kotlin
package com.capstone.vehicle.app

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.capstone.vehicle.app.data.VehicleRepository
import com.capstone.vehicle.app.data.VehicleUiState
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn

class DashboardViewModel(
    private val repository: VehicleRepository = VehicleRepository()
) : ViewModel() {

    val vehicleState: StateFlow<VehicleUiState> = repository.vehicleState
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5000),
            initialValue = VehicleUiState()
        )
}
```

#### 8. SocGauge.kt Composable (3주차)

`ivi_platform/app/SocGauge.kt`:

```kotlin
package com.capstone.vehicle.app

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp

@Composable
fun SocGauge(soc: Float, modifier: Modifier = Modifier) {
    val color = socColor(soc)

    Box(contentAlignment = Alignment.Center, modifier = modifier.size(200.dp)) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val strokeWidth = 20f
            val padding = strokeWidth / 2
            val arcSize = Size(size.width - strokeWidth, size.height - strokeWidth)

            // 배경 원호 (회색)
            drawArc(
                color = Color(0xFFE0E0E0),
                startAngle = 135f,
                sweepAngle = 270f,
                useCenter = false,
                topLeft = Offset(padding, padding),
                size = arcSize,
                style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
            )

            // SOC 값 원호 (색상별)
            drawArc(
                color = color,
                startAngle = 135f,
                sweepAngle = 270f * (soc / 100f).coerceIn(0f, 1f),
                useCenter = false,
                topLeft = Offset(padding, padding),
                size = arcSize,
                style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
            )
        }

        Text(
            text = "${soc.toInt()}%",
            style = MaterialTheme.typography.headlineLarge,
            color = color
        )
    }
}

/**
 * SOC 값에 따른 색상 결정.
 * - SOC >= 50% → Green (0xFF4CAF50)
 * - SOC >= 20% → Orange (0xFFFF9800)
 * - SOC < 20% → Red (0xFFF44336)
 */
fun socColor(soc: Float): Color = when {
    soc >= 50f -> Color(0xFF4CAF50)  // Green
    soc >= 20f -> Color(0xFFFF9800)  // Orange
    else       -> Color(0xFFF44336)  // Red
}
```

TC-IVI-005 테스트 `ivi_platform/app/test/SocGaugeTest.kt`:

```kotlin
package com.capstone.vehicle.app

import org.junit.Assert.assertEquals
import org.junit.Test
import androidx.compose.ui.graphics.Color

class SocGaugeTest {
    @Test
    fun `TC-IVI-005 SOC 80 Green`() {
        assertEquals(Color(0xFF4CAF50), socColor(80f))
    }

    @Test
    fun `TC-IVI-005 SOC 50 Green boundary`() {
        assertEquals(Color(0xFF4CAF50), socColor(50f))
    }

    @Test
    fun `TC-IVI-005 SOC 49 Orange`() {
        assertEquals(Color(0xFFFF9800), socColor(49f))
    }

    @Test
    fun `TC-IVI-005 SOC 20 Orange boundary`() {
        assertEquals(Color(0xFFFF9800), socColor(20f))
    }

    @Test
    fun `TC-IVI-005 SOC 19 Red`() {
        assertEquals(Color(0xFFF44336), socColor(19f))
    }

    @Test
    fun `TC-IVI-005 SOC 5 Red`() {
        assertEquals(Color(0xFFF44336), socColor(5f))
    }
}
```

실행:
```bash
cd ivi_platform/app
./gradlew test --tests "*.SocGaugeTest"
# 기대 출력: 6 tests passed
```

#### 9. secoc_verifier.cpp (4주차)

> **의존성**: 팀원A의 `secoc_module.cpp` TC-SEC-001~004 통과 후 구현 가능

`ivi_platform/hal/secoc_verifier.h`:

```cpp
#pragma once
#include <cstdint>
#include <string>

class SecOcVerifier {
public:
    bool loadKey(const std::string& keyPath);  // /etc/secoc/key.bin (32B)
    bool verify(uint16_t canId, const uint8_t* payload, uint8_t payloadLen,
                uint32_t receivedMac, uint32_t counter);
    bool checkCounter(uint32_t counter);

private:
    uint8_t sharedKey_[32];
    uint32_t lastCounter_ = 0;
    bool keyLoaded_ = false;
    int consecutiveFailures_ = 0;  // ICD §2.5.2 에스컬레이션
};
```

`ivi_platform/hal/secoc_verifier.cpp`:

```cpp
#include "secoc_verifier.h"
#include <openssl/hmac.h>
#include <openssl/crypto.h>
#include <cstring>
#include <fstream>
#include <android/log.h>

#define LOG_TAG "SecOcVerifier"
#define LOG_WARN(...)  __android_log_print(ANDROID_LOG_WARN, LOG_TAG, __VA_ARGS__)
#define LOG_ERR(...)   __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

bool SecOcVerifier::loadKey(const std::string& keyPath) {
    std::ifstream f(keyPath, std::ios::binary);
    if (!f.read(reinterpret_cast<char*>(sharedKey_), 32)) {
        LOG_ERR("Failed to load SecOC key from %s", keyPath.c_str());
        return false;
    }
    keyLoaded_ = true;
    return true;
}

bool SecOcVerifier::checkCounter(uint32_t counter) {
    // ICD §2.4: last < received <= last + 100
    if (counter <= lastCounter_) {
        LOG_WARN("ERR_COUNTER_OUT_OF_WINDOW: rx=%u <= last=%u", counter, lastCounter_);
        return false;
    }
    if (counter > lastCounter_ + 100) {
        LOG_WARN("ERR_COUNTER_OUT_OF_WINDOW: rx=%u > last+100=%u", counter, lastCounter_ + 100);
        return false;
    }
    lastCounter_ = counter;
    return true;
}

bool SecOcVerifier::verify(uint16_t canId, const uint8_t* payload, uint8_t payloadLen,
                           uint32_t receivedMac, uint32_t counter) {
    if (!keyLoaded_) {
        LOG_ERR("SecOC key not loaded");
        return false;
    }

    // ICD §1.4: HMAC_Input = CAN_ID(2B, BE) || RollingCounter(4B, BE) || Payload(8B)
    uint8_t hmacInput[14]; // 2 + 4 + 8
    hmacInput[0] = (canId >> 8) & 0xFF;
    hmacInput[1] = canId & 0xFF;
    hmacInput[2] = (counter >> 24) & 0xFF;
    hmacInput[3] = (counter >> 16) & 0xFF;
    hmacInput[4] = (counter >> 8) & 0xFF;
    hmacInput[5] = counter & 0xFF;
    std::memcpy(hmacInput + 6, payload, payloadLen);

    // HMAC-SHA256 계산
    unsigned int mdLen = 0;
    uint8_t md[32];
    HMAC(EVP_sha256(), sharedKey_, 32, hmacInput, sizeof(hmacInput), md, &mdLen);

    // 앞 4바이트 추출하여 비교 (timing-safe)
    uint8_t expectedMac[4] = {md[0], md[1], md[2], md[3]};
    uint8_t rxMac[4] = {
        static_cast<uint8_t>((receivedMac >> 24) & 0xFF),
        static_cast<uint8_t>((receivedMac >> 16) & 0xFF),
        static_cast<uint8_t>((receivedMac >> 8) & 0xFF),
        static_cast<uint8_t>(receivedMac & 0xFF)
    };

    if (CRYPTO_memcmp(expectedMac, rxMac, 4) != 0) {
        consecutiveFailures_++;
        // ICD §2.5.2 에스컬레이션
        if (consecutiveFailures_ >= 10) {
            LOG_ERR("ERR_HMAC_VERIFY_FAIL: 10+ consecutive — possible key desync");
        } else if (consecutiveFailures_ >= 4) {
            LOG_WARN("ERR_HMAC_VERIFY_FAIL: %d consecutive failures", consecutiveFailures_);
        } else {
            LOG_WARN("ERR_HMAC_VERIFY_FAIL");
        }
        return false;
    }

    // 카운터 윈도우 검사
    if (!checkCounter(counter)) {
        return false;
    }

    consecutiveFailures_ = 0;  // 성공 시 리셋
    return true;
}
```

#### 10. GitHub Actions Stage 2 — ARM64 빌드 (4주차)

ci.yml에 Stage 2 추가 (CICD_SPEC.md §2.3 기반):

```yaml
  stage2-arm64-build:
    name: "Stage 2: ARM64 Cross-Compile"
    needs: stage1-static-analysis
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build ARM64 Docker image
        run: docker build -f Dockerfile.arm64 -t ecu-builder:arm64 .

      - name: Cross-compile ECU binary
        run: |
          docker run --rm \
            -v ${{ github.workspace }}:/workspace \
            ecu-builder:arm64 \
            bash -c "
              cmake -S /workspace/adaptive_ecu \
                    -B /workspace/build \
                    -DCMAKE_TOOLCHAIN_FILE=/workspace/toolchain-aarch64.cmake \
                    -DCMAKE_BUILD_TYPE=Release && \
              cmake --build /workspace/build -j\$(nproc)
            "

      - name: Verify ARM64 binary
        run: file build/ecu_node_a | grep -q "ARM aarch64"

      - name: Upload binary artifact
        uses: actions/upload-artifact@v4
        with:
          name: ecu-arm64-binary
          path: build/ecu_node_a
          retention-days: 7
```

검증:
```
GitHub → Actions 탭 → Stage 2 녹색
Artifacts에 ecu-arm64-binary 다운로드 가능
```

#### 11. GitHub Actions Stage 3 — QEMU 테스트 (4주차)

ci.yml에 Stage 3 추가 (CICD_SPEC.md §2.4 기반):

```yaml
  stage3-qemu-test:
    name: "Stage 3: QEMU ARM64 Test + Coverage"
    needs: stage2-arm64-build
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4

      - name: Install QEMU user-mode + coverage tools
        run: |
          sudo apt-get install -y \
            qemu-user-static \
            gcc-aarch64-linux-gnu \
            lcov

      - name: Register QEMU binfmt
        run: sudo update-binfmts --enable qemu-aarch64

      - name: Build test binary (ARM64 + coverage flags)
        run: |
          docker run --rm \
            -v ${{ github.workspace }}:/workspace \
            ecu-builder:arm64 \
            bash -c "
              cmake -S /workspace/adaptive_ecu \
                    -B /workspace/build_test \
                    -DCMAKE_TOOLCHAIN_FILE=/workspace/toolchain-aarch64.cmake \
                    -DCMAKE_BUILD_TYPE=Debug \
                    -DENABLE_COVERAGE=ON \
                    -DBUILD_TESTS=ON && \
              cmake --build /workspace/build_test -j\$(nproc)
            "

      - name: Run tests via QEMU
        run: |
          cd build_test
          ctest --output-on-failure --timeout 60

      - name: Generate coverage report
        run: |
          lcov --capture \
               --directory build_test \
               --output-file coverage.info \
               --gcov-tool aarch64-linux-gnu-gcov \
               --ignore-errors mismatch
          lcov --remove coverage.info \
               '*/test/*' '/usr/*' \
               --output-file coverage_filtered.info
          lcov --summary coverage_filtered.info

      - name: Quality gate — Statement coverage >= 80%
        run: |
          LINES=$(lcov --summary coverage_filtered.info 2>&1 | grep "lines" | awk '{print $2}' | tr -d '%')
          echo "Statement coverage: ${LINES}%"
          python3 -c "
          import sys
          cov = float('${LINES}')
          if cov < 80.0:
              print(f'FAIL: Statement coverage {cov:.1f}% < 80%')
              sys.exit(1)
          print(f'PASS: Statement coverage {cov:.1f}%')
          "

      - name: Quality gate — Fail-safe Branch coverage 100%
        run: |
          lcov --extract coverage_filtered.info \
               '*/failsafe_sm.cpp' \
               --output-file failsafe_coverage.info
          BRANCHES=$(lcov --summary failsafe_coverage.info 2>&1 | grep "branches" | awk '{print $2}' | tr -d '%')
          python3 -c "
          import sys
          cov = float('${BRANCHES}')
          if cov < 100.0:
              print(f'FAIL: Fail-safe branch coverage {cov:.1f}% < 100%')
              sys.exit(1)
          print(f'PASS: Fail-safe branch coverage {cov:.1f}%')
          "

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          files: coverage_filtered.info
          flags: unit-tests
          token: ${{ secrets.CODECOV_TOKEN }}
```

**트러블슈팅 — QEMU binfmt 등록 실패**:
```bash
# GitHub Actions 러너에서 수동 확인
cat /proc/sys/fs/binfmt_misc/qemu-aarch64
# 출력이 없으면:
sudo update-binfmts --enable qemu-aarch64
# 또는 Docker 기반 binfmt 등록:
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
```

**트러블슈팅 — CTest 테스트 타임아웃**:
```bash
# QEMU 에뮬레이션은 네이티브보다 느림. timeout 증가:
ctest --output-on-failure --timeout 120
```

---

## M4 (9월) — 통합 UI + CI Stage 4

### 목표

대시보드 전체 UI 완성 (DashboardScreen + FailSafeIndicator + AlertBanner), CI Stage 4 SSH 자동 배포 구현, 통합 테스트 IT-001~005 참여, end-to-end 동작 영상 촬영.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | `DashboardScreen.kt` 전체 레이아웃 | 6시간 | 화면 구성 완료 + Preview 동작 |
| 1 | `FailSafeIndicator.kt` 상태 인디케이터 | 3시간 | Composable 4개 상태 표시 |
| 2 | `AlertBanner.kt` 공격 경보 배너 | 4시간 | TC-IVI-006 통과 |
| 2 | TC-IVI-007 (CRITICAL 풀스크린 Dialog) | 3시간 | PASSED |
| 3 | CI Stage 4: SSH 자동 배포 ci.yml | 4시간 | TC-CI-006 통과 |
| 3 | `scripts/health_check.sh` 작성 | 1시간 | 5회 재시도 동작 확인 |
| 3 | `ecu-node-a.service` systemd 유닛 파일 | 30분 | RPi4에서 서비스 등록 확인 |
| 3 | SSH 키 설정 (GitHub Secrets + RPi4) | 1시간 | SSH 접속 테스트 성공 |
| 4 | IT-001~005 통합 테스트 참여 | 4시간 | 전체 Pass |
| 4 | end-to-end 동작 영상 촬영 참여 | 2시간 | 영상 파일 저장 |
| 4 | `docs/SDD-IVI.md` §3 App 레이어 섹션 | 3시간 | PR 머지 |

**M4 총 예상 시간: 약 31.5시간**

### 수행 과정

#### 1. DashboardScreen.kt (1주차)

`ivi_platform/app/DashboardScreen.kt`:

```kotlin
package com.capstone.vehicle.app

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.capstone.vehicle.app.data.VehicleUiState

@Composable
fun DashboardScreen(viewModel: DashboardViewModel = viewModel()) {
    val state by viewModel.vehicleState.collectAsState()

    Box(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // 상단: SOC 게이지
            SocGauge(soc = state.soc, modifier = Modifier.padding(top = 32.dp))

            Spacer(modifier = Modifier.height(24.dp))

            // 중단: BMS 데이터 카드
            BmsDataCard(state = state)

            Spacer(modifier = Modifier.height(16.dp))

            // Fail-safe 상태 인디케이터
            FailSafeIndicator(state = state.failSafeState)

            Spacer(modifier = Modifier.weight(1f))

            // 통신 상태 표시
            if (state.stale) {
                Text(
                    text = "통신 끊김",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyLarge
                )
            }
        }

        // 공격 경보 배너 (상단 오버레이)
        AlertBanner(
            attackType = attackTypeName(state.attackType),
            visible = state.attackDetected,
            modifier = Modifier.align(Alignment.TopCenter)
        )

        // CRITICAL/SHUTDOWN 풀스크린 경고 Dialog
        if (state.failSafeState >= 2) {
            CriticalDialog(state = state)
        }
    }
}

@Composable
private fun BmsDataCard(state: VehicleUiState) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text("전압: ${"%.2f".format(state.voltage)} V")
            Text("전류: ${"%.1f".format(state.current)} A")
            Text("온도: ${state.temperature} °C")
            Text("SOH: ${"%.1f".format(state.soh)} %")
        }
    }
}

@Composable
private fun CriticalDialog(state: VehicleUiState) {
    val title = if (state.failSafeState == 3) "SHUTDOWN" else "CRITICAL"
    AlertDialog(
        onDismissRequest = { /* 닫기 불가 */ },
        title = { Text(title, color = MaterialTheme.colorScheme.error) },
        text = {
            Text("배터리 상태가 $title 입니다.\nSOC: ${"%.1f".format(state.soc)}%\n온도: ${state.temperature}°C")
        },
        confirmButton = {
            TextButton(onClick = { /* 수동 리셋 요청 */ }) {
                Text("확인")
            }
        }
    )
}

private fun attackTypeName(type: Int): String = when (type) {
    1 -> "Fuzzy Attack"
    2 -> "Replay Attack"
    3 -> "Spoofing Attack"
    4 -> "Flooding Attack"
    else -> "Unknown Attack"
}
```

#### 2. FailSafeIndicator.kt (1주차)

`ivi_platform/app/FailSafeIndicator.kt`:

```kotlin
package com.capstone.vehicle.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

@Composable
fun FailSafeIndicator(state: Int, modifier: Modifier = Modifier) {
    val (label, color) = when (state) {
        0 -> "NORMAL" to Color(0xFF4CAF50)       // Green
        1 -> "WARNING" to Color(0xFFFF9800)       // Orange
        2 -> "CRITICAL" to Color(0xFFF44336)      // Red
        3 -> "SHUTDOWN" to Color(0xFF9E9E9E)      // Gray
        else -> "UNKNOWN" to Color(0xFF757575)
    }

    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = modifier
            .fillMaxWidth()
            .background(color.copy(alpha = 0.15f), RoundedCornerShape(8.dp))
            .padding(12.dp)
    ) {
        Box(
            modifier = Modifier
                .size(12.dp)
                .background(color, RoundedCornerShape(6.dp))
        )
        Spacer(Modifier.width(8.dp))
        Text(
            text = "Fail-Safe: $label",
            style = MaterialTheme.typography.bodyLarge,
            color = color
        )
    }
}
```

#### 3. AlertBanner.kt (2주차)

`ivi_platform/app/AlertBanner.kt`:

```kotlin
package com.capstone.vehicle.app

import androidx.compose.animation.*
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

@Composable
fun AlertBanner(
    attackType: String,
    visible: Boolean,
    modifier: Modifier = Modifier
) {
    AnimatedVisibility(
        visible = visible,
        enter = slideInVertically(initialOffsetY = { -it }) + fadeIn(),
        exit = slideOutVertically(targetOffsetY = { -it }) + fadeOut(),
        modifier = modifier
    ) {
        Surface(
            color = Color(0xFFF44336),
            modifier = Modifier.fillMaxWidth()
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(16.dp)
            ) {
                Icon(
                    imageVector = Icons.Filled.Warning,
                    contentDescription = null,
                    tint = Color.White
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    text = "⚠ $attackType Detected!",
                    color = Color.White,
                    style = MaterialTheme.typography.titleMedium
                )
            }
        }
    }
}
```

TC-IVI-006 검증:
```kotlin
// Compose UI 테스트
@Test
fun `TC-IVI-006 AlertBanner shows Flooding Attack text`() {
    composeTestRule.setContent {
        AlertBanner(attackType = "Flooding Attack", visible = true)
    }
    composeTestRule.onNodeWithText("⚠ Flooding Attack Detected!").assertIsDisplayed()
}
```

TC-IVI-007 검증:
```kotlin
// Compose UI 테스트
@Test
fun `TC-IVI-007 CRITICAL shows fullscreen Dialog`() {
    composeTestRule.setContent {
        DashboardScreen(/* mock viewModel with failSafeState=2 */)
    }
    composeTestRule.onNodeWithText("CRITICAL").assertIsDisplayed()
}

@Test
fun `TC-IVI-007 NORMAL does not show Dialog`() {
    composeTestRule.setContent {
        DashboardScreen(/* mock viewModel with failSafeState=0 */)
    }
    composeTestRule.onNodeWithText("CRITICAL").assertDoesNotExist()
}
```

#### 4. ecu-node-a.service systemd 유닛 파일 (3주차)

RPi4에 배치할 파일 `/etc/systemd/system/ecu-node-a.service`:

```ini
[Unit]
Description=AUTOSAR ECU Node A Service
After=network.target

[Service]
Type=simple
User=deploy
ExecStart=/opt/ecu/ecu_node_a --interface can0
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

RPi4에서 서비스 등록:
```bash
sudo cp ecu-node-a.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ecu-node-a.service
sudo systemctl start ecu-node-a.service

# 동작 확인
systemctl is-active ecu-node-a.service
# 기대 출력: active

journalctl -u ecu-node-a.service -f
# 기대 출력: ECU 로그 실시간 출력
```

#### 5. SSH 키 설정 (3주차)

**Step 1: SSH 키 생성 (로컬 PC)**:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/rpi_deploy_key -N ""
cat ~/.ssh/rpi_deploy_key.pub
# 출력된 공개키를 RPi4에 등록
```

**Step 2: RPi4에 배포 계정 + 키 등록**:
```bash
# RPi4에서 실행
sudo useradd -m -s /bin/bash deploy
sudo usermod -aG sudo deploy

# sudoers 설정 (비밀번호 없이 systemctl restart 허용)
echo "deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart ecu-node-a.service" \
  | sudo tee /etc/sudoers.d/deploy-ecu

# 공개키 등록
sudo mkdir -p /home/deploy/.ssh
echo "<위에서 복사한 공개키>" | sudo tee /home/deploy/.ssh/authorized_keys
sudo chmod 700 /home/deploy/.ssh
sudo chmod 600 /home/deploy/.ssh/authorized_keys
sudo chown -R deploy:deploy /home/deploy/.ssh
```

**Step 3: GitHub Secrets 등록**:
```
Repository Settings → Secrets and variables → Actions → New repository secret

1. RPI_SSH_KEY → ~/.ssh/rpi_deploy_key (개인키 전체 내용 복사)
2. RPI_NODE_A_HOST → RPi4의 IP 주소 (예: 192.168.1.100)
3. CODECOV_TOKEN → Codecov 대시보드에서 토큰 복사
```

**Step 4: SSH 접속 테스트**:
```bash
ssh -i ~/.ssh/rpi_deploy_key deploy@<RPi4_IP>
# 기대 출력: deploy@rpi4:~$
```

#### 6. CI Stage 4: SSH 배포 (3주차)

ci.yml에 Stage 4 추가 (CICD_SPEC.md §2.5 기반):

```yaml
  stage4-deploy:
    name: "Stage 4: SSH Deploy + Health Check"
    needs: stage3-qemu-test
    runs-on: ubuntu-22.04
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - name: Download ARM64 binary
        uses: actions/download-artifact@v4
        with:
          name: ecu-arm64-binary
          path: dist/

      - name: Setup SSH key
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.RPI_SSH_KEY }}" > ~/.ssh/rpi_deploy_key
          chmod 600 ~/.ssh/rpi_deploy_key
          ssh-keyscan -H ${{ secrets.RPI_NODE_A_HOST }} >> ~/.ssh/known_hosts

      - name: Transfer binary via SCP
        run: |
          scp -i ~/.ssh/rpi_deploy_key \
              dist/ecu_node_a \
              deploy@${{ secrets.RPI_NODE_A_HOST }}:/opt/ecu/ecu_node_a.new

      - name: Restart service via SSH
        run: |
          ssh -i ~/.ssh/rpi_deploy_key \
              deploy@${{ secrets.RPI_NODE_A_HOST }} \
              "mv /opt/ecu/ecu_node_a.new /opt/ecu/ecu_node_a && \
               chmod +x /opt/ecu/ecu_node_a && \
               sudo systemctl restart ecu-node-a.service"

      - name: Health check
        run: |
          ssh -i ~/.ssh/rpi_deploy_key \
              deploy@${{ secrets.RPI_NODE_A_HOST }} \
              "bash /opt/ecu/scripts/health_check.sh"
```

#### 7. scripts/health_check.sh (3주차)

`scripts/health_check.sh`:

```bash
#!/bin/bash
SERVICE="ecu-node-a.service"
MAX_RETRY=5
INTERVAL=3

for i in $(seq 1 $MAX_RETRY); do
    STATUS=$(systemctl is-active "$SERVICE")
    if [ "$STATUS" = "active" ]; then
        echo "PASS: $SERVICE is active (attempt $i)"
        exit 0
    fi
    echo "Attempt $i/$MAX_RETRY: $SERVICE is $STATUS, retrying in ${INTERVAL}s..."
    sleep $INTERVAL
done

echo "FAIL: $SERVICE did not become active after $((MAX_RETRY * INTERVAL))s"
systemctl status "$SERVICE" --no-pager
exit 1
```

TC-CI-006 검증:
```bash
ssh deploy@<RPi4_IP> "bash /opt/ecu/scripts/health_check.sh"
# 기대 출력: PASS: ecu-node-a.service is active (attempt 1)
```

**트러블슈팅 — SSH 접속 타임아웃 (CI에서)**:
- GitHub Actions 러너가 RPi4에 접근 불가 → VPN/Tailscale/ngrok 설정 필요
- 대안: self-hosted runner를 동일 네트워크에 설치

**트러블슈팅 — health_check.sh 실패**:
```bash
# RPi4에서 직접 확인
sudo systemctl status ecu-node-a.service
journalctl -u ecu-node-a.service --since "5 minutes ago"
# ExecStart 경로 확인, 퍼미션 확인
ls -la /opt/ecu/ecu_node_a
# 기대: -rwxr-xr-x deploy deploy
```

#### 8. SDD-IVI.md §3 App 레이어 섹션 (4주차)

작성할 내용:
```markdown
## §3.4 App Layer — Jetpack Compose Dashboard

### 3.4.1 DashboardViewModel
- StateFlow<VehicleUiState> 기반 UI 상태 관리
- VehicleRepository로부터 데이터 수신
- TC-IVI-008 매핑: StateFlow 갱신 레이턴시 ≤20ms

### 3.4.2 SocGauge Composable
- 원형 게이지: Canvas drawArc + Stroke
- 색상 로직: ≥50%=Green, ≥20%=Orange, <20%=Red
- TC-IVI-005 매핑: 6 color cases

### 3.4.3 AlertBanner Composable
- AnimatedVisibility: slideInVertically + fadeIn
- 공격 유형 텍스트: "⚠ {AttackType} Detected!"
- TC-IVI-006 매핑

### 3.4.4 FailSafeIndicator Composable
- 4개 상태: NORMAL(Green), WARNING(Orange), CRITICAL(Red), SHUTDOWN(Gray)
- TC-IVI-007 매핑: CRITICAL/SHUTDOWN 시 풀스크린 Dialog
```

---

## M5 (10월) — 성능 최적화 + UI 개선

### 목표

e2e 레이턴시 측정 및 최적화 (TC-PERF-001: avg ≤50ms), BMS CAN 주기 정확도 검증 (TC-PERF-002: 100ms ±10ms), 대시보드 UI/UX 개선 (SocGauge 애니메이션, AlertBanner 공격 유형별 아이콘), ADR-004/006/007/010 완성.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | 레이턴시 측정 스크립트 작성 + 실행 | 4시간 | 1,000회 샘플링 결과 CSV 생성 |
| 1 | TC-PERF-001 (avg/P95/P99/max) 기록 | 1시간 | 측정값 기록 완료 |
| 1 | TC-PERF-002 (BMS CAN 100ms ±10ms) 측정 | 1시간 | 측정값 기록 완료 |
| 1 | P95/P99 병목 구간 분석 | 3시간 | 병목 계층 식별 (CAN/HAL/Binder/UI) |
| 2 | P95/P99 최적화 작업 | 6시간 | avg ≤50ms, max ≤100ms 달성 |
| 2 | `SocGauge.kt` 애니메이션 개선 | 3시간 | 부드러운 전환 동작 확인 |
| 3 | `AlertBanner.kt` UX 개선 (공격 유형별) | 3시간 | 아이콘 + 색상 구분 동작 |
| 3 | ADR-004 (HIDL vs AIDL) 완성 | 2시간 | PR 머지 |
| 3 | ADR-010 (Plan B 근거) 완성 | 2시간 | PR 머지 (Plan B 전환 시만) |
| 4 | ADR-006 (QEMU user-mode) 완성 | 2시간 | PR 머지 |
| 4 | ADR-007 (Docker 크로스컴파일) 완성 | 2시간 | PR 머지 |

**M5 총 예상 시간: 약 29시간**

### 수행 과정

#### 1. 레이턴시 측정 스크립트 (1주차)

`scripts/analyze_latency.py`:

```python
#!/usr/bin/env python3
"""
e2e 레이턴시 분석 스크립트.
candump -t d can0 출력에서 CAN ID 0x100 타임스탬프를 추출하여
P50/P95/P99/max 통계를 계산한다.

사용법:
  1. Node A + Node B 가동
  2. Node B에서: candump -t d can0 > latency_raw.txt &
  3. 10분 이상 수집 후: python3 analyze_latency.py latency_raw.txt
"""

import sys
import re
import statistics

def parse_candump(filepath):
    """candump -t d 출력 파싱. 각 줄: (timestamp_delta) can0 100#... 형식"""
    intervals = []
    timestamps = []
    pattern = re.compile(r'\((\d+\.\d+)\)\s+\w+\s+(\w+)#')

    with open(filepath, 'r') as f:
        for line in f:
            m = pattern.match(line)
            if m:
                ts = float(m.group(1))
                can_id = m.group(2)
                if can_id.upper() == '100':
                    timestamps.append(ts)

    if len(timestamps) < 2:
        print(f"ERROR: Only {len(timestamps)} samples found. Need at least 2.")
        sys.exit(1)

    for i in range(1, len(timestamps)):
        delta_ms = (timestamps[i] - timestamps[i-1]) * 1000.0
        intervals.append(delta_ms)

    return intervals

def analyze(intervals, label="Latency"):
    n = len(intervals)
    avg = statistics.mean(intervals)
    p50 = sorted(intervals)[int(n * 0.50)]
    p95 = sorted(intervals)[int(n * 0.95)]
    p99 = sorted(intervals)[int(n * 0.99)]
    mx = max(intervals)
    mn = min(intervals)
    std = statistics.stdev(intervals) if n > 1 else 0

    print(f"=== {label} Analysis ({n} samples) ===")
    print(f"  avg    = {avg:.2f} ms")
    print(f"  P50    = {p50:.2f} ms")
    print(f"  P95    = {p95:.2f} ms")
    print(f"  P99    = {p99:.2f} ms")
    print(f"  max    = {mx:.2f} ms")
    print(f"  min    = {mn:.2f} ms")
    print(f"  stddev = {std:.2f} ms")
    print()

    # 목표 판정
    if avg <= 50.0:
        print(f"  TC-PERF-001 avg <= 50ms: PASS ({avg:.2f}ms)")
    else:
        print(f"  TC-PERF-001 avg <= 50ms: FAIL ({avg:.2f}ms)")

    if mx <= 100.0:
        print(f"  TC-PERF-001 max <= 100ms: PASS ({mx:.2f}ms)")
    else:
        print(f"  TC-PERF-001 max <= 100ms: FAIL ({mx:.2f}ms)")

    # TC-PERF-002: 100ms ±10ms 판정
    in_range = sum(1 for x in intervals if 90.0 <= x <= 110.0)
    pct = in_range / n * 100
    print(f"  TC-PERF-002 100ms±10ms: {pct:.1f}% in range ({in_range}/{n})")

    return {'avg': avg, 'p50': p50, 'p95': p95, 'p99': p99, 'max': mx}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_latency.py <candump_output.txt>")
        sys.exit(1)

    intervals = parse_candump(sys.argv[1])
    results = analyze(intervals)
```

측정 실행 절차:
```bash
# Step 1: Node A + Node B 양쪽 가동 확인
ssh deploy@<NodeA_IP> "systemctl is-active ecu-node-a"
# 기대: active

# Step 2: Node B에서 CAN 트래픽 캡처 시작 (10분+)
candump -t d can0 > ~/latency_raw.txt &
sleep 600  # 10분 수집

# Step 3: 캡처 중지 + 분석
kill %1
python3 scripts/analyze_latency.py ~/latency_raw.txt
# 기대 출력 예시:
# === Latency Analysis (5847 samples) ===
#   avg    = 35.20 ms
#   P95    = 48.30 ms
#   P99    = 72.10 ms
#   max    = 95.40 ms
#   TC-PERF-001 avg <= 50ms: PASS (35.20ms)
```

#### 2. P95/P99 병목 구간 분석 (1주차)

세 구간의 레이턴시를 개별 측정하여 병목 식별:

| 구간 | 측정 방법 | 목표 |
|------|----------|------|
| CAN 수신 → HAL 콜백 | `vehicle_hal_impl.cpp`에 `std::chrono` 타이밍 로그 추가 | ≤5ms |
| HAL → Binder IPC → Service | Service 수신 시점 로그 - HAL 전송 시점 로그 | ≤15ms |
| Service → ViewModel → UI 렌더링 | StateFlow emit 시점 - Service 디스패치 시점 | ≤20ms |

HAL 구간 타이밍 측정 코드:
```cpp
// vehicle_hal_impl.cpp rxLoop() 내부
case 0x100: {
    auto t_start = std::chrono::steady_clock::now();
    auto status = parser_.parseBmsStatus(frame.data);
    for (auto* cb : callbacks_) {
        cb->onVehicleDataChanged(status);
    }
    auto t_end = std::chrono::steady_clock::now();
    auto us = std::chrono::duration_cast<std::chrono::microseconds>(t_end - t_start).count();
    LOG_INFO("HAL callback latency: %lld us", (long long)us);
    break;
}
```

#### 3. 최적화 기법 (2주차)

**기법 1: CAN 수신 스레드 우선순위 상향**:
```cpp
// vehicle_hal_impl.cpp start() 내부
void VehicleHalImpl::start() {
    running_ = true;
    rx_thread_ = std::thread(&VehicleHalImpl::rxLoop, this);

    // SCHED_FIFO 실시간 우선순위 설정 (root 또는 CAP_SYS_NICE 필요)
    struct sched_param param;
    param.sched_priority = 50;  // 1~99 범위
    if (pthread_setschedparam(rx_thread_.native_handle(), SCHED_FIFO, &param) != 0) {
        LOG_WARN("Failed to set RT priority for rx_thread_");
    }
}
```

**기법 2: CAN 소켓 버퍼 크기 증가**:
```bash
# RPi4에서 실행
sudo sysctl -w net.core.rmem_max=2097152
sudo sysctl -w net.core.rmem_default=1048576
# 영구 적용: /etc/sysctl.conf에 추가
echo "net.core.rmem_max=2097152" | sudo tee -a /etc/sysctl.conf
echo "net.core.rmem_default=1048576" | sudo tee -a /etc/sysctl.conf
```

**기법 3: HAL 콜백 경로 불필요 복사 제거**:
```cpp
// 변경 전: BmsStatus 값 복사
void onVehicleDataChanged(BmsStatus data);  // 값 복사

// 변경 후: const 참조 전달
void onVehicleDataChanged(const BmsStatus& data);  // 참조 전달
```

**기법 4: read() 타임아웃 설정 (stop() 시 즉시 종료)**:
```cpp
// init() 내부
struct timeval tv;
tv.tv_sec = 1;
tv.tv_usec = 0;
setsockopt(sock_, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
```

#### 4. SocGauge.kt 애니메이션 개선 (2주차)

```kotlin
@Composable
fun SocGauge(soc: Float, modifier: Modifier = Modifier) {
    // 애니메이션: 이전 값 → 새 값 부드러운 전환 (300ms)
    val animatedSoc by animateFloatAsState(
        targetValue = soc,
        animationSpec = tween(durationMillis = 300, easing = FastOutSlowInEasing),
        label = "soc-animation"
    )

    val color = socColor(animatedSoc)

    Box(contentAlignment = Alignment.Center, modifier = modifier.size(200.dp)) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val strokeWidth = 20f
            val padding = strokeWidth / 2
            val arcSize = Size(size.width - strokeWidth, size.height - strokeWidth)

            // 배경 원호
            drawArc(
                color = Color(0xFFE0E0E0),
                startAngle = 135f, sweepAngle = 270f,
                useCenter = false,
                topLeft = Offset(padding, padding), size = arcSize,
                style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
            )

            // 값 원호 (애니메이션 적용)
            drawArc(
                color = color,
                startAngle = 135f,
                sweepAngle = 270f * (animatedSoc / 100f).coerceIn(0f, 1f),
                useCenter = false,
                topLeft = Offset(padding, padding), size = arcSize,
                style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
            )
        }

        Text(
            text = "${animatedSoc.toInt()}%",
            style = MaterialTheme.typography.headlineLarge,
            color = color
        )
    }
}
```

필요한 import 추가:
```kotlin
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.core.FastOutSlowInEasing
```

#### 5. AlertBanner.kt UX 개선 — 공격 유형별 아이콘 + 색상 (3주차)

```kotlin
@Composable
fun AlertBanner(
    attackType: String,
    attackCode: Int = 0,
    visible: Boolean,
    modifier: Modifier = Modifier
) {
    val (bgColor, icon) = when (attackCode) {
        1 -> Color(0xFFE91E63) to Icons.Filled.BugReport       // Fuzzy — 핑크
        2 -> Color(0xFF9C27B0) to Icons.Filled.Replay           // Replay — 보라
        3 -> Color(0xFFF44336) to Icons.Filled.SecurityUpdate   // Spoofing — 빨강
        4 -> Color(0xFFFF5722) to Icons.Filled.FlashOn          // Flooding — 주황
        else -> Color(0xFFF44336) to Icons.Filled.Warning       // 기본 — 빨강
    }

    AnimatedVisibility(
        visible = visible,
        enter = slideInVertically(initialOffsetY = { -it }) + fadeIn(),
        exit = slideOutVertically(targetOffsetY = { -it }) + fadeOut(),
        modifier = modifier
    ) {
        Surface(color = bgColor, modifier = Modifier.fillMaxWidth()) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(16.dp)
            ) {
                Icon(imageVector = icon, contentDescription = null, tint = Color.White)
                Spacer(Modifier.width(8.dp))
                Text(
                    text = "⚠ $attackType Detected!",
                    color = Color.White,
                    style = MaterialTheme.typography.titleMedium
                )
            }
        }
    }
}
```

#### 6. ADR 작성 템플릿 (3~4주차)

모든 ADR에 공통 적용할 구조:

```markdown
# ADR-NNN: [결정 제목]

## 상태
[Proposed | Accepted | Deprecated | Superseded by ADR-XXX]

## 맥락
어떤 문제를 해결해야 했는가? 어떤 조건/제약이 있었는가?

## 고려한 대안
| 대안 | 장점 | 단점 |
|------|------|------|
| 대안 A | ... | ... |
| 대안 B | ... | ... |
| **선택: 대안 X** | ... | ... |

## 결정
무엇을 선택했는가?

## 근거
왜 이 선택을 했는가? (기술적 근거 + 실험 데이터)

## 결과
이 결정으로 인한 영향은? (구현 방식, 제약사항, 향후 변경 가능성)

## 관련 문서
- SRS FR-XXX, SDD-XXX §N, TEST_PLAN TC-XXX
```

**ADR-006 (QEMU user-mode) 작성 내용**:
```markdown
# ADR-006: QEMU user-mode 에뮬레이션 CI 테스트 전략

## 상태: Accepted
## 맥락:
GitHub Actions ubuntu-22.04 러너(x86_64)에서 ARM64 바이너리 테스트 필요.
풀 시스템 에뮬레이션(qemu-system-aarch64) vs user-mode(qemu-user-static) 선택.

## 고려한 대안:
| 대안 | 장점 | 단점 |
|------|------|------|
| qemu-system | 커널 포함 완전 에뮬레이션 | 느림 (수분), 설정 복잡 |
| **qemu-user-static** | 빠름 (수초), binfmt 투명 실행 | SocketCAN 미지원 |
| self-hosted runner | 실제 ARM64 | 유지보수 부담, 비용 |

## 결정: qemu-user-static
## 근거:
- 단위 테스트(입출력, 상태머신)는 HW 독립적 → QEMU user-mode 충분
- SocketCAN/I2C 의존 테스트 → Mock 주입으로 우회 (CICD_SPEC §4.2)
- 실행 속도 10~30초 (CI에 적합)

## 결과:
- CAN CDD 테스트: MockCanDriver 사용
- SensorSimulator: CONSTANT 모드 강제
- 타이밍 테스트: 실 RPi4에서만 수행 (통합 테스트)
```

---

## M6 (11월) — 문서 + README + Coverage

### 목표

e2e 레이턴시 최종 최적화 (TC-PERF-001 avg ≤50ms 확정), IDS 응답 시간 최종 확인 (TC-PERF-003 ≤3s), SDD-IVI.md 전체 완성, README.md 완성, Codecov Statement ≥80% 확인.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | e2e 레이턴시 최종 최적화 | 6시간 | TC-PERF-001 avg ≤50ms 달성 |
| 1 | TC-PERF-003 (IDS 응답 ≤3초) 최종 확인 | 2시간 | PASSED |
| 2 | `docs/SDD-IVI.md` 전체 작성 | 8시간 | HAL/Service/App + TC 매핑 완료 |
| 3 | `README.md` 완성 | 6시간 | 아키텍처 다이어그램 + 빌드 방법 + 결과 |
| 3 | Codecov 리포트 확인 + 보강 | 4시간 | Statement ≥80% |
| 4 | CI 전체 녹색 최종 확인 | 2시간 | TC-CI-001~006 전체 Pass |

**M6 총 예상 시간: 약 28시간**

### 수행 과정

#### 1. e2e 레이턴시 최종 최적화 (1주차)

이전 M5에서 측정한 P95/P99 결과를 기반으로 추가 최적화:

```bash
# 최종 측정 (1,000회 이상)
candump -t d can0 > ~/latency_final.txt &
sleep 600
kill %1
python3 scripts/analyze_latency.py ~/latency_final.txt
```

목표값 확인:
```
TC-PERF-001 avg <= 50ms: PASS
TC-PERF-001 max <= 100ms: PASS
```

최적화가 부족한 경우 추가 시도:
- CAN 수신 버퍼 `SO_RCVBUF` 증가
- rx_thread_ CPU affinity 고정 (`pthread_setaffinity_np`)
- Binder IPC 대신 SharedMemory 사용 (최후 수단)

#### 2. TC-PERF-003 IDS 응답 시간 확인 (1주차)

```bash
# 공격 시작 시각 기록
date +%s%N > /tmp/attack_start.txt
python3 security/attacks/flooding_attack.py --duration 10 &

# Node B에서 0x200 수신 시각 캡처
candump -t a can0 | grep "200#" | head -1 > /tmp/ids_alert.txt

# 시간 차이 계산
python3 -c "
start = int(open('/tmp/attack_start.txt').read().strip()) / 1e9
# 0x200 수신 타임스탬프 파싱
import re
line = open('/tmp/ids_alert.txt').read()
ts = float(re.search(r'\((\d+\.\d+)\)', line).group(1))
delta = ts - start
print(f'IDS response time: {delta:.3f}s')
if delta <= 3.0:
    print('TC-PERF-003: PASS')
else:
    print('TC-PERF-003: FAIL')
"
```

#### 3. SDD-IVI.md 작성 가이드 (2주차)

SDD-IVI.md 전체 구조 (각 섹션에 반드시 포함할 내용):

```markdown
# SDD-IVI: IVI Software Design Document

## §1. 문서 개요
- 목적, 범위, 참조 문서(ICD, SRS, TEST_PLAN)

## §2. 시스템 아키텍처
- 3계층 다이어그램: HAL Layer ← Service Layer ← App Layer
- 각 계층 역할 + 의존 관계

## §3. 모듈 상세 설계

### §3.1 HAL Layer
- can_parser.h/.cpp: CAN 프레임 파싱 로직 (ICD §1.2~1.5 매핑)
  - TC 매핑: TC-IVI-002-a/b/c
- vehicle_hal_impl.h/.cpp: SocketCAN rx_thread_, 콜백 관리
  - TC 매핑: TC-IVI-001
- secoc_verifier.h/.cpp: HMAC 검증 (ICD §2.3 수신 절차)
  - TC 매핑: TC-SEC-001~004 (팀원A TC 참조)

### §3.2 Service Layer
- IVehicleDataService.aidl: Binder IPC 인터페이스 정의
  - TC 매핑: TC-IVI-003
- VehicleDataService.java: RemoteCallbackList 기반 리스너 디스패치
  - TC 매핑: TC-IVI-003, TC-IVI-004
- VehicleDataManager.java: 앱 클라이언트 편의 API
  - TC 매핑: TC-IVI-004

### §3.3 App Layer
- DashboardViewModel.kt: StateFlow<VehicleUiState>
  - TC 매핑: TC-IVI-004, TC-IVI-008
- SocGauge.kt: 원형 게이지 Composable + 색상 로직
  - TC 매핑: TC-IVI-005 (6 cases)
- AlertBanner.kt: 공격 경보 배너 + 유형별 아이콘
  - TC 매핑: TC-IVI-006
- FailSafeIndicator.kt: 4상태 인디케이터
- DashboardScreen.kt: 전체 레이아웃 + CriticalDialog
  - TC 매핑: TC-IVI-007

## §4. 데이터 흐름
- CAN Frame → can_parser → vehicle_hal_impl → callback →
  VehicleDataService (Binder) → VehicleDataManager →
  DashboardViewModel (StateFlow) → Composable UI

## §5. 에러 처리
- ICD §3.3 에러 코드 매핑 (ERR_CAN_INIT_FAIL ~ ERR_UNKNOWN_CAN_ID)
- ICD §2.5 타임아웃/에스컬레이션 정책

## §6. 테스트 케이스 매핑 요약
| TC ID | 모듈 | 검증 대상 |
|-------|------|----------|
| TC-IVI-001 | HAL | CAN 수신 콜백 |
| TC-IVI-002 | HAL | CAN 파싱 정확도 |
| ... | ... | ... |
```

#### 4. README.md 템플릿 (3주차)

```markdown
# AUTOSAR 계층 기반 IVI-ECU 통합 플랫폼

[![CI](https://github.com/<user>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<user>/<repo>/actions)
[![codecov](https://codecov.io/gh/<user>/<repo>/branch/main/graph/badge.svg)](https://codecov.io/gh/<user>/<repo>)

## 프로젝트 개요
AUTOSAR Adaptive 기반 BMS ECU(Node A)와 Android IVI 대시보드(Node B)의
CAN 버스 통합 플랫폼. SecOC HMAC 인증 + Isolation Forest ML IDS 보안 계층 포함.

## 시스템 아키텍처
![Architecture](docs/architecture.png)

```
[Node A - RPi4 Ubuntu]           CAN Bus (500kbps)           [Node B - RPi4 AOSP/Ubuntu]
├── BSW Layer (C++)              ◄──── 0x100 BMS_Status ───► ├── HAL Layer (C++)
│   ├── CAN CDD                 ◄──── 0x101 FailSafe ─────► │   ├── can_parser
│   ├── SecOC HMAC               ◄──── 0x102 SecOC ────────► │   ├── secoc_verifier
│   └── Watchdog                 ◄──── 0x200 IDS_Alert ────► │   └── vehicle_hal_impl
├── App Layer (C++)                                           ├── Service Layer (Java)
│   ├── EKF SOC                                               │   └── VehicleDataService
│   ├── Fail-safe FSM                                         └── App Layer (Kotlin)
│   └── BMS Component                                             ├── DashboardViewModel
└── Security (Python)                                              ├── SocGauge
    ├── IDS Engine                                                 ├── AlertBanner
    └── Attack Simulator                                           └── FailSafeIndicator
```

## 빌드 방법

### Node A (C++ ECU)
```bash
docker build -f Dockerfile.arm64 -t capstone-arm64 .
docker run --rm -v $(pwd):/workspace capstone-arm64 \
  bash -c "cmake -S /workspace/adaptive_ecu -B /workspace/build \
    -DCMAKE_TOOLCHAIN_FILE=/workspace/toolchain-aarch64.cmake && \
    cmake --build /workspace/build -j$(nproc)"
```

### Node B (Android IVI / Ubuntu IVI)
```bash
# Plan A (AOSP)
cd ~/aosp && source build/envsetup.sh && lunch rpi4-eng && make -j$(nproc)

# Plan B (Ubuntu + Qt/Flutter)
cd ivi_platform && mkdir build && cd build && cmake .. && make
```

## 실험 결과

### SecOC + IDS Ablation Study
| Config | Spoofing 차단율 | Replay 차단율 | Flooding 탐지율 | Fuzzy 차단율 |
|--------|----------------|--------------|----------------|-------------|
| 방어 없음 | 0% | 0% | 0% | 0% |
| SecOC only | 100% | 100% | N/A | 100% |
| SecOC+IDS | 100% | 100% | (실측값)% | 100% |

### e2e 레이턴시
| 지표 | 측정값 | 목표 |
|------|--------|------|
| avg | (실측)ms | ≤50ms |
| P95 | (실측)ms | — |
| P99 | (실측)ms | — |
| max | (실측)ms | ≤100ms |

## 문서
- [ICD](docs/ICD.md) — 인터페이스 규격
- [SDD-ECU](docs/SDD-ECU.md) — Node A 설계 문서
- [SDD-IVI](docs/SDD-IVI.md) — Node B 설계 문서
- [TARA](docs/TARA.md) — 보안 위협 분석
- [TEST_PLAN](docs/TEST_PLAN.md) — 테스트 계획

## 라이선스
MIT
```

#### 5. Codecov 설정 및 배지 (3주차)

**Step 1: Codecov 연동**:
1. [codecov.io](https://codecov.io) → GitHub 로그인 → Repository 추가
2. Repository Settings에서 `CODECOV_TOKEN` 복사
3. GitHub Repository Settings → Secrets → `CODECOV_TOKEN` 등록

**Step 2: codecov.yml (프로젝트 루트)**:
```yaml
codecov:
  require_ci_to_pass: true

coverage:
  status:
    project:
      default:
        target: 80%
        threshold: 2%
    patch:
      default:
        target: 80%

ignore:
  - "adaptive_ecu/test/"
  - "security/tests/"
```

**Step 3: 커버리지 부족 시 보강**:
```bash
# 현재 커버리지 확인
lcov --summary coverage_filtered.info
# 미커버 파일 식별
lcov --list coverage_filtered.info | sort -t'|' -k2 -n
# 커버리지 낮은 파일에 테스트 추가
```

커버리지 80% 미달 시 보강 우선순위:
1. `can_parser.cpp` — 모든 CAN ID 파싱 경로 테스트
2. `vehicle_hal_impl.cpp` — 에러 경로 (CAN 초기화 실패, 읽기 실패)
3. `secoc_verifier.cpp` — 검증 실패 에스컬레이션 경로

---

## M7 (12월) — 안정성 + CI 점검

### 목표

24시간 장시간 운행 테스트 (메모리 누수, 프로세스 안정성), CI/CD 4단계 파이프라인 최종 점검, 문서 교차 검토, 최종 통합 테스트 IT-001~005, TC-PERF 최종 수치 확정.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | 24시간 장시간 운행 테스트 시작 | 2시간 (설정) + 24시간 (운행) | 가동 시작 기록 |
| 1 | 메모리 누수 사전 점검 (ASan/Valgrind) | 4시간 | 누수 0건 또는 수정 완료 |
| 2 | 장시간 운행 결과 분석 | 3시간 | 분석 보고서 작성 |
| 2 | CI/CD Stage 1~4 전체 파이프라인 점검 | 3시간 | TC-CI-001~006 전체 Pass |
| 3 | 문서 교차 검토 참여 (SDD-ECU, TARA 리뷰) | 4시간 | PR 코멘트 완료 |
| 3 | ICD.md ↔ 실제 구현 일치 검증 | 2시간 | 불일치 항목 0건 또는 수정 |
| 4 | 최종 통합 테스트 IT-001~005 | 4시간 | 전체 Pass |
| 4 | TC-PERF-001~003 최종 수치 기록 | 2시간 | 최종값 확정 |

**M7 총 예상 시간: 약 24시간 + 24시간 운행**

### 수행 과정

#### 1. 메모리 누수 사전 점검 — AddressSanitizer (1주차)

빌드 시 ASan 활성화:
```bash
# CMakeLists.txt에 ASan 옵션 추가 (로컬 빌드용)
cmake -S adaptive_ecu -B build_asan \
  -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_CXX_FLAGS="-fsanitize=address -fno-omit-frame-pointer" \
  -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=address"
cmake --build build_asan

# ASan으로 테스트 실행
ASAN_OPTIONS=detect_leaks=1 ./build_asan/ecu_node_a --interface vcan0 &
sleep 60  # 1분 가동
kill %1
# 종료 시 ASan 리포트 확인 — 누수 있으면 출력됨
```

기대 출력 (정상):
```
=================================================================
==12345==SUMMARY: AddressSanitizer: 0 error(s) found.
```

**트러블슈팅 — ASan에서 누수 발견**:
```
ERROR: LeakSanitizer: detected memory leaks
Direct leak of 128 byte(s) in 1 object(s) allocated from:
    #0 0x... in operator new
    #1 0x... in VehicleHalImpl::init
```
→ 해당 함수에서 `new`로 할당한 메모리의 `delete` 누락 확인 → 수정

#### 2. 메모리 누수 사전 점검 — Valgrind (1주차 대안)

```bash
# Valgrind 설치 (x86 빌드에서만 사용 가능)
sudo apt install -y valgrind

# x86 네이티브 빌드
cmake -S adaptive_ecu -B build_valgrind -DCMAKE_BUILD_TYPE=Debug
cmake --build build_valgrind

# Valgrind 실행 (1분 가동 후 종료)
timeout 60 valgrind --leak-check=full --show-leak-kinds=all \
  --track-origins=yes ./build_valgrind/ecu_node_a --interface vcan0 \
  2>&1 | tee valgrind_report.txt
```

기대 출력 (정상):
```
==12345== LEAK SUMMARY:
==12345==    definitely lost: 0 bytes in 0 blocks
==12345==    indirectly lost: 0 bytes in 0 blocks
```

Valgrind에서 발견된 누수 수정 후 재확인:
```bash
grep "definitely lost" valgrind_report.txt
# 기대: "definitely lost: 0 bytes in 0 blocks"
```

#### 3. 24시간 장시간 운행 테스트 (1주차)

```bash
# === Node A 시작 ===
ssh deploy@<NodeA_IP>
sudo systemctl start ecu-node-a.service
# 시작 시각 기록
echo "Start: $(date)" >> /tmp/longrun_log.txt

# === Node B 대시보드 시작 ===
# (AOSP 또는 Ubuntu에 따라 다름)

# === 24시간 모니터링 셋업 ===
# 1시간마다 메모리 사용량 기록
while true; do
    echo "$(date) $(ps -o rss,vsz,pid,comm -p $(pgrep ecu_node_a))" >> /tmp/memory_log.txt
    sleep 3600
done &

# === 24시간 후 확인 ===
# 1. 프로세스 생존 확인
ps aux | grep ecu_node_a
# 기대: 프로세스 실행 중

# 2. 메모리 증가 추세 확인
cat /tmp/memory_log.txt
# RSS가 시간에 따라 단조 증가하면 → 메모리 누수 의심

# 3. 프로세스 재시작 여부 확인
journalctl -u ecu-node-a.service --since "24 hours ago" | grep -i restart
# 기대: restart 로그 없음

# 4. CAN 통신 에러 카운트
ip -s link show can0 | grep errors
# 기대: errors 0 또는 매우 적은 수

# 5. 결과 정리
echo "End: $(date)" >> /tmp/longrun_log.txt
echo "Restarts: $(journalctl -u ecu-node-a.service --since '24 hours ago' | grep -c restart)" >> /tmp/longrun_log.txt
```

장시간 운행 결과 기록 템플릿:

| 항목 | 결과 |
|------|------|
| 운행 시간 | 24시간 / ___시간 (중단 시 사유) |
| 프로세스 재시작 횟수 | ___회 |
| RSS 시작 | ___MB |
| RSS 종료 | ___MB |
| RSS 증가량 | ___MB (___% 증가) |
| CAN 에러 횟수 | ___건 |
| 판정 | PASS / FAIL |

#### 4. CI/CD 파이프라인 최종 점검 체크리스트 (2주차)

| TC | 검증 내용 | 실행 방법 | 결과 |
|----|----------|----------|------|
| TC-CI-001 | PR 생성 시 자동 기동 | develop에 PR 생성 → Actions 탭 확인 | [ ] PASS |
| TC-CI-002 | cppcheck Error 시 중단 | 의도적 누수 코드 push → Stage 1 빨간색 | [ ] PASS |
| TC-CI-003 | ARM64 바이너리 생성 | Artifacts 다운로드 → `file` 확인 | [ ] PASS |
| TC-CI-004 | Coverage ≥80% | Codecov 대시보드 확인 | [ ] PASS (___%) |
| TC-CI-005 | SSH 자동 배포 | main 머지 → RPi4 바이너리 갱신 확인 | [ ] PASS |
| TC-CI-006 | Health Check | `systemctl is-active ecu-node-a` = active | [ ] PASS |

TC-CI-002 의도적 실패 테스트:
```bash
# 의도적 메모리 누수 코드 추가
git switch -c test/ci-fail-check
cat >> adaptive_ecu/src/bsw/test_leak.cpp << 'EOF'
void intentional_leak() {
    int* p = new int[100];
    // delete 없음 → cppcheck 경고
}
EOF
git add adaptive_ecu/src/bsw/test_leak.cpp
git commit -m "test(ci): 의도적 cppcheck 실패 테스트"
git push origin test/ci-fail-check
# PR 생성 → Stage 1 빨간색 확인 → 브랜치 삭제
```

#### 5. 문서 교차 검토 방법론 (3주차)

교차 검토 체크리스트 (팀원B → 팀원A 문서 리뷰):

**SDD-ECU.md 리뷰 항목**:
- [ ] CAN ID 0x100~0x200 바이트 레이아웃이 ICD.md §1.2~1.5와 일치하는가?
- [ ] SecOC HMAC 입력 구성이 ICD.md §1.4와 일치하는가?
- [ ] Fail-safe 전이 조건이 ICD.md §1.3 Reason 코드와 일치하는가?
- [ ] TC 매핑이 TEST_PLAN.md TC-BSW/BMS/SEC와 정확히 대응하는가?
- [ ] 코드 예시의 변수명/함수명이 실제 구현과 일치하는가?

**TARA.md 리뷰 항목**:
- [ ] 위협 시나리오가 실제 공격 스크립트(security/attacks/)와 대응하는가?
- [ ] Risk Level 판정이 Feasibility Rating 계산과 일치하는가?
- [ ] 대응 방안이 실제 구현(SecOC, IDS)과 매핑되는가?

리뷰 절차:
```bash
# 1. 리뷰 브랜치 체크아웃
git switch develop && git pull
# 2. docs/ 파일 열어서 항목별 검토
# 3. GitHub PR에 코멘트 작성 (항목별 체크)
# 4. 불일치 발견 시 수정 사항 구체적으로 기록
```

#### 6. 최종 통합 테스트 (4주차)

IT-001~005 재검증 절차 (M4와 동일, 최종 확인):

```bash
# IT-001: Node A → Node B BMS 데이터 전달
# Node A 가동 상태에서 Node B logcat 확인
adb logcat -s VehicleHAL | head -20
# 기대: "BMS_Status: SOC=XX.X%, V=XX.XXV, T=XX°C" 출력

# IT-002: Fail-safe CRITICAL 전이 → UI 팝업
# Node A에서 SOC=4.5% 시뮬레이션 → Node B 화면 확인
# 기대: CRITICAL 풀스크린 Dialog 표시

# IT-003: SecOC 정상 인증
# 동일 키 양 노드 배포 → 정상 데이터 수신 확인
# 기대: 인증 성공 로그

# IT-004: 변조 MAC 차단
# Node A 키 변경 → Node B ERR_HMAC_VERIFY_FAIL 로그
# 기대: 데이터 갱신 없음

# IT-005: Flooding → IDS → AlertBanner
python3 security/attacks/flooding_attack.py --duration 10
# Node B에서 ≤3초 내 "⚠ Flooding Attack Detected!" 표시 확인
```

TC-PERF 최종 수치 기록:

| TC | 지표 | 최종 측정값 | 목표 | 결과 |
|----|------|-----------|------|------|
| TC-PERF-001 | avg latency | ___ms | ≤50ms | [ ] PASS |
| TC-PERF-001 | max latency | ___ms | ≤100ms | [ ] PASS |
| TC-PERF-002 | CAN 주기 정확도 | ±___ms | ±10ms | [ ] PASS |
| TC-PERF-003 | IDS 응답 시간 | ___s | ≤3s | [ ] PASS |

---

## M8 (1월) — 발표 준비

### 목표

데모 시나리오 A/B 리허설 3회, 발표 자료 완성 (팀원B 직무 어필 슬라이드 포함), 최종 보고서 팀원B 담당 섹션 작성, GitHub README 최종화, GitHub Releases 8개 + v1.0.0 태그.

### 체크리스트

| 주차 | 작업 | 예상 시간 | 완료 확인 기준 |
|------|------|----------|---------------|
| 1 | 데모 시나리오 A 구성 + 리허설 1회 | 3시간 | 시나리오 A 정상 동작 |
| 1 | 데모 시나리오 B 구성 + 리허설 1회 | 3시간 | 시나리오 B 정상 동작 |
| 1 | 발표 자료 초안 — 팀원B 슬라이드 | 4시간 | 슬라이드 구조 확정 |
| 2 | 최종 보고서 — IVI/CI 섹션 작성 | 6시간 | 초안 완성 |
| 2 | 발표 자료 수정 (피드백 반영) | 2시간 | 수정 완료 |
| 2 | 리허설 2회차 | 2시간 | 완료 |
| 3 | 리허설 3회차 (최종) | 2시간 | 완료 |
| 3 | 발표 자료 최종 완성 | 2시간 | 최종본 확정 |
| 3 | 최종 보고서 제출 | 1시간 | 제출 완료 |
| 4 | GitHub README 최종화 | 2시간 | 실측값 삽입 완료 |
| 4 | GitHub Releases 8개 작성 | 3시간 | 8개 릴리즈 완료 |
| 4 | `v1.0.0` 태그 생성 + push | 15분 | 태그 확인 |

**M8 총 예상 시간: 약 30시간**

### 수행 과정

#### 1. 데모 시나리오 (1주차)

**시나리오 A — 정상 동작 (3분)**:
1. Node A BMS 가동 → SOC/전압/전류/온도 대시보드 실시간 표시
2. SOC 서서히 감소 → SocGauge 색상 전환 (Green → Orange → Red)
3. SOC < 20% → WARNING 전이 → FailSafeIndicator 변경
4. SOC < 5% → CRITICAL 전이 → 풀스크린 Dialog 팝업
5. 수동 리셋 → NORMAL 복귀

**시나리오 B — 보안 공격 (3분)**:
1. 보안 없는 상태 (SecOC off): Spoofing → 가짜 SOC=100% 표시 (위험성 시연)
2. SecOC 활성화: 동일 Spoofing → ERR_HMAC_VERIFY_FAIL → 차단 확인
3. Flooding 공격 → IDS 탐지 → CAN 0x200 → AlertBanner 등장 (≤3초)
4. 공격 중단 → AlertBanner 사라짐

**백업 계획**:
- 하드웨어 장애 시 → 사전 녹화 영상 재생
- CAN 연결 불안정 시 → vcan0 가상 버스 fallback 데모

데모 체크리스트 (리허설마다 확인):
- [ ] CAN 케이블 연결 상태
- [ ] Node A ecu-node-a.service 가동 중
- [ ] Node B 대시보드 앱 실행 중
- [ ] 공격 스크립트 경로 확인
- [ ] HDMI 외부 모니터 연결 (시연용)
- [ ] 화면 녹화 소프트웨어 준비

#### 2. 팀원B 발표 슬라이드 내용 구성 (1~2주차)

팀원B 담당 슬라이드 구성 (5~7장):

**슬라이드 1: IVI SW 플랫폼 아키텍처**
```
[제목] Node B: IVI Software Platform Architecture

[내용]
┌─────────────────────────────────────────┐
│           App Layer (Kotlin)            │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │SocGauge  │ │AlertBanner│ │FailSafe │ │
│  └──────────┘ └──────────┘ └─────────┘ │
│        DashboardViewModel (StateFlow)   │
├─────────────────────────────────────────┤
│         Service Layer (Java)            │
│  VehicleDataService (Binder IPC)        │
│  VehicleDataManager (Client API)        │
├─────────────────────────────────────────┤
│           HAL Layer (C++)               │
│  can_parser │ secoc_verifier            │
│  vehicle_hal_impl (SocketCAN rx_thread) │
└─────────────────────────────────────────┘
```

**슬라이드 2: AOSP HIDL / Plan B 결정 과정**
- ADR-004 (HIDL vs AIDL) 선택 근거
- Plan A/B 판단 기준 3가지
- (Plan B 전환 시) ADR-010 전환 사유 + 아키텍처 유지 전략

**슬라이드 3: CI/CD 4단계 파이프라인**
```
Stage 1: cppcheck     → 정적 분석 게이트
Stage 2: ARM64 빌드    → Docker 크로스컴파일
Stage 3: QEMU 테스트   → Coverage ≥80%
Stage 4: SSH 배포      → Health Check
```

**슬라이드 4: e2e 레이턴시 측정 결과**
- 측정 방법: candump 타임스탬프 1,000회 샘플링
- 결과 표: avg / P95 / P99 / max
- 병목 분석 + 최적화 기법 (스레드 우선순위, 버퍼 크기)

**슬라이드 5: SecOC 검증 + IDS 경보 흐름**
- ICD §6 시퀀스 다이어그램 참조
- CAN 0x100 → SecOC 검증 → HAL 콜백 → Binder → UI 경로

**슬라이드 6: 직무 어필 — IVI SW 개발자 역량**
```
[핵심 역량]
1. AOSP HIDL HAL 설계 + CAN 파서 C++ 구현
2. Android SystemService (Binder IPC) + Jetpack Compose UI
3. CI/CD 4단계 파이프라인 설계 + 운영
4. Docker 크로스컴파일 + QEMU 에뮬레이션 테스트 자동화
5. 성능 최적화 (P95/P99 레이턴시 분석 + 최적화)

[관련 직무]
- 현대모비스 IVI SW 플랫폼 개발
- 차량 인포테인먼트 시스템 HAL/Service 개발
- Automotive CI/CD 파이프라인 운영
```

#### 3. GitHub Releases 템플릿 (4주차)

8개 릴리즈를 태그별로 생성:

```bash
# v0.1.0 (M1)
gh release create v0.1.0 \
  --title "v0.1.0 — M1: 환경 구축 + ICD 확정" \
  --notes "$(cat <<'EOF'
## Changes
- AOSP repo sync 완료 + 빌드 서버 구성
- Dockerfile.arm64 + toolchain-aarch64.cmake 작성
- IVehicleHal.hal HIDL 초안
- GitHub Actions Stage 1 (cppcheck) 설정
- ICD.md 최종 확정
- SRS.md FR-IVI/CI 초안

## Documents
- docs/ICD.md v1.0
- docs/SRS.md v1.0
- ADR-004, ADR-007 초안
EOF
)"

# v0.2.0 ~ v0.7.0 동일 형식으로 생성
# 각 릴리즈에 해당 월의 변경 내역 기록

# v1.0.0 (최종)
gh release create v1.0.0 \
  --title "v1.0.0 — Final Release" \
  --notes "$(cat <<'EOF'
## Final Release
AUTOSAR 계층 기반 IVI-ECU 통합 플랫폼 최종 버전.

## Key Metrics
- TC-PERF-001: avg latency = [실측]ms (목표 ≤50ms)
- CI Coverage: [실측]% (목표 ≥80%)
- Ablation Study: 12세트 완료

## All Tests
- TC-BSW-001~008: PASSED
- TC-BMS-001~007: PASSED
- TC-SEC-001~007: PASSED
- TC-IVI-001~008: PASSED
- TC-INT-001~004: PASSED
- TC-PERF-001~003: PASSED
- TC-CI-001~006: PASSED

## Deliverables
- 최종 보고서
- 발표 자료
- 데모 영상
EOF
)"
```

#### 4. v1.0.0 태그 생성 (4주차)

```bash
git switch main
git pull origin main

# 최종 상태 확인
git log --oneline -5
# develop → main 마지막 머지 커밋 확인

# 태그 생성
git tag -a v1.0.0 -m "v1.0.0: 최종 릴리즈 — AUTOSAR 계층 기반 IVI-ECU 통합 플랫폼"
git push origin v1.0.0

# 태그 확인
git tag -l
# 기대 출력: v0.1.0 v0.2.0 ... v0.7.0 v1.0.0
```

#### 5. 최종 제출 전 체크리스트

| # | 항목 | 확인 |
|---|------|------|
| 1 | `main` 브랜치 CI 4단계 전체 녹색 | [ ] |
| 2 | Codecov Statement ≥80% | [ ] |
| 3 | GitHub Releases v0.1.0 ~ v1.0.0 (8개) | [ ] |
| 4 | README.md 실측값 삽입 완료 | [ ] |
| 5 | docs/SDD-IVI.md 최종본 머지 완료 | [ ] |
| 6 | docs/ADR.md ADR-004/006/007/010 완성 | [ ] |
| 7 | 데모 시나리오 A/B 리허설 3회 완료 | [ ] |
| 8 | 발표 자료 최종본 완성 | [ ] |
| 9 | 최종 보고서 제출 완료 | [ ] |
| 10 | 데모 백업 영상 준비 | [ ] |
| 11 | `.env`, `key.bin` 등 시크릿 파일이 `.gitignore`에 포함 | [ ] |
| 12 | 불필요한 브랜치 정리 (머지 완료된 feature 브랜치 삭제) | [ ] |

```bash
# 머지 완료된 원격 브랜치 정리
git branch -r --merged origin/develop | grep -v 'main\|develop' | \
  sed 's/origin\///' | xargs -I {} git push origin --delete {}

# 로컬 브랜치 정리
git branch --merged develop | grep -v 'main\|develop' | xargs git branch -d
```

---

## 부록 A: CI/CD 전체 ci.yml 최종본

```yaml
name: CI Pipeline
on:
  push:
    branches: [develop, main]
  pull_request:
    branches: [develop, main]

jobs:
  # ========== Stage 1: 정적 분석 ==========
  stage1-static-analysis:
    name: "Stage 1: cppcheck"
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4

      - name: Install cppcheck
        run: sudo apt-get install -y cppcheck

      - name: Run cppcheck
        run: |
          if find adaptive_ecu/src/ adaptive_ecu/include/ -name '*.cpp' -o -name '*.h' 2>/dev/null | grep -q .; then
            cppcheck \
              --enable=all \
              --error-exitcode=1 \
              --suppress=missingIncludeSystem \
              --suppress=unusedFunction \
              -I adaptive_ecu/include \
              --std=c++17 \
              adaptive_ecu/src/ adaptive_ecu/include/
          else
            echo "No C++ source files found — skipping cppcheck"
          fi

  # ========== Stage 2: ARM64 크로스컴파일 ==========
  stage2-arm64-build:
    name: "Stage 2: ARM64 Cross-Compile"
    needs: stage1-static-analysis
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build ARM64 Docker image
        run: docker build -f Dockerfile.arm64 -t ecu-builder:arm64 .

      - name: Cross-compile ECU binary
        run: |
          docker run --rm \
            -v ${{ github.workspace }}:/workspace \
            ecu-builder:arm64 \
            bash -c "
              cmake -S /workspace/adaptive_ecu \
                    -B /workspace/build \
                    -DCMAKE_TOOLCHAIN_FILE=/workspace/toolchain-aarch64.cmake \
                    -DCMAKE_BUILD_TYPE=Release && \
              cmake --build /workspace/build -j\$(nproc)
            "

      - name: Verify ARM64 binary
        run: file build/ecu_node_a | grep -q "ARM aarch64"

      - name: Upload binary artifact
        uses: actions/upload-artifact@v4
        with:
          name: ecu-arm64-binary
          path: build/ecu_node_a
          retention-days: 7

  # ========== Stage 3: QEMU 테스트 + 커버리지 ==========
  stage3-qemu-test:
    name: "Stage 3: QEMU ARM64 Test + Coverage"
    needs: stage2-arm64-build
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4

      - name: Install QEMU user-mode + coverage tools
        run: |
          sudo apt-get install -y \
            qemu-user-static \
            gcc-aarch64-linux-gnu \
            lcov

      - name: Register QEMU binfmt
        run: sudo update-binfmts --enable qemu-aarch64

      - name: Build test binary (ARM64 + coverage)
        run: |
          docker run --rm \
            -v ${{ github.workspace }}:/workspace \
            ecu-builder:arm64 \
            bash -c "
              cmake -S /workspace/adaptive_ecu \
                    -B /workspace/build_test \
                    -DCMAKE_TOOLCHAIN_FILE=/workspace/toolchain-aarch64.cmake \
                    -DCMAKE_BUILD_TYPE=Debug \
                    -DENABLE_COVERAGE=ON \
                    -DBUILD_TESTS=ON && \
              cmake --build /workspace/build_test -j\$(nproc)
            "

      - name: Run tests via QEMU
        run: |
          cd build_test
          ctest --output-on-failure --timeout 120

      - name: Generate coverage report
        run: |
          lcov --capture \
               --directory build_test \
               --output-file coverage.info \
               --gcov-tool aarch64-linux-gnu-gcov \
               --ignore-errors mismatch
          lcov --remove coverage.info \
               '*/test/*' '/usr/*' \
               --output-file coverage_filtered.info
          lcov --summary coverage_filtered.info

      - name: Quality gate — Statement coverage >= 80%
        run: |
          LINES=$(lcov --summary coverage_filtered.info 2>&1 | grep "lines" | awk '{print $2}' | tr -d '%')
          echo "Statement coverage: ${LINES}%"
          python3 -c "
          import sys
          cov = float('${LINES}')
          if cov < 80.0:
              print(f'FAIL: Statement coverage {cov:.1f}% < 80%')
              sys.exit(1)
          print(f'PASS: Statement coverage {cov:.1f}%')
          "

      - name: Quality gate — Fail-safe Branch coverage 100%
        run: |
          lcov --extract coverage_filtered.info \
               '*/failsafe_sm.cpp' \
               --output-file failsafe_coverage.info
          BRANCHES=$(lcov --summary failsafe_coverage.info 2>&1 | grep "branches" | awk '{print $2}' | tr -d '%')
          python3 -c "
          import sys
          cov = float('${BRANCHES}')
          if cov < 100.0:
              print(f'FAIL: Fail-safe branch coverage {cov:.1f}% < 100%')
              sys.exit(1)
          print(f'PASS: Fail-safe branch coverage {cov:.1f}%')
          "

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          files: coverage_filtered.info
          flags: unit-tests
          token: ${{ secrets.CODECOV_TOKEN }}

  # ========== Stage 4: SSH 배포 + Health Check ==========
  stage4-deploy:
    name: "Stage 4: SSH Deploy + Health Check"
    needs: stage3-qemu-test
    runs-on: ubuntu-22.04
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - name: Download ARM64 binary
        uses: actions/download-artifact@v4
        with:
          name: ecu-arm64-binary
          path: dist/

      - name: Setup SSH key
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.RPI_SSH_KEY }}" > ~/.ssh/rpi_deploy_key
          chmod 600 ~/.ssh/rpi_deploy_key
          ssh-keyscan -H ${{ secrets.RPI_NODE_A_HOST }} >> ~/.ssh/known_hosts

      - name: Transfer binary via SCP
        run: |
          scp -i ~/.ssh/rpi_deploy_key \
              dist/ecu_node_a \
              deploy@${{ secrets.RPI_NODE_A_HOST }}:/opt/ecu/ecu_node_a.new

      - name: Restart service via SSH
        run: |
          ssh -i ~/.ssh/rpi_deploy_key \
              deploy@${{ secrets.RPI_NODE_A_HOST }} \
              "mv /opt/ecu/ecu_node_a.new /opt/ecu/ecu_node_a && \
               chmod +x /opt/ecu/ecu_node_a && \
               sudo systemctl restart ecu-node-a.service"

      - name: Health check
        run: |
          ssh -i ~/.ssh/rpi_deploy_key \
              deploy@${{ secrets.RPI_NODE_A_HOST }} \
              "bash /opt/ecu/scripts/health_check.sh"
```

---

## 부록 B: 월별 총 예상 시간 요약

| 월 | 예상 시간 | 주요 산출물 |
|----|----------|-----------|
| M1 (6월) | 18~22시간 | AOSP 환경, Docker, ci.yml Stage 1, HIDL 초안 |
| M2 (7월) | 26~34시간 | HAL Mock, AOSP 부팅 시도, Plan A/B 결정 |
| M3 (8월) | ~42시간 | CAN 파서, HAL, Service, SocGauge, CI Stage 2~3 |
| M4 (9월) | ~31.5시간 | DashboardScreen, AlertBanner, CI Stage 4, IT-001~005 |
| M5 (10월) | ~29시간 | 레이턴시 측정/최적화, UI 개선, ADR 완성 |
| M6 (11월) | ~28시간 | SDD-IVI.md, README.md, Codecov ≥80% |
| M7 (12월) | ~24시간 + 24h 운행 | 24h 안정성 테스트, CI 점검, 교차 검토 |
| M8 (1월) | ~30시간 | 데모 리허설, 발표 자료, Releases, v1.0.0 |

**8개월 총 예상: 약 228~240시간** (주당 약 7~8시간)

---

## 부록 C: 팀원B 담당 파일 전체 목록

| 파일 | 경로 | 구현 시점 |
|------|------|-----------|
| `IVehicleHal.hal` | `ivi_platform/hal/` | M1 (6월) |
| `IVehicleHalCallback.hal` | `ivi_platform/hal/` | M1 (6월) |
| `VehicleHalMock.java` | `ivi_platform/hal/mock/` | M2 (7월) |
| `VehicleRepository.kt` | `ivi_platform/app/data/` | M2 (7월) |
| `can_parser.h / .cpp` | `ivi_platform/hal/` | M3 (8월) |
| `vehicle_hal_impl.h / .cpp` | `ivi_platform/hal/` | M3 (8월) |
| `secoc_verifier.h / .cpp` | `ivi_platform/hal/` | M3 (8월) |
| `IVehicleDataService.aidl` | `ivi_platform/service/` | M3 (8월) |
| `VehicleDataService.java` | `ivi_platform/service/` | M3 (8월) |
| `VehicleDataManager.java` | `ivi_platform/service/` | M3 (8월) |
| `DashboardViewModel.kt` | `ivi_platform/app/` | M3 (8월) |
| `SocGauge.kt` | `ivi_platform/app/` | M3 (8월) |
| `DashboardScreen.kt` | `ivi_platform/app/` | M4 (9월) |
| `FailSafeIndicator.kt` | `ivi_platform/app/` | M4 (9월) |
| `AlertBanner.kt` | `ivi_platform/app/` | M4 (9월) |
| `test_can_parser.cpp` | `ivi_platform/test/` | M3 (8월) |
| `test_vehicle_service.java` | `ivi_platform/test/` | M3 (8월) |
| `SocGaugeTest.kt` | `ivi_platform/app/test/` | M3 (8월) |
| `DashboardScreenTest.kt` | `ivi_platform/app/test/` | M4 (9월) |
| `DashboardViewModelTest.kt` | `ivi_platform/app/test/` | M4 (9월) |
| `Dockerfile.arm64` | 루트 | M1 (6월) |
| `toolchain-aarch64.cmake` | 루트 | M1 (6월) |
| `ci.yml` | `.github/workflows/` | M1~M4 단계별 |
| `health_check.sh` | `scripts/` | M4 (9월) |
| `ecu-node-a.service` | RPi4 배포 | M4 (9월) |
| `analyze_latency.py` | `scripts/` | M5 (10월) |
| `codecov.yml` | 루트 | M6 (11월) |
| `docs/SDD-IVI.md` | `docs/` | M6 (11월) |
| `README.md` | 루트 | M6 (11월) |
| `docs/ADR.md` (ADR-004/006/007/010) | `docs/` | M5 (10월) |
