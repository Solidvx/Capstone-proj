> **계약 프로파일 경계(2026-11-11)**: §1~2의 고정키·인증 ID별 counter/래핑은 `legacy-v1` 실험 재현 프로파일이다. 사용자 승인된 제품 전환 계약 `session-v2`는 [인증 세션](ICD-CAN-SESSION.md) 및 [CAN 진단](ICD-CAN-DIAGNOSTIC.md)을 함께 따른다. 기존0x100~103/200 배치는 유지하지만 키/counter 의미는 비호환이다. 프로파일을 명시하고 자동 downgrade하지 않는다. 제품 양쪽 연결은 [CHG-029](aidlc/changes/CHG-029/aidlc-state.md)에서 진행 중이며 승인만으로 배포/물리 인수가 완료된 것이 아니다. §3은 현재 C++ Service API이며 확장 연동도 같은 변경 단위로 진행한다. §8 sensorState byte7을 이번에 임의 활성화하지 않고 입력 준비/오류는 인증 NodeStatus로 전달한다.

> **선택형 단셀 실측(2026-11-17)**: 승인된 [CAN 진단 종류9](ICD-CAN-DIAGNOSTIC.md)는 기존0x100~105/200의 배치를 보존하고0x302로 실측값·미산정·품질을 전달한다. `physical` 모드는 종류9로 표시하며0x100/102에 미산정값을 채우지 않는다. 아래100ms 가상 BMS 계약과 구분한다. 현재 C++ Service API는 `VehicleSnapshot::physical_measurement` 및 채널별 `physical_valid`를 확장하며 기존 소비자는 새 모드의 정상 BMS로 간주하지 않는다. 기존 checkpoint/가상 보호를 실셀에 자동 적용하지 않는다.

> **문서명**: Interface Control Document (ICD)  
> **버전**: v1.7 (session-v2 전환 포함) | **작성일**: 2026-03-01 | **최종 수정**: 2026-11-11
> **작성자**: 팀원A + 팀원B (공동 — 인터페이스 확정 후 각자 독립 개발 시작)  
> **참조**: SRS v1.6, ADR-002 (SecOC 설계), ADR-009 (IDS 위치), ADR-010 (IVI Plan B), ADR-012 (분리 프레임)
> **변경 관리**: 수정 시 GitHub Issue (`interface-change` 라벨) + 양측 합의 후 PR 머지

---

# 1. CAN 메시지 규격

## 1.1. 메시지 ID 할당 테이블

| CAN ID | 방향 | 메시지명 | 송신 주기 | DLC | 설명 |
| --- | --- | --- | --- | --- | --- |
| 0x100 | Node A → Node B | BMS_Status | 100ms | 8 | BMS 상태 데이터 (SOC, SOH, 전압, 전류, 온도) |
| 0x101 | Node A → Node B | BMS_FailSafe | 이벤트 기반 | 8 | Fail-safe 상태 전이 이벤트 |
| 0x102 | Node A → Node B | BMS_SecOC | 100ms | 8 | SecOC HMAC 인증 데이터 (0x100에 대한 MAC) |
| 0x103 | Node A → Node B | FailSafe_SecOC | 이벤트 기반 | 8 | SecOC HMAC 인증 데이터 (0x101에 대한 MAC) |
| 0x200 | **Node A → Node B** *(ADR-009)* | IDS_Alert | 이벤트 기반 | 8 | ML IDS 탐지 결과 (공격 유형, 이상 점수). IDS는 Node A에서 실행하며 0x200을 Node B로 전송함 (ADR-009 참조) |

## 1.2. 0x100 — BMS_Status 데이터 레이아웃

