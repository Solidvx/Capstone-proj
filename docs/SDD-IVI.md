> **문서명**: Software Design Document — Node B (IVI)
> **버전**: v2.5 | **작성일**: 2026-03-15 | **최종 수정**: 2026-11-11 | **작성자**: 팀원B
> **참조**: ICD v1.6, SRS v1.6 (FR-IVI-*), ADR-010, IVI Plan B 전환 계획

# 1. 목적과 현재 기준선

**2026-11-11 승인된 제품 전환 설계:** [ICD session-v2](ICD-CAN-SESSION.md)/[진단](ICD-CAN-DIAGNOSTIC.md)을 적용한다. 세션·유한 인증 정렬/보호 예약·진단을 같은 수신 소유 경계에서 처리하고 현재 상태 반영 뒤 receipt를 전송한다. 새 세션은 옛 후보/정렬 큐를 버리되 마지막 화면/위험을 정상으로 낮추지 않는다. Service snapshot은 프로그램 단계/입력 준비·현재 위험·통신 신선도·사건/거부/관찰 품질·Flooding 출처를 분리해 Qt queued signal로 넘긴다. 팝업 닫기는 reset/재시작 ACK가 아니다. 실제 연결/인수는 [CHG-029](aidlc/changes/CHG-029/aidlc-state.md)를 따른다.

이 문서는 Node B를 Debian 13 ARM64, C++17, SocketCAN, Qt 6.8 Quick/QML로 구현하기 위한 설계 기준이다. CAN ID·DLC·바이트 순서·SecOC MAC/rolling counter 계약은 [ICD](ICD.md)를 그대로 따른다.

2026-09-23 현재 `ivi_platform/`에는 P1 기준선, P2 CAN·SecOC, P3 상태·Qt UI와 P4 Linux vcan·계측이 있다. Linux aarch64 VM에서 Qt Release 9/9와 실제 `vcan0` 1,000표본을 검증했다. RPi4/MCP2515 `can0`와 물리 화면은 P5에서 별도 검증한다. Android AOSP, HIDL, Binder/AIDL, Jetpack Compose 설계는 과거 결정 기록으로만 유지한다.

# 2. 구조와 책임

```text
QML Dashboard
    │ Qt property binding / signal
DashboardViewModel (QObject)
    │ immutable snapshot
VehicleDataService
    ├── CanParser
    ├── SecOcVerifier
    └── SocketCanReceiver ── can0 또는 vcan0
```

첫 제출은 한 프로세스로 구성한다. 모듈 경계는 C++ 인터페이스로 유지하되 D-Bus/gRPC 프로세스 분리는 후속 범위로 둔다. 이렇게 하면 IPC 없이 통합 위험을 줄이면서 수신·인증·상태·표시 책임을 독립 시험할 수 있다.

## 2.1. 목표 디렉터리

```text
ivi_platform/
├── CMakeLists.txt
├── README.md
├── hal/
│   ├── socketcan_receiver.{h,cpp}
│   ├── can_frame_validator.{h,cpp}
│   ├── receive_retry_policy.h
│   ├── can_parser.{h,cpp}
│   └── secoc_verifier.{h,cpp}
├── service/vehicle_data_service.{h,cpp}
├── ui_qml/
│   ├── main.cpp
│   ├── dashboard_view_model.{h,cpp}
│   └── qml/
│       └── Main.qml
├── scripts/
│   ├── check_qt_ivi_env.sh
│   ├── send_ivi_test_vectors.py
│   ├── measure_latency.py
│   ├── run_vcan_integration.sh
│   └── run_vcan_latency.sh
└── test/
    ├── test_can_parser.cpp
    ├── test_can_frame_validator.cpp
    ├── test_receive_retry_policy.cpp
    ├── test_secoc_verifier.cpp
    ├── test_vehicle_data_service.cpp
    ├── test_vehicle_data_service_security.cpp
    ├── test_vehicle_data_service_state.cpp
    ├── test_dashboard_view_model.cpp
    └── test_socketcan_receiver.cpp
```

이 트리의 파일은 현재 존재한다. ViewModel은 Qt Test로 검증하고 QML 화면 상태는 deterministic demo/offscreen render로 확인한다.

# 3. 모듈 설계

## 3.1. SocketCanReceiver

