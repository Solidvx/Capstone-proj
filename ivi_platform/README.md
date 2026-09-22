# Node B IVI — Qt Plan B

Ubuntu 22.04, C++17, SocketCAN, Qt 6 Quick/QML 기반 Node B 구현이다. CAN/SecOC wire 계약은 [ICD](../docs/ICD.md)를 따른다.

## 현재 구현 범위

P1에서 로컬 보관본의 C++/QML을 선택 이관하고 현재 계약에 맞게 core와 UI target을 분리했다.

- `ivi_core`: CAN parser, OpenSSL HMAC-SHA256 verifier, 인증 후 게시하는 `VehicleDataService`
- `ivi_socketcan`: Linux SocketCAN 수신 worker와 5개 CAN ID 필터
- `ivi_dashboard`: Qt 6가 있을 때만 생성되는 QML 앱
- `test/`: 외부 테스트 프레임워크 없이 Debug/Release에서 동일하게 동작하는 core 시험 3개

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

P2에서 pending timeout, 새 원본 덮어쓰기 정책, SocketCAN 오류 재시도 및 전체 counter/프레임 경계 시험을 완성한다. P3에서 stale timer, IDS 확인 동작, CRITICAL/SHUTDOWN 전체 화면 경고와 Qt 시험을 추가한다. P1의 상세 구현과 결과는 [P1 구현 결과](../docs/aidlc/changes/CHG-003/construction/P1_구현_결과.md), 전체 상태는 [CHG-003](../docs/aidlc/changes/CHG-003/aidlc-state.md)에 기록한다.