| Byte | Bit Range | 필드명 | 타입 | 스케일링 | 단위 | 유효 범위 | 설명 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | [7:0] | SOC | uint8 | × 0.5 | % | 0.0 ~ 100.0 | 배터리 잔량 (EKF 추정값). 예: raw=150 → 75.0% |
| 1 | [7:0] | SOH | uint8 | × 0.5 | % | 0.0 ~ 100.0 | 배터리 건강도. 예: raw=190 → 95.0% |
| 2-3 | [15:0] | Voltage | uint16 (BE) | × 0.01 | V | 0.00 ~ 655.35 | 팩 전압. 예: raw=4200 → 42.00V |
| 4-5 | [15:0] | Current | int16 (BE) | × 0.1 | A | -3276.8 ~ 3276.7 | 충방전 전류. 양수=충전, 음수=방전 |
| 6 | [7:0] | Temperature | uint8 | × 1 | °C | -40 ~ 125 | 셀 온도. offset=+40 적용 (raw 0 = -40°C, raw 165 = 125°C) |
| 7 | [7:0] | Reserved | uint8 | — | — | — | 예약 (향후 확장용, 0x00으로 채움) |

## 1.3. 0x101 — BMS_FailSafe 데이터 레이아웃

| Byte | Bit Range | 필드명 | 타입 | 설명 |
| --- | --- | --- | --- | --- |
| 0 | [7:0] | PrevState | uint8 | 이전 Fail-safe 상태 (0=NORMAL, 1=WARNING, 2=CRITICAL, 3=SHUTDOWN) |
| 1 | [7:0] | NewState | uint8 | 새로운 Fail-safe 상태 (동일 코드) |
| 2 | [7:0] | Reason | uint8 | 전이 사유 코드 (아래 표 참조) |
| 3 | [7:0] | SOC_AtEvent | uint8 | 전이 시점 SOC (× 0.5, %) |
| 4 | [7:0] | Temp_AtEvent | uint8 | 전이 시점 온도 (offset=+40) |
| 5-7 | — | Reserved | — | 예약 (0x00) |

**Fail-safe 전이 사유 코드:**

| Reason Code | 의미 | 전이 방향 |
| --- | --- | --- |
| 0x01 | SOC < 20% | NORMAL → WARNING; 과열 해제 후 SHUTDOWN → WARNING |
| 0x02 | SOC < 5% 또는 보존된 저전압 CRITICAL | WARNING → CRITICAL; 과열 해제 후 SHUTDOWN → CRITICAL |
| 0x03 | 온도 > 55°C | NORMAL → WARNING |
| 0x04 | 온도 > 60°C | WARNING/CRITICAL → SHUTDOWN |
| 0x05 | SOC ≥ 20% && 온도 ≤ 55°C | WARNING → NORMAL; 아래 연속 확인 조건 충족 시 SHUTDOWN → NORMAL |
| 0x06 | 수동 리셋 명령 수신 | SHUTDOWN → NORMAL (복귀) |
| 0x07 | Watchdog 태스크 재시작 3회 연속 실패 | NORMAL → WARNING |

**2026-11-11 승인된 과열 복귀 정책:** SHUTDOWN은 프로그램 재시작이나 실제 전원 차단 명령이 아니다. ECU 실행·온도 감시·상태 전송을 유지한다. 유효 온도가 55°C 이하로 5초 연속 유지되면 과열 보호를 해제한다. 무효 입력/입력 오류, 200ms 초과 관찰 공백, 시각 역행, 55°C 초과는 확인 구간을 다시 시작한다. 재시작 전 냉각 확인 시간은 복원하지 않는다. 55°C·5초는 가상 배터리 정책이며 산업 공통 기준이 아니다.

해제 시 저전압 CRITICAL 이력이 있거나 관찰 SOC<5%이면 CRITICAL/0x02, 그 외 SOC<20%이면 WARNING/0x01, 나머지는 NORMAL/0x05로 전이한다. 저전압 CRITICAL은 과열 해제만으로 지우지 않는다. 현재 상태 통보의 reason도 목적 상태와 일치한다. 기존 CAN ID·방향·DLC·배치·인증 입력은 변경하지 않으며 기존 사유 코드의 허용 출발 상태를 확장한다. IVI는 인증된 전이를 받아 표시하고 UI 자체 타이머로 위험 상태를 해제하지 않는다.