- `PF_CAN/SOCK_RAW` 소켓을 지정 인터페이스(`vcan0` 기본, 배포 시 `can0`)에 바인드한다.
- CAN 필터는 `0x100`, `0x101`, `0x102`, `0x103`, `0x200`만 허용한다.
- Classic CAN DLC 8만 상위로 전달하고 RTR·ERR·확장 ID 및 잘못된 길이는 거부한다.
- 수신 대기는 `poll()`과 종료용 `eventfd` 또는 유한 timeout으로 깨울 수 있게 한다. 다른 스레드의 `close()`만으로 blocking read 종료를 가정하지 않는다.
- 소켓은 non-blocking으로 열며 poll/read의 일시 오류는 10/20/30ms backoff로 최대 3회 재시도한다. 정상 read에서 retry 예산을 초기화하고 지속 오류는 오류 문자열을 남긴 뒤 loop를 종료한다.

## 3.2. SecOcVerifier와 프레임 결합

인증 대상 원본/인증 프레임 쌍은 `(0x100, 0x102)`, `(0x101, 0x103)`이다. 원본 프레임을 ID별 pending 슬롯에 저장하고 해당 인증 프레임이 도착했을 때 다음 순서로 처리한다.

1. DLC와 ID 쌍을 확인한다.
2. `delta = receivedCounter - lastAcceptedCounter`를 `uint32_t` 모듈러 연산으로 계산한다.
3. 초기 동기화 정책 또는 `1 <= delta <= 100`을 만족하는지 확인한다.
4. ICD의 입력 바이트 순서로 HMAC-SHA256을 계산하고 앞 4바이트를 constant-time 비교한다.
5. 성공한 경우에만 counter를 갱신하고 원본을 파싱·게시한다.

MAC 실패, counter 거부, 쌍 timeout은 데이터를 게시하지 않으며 마지막 정상 snapshot을 덮어쓰지 않는다. 실패한 MAC은 수신 counter를 소비하지 않는다. `0x200` IDS 경보는 현 계약상 SecOC 비대상이다.

pending은 BMS와 Fail-safe에 각각 한 슬롯만 둔다. 보관시간은 100ms이며 같은 ID의 새 원본은 기존 원본을 폐기·교체한다. 인증이 먼저 오면 다음 원본에 연결하지 않고 orphan으로 폐기한다. 100ms는 raw/auth pair의 내부 자원 정책이며 ICD §2.5의 300ms stale 판정을 바꾸지 않는다.

## 3.3. CanParser

`CanParser`는 인증이 끝난 8바이트 payload를 host 표현으로 변환하는 순수 함수 모듈이다. 전압·전류·온도의 endian, scale, signed 변환은 ICD 벡터로 고정한다. 범위 밖 값과 예약 필드 위반은 오류로 반환하며 임의 보정하지 않는다.

## 3.4. VehicleDataService

서비스는 다음 하나의 일관된 snapshot을 소유한다.

```cpp
struct VehicleData {
    double socPercent;
    double sohPercent;
    double voltageV;
    double currentA;
    double temperatureC;
    std::uint8_t failSafeState;
    std::uint8_t sensorState;
    bool stale;
    bool valid;
    std::chrono::steady_clock::time_point receivedAt;
};
```

- 인증 성공 데이터만 snapshot에 반영한다.
- 최초 정상 수신 전에는 `valid=false`로 두어 0%를 실제 SOC처럼 표시하지 않는다.
- 마지막 인증 성공 BMS 시각을 별도로 보관하고 300ms부터 마지막 정상 수치를 보존하면서 `stale=true`로 전환한다. Fail-safe와 IDS 이벤트는 이 시각을 갱신하지 않는다.
- Fail-safe CRITICAL/SHUTDOWN과 IDS 경보는 별도 이벤트로 전달한다.
- IDS 경보 확인(ack)은 관찰한 event sequence가 현재 sequence와 같을 때만 표시 상태를 닫으며 stale·센서 오류·Fail-safe를 해제하지 않는다.
- `sensorState`의 실제 wire 반영은 ICD §8의 양 노드 동시 전환 이후에만 유효하다. 전환 전에는 미지원으로 표시한다.

## 3.5. DashboardViewModel

`DashboardViewModel`은 `QObject`와 `Q_PROPERTY`로 snapshot과 경보 상태를 QML에 제공한다. CAN 수신 스레드에서 UI 객체를 직접 수정하지 않고 queued signal/slot으로 GUI 스레드에 전달한다. 한 snapshot의 필드는 한 번에 교체해 서로 다른 시점의 값이 섞이지 않게 한다.

## 3.6. Qt Quick/QML 화면

