# CHG-011 검증 증거

## 1. 착수 전 ECU RPi 확인 (기준 커밋 `615efb1`)

2026-10-03 ECU RPi4(Debian GNU/Linux 13.5 trixie)에서 사용자가 실행했다. 이 변경 이전 바이너리의 `constant` 모드 확인이며, 키 배치와 C++/Python SecOC 일치의 기준선이다.

- `--clean-first` 재빌드 후 `adaptive_ecu --interface vcan0 --sensor-mode constant --secoc on --key /etc/secoc/key.bin`.
- `candump vcan0`: `0x100` 다음 `0x102`가 교대로 나오고 `0x102` counter가 `0x00`부터 `0x31`까지 1씩 증가.
- 처음 세 쌍을 `security/secoc_module.py`로 같은 키를 읽어 검증: 정상 3쌍 `True`, MAC 1비트 변조 `False`.
- 키는 ICD §1.4대로 `/etc/secoc/key.bin`(0400, root:root, 32바이트)에 두었다. 키와 해시 값은 기록하지 않는다.

## 2. 단위 시험 (WSL2 Ubuntu x86_64)

```bash
cmake -S adaptive_ecu -B tmp/stage1-ecu-build -DECU_BUILD_TESTS=ON -DCMAKE_BUILD_TYPE=Release \
  "-DCMAKE_CXX_FLAGS=-Wall -Wextra -Wpedantic -Werror" -DCMAKE_PREFIX_PATH=$PWD/tmp/adc-smoke-deps/install
cmake --build tmp/stage1-ecu-build -j4
ctest --test-dir tmp/stage1-ecu-build --output-on-failure
ctest --test-dir tmp/stage1-ecu-build -R "acquirer|sample_feed|sensor_simulator" --repeat until-fail:30
```

결과: 경고 없이 빌드, CTest 16/16 통과(기존 14 + 신규 2). 신규·변경 시험 `test_ads1115_acquirer` 6건, `test_hardware_sample_feed` 6건, `test_sensor_simulator` 5건 통과. 세 시험 30회 반복 실패 0건(스레드 worker 시험 포함).

| 시험 | 확인 내용 |
|---|---|
| `test_ads1115_acquirer` | 요청당 결과 1개와 100ms 간격, 20ms 넘긴 결과 거부, 시작 I/O 오류 뒤 간격 유지 재시도, 미완료 변환 20ms 만료와 복구, 범위 밖 raw 거부와 마지막 유효값 유지, 실제 스레드 worker 게시 |
| `test_hardware_sample_feed` | 첫 결과 전 보류, 새 유효 결과 3회 뒤 송신, 같은 순번 재조회 미계수, 순번이 안 바뀐 주기의 주기 유지, 오류 뒤 보류와 3회 재확인, worker 정지(200ms 초과) 보류 |
| `test_sensor_simulator` | ADS1115 모드의 검증 전압·가상 전류·온도, 검증값 없는 호출 거부, 공식 모드 이름만 수락(`potentiometer`·대소문자 오타 거부) |

CLI: `--sensor-mode potentiometer`와 `--sensor-mode ADS1115`가 다른 모드로 대체되지 않고 `Unsupported sensor mode`, 종료 코드 2.

## 3. ECU RPi 실장비 (커밋 `ccad48b`, 끝점 허용 적용 전)

2026-10-03 사용자 실행. `vcan0`, `--sensor-mode ads1115 --secoc on --key /etc/secoc/key.bin`.

