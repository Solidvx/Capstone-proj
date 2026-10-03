# M5 실행 하네스 — 파일럿부터 공식 평가까지

2026-10-03: Linux vcan 실행 경로 구현. 물리 1,200회 결과나 보안 인수 완료 기록이 아니다.

## 합성 도구 분리 — PR #21 구현 보존

최신 develop 통합 시 초기 합성 CLI와 후속 물리 러너의 파일명이 겹쳤다. 초기 구현은 아래 이름으로 보존한다. `ablation_core.py`·기존 회귀시험은 그대로 유지한다. 기존 `run_ablation.py`/`summarize_ablation.py`/`analyze_roc.py`는 후속 managed run·원장·독립 캡처 분석용이며, 아래 합성 결과와 섞지 않는다.

```bash
python3 security/experiments/run_ablation_synthetic.py --out tmp/NEW-synthetic.csv
python3 security/experiments/summarize_ablation_synthetic.py tmp/NEW-synthetic.csv
python3 security/experiments/analyze_roc_synthetic.py --out-dir tmp/NEW-synthetic-roc
```

합성 ROC 출력 디렉토리는 새로 준비한다. 초기 WSL 측정과 후속 로컬 IF 후보 `NO_FEASIBLE_THRESHOLD`는 서로 다른 탐지기/자료의 결과다. 합성 1,200행은 물리 1,200회 인수 완료가 아니다.

## 구성과 안전 경계

| 구성 | 시험 수신기 | IDS |
|---|---|---|
| 1 | 별도 `ivi_dashboard_experiment`, 인증 OFF | OFF |
| 2 | 같은 시험 바이너리, 인증 ON | OFF |
| 3 | 같은 시험 바이너리, 인증 ON | 실제 정상 캡처로 학습한 rules+IF |

정상 송신은 모든 구성에 같은 signed SOC75 fixture를 보낸다. 인증·IDS 외 입력 차이를 줄이기 위한 실험이다. 제품 ECU를 함께 실행하면 안 된다. 이 결과를 제품 ECU 자체의 성능·실시간 방어 결과로 대신하지 않는다. 기본 제품 빌드는 인증 OFF를 허용하지 않는다.

```bash
cmake -S ivi_platform -B ivi_platform/build-experiment \
  -DIVI_BUILD_EXPERIMENT_TOOLS=ON
cmake --build ivi_platform/build-experiment -j2
```

## 1. Linux 가상 CAN smoke

사용하지 않는 전용 vcan 인터페이스를 먼저 준비한다. 다음 명령은 물리 can0에서 실행할 수 없으며 임시 dummy key를 생성한다. 제품 송신·수신 프로세스를 전용 인터페이스에 붙이지 않는다.

```bash
sudo ip link add dev vcan91 type vcan
sudo ip link set vcan91 up
python3 -m security.experiments.vcan_review_smoke \
  --interface vcan91 \
  --receiver-bin "$PWD/ivi_platform/build-experiment/ivi_dashboard_experiment"
```

학습용 정상 캡처→MAC 변조/회복·silent pending 만료→3구성×4공격 각 1회→원본 로그 hash 검증→집계 순서다. 출력 `artifact_dir`에 로그가 남는다. `matrix_complete=true`는 12회 수집 완결성이지 방어 합격 판정이 아니다. 짧은 smoke의 flooding은 1,000fps 소프트웨어 연결 검증이며 실제 버스 부하 시험이 아니다.

## 2. 장비 설정 파일

하네스는 `--settings` JSON의 `observer`, `receiver_on`, `receiver_off`, `normal_sender`, `ids`를 **argv 배열**로 받는다. 셸 문자열을 자동 추정하지 않는다. smoke가 남긴 settings.json을 형식 예제로 사용하되 dummy key와 `/tmp` 경로는 실제 승인된 장비 경로로 바꾼다.

- `{run_id}`, `{lifetime_s}`, `{lifetime_ms}`, `{secoc}`를 지원한다. `{secoc}`는 입력 동일성 때문에 항상 `on`이다.
- observer: `python -m security.experiments.bus_observer --interface can0 --run-id {run_id} --duration {lifetime_s}`.
- receiver_on: 시험 바이너리 `--interface can0 --secoc-key KEY --run-id {run_id} --observation-jsonl - --demo-exit-ms {lifetime_ms}`.
- receiver_off: receiver_on에 `--experiment-secoc-off --confirm-isolated-test-bus` 추가.
- normal_sender: `python -m security.experiments.normal_sender --interface can0 --secoc on --key KEY --run-id {run_id} --duration {lifetime_s} --confirm-isolated-test-bus`.
- ids: `python -m security.ids.runtime --interface can0 --train-normal CAPTURE --normal-manifest MANIFEST --secoc-key KEY --run-id {run_id} --log UNIQUE_PATH --duration {lifetime_s} --send-alerts`.

