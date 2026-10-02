# CHG-003 — IVI Plan B P1~P6 진행 상태

> 기준일: 2026-09-23
> 작업 브랜치: P1 `feat/ivi-plan-b`, P2 `fix/ivi-secoc-state`, P3 `feat/ivi-qt-dashboard`, P4 `feat/ivi-vcan-integration`
> 통합 대상: `develop`

이 문서는 Plan B 실행 단계 P1~P6의 실제 상태와 결과물 위치를 갱신하는 작업 원본이다. 계획의 정의와 순서는 `plan/IVI_PLAN_B_전환계획.md`, CAN/SecOC 계약은 `docs/ICD.md`가 우선한다.

P1에서 실제로 구현한 내용과 결과물별 설명은 [P1 구현 결과](construction/P1_구현_결과.md), 실행 명령과 시험 근거는 [P1 빌드·시험 증거](construction/build-and-test/evidence.md)에 정리한다.

P2의 pending·CAN·SecOC 정책과 결과물은 [P2 구현 결과](construction/P2_구현_결과.md), 실제 검증은 [P2 빌드·시험 증거](construction/build-and-test/P2_빌드_시험_증거.md)에 정리한다.

P3의 상태·Qt UI 결과물은 [P3 구현 결과](construction/P3_구현_결과.md), 실제 Qt 빌드·시험은 [P3 빌드·시험 증거](construction/build-and-test/P3_빌드_시험_증거.md)에 정리한다.

P4의 Linux vcan·T1~T4 결과물은 [P4 구현 결과](construction/P4_구현_결과.md), 실제 환경·수치·제한은 [P4 빌드·시험 증거](construction/build-and-test/P4_빌드_시험_증거.md)에 정리한다.

## 전체 상태

| 단계 | 상태 | 이번 결과 | 남은 완료 조건 |
|---|---|---|---|
| P0 전환 기록 | 완료 | CHG-002에서 Qt Plan B 계약·문서 기준 고정 | 구현 진행 시 문서 drift 재검토 |
| P1 선택 이관 | 완료 | CMake, core, SocketCAN, Qt/QML 기준 코드, 단위 시험 3개, 스크립트 추가. Debug/Release 각 3/3 통과 | Qt 앱의 실제 빌드·화면 실행은 P3, Linux SocketCAN 실행은 P4에서 검증 |
| P2 CAN·SecOC 수정 | 완료 | pending 100ms 만료·최신 원본 교체·orphan 폐기, 두 쌍 독립 처리, CAN frame validator, 수신 재시도. Debug/Release 각 6/6 통과 | Linux 실제 SocketCAN 동작은 P4 vcan에서 검증 |
| P3 상태·UI | 완료 | 300ms stale/last-good, IDS sequence 확인, reason 0x07, CRITICAL/SHUTDOWN overlay, Qt 6 앱·ViewModel 시험. Debug/Release 각 8/8 | sensorState wire 활성화는 ICD §8 동시 전환 과제. Linux 실제 화면·vcan은 P4~P5에서 검증 |
| P4 vcan·계측 | 완료 | Linux PF_CAN 정상/변조/replay/timeout, Qt Release 9/9, 100ms 1,000표본 T1→T4 평균 6.037ms·최대 10.827ms·누락 0 | 물리 display와 RPi4/can0는 P5에서 검증 |
| P5 물리 통합 | 미착수 | 없음 | RPi4 배포, `can0` 500 kbps, Node A IT-001~005, 재시작·링크 복구 |
| P6 문서·CI·데모 | 진행 기록 기반만 추가, 단계 미착수 | 본 CHG 기록과 P1 관련 문서 동기화 | Linux/Qt CI, 배포·운영 문서, 공식 TC 증거, 최종 데모·Release |

## P1 결과물