- 시작 출력: `ADS1115 quality: VALID`까지 확인. 처음에는 이전 바이너리가 실행돼 두 번째 줄이 없었고, 브랜치·재빌드 확인 후 정상 출력됐다.
- `candump -L -n 202` 약 10초, 노브를 양 끝까지 회전하며 캡처 후 Python 분석: `0x100` 101개, 간격 최소 100.0 / 평균 103.1 / 최대 400.3ms, 전압 30.00~41.99V, `0x102` MAC 검증 101/101 성공.
- 최대 400.3ms는 오류 1회와 복구 3회 동안의 송신 보류(D1)다. 노브를 0V 쪽 끝에 두면 `ERROR_WITH_LAST_VALUE → RECOVERING_WITH_LAST_VALUE → VALID`가 반복됐고 가운데에서는 재현되지 않았다.
- 원인 측정(ECU 정지 후 `i2ctransfer`로 단발 변환 100회): 0V 쪽 끝 최소 -4 / 최대 6, 분포 (-4:1, -1:1, 2:70, 3:27, 6:1). 3.3V 쪽 끝 최소 26342 / 최대 26364. 음수 2%가 기존 범위(0~26400) 밖 오류의 원인이다.
- 사용자 결정 D5=B로 ±16코드 끝점 허용을 추가했다(커밋 `f05f120`).

### 3.1 ±16코드 적용 후 (커밋 `f05f120`)

- 0V 쪽 끝 30초 정지: 오류 없음.
- 같은 캡처·분석: `0x100` 101개, 간격 최소 100.0 / 평균 100.1 / 최대 100.1ms, 전압 30.00~41.98V, MAC 101/101.
- Fail-safe: 0V 쪽 끝에 두자 `Fail-safe transition: 0 -> 1 reason=0x1`(WARNING), 이어서 `1 -> 2 reason=0x2`(CRITICAL). 각 전이 때 `0x101`과 `0x103`을 송신한다(프레임 캡처는 미수집).
- 이후 수 분 대기 중 `ERROR_WITH_LAST_VALUE → RECOVERING_WITH_LAST_VALUE → VALID`가 1회 발생했다.
- 원인 재측정(ECU 정지, 0V 끝 단발 변환 1000회): 최소 -20 / 최대 19, -16 미만 2회(-20·-18), 음수 9회, 2~3이 961회. 0.2%의 큰 순간 잡음이 ±16을 넘는다(10Hz 취득 기준 약 50초에 1회). 사용자 결정으로 ±32코드로 넓히고(관측 최대 이탈의 약 1.6배) 오류 원인 로그를 추가했다(D6). 장비 1대의 측정이므로 추가 측정 후 재검토한다.

## 4. 단위 시험 (WSL2, ±32코드·원인 로그 적용)

같은 `-Werror` 빌드에서 CTest 16/16 통과. `test_ads1115_conversion` 3건(전체 65,536 코드의 허용·거부와 끝값 매핑, 경계 -32·-33·26432·26433, 실측 최저 -20), `test_ads1115_acquirer` 7건(원인 기록 Late 20ms·ReadFailed·StartFailed·Timeout·OutOfRange -33과 로그 문구 포함), `test_hardware_sample_feed` 6건(취득 오류와 stale 원인 구분), `test_ads1115_sample` 5건의 범위 밖 입력을 -33(0xFFDF)·26433으로 갱신. 관련 시험 30회 반복 실패 0건. ±16 적용 때 첫 빌드는 `-Werror=dangling-else`로 실패해 시험 코드에 중괄호를 넣었으며, 그 사이 출력된 CTest 결과는 갱신 전 바이너리라 증거로 쓰지 않았다.

## 5. 미실행

- ±32코드·원인 로그 적용 후 ECU RPi 재시험: 0V 쪽 끝 장시간 정지 시 오류 빈도, 오류가 나면 원인 로그 확인.
- Fail-safe 전이 프레임(`0x101`/`0x103`) 캡처.
- 전원이 켜진 상태의 배선 분리 시험은 하지 않는다([진단 절차](../../../development/playbooks/ads1115-can-smoke.md)). 오류·복구는 단위 시험으로 확인했다.
- IVI 화면 반영(IT-001·IT-003)은 공동 시험. SecOC 키는 2026-10-03 IVI에 전달해 양측 SHA-256 일치를 확인했다(값은 기록하지 않음).
