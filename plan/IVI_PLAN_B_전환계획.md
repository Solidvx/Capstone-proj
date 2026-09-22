# IVI Plan B 전환 및 구현 계획

> **결정일**: 2026-09-22
> **결정**: Android AOSP 포팅을 현 제출 범위에서 제외하고, Ubuntu + C++17 + SocketCAN + Qt Quick/QML로 Node B를 구현한다.
> **통합 기준 브랜치**: 원격 `develop` (초기 생성 기준 `main`의 `70acbd34fcea`)
> **기존 구현 출처**: 팀 보관본 `도토리팀_소스코드/Cap-proj`, Qt 기준 커밋 `c6d632c`
> **계약 정본**: `docs/ICD.md`. CAN ID, payload, SecOC 규칙은 플랫폼 전환으로 바꾸지 않는다.

## 1. 목표와 범위

Node B를 하나의 Linux 네이티브 IVI 프로그램으로 구성한다.

```text
SocketCAN(can0/vcan0)
  -> SocketCanReceiver
  -> pending original/auth pair + SecOCVerifier
  -> CanParser
  -> VehicleDataService
  -> DashboardViewModel
  -> Qt Quick/QML Dashboard
```

시간 제약을 고려해 D-Bus/gRPC 프로세스 분리는 현 필수 범위에서 제외한다. 수신, 인증, 상태 관리, UI 계층은 C++ 인터페이스로 분리해 이후 IPC를 추가할 수 있게 유지한다. Android HIDL, Binder/AIDL, Jetpack Compose, AOSP 빌드 및 포팅은 후속 과제로 둔다.

### 완료 기준

- `0x100`, `0x101`, `0x102`, `0x103`, `0x200`을 현행 ICD대로 처리한다.
- `0x100/0x101` 데이터는 대응 인증 프레임 검증에 성공한 뒤에만 UI 상태에 반영한다.
- 변조 MAC, 잘못된 counter, 인증 timeout에서는 마지막 정상값을 유지한다.
- rolling counter의 `+100`, `+101`, `0xFFFFFFFF -> 0` 경계를 검증한다.
- 300ms 이상 정상 인증 데이터가 없으면 stale을 표시한다.
- IDS 경고는 사용자 확인까지 유지하며, 확인 뒤 새로운 이벤트는 다시 표시한다.
- Qt 대시보드가 SOC/SOH/전압/전류/온도, sensor state, stale, Fail-safe, IDS 경고를 표시한다.
- `vcan0` 자동 시험을 통과하고, 가능하면 Node A와 물리 `can0` 통합 결과를 별도로 기록한다.
- 목표 지연과 실측 지연을 구분하고 T1~T4 측정 위치와 표본 수를 남긴다.

## 2. Git 브랜치와 반입 원칙

### 2.1 브랜치

원격 `develop`은 `main`의 기준 커밋 `70acbd34fcea`에서 생성되었다. 이후 IVI 작업은 최신 `develop`에서 기능 브랜치를 만들고 PR base를 `develop`으로 지정한다.

```bash
git switch develop
git pull --ff-only origin develop
git switch -c feat/ivi-<topic>
```

이전 저장소의 `develop`이나 `feat/#3-ivi-qt-dashboard`를 현재 저장소에 merge하지 않는다. 두 저장소의 문서와 이력이 갈라져 있고, 이전 작업 트리에는 삭제·수정·미추적 파일이 섞여 있기 때문이다. 필요한 파일만 가져오고 출처를 커밋 메시지와 PR 본문에 기록한다.

### 2.2 반입 출처

| 분류 | 출처 | 반입 방식 |
|---|---|---|
| Qt/SocketCAN/Service 기준 코드 | 이전 커밋 `c6d632c` | 커밋의 해당 파일만 추출 |
| parser/SecOC와 단위시험 | 이전 작업 트리 및 2026-08-31 zip | SHA-256 확인 후 복사 |
| 이전 Plan B 설계 기록 | 이전 `docs/ADR.md`, `docs/SDD-IVI.md`, `docs/TEST_PLAN.md` | 현 문서에 수동 병합 |
| Android/HIDL/AIDL/Kotlin 0바이트 파일 | 이전 작업 트리 | 반입하지 않음 |
| `build/`, `.DS_Store`, `__MACOSX`, 바이너리 | 이전 작업 트리/zip | 반입하지 않음 |
| 이전 `.git`, 삭제 상태, 과거 계획 전체 | 이전 저장소 | 반입하지 않음 |