- 초기 상태: 값 대신 `--`와 연결 대기 상태를 표시한다.
- SOC 색상: 50% 이상 초록, 20% 이상 50% 미만 주황, 20% 미만 빨강.
- stale 또는 sensor 오류: 마지막 값임을 명시하고 정상 색상만으로 오인되지 않게 한다.
- CRITICAL/SHUTDOWN: 중앙 위험 팝업을 표시하고 닫은 뒤에도 전체 화면 위험 테두리와 상태 카드를 유지한다.
- IDS 경보: 공격 이름의 중앙 팝업을 표시한다. 닫기는 ViewModel의 popup만 숨기며 서비스 ack를 호출하지 않는다. 같은 활성 episode의 반복 유형 보고는 팝업 중복을 억제하고 유형별 결과/이력을 유지한다. 새 사건 구분은 후속 인수 항목이다.

# 4. 실행·스레드·배포

프로세스는 수신 worker 한 개와 Qt GUI thread로 시작한다. 50ms Qt timer가 service의 monotonic stale 판정을 갱신한다. 종료 순서는 신규 이벤트 차단, 수신 대기 해제, worker join, SocketCAN 자원 해제, UI 종료다. 구성값은 CAN 인터페이스, 키 파일 경로, timeout이며 비밀키는 저장소에 넣지 않는다. `--demo`는 CAN·키 없이 P3 화면을 재현하는 개발·시험 진입점이다.

P4 계측 모드의 `--latency-csv`와 `--latency-samples`는 T1~T4 stage row를 기록한다. T1~T4는 한 프로세스의 `steady_clock`을 사용하며 CAN payload에 timestamp나 sample id를 넣지 않는다. T4는 `QQuickWindow::frameSwapped`이고 종료는 signal callback 밖의 다음 event-loop tick에서 수행한다.

004 계측 보완은 실제 `--run-id`와 Linux boot UUID를 기록한다. `beforeSynchronizing`에서 표본 ID를 프레임에 연결하고 `frameSwapped` emitting thread에서 T4를 채취한다. 프레임당 최신 표본 최대1개만 완료로 세며, 합쳐진 이전 갱신은 NOT_RENDERED, 미확정 종료/시각 오류/비노출은 INDETERMINATE다. 실제 패널 픽셀 표시 시각을 보장하지 않는다. CSV 열·종료·집계 계약은 [성능 전달본 안내](development/playbooks/ivi-performance-handoff.md)에 있다. 기존 5열 CSV용 집계 도구를 004의 상태 포함 CSV에 그대로 적용하지 않는다.

개발 환경은 `vcan0`, 실제 RPi4는 `can0`을 사용한다. Qt 전체 빌드의 최소 버전은 6.8이며 Debian 13 배포판 패키지를 기준으로 한다. 배포 전 Node A와 bitrate 500 kbps, CAN ID, 키, counter 초기화 정책을 함께 확인한다.

# 5. 검증 전략

- 순수 단위 시험: parser 경계값, signed 변환, HMAC 정상/변조, counter replay/wrap.
- 서비스 시험: 인증 전 미게시, last-good/stale, Fail-safe·IDS 이벤트, ack 경쟁.
- Qt 시험: Q_PROPERTY 갱신, SOC 색상, 전체 화면 경고, IDS 유지/재표시.
- vcan 통합: 실제 PF_CAN에서 filter·종료, `0x100→0x102`와 변조·replay·timeout, Qt offscreen T1→T4 1,000회 계측.
- 물리 통합: RPi4 `can0`, Node A 송신과 실제 display·복구를 vcan 결과와 분리 검증.

세부 합격 기준은 [TEST_PLAN](TEST_PLAN.md)을 따른다. P1~P3의 macOS core/Qt 결과, P4 Linux vcan 결과, P5 물리 CAN 미실행 범위를 구분한다.

# 6. 변경 이력

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| v1.3 | 2026-09-09 | Android/HIDL 기반 설계 보완 |
| v2.0 | 2026-09-22 | ADR-010 활성화에 따라 Ubuntu/C++17/SocketCAN/Qt Quick 구조로 전환 |
| v2.1 | 2026-09-23 | P2 pending 100ms·교체·orphan, frame validator와 제한 수신 retry 구현 상태 반영 |
| v2.2 | 2026-09-23 | P3 BMS 300ms stale, IDS sequence ack, Qt ViewModel·QML 경고와 실제 Qt 시험 반영 |
| v2.3 | 2026-09-23 | P4 Linux vcan 통합시험, T1~T4 stage 계측·자동화와 1,000표본 결과 반영 |
| v2.4 | 2026-10-03 | RPi4 Debian 13·Qt 6.8 배포 기준과 강제 SocketCAN 검증 조건 반영 |