물리 실행은 Node A에서 한다. observer와 두 receiver 명령은 **같은 Node B로 SSH**해야 하며 `observer_receiver_same_node: true`를 명시한다. 원격 명령은 lifetime placeholder를 포함한 실제 유한 종료 옵션을 사용한다. SSH 종료만으로 원격 자원 회수를 보장하지 않으므로 시행 후 양측 프로세스를 점검한다. 키·학습 capture/manifest·바이너리 hash, sklearn 버전, 모델·규칙 설정을 공식 시행 전에 보존·동결한다. 설정 파일에는 키 내용이 아닌 경로만 넣는다.

## 3. 물리 파일럿 → 동결 → 공식 시행

먼저 양측 동일 키, 500kbit/s, `ERROR-ACTIVE`, 중복 송신 없음, 정상 입력과 인증 쌍, Node B UI를 확인한다. 정상 학습 데이터는 [통합 절차](security-can-integration.md)의 capture_normal로 새로 수집한다. calibration과 최종 정상 평가 로그를 분리한다.

```bash
python3 -m security.experiments.run_ablation \
  --settings results/m5-settings.json \
  --output-dir results/m5-physical-pilot-001 \
  --run-id M5-PHYSICAL-PILOT-001 \
  --environment physical-can --interface can0 --trials 1 \
  --confirm-product-ecu-stopped --confirm-isolated-test-bus

python3 -m security.experiments.summarize_ablation \
  --input-dir results/m5-physical-pilot-001 \
  --output results/m5-physical-pilot-001.summary.json
```

준비→정상 baseline→Config 3 IDS READY+warmup→제한 공격→고정 평가 구간→종료→drain→cooldown 순서다. 기존 output/log/summary는 덮어쓰지 않는다. 원본 손상·준비 실패·프로세스 중단은 INVALID로 보존한다. 미탐은 유효 시행의 검출 실패이며 지연 0으로 바꾸지 않는다. 시행별 result와 attempts 원장·artifact SHA256을 대조하고, 같은 seed의 구성 간 실제 공격 입력 hash도 확인한다.

파일럿에서 단계 길이·공격률·장비 상태를 확정한 뒤 **새 output-dir/run-id**로 `--trials 100`을 실행한다. `--flood-rate` 기본 3,000fps는 calibration 후보이지 확정 실측값이 아니다. 구성 간 실제 송신량/hash가 다르면 비교 완료로 인정하지 않고 원인을 조사한다. 하네스 최대 물리 공격 시간은 시행당 10초이며 bounded source rate가 실제 버스 점유율을 증명하지 않는다.

## 계측 해석과 남은 인수 조건

- `attack_success`: 실제 수신기 게시/정상 전달 결과, `blocked`: 대응되는 인증 거부 로그, `detected`: Node B의 0x200 관측으로 각각 독립 집계한다. 파서 거부는 SecOC 차단이 아니다.
- 인증 프레임 거부와 timer의 pending 만료를 원래 raw 입력에 대응시킨다. pending 입력 덮어쓰기·버스 유실은 인증 거부로 추정하지 않는다. MAC 변조는 IT-004의 baseline→MAC_FAIL→recovery로 별도 인수하며 공식 차단율은 요구사항별 원본 증적과 함께 판단한다.
- 검출은 평가 구간의 IDS alert 관측이다. 공격 유형 분류 정확도·정상 오탐·ROC 평가는 별도 정상 window/혼동행렬로 산출한다.
- 지연은 같은 Node B observer의 첫 공격 수신→첫 alert 수신이다. 송신기 소켓 수락 시간과 다른 노드 시간을 빼지 않는다. UI 완전 표시 지연과 물리 bus load는 미측정 `null`이다.
- `official_1200_complete`도 시행 완결성만 뜻한다. 물리 버스 점유율, UI 표시 지연, 정상 오탐/ROC, 재부팅·CRITICAL 복구, 제품 ECU 처리량 증거를 함께 인수해야 최종 완료다.