커밋되지 않았던 핵심 파일은 반입 전에 아래 해시와 일치하는지 확인한다.

| 파일 | SHA-256 |
|---|---|
| `hal/can_parser.cpp` | `7bd5b00b8cae04faeeaa6e2124945a23e27cf1829870e44683b8b7822aa90001` |
| `hal/can_parser.h` | `eef5d55cd3486c848f1ed783f3e66a03990d59e4f80de4843f706e75bdd847f5` |
| `hal/secoc_verifier.cpp` | `37d931777c5dc2028018d40cee6f6bdc6a333298ee990b072d3031f8e460c157` |
| `hal/secoc_verifier.h` | `138f5186ac6054af83415a7c9fd7b5a26a530ca3b5fe30130ce9eba7498d86da` |
| `test/test_can_parser.cpp` | `2886b2971648289ceb1df650a37d2182d9a397a9c192c8a6ad0f88e85c352a76` |
| `test/test_secoc_verifier.cpp` | `e1adbba06e0fa526d988476388372cb208029d708020291d09f1fa8be6357d4a` |

### 2.3 권장 커밋 순서

1. `docs(ivi): Plan B 전환 계획 확정`
2. `feat(ivi): 기존 Qt SocketCAN 기준 코드 이관`
3. `fix(secoc): 인증 성공 후 데이터 게시하도록 상태 처리 수정`
4. `fix(hal): CAN 필터와 수신 복구 및 stale 처리 추가`
5. `feat(ui): stale 센서 상태와 확인형 경고 표시`
6. `test(ivi): 현행 ICD 경계 및 vcan 통합 시험 추가`
7. `docs(ivi): Plan B 설계 시험 배포 문서 동기화`
8. `ci(ivi): Linux Qt 빌드와 테스트 자동화`

각 커밋은 대응 시험을 함께 포함한다. 기준 코드를 반입한 두 번째 커밋은 최종 병합 대상이 아니라 출처 보존용 중간 상태이며, 보안 수정과 시험이 끝나기 전에는 `main`에 병합하지 않는다.

## 3. 단계별 실행 계획

### P0. 전환 기록과 기준 고정 — 0.5일

**작업**

- ADR-010을 `Activated`로 갱신하고 결정일·시간 제약·채택 스택을 기록한다.
- ADR-004의 HIDL 결정은 삭제하지 않고 `Superseded for current delivery by ADR-010`으로 표시한다.
- Android 전용 요구와 시험을 Plan B 대응 항목으로 매핑한다.
- 현행 ICD 버전과 ECU SecOC 테스트 벡터를 고정한다.

**완료 증거**

- Plan B 구성과 제외 범위가 ADR, SRS, 상위 IVI 계획에서 일치한다.
- CAN/SecOC 계약 변경이 없음을 확인한다.

### P1. 선택 이관과 재현 가능한 빌드 — 0.5~1일

**반입 대상**

```text
ivi_platform/
├── CMakeLists.txt
├── hal/
│   ├── can_parser.{h,cpp}
│   ├── secoc_verifier.{h,cpp}
│   └── socketcan_receiver.{h,cpp}
├── service/vehicle_data_service.{h,cpp}
├── ui_qml/
│   ├── DashboardViewModel.{h,cpp}
│   ├── main.cpp
│   └── qml/Dashboard.qml
├── scripts/
│   ├── check_qt_ivi_env.sh
│   ├── send_ivi_test_vectors.py
│   └── measure_latency.py
└── test/
    ├── test_can_parser.cpp
    ├── test_secoc_verifier.cpp
    └── test_vehicle_data_service.cpp
```

**수정**

- 모든 `Makefile`을 무시하는 루트 `.gitignore` 규칙을 확인하고 CMake를 공식 빌드 진입점으로 고정한다.
- build 산출물과 테스트 바이너리는 생성물로 유지하고 Git에 추가하지 않는다.
- Qt가 없는 환경에서도 parser, SecOC, service 단위시험을 빌드할 수 있게 CMake target을 분리한다.
- `assert`만 사용하는 시험을 명시적 실패 또는 GoogleTest로 교체한다.

**완료 증거**

- 깨끗한 checkout에서 configure/build/test 명령이 재현된다.
- Debug와 Release 모두 실제 assertion 개수와 실패를 보고한다.

### P2. CAN·SecOC 핵심 수정 — 1~1.5일

**필수 수정**

