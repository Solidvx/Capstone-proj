> **문서명**: Software Design Document — Node B (IVI) (SDD-IVI)  
> **버전**: v1.3 | **작성일**: 2026-03-15 | **최종 수정**: 2026-09-09 | **작성자**: 팀원B  
> **참조**: ICD v1.4, SRS v1.5 (FR-IVI-*), ADR-004 (HIDL), ADR-009 (IDS 위치), ADR-010 (Plan B)

---

# 1. 문서 개요

원천 역할: ICD는 계약, SRS는 요구, 본 문서는 설계다. plan/development 링크는 승인 답변·선정 근거·실행 절차의 위치이며 상위 계약을 변경하는 권한 위임이 아니다. 충돌 시 AGENTS Source of Truth와 사용자 승인 범위를 우선한다.

## 1.1. 목적

Node B(IVI)의 Android AOSP 포팅부터 대시보드 앱까지 전 스택의 모듈 구조, 클래스 설계, 데이터 흐름, UI 사양을 상세히 기술한다.

## 1.2. 참조 문서

- ICD v1.4 (CAN 메시지 규격, HAL API 명세, SecOC 시퀀스 다이어그램)
- SRS v1.5 (FR-IVI-*)
- ADR.md — ADR-004(HIDL), ADR-009(IDS 위치), ADR-010(Plan B)
- [Android 환경설정 §6~7](development/environment/안드로이드_환경설정.md): Raspberry Vanilla Android 16 우선 검증 후보. revision·빌드 대상·호환성은 실행 검증 후 고정하며 Android 13을 현행 플랫폼 선정으로 사용하지 않는다.

---

# 2. IVI SW 스택 구조

2026-09-08: `ivi_platform/`과 Android/Qt 제품 코드는 없다. 이 문서의 트리·시험 파일은 모두 예정이며 소스 존재/실행 성공을 뜻하지 않는다. 플랫폼 선정과 빌드의 최신 실행 기준은 [Android 환경설정](development/environment/안드로이드_환경설정.md) §6~7과 plan IVI M1~M3다.

```
┌─────────────────────────────────────────┐
│  Android App Layer                          │
│  ┌───────────────────────────────────┐  │
│  │  DashboardApp (Jetpack Compose)      │  │
│  │  └─ DashboardScreen                  │  │
│  │  └─ DashboardViewModel               │  │
│  └───────────────────────────────────┘  │
├─────────────────────────────────────────┤
│  Android Framework Layer                    │
│  ┌───────────────────────────────────┐  │
│  │  VehicleDataService (SystemService) │  │
│  │  └─ IVehicleDataService.aidl         │  │
│  └───────────────────────────────────┘  │
├─────────────────────────────────────────┤
│  HAL Layer                                   │
│  ┌───────────────────────────────────┐  │
│  │  Vehicle HAL (HIDL, C++)            │  │
│  │  └─ SecOC 검증 로직                  │  │
│  │  └─ CAN ID별 파싱 로직              │  │
│  └───────────────────────────────────┘  │
├─────────────────────────────────────────┤
│  Linux Kernel (SocketCAN + MCP2515 드라이버)  │
└─────────────────────────────────────────┘
```

---

# 3. AOSP 포팅 설정

## 3.1. 빌드 환경

| 항목 | 요구 사양 |
| --- | --- |
| OS | 서버의 Linux 빌드 환경. 실제 OS·도구는 착수 시 확인 |
| 디스크 | 사용자 확인상 서버 자원 충분. 특정 용량을 추정하지 않음 |
| RAM | 사용자 확인상 서버 자원 충분. 사양 재질문 종료 |
| AOSP 버전 | 최종 미선정. Raspberry Vanilla Android 16 우선 검증 후보 |
| 타겟 | RPi4 (arm64) |

최신 선정 근거·검증 조건은 [Android 환경설정 §6](development/environment/안드로이드_환경설정.md)을 따른다. 아래 §3.4의 Android 13 tag·도구·lunch 명령은 과거 포팅 예제이며 현재 확정 명령이 아니다. 실제 후보의 revision과 도구를 고정한 뒤 실행한다. 사용자 정의 HIDL을 유지하고 표준 VHAL·CarService는 요구하지 않는다.

## 3.2. 디바이스 트리 수정 사항