> `0x07`은 배터리 상태가 아니라 **소프트웨어 감시 실패**에 의한 전이다 (SRS FR-BSW-006, NFR-REL-001/002). Node B는 이 코드를 SOC·온도 사유와 구분하여 표시한다. 이미 WARNING 이상 상태이면 전이가 발생하지 않으므로 `0x101`도 송신하지 않는다.

## 1.4. 0x102 / 0x103 — SecOC HMAC 인증 데이터 레이아웃

| Byte | Bit Range | 필드명 | 타입 | 설명 |
| --- | --- | --- | --- | --- |
| 0-3 | [31:0] | TruncatedMAC | uint32 (BE) | HMAC-SHA256 출력의 앞 4바이트 |
| 4-7 | [31:0] | RollingCounter | uint32 (BE) | 인증 CAN ID별 메시지 순번(§2.4). 해당 인증 메시지 전송 시 +1 증가, 0xFFFFFFFF 도달 시 0으로 래핑 |

**HMAC 계산 입력 구성:**

```
HMAC_Input = CAN_ID(2B, BE) || RollingCounter(4B, BE) || Payload(8B)
MAC = HMAC-SHA256(SharedKey, HMAC_Input)
TruncatedMAC = MAC[0:4]  (앞 4바이트)
```

**키 관리:**

- SharedKey: 256-bit (32바이트) 사전 공유 키
- 저장 위치: 각 Node의 `/etc/secoc/key.bin` (파일 퍼미션 400, `root:root` 소유)
- 프로젝트 범위 내 키 교환은 수동(사전 복사), 추후 OTA 확장 가능

## 1.5. 0x200 — IDS_Alert 데이터 레이아웃

| Byte | Bit Range | 필드명 | 타입 | 설명 |
| --- | --- | --- | --- | --- |
| 0 | [7:0] | AttackType | uint8 | 탐지된 공격 유형 (0=None, 1=Fuzzy, 2=Replay, 3=Spoofing, 4=Flooding) |
| 1 | [7:0] | AnomalyScore | uint8 | 이상 점수 (× 0.01, 범위 0.00 ~ 2.55) |
| 2-3 | [15:0] | SuspectCANID | uint16 (BE) | 의심 CAN ID (해당 없으면 0xFFFF) |
| 4-7 | [31:0] | Timestamp | uint32 (BE) | Unix epoch 초 단위 (하위 32비트) |

---

# 2. SecOC 통신 프로토콜 규격

## 2.1. 인증 대상 메시지

| 원본 CAN ID | 인증 CAN ID | 비고 |
| --- | --- | --- |
| 0x100 (BMS_Status) | 0x102 (BMS_SecOC) | 100ms 주기 동기 전송 |
| 0x101 (BMS_FailSafe) | 0x103 (FailSafe_SecOC) | 이벤트 발생 시 원본 직후 전송 |
| 0x200 (IDS_Alert) | 인증 미적용 | IDS 경보는 참조용, 안전 제어 비관여 |

## 2.2. 송신 절차 (Node A)

1. BMS 컴포넌트가 Payload 8바이트 생성
2. 해당 인증 CAN ID(0x102)의 RollingCounter를 현재값으로 읽고 +1 증가
3. `HMAC_Input = CAN_ID || RollingCounter || Payload` 구성
4. `HMAC-SHA256(SharedKey, HMAC_Input)` 계산, 앞 4바이트 추출
5. 원본 메시지(0x100) CAN 전송
6. 인증 메시지(0x102) CAN 전송 (TruncatedMAC + RollingCounter)

## 2.3. 수신 검증 절차 (Node B)