## SecOC 런타임 보강 (CHG-006)

P2 위에 무수신 pending 만료, 실패 observer 진단 전달과 CRITICAL QML 경고를 구현했다. `VehicleDataService::pollTimeouts()`는 무수신 pending 100ms 만료만 담당하는 구현 내부 타이머 진입점(10ms)이며 ICD의 observer/wire 계약은 유지한다. 300ms stale은 P3의 `refreshTime()`(50ms)으로 일원화했고 stale 로그만 `reason=BMS_STALE`로 맞췄다. 실패 auth 뒤 원본 유지·새 원본 교체 정책은 유지하며, 키 재설정은 pending만 폐기하고 counter를 초기화하지 않는다. 상세 동작·재현은 [IVI README](../ivi_platform/README.md), 결과는 [CHG-006](aidlc/changes/CHG-006/audit.md)을 따른다. 물리 수신 복구·인증 세션 전환·P3 전체 UI 완료를 뜻하지 않는다.

## 2026-11-10 앱형 UI 제품 연결

[CHG-028](aidlc/changes/CHG-028/evidence.md). 배터리/보안/이력/설정, 공통800×480 canvas와 회전/scale, 내부 스크롤·테마·중앙 팝업을 구현했다. 배터리 페이지는 현황과 최근2이벤트·하단44px탭까지 고정 배치하며 보안/이력만 내부 스크롤한다. 실제 전체화면이 기본이고 점검용 --windowed를 제공한다.

ViewModel은 수신 snapshot에서 의미 있는 상태 전이·IDS 보고·SecOC 실패를 별도 UI 캐시로 유지한다. 현재 위험 상태의 인증 이벤트가 없으면 BMS만으로 NORMAL을 추정하지 않는다. legacy sensorState0은 미지원이며 센서 오류처럼 표시하지 않는다. 거부 진단은 특정 공격 차단 완료로 귀속하지 않는다. 재시작 진행/완료 표시는 실제 근거가 없으므로 미구현으로 남기고 [후속 결정](development/design/IVI_UI_추가연결_결정사항.md)에 연결한다.

이벤트는 프로세스 메모리100건이며 테마만 QSettings에 저장한다. 계측용 measurementReady 경로는 유지한다. 기존 service ack 경쟁 규칙은 유지되며 새 UI 닫기 동작과 구분한다.


## 2026-11-11 실제 session-v2 수신·화면 연결

VehicleDataService의 enableSession/processSessionFrame/pollSession이 같은 Exchange를 직렬 소유한다. 실제 SocketCAN 수신에서 캡처한 ns 시각을 보존하고 검증/정렬/반영 뒤 서비스 시각을 따로 기록한다. 수신 콜백과 GUI 타이머의 늦은 알림은 snapshot revision으로 걸러 최신 위험/데이터를 보존한다. 인증된 현재 위험 동기화와 새 BMS 준비는 구분하며 무수신은 마지막 값/위험을 보존한 연결 대기로 처리한다. 제품 경계에서 legacy 자동 fallback은 없다.

진단은 인증 후 snapshot/제한 receipt까지 연결했다. IDS 사건/실제 재시작 controller/전체 단계 전달은 미완료이며 보안 관찰 미연결을 정상으로 표시하지 않는다. [실제품 증거](aidlc/changes/CHG-029/ivi-product-evidence.md)의 실제 앱2개 vcan 결과와 물리 DSI 미검증 범위를 따른다.

### session-v2 실제 거부 기록과 보고

`VehicleDataService::configureRejectionReports(capacity, frame_budget, expiry_ms)`는 세션 활성화 전에 한 번 선택하는 제품 내부 송신 정책이다. HAL/wire 규격은 [인증 진단 계약](ICD-CAN-DIAGNOSTIC.md)을 따른다. 실제 수신 결정에서 IVI instance/거부 UUID/사유/처리/관찰 후보 참조를 생성하고 최신 로컬 기록을 snapshot에 게시한다. 유효 MAC이 확인돼야 하는 사유는 실제 검증된 쌍과 context가 없으면 기록을 생성하지 않는다. 만료를 MAC 실패로 바꾸지 않는다.

