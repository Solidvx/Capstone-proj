# CHG-010 검증 증거

## 기준

- 브랜치: `fix/ivi-debian13-qt68`
- 대상: Debian 13 ARM64, Qt 6.8, Raspberry Pi 4
- 강제 SocketCAN 검증: `IVI_REQUIRE_SOCKETCAN=1`

## 실행 결과

### 사전검증

| 환경 | 실행 | 결과 |
|---|---|---|
| macOS arm64, Qt 6.11 | Release·`-Werror`, Qt 포함 CTest, install | 10/10 통과, `bin/ivi_dashboard` 설치 확인 |
| ARM64 Linux VM, Qt 6.10 | `vcan0` 없음, 기본 모드 | SocketCAN 시험 SKIP |
| ARM64 Linux VM, Qt 6.10 | `vcan0` 없음, `IVI_REQUIRE_SOCKETCAN=1` | SocketCAN 시험 FAIL 확인(`errno=19`) |
| ARM64 Linux VM, Qt 6.10 | `vcan0` UP, `IVI_REQUIRE_SOCKETCAN=1` | Qt 포함 전체 11/11 통과, install 확인 |

VM 결과는 Debian 13 RPi4 시험을 대체하지 않는다.

### 실제 RPi4

2026-10-03에 배포 커밋 `dff736344cc224e2b9fa2f26b3be82470172e698`을 실제 IVI RPi4에 올려 실행했다. 앞선 의존성 설치 출력에서 대상 OS는 Debian GNU/Linux 13(trixie)으로 확인했다. CMake의 Qt 6.8 최소 버전 검사를 통과해 Qt dashboard와 Qt 시험을 빌드했으며, 정확한 `qmake6` 버전 문자열은 전달받은 출력에 포함되지 않았다.

실행 명령:

```bash
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set vcan0 up
IVI_REQUIRE_SOCKETCAN=1 ./ivi_platform/scripts/build_rpi.sh
```

결과:

```text
100% tests passed, 0 tests failed out of 11
Total Test time (real) = 0.73 sec
PASS: RPi Release dashboard built at /tmp/ivi-rpi-dff736344cc224e2b9fa2f26b3be82470172e698/Capstone-proj/ivi_platform/build-rpi/ivi_dashboard
```

`IVI_REQUIRE_SOCKETCAN=1`이므로 `test_socketcan_receiver`는 SKIP할 수 없으며 위 11/11에 실제 PF_CAN `vcan0` 수신 시험과 Qt 시험 2개가 포함된다.

실제 키 내용과 장비 주소는 기록하지 않는다. MCP2515 `can0`와 실제 display 결과는 `vcan0` 결과와 구분한다.
