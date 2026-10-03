# 물리 CAN 보안 통합 실행 절차

대상은 두 Raspberry Pi만 연결된 승인된 캡스톤 시험버스다. 정상 BMS/SecOC 증거, IT-004 MAC 변조 차단, IT-005 IDS 경보를 같은 계약(ICD v1.6)으로 분리 수행한다. 합성·`vcan` 결과를 물리 CAN 결과로 표시하지 않는다.

## 1. 전원·배선 안전

- 배선, 종단저항, MCP2515 전원, CANH/CANL을 바꿀 때는 두 노드 전원을 모두 끈다. 전원이 켜진 상태에서 ADS1115나 CAN 배선을 뽑지 않는다.
- 전원 OFF에서 버스 양 끝 120Ω 종단 두 개의 병렬값이 약 60Ω인지 확인한다. 모듈 내장 종단 여부와 측정 오차를 함께 기록한다.
- CANH↔CANH, CANL↔CANL, 공통 GND, 모듈 발진자 8MHz, 양측 500kbit/s를 대조한다.
- 공격 도구는 차량·사내망·공용 CAN에 연결하지 않는다. 물리 실행은 `--confirm-isolated-test-bus`가 없으면 실패한다.

## 2. 정상 회로·통신 증거

Node A와 Node B에서 각각 다음을 캡처한다.

```bash
git -C ~/Capstone-proj rev-parse --short HEAD
ip -details -statistics link show can0
```

Node B에서 60초 원시 로그를 저장한다. ECU와 대시보드는 정상 실행하고 노브는 중간에 고정한다.

```bash
candump -L -n 1200 can0 > ~/can-normal-1200.log
```

`0x100` 직후 `0x102`, 연속 counter, UI `LIVE/NORMAL`, 종료 뒤 `ERROR-ACTIVE`, bus-off·drop 0을 확인한다. 파일이 생겼다는 사실만으로 100ms±10ms 공식 성능을 통과 처리하지 않고 원시 로그 분석 결과를 별도로 남긴다.

캡처 직전·직후 `ip -details -statistics link show can0`에서 RX errors, RX dropped, bus-off 누적값을 적는다. 아래 예시는 모두 0이었던 한 번의 부팅을 뜻한다. 실제 관측값으로 바꾸고 `RUN_ID`와 `BOOT_ID`는 해당 실행에서 유일하게 정한다.

```bash
cd ~/Capstone-proj
python3 ivi_platform/scripts/normalize_candump_period.py \
  --input ~/can-normal-1200.log \
  --output ~/period-001.csv \
  --manifest ~/period-001.manifest.json \
  --run-id PERIOD-PHYSICAL-001 --boot-id NODE-B-BOOT-001 \
  --interface can0 \
  --rx-errors-before 0 --rx-errors-after 0 \
  --rx-dropped-before 0 --rx-dropped-after 0 \
  --bus-off-before 0 --bus-off-after 0

python3 ivi_platform/scripts/analyze_period.py \
  --input ~/period-001.csv \
  --manifest ~/period-001.manifest.json \
  --output ~/period-001.result.json
```

분석기는 `0x100` 101개 이상, 모든 연속 간격 90~110ms, 캡처 중 오류·drop·bus-off 불변일 때만 PASS한다. 표본 부족·손상·통계 변화는 INVALID, 유효 캡처의 범위 이탈은 FAIL이다. 기존 결과 경로는 덮어쓰지 않는다.

### 2.1 결정적 Fail-safe 전이 재시험

노브 수동 시험과 별개로 아래 profile은 WARNING과 CRITICAL 사이를 약 12.9초 벌려 `0x103` 독립 counter 전이를 확실히 관찰한다. ECU·대시보드를 모두 종료하고 노브를 정상 범위로 돌린 뒤, ECU를 먼저 시작하고 대시보드를 새로 시작한다.

```bash
cd ~/Capstone-proj
sudo ./adaptive_ecu/build/adaptive_ecu \
  --interface can0 --secoc on --key /etc/secoc/key.bin \
  --sensor-mode profile_csv \
  --profile adaptive_ecu/data/failsafe_demo.csv
```

Node B에서 `candump -L can0,100:7FF,101:7FF,102:7FF,103:7FF`와 화면을 함께 기록한다. 기대값은 NORMAL→WARNING `0x101/0x103`, 10초가 넘은 뒤 WARNING→CRITICAL `0x101/0x103`이며 CRITICAL은 재시작 전까지 latch된다.

## 3. IDS 정상 학습 입력 수집

Node A에서 공격이 전혀 없는 정상 구간을 먼저 확인하고 새 경로를 사용한다. 기존 파일은 덮어쓰지 않는다.

