# IVI M2 — HAL Mock, AOSP 부팅 시도, Plan A/B 결정

> **상태(2026-09-22)**: ADR-010의 Qt Plan B 활성화로 이 문서의 Android/AOSP 실행 절차는 현 제출 범위에서 superseded된 역사 자료다. 현재 작업은 [IVI 계획](../../IVI.md)과 [Plan B 전환 계획](../../IVI_PLAN_B_전환계획.md)을 따른다.


## 현재 실행 진입점 — Qt Plan B

이 파일의 이전 M단계 절차·명령·체크리스트는 역사 자료이며 현재 완료 판정에 직접 사용하지 않는다. 현행 작업은 [IVI M1~M8 매핑](../../IVI.md#4-m1m8-마일스톤)과 [Qt P0~P6 실행 계획](../../IVI_PLAN_B_전환계획.md#3-단계별-실행-계획)을 따른다. Qt 관련 과거 대안도 현재 채택 구조와 다를 수 있으므로 D-Bus/Flutter를 추가 요구하지 않는다. 공식 요구·계약·시험은 SRS/ICD/TEST_PLAN이 원본이다.

---


> **예시 상태**: 코드·명령은 별도 검증 표시가 없으면 작성 골격·예정 절차다. 실행 전 생성할 파일·의존성·플랫폼을 확인한다. [공동 규약](../common/00_협업_규약.md)의 문서·예시 사용 규칙을 따른다.

> 상위 계획: [IVI.md](../../IVI.md) · 공동 절차: [00_협업_규약](../common/00_협업_규약.md) · 인계: [01_연계_의존성](../common/01_연계_의존성.md)
> 원본: `_archive/IVI.md` M2, `_archive/IVI_최종_실행계획서.md` §6

---

## 1. 목적과 범위

실제 CAN 없이도 Service·UI 개발이 가능하도록 HAL Mock을 만든다. AOSP RPi4 부팅 가능성을 **M2 말까지 판정**하고, 실패 시 증거와 일정 영향을 제시하고 사용자 인터뷰 후 플랫폼 방향을 결정한다.

| 항목 | 값 |
|---|---|
| 연결 요구사항 | FR-IVI-001, FR-IVI-004 |
| 연결 시험 | TC-IVI-001(초기), TC-CI-003 |
| 산출물 | `VehicleHalMock`, `VehicleRepository`, AOSP 부팅 결과 기록, Plan A/B 결정, (필요 시) ADR-010 |
| 태그 | `v0.2.0` |

### 주차별 작업

| 주차 | IVI 작업 | ECU/공동 연계 |
|---|---|---|
| 1주차 | HIDL 확정, `VehicleHalMock`, `VehicleRepository` | ECU `0x100` 샘플 payload 수신 |
| 2주차 | AOSP RPi4 첫 빌드·부팅 시도 | Mock payload 파싱 상호 검증 |
| 3주차 | 마지막 빌드 시도·로그 분석, Docker Stage 2 확인 | ECU C++ 크로스빌드 협업 |
| 4주차 | **Plan A/B 결정 미팅**, ADR-010 | 결정 결과 공유 |

> **이 단계의 핵심은 Mock이 아니라 판정이다.** AOSP에 매달려 결정을 미루면 M3 전체가 밀린다. 판정 기한은 M2 말이다.

---

## 2. 선행조건과 현재 구현 상태

**선행조건**: [M1](M1_AOSP_Docker_CI.md) 완료 — AOSP 소스, Docker 이미지, `ivi_platform/` 골격, HIDL 초안.

| 대상 | 상태 |
|---|---|
| `ivi_platform/hal/mock/` | **미구현** (M1에서 디렉토리만 생성) |
| `ivi_platform/app/data/` | **미구현** |
| AOSP RPi4 device tree | 외부 저장소. M2에서 클론 |
| `docs/ADR.md` ADR-010 | 미작성 (Plan B 전환 시에만 필요) |

### 통합 시 해소한 충돌

| 항목 | 세대A | 세대B | 채택 |
|---|---|---|---|
| Mock 데이터 방식 | `Timer` 100ms 주기 + SOC 점진 감소 | 수동 `emitBmsStatus()` 1회 | **세대A 기반** — 주기 갱신이 UI 개발에 필요. 세대B의 다중 콜백 목록도 반영 |
| `lunch` 타겟 | `rpi4-eng` | `aosp_arm64-eng` | device tree에 따라 다르다. **`lunch` 목록을 직접 확인**한다 |
| swap 크기 | 8G | 16G | **16G** — AOSP 링크 단계에서 8G로는 자주 부족하다 |
| Plan A 판정 | 3조건 전부 충족 | 3조건 + "UI 개발 과도 지연 시 Plan B/Hybrid" | **병합** — 4번째 조건을 판정표에 포함 |
| ARM64 산출물 이름 | `build/ecu_node_a` | — | **`adaptive_ecu`** — 실제 CMake 타겟 이름 |

---

### 대상 환경 확인 게이트

사용자 환경 인터뷰는 종료됐고 서버를 주 빌드 장비로 사용한다. [Android 환경설정 §6](../../../docs/development/environment/안드로이드_환경설정.md)의 Raspberry Vanilla Android 16은 우선 검증 후보이며 최종 버전 채택은 보류다. 아래 과거 Android 13 revision·JDK·lunch·device tree·flash 명령은 선정 결과가 아니다. 실제 후보의 도구와 revision을 대조하고 새 이미지나 Plan B 전환을 자동 확정하지 않는다.

선택 환경의 manifest/revision·kernel/device tree·toolchain/JDK/SDK·저장공간·빌드/flash 방법·artifact hash를 확보한다. 대상 디스크와 이미지 종류는 실제 환경에서 확인한다. 부팅→ADB→can0→HAL 등록/VINTF/init/권한→Service Binder→앱 표시를 순차 검증한다. can0 존재만으로 HAL 송수신·앱 접근을 합격시키지 않는다.

host Linux 코어, Node A Linux ARM64, Node B Android HAL/framework/app의 산출물·sysroot·라이브러리 ABI를 구분한다. Linux ARM64 빌드 성공은 Android 실행 성공이 아니다. Mock은 실제 HAL 등록·권한·렌더링의 대체 증거가 아니다.

## 3. 수행 절차

### 3.1 VehicleHalMock

아래는 기존 11필드 경로의 UI 부하 골격이다. 현 개발 목표는 ICD §8의 13필드이며 sensorState·stale를 포함하는 최초/오류/복구 fixture를 함께 작성한다. 아래 숫자는 UI 합성 입력이지 물리적으로 일관된 배터리 시뮬레이션이나 인증된 센서 측정이 아니다. 생성 HIDL의 bool 반환·callback 수명/해제·RemoteException 처리를 갖춘 adapter는 별도 구현 과제다.

`ivi_platform/hal/mock/VehicleHalMock.java`:

```java
package com.capstone.vehicle.hal.mock;

import java.util.ArrayList;
import java.util.List;
import java.util.Timer;
import java.util.TimerTask;

public class VehicleHalMock {
    private final List<IVehicleHalCallback> callbacks = new ArrayList<>();
    private Timer timer;
    private float socValue = 80.0f;

    public void subscribe(IVehicleHalCallback callback) {
        callbacks.add(callback);
    }

    public void start() {
        timer = new Timer();
        timer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                VehicleData data = new VehicleData();
                data.soc = socValue;
                data.soh = 95.0f;
                data.voltage = 42.0f + (socValue - 50.0f) * 0.1f;
                data.current = -2.0f;
                data.temperature = 35;
                data.failSafeState = 0;     // NORMAL
                data.failSafeReason = 0;
                data.attackDetected = false;
                data.attackType = 0;
                data.anomalyScore = 0.0f;
                data.timestamp = (int) (System.currentTimeMillis() / 1000);

                for (IVehicleHalCallback cb : callbacks) {
                    cb.onVehicleDataChanged(data);
                }

                socValue = Math.max(0.0f, socValue - 0.05f);   // 서서히 방전
            }
        }, 0, 100);   // 100ms 주기 — ICD의 0x100 주기와 동일
    }

    public void stop() {
        if (timer != null) {
            timer.cancel();
            timer = null;
        }
    }
}
```

**Mock이 지켜야 할 것**

- [ ] 주기는 100ms — 실제 `0x100`과 같아야 UI 갱신 부하를 미리 본다
- [ ] 값 범위를 ICD 유효 범위 안에서 만든다 (SOC 0~100, 온도 -40~125)
- [ ] Fail-safe 전이와 IDS 경보도 주입할 수 있게 해둔다. UI 시험에 필요하다

```java
// 시험용 주입 메서드 (권장)
public void emitFailSafe(int prev, int next, int reason) { ... }
public void emitAlert(int attackType, float score, int suspectCanId) { ... }
```

**검증**: Android Studio에서 Mock을 단독 실행하고 logcat에서 100ms 주기 갱신과 SOC 감소(80.0 → 79.95 → 79.90)를 확인한다.

### 3.2 VehicleRepository

아래 초기 숫자 0은 저장용 placeholder다. 최초 인증·정상 품질 수신 전에는 유효 값/배터리 NORMAL로 렌더하지 않는다. ICD §8의 sensorState와 정상값 보유 여부를 추가해 IVI M3/M4의 승인 상태 snapshot으로 전환한다. 외부 호출로 `clearStale()`만 실행해 정상 판정을 만들지 않고 인증/품질 수신 정책으로 갱신한다.

`ivi_platform/app/data/VehicleRepository.kt`:

```kotlin
package com.capstone.vehicle.app.data

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class VehicleUiState(
    val soc: Float = 0f,
    val soh: Float = 0f,
    val voltage: Float = 0f,
    val current: Float = 0f,
    val temperature: Int = 0,
    val failSafeState: Int = 0,     // 0=NORMAL, 1=WARNING, 2=CRITICAL, 3=SHUTDOWN
    val failSafeReason: Int = 0,
    val attackDetected: Boolean = false,
    val attackType: Int = 0,        // 0=None, 1=Fuzzy, 2=Replay, 3=Spoofing, 4=Flooding
    val anomalyScore: Float = 0f,
    val timestamp: Long = 0L,
    val stale: Boolean = false      // CAN 수신 타임아웃 (ICD §2.5.1)
)

class VehicleRepository {
    private val _vehicleState = MutableStateFlow(VehicleUiState())
    val vehicleState: StateFlow<VehicleUiState> = _vehicleState.asStateFlow()

    fun updateVehicleData(state: VehicleUiState) {
        _vehicleState.value = state
    }

    fun markStale() {
        _vehicleState.value = _vehicleState.value.copy(stale = true)
    }

    fun clearStale() {
        _vehicleState.value = _vehicleState.value.copy(stale = false)
    }
}
```

`stale` 플래그는 ICD §2.5.1의 수신 타임아웃 처리에 대응한다. **타임아웃 시 마지막 값을 그대로 두지 말고 오래된 값임을 표시한다.**

### 3.3 AOSP RPi4 빌드 시도

[Android 환경설정](../../../docs/development/environment/안드로이드_환경설정.md) §6~7의 고정 후보 조합과 실제 빌드 절차를 사용한다. 사용자에게 받은 resolved manifest·종료 코드·로그·이미지 hash를 먼저 대조한다. 임의 device tree/Android 13 branch 추가는 하지 않는다. 대상 SD를 확인해 기록한 뒤 부팅·디스플레이·adb·can0·사용자 정의 HIDL 등록/호출·키 접근을 검증한다. `adb connect`는 네트워크 adb가 실제 활성화된 환경에서만 사용한다. 후보 빌드/부팅이 성공해도 프로젝트 HAL/UI 인수까지 완료된 것은 아니다.

- [ ] 실패·부팅 로그 및 대응 revision을 ADR-010 판정 증거로 보존한다.

### 3.4 Plan A / Plan B 판정

**M2 말에 아래 표로 준비 상태를 확인한다. 플랫폼 변경은 사용자 답변 후 확정한다.**

| # | 조건 | 확인 방법 | 결과 |
|---|---|---|---|
| 1 | 선택 Android 후보 홈 화면 표시 | 보유 디스플레이의 실제 표시 확인 | ☐ 충족 ☐ 미충족 |
| 2 | `adb shell` 접속 가능 | `adb shell whoami` | ☐ 충족 ☐ 미충족 |
| 3 | CAN 인터페이스 접근 | `adb shell ip link show can0` | ☐ 충족 ☐ 미충족 |
| 4 | UI 개발이 일정 안에 가능 | Compose 빌드·배포 사이클 실측 | ☐ 충족 ☐ 미충족 |

- **1~3 전부 충족 + 4 충족** → **Plan A 유지**
- **1~3 중 하나라도 미충족** → **차단 원인 기록 후 사용자 인터뷰**
- **1~3 충족하지만 4 미충족** → Plan B 또는 Hybrid 검토 후 결정 기록

판정 결과는 [00_협업_규약](../common/00_협업_규약.md)의 결정 기록 절차에 따라 남긴다.

### 3.5 Plan B 아키텍처

| 계층 | Plan A (AOSP) | Plan B (Ubuntu) |
|---|---|---|
| HAL | HIDL C++ | 공통 C++ 파서/SecOC 코어 재사용, HIDL adapter 교체 |
| IPC | Binder | D-Bus (sd-bus) 또는 gRPC |
| Service | Android SystemService (Java) | systemd service + D-Bus daemon (C++/Python) |
| UI | Jetpack Compose (Kotlin) | Qt6 QML 또는 Flutter |
| 배포 | AOSP flashable image | deb 패키지 또는 직접 바이너리 |

**핵심**: 플랫폼 의존 코드를 분리한 **CAN 파싱과 SecOC 검증 코어를 재사용한다.** HIDL 등록/콜백/Android 로그 부분까지 무수정 재사용되는 것은 아니다. 바뀌는 것은 IPC와 UI다. `HAL → Service → UI` 계층 분리 원칙은 양쪽 모두 유지한다.

**전환 절차**

1. Node B RPi4에 Ubuntu 22.04 Server 설치 (ECU 노드와 동일 OS)
2. SocketCAN + MCP2515 설정 ([ECU M1](../ecu/M1_환경구축_ICD확정.md) 3.2와 동일)
3. `can_parser.cpp`, `vehicle_hal_impl.cpp` 재사용
4. HIDL → D-Bus 인터페이스 교체 — **HAL API가 바뀌므로 `interface-change` 게이트 대상이다**
5. Service를 D-Bus daemon으로 교체
6. UI를 Qt6 QML 또는 Flutter로 교체
7. ADR-010 작성

```bash
sudo apt update
sudo apt install -y libdbus-1-dev libsystemd-dev python3-dbus python3-gi \
                    qtbase5-dev qtcreator protobuf-compiler
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

Flutter 대안:

```bash
sudo snap install flutter --classic
flutter doctor
flutter create ivi_dashboard
cd ivi_dashboard && flutter run -d linux
```

**ADR-010 내용**

```markdown
# ADR-010: AOSP → Ubuntu Plan B 전환

## 상태: Accepted
## 맥락: AOSP RPi4 부팅 실패 — [구체적 실패 사유와 로그 위치 기록]
## 결정: Ubuntu 22.04 + D-Bus + Qt/Flutter로 전환
## 근거:
- [실제 실패 사유. 추정이 아니라 로그 근거]
- 커뮤니티 device tree의 Android 13 지원 불완전
- 잔여 일정상 AOSP 디버깅에 추가 투자 불가
## 영향:
- HAL 계층(C++) 변경 없음 — CAN 파싱·SecOC 검증 재사용
- IPC: Binder → D-Bus (HAL API 변경 → ICD §3 갱신 필요)
- UI: Jetpack Compose → Qt/Flutter
- 계층 분리 아키텍처는 유지
## 위험 완화:
- D-Bus/gRPC 학습 [기간] 확보
- 대시보드 M3 내 완성 계획
```

> **ADR-010의 "맥락"에 추정을 쓰지 않는다.** 실제 빌드·부팅 로그에서 확인한 사유를 적고 로그 위치를 남긴다.

### 3.6 Docker Stage 2 ARM64 빌드 확인

`docs/CICD_SPEC.md`의 Stage 2를 로컬에서 먼저 확인한다.

```bash
docker build -f Dockerfile.arm64 -t capstone-arm64 .

docker run --rm -v "$(pwd)":/workspace capstone-arm64 bash -c "
  cmake -S /workspace/adaptive_ecu -B /workspace/build-arm64 \
        -DCMAKE_TOOLCHAIN_FILE=/opt/toolchain-aarch64.cmake \
        -DCMAKE_BUILD_TYPE=Release -DECU_BUILD_TESTS=ON &&
  cmake --build /workspace/build-arm64 -j\$(nproc)"

file build-arm64/adaptive_ecu
# 기대: ELF 64-bit LSB executable, ARM aarch64
```

- [ ] 산출물 이름은 CMake 타겟명 `adaptive_ecu`다. `ecu_node_a`가 아니다

### 3.7 ECU 샘플 payload 상호 검증

- [ ] ECU 담당자에게 `0x100` 샘플 프레임(바이트열)과 그 해석값을 받는다
- [ ] Mock/파서가 같은 바이트열에서 같은 값을 내는지 확인한다
- [ ] 다르면 반올림 규칙(`lround`)과 clamp 상한부터 대조한다 ([ECU M2](../ecu/M2_CAN_CDD_Publisher.md) 3.4)

---

## 4. 검증 명령과 합격 기준

```bash
# AOSP
ls out/target/product/*/system.img
adb shell whoami
adb shell ip link show can0

# Docker ARM64
docker run --rm -v "$(pwd)":/workspace capstone-arm64 bash -c \
  "cmake -S /workspace/adaptive_ecu -B /workspace/build-arm64 \
     -DCMAKE_TOOLCHAIN_FILE=/opt/toolchain-aarch64.cmake && \
   cmake --build /workspace/build-arm64"
file build-arm64/adaptive_ecu
```

| 기준 | 합격 조건 |
|---|---|
| Mock | 100ms 주기 갱신, Fail-safe·Alert 주입 가능 |
| Repository | StateFlow로 UI에 상태 전달, `stale` 처리 |
| 파싱 검증 | ECU 샘플 payload와 동일 해석 |
| AOSP | 부팅 시도 결과와 로그 보존 |
| 판정 | Plan A/B 결정 완료, 근거 기록 |
| ADR-010 | Plan B 전환 시 작성·머지 |
| Docker | ARM64 산출물 생성 |
| 태그 | `v0.2.0` |

---

## 5. 실패 시 대응과 우회

**AOSP 빌드 out of memory**
```bash
sudo fallocate -l 16G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
free -h
```
그래도 실패하면 `m -j4`처럼 병렬도를 낮춘다.

**RPi4 부팅 안 됨 (HDMI 출력 없음)**
1. SD 카드 이미지 플래시 재확인 (`dd` 또는 `bmaptool`)
2. device/kernel/vendor와 AOSP가 고정 후보 resolved manifest에 일치하는지 확인
3. `config.txt`에 `hdmi_force_hotplug=1` 추가
4. UART 콘솔을 연결해 커널 로그를 본다 — **부팅 실패 원인을 여기서만 알 수 있다**

**`lunch` 타겟이 목록에 없음**
- device tree 클론 경로가 `device/<vendor>/<board>` 규칙에 맞는지 확인
- `source build/envsetup.sh`를 device tree 클론 **이후에** 다시 실행

**판정 기한이 됐는데 결론이 안 남**
- 자동으로 Plan B로 전환하지 않는다. 빌드·부팅·HAL·표시 결과와 남은 장애, 일정 영향, A 유지/B 전환안을 정리해 사용자 인터뷰 후 결정한다. 답변 전 플랫폼·HAL 계약을 변경하지 않는다.
- 판정 지연의 영향 범위는 [01_연계_의존성](../common/01_연계_의존성.md)의 지연 시나리오를 참조

**Plan B 전환 시 ICD 영향**
- HAL API가 HIDL → D-Bus로 바뀌면 ICD §3이 바뀐다. 코드부터 고치지 말고 `interface-change` 게이트를 먼저 통과한다 ([00_협업_규약](../common/00_협업_규약.md))
- CAN 레이아웃(§1)과 SecOC(§2)는 **바뀌지 않는다.** 그 부분까지 건드리지 않는다

---

## 6. 완료 체크리스트

- [ ] HIDL 인터페이스 확정, ICD §3.1과 일치
- [ ] `VehicleHalMock` 100ms 주기 동작
- [ ] Mock에 Fail-safe·Alert 주입 경로 존재
- [ ] `VehicleRepository` StateFlow 동작, `stale` 처리
- [ ] ECU `0x100` 샘플 payload 동일 해석 확인
- [ ] AOSP 빌드·부팅 시도 결과와 로그 보존
- [ ] Plan A/B 판정 완료, 4개 조건 표 작성
- [ ] Plan B 전환 시 ADR-010 작성, ICD §3 영향 처리
- [ ] Docker ARM64 빌드 산출물 확인
- [ ] `v0.2.0` 태그 생성


<a id="ivi-hal-01"></a>
### IVI-HAL-01 — Plan 승계 과제

원문: [IVI.md](../../_archive/plan_20260908/IVI.md.txt)의 IVI-HAL-01. 실행 상태는 해당 역할의 진행 표·공동 인수 기록을 사용한다. 이 병합은 과제 실행 완료가 아니다.

선행·착수: 승인 계약; 대상 실행은 [IVI-ENV-01](M1_AOSP_Docker_CI.md#ivi-env-01) 및 [ECU-CAN-01](../ecu/M2_CAN_CDD_Publisher.md#ecu-can-01) 인계

보존한 수행·인수 조건: Mock 정상/경계/이벤트 입력으로 독립 시험하고 M3 reader/수신/종료·파서에 연결한다. DLC·부호·스케일·예약 필드와 인증 전 파싱/인증 후 전달을 구분한다. 실제 수신 증거를 COM-HAND-01에 인계한다.

현재 기준 적용: 현재 계약·승인 목표 전환을 분리; 호스트 성공은 대상 HAL 완료 아님. 본문의 공식 FR/TC·승인 정책·실패 대응을 함께 적용한다.
