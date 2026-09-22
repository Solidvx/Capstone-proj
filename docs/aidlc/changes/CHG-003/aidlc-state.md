# CHG-003 — IVI Plan B P1~P6 진행 상태

> 기준일: 2026-09-22
> 작업 브랜치: `feat/ivi-plan-b`
> 통합 대상: `develop`

이 문서는 Plan B 실행 단계 P1~P6의 실제 상태와 결과물 위치를 갱신하는 작업 원본이다. 계획의 정의와 순서는 `plan/IVI_PLAN_B_전환계획.md`, CAN/SecOC 계약은 `docs/ICD.md`가 우선한다.

## 전체 상태

| 단계 | 상태 | 이번 결과 | 남은 완료 조건 |
|---|---|---|---|
| P0 전환 기록 | 완료 | CHG-002에서 Qt Plan B 계약·문서 기준 고정 | 구현 진행 시 문서 drift 재검토 |
| P1 선택 이관 | 완료 | CMake, core, SocketCAN, Qt/QML 기준 코드, 단위 시험 3개, 스크립트 추가. Debug/Release 각 3/3 통과 | Qt 앱의 실제 빌드·화면 실행은 P3, Linux SocketCAN 실행은 P4에서 검증 |
| P2 CAN·SecOC 수정 | 일부 기반 반영, 단계 미완료 | 인증 후 게시, BMS/Fail-safe 상태 분리, unsigned counter `1..100`/wrap, constant-time MAC, IDS 상태 유지 구현 | pending timeout·덮어쓰기 정책, 수신 오류 복구, 잘못된 DLC 및 교차 순서 전체 시험 |
| P3 상태·UI | 기준 화면만 준비, 단계 미착수 | QObject view model과 WAITING/LIVE·수치·Fail-safe·IDS 표시 QML 추가 | 300ms stale timer, sensorState 전환, IDS 확인/재발생, 전체 화면 경고, Qt 시험 |
| P4 vcan·계측 | 준비물 일부 추가, 단계 미착수 | 인증된 테스트 벡터 송신기와 latency 요약기 추가 | Linux `vcan0` 자동 시나리오, T1~T4 수집, 손실·표본·p95/p99 증거 |
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
| 실행 증거 | `construction/build-and-test/evidence.md` | 실제 명령, 환경, 결과, 미실행 범위 |

## 다음 실행 순서

1. P2에서 pending 만료·덮어쓰기 정책과 SocketCAN 오류 복구를 코드와 시험으로 고정한다.
2. P3에서 monotonic clock 기반 stale 전환, IDS 확인, CRITICAL/SHUTDOWN 화면과 Qt 시험을 완성한다.
3. P4는 Linux에서 `vcan0` 시나리오와 T1~T4 계측을 자동화한다.
4. P5는 RPi4와 실제 Node A 제공물로 물리 CAN 증거를 분리 기록한다.
5. P6에서 GitHub Actions, 배포 절차, 공식 TC 추적과 데모 자료를 마감한다.
