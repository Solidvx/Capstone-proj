# CHG-013 — 초기 합성 실험과 후속 물리 통합 기록

서로 다른 작업 환경의 기록을 합쳐 보존한다. 아래 각 절의 실행 환경·시점·판정 범위를 섞지 않는다. 초기 PR #21의 합성 CLI는 `security/experiments/*_synthetic.py`로 보존했고, 원래 파일 이름은 후속 물리 실행/독립 캡처 분석 도구가 사용한다. 초기 실행 명령은 당시 이력이며 현재 재현 명령은 [M5 안내](../../../development/playbooks/m5-ablation-runner.md)의 합성 도구 분리 절을 따른다.

## 초기 합성 실험 — PR #21 기록

# CHG-013 검증 증거

2026-10-03, 브랜치 `feat/ecu-ablation`(기준 `develop` `6bf9688`), WSL2 Ubuntu x86_64, Python 3.12 가상환경(`~/venvs/capstone-security`).

## 단위 시험

```bash
python -m pytest security/tests -q
```
34 passed(기존 25 + 신규 9: `test_attack_simulator` 3, `test_ablation_core` 6). 공격 안전 게이트(vcan 허용·실 can 확인 필요·rate/duration 상한·프레임 형상·결정성), Ablation 판정(spoofing/replay의 Config별 차단·성공, 탐지는 Config 3에서만, 탐지≠차단, 합성 미측정 공백)을 확인했다.

## Ablation 합성 사전검증 (등급: synthetic)

```bash
python security/experiments/run_ablation.py --out tmp/ablation_synth.csv
python security/experiments/summarize_ablation.py tmp/ablation_synth.csv
```
1,200행(3구성×4공격×100회) 생성. 원시 CSV는 `.gitignore` 대상 `tmp/`에 둔다.

| Cfg | attack | total | success(측정) | block% | detect% |
|---|---|---|---|---|---|
| 1 | flooding | 100 | 미측정 | 0 | 0 |
| 1 | fuzzy | 100 | 미측정 | 0 | 0 |
| 1 | replay | 100 | 100/100 (100%) | 0 | 0 |
| 1 | spoofing | 100 | 100/100 (100%) | 0 | 0 |
| 2 | flooding | 100 | 미측정 | 0 | 0 |
| 2 | fuzzy | 100 | 미측정 | 52 | 0 |
| 2 | replay | 100 | 0/100 (0%) | 100 | 0 |
| 2 | spoofing | 100 | 0/100 (0%) | 100 | 0 |
| 3 | flooding | 100 | 미측정 | 0 | 100 |
| 3 | fuzzy | 100 | 미측정 | 52 | 100 |
| 3 | replay | 100 | 0/100 (0%) | 100 | 100 |
| 3 | spoofing | 100 | 0/100 (0%) | 100 | 100 |

해석: 무방어는 spoofing·replay가 100% 성공하고, SecOC는 두 공격을 100% 차단하며, IDS(Config 3)는 네 공격을 모두 탐지한다. flooding은 SecOC가 차단하지 못하지만(0%) IDS가 탐지(100%)해 "탐지≠차단"을 보여준다. fuzzy의 block 52%는 임의 ID 중 0x100에 맞은 프레임이 인증 거부된 trial 비율이다.

Config 3의 IDS는 실시간 탐지기 `security.ids.runtime_detector`의 규칙(기본 `Config()`: 최소 주기 50ms, 초당 100프레임 등 시험용 초기값)이다. 탐지는 **시행 단위**(공격 시행 중 ANOMALY 1건 이상)로 셌다. 정상 구간만 넣은 이 탐지기의 오탐은 아직 측정하지 않았다. 아래 ROC는 다른 탐지기(오프라인 규칙 베이스라인)의 윈도우 단위 결과다.

## ROC·임계·정상 오탐 (등급: synthetic)

대상은 오프라인 규칙 베이스라인(`rule_baseline.RuleBaseline`, 윈도우 단위 z-score)이다. Ablation Config 3의 실시간 IDS와 다른 탐지기다. NFR-SEC-003(공식 4종 각각 ≥90%)과 NFR-SEC-004·TC-EXP-005(정상 오탐 ≤5%)를 공식 4종으로 판정하고, 공식 외 masquerade는 참고로 분리했다. 선정 seed(42·43·44)와 평가 seed(142·143·144)를 분리했다.

