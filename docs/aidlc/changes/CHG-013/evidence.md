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
