# ADS1115 → CAN → Qt 전압 표시 진단

대상: 두 노드의 물리 CAN 통신과 Qt 모의값 표시를 확인한 ECU·IVI 담당자.
이 도구는 기존 ICD 형식으로 실제 입력의 표시 경로를 확인하는 독립 진단이다.
제품 `adaptive_ecu --sensor-mode ads1115`의 구현 완료를 뜻하지 않는다.
변경·검증 기록: [CHG-008](../../aidlc/changes/CHG-008/aidlc-state.md).

## 범위와 표시값

- AIN0, I²C `/dev/i2c-1`, 주소 `0x48`, 단발 128 SPS, PGA ±4.096 V.
- 원시값 0~26400만 인수. 0~3.3 V를 가상 팩 전압 30~42 V로 변환한다.
- 100ms 이상 간격으로 요청하며 20ms 이상 걸린 결과를 폐기한다. 실제 I/O 호출을 20ms 안에 취소한다는 뜻은 아니다.
- 최초 및 오류 후 새로운 유효 변환 3회 연속 성공부터 `0x100`을 송신한다.
- 기존 인코더 사용, byte 7은 0 유지. 전류 -2A, 온도 25°C, SOH 100%는 모의값이다.
- SOC는 EKF 출력이며 노브 각도에 비례하는 정답 SOC가 아니다. 취득 공백 후 진단용 EKF를 초기화한다.
- SecOC·Fail-safe 이벤트·Watchdog은 이 진단 도구에 포함하지 않는다. 화면의 Normal은 ECU 안전 판정 증거가 아니다.
- I²C 오류·범위 이탈·완료 시간 초과 시 CAN 송신을 멈춘다. 팀원 IVI는 이전 숫자를 계속 표시할 수 있으므로, 화면 정지만으로 센서 정상 여부를 판단하지 않는다.
- 동기 취득을 사용하므로 제품의 독립 감시·CAN 루프 요구를 충족하는 런타임이 아니다. 제품 통합은 센서 상태 계약과 양측 구현의 동기화가 필요하다.

## 1. ECU에 파일 전달

PC에서 작성한 파일은 Pi에 자동 반영되지 않는다. 이번 변경 파일은 다음 4개다.

```text
adaptive_ecu/CMakeLists.txt
adaptive_ecu/include/ads1115_sample.h
adaptive_ecu/tools/ads1115_can_smoke.cpp
adaptive_ecu/test/test_ads1115_sample.cpp
```

기본 전달 경로는 GitHub의 `chore/ecu-m1-baseline` 브랜치다. PC에서 push 완료를 확인한 뒤 ECU에서 실행한다.

```bash
cd ~/Capstone-proj
git status --short
git branch --show-current
git pull --ff-only origin chore/ecu-m1-baseline
```

현재 브랜치가 `chore/ecu-m1-baseline`인지 확인하고, 로컬 수정이 있거나 pull이 실패하면 먼저 해당 변경을 대조한다. 강제 reset으로 지우지 않는다. pull 성공 후 바로 2절로 이동한다.

아래 ZIP 경로는 Git 전달을 사용하지 못할 때의 대안이다. `tmp/ads1115-can-smoke.zip`을 USB 또는 사용 중인 파일 전송 도구로 ECU의 홈 디렉터리에 옮긴다. 압축에는 위 파일과 이 안내서만 들어 있다.

Pi에서 먼저 `cd ~/Capstone-proj`와 `git status --short`로 확인한다. 위 4개 경로에 자신의 변경이 있으면 덮어쓰지 말고 대조한다. 소스가 기존 baseline과 다르면 CMake 전체 덮어쓰기 대신 새 target·시험 목록 변경을 병합한다.

기존 변경이 없는 baseline에서는 다음처럼 소스를 백업한 후 적용할 수 있다.

```bash
cd ~/Capstone-proj
tar -czf "$HOME/ecu-before-adc-$(date +%Y%m%d-%H%M%S).tar.gz" --exclude=adaptive_ecu/build adaptive_ecu
python3 -m zipfile -e ~/ads1115-can-smoke.zip .
```

## 2. ECU 빌드·테스트

```bash
cmake -S adaptive_ecu -B adaptive_ecu/build -DECU_BUILD_TESTS=ON
cmake --build adaptive_ecu/build -j2
ctest --test-dir adaptive_ecu/build --output-on-failure
```

