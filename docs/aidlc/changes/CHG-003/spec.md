# CHG-003 — IVI Plan B P1 선택 이관과 구현 기반

## 요청

- 로컬 `도토리팀_소스코드/Cap-proj/ivi_platform`의 재사용 가능한 코드를 현재 저장소 `ivi_platform/`에 선택 이관한다.
- `adaptive_ecu/`의 송신 형식과 SecOC 벡터를 기준으로 현행 ICD에 맞게 보정한다.
- P1을 구현하고 P1~P6의 상태와 결과물 위치를 계속 기록한다.

## 적용 범위

- C++17/CMake 기반 parser, SecOC verifier, 상태 service, SocketCAN receiver
- Qt 6 Quick/QML 앱의 최소 조립 구조
- parser/SecOC/service 단위 시험과 보조 스크립트
- Plan B 계획·설계·시험·온보딩 문서의 실제 상태 동기화

Android AOSP, HIDL, AIDL, Kotlin, 과거 빌드 산출물과 실제 SecOC 키는 반입하지 않는다. CAN ID, DLC, payload와 HMAC 입력 순서는 `docs/ICD.md`를 변경하지 않는다.

## 입력과 출처

| 입력 | 사용 내용 |
|---|---|
| 로컬 보관본 `ivi_platform/` | parser/verifier/Qt 구조의 참고 기준 |
| `adaptive_ecu/src/bsw/can_publisher.cpp` | BMS·Fail-safe payload 인코딩 |
| `adaptive_ecu/src/bsw/secoc_module.cpp` | HMAC-SHA256 입력 순서와 counter 허용 범위 |
| `adaptive_ecu/test/test_secoc.cpp` | 더미 키 `00..1f`, 알려진 MAC과 경계 벡터 |
| `docs/ICD.md` | wire 계약의 최종 기준 |

보관본의 parser/verifier 및 시험 6개 파일은 `plan/IVI_PLAN_B_전환계획.md`에 고정한 SHA-256과 일치함을 확인했다. 코드는 그대로 덮어쓰지 않고 현재 계약에 맞춰 새 모듈 경계와 시험으로 구성했다.

## P1 합격 조건

- Qt가 없는 호스트에서도 `ivi_core`, `ivi_socketcan`, 단위 시험이 구성·빌드된다.
- Debug와 Release에서 parser, SecOC, service 시험이 각각 통과한다.
- 보호 데이터는 대응 인증 성공 전 snapshot에 게시되지 않는다.
- 빌드 산출물과 비밀키는 Git에 포함되지 않는다.
- Qt·SocketCAN 실동작처럼 현재 호스트에서 실행하지 못한 항목은 통과로 기록하지 않는다.