선택적 Qt 인수 `--rejection-queue`, `--rejection-frame-budget`, `--rejection-expiry-ms`를 모두 명시하면 고정 상한 큐로 인증 거부 기록을 ECU에 전송한다. 세션 변경·기한·큐 포화는 보고를 버리며 BMS 수신을 막지 않는다. outgoing adapter 인계는 원격 전달 확인이 아니다. 실제 ECU의 인증된 수신 로그에서 같은 거부 UUID를 확인해야 왕복 전달 증거가 된다.

화면은 실제 검증된 재생 거부 기록에 ‘재전송 데이터를 거부했습니다’를 표시한다. 경보만 있거나 확인 기한이 만료된 후보에는 이 문구를 사용하지 않는다. IDS 사건과 특정 거부의 유일한 후보 연결·전체 공격의 차단 귀속은 계속 별도 미완료 경계다. 기존 legacy 프로파일과 혼동하지 않는다.

### 이벤트 요약 영속 저장

이벤트 payload의 `typed_incidents`는 유형(`fuzzy/replay/spoofing/flooding`)별 `incident_id`와 실제 연결된 경우에만 `rejection_id`를 함께 보관한다. 기존 ID 배열은 유지하지만 빈 슬롯이 제거된 배열끼리 위치로 연결하지 않는다. 추가 필드가 없는 과거 기록의 유형/거부 연결을 추정하지 않는다. 저장된 연결은 당시 snapshot의 증거이며 재실행 시 현재 공격 상태나 차단 성공으로 복원하지 않는다.

`export_event_history.py`의 허용 필드에도 같은 항목을 포함하여 기존 digest 검증 후 그대로 내보낸다. 내보내기가 누락된 거부 ID를 채우거나 과거 사건을 현재 진행 중 상태로 바꾸지 않는다. 다른 미승인 필드는 기존과 같이 내보내기를 거부한다.

관찰 heartbeat의 탐지 표시 후 사건 ID가 늦게 도착하면 `ids-identified` 요약을 한 번 기록하여 식별 정보를 보완한다. 같은 ID의 후속 revision은 중복 기록/팝업을 만들지 않는다. 새 사건 ID의 재발 알림은 기존 규칙을 따른다.

이벤트의 선택적 `ecu_process`/`ecu_restart_plan`은 실제 인증 NodeStatus/RestartPlan의 실행·작업 식별과 envelope session_id/sequence/로컬 수신 시각을 보존한다. 식별자/세션의 첫 확인과 변경을 별도 요약으로 기록하며 단순 heartbeat는 중복 기록을 만들지 않는다. operation/보호 사건 번호가0이면 해당 키를 생략한다. 계산·위험 복원 플래그가 참이어도 현재 배터리 위험 상태를 정상으로 바꾸지 않는다. 동일 SOC/위험 코드만으로 실행 전후의 같은 사건을 추정하지 않는다. ProtectionStatus는2026-11-14 승인된 종류8이며 정확한 형식/연결 관문은 CAN 진단 ICD를 따른다. codec 승인/검증과 IVI 실제 사건 연결 구현 완료는 구분한다.

Linux desktop 실행은 외부 `supervise_dashboard.py`가 소유한다. 앱의 private socket 종료 알림은 Qt aboutToQuit 및 worker 회수 이전에 전달한다. 종료 요청 또는 첫 알림부터5초 후에도 종료하지 않으면 SIGKILL을 요청하고 최대1초 회수 대기한다. 반복 신호로 기한을 연장하지 않는다. 강제 종료는 exit124/미회수는125로 남기며 미저장 큐를 성공으로 기록하지 않는다. 강제 종료의 writer marker는 보존하여 다음 실행에서 기록 공백 가능성을 표시한다. 자동 재실행을 추가하지 않으며, 직접 바이너리 실행에는 이 외부 상한이 없다. 커널의 중단 불가 I/O 종료 보장은 물리 인수 범위와 구분한다.

`EventJournal`은 Qt 화면의 의미 있는 상태 전이/탐지 시작·종료/감시 불명/검증 결과/연결 변화 요약을 별도 작업 스레드의 유한 큐로 저장한다. `--event-policy FILE`에 개인 소유0700 디렉터리와 segment/총량/경고/여유 공간/큐 상한을 명시한다. 미선택 시 이벤트 화면에 이번 실행의 메모리 기록임을 표시한다. 파일/버전 검사·읽기·쓰기·fsync·회전은 CAN/GUI 스레드에서 수행하지 않는다. 실험 raw frame 로그와 보안 키 저장소는 이 경로에 포함하지 않는다.

