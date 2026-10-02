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

실제 RPi4 결과는 아직 기록하지 않았다. 다음 값을 장비 실행 후 원문 그대로 추가한다.

- `git rev-parse HEAD`
- `cat /etc/os-release`의 OS 식별값
- `qmake6 -query QT_VERSION`
- `ip -details link show vcan0`
- Qt 포함 Release 빌드 결과
- 전체 CTest 통과/실패/skip 수

실제 키 내용과 장비 주소는 기록하지 않는다. MCP2515 `can0`와 실제 display 결과는 `vcan0` 결과와 구분한다.