```bash
python security/experiments/analyze_roc.py --out-dir tmp
```
- 공식 4종 ROC-AUC(선정 seed) = 1.000
- 확정 임계 = 2.536(선정 seed에서 정상 오탐 ≤5%인 가장 낮은 임계)
- 평가 seed: 정상 오탐 3.9%(분모 180 윈도우, ≥100), flooding·fuzzy·replay·spoofing 각 100.0% → 기준 충족(합성)
- 참고(공식 외): masquerade 탐지는 규칙 0.0%, 사양기반 100.0%(사양기반 정상 오탐 0.0%)
- matplotlib 미설치로 ROC 그래프 PNG는 생성하지 않고 `tmp/roc_points.csv`만 남겼다. 필요 시 `pip install matplotlib` 후 재실행하면 PNG가 생성된다.

**정정(2026-10-03)**: 처음 버전은 공식 실험 대상이 아닌 masquerade까지 넣어 ROC를 계산해 "ROC-AUC 0.872, TPR≥90%·FPR≤5% 동시 만족점 없음, 임계 3.428, 정상 오탐 1.1%"로 기록했다. NFR-SEC-003은 공식 4종 공격별 기준이므로 공식 4종으로 다시 판정하고 masquerade를 분리했다. 앞선 "목표 미달" 서술은 분석 범위의 오류였다.

## 미실행 (물리 등급 과제)

- 두 RPi 물리 CAN에서의 1,200 최종 판정. `attack_simulator.py`로 실제 주입, 수신 측 관측으로 flooding·fuzzy 가용성·수용까지 측정.
- TC-SEC-005-d 버스 점유율 ≥50% 실측(캡처 기반).
- 실시간 IDS 실장비: `python -m security.ids.runtime --interface can0 --rules-only --log live.jsonl --send-alerts`로 0x200 송신, IVI 경보 배너와 TC-PERF-003(공격 시작→경보 ≤3초).
- 합성 결과를 물리 CAN 최종 인수로 표시하지 않는다.

---

## 후속 물리 통합 도구 — 로컬 기록

# CHG-013 검증 증거

2026-10-03, macOS arm64, 브랜치 `develop`, 기준 commit `6bf9688`.

## 로컬 검증

```bash
python3 -m unittest security.tests.test_attack_tools security.tests.test_runtime_ids -v
PYTHONPYCACHEPREFIX=/tmp/capstone-pycache python3 -m compileall -q security
python3 -m security.attack_simulator --help
python3 -m security.capture_normal --help
python3 -m security.secoc_tamper_fixture --help
python3 -m unittest ivi_platform.test.test_period_analysis -v
cmake -S adaptive_ecu -B /tmp/capstone-ecu-build-no-tests -DECU_BUILD_TESTS=OFF
cmake --build /tmp/capstone-ecu-build-no-tests --target adaptive_ecu -j2
```

- 신규 공격·변조 및 기존 runtime 회귀 15건, 주기 정규화·분석 회귀 4건 통과.
- 4종 frame 형식·결정적 fuzzy seed·replay 동일 payload·spoof SOC raw 200·flood ID/payload를 확인했다.
- 물리 인터페이스 명시 확인, 10초·4,000fps 상한, replay payload 검사, 키/counter 경계를 확인했다.
- IT-004 fixture의 bad MAC counter가 정상 복구에서 재사용되고 정상 MAC이 유효함을 독립 계산했다.
- cooldown 중 먼저 발생한 Fuzzy 증상 뒤 Flooding 분류가 유실되지 않고 bounded pending 1개로 전송 대기하는 회귀를 추가했다.
- Python 전체 문법 검사와 세 CLI help가 통과했다.
- 주기 분석은 90/110ms 포함 경계 PASS, 단일 110.1ms 이탈 FAIL, 짧거나 손상된 캡처 INVALID, 상대/verbose/역행 timestamp 거부를 확인했다.
- 결정적 Fail-safe profile을 독립 계산해 310표본, WARNING cycle 99(SOC 19.9249%), CRITICAL cycle 228(SOC 4.98769%), 전이 간격 12.9초, manifest SHA-256 일치를 확인했다.
- `ECU_BUILD_TESTS=OFF`의 제품 `adaptive_ecu` target은 현재 macOS/OpenSSL 환경에서 구성·컴파일·링크를 통과했다.

## 환경 제한

- 시스템 Python에 pytest와 scikit-learn이 없어 기존 실제 IF 학습 CLI 시험 1건은 이 환경에서 실행하지 못했다. 신규 시험은 표준 `unittest`만으로 통과했다.
- C++ Fail-safe 회귀는 로컬 CMake에 GTest가 없어 구성 단계에서 실행하지 못했다. 같은 CSV·모델 계산은 독립 Python 검사로 확인했지만 대상 Linux의 C++ 시험을 대신하지 않는다.
- Linux SocketCAN이 없는 macOS이므로 실제 `vcan`/`can0` 송수신, 물리 부하, `0x200` IVI 표시, 탐지 지연은 미실행이다.
