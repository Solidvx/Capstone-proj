# Node B IVI — Qt Plan B

Ubuntu 22.04, C++17, SocketCAN, Qt 6 Quick/QML 기반 Node B 구현이다. CAN/SecOC wire 계약은 [ICD](../docs/ICD.md)를 따른다.

## 현재 구현 범위

P1에서 로컬 보관본의 C++/QML을 선택 이관하고, P2에서 CAN·SecOC pending 정책과 수신 오류 경계를 완성했다. P3에서는 stale·IDS 확인·Fail-safe 전체 화면 경고를 완성했다. P4에서는 Linux `vcan0` 통합과 Qt T1~T4 계측을 완료했다.

- `ivi_core`: CAN parser, OpenSSL HMAC-SHA256 verifier, 인증 후 게시하는 `VehicleDataService`
- `ivi_socketcan`: Linux SocketCAN 수신 worker, 5개 CAN ID 필터와 최대 3회 오류 재시도
- `ivi_dashboard`: Qt 6가 있을 때만 생성되는 QML 앱
- `test/`: core 시험 8개, Linux SocketCAN 통합시험 1개, Qt 시험 2개

P2의 pending은 데이터 ID별 한 슬롯이며 100ms 동안 유지한다. 같은 ID의 새 원본은 기존 원본을 교체하고, 인증 선도착은 보관하지 않는다. 이 100ms는 raw/auth pair의 내부 정책이며 ICD의 300ms BMS stale 판정과 별개다.

ICD §8의 sensorState wire 전환 전에는 byte 7을 해석하지 않고 `UNSUPPORTED_LEGACY_WIRE`로 표시한다. Android/HIDL/AIDL/Kotlin과 이전 빌드 산출물은 반입하지 않았다. Linux `vcan0`와 Qt offscreen 계측은 검증했으며 RPi4/MCP2515 `can0`은 아직 미검증이다.

## 빌드와 시험

```bash
cmake -S ivi_platform -B ivi_platform/build -DIVI_BUILD_TESTS=ON
cmake --build ivi_platform/build
ctest --test-dir ivi_platform/build --output-on-failure
```

Qt 6가 없으면 core와 시험만 빌드된다. Qt target을 명시적으로 끄려면 `-DIVI_BUILD_QT_APP=OFF`를 사용한다. macOS Homebrew Qt는 CMake에 `-DCMAKE_PREFIX_PATH=/opt/homebrew`를 전달한다.

Qt 앱 실행 시 32바이트 SecOC 키와 CAN 인터페이스를 명시한다. 키 파일은 저장소에 커밋하지 않는다.

```bash
./ivi_platform/build/ivi_dashboard --interface vcan0 --secoc-key /etc/secoc/key.bin
```

환경 점검은 `scripts/check_qt_ivi_env.sh`, 테스트 프레임 전송은 `scripts/send_ivi_test_vectors.py --help`를 사용한다.

Linux `vcan0` 통합과 T1~T4 1,000표본 계측은 다음 스크립트로 재현한다.

```bash
./ivi_platform/scripts/run_vcan_integration.sh
./ivi_platform/scripts/run_vcan_latency.sh \
  ./ivi_platform/build/ivi_dashboard /tmp/ivi-p4-latency 1000
```

CAN 장치 없이 P3 화면을 확인하려면 demo 상태를 사용한다.

```bash
./ivi_platform/build/ivi_dashboard --demo waiting
./ivi_platform/build/ivi_dashboard --demo normal
./ivi_platform/build/ivi_dashboard --demo stale
./ivi_platform/build/ivi_dashboard --demo sensor-error
./ivi_platform/build/ivi_dashboard --demo warning
./ivi_platform/build/ivi_dashboard --demo critical
./ivi_platform/build/ivi_dashboard --demo shutdown
./ivi_platform/build/ivi_dashboard --demo ids
```

## 다음 단계

P5의 RPi4 업로드·설치 코드는 준비됐다. 깨끗하게 커밋된 현재 HEAD를 RPi에 올리려면 저장소 루트에서 다음을 실행한다.

```bash
./ivi_platform/scripts/deploy_rpi.sh <user>@<rpi-host>
```