| 파일 | 수정 내용 | 목적 |
| --- | --- | --- |
| `bcm2711-rpi-4-b.dts` | SPI0 노드 활성화, MCP2515 오버레이 추가 | CAN 컨트롤러 연결 |
| MCP2515 오버레이 | `compatible = "microchip,mcp2515"`, 클럭 8MHz, 인터럽트 GPIO25 | SPI-CAN 드라이버 로드 |
| `defconfig` | `CONFIG_CAN=y`, `CONFIG_CAN_MCP251X=y` | 커널 CAN 모듈 활성화 |

## 3.3. MCP2515 커널 모듈 통합

- 커널 소스의 `mcp251x.c` 드라이버 사용
- 빌트레이트: 500kbps (프로젝트 설정; 모든 차량의 표준 속도라는 뜻은 아님)
- 부팅 후 `can0` 인터페이스 자동 생성 확인: `ip link show can0`

## 3.4. AOSP RPi4 포팅 단계별 가이드

Android 13 tag와 별개 BSP 최신 branch를 혼합하던 과거 명령은 삭제했다. Android 16 우선 후보는 최종 선정/빌드 성공과 다르다. [Android 환경설정](development/environment/안드로이드_환경설정.md) §6~7에서 manifest/revision, device/kernel/vendor 정합, 실제 lunch 대상, 사용자 정의 HIDL 도구·등록, 커널 CAN, 키 권한, 부팅·HAL·앱 증거를 함께 고정한다. 다운로드는 사용자가 맡고 후속 검증은 IVI 담당이 수행한다. 산출 이미지명·소요 시간·플래시 대상은 실행 환경을 확인해 기록한다.

### 3.4.6. 대안 접근법 (AOSP 포팅 실패 시)

ADR-010의 대안 구조는 유지하되 과거 7월/2개월차 날짜로 자동 전환하지 않는다. 현재 시연 마감은 2026-09-18이며 M1~M8은 단계다. 대상 후보의 실패 로그·추가 작업량·요구사항/시험 영향을 제시한 뒤 Plan B를 판단한다. Ubuntu + D-Bus/gRPC + Qt/Flutter는 전환 대안이고 Android FR-IVI-003/004/008의 달성을 자동 대신하지 않는다. 전환 시 공식 요구·HAL/API·설계·시험을 승인 절차에 따라 동기화한다.

---

# 4. 모듈 상세 설계

## 4.1. 디렉토리 구조

```
ivi_platform/
├── hal/
│   ├── IVehicleHal.hal            // HIDL 인터페이스 정의
│   ├── IVehicleHalCallback.hal     // 콜백 인터페이스
│   ├── vehicle_hal_impl.h          // HAL 구현체 헤더
│   ├── vehicle_hal_impl.cpp        // HAL 구현체
│   ├── can_parser.h                // CAN ID별 파싱 로직
│   ├── can_parser.cpp
│   ├── secoc_verifier.cpp          // HMAC 검증 로직
│   └── mock/VehicleHalMock.java    // HAL 테스트용 Mock
├── service/
│   ├── IVehicleDataService.aidl    // Binder IPC 인터페이스
│   ├── VehicleDataService.java     // SystemService 구현
│   └── VehicleDataManager.java     // 앱용 클라이언트 API
├── app/
│   ├── DashboardActivity.kt        // 메인 Activity
│   ├── DashboardScreen.kt          // Compose UI
│   ├── DashboardViewModel.kt       // ViewModel + StateFlow
│   ├── SocGauge.kt                 // SOC 원형 게이지 Composable
│   ├── AlertBanner.kt              // 공격 경보 배너 Composable
│   ├── FailSafeIndicator.kt        // Fail-safe 상태 표시 Composable
│   ├── LogPanel.kt                 // CAN/보안 로그 패널 Composable
│   └── data/VehicleRepository.kt   // CAN 데이터 Repository
├── test/
│   ├── test_can_parser.cpp         // CAN 파싱 단위 테스트
│   └── test_vehicle_service.java   // Service 테스트
└── app/test/
    ├── SocGaugeTest.kt             // SOC 게이지 색상 코드 테스트
    ├── DashboardScreenTest.kt      // 경보 배너, Fail-safe 팝업 테스트
    └── DashboardViewModelTest.kt   // StateFlow 레이턴시 테스트
```

## 4.2. Vehicle HAL 구현체

### 4.2.1. CAN 수신 스레드 생명주기

