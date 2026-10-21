# 실시간 보안 실험과 실장비 인계

기준: [ICD v1.6](../../ICD.md), [TEST_PLAN](../../TEST_PLAN.md), [ECU M5](../../../plan/detail/ecu/M5_Ablation.md), [공동 IT](../../../plan/detail/common/02_통합시험.md). 구현·검증 상태 원본은 [CHG-014](../../aidlc/changes/CHG-014/aidlc-state.md)다.

2026-10-03 사용자 결정: 장비 명령은 사용자가 실행하고 로그를 전달한다. IVI 시험 전용 SecOC OFF·수신 로그는 **IVI 담당자가 구현**한다. 그 인수 전에는 참조 수신기 pilot만 가능하며 물리 제품 인수를 완료로 표시하지 않는다.

## 1. 산출물과 판정 경계

| 도구 | 실행 방법 | 결과 |
|---|---|---|
| 정상 수신 캡처 | `python -m security.experiments.can_capture` | 수신 전용 frames.jsonl + manifest.json; `--normal`은 운영자의 무공격 입력 확인 |
| 정상 평가 | `python -m security.experiments.evaluate_normal` | 독립 평가 캡처의 규칙 / 규칙+IF 오탐, 완전 1초 창·워밍업·빈 창 |
| 실시간 실행 | `python -m security.experiments.live_ablation` | 설정 1개당 별도 ECU/IDS 프로세스, 전체 시행 원장·실제 수신·참조 인증 결과 |
| 실제 결과 집계 | `python -m security.experiments.summarize_live` | 환경·구성·탐지기별 분모, INVALID·미실행·미탐지·지연 초과 |
| MAC fixture | `python -m security.experiments.mac_fixture` | 정상 MAC → 1비트 변조 → 동일 next-counter 정상 복구; 더미 키 전용 |
| ADC 원시 취득 | `adaptive_ecu/build/ads1115_capture` | CAN 무송신, 범위 밖 값도 보존하는 단발 변환 CSV |
| ADC 분석 | `python -m security.experiments.analyze_adc` | 위치별 1,000회 충족·원시 분포·오류·현재 ±32 범위 이탈 |
| Fail-safe 입력 | `adaptive_ecu/data/failsafe_demo.csv` | 실제 ECU CSV→EKF→FSM 경로의 결정적 입력 |

하네스는 별도 프로세스인 ECU·IDS와 같은 호스트에서 SocketCAN을 관측한다. `observer=reference_receiver`의 판정은 Python 참조 수신기 판정이며 실제 IVI 판정이 아니다. 실제 CAN 프레임을 받았더라도 `product_verdict=NOT_RUN`은 IVI 증거 인수 전까지 유지한다. Fuzzy는 유효 범위 밖 데이터 수용을 따로 센다. Flooding은 BMS 전달률을 보고하며 임의 90% 이진 성공 기준을 두지 않는다.

