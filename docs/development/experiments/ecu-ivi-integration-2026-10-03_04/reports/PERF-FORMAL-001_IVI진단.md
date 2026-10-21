# PERF-FORMAL-001 IVI 진단 자료 검토

2026-10-04 수령한 04H02M 압축파일을 검토했다. 원본 압축파일과 내부 일반 파일 15개를 보존했으며 [파일 목록과 SHA256](../inventory.json)에 추가했다. 원본 로그는 `../raw/PERF-FORMAL-001/ivi-diagnostics/`에 있다.

## 확인 결과

| 확인 항목 | 자료에서 확인한 사실 | 판단 범위 |
|---|---|---|
| 커널 | 6.18.29+rpt-rpi-v8, aarch64 | 수집 당시 환경 |
| CAN 드라이버 | mcp251x, spi0.0, MCP2515 초기화 성공 메시지 | 초기화 성공이 전체 시험의 정상 동작을 보장하지 않음 |
| CAN 설정 | 500000bit/s, sample-point 0.750, restart-ms 100, clock 4000000 | 조회 값 보존. clock을 SPI 통신 속도로 해석하지 않음 |
| 상태 | ERROR-ACTIVE, RX 16678, RX errors 12, dropped 0, warning 5, passive 5, bus-off 0 | 시험 전 통계가 없어 이번 시험 증가량 미확인 |
| journal | 최초 전체 수집은 sudo 인증 3회 실패, 이후 지정 시간대 조회는 오류 출력 없이 No entries | 최초 빈 파일을 성공한 조회로 처리하지 않음 |
| dmesg | 시험 시간대 파일은 빈 파일, 전체 마지막 기록은 01:25:26 USB disconnect | 03:27:48~03:30:18 시험 구간의 오류 원인을 설명하는 기록 없음 |

수집 시각 파일은 03:53:47, 시간 기준 파일은 03:58:33이다. 진단 시점의 통계를 시험 전 통계로 사용하지 않는다. ERROR-ACTIVE라는 현재 상태만으로 과거 오류 여부를 결정하지 않는다.

## 코드와 기존 증거 대조

ECU 실행 버전 `9568d90`의 `adaptive_ecu/src/bsw/can_cdd.cpp`는 스택의 초기화된 can_frame에 ID·DLC·payload를 복사하고 write한다. IVI 004 전달 압축파일의 `hal/socketcan_receiver.cpp`는 read한 프레임을 검증한 뒤 payload를 복사해 callback으로 전달한다. 이 두 경로의 정적 검토에서 payload 비트를 의도적으로 이동하는 연산은 발견하지 못했다. 이 확인은 드라이버·하드웨어 및 전체 런타임 결함이 없다는 증명이 아니다.

기존 공식 시험에서는 IVI 앱이 기록한 이상 payload가 IVI candump에도 존재한다. 따라서 앱의 인증 판정 또는 Qt 지연 CSV 기록만으로 양측 CAN payload 차이를 설명할 수 없다. ECU의 로컬 CAN 기록 역시 물리 버스 파형을 직접 측정한 자료는 아니다. 현재 자료만으로 ECU 송신 측과 IVI 수신 측 중 어느 쪽이 원인인지 확정하지 않는다.

## 다음 진단

ECU에서도 커널 버전, mcp251x 모듈 정보, 현재 CAN 통계, 전체 dmesg, 동일 시험 시간대 journal을 읽기 전용으로 수집한다. 필요하면 그다음 양측 실제 SPI 설정·장치 구성 자료를 대조한다. 현재 자료만으로 키·CAN bitrate·SPI 설정을 바꾸거나 재부팅하지 않는다. 새로운 공식 시험 반복보다 발생 경로를 좁히는 진단을 먼저 수행한다.

**판정: 원인 미확정, 공식 인수 보류 유지.** 로그 부재를 오류 부재로 간주하지 않는다. 이번 작업은 증거 보존·정적 검토이며 신규 장비 시험을 수행하지 않았다.

## ECU 추가 자료 대조 — 04:07 수집

`tmp/perf-formal-001-ecu-diagnostics-20261004-040702`의 8개 파일을 `raw/PERF-FORMAL-001/ecu-diagnostics/`에 복사 보존했다. 누적 inventory는 90개 파일이다.

