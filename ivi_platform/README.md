# Node B IVI — Qt Plan B

Ubuntu 22.04, C++17, SocketCAN, Qt 6 Quick/QML 기반 Node B 구현이다. CAN/SecOC wire 계약은 [ICD](../docs/ICD.md)를 따른다.

## 현재 구현 범위

P1에서 로컬 보관본의 C++/QML을 선택 이관하고, P2에서 현재 계약에 맞는 CAN·SecOC pending 정책과 수신 오류 경계를 완성했다.

- `ivi_core`: CAN parser, OpenSSL HMAC-SHA256 verifier, 인증 후 게시하는 `VehicleDataService`
- `ivi_socketcan`: Linux SocketCAN 수신 worker, 5개 CAN ID 필터와 최대 3회 오류 재시도
- `ivi_dashboard`: Qt 6가 있을 때만 생성되는 QML 앱
- `test/`: 외부 테스트 프레임워크 없이 Debug/Release에서 동일하게 동작하는 core 시험 6개

P2의 pending은 데이터 ID별 한 슬롯이며 100ms 동안 유지한다. 같은 ID의 새 원본은 기존 원본을 교체하고, 인증 선도착은 보관하지 않는다. 이 100ms는 raw/auth pair의 내부 정책이며 ICD의 300ms BMS stale 판정과 별개다.

Android/HIDL/AIDL/Kotlin, 이전 빌드 산출물, 웹/Python Plan B 서버는 반입하지 않았다. 실제 Qt 앱, vcan, RPi4/can0 검증은 아직 완료되지 않았다.

## 빌드와 시험

```bash
cmake -S ivi_platform -B ivi_platform/build -DIVI_BUILD_TESTS=ON
cmake --build ivi_platform/build
ctest --test-dir ivi_platform/build --output-on-failure
```

Qt 6가 없으면 core와 시험만 빌드된다. Qt target을 명시적으로 끄려면 `-DIVI_BUILD_QT_APP=OFF`를 사용한다.

Qt 앱 실행 시 32바이트 SecOC 키와 CAN 인터페이스를 명시한다. 키 파일은 저장소에 커밋하지 않는다.

```bash
./ivi_platform/build/ivi_dashboard --interface vcan0 --secoc-key /etc/secoc/key.bin
```

환경 점검은 `scripts/check_qt_ivi_env.sh`, 테스트 프레임 전송은 `scripts/send_ivi_test_vectors.py --help`를 사용한다.

## 다음 단계

P3에서 stale timer, IDS 확인 동작, CRITICAL/SHUTDOWN 전체 화면 경고와 Qt 시험을 추가한다. P1은 [P1 구현 결과](../docs/aidlc/changes/CHG-003/construction/P1_구현_결과.md), P2는 [P2 구현 결과](../docs/aidlc/changes/CHG-003/construction/P2_구현_결과.md), 전체 상태는 [CHG-003](../docs/aidlc/changes/CHG-003/aidlc-state.md)에 기록한다.

## SecOC 보완 브랜치의 소프트웨어 구현

`feat/ivi-secoc-hardening`은 develop의 P2를 이어서 다음 동작을 구현한다.

- 원본/인증 쌍은 ID별 슬롯, 100ms 만료, 새 원본 우선 정책을 유지한다. 실패 auth는 게시/카운터 갱신 없이 버리고 원본은 만료 전 정상 auth 재시도를 허용한다.
- `pollTimeouts(now)`는 입력이 없어도 pending을 한 번 만료시킨다. Qt main의 10ms 타이머가 호출한다. 100ms는 논리 기한이며 실제 이벤트 루프 지연은 별도 실측 대상이다.
- 마지막 인증 BMS 이후 300ms에 last-good를 보존한 stale로 전환한다. Fail-safe 인증은 BMS 기한을 연장하지 않는다.
- 로컬 로그 reason: MAC_FAIL, COUNTER_REUSE, COUNTER_BACKWARD, COUNTER_WINDOW, AUTH_TIMEOUT, AUTH_ORPHAN, KEY_UNAVAILABLE, TIME_REGRESSION, PENDING_REPLACED, BMS_STALE. uint32 차이의 절반 구분은 로그용이며 전송 주체/공격 의도를 입증하지 않는다.
- 실패 snapshot도 observer로 전달한다. 이는 인증되지 않은 차량 데이터 게시가 아니라 진단 통지다. 연속 실패 4회 WARNING, 10회 CRITICAL과 Qt 인증 오류 경고, 정상 인증 후 연속 실패 해제를 구현한다.
- 키를 다시 설정하면 pending은 지우고 기존 counter 이력은 보존한다. 새 세션 인증·부팅 replay 방어 완성을 의미하지 않는다.

하드웨어 없는 재현 (저장소 루트, CMake/OpenSSL 및 Qt6 개발·QML 런타임 설치):

```sh
cmake -S ivi_platform -B ivi_platform/build -DCMAKE_BUILD_TYPE=Debug -DIVI_BUILD_QT_APP=ON
cmake --build ivi_platform/build -j4
ctest --test-dir ivi_platform/build --output-on-failure
```

Qt가 없으면 core 7개, Qt가 있으면 offscreen QML 경고·복구 시험을 포함한 8개가 등록된다. Qt 화면 시험을 완료로 보고하려면 `test_dashboard_security`가 실제 실행되어야 한다.
실행 증거와 한계: [CHG-006](../docs/aidlc/changes/CHG-006/audit.md).