공격 자기 송신은 payload 일치가 아닌 SocketCAN `MSG_CONFIRM`으로 구별한다. 해당 드라이버의 echo 지원과 Node B 캡처를 pilot에서 대조한다. 주입 시각은 같은 호스트의 첫 자기 echo 수신, 경보 종료 시각은 `0x200` 수신이다. 애플리케이션 수신 시각에는 스케줄링·큐 지연이 포함된다. TC-PERF-003 최종 계측에는 송신 로그·echo·수신 지연을 검토하고, UI 지연(TC-INT-004)과 구분한다. [Linux 공식 설명](https://www.kernel.org/doc/html/latest/networking/can.html#returned-message-flags).

## 2. RPi 준비와 시험

저장소 루트, 준비된 Linux/RPi에서 실행한다. 기존 가상환경이 있으면 그대로 사용한다. 새 환경이 필요할 때만 다음 설치를 수행한다.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r security/requirements.txt
```

```sh
cmake -S adaptive_ecu -B adaptive_ecu/build -DECU_BUILD_TESTS=ON
cmake --build adaptive_ecu/build -j2
ctest --test-dir adaptive_ecu/build --output-on-failure
.venv/bin/python -m pytest security/tests -q
ip -details -statistics link show can0
```

GTest·OpenSSL 등 C++ 의존성은 기존 환경 지침을 따른다. CAN bitrate·배선을 도구가 자동 변경하지 않는다. 두 노드의 키는 기존 비공개 배치 경로를 사용하며 내용·해시를 보고서에 붙이지 않는다. 아래 `/etc/secoc/key.bin`은 권한이 있는 기존 키 경로 예다. 권한 오류를 만나면 노드의 기존 실행 사용자·키 배치 정책을 적용한다.

## 3. 정상 캡처와 IF (EXQ-4·TC-EXP-005)

Node A 터미널 1에서 정상 ECU를 실행한다. 공격 주입기는 실행하지 않는다. ADS1115 실측 모드를 평가할 경우 `constant`를 `ads1115`로 바꾸고 두 캡처의 조건에 기록한다.

```sh
./adaptive_ecu/build/adaptive_ecu --interface can0 --sensor-mode constant --secoc on --key /etc/secoc/key.bin
```

Node A 터미널 2에서 서로 겹치지 않는 학습·평가 구간을 수집한다. 예제 출력 디렉터리가 이미 있으면 새 이름을 쓴다.

```sh
.venv/bin/python -m security.experiments.can_capture --channel can0 --environment physical --duration 150 --normal --out tmp/normal-train-01
.venv/bin/python -m security.experiments.can_capture --channel can0 --environment physical --duration 150 --normal --out tmp/normal-eval-01
.venv/bin/python -m security.experiments.evaluate_normal tmp/normal-eval-01 --train tmp/normal-train-01 --key /etc/secoc/key.bin --out tmp/normal-evaluation-01.json
```

2초 워밍업 이후 완전한 1초 창만 사용한다. 빈 창·수신 손실·중단 캡처는 판정 불가이며 제거해서 분모를 늘리지 않는다. ANOMALY가 있는 정상 창을 오탐으로 센다. 규칙과 IF 병용 결과를 각각 보고하고, 같은 파일/내용을 학습과 평가 양쪽에 쓰면 거부한다. IF 학습은 기존 `train_model`과 고정 random_state=42를 사용한다. IF 단독 진단을 임의의 wire 공격 유형으로 바꾸지 않는다.

전달할 파일: 두 디렉터리의 manifest.json·frames.jsonl, normal-evaluation-01.json, ECU·IVI 커밋과 실행 모드. 캡처에는 payload/MAC/counter가 포함되며 키 내용은 포함하지 않는다.

## 4. vcan pilot → 물리 pilot → 본 실험

vcan 지원 Linux/RPi에서 기존 `vcan0` 상태를 먼저 확인한다. 없을 때만 `sudo modprobe vcan`, `sudo ip link add dev vcan0 type vcan`, `sudo ip link set vcan0 up`을 각각 실행한다. 오류를 숨기지 않는다. CHG-014 로컬 WSL에는 모듈이 없어 이 검증을 대신할 수 없다.

기존 ECU·IDS를 해당 터미널에서 종료한다. 하네스는 다른 프로세스를 죽이지 않고, 이미 트래픽이 있는 버스에서는 시작을 거부한다. 각 구성은 독립 시험 인스턴스이며 실행 시작 시 ECU counter가 새로 시작한다. IVI 담당자는 이 구성에 대응하는 **독립 시험 수신 인스턴스**를 준비한다. 일반 오류 복구를 위해 제품 counter를 초기화하는 절차가 아니다. 시행 사이에는 같은 프로세스와 counter 이력을 유지한다.

먼저 vcan에서 세 구성을 각 1회씩 실행한다. 예제는 Config 2다. 키는 로컬 fixture용 키를 사용한다. Config 1은 `--config 1`이며 인증이 꺼진다. Config 3은 `--config 3 --train <정상 캡처 디렉터리>`를 추가한다. IF 준비 전 개발 pilot은 `--rules-only`로 명시하며 EXQ-4 완료로 세지 않는다.

```sh
.venv/bin/python -m security.experiments.live_ablation --channel vcan0 --environment vcan --config 2 --trials 1 --rate 1000 --duration 3 --key /etc/secoc/key.bin --ecu adaptive_ecu/build/adaptive_ecu --run-id pilot-vcan-01 --out tmp/pilot-vcan-c2-01
```

실제 두 RPi 격리 버스에서의 Config 3 pilot:

```sh
.venv/bin/python -m security.experiments.live_ablation --channel can0 --environment physical --config 3 --trials 1 --rate 1000 --duration 3 --key /etc/secoc/key.bin --ecu adaptive_ecu/build/adaptive_ecu --train tmp/normal-train-01 --ivi-run-id pilot-ivi-c3-01 --i-am-on-a-test-bus --run-id pilot-physical-01 --out tmp/pilot-physical-c3-01
```

1000fps는 pilot 시작 설정이지 TC-SEC-005-d 부하 충족값이 아니다. 아래 버스 부하 측정으로 강도를 확인·사전 고정한다. rate·duration·입력·센서 모드·IF 학습 자료는 본 평가에서 고정하고 평가 결과를 보고 임계를 재조정하지 않는다. 5000fps/120초 상한은 입력 오류 방지 상한이며 물리 달성 보증이 아니다.

본 실험은 케이스(구성×공격)별 독립 run ID/출력 경로로 실행한다. `--attack` 하나씩 순차 수집해도 전체 12조건을 연결하면 본 실험이다. 사용자 결정 DEV-EXP-001에 따라 `--trials 100 --continue-invalid`로 계획 번호를 수집하며 INVALID는 보존하고 자동 보충하지 않는다. 기존 TEST_PLAN의 100유효 목표와 차이는 [방법·편차](../experiments/physical-ablation-formal-2026-10-04/METHODS-AND-TRACEABILITY.md)에 명시한다. 재개는 새 run ID, `--start-trial`, `--previous-run-id`로 연결한다. C1/C2에는 학습 옵션을 넣지 않고 C3는 독립 fit/calibration을 지정한다.

```sh
.venv/bin/python -m security.experiments.summarize_live tmp/full-c1-01 tmp/full-c2-01 tmp/full-c3-01 --out tmp/full-summary-01.json
```

실행마다 manifest.json, attempts.jsonl, warmup.jsonl, 공격별 원시 JSONL, ECU 로그, Config 3의 IDS 로그를 보존한다. 판정된 INVALID는 `--continue-invalid` 사용 시 원장에 남기고 다음 번호로 진행한다. 소유 프로세스 종료·버스/시각 오류처럼 실행 자체가 불가능한 예외는 기록 후 중단한다. 옵션이 없으면 INVALID 시 중단한다. 미탐지는 유효한 실패 결과이며 지연 0으로 바꾸지 않는다. SIGINT/SIGTERM 시 소유 프로세스를 종료·회수한다. IVI는 외부 프로세스이므로 하네스가 종료하지 않는다.

## 5. 물리 버스 점유율 (TC-SEC-005-d)

실제 can0가 500kbps인지 먼저 확인하고, 설치된 can-utils의 도움말에서 옵션을 확인한다. Node B 별도 터미널에서 다음처럼 수신 기반 부하를 기록한다.

```sh
canbusload -t -e can0@500000 | tee tmp/busload-01.log
```

`-e`는 캡처 프레임 내용·CRC 기반 bit stuffing 계산이다. [can-utils 공식 소스](https://github.com/linux-can/can-utils/blob/master/canbusload.c). 실제 캡처 기반 계산이며 오실로스코프 측정과 동일하지 않다. 실제 bitrate·도구 버전·오류/유실 카운터·완전한 1초 공격 구간·시계 대응을 함께 남긴다. 시작/종료 경계가 섞인 1초 행을 골라 통과시키지 않는다. 최악 stuffing 계산이나 송신 설정 fps만으로 50% 달성을 주장하지 않는다. 오류 프레임·재송신·캡처 손실이 있으면 원인을 기록하고 최종 부하 인수를 보류한다.

## 6. IT-004 MAC fixture

IVI 담당자는 독립 시험 수신기를 준비하고 기존 ECU·IDS 송신을 중지한다. 실제 운영 키를 교체하지 않는다. 다음 명령은 **공개된 더미 키**만 새 파일로 생성한다. 생성 파일을 비공개 절차로 상대에게 전달할 필요는 없지만 운영용 키로 사용해서는 안 된다.

```sh
.venv/bin/python -m security.experiments.mac_fixture --prepare-key tmp/it004-dummy.bin
```

Node B의 독립 시험 실행에서 이 더미 키를 사용한다. 수신 이력·counter 시작값을 알려진 상태로 준비한 뒤 Node A에서 실행한다.

```sh
.venv/bin/python -m security.experiments.mac_fixture --channel can0 --environment physical --counter-start 0 --i-am-on-a-test-bus --out tmp/it004-01
```

관측 순서는 정상 counter=0 수용 → next counter=1의 MAC 1비트 변조 거부 → **같은 counter=1**의 정상 데이터 수용이다. 정상/변조 raw는 서로 다르다. 원본→auth는 연속 송신되며 실제 수신에서 100ms pending 조건을 확인한다. 외부 송신·orphan·만료·counter 오류로 거부되면 성공으로 세지 않는다. 참조 결과 외에 IVI MAC 실패 사유, 변조값 미반영, counter 미소비, 정상 갱신 복구와 화면 증거가 있어야 IT-004 인수 가능하다. fixture 종료 후 팀의 원래 실행 설정으로 복귀한다.

## 7. IT-002 프로파일과 EXQ-10

ECU 기본 설정은 유지했다. [프로파일 manifest](../../../adaptive_ecu/data/failsafe_demo.manifest.json)에 입력 단위·EKF 설정·CSV 마지막 행 유지와 실제 호스트 시험 전이를 기록했다. 모델 시간은 물리 UI 지연이 아니다.

```sh
./adaptive_ecu/build/adaptive_ecu --interface can0 --secoc on --key /etc/secoc/key.bin --sensor-mode profile_csv --profile adaptive_ecu/data/failsafe_demo.csv
```

ECU 로그·`0x101`/`0x103`·IVI 인증/화면을 함께 남긴다. 별도 노브 경로의 10초 이상 간격 이벤트 수락 시험도 유지한다.

EXQ-10은 ECU와 다른 ADC 사용자를 정지하고, 가변저항을 가운데/3.3V 끝으로 각각 고정해 수집한다. `set -C`는 기존 CSV 덮어쓰기를 막는다.

```sh
set -C
./adaptive_ecu/build/ads1115_capture --count 1000 > tmp/adc-middle-01.csv
.venv/bin/python -m security.experiments.analyze_adc tmp/adc-middle-01.csv --position middle --out tmp/adc-middle-01.json
./adaptive_ecu/build/ads1115_capture --count 1000 > tmp/adc-high-01.csv
.venv/bin/python -m security.experiments.analyze_adc tmp/adc-high-01.csv --position high --out tmp/adc-high-01.json
```

두 CSV/JSON과 위치·전원·배선 조건을 전달한다. 이 도구는 범위 밖 raw를 버리지 않으며 CAN을 송신하지 않는다. 분석 결과만으로 제품 ±32 허용값을 자동 변경하지 않는다.

## 8. 제출 표

합성 표는 `summarize_ablation.py`의 environment 열을 사용한다. `analyze_roc.py`가 만드는 `detector_reference.csv`는 masquerade **참고 표**이며 공식 4종·3구성 표에 합산하지 않는다. 단일 run 진단은 `summarize_live`, 실제 재개·버전별 논문 집계는 [publication 재현 절차](../experiments/physical-ablation-formal-2026-10-04/REPRODUCE.md)를 사용한다. 탐지율의 시행 분모와 ROC/오탐의 윈도우 분모를 혼합하지 않는다. 물리 미측정 칸은 미측정으로 남긴다. 계획 번호 수집 완료와 원래 유효100회 기준 충족을 분리하며 미충족 조건을 PASS로 바꾸지 않는다.

IVI 인계: [시험 모드·관측 계약](../security/IVI_실험_인계.md).

## 2026-10-04 v8 장기 실행 보완

현재 실행기는 소유 IDS 수명을 부모 프로세스에 연결하고 누적 IDS 로그를 증분 처리한다. 공격 관측 프레임 시각은 커널 SO_TIMESTAMPNS_NEW의 고정 monotonic 매핑이며 기존 dequeue 시각과 버전을 구분한다. `--continue-invalid`는 판정된 INVALID를 보존하고 다음 계획 시행으로 진행한다. 실제 프로세스 종료·버스 오류·시각 오류는 중단한다. 이전 C3 delivery_ratio 이상은 원본 보존 후 양측 CAN 로그로 재분석한다. [002 보고서](../experiments/physical-ablation-formal-2026-10-04/reports/ABLATION-FORMAL-C3-FLOOD-002.md).