각 요약에는 event UUID/IVI 실행 source UUID/분류/UTC 생성 시각/표시 문자열/세션·연결·현재 위험과 관련 incident/거부 UUID 문맥을 저장한다. 문맥 ID의 존재만으로 특정 공격의 인과적 차단을 확정하지 않는다. 기록은 sequence와 payload의 SHA-256으로 손상을 검출하며 보안 인증을 대체하지 않는다. 날짜/크기 단위로 새 JSONL segment를 만들고, 재실행 시 기존 segment에는 append하지 않는다. 끝이 잘린 미완성 행은 원본을 보존하고 제외한다. 완성된 행의 손상은 검증된 앞부분까지만 복원하고 새 쓰기를 중단한다.

이전 실행의 active marker나 저장 유실이 있으면 누락 가능 구간을 표시하고 다음 가능한 기록에 남긴다. 손상/권한/공간/큐 실패는 GUI 경고와 이력 상태로 표시하며 더 높은 배터리 보호 경고를 덮지 않는다. 최근100개를 화면에 복원하며 전체 검증 기록은 exporter로 읽는다. 수동 fresh가 이력을 초기화하지 않는다.

복구 불가능한 저장 오류는 mutex 안에서 먼저 접수를 닫고 대기 큐의 누락을 집계한 후 실패 신호를 발행한다. 실패 신호 처리 중 새 submit을 호출해도 거부하며 GUI를 디스크 I/O에 기다리게 하지 않는다. 과대 기록의 거부도 다음 저장 가능한 요약의 records_lost_before에 반영한다. checksum만 유효한 잘못된 본문을 정상 이력으로 복구하지 않고, 중복 writer는 기존 writer/marker를 변경하지 않는다.

기존 기록은 자동 삭제하지 않는다. 개발 정책 예시는10MiB segment/1GiB 경고/2GiB 총량/여유500MiB/큐128이며 운영 부하 측정값이 아니다. 한도 도달 시 이후 디스크 기록을 제한하고 메모리/현재 위험 표시는 유지한다. 자동 압축·삭제는 구현/활성화하지 않았다. Python `export_event_history.py`는 검증된 요약과 hash manifest를 새 디렉터리에 내보내며 원본을 변경하지 않는다. 실제 설치/운영 경계는 CHG-029 상태 기록을 따른다.

### 사건과 실제 거부의 제한적 연결

session-v2 IDS는 현재 관찰 구간에 유형별 근거 후보가 정확히 하나일 때만 기존 FrameReference를 채운다. 현재 검증된 연결 범위는 Replay이다. IVI는 현재 세션의 전체 원본/인증 후보 참조와 실제 MAC 검증된 replay 거부 기록을 비교하며, 단순 시각/해시나 공격 이름으로 귀속하지 않는다. 동일 후보의 서로 다른 거부 UUID, 관찰 공백, context 변경, 오래된 근거, 유한 캐시 초과는 미확정으로 남긴다. 같은 로컬 결과 UUID의 재전달은 새 관찰로 세지 않는다. 화면에는 관련 데이터의 수신 거부 확인을 표시하고, Flooding이나 근거가 약한 다른 유형을 전체 차단 완료로 표시하지 않는다.

새 세션의 이전 IDS 사건은 마지막 상태로 유지하되 새 감시에서5초 연속 정상·해당 조건 없음을 확인하면 현재 경고를 해제한다. 이전 사건은 종료 미확인으로 기록하며 정상 종료로 바꾸지 않는다. 소유자가 보낸 새로운 정상 관찰과 이전 사건 종료 확인은 다른 근거다. popup의 배터리/보안/저장 영역을 분리해 정상 회복 시 예전 위험 popup이 남는 문제를 방지한다. 배터리 위험 하향은 인증된 최신 입력/BMS 확인 이후에만 반영하며, 보안 사건 경고 해제는 실제 정상 관찰/사건 상태를 따른다.


### 센서 오류·회복 보완 (2026-11-11)

기존 인증 NodeStatus의 입력 품질을 ECU 오류 경로에서도 전달한다. IVI는 최근 입력 오류 보고와 통신 단절을 구분하고, 정상 품질 보고에 더해 새 BMS 수신을 확인한 뒤 stale을 해제한다. 상세 구현·호스트 시험·물리 미검증 범위는 [CHG-029 추가 증거](aidlc/changes/CHG-029/evidence.md)의 센서 오류 전달·회복 절을 따른다.


