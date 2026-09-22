> **문서명**: Software Design Document — Node B (IVI)
> **버전**: v2.0 | **작성일**: 2026-03-15 | **최종 수정**: 2026-09-22 | **작성자**: 팀원B
> **참조**: ICD v1.5, SRS v1.6 (FR-IVI-*), ADR-010, IVI Plan B 전환 계획

# 1. 목적과 현재 기준선

이 문서는 Node B를 Ubuntu 22.04, C++17, SocketCAN, Qt Quick/QML로 구현하기 위한 설계 기준이다. CAN ID·DLC·바이트 순서·SecOC MAC/rolling counter 계약은 [ICD](ICD.md)를 그대로 따른다.

2026-09-22 현재 `ivi_platform/`에는 안내 README만 있고 제품 소스·빌드·시험 결과는 없다. 아래 트리와 클래스는 P1 이후 만들 목표이며 구현 완료를 뜻하지 않는다. Android AOSP, HIDL, Binder/AIDL, Jetpack Compose 설계는 과거 결정 기록으로만 유지한다.

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
├── app/main.cpp
├── hal/
│   ├── socketcan_receiver.{h,cpp}
│   ├── can_parser.{h,cpp}
│   └── secoc_verifier.{h,cpp}
├── service/vehicle_data_service.{h,cpp}
├── ui_qml/
│   ├── dashboard_view_model.{h,cpp}
│   └── qml/
│       ├── Main.qml
│       ├── SocGauge.qml
│       ├── AlertBanner.qml
│       └── FailSafeOverlay.qml
└── test/
    ├── test_can_parser.cpp
    ├── test_secoc_verifier.cpp
    ├── test_vehicle_data_service.cpp
    └── tst_dashboard.qml
```

# 3. 모듈 설계

## 3.1. SocketCanReceiver

- `PF_CAN/SOCK_RAW` 소켓을 지정 인터페이스(`vcan0` 기본, 배포 시 `can0`)에 바인드한다.
- CAN 필터는 `0x100`, `0x101`, `0x102`, `0x103`, `0x200`만 허용한다.
- Classic CAN DLC 8만 상위로 전달하고 RTR·ERR·확장 ID 및 잘못된 길이는 거부한다.
- 수신 대기는 `poll()`과 종료용 `eventfd` 또는 유한 timeout으로 깨울 수 있게 한다. 다른 스레드의 `close()`만으로 blocking read 종료를 가정하지 않는다.
- 일시 오류는 제한된 backoff로 재시도하고 초기화 실패와 지속 오류를 호출자에게 전달한다.

## 3.2. SecOcVerifier와 프레임 결합

인증 대상 원본/인증 프레임 쌍은 `(0x100, 0x102)`, `(0x101, 0x103)`이다. 원본 프레임을 ID별 pending 슬롯에 저장하고 해당 인증 프레임이 도착했을 때 다음 순서로 처리한다.

1. DLC와 ID 쌍을 확인한다.
2. `delta = receivedCounter - lastAcceptedCounter`를 `uint32_t` 모듈러 연산으로 계산한다.
3. 초기 동기화 정책 또는 `1 <= delta <= 100`을 만족하는지 확인한다.
4. ICD의 입력 바이트 순서로 HMAC-SHA256을 계산하고 앞 4바이트를 constant-time 비교한다.
5. 성공한 경우에만 counter를 갱신하고 원본을 파싱·게시한다.

MAC 실패, counter 거부, 쌍 timeout은 데이터를 게시하지 않으며 마지막 정상 snapshot을 덮어쓰지 않는다. 실패한 MAC은 수신 counter를 소비하지 않는다. `0x200` IDS 경보는 현 계약상 SecOC 비대상이다.

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
- timeout 시 마지막 정상 수치를 보존하면서 `stale=true`로 전환한다.
- Fail-safe CRITICAL/SHUTDOWN과 IDS 경보는 별도 이벤트로 전달한다.
- IDS 경보 확인(ack)은 표시 상태만 닫으며 stale·센서 오류·Fail-safe를 해제하지 않는다.
- `sensorState`의 실제 wire 반영은 ICD §8의 양 노드 동시 전환 이후에만 유효하다. 전환 전에는 미지원으로 표시한다.

## 3.5. DashboardViewModel

`DashboardViewModel`은 `QObject`와 `Q_PROPERTY`로 snapshot과 경보 상태를 QML에 제공한다. CAN 수신 스레드에서 UI 객체를 직접 수정하지 않고 queued signal/slot으로 GUI 스레드에 전달한다. 한 snapshot의 필드는 한 번에 교체해 서로 다른 시점의 값이 섞이지 않게 한다.

## 3.6. Qt Quick/QML 화면

- 초기 상태: 값 대신 `--`와 연결 대기 상태를 표시한다.
- SOC 색상: 50% 이상 초록, 20% 이상 50% 미만 주황, 20% 미만 빨강.
- stale 또는 sensor 오류: 마지막 값임을 명시하고 정상 색상만으로 오인되지 않게 한다.
- CRITICAL/SHUTDOWN: 전체 화면 경고를 표시한다.
- IDS 경보: 공격 유형을 즉시 완전히 표시하고 사용자가 확인할 때까지 유지한다. 새 경보는 확인 경쟁 중에도 소실되지 않는다.

# 4. 실행·스레드·배포

프로세스는 수신 worker 한 개와 Qt GUI thread로 시작한다. 종료 순서는 신규 이벤트 차단, 수신 대기 해제, worker join, SocketCAN 자원 해제, UI 종료다. 구성값은 CAN 인터페이스, 키 파일 경로, timeout이며 비밀키는 저장소에 넣지 않는다.

개발 환경은 `vcan0`, 실제 RPi4는 `can0`을 사용한다. 배포 전 Node A와 bitrate 500 kbps, CAN ID, 키, counter 초기화 정책을 함께 확인한다.

# 5. 검증 전략

- 순수 단위 시험: parser 경계값, signed 변환, HMAC 정상/변조, counter replay/wrap.
- 서비스 시험: 인증 전 미게시, last-good/stale, Fail-safe·IDS 이벤트, ack 경쟁.
- Qt 시험: Q_PROPERTY 갱신, SOC 색상, 전체 화면 경고, IDS 유지/재표시.
- vcan 통합: `0x100→0x102`, `0x101→0x103`, `0x200` 순서와 변조·replay·timeout.
- 물리 통합: RPi4 `can0`, Node A 송신, T1 수신부터 T4 QML 렌더까지 1,000회 계측.

세부 합격 기준은 [TEST_PLAN](TEST_PLAN.md)을 따른다. 소스가 생기기 전까지 모든 시험 항목은 계획 상태다.

# 6. 변경 이력

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| v1.3 | 2026-09-09 | Android/HIDL 기반 설계 보완 |
| v2.0 | 2026-09-22 | ADR-010 활성화에 따라 Ubuntu/C++17/SocketCAN/Qt Quick 구조로 전환 |
