# IVI M3 — CAN Parser, HAL, Service, 대시보드, SecOC Verifier

> **2026-09-09 보안 방식 선별 반영:** 기존 단계·과제에 [하단 추가 수행·인수 조건](#security-adoption)을 함께 적용한다. 구현·시험 완료 기록은 아니다.

> **예시 상태**: 코드·명령은 별도 검증 표시가 없으면 작성 골격·예정 절차다. 실행 전 생성할 파일·의존성·플랫폼을 확인한다. [공동 규약](../common/00_협업_규약.md)의 문서·예시 사용 규칙을 따른다.

> 상위 계획: [IVI.md](../../IVI.md) · 공동 절차: [00_협업_규약](../common/00_협업_규약.md) · 인계: [01_연계_의존성](../common/01_연계_의존성.md)
> 원본: `_archive/IVI.md` M3, `_archive/IVI_최종_실행계획서.md` §7

---


<a id="security-integration"></a>
## 현행 과제에 병합한 보안 수행·인수 조건 — IVI-SEC-01 인증 이벤트 생산·송신

이 절은 2026-09-09 보안 상세 계획을 기존 단계에 반영한 실행 조건이다. 초기 보안 보강 절과 함께 적용하며 제품 실행 완료 기록은 아니다. 상세 규칙은 [메시지·상태 규약](../../../docs/development/security/인증이벤트_메시지_상태규약.md)과 [송신·큐·실패 정책](../../../docs/development/security/인증이벤트_메시지_상태규약.md#planning-final)을 참조한다.

**선행 조건:** IVI M1의 플랫폼 가능성, 공동 인계의 채택 profile/schema·상세 전환 조건을 확인한다. 제품 연결은 필요한 계약 확정 후 진행하며 독립 모형/입력 검토는 먼저 할 수 있다.

**수행:** 기존 Q4 pending·검증 commit 후 결과를 생성하고 유한 producer 큐에 기록한다. STOPPED→CONNECTING→WAIT_CHALLENGE→PREPARE→STREAMING 및 BACKOFF/STOPPING을 규약 §10에 따라 구현할 과제로 편입한다. ready 경계의 epoch·cutoff·이전 worker 세대와 큐 폐기를 원자적으로 연결한다.

**실패 대응·인계:** 단일 writer의 ready→최초 status→event/status 순서를 보존한다. status는 FIFO 삽입 시 snapshot하고 제어 공간을 예약한다. overflow/expired/reset/offer를 중복 집계하지 않는다. verifier/UI에서 네트워크·재연결 대기를 하지 않는다. Q2-P01~P07 기대 결과와 producer 원장을 ECU에 인계한다.

**완료 확인:**

- [ ] 실제 verifier 결과·송신 순서·큐/종료·복구 증거를 인계하고 기존 인증/표시 회귀를 확인했다.
- [ ] 기존 공식 시험 결과와 추가 보조 시나리오의 실제 증거·미검증 사유를 구분했다.


## 1. 목적과 범위

**추가 승인 방향:** 세션 인증 메시지는 CAN으로 교환한다. IVI의 challenge 송신·상호 인증·ACK 확인·stale 연계가 새 과제다. [CAN 세션 인증 설계안](../../../docs/development/security/CAN_세션인증_설계안.md)의 구체적인 ID·키 파생·counter 소진·복구 시간은 검토 대기다. 현재 수신 전용 가정과 고정키 예시는 새 프로토콜의 완성 구현으로 사용하지 않는다. 승인 후 ECU·Python 참조와 동일한 상태 전이·교차 벡터를 검증한다.

CAN 프레임을 `VehicleData`로 파싱하고, **HAL → Service → UI** 흐름을 끝까지 연결한다. SecOC 검증을 붙이고 CI Stage 2~3을 추가한다.

| 항목 | 값 |
|---|---|
| 연결 요구사항 | FR-IVI-001~005, FR-CI-003~004 |
| 연결 시험 | TC-IVI-001~005, TC-IVI-008, TC-INT-002, TC-CI-003~004 |
| 산출물 | `can_parser`, `vehicle_hal_impl`, Service/Manager, `DashboardViewModel`, `SocGauge`, `secoc_verifier`, CI Stage 2~3 |
| 태그 | `v0.3.0` |
| **ECU 의존** | `secoc_verifier`는 [ECU M3](../ecu/M3_EKF_Failsafe_SecOC.md)의 테스트 벡터 인계 후 착수 |

### 주차별 작업

| 주차 | IVI 작업 | ECU 연계 |
|---|---|---|
| 1주차 | `can_parser`, HAL 수신 루프, TC-IVI-001~002 | `0x100`/`0x101` 샘플 |
| 2주차 | Binder/AIDL Service, Manager, TC-IVI-003~004 | 서비스 계약 리뷰 |
| 3주차 | Compose 대시보드, ViewModel, `SocGauge` | 실시간 값 범위 확인 |
| 4주차 | `secoc_verifier`, CI Stage 2~3 | **SecOC 테스트 벡터 검증** |

---

## 2. 선행조건과 현재 구현 상태

**선행조건**: [M2](M2_HALMock_PlanAB.md) 완료 — Plan A/B 결정, Mock, Repository.

| 대상 | 상태 |
|---|---|
| `ivi_platform/hal/*` | **전부 미구현** |
| `ivi_platform/service/*` | **전부 미구현** |
| `ivi_platform/app/*` | **전부 미구현** |
| ECU `secoc_module` | **구현됨** — 벡터 대조 가능 ([ECU M3](../ecu/M3_EKF_Failsafe_SecOC.md) 3.10) |
| CI Stage 2~3 | 미구현 (`docs/CICD_SPEC.md`에 명세만 존재) |

> **Plan B로 전환했다면**: HAL(C++) 계층인 3.1~3.2, 3.6은 그대로 쓴다. 3.3~3.5(Binder/AIDL/Compose)는 D-Bus + Qt/Flutter로 대체한다. CI(3.7~3.8)는 동일하다.

### 통합 시 해소한 충돌 — **파서 결함 2건 포함**

| 항목 | 세대A | 세대B | 채택 |
|---|---|---|---|
| **전류 디코딩** | `((d[4]<<8) \| d[5]) * 0.1f - 3276.8f` | `int16_be(&d[4]) * 0.1f` | **세대B**. 세대A 식은 **틀렸다** — ECU는 int16을 2의 보수로 싣는다. 세대A 코드로 `0x0014`(+2.0A)를 풀면 −3274.8이 나오고, 세대A 자신의 시험(`EXPECT_NEAR(current, 2.0f)`)도 실패한다 |
| **온도 디코딩** | `static_cast<int8_t>(data[6]) - 40` | `static_cast<int>(d[6]) - 40` | **세대B**. 세대A 식은 raw > 127에서 깨진다. 예: 90°C → raw 130 → `int8_t(130)` = −126 → −166 |
| SecOC 검증 순서 | MAC 먼저, 카운터 나중 | 카운터 먼저 | **카운터 먼저** — ICD §2.3의 절차 순서이고 ECU 구현과 같다 |
| 카운터 비교 | `counter <= last \|\| counter > last+100` | `last < counter && counter <= last+100` | **부호 없는 delta 방식** — ICD §2.4가 `0xFFFFFFFF → 0` 래핑을 규정하므로 단순 비교는 래핑에서 정상 프레임을 거부한다 ([ECU M3](../ecu/M3_EKF_Failsafe_SecOC.md) 3.8과 동일) |
| SOC 색상 경계 | `>=50 Green, >=20 Orange, else Red` | `<20 Red, <50 Orange, else Green` | **동일 로직**. 표현만 다르다 |
| ARM64 산출물 이름 | `build/ecu_node_a` | — | **`adaptive_ecu`** (실제 CMake 타겟) |
| `VehicleData` 필드 | ICD §3.1과 동일 | 별도 13필드 | **ICD §3.1** ([M1](M1_AOSP_Docker_CI.md) 3.6) |

---

## 3. 수행 절차

### 3.1 CAN Parser

`ivi_platform/hal/can_parser.h`:

```cpp
#pragma once
#include <cstdint>

// ICD §1.2 — 0x100 BMS_Status
struct BmsStatus {
    float soc;      // Byte0 x 0.5
    float soh;      // Byte1 x 0.5
    float voltage;  // uint16 BE x 0.01
    float current;  // int16  BE x 0.1  (양수=충전)
    int   temp;     // Byte6 - 40
};

// ICD §1.3 — 0x101 BMS_FailSafe
struct FailSafeEvent {
    uint8_t prevState;
    uint8_t newState;
    uint8_t reason;
    float   socAtEvent;   // Byte3 x 0.5
    int     tempAtEvent;  // Byte4 - 40
};

// ICD §1.4 — 0x102 / 0x103 SecOC
struct SecOcAuth {
    uint32_t truncatedMac;    // Byte0~3 BE
    uint32_t rollingCounter;  // Byte4~7 BE
};

// ICD §1.5 — 0x200 IDS_Alert
struct IdsAlert {
    uint8_t  attackType;      // 0=None,1=Fuzzy,2=Replay,3=Spoofing,4=Flooding
    float    anomalyScore;    // Byte1 x 0.01
    uint16_t suspectCanId;    // Byte2~3 BE
    uint32_t timestamp;       // Byte4~7 BE
};

class CanParser {
public:
    BmsStatus     parseBmsStatus(const uint8_t* d);
    FailSafeEvent parseFailSafe(const uint8_t* d);
    SecOcAuth     parseSecOcAuth(const uint8_t* d);
    IdsAlert      parseIdsAlert(const uint8_t* d);
};
```

`ivi_platform/hal/can_parser.cpp`:

```cpp
#include "can_parser.h"

namespace {
uint16_t u16be(const uint8_t* p) {
    return static_cast<uint16_t>((p[0] << 8) | p[1]);
}
int16_t i16be(const uint8_t* p) {
    return static_cast<int16_t>(u16be(p));      // 2의 보수 복원
}
uint32_t u32be(const uint8_t* p) {
    return (static_cast<uint32_t>(p[0]) << 24) | (static_cast<uint32_t>(p[1]) << 16) |
           (static_cast<uint32_t>(p[2]) << 8)  |  static_cast<uint32_t>(p[3]);
}
}

BmsStatus CanParser::parseBmsStatus(const uint8_t* d) {
    BmsStatus s{};
    s.soc     = d[0] * 0.5f;
    s.soh     = d[1] * 0.5f;
    s.voltage = u16be(&d[2]) * 0.01f;
    s.current = i16be(&d[4]) * 0.1f;            // int16 2의 보수
    s.temp    = static_cast<int>(d[6]) - 40;    // uint8 offset, int8_t 캐스트 금지
    return s;
}

FailSafeEvent CanParser::parseFailSafe(const uint8_t* d) {
    FailSafeEvent e{};
    e.prevState   = d[0];
    e.newState    = d[1];
    e.reason      = d[2];
    e.socAtEvent  = d[3] * 0.5f;
    e.tempAtEvent = static_cast<int>(d[4]) - 40;
    return e;
}

SecOcAuth CanParser::parseSecOcAuth(const uint8_t* d) {
    return SecOcAuth{ u32be(&d[0]), u32be(&d[4]) };
}

IdsAlert CanParser::parseIdsAlert(const uint8_t* d) {
    IdsAlert a{};
    a.attackType    = d[0];
    a.anomalyScore  = d[1] * 0.01f;
    a.suspectCanId  = u16be(&d[2]);
    a.timestamp     = u32be(&d[4]);
    return a;
}
```

> **디코딩 규칙 3가지를 외운다.** ① uint16/uint32는 BE 그대로 ② 전류는 `int16_t`로 캐스트해 2의 보수 복원 ③ 온도는 `int`로 넓힌 뒤 −40. 이 셋이 ECU 인코딩([ECU M2](../ecu/M2_CAN_CDD_Publisher.md) 3.4)의 정확한 역연산이다.

**단위 시험** `ivi_platform/test/test_can_parser.cpp`:

```cpp
#include <gtest/gtest.h>
#include "can_parser.h"

// TC-IVI-002-a: SOC=75%, SOH=95%, V=42.00V, I=-2.0A(방전), T=25C
TEST(CanParser, TC_IVI_002_a_BmsStatus) {
    uint8_t d[] = {150, 190, 0x10, 0x68, 0xFF, 0xEC, 65, 0x00};
    CanParser p;
    auto s = p.parseBmsStatus(d);
    EXPECT_FLOAT_EQ(s.soc, 75.0f);
    EXPECT_FLOAT_EQ(s.soh, 95.0f);
    EXPECT_NEAR(s.voltage, 42.00f, 0.01f);
    EXPECT_NEAR(s.current, -2.0f, 0.01f);      // 0xFFEC = -20 -> -2.0A
    EXPECT_EQ(s.temp, 25);
}

// 충전 방향과 고온을 함께 확인한다 (세대A 결함이 드러나는 케이스)
TEST(CanParser, TC_IVI_002_a_ChargingAndHighTemp) {
    uint8_t d[] = {150, 190, 0x10, 0x68, 0x00, 0x14, 130, 0x00};
    CanParser p;
    auto s = p.parseBmsStatus(d);
    EXPECT_NEAR(s.current, 2.0f, 0.01f);       // 0x0014 = +20 -> +2.0A
    EXPECT_EQ(s.temp, 90);                     // 130 - 40
}

// TC-IVI-002-b: NORMAL(0) -> WARNING(1), reason 0x01, SOC=75%, T=25C
TEST(CanParser, TC_IVI_002_b_FailSafe) {
    uint8_t d[] = {0x00, 0x01, 0x01, 150, 65, 0, 0, 0};
    CanParser p;
    auto e = p.parseFailSafe(d);
    EXPECT_EQ(e.prevState, 0);
    EXPECT_EQ(e.newState, 1);
    EXPECT_EQ(e.reason, 0x01);
    EXPECT_FLOAT_EQ(e.socAtEvent, 75.0f);
    EXPECT_EQ(e.tempAtEvent, 25);
}

// TC-IVI-002-c: Flooding(4), score 2.55, suspect 0x0100
TEST(CanParser, TC_IVI_002_c_IdsAlert) {
    uint8_t d[] = {0x04, 0xFF, 0x01, 0x00, 0x01, 0x02, 0x03, 0x04};
    CanParser p;
    auto a = p.parseIdsAlert(d);
    EXPECT_EQ(a.attackType, 4);
    EXPECT_NEAR(a.anomalyScore, 2.55f, 0.01f);
    EXPECT_EQ(a.suspectCanId, 0x0100);
    EXPECT_EQ(a.timestamp, 0x01020304u);
}
```

```bash
cmake -S ivi_platform -B ivi_platform/build -DCMAKE_BUILD_TYPE=Debug
cmake --build ivi_platform/build
ctest --test-dir ivi_platform/build -R test_can_parser --output-on-failure
```

- [ ] ECU에게 받은 **실제 샘플 프레임**으로도 같은 값이 나오는지 대조한다

### 3.2 Vehicle HAL 수신 루프

**미구현 과제.** 외부 API는 [ICD](../../../docs/ICD.md) §3의 HIDL 타입·서명을 그대로 구현한다. 내부 모델 `BmsStatus`·연결 상태와 외부 `VehicleData`를 구분하고, 내부 인터페이스에 외부 HIDL 이름을 재사용하지 않는다.

| 경계 | 구현 산출물 | 완료 조건 |
|---|---|---|
| SocketCAN → 내부 코어 | 수신·길이/DLC/ID 검사, parser, 인증 대기 상태 | 잘못된 프레임은 상태 변경 없이 폐기 |
| 내부 코어 → HIDL adapter | 기존 계약 시험은 11필드, 승인 목표 ICD §8 전환은 13필드 매핑, 3개 callback, getVehicleData·register/unregister의 bool 결과 | ICD 타입·필드·반환값과 1:1 대조, 등록·해제·스냅샷 시험 |
| 연결 상태 → UI | 내부 stale 상태와 복구 이벤트 | ICD §2.5와 §3 서명 사이의 stale 표현 충돌은 M1 게이트에서 승인된 방식으로 해소; 승인 전 외부 필드 추가 금지 |

**인증 수신 상태 전이 (설명용 의사코드, API 구현 아님):**

```text
수신 길이 / DLC=8 / 표준 데이터 프레임 / 허용 ID 검사
데이터 0x100 또는 0x101:
  인증 OFF 실험 모드 -> 유효 범위 검사 후 상태 확정 (명시적 비인증 모드 표시)
  인증 ON -> 원본 8바이트와 수신 시각을 해당 데이터 ID의 pending에 보류
인증 0x102 또는 0x103:
  각각 0x100 또는 0x101 pending을 찾음; 없는 경우 폐기
  원본 CAN ID와 원본 bytes로 MAC 및 카운터 규칙 검증
  실패 -> 상태·유효 수신시각·카운터를 갱신하지 않음, ICD 오류 처리
  성공 -> pending 소비, 카운터 commit, 의미 값 파싱·상태 commit
  상태 commit 후 등록 callback 스냅샷을 취하고 락 밖에서 통지
0x200 -> ICD의 인증 미적용 참고 경보로 파싱·전달 (안전 제어와 분리)
```

구현 과제:

1. 데이터 ID별 pending을 관리한다. 같은 ID의 새 원본이 오면 이전 미완성 원본의 교체·폐기를 계수하고 새 원본만 보류한다. 인증이 먼저 온 경우 다음 원본에 임의로 붙이지 않고 폐기한다. MAC이 맞지 않는 짝으로 상태를 확정하지 않는다.
2. pending 보관 시간·용량은 M3 시험 설정에 기록하고 만료·메모리 상한을 시험한다. 보관시간은 내부 자원 정책이며 CAN 주기·ICD timeout을 바꾸지 않는다. 정상 간격·지연·교차 ID·원본/인증 유실에서 손실과 동작을 기록한다.
3. SecOC 카운터·재동기화는 §3.6과 ICD 규칙을 사용한다. MAC 확인 전 카운터를 commit하지 않는다. 현행 고정키는 범위 밖 유효 MAC으로 재동기화하지 않는다. 수신 이력 소실 후 과거 MAC 수락 한계를 시험하고 인증 세션 복구는 별도 승인된 상세 계약으로 구현한다. 해석이 모호하면 계약 변경 게이트를 거치며 임의의 replay 허용 규칙을 만들지 않는다.
4. stale는 마지막 **유효한 상태 반영** 이후 300ms를 별도 타이머로 감시한다. 인증 실패 트래픽이 통신 정상 시간을 연장하지 못하게 한다. 유효 상태 1회로 복구한다. 수신 read가 멈춰도 감시가 동작해야 한다.
5. 종료 시 소켓 대기를 해제하고 수신·감시 스레드를 join한다. 콜백 재진입·해제·느린 수신자를 고려해 객체 수명과 작업 큐 상한을 검증한다.

**시험:** TC-IVI-001~002, TC-INT-002 및 TC-SEC-002/003 교차 시험에 두 인증 쌍의 정상·변조·누락·순서 역전·중복·카운터 래핑·재부팅·잘못된 DLC를 포함한다. 유효한 쌍만 한 번 전달하고 실패한 데이터·Fail-safe는 한 번도 전달하지 않는다는 콜백 계수를 검사한다. 인증 OFF 단독 원본 시험은 보안 합격 증거와 구분한다.

**센서 오류 별도 전달 — 사용자 I-2=B:** 통신 중단과 센서 데이터 무효를 구분한다. 오류 중에도 전송되는 마지막 유효 BMS를 새 센서 측정값으로 표시하지 않도록 품질 정보·값 결합·만료·복구를 계약 설계에 포함한다. 현재 stale 의미에 센서 오류를 조용히 합치지 않는다. Q-1=B에 따라 기존 `0x100` 예약 영역을 사용하는 방향이다. S-3=A로 비트 배치·HAL 필드 목표는 ICD §8에 승인됐으며 제품 동시 전환과 실행 인수는 대기다. 예제의 구형 11필드만으로 목표 완료를 표시하지 않는다. Q-2~4=A에 따라 마지막 정상값·오류 표시를 유지하고, ECU의 새 정상 입력 3회 복구 판정을 반영하며 마지막 확정 Fail-safe를 보존한다. IVI 수신 프레임 3개를 ADC 정상 입력 3회로 대신 세지 않는다. R-2=A에 따라 전체 통신 수신 기록과 마지막 인증·정상 품질 데이터 수신 기록을 분리한다. UI 시간은 후자의 수신 이후 경과시간이며 ECU 측정 시각으로 표시하지 않는다. 오류/복구 확인 중 프레임은 정상 수신 기준점을 갱신하지 않는다. 이력이 없는 재시작에서는 경과시간 확인 불가를 전달한다. R-1=A의 네 센서 상태·마지막 정상값 존재·미지원 상태 처리를 HAL부터 UI까지 일관되게 매핑하고, R-3=A의 최초 3회 확인은 ECU 판정을 사용한다. 현재 승인된 비트·HAL 필드명은 ICD §8을 따른다. 세션 상세 계약의 추가 변경은 별도 관문이다. 공동 규약의 Q 공통 정책을 HAL→Service→ViewModel→UI의 동일 관측 상태로 전달할 과제를 작성한다.

**IDS 사용자 확인 — I-4-2=A:** Service/Repository에서 수신 경보에 내부 이벤트 식별자를 부여해 현재 경보와 확인 요청을 연결한다. 확인 후에도 새로운 동일 유형 경보는 다시 표시한다. 확인 요청은 경보의 UI 상태만 바꾸고 Fail-safe/stale/센서 품질을 해제하지 않는다. 이전 이벤트의 확인과 새 이벤트 수신이 겹치는 경쟁을 시험한다.

### 3.3 Binder IPC — Service 계층 (Plan A)

FR-IVI-003·FR-IVI-004·FR-IVI-008을 완료하려면 아래 예시 클래스 외에 [M1](M1_AOSP_Docker_CI.md) §3.5의 빌드·등록 산출물을 완성해야 한다. HIDL adapter → 서비스 Binder stub → manager → Repository·StateFlow의 변환 위치와 스레드를 SDD에 기록한다. Parcelable 기본 생성자·CREATOR·직렬화 순서·AIDL 선언·소스셋을 컴파일로 확인한다. 아래 예시는 완성된 프레임워크 패치가 아니다.

- [ ] TC-IVI-003: 일반 테스트 앱에서 getSystemService("vehicle_data")로 manager를 얻고 snapshot 읽기·리스너 등록·해제 성공
- [ ] TC-IVI-004: 실제 Binder 경유 값·경보·전이를 확인; 프로세스 종료·재기동 시 리스너 정리·재연결 확인
- [ ] TC-IVI-008: Service 발행→StateFlow의 단조 시계 계측과 내부 sample 식별자를 연결 ([공동 측정](../common/02_통합시험.md) §6)
- [ ] 기기 재부팅 후 HAL 등록→서비스 시작→앱 연결까지 자동 복구, 권한 거부와 실패 로그 확인


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

`oneway`는 호출자를 블로킹하지 않는다. 100ms 주기 갱신에서 UI 스레드가 밀리지 않게 하려면 필요하다.

`VehicleDataParcel.java` (Parcelable) — 필드는 ICD §3.1 `VehicleData`와 맞춘다.

```java
public class VehicleDataParcel implements Parcelable {
    public float soc, soh, voltage, current, anomalyScore;
    public int temperature, failSafeState, failSafeReason, attackType;
    public boolean attackDetected;
    public long timestamp;

    protected VehicleDataParcel(Parcel in) {
        soc = in.readFloat();  soh = in.readFloat();
        voltage = in.readFloat();  current = in.readFloat();
        temperature = in.readInt();
        failSafeState = in.readInt();  failSafeReason = in.readInt();
        attackDetected = in.readBoolean();
        attackType = in.readInt();
        anomalyScore = in.readFloat();
        timestamp = in.readLong();
    }

    @Override public void writeToParcel(Parcel dest, int flags) {
        dest.writeFloat(soc);  dest.writeFloat(soh);
        dest.writeFloat(voltage);  dest.writeFloat(current);
        dest.writeInt(temperature);
        dest.writeInt(failSafeState);  dest.writeInt(failSafeReason);
        dest.writeBoolean(attackDetected);
        dest.writeInt(attackType);
        dest.writeFloat(anomalyScore);
        dest.writeLong(timestamp);
    }

    @Override public int describeContents() { return 0; }

    public static final Creator<VehicleDataParcel> CREATOR = new Creator<>() {
        @Override public VehicleDataParcel createFromParcel(Parcel in) { return new VehicleDataParcel(in); }
        @Override public VehicleDataParcel[] newArray(int size) { return new VehicleDataParcel[size]; }
    };
}
```

> **읽는 순서와 쓰는 순서가 정확히 같아야 한다.** 하나만 어긋나도 값이 조용히 밀린다. 필드를 추가할 때는 양쪽 끝에 함께 추가한다.

`VehicleDataService.java` — `RemoteCallbackList`가 죽은 리스너를 자동 정리한다.

```java
public class VehicleDataService extends IVehicleDataService.Stub {
    private static final String TAG = "VehicleDataService";
    private final RemoteCallbackList<IVehicleDataListener> listeners = new RemoteCallbackList<>();
    private VehicleDataParcel latestData = new VehicleDataParcel();

    @Override public VehicleDataParcel getLatestData() { return latestData; }

    @Override public void registerListener(IVehicleDataListener l) { listeners.register(l); }
    @Override public void unregisterListener(IVehicleDataListener l) { listeners.unregister(l); }

    /** HAL 콜백에서 호출 — 등록된 모든 리스너에 전파 */
    public void dispatchDataChanged(VehicleDataParcel data) {
        latestData = data;
        int n = listeners.beginBroadcast();
        for (int i = 0; i < n; i++) {
            try { listeners.getBroadcastItem(i).onDataChanged(data); }
            catch (RemoteException e) { Log.e(TAG, "dispatch failed", e); }
        }
        listeners.finishBroadcast();
    }

    public void dispatchSecurityAlert(int attackType, float score, int suspectCanId) { /* 동일 패턴 */ }
    public void dispatchFailSafeTransition(int prev, int next, int reason) { /* 동일 패턴 */ }
}
```

> `beginBroadcast()`와 `finishBroadcast()`는 반드시 짝을 맞춘다. 예외가 나도 `finishBroadcast()`가 실행되도록 `try/finally`를 검토한다.

`VehicleDataManager.java` — 앱이 `getSystemService("vehicle_data")`로 받는 클라이언트 API. 모든 호출을 `RemoteException` 방어로 감싼다.

```java
public class VehicleDataManager {
    private final IVehicleDataService service;
    public VehicleDataManager(IVehicleDataService service) { this.service = service; }

    public VehicleDataParcel getLatestData() {
        try { return service.getLatestData(); }
        catch (RemoteException e) { Log.e(TAG, "getLatestData failed", e); return new VehicleDataParcel(); }
    }
    public void registerListener(IVehicleDataListener l) { /* 동일 패턴 */ }
    public void unregisterListener(IVehicleDataListener l) { /* 동일 패턴 */ }
}
```

- [ ] **TC-IVI-003**: `context.getSystemService("vehicle_data")`가 `VehicleDataManager`를 반환한다
- [ ] **TC-IVI-004**: Mock에서 데이터를 주입하면 ViewModel의 StateFlow 값이 바뀐다

### 3.4 Compose 프로젝트와 ViewModel

`ivi_platform/app/build.gradle.kts` 핵심:

```kotlin
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    compileSdk = 33
    defaultConfig { minSdk = 33; targetSdk = 33 }
    buildFeatures { compose = true }
    composeOptions { kotlinCompilerExtensionVersion = "1.5.3" }
}

dependencies {
    implementation("androidx.compose.ui:ui:1.5.4")
    implementation("androidx.compose.material3:material3:1.1.2")
    implementation("androidx.compose.ui:ui-tooling-preview:1.5.4")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.6.2")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.6.2")

    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4:1.5.4")
    debugImplementation("androidx.compose.ui:ui-test-manifest:1.5.4")
}
```

`ivi_platform/app/DashboardViewModel.kt`:

```kotlin
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

**TC-IVI-008**: CAN 데이터가 StateFlow에 반영되기까지 ≤20ms. 측정 방법과 지점을 [M5](M5_성능_UI개선.md)에서 확정한다.

### 3.5 SocGauge

`ivi_platform/app/SocGauge.kt`:

```kotlin
@Composable
fun SocGauge(soc: Float, modifier: Modifier = Modifier) {
    val color = socColor(soc)

    Box(contentAlignment = Alignment.Center, modifier = modifier.size(200.dp)) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val strokeWidth = 20f
            val padding = strokeWidth / 2
            val arcSize = Size(size.width - strokeWidth, size.height - strokeWidth)

            drawArc(                                   // 배경 원호
                color = Color(0xFFE0E0E0),
                startAngle = 135f, sweepAngle = 270f, useCenter = false,
                topLeft = Offset(padding, padding), size = arcSize,
                style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
            )
            drawArc(                                   // SOC 원호
                color = color,
                startAngle = 135f,
                sweepAngle = 270f * (soc / 100f).coerceIn(0f, 1f),
                useCenter = false,
                topLeft = Offset(padding, padding), size = arcSize,
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

/** SOC >= 50 Green / >= 20 Orange / < 20 Red */
fun socColor(soc: Float): Color = when {
    soc >= 50f -> Color(0xFF4CAF50)
    soc >= 20f -> Color(0xFFFF9800)
    else       -> Color(0xFFF44336)
}
```

**색상 로직을 `socColor()` 순수 함수로 분리한 이유**: Composable 렌더링 없이 경계값을 시험할 수 있다.

`ivi_platform/app/test/SocGaugeTest.kt` — TC-IVI-005 경계 6케이스:

```kotlin
class SocGaugeTest {
    @Test fun `SOC 80 Green`()          { assertEquals(Color(0xFF4CAF50), socColor(80f)) }
    @Test fun `SOC 50 Green boundary`() { assertEquals(Color(0xFF4CAF50), socColor(50f)) }
    @Test fun `SOC 49 Orange`()         { assertEquals(Color(0xFFFF9800), socColor(49f)) }
    @Test fun `SOC 20 Orange boundary`(){ assertEquals(Color(0xFFFF9800), socColor(20f)) }
    @Test fun `SOC 19 Red`()            { assertEquals(Color(0xFFF44336), socColor(19f)) }
    @Test fun `SOC 5 Red`()             { assertEquals(Color(0xFFF44336), socColor(5f)) }
}
```

```bash
cd ivi_platform/app && ./gradlew test --tests "*.SocGaugeTest"
# 기대: 6 tests passed
```

### 3.6 SecOC Verifier

> **선행**: [ECU M3](../ecu/M3_EKF_Failsafe_SecOC.md) 3.10의 테스트 벡터를 받은 뒤 착수한다.

**사용자 선택 4=B 반영: 인증 세션 기반 자동 복구를 구현한다.** 기존의 “윈도우 밖이지만 MAC이 유효하면 lastCounter를 재설정”하는 코드 예시는 과거 프레임으로 기준을 되돌릴 수 있어 제거했다. 첫 메시지를 무조건 신뢰하는 초기화도 새 세션 인증을 대신할 수 없다.

상세 프로토콜은 사용자 I-1=B에 따라 후보 사전 검증 후 확정한다. [확인사항](../../../docs/development/governance/의사결정_기록.md#part2-confirmed) §4·§10의 상태 머신·유실/재생·대상 환경 검토 과제를 먼저 수행한다. 세션 인증 전 데이터 전달 금지, 이전 세션 재생 차단, 양측 전환 확인, pending·카운터 수명, 재시도와 실패 상태를 명시한다. 아래 기존 교차 검증만으로 새 프로토콜을 합격 처리하지 않는다. 계약 확정 후 양측 재부팅·동시 재부팅·교환 유실·이전 세션 재생 시험을 추가한다.

stale 전달은 사용자 선택 3=A에 따라 `VehicleData.bool stale` 추가를 목표로 한다. §3.2의 기존 11필드 매핑은 현재 계약 기준이며, 계약 변경 단계에서 HIDL·Parcelable 직렬화·Service·Mock·UI를 함께 갱신한다. 별도 stale 콜백을 추가하지 않는다.

**교차 검증**:

```bash
# ECU 쪽에서 만든 벡터로 시험한다 (더미 키)
ctest --test-dir ivi_platform/build -R test_secoc_verifier --output-on-failure
```

- [ ] 정상 MAC → true
- [ ] 1비트 변조 MAC → false, `ERR_HMAC_VERIFY_FAIL` 로그
- [ ] 같은 카운터 재사용 → false (Replay 차단)
- [ ] 현 고정키 계약의 래핑 시험과 새 세션 카운터 정책을 구분하고 상세 승인 후 기대값을 동기화
- [ ] 10회 연속 실패 → CRITICAL 로그 + 대시보드 "인증 오류" 표시

### 3.7 CI Stage 2 — ARM64 크로스 빌드

Stage 2: ARM64 크로스 빌드. ECU와 IVI host core의 소스·toolchain·산출물 경계를 기록하고 TC-CI-003으로 아키텍처를 확인한다. 전체 설정·산출물·실패 조건은 [CI 참조](ref_CI파이프라인_명령모음.md) §1만 유지한다. 이 단계에서는 해당 Stage를 구현하고 실행 증적을 인계한다.

### 3.8 CI Stage 3 — QEMU 시험 + 커버리지 게이트

Stage 3: QEMU 시험·커버리지. TC-CI-004, 시험 0개 실패, ARM64 실행 및 Fail-safe branch coverage를 확인한다. 전체 설정·산출물·실패 조건은 [CI 참조](ref_CI파이프라인_명령모음.md) §1만 유지한다. 이 단계에서는 해당 Stage를 구현하고 실행 증적을 인계한다.

## 4. 검증 명령과 합격 기준

```bash
cmake -S ivi_platform -B ivi_platform/build -DCMAKE_BUILD_TYPE=Debug
cmake --build ivi_platform/build
ctest --test-dir ivi_platform/build -R test_can_parser      --output-on-failure
ctest --test-dir ivi_platform/build -R test_secoc_verifier  --output-on-failure

cd ivi_platform/app && ./gradlew test
```

| TC | 합격 기준 |
|---|---|
| TC-IVI-001 | 인증 ON: 유효 0x100/0x102 쌍 반영 후 콜백 1회; OFF 단독 원본 시험은 별도 증적 |
| TC-IVI-002-a/b/c | `0x100`/`0x101`/`0x200` 파싱 정확 (충전·고온 케이스 포함) |
| TC-IVI-003 | `getSystemService("vehicle_data")` 접근 |
| TC-IVI-004 | Binder → StateFlow 갱신 |
| TC-IVI-005 | SOC 색상 경계 6케이스 |
| TC-IVI-008 | T2→T3 평균 ≤20ms AND P99 ≤50ms, 유효 100개 이상 |
| TC-INT-002 | ECU 벡터로 SecOC 검증 성공, 변조 MAC 거부 |
| TC-CI-003 | Stage 2 ARM64 artifact 생성 |
| TC-CI-004 | Stage 3 커버리지 게이트 통과 |
| 태그 | `v0.3.0` |

---

## 5. 실패 시 대응과 우회

**파싱 값이 ECU와 다름**
- 전류: `int16_t` 캐스트가 있는지 먼저 본다. 가장 흔한 원인이다
- 온도: `int8_t`로 캐스트하지 않았는지 본다. 90°C 이상에서만 드러나므로 저온 시험만으로는 못 잡는다
- 전압: BE 순서와 `×0.01`
- SOC/SOH: `×0.5`, ECU가 `lround` 반올림을 쓴다

**SecOC 검증이 항상 실패**
1. 키 파일이 32바이트인지 (`ls -l /etc/secoc/key.bin`)
2. 양 노드의 키가 같은 파일인지
3. HMAC 입력 조립이 14바이트(2+4+8)인지
4. CAN ID를 2바이트 BE로 넣었는지 (4바이트 아님)
5. `0x102` 검증에 쓰는 CAN ID는 **원본 `0x100`**이다. 인증 프레임 ID가 아니다

**재부팅 후 계속 거부됨**
- 현재 계약과 승인된 세션 목표의 차이를 확인한다. 첫 MAC 유효 메시지만으로 재부팅을 판정하거나 counter를 재설정하지 않는다. 세션 상세 미확정은 복구 인수 보류다.

**QEMU binfmt 등록 실패**
```bash
cat /proc/sys/fs/binfmt_misc/qemu-aarch64
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
```

**QEMU에서 CTest 타임아웃**
- QEMU 에뮬레이션은 네이티브보다 느리다. `--timeout 120` 이상으로 올린다
- 그래도 걸리면 어떤 시험이 오래 걸리는지 확인한다. 스레드 대기 시험이 원인인 경우가 많다

**ECU SecOC 벡터가 아직 없음**
- `secoc_verifier`를 뒤로 미루고 3.1~3.5를 먼저 끝낸다
- 자체 더미 키로 자기 일관성(sign→verify)만 먼저 확인해 둔다. 교차 검증은 벡터 수령 후에 한다

---

## 6. 완료 체크리스트

- [ ] `can_parser` 4종 파싱 구현, 전류·온도 디코딩 정확
- [ ] 파서 시험 통과 (충전/방전, 저온/고온 케이스 포함)
- [ ] HAL 수신 루프 동작, `ERR_*` 코드 로그, DLC 검사
- [ ] **`0x100`/`0x101`을 인증 검증 통과 후에만 전달** (보류 → 검증 → 확정)
- [ ] 짝 없는 인증 프레임·보류 만료 시 폐기, 콜백 미호출
- [ ] 비인증 실험 모드(`secoc_enabled_=false`) 분리 동작
- [ ] 수신 타임아웃(300ms) 시 `stale=true` 처리
- [ ] AIDL/Binder Service·Manager 동작 (TC-IVI-003~004)
- [ ] `DashboardViewModel` StateFlow 갱신 (TC-IVI-008)
- [ ] `SocGauge` 색상 경계 6케이스 통과 (TC-IVI-005)
- [ ] `secoc_verifier` ECU 벡터 교차 검증 통과
- [ ] 카운터 래핑·재동기화·에스컬레이션 동작 확인
- [ ] CI Stage 2 ARM64 artifact 생성
- [ ] CI Stage 3 QEMU 시험 + 커버리지 게이트 통과
- [ ] `v0.3.0` 태그 생성


### CAN 수신 작업 복구 요구의 별도 인수

[SRS](../../../docs/SRS.md)의 NFR-REL-002는 CAN 수신 스레드 이상 종료 시 자동 재시작과 최대 3회 재시도 후 실패 로그를 요구한다. BMS 계산 작업의 복구 시험으로 대체하지 않는다. 원천의 TC-BSW-007 연결과 그 TC 본문의 차이는 [공동 매핑](../common/01_연계_의존성.md) MAP-01에서 관리한다.

- [ ] 수신 작업의 소유자와 소켓·콜백 수명을 명세하고 정상 서비스 종료를 장애로 오인해 재시작하지 않도록 한다.
- [ ] 수신 작업 장애를 주입하여 회수→재시작→새 프레임 처리 재개를 확인한다. 스레드 생성만으로 성공 판정하지 않는다.
- [ ] 실제 재시도별 실패를 집계하고 최대 3회 이후 실패 로그를 확인한다. 작업 중복·콜백 중복·자원 누수가 없어야 한다.
- [ ] ECU의 Watchdog 감시 범위와 IVI 수신 스레드 수명 관리를 양측 설계에서 대조한다. BMS에 대해 승인한 snapshot 정책을 CAN 수신기에 자동 적용하지 않는다.
- [ ] 수신 재개만으로 세션/counter를 초기화하거나 센서 품질을 정상으로 바꾸지 않는다. 회수 불가·세션 영향의 구체 처리에 판단이 필요하면 인터뷰한다.

공식 TC의 연결/하위 시험은 계약·시험 검토 단계에서 확정한다. 현재는 누락 방지를 위한 수행 계획이며 구현·시험 통과가 아니다.


**S-3=A 후속 상태:** 이전 본문의 byte 7·HAL “검토 대기”는 [ICD §8](../../../docs/ICD.md#8-승인된-다음-전환-목표--s-3a-제품-반영-전)의 목표 계약 승인으로 갱신됐다. 목표를 다시 제안하는 단계는 끝났고 실제 양측 구현·직렬화·Mock·참조·시험 동시 전환이 남아 있다. 기존 코드 예시는 전환 전 상태이며 목표가 이미 구현됐다고 해석하지 않는다. S-2=A의 상태 통보가 실제 전류 제어를 뜻하지 않는다는 기준도 적용한다.


### S-10=A 복구 상태 수신

인증된 현재 위험 상태 동기화를 받아 현재 표시를 맞추며, ECU에만 남긴 과거 전이를 새 경고처럼 재생하지 않는다. 이미 해소된 WARNING과 현재 WARNING을 구분하고 센서 품질·통신 stale·IDS 사용자 확인 상태는 독립적으로 유지한다. 새 연결 준비 완료나 ECU 송신 로그만으로 상태 수신 성공이라 하지 않는다.

미수신·변조·중복·순서 경합과 초기 NORMAL을 [세션 설계안](../../../docs/development/security/CAN_세션인증_설계안.md) §14의 상태 표로 검증한다. 동기화 식별/필드·유실 복구 계약이 아직 미확정이므로 기존 0x101에 임의 특수값을 가정한 구현을 만들지 않는다. 단순 상태 동기화를 새로운 Fail-safe 전이 알림과 혼동하지 않는다.



### S-11=A·S-12=A 현재 상태 인수·인증 답장

전용 상태/인증 쌍을 검증해 현재 상태에 반영한 뒤 해당 메시지에 결합된 인증 receipt를 송신한다. 후보 형식과 미결 경계는 [세션 설계안](../../../docs/development/security/CAN_세션인증_설계안.md) §15~16을 따른다. 원본만 도착하거나 인증이 실패하면 상태 반영·receipt를 하지 않는다. READY와 상태 인수 완료를 구분한다.

중복/재시도 상태가 새 전이 알림을 반복하지 않는지, 구상태가 최신 상태를 덮어쓰지 않는지 검증한다. 세션·counter·payload가 다른 receipt를 섞지 않는다. HAL/Service의 현재 상태 갱신과 사건 알림 매핑은 상세 계약 전환 목록에 포함하며 실제 화면 표시 완료는 별도 통합 시험으로 관측한다. 새 형식은 아직 공식 ICD나 제품에 적용되지 않았다.



### S-13=A·S-14=A 복구 중 표시·확인

연결 복구 중에는 마지막 BMS 값과 통신 대기/단절 표시를 유지한다. 인증된 최신 현재 위험 상태는 받아 반영하고 해당 메시지에 결합된 receipt를 보낸다. 상태 receipt를 보냈다는 사실만으로 일반 BMS 수신이나 센서 정상 복귀를 선언하지 않는다. 최신 BMS 인증 쌍 수신 후 기존 통신 복귀 조건을 확인한다.

늦은 구상태·중복 상태·과거 receipt가 최신 표시를 되돌리거나 새 전이 알림을 반복하지 않는지 [세션 설계안](../../../docs/development/security/CAN_세션인증_설계안.md) §18로 검증한다. ECU의 내부 최신 상태는 메시지를 받기 전에 IVI가 알 수 없으므로 도착/검증/반영 시각과 판정 범위를 명시한다. 기존 IDS 사용자 확인·센서 품질 정책은 유지한다.



### S-15=A·S-16=A 인증 정렬과 수신 확인 과제

[세션 설계안](../../../docs/development/security/CAN_세션인증_설계안.md) §23에 따라 인증된 완성 쌍만 제한된 큐에서 counter 순서로 반영한다. 기한/용량/포화·누락 번호·중복·상충·세션 전환을 검증하고 미인증 입력이나 반복 조각으로 기한을 늘리지 않는다. 현재 상태는 실제 반영 후에 기존 후보 5조각 receipt로 확인한다. 이미 반영한 counter를 되돌리지 않는다.

CAN 수신 시각·인증 완료·큐 입장·반영·HAL·UI 시각을 구분한다. 정렬 후 반영 시각을 마지막 BMS 수신 시각으로 기록하지 않는다. 인증 전이/중복 입력으로 BMS stale을 해제하지 않으며 센서 품질과 통신 상태도 분리한다. 정렬에 따른 지연은 NFR-PERF-001/TC-PERF-001의 기존 전체 구간에 포함한다. 운영 대기 상한·용량과 위험 전이 포화 정책은 아직 미확정이며 시험용 값을 임의 적용하지 않는다.



### S-17=A·S-18=A 예약 큐·인증 불일치 대응

정렬 큐의 총 상한 안에 전이/현재 상태 동기화용 공간을 예약한다. 저장 공간을 예약해도 전역 counter 반영 순서는 유지한다. 예약 공간까지 포화되거나 아직 반영하지 않은 같은 counter에 서로 다른 인증된 ID/본문이 발견되면 해당 수신 세션 실패·미반영 큐 폐기·기존 표시/경고 보존·오류 표시·제한 재동기화를 수행한다. 단순 동일 중복은 기한을 연장하지 않고 무시한다.

[세션 설계안](../../../docs/development/security/CAN_세션인증_설계안.md) §25에 모형 16개 검사와 운영 한계를 기록했다. 실제 UI·진단 전달과 사유 부재 표현은 S-20 계약 후보를 검토한다. 시험용 6+2 공간이나 5 tick 대기는 공식 값이 아니다. 통신 오류를 ECU 로컬 위험 전이로 생성하지 않는다.


### S-19=A·S-20=A 수신·표시 연결

새 CONFIRM 후 구세션 BMS 중단을 정상 교환 대기로 처리하되 마지막 값·통신/센서 품질을 구분한다. READY와 최신 상태 receipt 전 일반 BMS 재개를 기대하지 않는다. 목표 HAL failSafeReason=0은 사유 정보 없음, 1~7은 기존 사유이며 별도 존재 필드는 추가하지 않는다. 상태 snapshot만으로 전이 콜백을 생성하거나 정상으로 추론하지 않는다. 세션 설계안 §26의 HAL 경계 시험과 공식 계약 동기화 후 구현한다.

### S-22=A와 운영 수치 근거

일반 BMS 구역만 차면 신규 BMS를 거부·진단하고 기존 대기 건과 위험 예약 공간을 보존한다. 해당 포화만으로 즉시 재연결하지 않으며 지속 누락의 counter/timeout 처리는 기존 정책을 따른다. 위험 구역 포화·인증 상충은 계속 세션 실패다. 상세 인수와 담당별 수치 측정·승인 기준은 [세션 설계안](../../../docs/development/security/CAN_세션인증_설계안.md) §28을 따른다. 실제 UI 시각·커널 송신 경계·장비 부하는 후속 검증이다.


<a id="ivi-sec-01"></a>
### IVI-SEC-01 — Plan 승계 과제

원문: [IVI.md](../../_archive/plan_20260908/IVI.md.txt)의 IVI-SEC-01. 실행 상태는 해당 역할의 진행 표·공동 인수 기록을 사용한다. 이 병합은 과제 실행 완료가 아니다.

선행·착수: [IVI-HAL-01](M2_HALMock_PlanAB.md#ivi-hal-01), ECU-SEC-01의 벡터

보존한 수행·인수 조건: 더미 키 정상/변조/키 불일치/Replay/초기값/wrap와 constant-time 비교를 교차 확인한다. 누락·순서·재시작 정책은 승인 계약대로 처리하고 거부 입력의 상태 미반영까지 COM-INT-01에 인계한다.

현재 기준 적용: 세션 상세/시간 상수는 현행 승인 관문 유지. 본문의 공식 FR/TC·승인 정책·실패 대응을 함께 적용한다.


<a id="ivi-app-01"></a>
### IVI-APP-01 — Plan 승계 과제

원문: [IVI.md](../../_archive/plan_20260908/IVI.md.txt)의 IVI-APP-01. 실행 상태는 해당 역할의 진행 표·공동 인수 기록을 사용한다. 이 병합은 과제 실행 완료가 아니다.

선행·착수: [IVI-HAL-01](M2_HALMock_PlanAB.md#ivi-hal-01), [IVI-SEC-01](M3_HAL_Service_대시보드.md#ivi-sec-01); Mock UI는 독립 가능

보존한 수행·인수 조건: getSystemService("vehicle_data") 접근·HAL→Binder→StateFlow와 필수 수치/경고를 검증한다. 앱 전용 서비스로 공식 경로를 대체하지 않는다. M4의 Fail-safe/IDS UI·정상/복귀·인증 실패 미갱신과 측정 지점을 연결한다.

현재 기준 적용: I-4/S/R 승인 표시·센서/통신 품질 정책 우선. 본문의 공식 FR/TC·승인 정책·실패 대응을 함께 적용한다.


<a id="security-adoption"></a>
## 보안 차용 보강 — pending 검증·인증 이벤트 생산

### 목적·선행조건

IVI-SEC-01·IVI-APP-01에 Q4=A와 Q2=B의 생산자 책임, N01·N03을 연결한다. 적용 ICD·센서 품질 버전·ECU 더미 벡터와 [공동 전달 계약 검토](../common/01_연계_의존성.md#security-adoption)를 확인한다. Node A IDS·기존 HAL/0x200 방향을 유지한다.

### 수행 절차

1. 기존 기본 수신의 최신 원본 보류·교체·만료·인증 선도착 폐기를 유지한다. raw 수신과 검증 완료·counter/상태 commit·callback 시점을 각각 기록한다. 다중 후보·선도착 인증 저장은 추가하지 않는다.
2. 정상 pair·raw만/auth만·변조·재생·교차 ID·중복·순서 역전·메모리 상한·만료의 기대값을 기존 정책으로 작성한다. 가짜 raw 때문에 정상 후보가 교체된 경우도 손실로 기록하며 정상 수락 100%를 추정하지 않는다.
3. 실패한 MAC이 counter를 소비하지 않는지, 미검증 값·품질이 서비스/UI에 반영되지 않는지 확인한다. 인증 전이·공격 프레임을 유효 BMS 수신이나 신규 센서 측정으로 계수하지 않는다.
4. Q2 생산 이벤트에는 결과·reason·대상 ID·부팅 식별·순번·발생 시각·집계/드롭 등 공동 설계가 정한 의미를 연결한다. 이벤트 생성·큐 삽입과 실제 전달을 구분하고, 느린 소비자가 verifier/commit을 막지 않도록 유한 큐·실패 진단을 준비한다.
5. 전달 수단·보호·wire/API 확정 전에는 더미 이벤트와 인터페이스 모형으로 준비할 수 있다. 생산자 로그만으로 실제 Node A 수신·IDS 반영을 완료 처리하지 않는다. 상세 계약 변경은 공동 관문을 따른다.
6. 일반 실행/재시작의 인증 ON과 키 접근 실패를 ECU-SEC-01·배포 담당과 확인한다. 실제 키·토큰을 이벤트·로그에 넣지 않는다.

### 검증

TC-SEC-002~004·TC-INT-002·TC-IVI-001의 기존 의미와 실패 시 값 미갱신을 유지한다. event 폭주·큐 포화·소비자 단절·재부팅·순번 재사용의 생산자 증거를 공동 통합에 인계한다. 동일 run·boot·sample 식별과 원본 수신 시각을 IVI-MEAS-01에 제공한다.

### 실패 대응

키 실패나 인증 오류로 정상 값을 새로 commit하지 않는다. 이벤트 채널 단절은 인증 결과가 정상이라는 뜻이 아니며 기존 SecOC·stale·센서 품질 처리를 유지한다. 세션 후보의 인증 완료 정렬 큐·복구 정책을 기본 pending 시험과 혼용하지 않는다.

### 완료 체크

- [ ] Q4 기본 정책의 정상·경계·폐기·정상 손실 로그 검증
- [ ] 키 오류·보안 시작/재시작 및 값·품질 원자적 반영 인계
- [ ] Q2 생산자 형식·큐·드롭·단절·실제 전달 상태와 대상 플랫폼 제한 기록