### 과열 대기·복귀 표시 — 2026-11-11

SHUTDOWN에서 ‘과열 보호 중’을 표시하며 유효·최신 온도≤55°C이면 ‘온도 회복 확인 중’으로 설명한다. 센서 오류/데이터 오래됨이면 현재 온도를 확인할 수 없어 보호를 유지함을 표시한다. 이 문구는 로컬 관측 설명이며 ECU 확인 타이머의 남은 초를 추정하지 않는다. 인증된 ECU 전이와 새 BMS가 확인되기 전 위험 해제를 표시하지 않는다. 저전압이 남으면 해당 경고를 표시하며 프로그램 복구 완료와 구분한다.


### BMS 작업 복구 상태 표시

최근 인증 NodeStatus 단계3/5는 계산 복원 중/운영자 확인 필요로 표시한다. 이 보고가 계속 들어오면 BMS 중단만으로 세션 재협상을 반복하지 않는다. 작업 미회수 상태를 프로세스 재시작으로 추측하지 않으며 실제 3회 실패 WARNING/0x07과 구분한다. 전체 프로세스 복구 완료·배터리 위험 정상 복귀와도 별개다.

### 보호 사건 기록의 새 세션 연결 — 2026-11-14

Service는 현재 인증 세션의 STATE·NodeStatus instance/상태/사유·ProtectionStatus를 대조한다. 검증된 resume 비트에는 NodeStatus의 resume/계산·위험 복원 플래그가 필요하다. 같은 세션의 낮은 revision·같은 revision의 다른 의미·실행/계보 변경은 미확정이며, 늦은 더 작은 sequence가 이를 해제하지 않는다. 새 인증 세션은 후보/확인 상태를 초기화한다. 진단은 기존1초 갱신/3초 보고 유효기간을 사용하고300ms BMS 측정값 신선도와 구분한다. 확인 상태 자체는 실제 센서 회복이나 배터리 정상 복귀를 뜻하지 않는다.

확인된 기록은 `ecu_protection`에 본문 hex·instance/lineage/incident·단계/위험/사유/revision·resume·인증 envelope 식별/순번·로컬 수신 시각을 보존한다. ViewModel은 같은 본문/세션의 heartbeat를 새 사건 기록으로 만들지 않는다. `protection_link`는 마지막 저장 완료된 보호 상태 기록과의 관계를 나타내며, 원시 기록은 추가만 하고 이전 위험을 정상 종료로 덮어쓰지 않는다.

| link status | 의미 |
|---|---|
|unlinked|이전 저장 완료 기록과의 연결을 확인하지 못함|
|updated|동일 실행/세션의 같은 보호 기록 갱신|
|reconnected|같은 ECU 실행에서 새 인증 세션으로 다시 연결|
|resumed|검증된 계산 계보/사건을 새 ECU 실행에서 복원|
|checkpoint-history-gap|저장본이 과거 이력보다 이전이거나 같은 revision의 의미가 달라 공백/분기 가능성 보존|
|new-lineage / new-incident|명시적 새 계산 계보 또는 새 보호 사건. 이전 active 사건은 종료 미확인으로 남김|

동일 사건은 `previous_event_id`로 저장된 레코드를 참조한다. 새 계보/사건의 `prior_record_id`는 앞선 기록의 참고일 뿐 동일 사건 연결이 아니다. `high_water_revision`은 기록에서 본 최대값을 보존하여 rollback이 뒤이은 저장으로 사라지지 않게 하며, `gap_possible`은 공백을 숨기지 않는다. 순번/revision만으로 전체 기록 무손실이나 교차 호스트 지연을 주장하지 않는다.

Journal은 scan에서 마지막 보호 상태 레코드1개만 추가 보유하고, 전체 원문은 기존 정책대로 파일에 보존한다. ViewModel은 scan 완료를 기다린 뒤 연결하며 실제 fsync 후 신호만 다음 연결의 저장 완료 근거로 사용한다. 미저장 큐나 잘못된 구조의 과거 메타데이터를 저장 완료 기록으로 사용하지 않는다. 같은 사건의 고유 ID는 내보내기에도 보존한다. 구형/더 오래된 다른 계보의 파일 전체를 임의로 같은 사건에 재분류하지 않는다. 내보내기는 새 객체의 명시적 필드/형식도 검토하고 미지원 추가 필드는 거부한다.