업로드 후 출력되는 RPi 경로에서 의존성 설치, Release 빌드와 설치를 순서대로 실행한다. `deploy_rpi.sh`는 git archive와 SHA-256을 사용하며 작업 트리의 미커밋 파일, SecOC 키, 로컬 빌드 산출물은 전송하지 않는다.

```bash
sudo ./ivi_platform/scripts/install_rpi_dependencies.sh
./ivi_platform/scripts/build_rpi.sh
sudo ./ivi_platform/scripts/install_rpi.sh
sudo ./ivi_platform/scripts/provision_secoc_key.sh <32-byte-key-file>
sudo systemctl enable --now ivi-can0.service ivi-dashboard.service
```

MCP2515 overlay는 `deploy/rpi/config.txt.fragment`를 실제 8MHz crystal과 GPIO25 INT 배선에 대조한 뒤 적용한다. 실제 장비 시험 전에는 [preflight](scripts/rpi_preflight.sh)가 모두 통과해야 한다. 단계별 결과는 [P1](../docs/aidlc/changes/CHG-003/construction/P1_구현_결과.md), [P2](../docs/aidlc/changes/CHG-003/construction/P2_구현_결과.md), [P3](../docs/aidlc/changes/CHG-003/construction/P3_구현_결과.md), [P4](../docs/aidlc/changes/CHG-003/construction/P4_구현_결과.md), [P5 배포 준비](../docs/aidlc/changes/CHG-003/construction/P5_배포_준비_결과.md), 전체 상태는 [CHG-003](../docs/aidlc/changes/CHG-003/aidlc-state.md)에 기록한다.

## SecOC 소프트웨어 보완

CHG-006에서는 P2를 이어서 다음 동작을 구현했고, develop의 P3·P4와 병합하면서 stale 판정은 P3 `refreshTime()`으로 일원화했다.

- 원본/인증 쌍은 ID별 슬롯, 100ms 만료, 새 원본 우선 정책을 유지한다. 실패 auth는 게시/카운터 갱신 없이 버리고 원본은 만료 전 정상 auth 재시도를 허용한다.
- `pollTimeouts(now)`는 입력이 없어도 pending을 한 번 만료시킨다. Qt main의 10ms 타이머가 호출하며 stale은 다루지 않는다. 100ms는 논리 기한이며 실제 이벤트 루프 지연은 별도 실측 대상이다.
- 300ms stale은 P3 `refreshTime()`(50ms 타이머)이 last-good를 보존한 채 전환하며 로그 reason은 `BMS_STALE`이다. Fail-safe 인증은 BMS 기한을 연장하지 않는다.
- 로컬 로그 reason: MAC_FAIL, COUNTER_REUSE, COUNTER_BACKWARD, COUNTER_WINDOW, AUTH_TIMEOUT, AUTH_ORPHAN, KEY_UNAVAILABLE, TIME_REGRESSION, PENDING_REPLACED, BMS_STALE. uint32 차이의 절반 구분은 로그용이며 전송 주체/공격 의도를 입증하지 않는다.
- 실패 snapshot도 observer로 전달한다. 이는 인증되지 않은 차량 데이터 게시가 아니라 진단 통지다. 연속 실패 4회 WARNING, 10회 CRITICAL과 Qt 인증 오류 경고, 정상 인증 후 연속 실패 해제를 구현한다.
- 키를 다시 설정하면 pending은 지우고 기존 counter 이력은 보존한다. 새 세션 인증·부팅 replay 방어 완성을 의미하지 않는다.

하드웨어 없는 재현 (저장소 루트, CMake/OpenSSL 및 Qt6 개발·QML 런타임 설치):

```sh
cmake -S ivi_platform -B ivi_platform/build -DCMAKE_BUILD_TYPE=Debug -DIVI_BUILD_QT_APP=ON
cmake --build ivi_platform/build -j4
ctest --test-dir ivi_platform/build --output-on-failure
```

Qt 화면 시험을 완료로 보고하려면 offscreen QML 경고·복구 시험 `test_dashboard_security`가 실제 실행되어야 한다.
실행 증거와 한계: [CHG-006](../docs/aidlc/changes/CHG-006/audit.md).
