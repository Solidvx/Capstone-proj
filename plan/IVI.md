# IVI 실행 계획 — Node B Plan B

> 2026-10-04 실장비 증거 연결: [실행 상태·시험 추적](../docs/aidlc/changes/CHG-014/aidlc-state.md). 계획/설계의 존재와 시험 인수를 구분하며 INVALID·버전 편차·미수집 화면·비인증 0x200 경보의 제한을 적용한다. 아래 요구/계약 목표를 실험 결과에 맞춰 낮추지 않는다.


> **담당**: IVI / SocketCAN / Service / Qt Dashboard / CI·CD
> **플랫폼 결정**: Debian 13 ARM64 + C++17 + SocketCAN + Qt 6.8 Quick/QML
> **결정일**: 2026-09-22
> **상세 실행 순서**: [IVI Plan B 전환 및 구현 계획](IVI_PLAN_B_전환계획.md)
> **온보딩 안내**: [IVI Plan B 진행 상황과 프로젝트 구조](../docs/development/governance/IVI_Plan_B_진행상황_및_구조_안내.md)

Android AOSP, HIDL, Binder/AIDL, Jetpack Compose는 현재 제출 범위에서 제외한다. 과거 Android 상세 문서는 결정 이력으로 보존하고 현재 구현 지시로 사용하지 않는다. CAN ID, DLC, payload와 SecOC 규칙은 [ICD](../docs/ICD.md)를 따른다.

## 1. 목표

Node A가 전송한 BMS·Fail-safe·SecOC·IDS 프레임을 Node B에서 수신하고, 인증에 성공한 데이터만 Qt 대시보드에 표시한다.

```text
SocketCAN(can0/vcan0)
  -> SocketCanReceiver
  -> 원본/auth pending pair
  -> SecOcVerifier
  -> CanParser
  -> VehicleDataService
  -> DashboardViewModel(QObject)
  -> Qt Quick/QML Dashboard
```

### 완료 조건

- CAN ID `0x100`, `0x101`, `0x102`, `0x103`, `0x200`을 ICD대로 처리한다.
- `0x100/0x101`은 대응 인증 프레임 검증 성공 후에만 상태에 반영한다.
- 변조 MAC, replay, 범위 밖 counter에서 마지막 정상값을 유지한다.
- 300ms 동안 정상 인증 BMS 데이터가 없으면 stale을 표시한다.
- IDS 경고는 사용자 확인까지 유지하고 새로운 이벤트는 다시 표시한다.
- CRITICAL/SHUTDOWN을 전체 화면 경고로 표시한다.
- `vcan0` 자동 시험과 물리 `can0` 시험을 별도 증거로 기록한다.
- 실제 측정값과 목표값, 구현과 계획을 구분한다.

## 2. 현재 상태

확인 기준일은 2026-10-21이다. [통합 검증](../docs/aidlc/changes/CHG-019/evidence.md)·[팀원 인계](../docs/development/governance/팀원_인계_20261021.md)에서 현재 소스와 과거 시험을 구분한다.

| 영역 | 상태 | 근거 |
|---|---|---|
| Plan B | Debian13·C++17·Qt6.8 Quick | ADR-010, P0 결정 |
| 제품 코드 | P1~P4 구현·시험 기록 존재 | 인증 수신·서비스·QML, CHG-003/006 |
| 실험 타깃 | 별도 `ivi_dashboard_experiment`와 READY·수신 관측 코드 통합 | 제품 인증 OFF는 금지, 격리 실험만 명시 허용. CHG-014 원격 리뷰 증거 |
| 최신 통합 코어 시험 | 9개 통과·SocketCAN1개 skip | CHG-019 WSL. Qt6.4만 설치되어 Qt6.8 화면·실험 앱 빌드는 미실행 |
| 물리 CAN·RPi4 | P5 부분 인수·10월3~4일 결과 보존 | 정상·노브·성능·12조건 실험 로그 대조. 화면 캡처/Qt 경고 영향·전용변조/복구·장시간 인수 잔여 |
| GitHub Actions·ARM64 toolchain | 미구현 | P6/품질 후속 과제. 예정 명세를 현재 CI로 간주하지 않음 |

이전 구현은 인증 전에 원본 데이터를 게시하는 문제, counter wrap-around 오류, IDS 자동 해제 등 현행 계약과 맞지 않는 부분이 있었다. P1에서 안전한 기준선을 만들고 P2에서 pending·SecOC·CAN 수신 경계를 완성했다. P3에서 BMS 300ms stale, last-good, sequence 기반 IDS 확인, 전체 화면 Fail-safe 경고와 Qt 시험을 완성했다. sensorState wire는 ICD §8의 양측 동시 전환 전까지 미지원으로 표시한다.

## 3. 지켜야 할 계약

| 대상 | 원천 |
|---|---|
| CAN ID·방향·주기·DLC·payload | ICD §1 |
| HMAC 입력·counter·timeout | ICD §2 |
| Plan B C++ 서비스 경계 | ICD §3 |
| 기능 요구 | SRS FR-IVI-001~008 |
| 공식 합격 기준 | TEST_PLAN TC-IVI/TC-INT/TC-PERF |
| 플랫폼 결정 | ADR-010 |

`sensorState` byte 7 전환은 ICD §8의 별도 동시 전환 과제다. ECU·IVI·Python 벡터·시험이 같은 변경에서 전환되기 전에는 byte 7 값 `0`을 정상 센서 상태로 간주하지 않는다.

