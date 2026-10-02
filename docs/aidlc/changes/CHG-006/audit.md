# CHG-006 검증 증거

- 기준 커밋: 8c78672, 브랜치 feat/ivi-secoc-hardening. 동료의 P2 core 위에 추가 구현.
- 환경: Windows 호스트의 WSL Ubuntu, GNU C++ 13.3.0, OpenSSL 3.0.13, Qt 6.4.2, CMake Debug.
- 명령: `cmake -S ivi_platform -B ivi_platform/build -DCMAKE_BUILD_TYPE=Debug`, `cmake --build ivi_platform/build -j4`, `ctest --test-dir ivi_platform/build --output-on-failure`.
- 결과: Qt 앱 빌드 성공, CTest 8/8 통과. 마지막 시험 총 0.39초(성능 합격 기준이 아닌 실행 기록).
- `test_secoc_runtime`: 무수신 99/100ms 만료, 반복 poll 중복 집계 방지, BMS 299/300ms stale와 last-good 보존, Fail-safe 독립성, counter 재사용/역전/+100/+101/wrap, MAC 실패, 키 재설정 pending 폐기·counter 보존, 변조 100회와 Replay 100회 거부.
- `test_dashboard_security`: 실제 QML을 offscreen으로 로드, 10회 인증 실패 표시 및 정상 인증 복구, stale 전달 확인. 외부 화면/실장비 캡처가 아니다.
- 실패 진단 callback은 mutex 밖에서 호출하며 정상 차량 상태는 변경하지 않는다. 기존 peer API/ICD wire 계약은 불변이다. 내부 타이머 진입점과 Qt 표시 속성만 추가했다.
- WSL의 `ip link add codexvcan0 type vcan`은 `Unknown device type`으로 실패. 인터페이스가 생성되지 않았으며 vcan/물리 CAN 송수신은 미검증이다.
- Linux 수신 복구·실제 시간 지연·P3 전체 UI·인증 세션 전환은 완료 범위에 포함하지 않는다. 실제 키를 생성/저장하지 않았다.