저장 worker는 enqueue 이후에 발생한 누락도 알고 있으므로 fsync 전에 보호 기록의 `protection_link.gap_possible`에 기존 저장 공백·비정상 종료·새 유실을 OR한다. 일반 이벤트가 `records_lost_before`를 먼저 소비해도 이후 보호 기록에서 누락 가능성을 숨기지 않는다. ViewModel은 검증된 commit에 실린 누락 정보만 실행 중 후속 사건 연결에 유지한다. 내보내기 manifest의 `contains_gap_annotations`는 상위 누락 필드와 보호 연결의 gap 플래그를 함께 집계하며, 단순 누락을 특정 공격이나 보호 해제로 해석하지 않는다.

재실행 scan은 상위 누락 주석뿐 아니라 저장된 `protection_link.gap_possible`도 읽는다. 마지막 보호 기록을 전달받은 ViewModel은 scan의 gap 인수와 검증된 기록의 gap을 함께 보존한다. 따라서 원래 누락 주석이 다른 이벤트에 있어도, 저장된 보호 기록만으로 이어지는 현재 연결에서 누락 가능성을 거짓으로 해제하지 않는다.

### 배포 health의 현재 게시 증거

session-v2의 로컬 `SESSION_PUBLICATION` 관찰에는 현재 확인된 `session_id`, `secoc_verified`, `state_confirmed`, `protection_confirmed`, `battery_state`, `battery_reason`을 추가한다. 보호 확인 전에는 세션 번호를 빈 값으로 두며, 진단/STATE가 일치하지 않은 게시를 health 성공으로 사용하지 않는다. 기존 CAN ID/DLC/바이트와 HAL API는 바꾸지 않는다. `tools/deployment/health.py`는 정확한 live IVI 실행본·실제 열고 있는 비공개 관찰 파일과 새 인증 BMS/NodeStatus/종류8을 읽기 전용 대조한다. 배터리 위험 상태의 유지와 프로그램 정상성은 별개다. 운영 입력과 소프트웨어 검증 경계는 [배포 안전 절차](development/playbooks/deployment-safety.md)를 따른다.


### 2026-11-16 — R02/R03/R05 구현 경계

R02 센서 추가 검사는 알려진 합성 프로필과 native 관측을 비교하는 상세 로그 도구로 우선 구현한다. 자유 조작 ADS/실제 배터리의 운영 임계나 CAN 공격 분류를 추가하지 않는다. R03은 IVI 동일 boot/monotonic 시계에서 식별 가능한 최초 공격 관찰부터 새 사건의 완전한 인증·의미 검증까지 평가하며 목표3초·화면 지연 별도를 유지한다. MAC/본문 인증과 사건 revision/관찰 순서 수용을 구분하고 의미 수용 플래그·완료 시각을 제품 관찰 로그에 남긴다. R05는 동일 QML/실행본 분리를 유지하고 데스크톱 소유권·협조 종료·PC stdin 수명의 실험 lease·단일 Wayland 화면·종료 후 기존 앱 복원을 연결한다. 관리되지 않은 앱이나 회수/복원 불명은 성공으로 처리하지 않는다. 계약 바이트는 변경하지 않는다. 정의/합격 기준은 [TC-PERF-003](TEST_PLAN.md#tc-perf-003-ids-탐지-응답-시간), 운영 절차는 [session campaign](development/playbooks/session-campaign.md)을 따른다.


### 2026-11-17 Replay 응답 계측 근거

관찰용 LOCAL_REJECTION_RECORD에 run_id·Linux boot clock_id·기록 시각 recorded_monotonic_ns를 추가한다. 기존 네트워크 RejectionRecord 바이트/인증과 UI 동작은 유지한다. 평가기는 같은 세션의 MAC 검증된 COUNTER_REPLAY 전체 참조·이전 원본/auth 관찰·이후 첫 반복auth를 대조해 식별 가능한 IVI 관찰 시작점을 정한다. SESSION_PUBLICATION에는 실제 적용된 BMS 원본/auth bytes·context·수신시각을 기록하고 새 세션에서 이 근거를 비운다. 이전 원본의 실제 인증/적용 완료가 첫 반복auth보다 앞서는지도 대조한다. 원본raw 송신 시각이나 PC/다른 노드의 시각을 대신 쓰지 않는다. 종료는 기존 새 IncidentStatus의 인증/의미 수용 완료다. 근거 누락·다른run/clock/context·원본 미관찰은 지연 성공이 아니다. [시험 기준](TEST_PLAN.md)·[진행](aidlc/changes/CHG-030/aidlc-state.md).