## 4. M1~M8 마일스톤

`M`은 프로젝트 전체의 Milestone이다. 단계 번호는 날짜가 아니라 선행 관계를 뜻한다.

| 단계 | Plan B 의미 | 핵심 산출물 | 연결 시험 |
|---|---|---|---|
| M1 | Linux/Qt 환경과 계약 기준 | Debian 13, CMake, Qt 6.8, OpenSSL, ICD/ADR 정합 | 환경 sanity, TC-CI-001~002 |
| M2 | 기존 코드 이관과 Mock 기반 빌드 | parser/verifier/service/Qt 기준 코드, clean build | TC-IVI-001~002, TC-CI-003 |
| M3 | 인증 수신 체인과 서비스 | pending pair, SecOC, snapshot, stale | TC-IVI-001~004·008, TC-INT-002 |
| M4 | Qt UI·배포·통합 | 대시보드, 경고, systemd/실행 스크립트, 물리 CAN | TC-IVI-005~007, TC-INT-001~004 |
| M5 | 성능·UI 개선 | T1~T4 계측, 병목 개선 | TC-PERF-001~003 |
| M6 | 문서·CI·Coverage | SDD/README/CICD, 정적 분석, coverage | TC-CI-001~006 |
| M7 | 안정성·교차 검토 | 장시간 실행, 복구, 누수, ICD 대조 | TC-PERF 및 TC-INT 재검증 |
| M8 | 데모·발표·제출 | 데모, 보고서, 재현 절차, Release | 최종 인수 |

## 5. P0~P6 실행 Phase

`P`는 Plan B 구현을 위한 IVI 내부 실행 Phase다. 상세 절차와 예상 시간은 [전환 계획](IVI_PLAN_B_전환계획.md)을 따른다.

| Phase | 의미 | 대응 M |
|---|---|---|
| P0 | Plan B 결정과 문서 계약 동기화 | M1~M2 |
| P1 | 이전 코드 선택 이관과 빌드 복구 | M2~M3 |
| P2 | CAN·SecOC 보안 상태 머신 수정 | M3 |
| P3 | 상태 관리와 Qt UI 완성 | M3~M4 |
| P4 | vcan 통합과 계측 | M4~M5 |
| P5 | Raspberry Pi 배포와 물리 CAN | M4~M7 |
| P6 | 문서·CI·데모 마감 | M6~M8 |

## 6. 다음 실행 순서

1. P5에서 RPi4 Debian 13과 물리 `can0`을 검증한다.
2. P6에서 CI, 성능 결과, 최종 문서와 데모를 마감한다.

## 7. ECU 인계물

IVI 작업에 필요한 ECU 제공물은 다음과 같다.

- 적용 ICD 버전과 CAN 예제 프레임
- 명시적 더미 키 기반 정상·실패 SecOC 벡터
- BMS 100ms 주기와 Fail-safe 발생 조건
- IDS `0x200` 예제와 공격 유형 의미
- 물리 통합에 사용할 ECU commit, 실행 명령과 환경

파일 수신만으로 인수를 끝내지 않는다. IVI가 같은 입력으로 parser·verifier·UI 결과를 재현해야 한다.

## 8. 진행 기록

| 단계 | 상태 | 현재 증거 | 남은 일 |
|---|---|---|---|
| P0 | 완료 | Plan B 계약·요구·설계·시험 문서 동기화 | 구현 시 drift 재검토 |
| P1 | 완료 | `ivi_platform/` 선택 이관, Debug/Release core 시험 각 3/3 | Qt 실빌드는 P3에서 완료 |
| P2 | 완료 | pending·SecOC·frame·retry 정책, Debug/Release 각 6/6. [결과](../docs/aidlc/changes/CHG-003/construction/P2_구현_결과.md) | Linux 실제 SocketCAN은 P4에서 검증 |
| P3 | 완료 | stale·last-good·IDS ack·전체 화면 경고, Qt Debug/Release 각 8/8. [결과](../docs/aidlc/changes/CHG-003/construction/P3_구현_결과.md) | sensorState wire 전환은 별도 계약 변경, Linux 화면은 P4~P5 |
| P4 | 완료 | [Linux vcan·T1~T4 결과](../docs/aidlc/changes/CHG-003/construction/P4_구현_결과.md): Release 9/9, 1,000표본 평균 6.037ms·최대 10.827ms·누락 0 | 물리 display/can0는 P5 |
| P5 | 진행 중 | RPi4 Debian 13 빌드, `can0` preflight, SecOC 키, DSI·터치·Wayland 창 실행. [결과](../docs/aidlc/changes/CHG-003/construction/P5_구현_결과.md) | 재부팅 자동 시작, Node A 실제 프레임·SecOC·복구·지연 검증 |
| P6 | 기록 기반 준비 | [CHG-003](../docs/aidlc/changes/CHG-003/aidlc-state.md) 상태·증거 문서 | CI·최종 증거·데모 |

## SecOC 보완 브랜치 인계

`feat/ivi-secoc-hardening`: P2 기반 무수신 만료·실패 진단 전달·stale와 인증 오류 표시 보완. [재현/증거](../docs/aidlc/changes/CHG-006/audit.md). P3 전체 경고 UX, 실 CAN 통합과 새 세션 인증은 별도 범위다.