`ads1115_can_smoke` 생성 및 14개 CTest 통과를 확인한다. 실패하면 다음 단계로 진행하지 않고 첫 오류를 확인한다.

## 3. 센서 단독 확인

기존 `adaptive_ecu` 송신과 Python ADC 측정기를 Ctrl+C로 종료한다. 한 번에 하나의 ADC 취득 프로그램만 실행한다.

```bash
sudo ./adaptive_ecu/build/ads1115_can_smoke
```

`--interface`가 없으면 CAN 송신 없이 측정만 한다. 노브를 돌려 `RAW`, `A0`, `PACK`이 변하는지 확인한다. 준비 메시지 뒤 `ADC_ONLY`가 출력되어야 한다. `ADC ERROR`가 반복되면 출력과 I²C 상태를 확인하며, `-f` 등 강제 주소 사용으로 우회하지 않는다. 종료는 Ctrl+C.

## 4. IVI 화면 및 CAN 확인

양쪽 `can0`는 일반 모드, 500000 bit/s로 켜져 있어야 한다. IVI 데스크톱 터미널에서 팀원이 실제 시험한 버전을 실행한다.

```bash
cd ~/Cap-proj
./ivi_platform/build/ivi_qml_dashboard --interface can0
```

이는 대화에서 제공된 팀원 소스에 맞춘 명령이다. 저장소의 다른 버전(`ivi_dashboard`, 인증 후 게시)에는 그대로 적용하지 않는다. 이번 팀원 버전은 미인증 `0x100`도 표시하는 drift가 있으며, 본 진단 성공으로 보안 인수하지 않는다.

IVI의 다른 터미널에서 실제 프레임도 확인한다.

```bash
candump -td can0,100:7FF
```

ECU에서 실행한다.

```bash
cd ~/Capstone-proj
sudo ./adaptive_ecu/build/ads1115_can_smoke --interface can0
```

노브를 천천히 돌려 아래 비교를 한다. 수치는 이상적 변환 기준이며 정확한 장비 측정값을 보장하지 않는다.

| ECU A0 | ECU PACK / IVI Voltage |
|---|---|
| 약 0 V | 약 30 V |
| 약 1.65 V | 약 36 V |
| 약 3.3 V | 약 42 V |

수신 바이트 2~3은 전압×100의 big-endian이다. 예: 30V=`0B B8`, 36V=`0E 10`, 42V=`10 68`. ECU 로그와 IVI 숫자가 함께 변하는지 확인한다. Security는 Unverified가 예상된다.

## 5. 오류·복구와 종료

자동 시험은 I/O 실패, 잘못된 설정, 범위 이탈, 변환 미완료, 20ms 경계, 복구 3회 조건을 모의 검증한다. 잘못된 장치 경로는 다음으로 전원 조작 없이 시험할 수 있다.

```bash
sudo ./adaptive_ecu/build/ads1115_can_smoke --i2c-device /dev/i2c-does-not-exist
```

이 실행은 CAN을 열기 전에 오류·비정상 종료해야 한다. 정상 경로로 다시 시작하면 준비 3회 후 측정이 재개돼야 한다. 이는 시작 실패·재시작 시험이며 동작 중 단선 복구 시험과 다르다. 전원이 켜진 채 배선을 뽑는 시험은 하지 않는다.

종료는 ECU 진단·IVI 수신 터미널에서 Ctrl+C. 양쪽 `ip -details -statistics link show can0` 출력과 A0/PACK/UI 값, 오류 발생 여부를 기록한다. 세 지점 값 변화와 오류 통계까지 확보해야 물리 시험 결과를 남길 수 있다.

## 후속 제품 통합

[SDD-ECU](../../SDD-ECU.md)의 비동기 취득·감시 분리, [ICD](../../ICD.md)의 승인된 센서 상태 목표와 양측 UI 처리, SecOC 인증 후 반영을 함께 구현·검증해야 한다. 이 진단은 해당 계약 변경을 수행하지 않는다.

Linux 결합 I²C 전송은 [커널 i2c-dev 문서](https://docs.kernel.org/i2c/dev-interface.html)의 `I2C_RDWR`를 사용한다.