1. 원본 메시지(0x100)와 인증 메시지(0x102) 수신
2. 같은 원본 CAN ID의 마지막 인증 성공 counter가 있으면 `delta = (received - last) mod 2^32`를 계산한다. `1 <= delta <= 100`이 아니면 **폐기**한다. 이력이 없는 첫 수신은 아래 MAC 검증을 수행한다(재부팅 한계는 §2.5.3).
3. `HMAC_Input = CAN_ID || RollingCounter || Payload` 재구성
4. `HMAC-SHA256(SharedKey, HMAC_Input)` 재계산, 앞 4바이트 추출
5. `hmac.compare_digest(수신MAC, 재계산MAC)` 비교 → 불일치 시 **폐기** (타이밍 공격 방지)
6. 모든 검증 성공 시에만 해당 원본 CAN ID의 마지막 인증 성공 counter를 갱신하고 Node B Service로 데이터를 전달한다. 실패하면 counter와 기존 전달 데이터를 유지한다.

## 2.4. 롤링 카운터 규칙

- 초기값: 0
- 범위: 인증 CAN ID별로 독립이다. `0x102`(원본 `0x100`)와 `0x103`(원본 `0x101`)은 counter를 공유하지 않으며, 수신 측의 허용 윈도우와 마지막 인증 성공 이력도 원본 CAN ID별로 관리한다. 드문 이벤트 메시지(`0x101`)의 counter가 주기 메시지(`0x100`) 송신 수만큼 건너뛰어 윈도우를 벗어나지 않게 하기 위함이다.
- 증가: 해당 인증 CAN ID의 인증 메시지 전송 시 +1
- 오버플로우: 0xFFFFFFFF → 0x00000000 (래핑)
- 수신 허용 윈도우: §2.3의 uint32 차이 규칙을 적용한다. +100은 허용하며 +101은 거부한다. MAC 검증 실패 시 counter를 소비하지 않는다.
- 첫 수신: 마지막 인증 성공 이력이 없을 때 MAC 성공 후 기준값을 설정한다. 첫 MAC 성공은 새 부팅·새 세션의 증거가 아니다.
- 범위 밖 MAC 유효 메시지로 자동 재동기화하지 않는다. 재부팅과 목표 세션 전환은 §2.5.3을 따른다.

## 2.5. CAN 통신 타임아웃 및 오류 복구 절차

### 2.5.1. 수신 타임아웃

| 항목 | 규격 |
| --- | --- |
| 대상 메시지 | 0x100 (BMS_Status), 100ms 주기 |
| 타임아웃 판정 | 3주기 연속 미수신 (300ms) |
| Node B 동작 | `onVehicleDataChanged()` 콜백에 `stale=true` 플래그 전달, 대시보드에 "통신 끊김" 표시 |
| Node B 복구 | 유효 메시지 1회 수신 시 자동 복구, `stale=false` |

### 2.5.2. SecOC 검증 연속 실패 에스컬레이션

| 연속 실패 횟수 | 동작 |
| --- | --- |
| 1~3회 | `ERR_HMAC_VERIFY_FAIL` 로그 기록, 해당 메시지만 폐기 |
| 4~9회 | 로그 레벨 WARNING 상향, IDS_Alert와 별개로 Node B 내부 보안 이벤트 기록 |
| 10회 이상 | SecOC 키 동기화 오류 의심, Node B 구조화 로그 CRITICAL 항목 + 대시보드에 "인증 오류" 경고 표시 |

### 2.5.3. 롤링 카운터 재동기화

| 상황 | 절차 |
| --- | --- |
| Node A 재부팅 | 송신 counter는 0부터 시작한다. 수신기는 §2.3의 기존 윈도우로 판정하며 범위 밖 메시지는 MAC이 유효해도 거부한다. 현행 고정키 방식에는 인증된 자동 복구가 없다. 일반 수신 오류를 이유로 수신 counter 이력을 지우지 않는다. |
| Node B 재부팅 | 마지막 counter 이력이 없으면 첫 MAC 성공 메시지로 기준값을 설정한다. 과거 유효 메시지도 수락할 수 있으므로 replay 방어 완료나 새 세션 인증으로 판정하지 않는다. |
| 양측 동시 재부팅 | 송신 counter=0, 수신 이력 없음. 과거 counter=0의 유효 메시지도 수락할 수 있으며 새 부팅을 증명하지 못한다. |