1. `init()` 호출 시 SocketCAN can0 소켓 오픈
2. `rx_thread_` 시작: `read()` blocking 대기
3. 프레임 도착 시 CAN ID 확인 → 파싱 → 콜백 디스패치
4. `shutdown()` 시 정지 요청 후 대기 중인 수신을 깨우고 종료를 확인한 뒤 자원을 회수한다. 다른 스레드의 `close()`만으로 blocking read 종료를 보장하지 않는다. poll/eventfd 또는 유한 대기 등 회수 방식과 timeout·재시작 시험은 구현 시 검증한다.

### 4.2.2. CAN ID별 파싱 로직

| CAN ID | 파싱 동작 | 콜백 |
| --- | --- | --- |
| 0x100 + 0x102 | BMS 데이터 파싱, SecOC 검증 후 VehicleData 구성 | `onVehicleDataChanged(data)` |
| 0x101 + 0x103 | Fail-safe 이벤트 파싱, SecOC 검증 | `onFailSafeTransition(prev, new, reason)` |
| 0x200 | IDS 경보 파싱 (HMAC 없음) | `onSecurityAlert(type, score, canId)` |
| 기타 | 로그 기록 후 무시 | 없음 |

### 4.2.3. SecOC 검증 흐름 (HAL 내부)

```
원본 메시지(0x100) 수신 → 버퍼에 저장
인증 메시지(0x102) 수신 → TruncatedMAC + RollingCounter 추출
    │
    ├─ Counter 윈도우 검사 (last < received <= last+100)
    │   └─ 실패: 폐기 + 로그 ERR_COUNTER_MISMATCH
    │
    ├─ HMAC 재계산 + compare_digest
    │   └─ 실패: 폐기 + 로그 ERR_HMAC_VERIFY_FAIL
    │
    └─ 성공: VehicleData 구성 → 콜백 호출
```

## 4.3. VehicleDataService (SystemService)

### 4.3.1. 서비스 등록