| 항목 | ECU | IVI | 해석 |
|---|---|---|---|
| 커널 | 6.18.33+rpt-rpi-v8 | 6.18.29+rpt-rpi-v8 | 버전 차이 확인. 원인으로 확정하지 않음 |
| 드라이버 | mcp251x, MCP2515 초기화 성공 | mcp251x, MCP2515 초기화 성공 | 같은 드라이버 이름이나 동일 모듈 구현이라고 단정할 수 없음 |
| CAN 설정 | 500kbps, sample-point 0.750, restart-ms 100, clock 4000000 | 동일 | 조회된 CAN 설정 차이는 없음. 실제 SPI 속도는 이 값으로 알 수 없음 |
| 사후 통계 | TX 16678, TX errors 0 | RX 16678, RX errors 12 | 누적 프레임 수 일치가 payload 일치를 보장하지 않음 |
| 지정 시간대 journal | No entries, 오류 출력 없음 | No entries, 오류 출력 없음 | 양측 모두 원인 설명 로그 미확보 |

ECU 전체 dmesg에서 MCP2515 초기화 성공 메시지를 확인했고 mcp/SPI/CAN0/전압/overflow/overrun 키워드 검색으로 추가 원인 단서를 찾지 못했다. ECU 모듈 srcversion은 `66B01DAB819A3321F6A4714`이다. IVI의 대응 modinfo 자료는 아직 없다.

다음 비교 대상은 양측 mcp251x 모듈 정보와 실제 Device Tree의 spi0.0 설정, 부팅 설정의 CAN/SPI overlay다. 우선 읽기 전용으로 확보하며 커널 업데이트나 SPI 속도 변경은 원인을 확정하기 위한 증거 확보 이후에 판단한다. 커널 버전 차이만으로 업데이트를 해결책이라고 제시하지 않는다.

## IVI 04H16M 실제 설정 확인

원본 압축파일과 내부 6개 파일을 추가 보존했다. 누적 inventory는 97개다. 중첩된 Device Tree 압축파일은 메모리에서 읽어 속성을 확인했다.

- 실제 노드는 `/soc/spi@7e204000/mcp2515@0`이다.
- `spi-max-frequency`는 big-endian 값 `000186a0`, 즉 100000Hz이다. 이는 적용된 최대 주파수 설정이며 실제 신호 주파수를 측정한 것은 아니다.
- `interrupts`는 `[25, 8]`이다.
- `clocks` phandle 247을 전체 적용 트리에서 추적하면 `can0_osc`의 `clock-frequency`가 8000000Hz다. 실제 보드 발진자의 물리 측정값은 아니다.
- 부팅 overlay의 oscillator=8000000, interrupt=25, spimaxfrequency=100000과 위 적용값이 일치한다.
- IVI mcp251x srcversion은 `66B01DAB819A3321F6A4714`로 ECU 자료와 같다. 커널 버전이 다르다는 이유만으로 mcp251x 소스가 다르다고 판단할 근거는 줄었지만, 모듈 바이너리와 전체 커널 동작이 같다는 증명은 아니다.

ECU의 SPI 추가 수집 폴더는 이번 로컬 확인 시 아직 없었다. 따라서 양측 실제 SPI·overlay 설정 비교는 ECU 파일 수령 대기다. 설정 변경·재시험은 수행하지 않았다.

## ECU 04:20 SPI 자료 수령 — 양측 비교 완료

후속 수령한 `ecu-can-spi-diagnostics-20261004-042002`의 파일 6개를 `raw/PERF-FORMAL-001/ecu-can-config/`에 보존했다. 앞 절의 수령 대기는 해소됐으며 누적 증거 파일은 103개다. 수정된 grep 결과 파일의 오류 출력은 비어 있고 Device Tree 속성 조회 결과도 정상적으로 담겨 있다.

| 항목 | ECU 적용값 | IVI 적용값 |
|---|---|---|
| spi-max-frequency | 1000000Hz | 100000Hz |
| 참조 clock-frequency | 8000000Hz | 8000000Hz |
| interrupts | [25, 8] | [25, 8] |
| mcp251x srcversion | 66B01DAB819A3321F6A4714 | 동일 |

양측 모두 부팅 overlay에 적힌 SPI 최대 주파수가 실제 적용 트리와 일치한다. ECU는 1MHz, IVI는 100kHz로 설정 차이가 확인됐지만 실제 신호 파형을 측정하거나 설정을 변경해 비교한 결과는 없다. 따라서 차이가 인증 payload 불일치의 원인이라는 결론은 내리지 않는다. 설정값을 무조건 통일하는 수정은 아직 수행하지 않는다.

다음 단계는 설정을 유지한 상태에서 오류 프레임도 포함하는 양측 캡처와 CAN 전후 통계를 갖춘 짧은 진단 시험을 준비하는 것이다. 공식 성능 인수 시험과 구분하고, 양측 수집 준비 및 담당자 합의 후에만 송신한다. 변화가 생긴 위치를 더 좁힐 수 없다면 별도 CAN 관측 장비나 SPI 신호 계측 가능 여부를 검토한다. 단일 원인으로 좁히지 못한 상태에서 커널·SPI·배선을 동시에 변경하지 않는다.