현행 고정키의 uint32 래핑은 유지하지만 last=0xFFFFFFFF 이후 0 수신은 동일 키의 정상 래핑과 재부팅을 구별하지 못한다. 위 정정만으로 재부팅·전체 counter 순환의 replay 위험을 해결했다고 주장하지 않는다.

**승인된 다음 방향:** 인증된 세션을 통해 자동 복구한다. [세션 설계안](development/security/CAN_세션인증_설계안.md)의 상세 wire·키 파생·운영 수치는 사전 검증과 별도 승인 후 양측에 동시 적용한다. 새 세션 없이 고정키 counter를 초기화하는 것으로 대체하지 않는다. 이번 정정은 CAN ID·방향·DLC·바이트 배치·HMAC 입력 순서·Node B Service API를 변경하지 않는다.

2026-09-09 사용자 승인: [현행 계약 정정안](development/security/CAN_세션인증_설계안.md#secoc-amendment). 이전 §2.3 단순 비교·§2.4 경계 설명·§2.5.3 범위 밖 MAC 재동기화는 이 절로 대체한다.

---

# 3. Node B C++ Service API 명세

이 절은 ADR-010으로 활성화한 Plan B의 프로세스 내부 C++ 계약이다. CAN wire 계약인 §1~2를 변경하지 않는다. 첫 제출은 한 프로세스이며 D-Bus/gRPC 직렬화는 후속 범위다.

## 3.1. 데이터와 observer

```cpp
struct VehicleData {
    double socPercent;
    double sohPercent;
    double voltageV;
    double currentA;
    double temperatureC;
    std::uint8_t failSafeState;
    std::uint8_t failSafeReason;
    std::uint8_t sensorState;  // §8 동시 전환 전에는 미지원
    bool stale;
    bool valid;
    std::uint64_t receivedMonotonicNs;
};

struct SecurityAlert {
    std::uint8_t attackType;
    double anomalyScore;
    std::uint16_t suspectCanId;
    std::uint32_t sourceTimestamp;
};

class IVehicleDataObserver {
public:
    virtual ~IVehicleDataObserver() = default;
    virtual void onVehicleDataChanged(const VehicleData&) = 0;
    virtual void onSecurityAlert(const SecurityAlert&) = 0;
    virtual void onFailSafeTransition(std::uint8_t previous,
                                      std::uint8_t current,
                                      std::uint8_t reason) = 0;
};
```

## 3.2. 서비스 동작

| API/항목 | 사양 |
| --- | --- |
| `latest()` | mutex로 보호한 최신 일관 snapshot의 복사본 반환 |
| `registerObserver()` / `unregisterObserver()` | 중복 등록을 막고 수명 종료 후 호출하지 않음 |
| 데이터 게시 | 0x100/0x101은 대응 SecOC 성공 뒤에만 게시. 0x200은 현 계약상 인증 비대상 |
| 최초 상태 | 정상 인증 전 `valid=false`; 0을 실제 SOC로 표시하지 않음 |
| timeout | 300ms 후 last-good를 유지하며 `stale=true`; 유효 메시지 수신 시 복구 |
| UI 전달 | `DashboardViewModel`이 observer를 구현하고 Qt queued signal로 GUI thread에 전달 |
| 오류 로그 | stderr/journald 또는 Qt logging category에 구조화해 기록 |

`sensorState`는 §8이 Node A/Node B에 같은 변경 단위로 반영되기 전까지 wire에서 읽지 않는다. byte 7을 독자적으로 활성화하지 않는다.

## 3.3. 에러 코드

| 코드 | 이름 | 설명 |
| --- | --- | --- |
| 0 | OK | 정상 |
| -1 | ERR_CAN_INIT_FAIL | SocketCAN 인터페이스 초기화 실패 |
| -2 | ERR_CAN_READ_FAIL | CAN 프레임 읽기 오류 |
| -3 | ERR_HMAC_VERIFY_FAIL | HMAC 인증 실패 |
| -4 | ERR_COUNTER_MISMATCH | rolling counter 윈도우 거부 |
| -5 | ERR_INVALID_FRAME | ID/DLC/RTR/ERR 또는 payload 형식 오류 |
| -6 | ERR_UNKNOWN_CAN_ID | 등록되지 않은 CAN ID |

# 4. ara::com 서비스 인터페이스 명세

## 4.1. 서비스 토픽 정의

| 토픽명 | 데이터 타입 | 발행 조건 | 발행 주기 |
| --- | --- | --- | --- |
| `/bms/status` | `BmsStatusData` | BMS 주기적 계산 완료 시 | 100ms |
| `/bms/failsafe` | `FailSafeEvent` | Fail-safe 상태 전이 발생 시 | 이벤트 기반 |

## 4.2. 데이터 타입 정의

```cpp
struct BmsStatusData {
    float soc;          // EKF 추정 SOC (%)
    float soh;          // SOH (%)
    float voltage;      // 팩 전압 (V)
    float current;      // 충방전 전류 (A)
    int8_t temperature; // 셀 온도 (°C)
    uint32_t timestamp; // 계산 시점 (ms since boot)
};

struct FailSafeEvent {
    uint8_t prevState;  // 이전 상태
    uint8_t newState;   // 새 상태
    uint8_t reason;     // 전이 사유 코드
    float socAtEvent;   // 전이 시점 SOC
    int8_t tempAtEvent; // 전이 시점 온도
    uint32_t timestamp; // 전이 시점 (ms since boot)
};
```

---

# 5. 인터페이스 변경 관리 절차

1. 변경 요청자가 GitHub Issue 생성 (라벨: `interface-change`)
2. Issue에 변경 사유, 영향 범위, 변경 전/후 비교 기술
3. 상대 팀원이 48시간 이내 리뷰 코멘트
4. 양측 합의 후 `docs/ICD.md` 수정 PR 생성
5. PR 머지 후 관련 코드 수정 작업 각자 진행
6. 변경 이력은 ICD 문서 하단 Changelog 섹션에 기록

---

# 6. SecOC 통신 시퀀스 다이어그램

## 6.1. 정상 인증 플로우 (Node A → Node B)

```
Node A (ECU)                    CAN 버스                Node B (IVI Service)
     │                              │                         │
     │  BmsComponent.update()       │                         │
     │  ├─ EKF → SOC = 75.0%        │                         │
     │  └─ Payload 8B 생성          │                         │
     │                              │                         │
     │  SecOcModule.sign(0x100,     │                         │
     │       payload, counter++)    │                         │
     │  → TruncatedMAC (4B)         │                         │
     │                              │                         │
     │── 0x100 (BMS 데이터 8B) ────▶│                         │
     │                              │── CAN read ────────────▶│
     │── 0x102 (MAC 4B + CTR 4B) ──▶│                         │
     │                              │── CAN read ────────────▶│
     │                              │                         │
     │                              │   ① Counter 윈도우 검사  │
     │                              │   Δ=(rx-last) mod 2^32  │
     │                              │     1 <= Δ <= 100       │
     │                              │   이력 없으면 ② (§2.3)  │
     │                              │   ② HMAC 재계산          │
     │                              │   ③ compare_digest()    │
     │                              │                         │
     │                              │   [검증 성공]            │
     │                              │   VehicleData 구성       │
     │                              │── onVehicleDataChanged ─▶│ Service → App
     │                              │                         │
     │                              │   [검증 실패]            │
     │                              │   ERR_HMAC_VERIFY_FAIL   │
     │                              │   폐기 + 구조화 로그 기록      │
```

## 6.2. Replay 공격 차단 플로우

```
공격자 노드                     CAN 버스                Node B (IVI Service)
     │                              │                         │
     │ (사전 캡처: Counter=42,       │                         │
     │  MAC=0xABCD1234)             │                         │
     │                              │                         │
     │── 0x100 (캡처된 원본) ───────▶│                         │
     │── 0x102 (Counter=42, ───────▶│                         │
     │          MAC=0xABCD1234)     │── CAN read ────────────▶│
     │                              │                         │
     │                              │   ① Counter 검사:        │
     │                              │     last_counter = 55   │
     │                              │     received = 42       │
     │                              │     42 <= 55 → ❌ 실패   │
     │                              │   ERR_COUNTER_MISMATCH  │
     │                              │   즉시 폐기              │
```

## 6.3. IDS 공격 탐지 → Node B 경보 플로우

```
공격자 노드    CAN 버스    [Node A] ML IDS       [Node B] Service     Qt App
     │            │               │                    │               │
     │─ 공격 ────▶│               │                    │               │
     │            │─ 트래픽 수집 ─▶│                    │               │
     │            │               │ 1초 슬라이딩 윈도우  │               │
     │            │               │ 7차원 특징 추출      │               │
     │            │               │ decision_function() │               │
     │            │               │ < threshold → 공격  │               │
     │            │               │ 유형 추론 (규칙)     │               │
     │            │◀─ 0x200 경보 ──│                    │               │
     │            │    AttackType  │                    │               │
     │            │    AnomalyScore│                    │               │
     │            │               │                    │─ CAN read ───▶│
     │            │               │                    │  0x200 파싱   │
     │            │               │                    │─ onSecurity ─▶│
     │            │               │                    │    Alert()    │
     │            │               │                    │               │─ AlertBanner
     │            │               │                    │               │  애니메이션
```

---

# 7. 변경 이력 (Changelog)

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| v1.0 | 2026-03-01 | 초안 작성 — CAN ID 할당, 0x100/0x101/0x102/0x103/0x200 레이아웃 확정 | 팀원A, 팀원B |
| v1.0 | 2026-03-01 | SecOC HMAC 프로토콜, 롤링 카운터 규칙 확정 | 팀원A |
| v1.0 | 2026-03-01 | Vehicle HAL HIDL 인터페이스 VehicleData 구조체 확정 | 팀원B |
| v1.0 | 2026-03-01 | ara::com 서비스 토픽 `/bms/status`, `/bms/failsafe` 확정 | 팀원A |
| v1.1 | 2026-03-15 | ADR-009 반영 — IDS 실행 위치 Node A 확정, 0x200 방향 명시 | 팀원A, 팀원B |
| v1.2 | 2026-03-15 | 시퀀스 다이어그램 추가 (§6 SecOC 정상/Replay/IDS 탐지 플로우) | 팀원A |
| v1.3 | 2026-05-09 | §2.5 CAN 통신 타임아웃 및 오류 복구 절차 추가 (수신 타임아웃, SecOC 연속 실패 에스컬레이션, 롤링 카운터 재동기화) | 팀원A, 팀원B |
| v1.3 | 2026-05-09 | §1.4 키 파일 퍼미션 600→400 수정 (TARA TS-007 보안 권고 반영, 읽기 전용) | 팀원A |
| v1.5 | 2026-09-22 | §3 Node B API를 HIDL에서 C++ Service/Qt 전달 계약으로 전환; §1~2 wire 계약 유지 | 팀원B |
| v1.4 | 2026-09-06 | §1.3 Fail-safe 전이 사유 코드 `0x07`(Watchdog 재시작 3회 실패) 신설. SRS FR-BSW-006이 필수로 요구하는 전이를 표현할 코드가 없어 추가 | 팀원A, 팀원B |
| v1.6 | 2026-10-03 | §1.4·§2.2~2.4 RollingCounter 범위를 인증 CAN ID별 독립으로 명시(0x102·0x103 비공유, 수신 윈도우·이력은 원본 CAN ID별). ECU·Python 참조는 단일 counter, IVI·IDS는 ID별 판정이던 차이를 해소. CAN ID·DLC·바이트 배치·HMAC 입력 변경 없음 | 팀원A |

# 8. 승인된 다음 전환 목표 — S-3=A (제품 반영 전)

2026-09-06 사용자 S-3=A는 아래 byte 7 상태표와 Node B 데이터 모델 확장을 목표 계약으로 승인했다. **§1~3은 현행 형식, 본 절은 승인된 다음 전환 목표**다. 현 소스가 이미 이 확장을 지원한다는 뜻이 아니다. 한 실행에서 두 형식을 섞지 않으며 실제 전환 시 양측 구현·Python 참조·Mock·직렬화·시험을 같은 변경 단위로 동기화하고 버전을 확정한다. 이 계획 작업에서 제품 코드는 변경하지 않았다.

| 항목 | 기존 계약 | 승인된 목표 |
|---|---|---|
| 0x100 byte 7 | Reserved=0x00 | 아래 SensorState 번호 |
| VehicleData | 기존 11필드 | 기존 필드 뒤 `bool stale`, `uint8_t sensorState` 추가 |
| 데이터 콜백 | 기존 onVehicleDataChanged | 유지. 값·stale·sensorState를 같은 snapshot으로 전달 |
| CAN ID·DLC·HMAC 입력 | §1~2 | 이 확장으로 바꾸지 않음. 품질 바이트도 기존 8바이트 payload 전체와 함께 인증 |

| sensorState / byte 7 | 의미 | 값 인수 |
|---|---|---|
| 0 | 이전 형식 또는 상태 확인 불가 | 정상 측정으로 인수하지 않음 |
| 1 | 최초 측정 준비 중 | 측정값 없음·판정 대기 |
| 2 | 정상 입력 인수 완료 | 정상 데이터 사용 |
| 3 | 센서 오류, 이전 정상값 없음 | 측정값 없음·센서 오류 |
| 4 | 센서 오류, 이전 정상값 있음 | 마지막 정상값·센서 오류 |
| 5 | 복구 확인 중, 이전 정상값 없음 | 측정값 없음·복구 확인 중 |
| 6 | 복구 확인 중, 이전 정상값 있음 | 마지막 정상값·복구 확인 중 |
| 7~255 | 미지원 코드 | 상태 확인 불가; 정상으로 간주하지 않음 |

최초 새 정상 입력 3회 전에는 1, 오류는 이전 정상값 유무에 따라 3/4, 오류 후 새 정상 입력 1~2회는 5/6, 연속 3회에서 2다. 중간 오류는 횟수를 초기화한다. 같은 ADC 변환 재조회·CAN 재송신은 새 입력으로 세지 않는다. 정상 측정이 없는 코드의 숫자 바이트는 측정값으로 사용하지 않는다. 이전 정상값 존재를 뜻하는 별도 boolean은 중복 추가하지 않는다.

정상 데이터 수신 기록은 인증·품질 확인 후 갱신한다. 오류/복구/미지원 상태로 마지막 정상 수신 경과시간을 갱신하지 않는다. UI 표시는 `마지막 정상 데이터 수신 후 …`이며 실제 측정 시각으로 표현하지 않는다. 통신 timeout의 stale과 sensorState는 독립이다. 센서 상태 정상만으로 이전 Fail-safe 판정 유무나 계산 공백 후 SOC 정확도를 추론하지 않는다.

이 byte 7 확장은 세션 인증 후보의 승인과 별개다. 세션 nonce·ID·키 파생·counter 변경은 [세션 후보](development/security/CAN_세션인증_설계안.md)의 사전 검증·확정 절차를 계속 따른다. 혼합 버전에서 0을 새 정상 상태로 처리하지 않는다.

### 2026-11-14 보호 사건 연속성 확장 승인

ECU→IVI0x302의 종류8 ProtectionStatus(56B/24프레임)를 승인했다. 정확한 본문/단계/복원·연결 규칙은 [CAN 진단 계약](ICD-CAN-DIAGNOSTIC.md#8-protectionstatus--ecuivi56b24프레임)을 따른다. 기존 ID/DLC·종류1~7·HMAC 입력/최대 조립 상한은 유지한다. 신규 codec/문서 변경과 실제 ECU checkpoint/발행·IVI 영속 연결·물리 인수 완료를 구분한다.