- SystemServer/SystemServiceManager에서 서비스 생명주기를 시작하고 Binder 서비스를 `"vehicle_data"`로 게시한다. 앱의 `getSystemService` 연결에는 별도로 SystemServiceRegistry의 manager 생성/캐시 등록과 Context 이름 연결이 필요하다. 선택한 AOSP revision에서 API·권한·SELinux를 검증한다.
- 앱에서 `getSystemService("vehicle_data")` → `VehicleDataManager` 인스턴스 반환
- 등록 구조 참고: [AOSP SystemServiceRegistry 소스](https://android.googlesource.com/platform/frameworks/base/+/3963bd5d5d453a337b192df1d810397f7ead20d4/core/java/android/app/SystemServiceRegistry.java). 이 참조 revision을 Android 후보의 검증 완료로 해석하지 않는다.

### 4.3.2. AIDL 인터페이스

프로젝트 내부 Binder 인터페이스의 작성 정본은 [IVI M3 §3.3](../plan/detail/ivi/M3_HAL_Service_대시보드.md#33-binder-ipc--service-계층-plan-a)이다. `IVehicleDataService.getLatestData/registerListener/unregisterListener`, `IVehicleDataListener`, `VehicleDataParcel` 명칭으로 통일한다. HIDL `VehicleData`와 Parcelable의 필드·단위·품질/stale를 1:1 대조한다. 이 앱 내부 인터페이스 이름 정리는 ICD HAL API 변경이 아니다.

### 4.3.3. 데이터 흐름 (HAL → Service → App)

```
HAL onVehicleDataChanged()
    │  (사용자 정의 HIDL Binder)
    ▼
VehicleDataService.onHalCallback()
    │  (Binder IPC)
    ▼
IVehicleDataListener.onDataChanged()
    │  (등록된 앱의 콜백)
    ▼
DashboardViewModel._vehicleState.emit()
    │  (StateFlow)
    ▼
DashboardScreen collectAsState()
    → UI 자동 리컴포지션
```

## 4.4. 대시보드 앱 (Jetpack Compose)

### 4.4.1. Composable 트리 구조

```
DashboardScreen
├── SocGauge (soc: Float, soh: Float)
│   └─ 원형 프로그레스바 + 중앙 숫자
│   └─ 색상 코드: soc >= 50 → Green, soc >= 20 → Orange, else → Red
├── VehicleInfoCard (voltage, current, temperature)
│   └─ 전압, 전류, 온도 실시간 표시
├── FailSafeIndicator (state: Int)
│   └─ NORMAL=초록, WARNING=주황, CRITICAL=빨강, SHUTDOWN=검정+점멸
│   └─ CRITICAL/SHUTDOWN 시 풀스크린 경고 Dialog 표시
├── AlertBanner (attackDetected: Boolean, attackType: String)
│   └─ 배너·경고 텍스트 즉시 완전 표시; 장식 요소에만 효과 허용
│   └─ 텍스트: "⚠ {AttackType} Attack Detected!"
│   └─ 사용자 확인까지 유지; 신규 경보는 다시 표시
└── LogPanel (recentLogs: List<LogEntry>)
    └─ 최근 20건 CAN/보안 로그 스크롤 표시
```

### 4.4.2. ViewModel 상태 관리

초기 상태를 SOC=0·SOH=100·온도=25·NORMAL의 유효 측정으로 표시하지 않는다. 최초 인증/품질 인수 전에는 미수신·품질 미확정 상태로 숫자/게이지의 유효 표시를 막는다. 이후 값·sensorState·stale·수신 시각을 한 snapshot으로 게시한다. 오류/공백 동안 마지막 유효 숫자와 마지막 확정 Fail-safe를 보존하되 정상·최신 값으로 표시하지 않는다. 승인된 ICD §8 및 IVI M3/M4의 필드·복구 3회 규칙을 따른다.

ViewModel의 StateFlow 수신(T3)과 실제 화면 렌더(T4)는 다른 시점이다. TC-IVI-008은 Service→StateFlow, TC-PERF-001은 원본 CAN 수신→렌더를 검사한다. 아래 색상 함수는 유효한 SOC에만 적용한다.

### 4.4.3. SOC 게이지 색상 코드 로직

```kotlin
fun socColor(soc: Float): Color = when {
    soc >= 50f -> Color(0xFF4CAF50)  // Green
    soc >= 20f -> Color(0xFFFF9800)  // Orange
    else       -> Color(0xFFF44336)  // Red
}
```

---

# 5. 시퀀스 다이어그램

## 5.1. 정상 시나리오: BMS 데이터 수신 → UI 표시

```
Node A              CAN Bus           Vehicle HAL         Service            App
  │                    │                  │                  │                │
  │── 0x100 BMS ────▶│                  │                  │                │
  │── 0x102 MAC ────▶│                  │                  │                │
  │                    │── CAN read ──▶│                  │                │
  │                    │                  │─ SecOC 검증      │                │
  │                    │                  │─ 파싱             │                │
  │                    │                  │── callback ──▶│                │
  │                    │                  │                  │─ Binder IPC ▶│
  │                    │                  │                  │                │─ StateFlow
  │                    │                  │                  │                │─ UI 갱신
```

## 5.2. 공격 탐지 시나리오

> ⚠️ **ADR-009 반영**: ML IDS 엔진은 Node B(IVI)가 아닌 **Node A(Ubuntu)**에서 Python 프로세스로 실행된다. IDS가 CAN 버스를 직접 모니터링하고, 탐지 결과를 CAN ID 0x200으로 **Node B 방향으로** 전송한다.
> 

```jsx
공격자         CAN Bus      [Node A] ML IDS     [Node B] Vehicle HAL    App
  │                  │                  │                    │                  │
  │── 공격 패킷 ──▶│                  │                    │                  │
  │                  │── 트래픽 수집 ──▶│                    │                  │
  │                  │                  │─ 특징 추출           │                  │
  │                  │                  │─ 이상 점수 계산       │                  │
  │                  │                  │─ 이상 판정 경계 통과           │                  │
  │                  │◀── 0x200 경보 ──│                    │                  │
  │                  │    (Node A 발신) │                    │                  │
  │                  │                  │                    │─ CAN read     │
  │                  │─────────────────────────────────────▶│─ 파싱          │
  │                  │                  │                    │─ callback ──▶│
  │                  │                  │                    │                  │─ 경보 배너
```

---

# 6. 테스트 케이스 매핑

| 모듈 | 테스트 케이스 ID | SRS 요구사항 | 파일 |
|------|----------------|-------------|------|
| VehicleHalImpl (CAN 수신) | TC-IVI-001 | FR-IVI-001 | `test/test_can_parser.cpp` |
| CanParser | TC-IVI-002 (a~c) | FR-IVI-002 | `test/test_can_parser.cpp` |
| VehicleDataService | TC-IVI-003 ~ TC-IVI-004 | FR-IVI-003~004 | `test/test_vehicle_service.java` |
| SocGauge (색상 코드) | TC-IVI-005 | FR-IVI-005 | `app/test/SocGaugeTest.kt` |
| AlertBanner | TC-IVI-006 | FR-IVI-006 | `app/test/DashboardScreenTest.kt` |
| FailSafeIndicator | TC-IVI-007 | FR-IVI-007 | `app/test/DashboardScreenTest.kt` |
| DashboardViewModel (StateFlow) | TC-IVI-008 | FR-IVI-008 | `app/test/DashboardViewModelTest.kt` |

---

# 7. 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| v1.0 | 2026-03-15 | 초안 작성 — AOSP 포팅 가이드, Vehicle HAL, VehicleDataService, 대시보드 앱, 시퀀스 다이어그램 | 팀원B |
| v1.1 | 2026-03-15 | ADR-009 반영 — §5.2 공격 탐지 시퀀스 다이어그램에 "IDS=Node A 발신" 명시 | 팀원B |
| v1.2 | 2026-04-15 | 테스트 케이스 매핑 §6 추가 | 팀원B |
| v1.3 | 2026-05-09 | §3.4.6 Plan B 대안을 ADR-010과 일치 (D-Bus/gRPC + Qt/Flutter 명시), 참조 문서 버전 ICD v1.3, SRS v1.4 반영 | 팀원B |

## 승인된 화면·센서 품질 목표

S-1=A: 경고 읽기를 지연시키는 slide/fade 등 등장 효과는 사용하지 않는다. 배너·문구는 첫 경고 반영에서 즉시 완전히 표시하고 장식 효과만 허용한다. 값 보간·게이지 지연 갱신은 추가하지 않는다. 사용자 확인은 해당 IDS 이벤트만 확인하며 새 이벤트·Fail-safe·stale·센서 오류를 해제하지 않는다.

S-2=A: IVI의 위험 경고는 ECU 상태 통보의 표시다. 실제 전류 차단 명령을 전송하거나 차단 성공을 보장하는 기능으로 설명하지 않는다.

S-3=A: 기존 HIDL/Parcelable 예시는 전환 전 계약이다. 다음 전환에서 [ICD §8](ICD.md#8-승인된-다음-전환-목표--s-3a-제품-반영-전)의 stale·sensorState를 HAL→Service→ViewModel→UI에 동일 snapshot으로 전달하고 Mock·직렬화·콜백 시험을 함께 갱신한다. 최초 상태는 측정/판정 대기이며 기본 SOC를 실측처럼 표시하지 않는다. 정상 데이터 수신 후 경과시간은 IVI 수신 기록으로 관리하고 이력이 없으면 확인 불가로 표시한다.

2026-09-08 종합 정합성 검토: 현재/예정 경로, 승인 상태, 단위·측정·실행 예제를 대조·정정했다. 세부 변경과 보류 관문은 [종합 검토](development/reviews/문서_종합정합성_검토.md)에 기록한다. 기존 요구/TC ID와 ICD 계약 본문은 보존했다.


## 2026-09-09 승인된 SecOC 현행 규칙 정정

현행 고정키 수신 규칙은 [ICD §2.3~2.5](ICD.md#23-수신-검증-절차-node-b)를 따른다. 단순 대소 비교나 범위 밖 유효 MAC만으로 counter를 재동기화하는 이전 설명은 적용하지 않는다. 실제 C++/Python verify는 이 정정과 일치하며 알고리즘 변경은 없다. 첫 수신 MAC 성공은 새 부팅을 증명하지 못하고, 수신기 재부팅 후 과거 메시지 수락 위험이 남는다. 요구사항의 replay 방어 기준을 낮추거나 전체 보안 인수를 완료 처리하지 않는다.

인증 세션 자동 복구의 승인된 방향은 유지한다. 세션 상세 계약·양측 전환·재부팅 보안 시험은 [세션 설계안](development/security/CAN_세션인증_설계안.md)의 별도 관문이다. 새 wire·키 파생·HAL 변경을 이번 정정 승인으로 포함하지 않는다.