IDS의 Isolation Forest를 처음 실행하는 장비라면 저장소 전용 가상환경을 한 번 준비한다. 이후 `sudo python3` 대신 같은 가상환경의 Python을 명시해 root 실행 때 다른 패키지 환경이 선택되지 않게 한다.

```bash
cd ~/Capstone-proj
python3 -m venv .venv
.venv/bin/python -m pip install -r security/requirements.txt
```

```bash
cd ~/Capstone-proj
.venv/bin/python -m security.capture_normal \
  --interface can0 --duration 30 \
  --output ~/ids-normal.jsonl \
  --manifest ~/ids-normal.manifest.json
```

manifest의 accepted/rejected 수와 capture SHA-256을 보존한다. 정상성은 운영자가 dump와 CAN 오류 통계로 확인하며 도구가 자동 보증하지 않는다.

## 4. IT-004 — MAC 1비트 변조 차단

이 시험은 제품 ECU와 fixture가 같은 ID를 동시에 송신하면 무효다.

1. Node A 제품 ECU를 `Ctrl+C`로 완전히 종료한다.
2. Node B 대시보드를 재시작해 counter 이력이 없는 시험 인스턴스를 만든다.
3. Node B에서 `candump -td can0`를 시작한다.
4. Node A에서 다음을 실행한다.

```bash
cd ~/Capstone-proj
sudo .venv/bin/python -m security.secoc_tamper_fixture \
  --interface can0 --key /etc/secoc/key.bin --counter-start 0 \
  --inter-pair-delay 1 \
  --confirm-ecu-stopped --confirm-receiver-reset \
  --confirm-isolated-test-bus \
  --log ~/it004-tamper.json
```

기대 순서는 인증된 SOC 75% 게시 → 위조 SOC 100% 미게시 및 MAC 실패 1회 → 실패가 counter를 소비하지 않아 같은 counter의 정상 SOC 70% 게시다. 화면 전체 정지, orphan auth, pending timeout, counter 거부는 MAC 변조 합격 증거가 아니다. 시험 후 노브를 정상 범위에 두고 ECU를 먼저 시작한 뒤 대시보드를 재시작한다.

## 5. IT-005 — 실시간 IDS와 0x200

Node A에서 정상 캡처를 명시적으로 학습해 IDS를 시작한다.

```bash
cd ~/Capstone-proj
sudo .venv/bin/python -m security.ids.runtime \
  --interface can0 \
  --train-normal ~/ids-normal.jsonl \
  --normal-manifest ~/ids-normal.manifest.json \
  --secoc-key /etc/secoc/key.bin \
  --log ~/it005-ids.jsonl \
  --run-id IT005-PHYSICAL-001 --ready-file ~/it005-ready.json \
  --duration 30 --send-alerts
```

공격자 역할 노드의 별도 터미널에서, IDS와 Node B 캡처 준비 완료를 확인한 뒤 제한형 CLI를 실행한다. 아래 명령은 격리된 물리 시험버스 전용이다.

```bash
cd ~/Capstone-proj
sudo .venv/bin/python -m security.attack_simulator \
  --type flooding --channel can0 --duration 3 \
  --run-id IT005-PHYSICAL-001 --trial 0 \
  --confirm-isolated-test-bus \
  --log ~/it005-attack.json
```

READY JSON의 run ID와 `mode=rules+if`를 확인하기 전에는 공격을 시작하지 않는다. 정상 캡처는 3초 이상, 두 ID 각각 25개 이상이며 300ms 공백·오염·hash 불일치가 있으면 학습하지 않는다.

Node B에서는 첫 실제 공격 수신 시각, 첫 `0x200` 수신, AlertBanner 완전 표시를 같은 run ID로 기록한다. IDS 로그의 `ALERT_SENT`, `attack_type=4`, dump의 `0x200`, 화면의 Flooding 배너를 모두 확인한다. 공격 도구의 TX_ACCEPTED 시각은 소켓 송신 수락 시각이지 실제 버스 주입 시각이 아니다. Node A와 Node B의 monotonic 값을 서로 빼지 않는다. 요청률이나 송신 프레임 수만으로 버스 점유율 또는 3초 지연을 추정하지 않는다.

## 6. 종료·복구

- 공격·IDS 프로세스를 종료하고 남은 중복 프로세스가 없는지 확인한다.
- 양측 `ip -details -statistics link show can0`를 다시 저장한다.
- 정상 ECU의 `0x100/0x102`와 IVI 갱신이 재개됐는지 확인한다.
- bus-off, drop, 송신 오류, UI 미복구가 있으면 해당 run을 실패/INVALID로 보존하고 정상 결과로 덮어쓰지 않는다.