- 원본 프레임을 pending buffer에 저장하고 인증 성공 시에만 snapshot을 commit한다.
- BMS(`0x100/0x102`)와 Fail-safe(`0x101/0x103`)의 pending 및 counter 상태를 분리한다.
- counter 검사는 unsigned delta `1..100`으로 구현한다.
- 최초 정상 MAC 처리, wrap-around, replay, `+101`, 변조 MAC을 구분한다.
- 실패한 인증은 counter와 마지막 정상값을 갱신하지 않는다.
- pending timeout, 대응 원본이 없는 auth, 새 원본 덮어쓰기 정책을 명시하고 시험한다.
- `0x100` 수신만으로 Fail-safe 상태를 새로 추론하지 않는다.
- 정확한 DLC 8, SFF ID, RTR/ERR 제외, 허용 ID 필터를 적용한다.

**최소 시험**

- signed current와 temperature offset
- 알려지지 않은 ID/잘못된 DLC
- 정상/변조 HMAC
- counter `+1`, `+100`, `+101`, replay, wrap-around
- auth 전 값 미갱신, auth 실패 후 값 미갱신
- BMS와 Fail-safe 쌍이 섞여 도착하는 경우

### P3. 상태·UI 완성 — 1일

**작업**

- `VehicleData`에 현행 목표 계약의 `sensorState`, `stale` 및 데이터 유효 상태를 반영한다.
- 최초 정상 데이터 전에는 숫자를 실제 측정값처럼 표시하지 않는다.
- 마지막 정상 인증 시각에서 300ms가 지나면 stale로 표시한다.
- sensor error 중 마지막 정상값과 경과시간을 표시한다.
- Fail-safe의 CRITICAL/SHUTDOWN은 전체 화면 경고로 표시한다.
- reason `0x07`을 포함한 전체 사유 문자열을 제공한다.
- IDS 이벤트는 BMS 갱신으로 해제하지 않고 사용자 확인 동작으로만 해제한다.
- 확인한 이벤트와 이후 새 이벤트를 구분한다.

**완료 증거**

- 초기 대기, 정상, stale, sensor error, WARNING, CRITICAL, SHUTDOWN, IDS 경고 화면을 각각 재현한다.
- 보안 실패 전후로 보호 데이터 표시가 바뀌지 않는 것을 확인한다.

### P4. vcan 통합과 계측 — 1일

**작업**

- `vcan0` 준비 스크립트와 정상·변조·replay·timeout 시나리오를 자동화한다.
- `send_ivi_test_vectors.py`는 ICD §1~2의 현행 payload를 사용한다. sensorState는 §8 동시 전환 전에는 별도 목표 계약 시험으로 분리하며 현행 wire에 섞지 않는다.
- `measure_latency.py`가 T1 CAN 송신, T2 수신, T3 상태 게시, T4 화면 반영을 구분해 수집하도록 보강한다.
- 표본 수, 손실 수, 평균, p95, p99, 최대값을 결과에 기록한다.

**완료 증거**

- 공식 TC-ID별 명령, 환경, 로그 및 결과 파일이 연결된다.
- 실행하지 않은 Qt 화면 시험이나 물리 CAN 시험을 PASS로 기록하지 않는다.

### P5. Raspberry Pi 배포와 물리 통합 — 0.5~1일

**작업**

- Ubuntu 대상에 Qt runtime, SocketCAN, key 파일 권한을 준비한다.
- `systemd` 서비스 또는 데모 실행 스크립트 중 실제 시연 방식 하나를 고정한다.
- `can0` 500kbps 설정, MCP2515 상태, 종단 저항을 확인한다.
- Node A와 IT-001~005를 실행한다.
- 프로세스 재시작, CAN 링크 down/up, 잘못된 키, Node A 중단 후 복구를 점검한다.

**완료 증거**

- 대상 장비의 commit hash, 빌드 명령, 실행 명령과 통합 로그를 남긴다.
- `vcan0` 결과와 물리 CAN 결과를 별도로 표시한다.

### P6. 문서·CI·데모 마감 — 0.5~1일

**문서 병합**