| 구분 | 위치 | 현재 역할 |
|---|---|---|
| 빌드 진입점 | `ivi_platform/CMakeLists.txt` | Qt 선택 빌드와 core/test 분리 |
| CAN 자료형·파서 | `ivi_platform/hal/can_types.h`, `can_parser.*` | ICD 5개 ID와 payload 해석 |
| SecOC | `ivi_platform/hal/secoc_verifier.*` | HMAC-SHA256-32와 counter 검증 |
| SocketCAN | `ivi_platform/hal/socketcan_receiver.*` | Linux SFF/DLC 8/허용 ID 수신 경계 |
| 상태 서비스 | `ivi_platform/service/vehicle_data_service.*` | pending 원본, 인증 후 snapshot 게시, 관찰자 알림 |
| Qt 앱 기준 | `ivi_platform/ui_qml/` | service→QObject→QML 조립과 기본 화면 |
| 단위 시험 | `ivi_platform/test/` | parser, verifier, 인증 게시 정책 회귀 시험 |
| 실행 보조 | `ivi_platform/scripts/` | 환경 점검, 벡터 송신, latency 요약 |
| 사용 안내 | `ivi_platform/README.md` | 빌드·실행·현재 제한 |
| P1 구현 결과 | `construction/P1_구현_결과.md` | 반입 근거, 구현 내용, 결과물, 검증과 남은 범위 |
| 실행 증거 | `construction/build-and-test/evidence.md` | 실제 명령, 환경, 결과, 미실행 범위 |

## P2 결과물

| 구분 | 위치 | 현재 역할 |
|---|---|---|
| CAN frame validator | `ivi_platform/hal/can_frame_validator.*` | DLC/SFF/flag/허용 ID 공통 검사 |
| 수신 retry 정책 | `ivi_platform/hal/receive_retry_policy.h` | 최대 3회 retry 예산과 정상 후 초기화 |
| 상태 서비스 보강 | `ivi_platform/service/vehicle_data_service.*` | pending 만료·교체·orphan·연속 실패 진단 |
| P2 회귀시험 | `ivi_platform/test/test_*` | frame/retry/SecOC/pending/교차 쌍 경계 6종 |
| P2 구현 결과 | `construction/P2_구현_결과.md` | 정책, 변경 파일, 검증과 남은 범위 |
| P2 실행 증거 | `construction/build-and-test/P2_빌드_시험_증거.md` | 실제 명령·환경·결과·미실행 범위 |

## P3 결과물

| 구분 | 위치 | 현재 역할 |
|---|---|---|
| 상태 서비스 | `ivi_platform/service/vehicle_data_service.*` | BMS 300ms stale, last-good age, IDS sequence 확인 |
| Qt ViewModel·화면 | `ivi_platform/ui_qml/` | queued property, 상태 banner, 전체 화면 경고, demo 재현 |
| P3 시험 | `ivi_platform/test/test_vehicle_data_service_state.cpp`, `test_dashboard_view_model.cpp` | stale/ack 경계와 Qt thread/property/지연 검증 |
| P3 구현 결과 | `construction/P3_구현_결과.md` | 상태 정책, UI, 결과물, 제한 |
| P3 실행 증거 | `construction/build-and-test/P3_빌드_시험_증거.md` | Qt Debug/Release, sanitizer, offscreen smoke |

## P4 결과물

| 구분 | 위치 | 현재 역할 |
|---|---|---|
| Linux 통합시험 | `ivi_platform/test/test_socketcan_receiver.cpp` | 실제 PF_CAN filter·종료·SecOC 실패 시나리오 |
| 단계 계측 | `ivi_platform/service/`, `ivi_platform/ui_qml/` | T1~T4 같은 단조 시계와 sample sequence 연결 |
| 자동화 | `ivi_platform/scripts/run_vcan_*.sh`, `measure_latency.py` | vcan 준비, 반복 송신, 누락·통계 판정 |
| P4 구현 결과 | `construction/P4_구현_결과.md` | 구현 경계, 결과물, 판정과 제한 |
| P4 실행 증거 | `construction/build-and-test/P4_빌드_시험_증거.md` | Linux 환경, 9/9, 1,000표본 수치와 원시 SHA-256 |

## 다음 실행 순서

1. P5는 RPi4와 실제 Node A 제공물로 물리 CAN 증거를 분리 기록한다.
2. P6에서 GitHub Actions, 배포 절차, 공식 TC 추적과 데모 자료를 마감한다.