| 현 문서 | 가져올 내용 | 반드시 고칠 내용 |
|---|---|---|
| `docs/ADR.md` | 이전 ADR-010의 실제 Qt 전환 배경과 구조 | 과거 날짜·환경을 현재 결정 근거로 오인하지 않도록 갱신 |
| `docs/SDD-IVI.md` | 이전 Plan B 부록의 C++/Qt 모듈 구조와 실행 명령 | 인증 전 게시, IDS 자동 해제, BMS 기반 Fail-safe 추론 제거 |
| `docs/TEST_PLAN.md` | 이전 Plan B TC 매핑과 vcan 명령 | 기존 PASS를 `미실행/재검증 필요`로 초기화하고 현행 합격 조건 적용 |
| `docs/SRS.md` | FR-IVI-001~008의 기능 의도 | HIDL/Binder/StateFlow/Android 표현을 SocketCAN/Service/QObject/QML로 전환 |
| `docs/CICD_SPEC.md` | ARM64 빌드·배포 목표 | AOSP 단계 대신 Linux CMake/Qt, 단위시험, 패키징, SSH 배포로 갱신 |
| `docs/ICD.md` | CAN/SecOC 계약 유지 | HIDL 전용 API 절의 적용 상태와 Plan B C++ 데이터 모델을 명확히 구분 |
| `README.md` | 실제 IVI 빌드·실행 진입점 | 미구현 Android 명령 제거, vcan/can0 절차와 제한 기록 |

이전 문서를 파일 단위로 덮어쓰지 않는다. 현행 ICD v1.5, SRS v1.6, SDD-IVI v2.0과 sensorState/stale 정책 및 보안 후속 결정을 보존하면서 Plan B 관련 문단만 병합한다.

**CI 최소 범위**

1. CMake configure/build
2. parser/SecOC/service unit tests
3. Python script syntax 및 관련 pytest
4. 가능하면 Linux Qt headless build
5. 산출물과 시험 결과 업로드

## 4. 우선순위

### 제출 전 필수

1. 선택 이관과 clean build
2. 인증 성공 전 데이터 미게시
3. counter wrap/replay/변조 시험
4. stale 및 IDS 확인 정책
5. Qt 기본 화면과 vcan 시나리오
6. ADR, SDD-IVI, TEST_PLAN, README 동기화

### 시간이 남으면 수행

- ARM64 cross-build와 GitHub Actions artifact
- systemd 자동 시작 및 health check
- 화면 캡처 자동화
- 장시간/메모리 누수 시험
- D-Bus 또는 gRPC 프로세스 분리

### 현 제출 범위에서 제외

- AOSP 빌드와 RPi4 Android 포팅
- HIDL HAL 등록
- Binder/AIDL SystemService
- Jetpack Compose 앱
- Android Instrumentation 시험

## 5. 병합 게이트

`feat/ivi-plan-b`를 `develop`에 병합하기 전에 다음을 모두 확인한다.

- [ ] 이전 저장소 전체 merge/cherry-pick 없이 선택 파일만 반입했다.
- [ ] 빌드 산출물, 0바이트 Android 파일, 비밀키가 추적되지 않는다.
- [ ] clean checkout에서 CMake build와 CTest가 통과한다.
- [ ] 변조 MAC 및 잘못된 counter에서 표시 값이 갱신되지 않는다.
- [ ] IDS 경고가 사용자 확인 전까지 유지된다.
- [ ] 문서의 PASS 표시는 이번 브랜치에서 실행한 증거만 사용한다.
- [ ] ICD CAN/SecOC 계약과 ECU 테스트 벡터가 일치한다.
- [ ] 미실행 물리 CAN, 성능, 안정성 시험을 명확히 표시한다.

## 6. 진행 기록

| 단계 | 상태 | 산출물/검증 | 차단 요인 |
|---|---|---|---|
| P0 전환 기록 | 완료 | ADR·SRS·ICD·SDD-IVI·TEST_PLAN·진행 안내 동기화 | 없음 |
| P1 선택 이관 | 완료 | CMake/core/SocketCAN/Qt 기준 코드, Debug·Release CTest 각 3/3 | Qt 앱 빌드는 P3에서 검증 |
| P2 CAN·SecOC 수정 | 완료 | pending 만료·교체·orphan, 두 쌍 분리, frame validator, retry 정책, Debug·Release 각 6/6 | Linux 실제 수신은 P4 vcan에서 검증 |
| P3 상태·UI | 기준 화면 준비 | QObject view model과 QML 기본 화면 | stale·IDS ack·전체 화면 경고·Qt 시험 |
| P4 vcan·계측 | 준비물 일부 추가 | 벡터 송신기·latency 요약기 | Linux vcan·T1~T4 자동 계측 |
| P5 물리 통합 | 미착수 |  | 장비 가용성 |
| P6 문서·CI·데모 | 기록 기반 준비 | `docs/aidlc/changes/CHG-003/` | CI·공식 증거·데모 |
