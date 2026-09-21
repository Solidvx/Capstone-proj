# ECU M5 — Ablation Study

> **2026-09-09 보안 방식 선별 반영:** 기존 단계·과제에 [하단 추가 수행·인수 조건](#security-adoption)을 함께 적용한다. 구현·시험 완료 기록은 아니다.

> **예시 상태**: 코드·명령은 별도 검증 표시가 없으면 작성 골격·예정 절차다. 실행 전 생성할 파일·의존성·플랫폼을 확인한다. [공동 규약](../common/00_협업_규약.md)의 문서·예시 사용 규칙을 따른다.

> 상위 계획: [ECU.md](../../ECU.md) · 실험 결합: [02_통합시험](../common/02_통합시험.md)
> 원본: `_archive/ECU.md` M5, `_archive/ECU_최종_실행계획서.md` §9

---


<a id="security-integration"></a>
## 현행 과제에 병합한 보안 수행·인수 조건 — 실험 설정과 인증 진단 원장

이 절은 2026-09-09 보안 상세 계획을 기존 단계에 반영한 실행 조건이다. 초기 보안 보강 절과 함께 적용하며 제품 실행 완료 기록은 아니다. 상세 규칙은 [메시지·상태 규약](../../../docs/development/security/인증이벤트_메시지_상태규약.md)과 [송신·큐·실패 정책](../../../docs/development/security/인증이벤트_메시지_상태규약.md#planning-final)을 참조한다.

**선행 조건:** ECU M4 준비와 공동 계측 정의를 인수한다. [M5 공동 인계 순서](../common/02_통합시험.md#m5-handoff-order)에 따라 run/trial·입력·구성을 먼저 합의하고 IVI의 계측 준비와 병행한다. IVI M5의 전체 완료는 착수 조건이 아니며 수신/UI 결과는 공동 실행 후 최종 집계 전에 인수한다. Q1/Q3의 기본 1,200 공격 시행·정상 평가·보조 A5/A6 구분은 유지한다.

**수행:** 입력/모델/규칙·profile/schema·실험 설정 hash와 calibration/평가 분리를 고정한다. producer 폐기·event gap·receiver 폐기는 같은 사건일 수 있으므로 합산하지 않고 epoch/event_seq로 대조한다. N06 혼동행렬과 N07 처리량/자원은 같은 단위·분모로 계산한다.

**실패 대응·인계:** 시험용 limits를 운영값으로 복사하지 않는다. 설정의 후보값·정상/경계/초과 측정·확정일을 원장에 남기고 공식 평가 전에 동결한다. 미탐은 결과, 계측 불능은 사유 있는 INVALID로 보존한다.

**완료 확인:**

- [ ] 공식/보조 결과·원본 원장·설정 확정 근거와 N/A 사유를 M7에 인계했다.
- [ ] 기존 공식 시험 결과와 추가 보조 시나리오의 실제 증거·미검증 사유를 구분했다.


## 1. 목적과 범위

**무방어 / SecOC only / SecOC+IDS** 세 가지 방어 구성에서 공격의 성공·차단·탐지를 정량화한다. IDS 동작점(임계)을 ROC 기준으로 확정하고, 실험 결과를 ADR과 TARA에 반영한다.

[M4](M4_IDS_공격_물리통합.md)의 결정에 따라 **오프라인 합성 실험은 준비·분석용으로, 최종 평가는 실제 CAN으로** 수행한다(S-5=A).

| 항목 | 값 |
|---|---|
| 연결 요구사항 | FR-SEC-001~007 (방어 계층 효과)<br>**NFR-SEC-001~002** (차단율 100%를 Config 2/3에서 정량화), **NFR-SEC-003~004** (탐지율·오탐율 실측) |
| 연결 시험 | TC-SEC-005-b/c, TC-EXP-001~005 |
| 산출물 | 실험 결과 CSV, 요약 통계, ROC 커브, 확정 임계, ADR 갱신 |
| 태그 | `v0.5.0` |

### 실험 매트릭스

| Config | SecOC | IDS | 목적 |
|---:|---|---|---|
| 1 | off | off | 무방어 baseline |
| 2 | on | off | SecOC 단독 효과 |
| 3 | on | on | SecOC + IDS 계층 방어 |

| 공격 | 생성 | 판정 근거 |
|---|---|---|
| Fuzzy | `traffic_gen.gen_attack("fuzzy", ...)` | ID/payload 랜덤성 (TC-SEC-005-a) |
| Replay | `gen_attack("replay", ...)` | payload 바이트 동일성 (TC-SEC-005-b) |
| Spoofing | `gen_attack("spoofing", ...)` | `0x100`, SOC raw=200 (TC-SEC-005-c) |
| Flooding | `gen_attack("flooding", ...)` | 합성 부하 입력 준비; TC-SEC-005-d는 실제 물리 버스 점유율 ≥50%로 판정 |
| (Masquerade) | `gen_attack("masquerade", ...)` | 공식 TC 없음. 탐지기 비교용 |

**4종 × 3 Config × 100회 = 1,200 시행**이 공식 목표다.

위 생성 함수는 합성 입력 준비용이다. 최종 평가는 M4에서 구현할 실 CAN 공격 CLI·수신 관측 어댑터로 수행하며, TC-EXP-005의 정상 윈도우 평가는 1,200개 공격 시행과 별도다.

---

## 2. 선행조건과 현재 구현 상태

**선행조건**: [M4](M4_IDS_공격_물리통합.md) 완료 — 탐지기 학습·평가 경로, `0x200` 송신 경로.

**현재 구현 상태 (확인 기준일 2026-09-05)**

| 대상 | 상태 | 비고 |
|---|---|---|
| `traffic_gen.gen_attack()` 5종 | **구현됨** | seed 고정, 라벨 포함 |
| `rule_baseline` / `spec_detector` / `if_detector` | **구현됨** | 탐지기 3종 |
| `run_eval.py` | **구현됨** | **탐지기 비교** 러너다. 방어 구성(Config 1/2/3) 비교는 하지 않는다 |
| `security/secoc_module.py` | **구현됨** | 합성/호스트 MAC·counter 검증의 비교 근거. 실제 Config 2/3 차단 판정은 대상 수신기의 인증/반영 로그로 확인 |
| Ablation 하네스 | **없음** | `run_ablation.sh`, `merge_results.py`, `analyze_roc.py` 모두 미존재 |
| 개별 공격 스크립트 | **없음** | `replay_attack.py`, `spoofing_attack.py` 등 미존재 |

> **혼동 금지**: `run_eval.py`가 만드는 "규칙 vs 사양 vs Isolation Forest" 표는 **탐지기 비교**다. M5가 만드는 "Config 1/2/3" 표는 **방어 구성 비교**다. 두 축을 한 표에 합치지 않는다.

### 해소한 충돌 — CLI 인자

| 계획 | 실제 `main.cpp` |
|---|---|
| `--secoc=on` / `--secoc=off` (등호) | **`--secoc on` / `--secoc off`** (공백 구분) |
| `--ids=on` / `--ids=off` | **존재하지 않는다.** IDS는 Python 별도 프로세스다 |

아래는 Node A 송신 프로세스의 실행 예다. 이것만으로 수신측 방어 설정이 전환되는 것은 아니다. Config 1에서는 격리 시험 수신기의 인증 OFF, Config 2/3에서는 인증 ON을 별도로 확인하며 Config 3에만 IDS를 연결한다. 수신측 전환 CLI·계측·복구는 미구현 과제다. 세 명령 블록을 동시에 실행하지 않는다.

```bash
# Config 1: 무방어
./adaptive_ecu/build/adaptive_ecu --interface vcan0 --secoc off

# Config 2: SecOC only
./adaptive_ecu/build/adaptive_ecu --interface vcan0 --secoc on

# Config 3: SecOC + IDS  (ECU는 Config 2와 동일, IDS 프로세스를 함께 띄운다)
./adaptive_ecu/build/adaptive_ecu --interface vcan0 --secoc on &
python3 security/ids/realtime_ids.py --channel vcan0        # M4 3.5에서 만든 루프
```

- [ ] 하네스가 별도 IDS 프로세스의 준비·종료를 관리한다. 현재 없는 `--ids` 인자를 ECU 명령에 넣지 않는다

---

## 3. 수행 절차

### 3.0 시행 수명과 증적 인수

오프라인 ReceiverModel은 합성 논리 시험이며 실제 CAN 수신 증거가 아니다. vcan/물리 실험은 별도 수신 프로세스에서 인증·수용·상태 반영을 관측한다.

1. run/config/attack/trial/seed/environment/protocol_version을 고정하고 입력·모델·threshold·바이너리 hash를 저장한다. 구성 간에는 같은 trial seed의 입력을 사용한다.
2. 이전 송신기·수신기·IDS·공격 프로세스를 종료·회수한다. 시행별 버퍼·IDS window·관측 상태를 새로 만들되 제품 counter/세션·UI 확인 상태를 외부에서 임의 초기화하지 않는다. 독립 시험 인스턴스 생성과 실제 재부팅/복구 시험을 분리한다. 보안 ON 구성은 양측 인증 설정·해당 계약의 준비 성공을 확인하며 미승인 세션 후보를 섞지 않는다.
3. 관측기 준비→정상 기준 구간→실제 공격 주입→고정 평가 구간→수집 종료→cooldown→자원 회수 순으로 실행한다. 준비·정상 구간·cooldown 길이는 pilot에서 산정 후 본 실험 전에 고정하며 시행 중 임의 변경하지 않는다.
4. 정상 기대 프레임·실제 수용·거부·오류·상태 반영·IDS 판정·공격 첫 주입을 원본 로그에 연결한다. 공격 성공·차단·탐지는 독립 관측하고, 검출 실패를 지연 0으로 넣지 않는다.
5. 시행 성공률의 분모는 유효 시행, 프레임 수용률은 공격/정상 프레임, 오탐률은 정상 window다. 각 분자·분모·미실시·INVALID·재시도 수를 함께 기록한다. 손실된 시행을 조용히 삭제하거나 재시도로 덮어쓰지 않는다.
6. 공식 3구성×4공격×100시행의 유일한 조합과 완료 증거를 확인한다. 1,200행만으로 PASS하지 않는다. 기존 요약 코드의 total은 유효 시행만 집계하도록 구현하고 전체 시도 목록은 별도로 보존한다.

실제 부하·지연은 물리 CAN에서 계측한다. measure_can_secoc.py 계산값과 vcan 결과를 실제 점유율로 사용하지 않는다. 전체 일정에는 준비·정상 기준·cooldown·실패 분석·장비 반복 시간을 포함한다.

### 3.1 오프라인 Ablation 하네스 (준비·분석 경로)

`security/experiments/run_ablation.py` (신규). 기존 자산만 조합하고 새 생성기·특징 추출기를 만들지 않는다.

**판정 규칙 — 세 값을 독립적으로 관측한다.**

| 값 | 의미 | 판정 방법 |
|---|---|---|
| `attack_success` | **수신 측 상태가 실제로 오염됐는가** | 아래 공격별 관측 정의 |
| `blocked` | 식별된 공격 입력을 수신측 인증 계층이 거부했는가 | 실제 수신 로그의 MAC/counter 거부 또는 인증 쌍 만료와 공격 입력을 대응. 파서 거부·버스 유실·송신 실패를 SecOC 차단으로 세지 않음 |
| `detected` | 고정 평가 구간의 공격을 IDS가 탐지했는가 | 고정한 점수 종류·부등호·임계로 판정. anomaly는 높을수록 이상, raw decision_function은 낮을수록 이상이며 wire_score와 구분 |

> **`attack_success`를 `not (blocked or detected)`로 계산하지 않는다.** **탐지는 차단이 아니다.** IDS가 경보를 울려도 공격 프레임이 수신 측에 수용됐다면 그 공격은 성공한 것이다. 반대로 Config 1은 방어가 없지만, 유효하지 않은 공격은 애초에 상태를 바꾸지 못하므로 성공이 아니다. 세 값을 각각 관측해야 `blocked=False, detected=True, attack_success=True`(탐지했지만 막지 못함) 같은 실제 상황이 기록된다.

**공격별 `attack_success` 관측 정의** — TEST_PLAN TC-EXP-001~004의 측정 항목과 대응한다.

| 공격 | TEST_PLAN 측정 항목 | 관측 방법 |
|---|---|---|
| Spoofing | 성공 횟수 | 조작된 SOC(raw 200)가 수신 측 상태에 반영됐는가 |
| Replay | 재생 성공률 | 재생된 프레임이 수용됐는가 (카운터 거부 여부) |
| Flooding | **BMS 전달 성공률** | 정상 `0x100`이 예상 주기대로 수용됐는가. 미수용률이 공격 성공 |
| Fuzzy | **비정상 데이터 수용률** | 유효 범위 밖 payload가 수용됐는가 |

Flooding은 MAC 거부와 별개로 **정상 메시지의 처리·지연·가용성**을 본다. SecOC는 위조 프레임을 막지만 버스 점유 자체를 막지는 못하므로, `blocked=True`여도 `attack_success=True`가 될 수 있다.

```python
# 개요 (security/experiments/run_ablation.py)
import random
from secoc_module import SecOcModule          # security/
from traffic_gen import gen_attack            # security/attacks/
from feature_extractor import raw_windows
from rule_baseline import RuleBaseline
from spec_detector import SpecDetector

CONFIGS = {1: (False, False), 2: (True, False), 3: (True, True)}
ATTACKS = ["fuzzy", "replay", "spoofing", "flooding"]
TRIALS  = 100
KEY = b"\x01" * 32          # 실험용 더미 키. 실 키는 쓰지 않는다

def trial_seed(attack: str, trial: int) -> int:
    """Config가 seed에 들어가지 않는다 — 같은 시행은 세 Config가 동일 입력을 받는다."""
    return 100_000 + 1_000 * ATTACKS.index(attack) + trial

def run_trial(config: int, attack: str, trial: int) -> dict:
    secoc_on, ids_on = CONFIGS[config]
    seed = trial_seed(attack, trial)
    frames = gen_attack(attack, duration=3.0, rng=random.Random(seed))

    # 수신 측 재현: 방어 구성에 따라 프레임을 수용/거부하고 그 결과를 관측한다
    rx = ReceiverModel(secoc_on=secoc_on, key=KEY)
    for f in frames:
        rx.feed(f)

    blocked  = rx.attack_auth_rejected_count > 0      # 공격에 대응된 인증 거부; 파서/정상 프레임 거부 제외
    detected = ids_flags(frames) if ids_on else False # 탐지기 판정
    success  = observe_success(attack, rx)            # 위 표의 공격별 정의

    return {
        "config": config, "attack_type": attack, "trial": trial, "seed": seed,
        "attack_success": success, "blocked": blocked, "detected": detected,
        "latency_s": rx.detect_latency, "rx_accepted": rx.accepted_count,
        "rx_rejected": rx.rejected_count, "normal_delivered": rx.normal_delivered,
    }
```

- [ ] **seed에 `config`를 넣지 않는다.** 같은 `(attack, trial)`이면 Config 1/2/3이 **동일한 공격 트래픽**을 받아야 비교가 성립한다. 위 `trial_seed()`가 그 형태다
- [ ] 시행별 1행 CSV: `config,attack_type,trial,seed,attack_success,blocked,detected,latency_s,rx_accepted,rx_rejected,normal_delivered`
- [ ] Config 1에서 `blocked=False, detected=False`는 정상이다. 다만 **`attack_success`는 관측 결과로 결정한다** — 무방어라는 이유로 True를 강제하지 않는다
- [ ] `blocked=False, detected=True, attack_success=True`(탐지했으나 오염됨) 조합이 나오면 그대로 기록한다. 이것이 IDS 단독 방어의 한계를 보여주는 데이터다

위 `ReceiverModel`, `ids_flags`, `observe_success`와 수신 카운터 속성은 미구현 모형 API다. 실제 `SecOcModule.verify(original_can_id, payload, auth_data)`만 호출해서는 인증 쌍 만료·수신 상태 오염·버스 전달·IDS 지연을 관측할 수 없다. `blocked=True`는 해당 시행에서 인증 거부가 한 번 이상 있었다는 뜻이며 전량 차단율 100%의 증거가 아니다. 공격 프레임별 수용/인증 거부/파서 거부/유실 카운터도 보존한다. 지연은 IDS 계측의 공격 시작·판정·0x200 수신·UI 표시를 각각 연결하고 수신 모형의 임의 필드로 채우지 않는다.

```bash
python security/experiments/run_ablation.py --trials 100 --out results/ablation.csv
wc -l results/ablation.csv
# 기대: 1201 (헤더 1 + 1200 시행)
```

### 3.2 결과 요약

`security/experiments/summarize_ablation.py` (신규)

아래 집계는 **동일 run·환경·계약/모델/설정, 중복 없는 유효 시행**으로 검증한 입력의 요약 골격이다. 원시 CSV 전체를 바로 읽어 모든 행을 유효 시행으로 간주하지 않는다. 하네스 구현 시 전체 시도 원장과 유효 시행 표를 분리하고 `(run_id, config, attack_type, trial)` 중복·결측/비유한 수치·잘못된 bool·분모 0을 오류 처리한다. 실패한 공격 탐지는 유효 시행의 미탐지이며 INVALID로 제외하지 않는다. 미탐지 지연은 결측 상태와 이유를 남기고 탐지된 시행의 평균/최대 및 미탐지·기한 초과 수를 별도 보고한다. 아래 평균은 검출된 유효 지연만의 통계이며 전체 응답 합격 기준을 대신하지 않는다.

```python
import pandas as pd

df = pd.read_csv("results/ablation.csv")
summary = df.groupby(["config", "attack_type"]).agg(
    total=("trial", "count"),
    attack_success=("attack_success", "sum"),
    blocked=("blocked", "sum"),
    detected=("detected", "sum"),
    avg_latency=("latency_s", "mean"),
).reset_index()

summary["success_rate"] = summary["attack_success"] / summary["total"] * 100
summary["block_rate"] = summary["blocked"] / summary["total"] * 100
summary["detection_rate"] = summary["detected"] / summary["total"] * 100
summary.to_csv("results/ablation_summary.csv", index=False)
print(summary.to_string(index=False))
```

기대 형태 (수치는 실행 결과로 채운다 — **여기에 예상치를 적지 않는다**):

```text
config attack_type  total  attack_success  blocked  detected  success_rate  block_rate  detection_rate
     1    spoofing    100             ...      ...       ...           ...         ...             ...
     2    spoofing    100             ...      ...       ...           ...         ...             ...
     3    spoofing    100             ...      ...       ...           ...         ...             ...
```

- [ ] 표의 분모(시행 수)와 seed 범위를 캡션에 함께 적는다
- [ ] 해당 run의 실제 실행 환경(합성 / `vcan0` / 물리 CAN)을 manifest와 대조해 캡션에 명시한다. 서로 다른 환경의 결과를 구분하고 합성/vcan을 물리 CAN 최종 인수로 표시하지 않는다

### 3.3 TC-EXP-005 — 정상 트래픽 오탐율 ≤5%

공격 없이 정상 윈도우만 평가한다. TEST_PLAN TC-EXP-005는 **"정상 100윈도우"** 를 요구하므로 완전한 평가 윈도우를 100개 이상 사전 고정한다. 길이·이동폭·시작/끝 경계와 빈 윈도우 처리, 실제 수집 손실을 구분한다. 100초 수집이나 마지막 프레임 시각만으로 완전한 윈도우 100개가 확보됐다고 가정하지 않는다. 최종 오탐률은 물리 CAN 정상 입력으로 판정하며 아래 합성 예제는 준비용이다.

> **현재 상태 확인 필요**: `run_eval.py`의 정상 평가 윈도우는 **60개**다(실행 출력의 "정상 60"). 이 상태로는 TC-EXP-005를 판정할 수 없다. `gen_normal()`의 `duration`을 늘려 **100개 이상**을 확보한다.

```python
# 개요 — 윈도우 1초 슬라이딩이므로 duration(초) ≈ 윈도우 수
normal_windows = list(windows(gen_normal(150.0, random.Random(EVAL_SEED))))
assert len(normal_windows) >= 100, f"분모 부족: {len(normal_windows)} < 100"

flags = [score(v) > THRESHOLD for v, _, _ in normal_windows]
fpr = sum(flags) / len(flags)
print(f"FPR = {sum(flags)}/{len(flags)} = {fpr:.2%}")
assert fpr <= 0.05, f"FPR {fpr:.2%} > 5%"
```

- [ ] 분모(윈도우 수)를 결과와 함께 기록한다. "100윈도우 중 3건"처럼 적는다
- [ ] `EVAL_SEED`는 **평가용 seed 집합**에서 고른다 (3.5.1)

### 3.4 ROC 분석과 임계 확정

`rule_baseline.roc_auc()`는 비교용 AUC 계산에 재사용할 수 있다. 공식 FR-SEC-006 및 Config 3 평가에는 실제 Isolation Forest 경로가 필요하다. sklearn 미가용이면 규칙 탐지기의 독립 분석은 진행할 수 있으나 IF/공식 IDS 완료는 보류한다.

```python
# security/experiments/analyze_roc.py (신규)
import matplotlib
matplotlib.use("Agg")          # 헤드리스 환경 대비
import matplotlib.pyplot as plt

# scores, labels는 임계 선택 전용 validation 데이터에서 얻는다. 최종 ablation 평가 데이터는 재사용하지 않는다
fpr_list, tpr_list, thresholds = roc_points(scores, labels)
auc_value = roc_auc(scores, labels)

plt.figure(figsize=(8, 6))
plt.plot(fpr_list, tpr_list, "b-", linewidth=2, label=f"Rule baseline (AUC = {auc_value:.3f})")
plt.plot([0, 1], [0, 1], "k--", linewidth=1, label="Random")
plt.xlabel("False Positive Rate")
plt.ylabel("True Positive Rate")
plt.title("ROC Curve — CAN IDS")
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("results/roc_curve.png", dpi=150)

# 비교용 전체 ROC의 후보 동작점. 이 결과만으로 공식 공격별 임계를 확정하지 않는다.
for fp, tp, th in zip(fpr_list, tpr_list, thresholds):
    if tp >= 0.90 and fp <= 0.05:
        print(f"후보 임계: {th:.4f} (전체 TPR={tp:.2%}, FPR={fp:.2%})")
        break
else:
    print("경고: TPR>=90% AND FPR<=5% 동시 만족점 없음")
    # 차선점을 고르되, 기준 미달 사실을 문서에 남긴다
```

`run_eval.py`는 이미 **정상 점수의 (1-목표FPR) 분위수**로 운영 임계를 잡는다. 같은 방식으로 통일할지, ROC 기반으로 바꿀지 하나로 정한다.

NFR-SEC-003은 네 공격 각각 ≥90%이므로 전체 공격을 합친 TPR ≥90%만으로 임계를 확정하지 않는다. validation에서 고정한 동일 동작점의 Fuzzy/Replay/Spoofing/Flooding별 분모·TPR와 정상 FPR를 대조한다. 선정 방법·후보 순서·동률 처리를 사전에 기록하고 최종 독립 평가에서는 임계를 고정한다. 실패한 공격을 제외하거나 평가 결과를 보고 임계를 바꾼 후 같은 데이터를 독립 평가라고 보고하지 않는다. 시행 기반 탐지율과 보조 윈도우 기반 ROC의 집계 단위를 분리한다.

- [ ] 확정 임계값과 그 근거(TPR/FPR)를 `docs/SDD-ECU.md`에 기록한다
- [ ] 임계를 바꾸면 [M4](M4_IDS_공격_물리통합.md)의 탐지 결과도 다시 뽑는다

**튜닝 가이드**

| 현상 | 조치 |
|---|---|
| FPR > 5% | 높을수록 이상인 anomaly 점수에서는 임계 상향 후보. raw decision 점수는 반대 방향. 실제 IF 기본 contamination=0.05와 고정/별도 임계 사용 여부를 기록하고 validation에서 재평가 |
| TPR < 90% | anomaly 점수에서는 임계 하향 후보. raw decision 점수는 반대 방향. contamination 변경 효과를 독립 임계 변화와 혼동하지 않고 공격별 TPR/FPR를 재평가 |
| 둘 다 나쁨 | 특징 추가 (`FEATURE_NAMES`와 규칙 `_DIRECTION` 동시 갱신) |
| 특정 공격만 낮음 | 그 공격의 특징이 정상과 유사하다는 뜻. masquerade면 사양기반 탐지기 결과를 본다 |

<a id="35-실행-환경-등급--tc-exp는-vcan0-이상에서-판정한다"></a>
### 3.5 실행 환경 등급 — 최종 TC-EXP는 물리 CAN에서 판정한다

측정 결과는 **어느 환경에서 얻었는지**에 따라 인정 범위가 다르다. 아래는 S-5=A에 따른 실험 환경별 인정 범위다. 측정 시계·표본·무효 처리의 정본은 [02_통합시험](../common/02_통합시험.md) §6이다. 이전 제목의 앵커는 링크 호환을 위해 유지하며 vcan 최종 인수를 허용하는 기준이 아니다.

| 등급 | 환경 | 이 단계에서의 역할 |
|---|---|---|
| **1. 합성** | 어디서나 (Python만) | 탐지기/임계·집계기 준비, 정상 입력 오탐률 사전 분석. 공식 TC-EXP 최종 인수 아님 |
| **2. `vcan0`** | 리눅스 1대, CAN 하드웨어 불필요 | 송수신·인증·하네스 전환·집계 경로 사전 검증. 1,200 시행을 완료해도 물리 CAN 최종 인수 아님 |
| **3. 물리 CAN** | RPi4 2대 + MCP2515 | TC-EXP-001~004의 4종×3구성×100시행과 TC-EXP-005 정상 평가, 통합·성능 TC 최종 판정 |

> **vcan의 역할**: 구현한 수신 어댑터와 verifier를 연결하면 커널 송수신 이후의 수용·거부·상태 반영을 장비 없이 사전 관측할 수 있다. 합성 ReceiverModel의 상태와 제품 수신기 관측은 별도 증거다. vcan에는 물리 중재·비트레이트·오류 환경이 없으며 Android 경로도 별도로 연결해야 하므로 물리 전달·지연·최종 TC의 증거로 대체하지 않는다.

vcan 준비는 Linux에서 기존 인터페이스 유무·종류를 먼저 확인하고, 없으면 vcan 생성·활성화 명령의 종료 코드를 각각 확인한다. 기존 인터페이스 충돌이나 권한 오류를 `|| true`로 숨기지 않는다. 하네스는 각 config의 송신기·수신기·IDS 프로세스를 소유하고 실제 준비 완료를 확인해야 한다. 고정 `sleep`이나 단일 ECU 기동만으로 준비/구성 전환 성공을 판정하지 않는다. 정상·오류·사용자 중단 모두에서 자신이 시작한 프로세스를 종료·회수하고 원시 결과를 보존한다.

```bash
# 예정 CLI: --channel·수신 관측·프로세스 수명 관리 구현과 독립 검증 후 실행
python security/experiments/run_ablation.py --channel vcan0 --trials 100 --out results/ablation_vcan.csv
```

1,200 시행 × 3초 = 1시간은 공격 구간만의 계산 예시다. 정상 기준 구간·프로세스 준비/회수·cooldown·실패 분석·재시도·물리 반복을 포함한 총 소요시간이 아니다. §3.0의 pilot에서 구간별 시간을 측정해 전체 일정을 산정한다. 3초도 모든 시행의 확정 길이로 자동 적용하지 않는다.

- [ ] 모든 표·그래프 캡션에 **등급을 표기한다**: `(합성 트래픽, seed 42)` / `(vcan0 실측, 1,200 시행)` / `(물리 CAN 실측)`
- [ ] 등급이 다른 수치를 같은 표에 합치지 않는다. 열이나 표를 나눈다
- [ ] `vcan0` 환경을 아직 쓸 수 없으면 합성으로 먼저 수행하되 **"잠정"** 으로 표기하고, 확보 시점에 재측정한다

### 3.5.1 임계 선정 데이터와 성능 평가 데이터를 분리한다

앞의 vcan 명령은 미구현 하네스의 목표 사용법이다. §3.0의 config별 양측 준비·시험 상태·프로세스 수명 관리와 수신 관측이 구현되기 전에는 명령을 인수 절차로 실행하지 않는다.

같은 데이터로 임계값도 고르고 성능도 재면 **성능이 실제보다 좋게 나온다**(시험 문제를 미리 보고 그 문제로 시험 보는 것과 같다).

- [ ] 임계 선정용 seed 집합과 최종 평가용 seed 집합을 **겹치지 않게** 나눈다
- [ ] 3.4의 ROC 동작점은 **선정용 데이터에서만** 구한다
- [ ] 최종 보고 수치는 **평가용 데이터**에서 얻는다
- [ ] 두 집합의 seed 범위를 결과 파일과 문서에 명시한다

### 3.6 ADR 최종화

실제로 검증한 결정에만 M5 결과를 근거로 연결한다. 아래 대안은 비교 후보 목록이며 해당 대안을 구현·측정했다는 뜻이 아니다. 예를 들어 ECU M3의 SOC 비교는 ADR-005에 별도 연결하고, M5의 SecOC/IDS 결과로 EKF·UKF·RSA 또는 Node A/Node B 성능 비교를 수행했다고 주장하지 않는다.

| ADR | 주제 | 대안 |
|---|---|---|
| ADR-001 | SocketCAN 선택 | PEAK PCAN, CANopen |
| ADR-002 | HMAC-SHA256 선택 | AES-CMAC, RSA |
| ADR-003 | Isolation Forest 선택 | Autoencoder, LSTM |
| ADR-005 | EKF SOC 추정 | UKF, 쿨롱 카운팅 |
| ADR-008 | Ablation 설계 (3 Config × 4 Attack) | — |
| ADR-009 | IDS를 Node A에 배치 | Node B, 별도 노드 |
| ADR-011 | Python IDS | C++ 구현 |
| ADR-012 | SecOC 분리 프레임 | Authenticated PDU |

- [ ] ADR-003은 sklearn 미가용 시 IF 비교가 SKIPPED였는지 여부까지 적는다. 비교 없이 선택 근거를 주장하지 않는다

---

## 4. 검증 명령과 합격 기준

```bash
python security/experiments/run_ablation.py --trials 100 --out results/ablation.csv
python security/experiments/summarize_ablation.py
python security/experiments/analyze_roc.py
python -m pytest security/tests -v
```

| 기준 | 합격 조건 |
|---|---|
| TC-SEC-005-b | Replay payload 바이트 동일성 확인 |
| TC-SEC-005-c | Spoofing `payload[0] == 200` |
| TC-EXP-001~004 | 실제 CAN 공격 4종 × 방어 구성 3개 × 유효 100시행과 전체 시도 원장. Config 3의 공격별 탐지율 ≥90%, 각 TC의 성공/거부/전달/지연을 독립 보고 |
| TC-EXP-005 | 실제 CAN 정상 입력 오탐율 ≤5%, 완전한 윈도우 100개 이상·길이/이동폭/분모·누락 기록 |
| 데이터 | 유효 조합 1,200개, 중복 없음, 실패/INVALID/재시도 원장 및 관측 로그 대응. 행 수만으로 PASS하지 않음 |
| 산출물 | `results/roc_curve.png`, 확정 임계값 |
| 문서 | TARA·ADR에 실험 결과 반영 |
| 태그 | `v0.5.0` |

---

## 5. 실패 시 대응과 우회

**Config 1에서 blocked/detected가 나옴**
- 하네스가 Config별 스위치를 실제로 반영하지 않는다는 뜻이다. `CONFIGS` 매핑과 분기를 먼저 확인한다

**시행 간 결과가 재현되지 않음**
- seed 배정이 시행마다 고정인지 확인한다. 전역 `random` 대신 `random.Random(seed)` 인스턴스를 쓴다
- `if_detector`는 `RANDOM_STATE=42` 고정이다. 변경하지 않는다

**TPR≥90% AND FPR≤5%를 동시에 만족하는 점이 없음**
1. 특징을 추가하거나 사양기반 탐지기를 병용한다
2. 그래도 없으면 **기준을 낮춰 통과 처리하지 않는다.** 차선 동작점과 미달 사실, 원인 분석을 함께 기록한다
3. 발표에서는 "달성"이 아니라 "차선 동작점에서 TPR x%, FPR y%"로 정확히 말한다

**matplotlib 없음 / 헤드리스 오류**
```python
import matplotlib
matplotlib.use("Agg")   # pyplot import 전에 호출
```
그래프를 못 만들면 수치 표만으로 진행하고, 그래프 부재를 기록한다

**실 CAN 표본 결과가 오프라인과 다름**
- 다르다는 사실 자체가 결과다. 합성 트래픽의 한계로 기록하고, 어느 쪽 수치를 발표에 쓰는지 명시한다

---

## 6. 완료 체크리스트

- [ ] Ablation 하네스가 Config 1/2/3을 실제로 다르게 실행한다
- [ ] **`attack_success`를 수신 측 관측으로 판정한다** (`not (blocked or detected)` 계산 금지)
- [ ] 공격별 성공 관측 정의를 구현했다 (Spoofing/Replay/Flooding/Fuzzy)
- [ ] **seed에 `config`가 들어가지 않는다** — 같은 시행은 세 Config가 동일 입력
- [ ] 1,200 시행 CSV 생성 (`rx_accepted`, `rx_rejected`, `normal_delivered` 포함)
- [ ] 요약 통계 CSV 생성 (성공률·차단율·탐지율·평균 지연)
- [ ] TC-EXP-005 **분모 100 이상** 확보, 오탐율 ≤5%
- [ ] **임계 선정용 / 평가용 seed 집합 분리**, 범위를 문서에 명시
- [ ] ROC 커브 저장, 확정 임계값과 근거 기록 (선정용 데이터 기준)
- [ ] 확정 임계를 `docs/SDD-ECU.md`에 반영
- [ ] 탐지기 비교 표와 방어 구성 비교 표를 분리 유지
- [ ] **모든 표·그래프 캡션에 실행 환경 등급 표기** (합성 / `vcan0` / 물리 CAN)
- [ ] TC-EXP-001~005 최종 인수는 물리 CAN에서 수행. 합성/vcan은 사전 검증으로 표기하고 장비 시험 부재는 미완료 유지
- [ ] ADR-001/002/003/005/008/009/011/012 실험 근거 반영
- [ ] `v0.5.0` 태그 생성


## S-5=A 실제 CAN 최종 평가 수행 계획

1. M4에서 실시간 공격 입력·CAN 수집·방어 실행·IVI 경보 경로를 먼저 점검한다. 합성 하네스가 실제 버스에도 연결된다고 가정하지 말고 해당 어댑터의 구현 여부를 확인한다.
2. Fuzzy/Replay/Spoofing/Flooding 각각에 무방어/SecOC only/SecOC+IDS를 적용하여 12개 조합을 실행한다. 공식 TEST_PLAN의 조건·반복 횟수·합격 기준을 사용하고 미정 장비 정보는 확인사항 입력 후 실행한다.
3. 공격 송신 기록과 독립 CAN 수집 기록으로 공격 구간·유실·실제 도달 입력을 확인한다. run ID, 소프트웨어 버전, 방어 구성, 세션 방식, 학습/평가 분리, 임계, 반복 조건을 고정하여 기록한다. 실제 키는 기록하지 않는다.
4. 공격별 TP/FN, 정상 구간 FP/TN의 집계 단위와 분모를 공식 시험에 맞춰 명시한다. 무방어·SecOC 차단·IDS 탐지를 같은 탐지기로 간주하지 않는다. 차단되어 IDS에 도달하지 않은 입력의 처리 기준을 기록한다.
5. 원시 점수 방향, 탐지율·오탐률·지연·자원 사용, ECU/IVI 상태를 구성별로 보고한다. 실패·중단·버스 유실도 포함한다. 합성 결과와 별도 표로 제시하고 실제 CAN 시험이 없으면 최종 인수는 보류한다.



<a id="ecu-exp-01"></a>
### ECU-EXP-01 — Plan 승계 과제

원문: [ECU.md](../../_archive/plan_20260908/ECU.md.txt)의 ECU-EXP-01. 실행 상태는 해당 역할의 진행 표·공동 인수 기록을 사용한다. 이 병합은 과제 실행 완료가 아니다.

선행·착수: [ECU-IDS-01](M4_IDS_공격_물리통합.md#ecu-ids-01), COM-INT-01의 해당 실험 준비, [IVI-MEAS-01](../ivi/M5_성능_UI개선.md#ivi-meas-01)

보존한 수행·인수 조건: 3개 방어 구성의 실제 상태·공식 4종 공격·성공/거부/탐지/IVI 전달·오탐을 분리한다. seed·분모·시계·환경·원출력과 재현 명령을 인계하고 M7에서 재현한다. 오프라인 탐지기 비교·연산/버스 계산을 물리 Ablation/UI 지연으로 대체하지 않는다.

현재 기준 적용: 합성 pilot은 독립 가능; 물리 실험의 선행과 구분. 본문의 공식 FR/TC·승인 정책·실패 대응을 함께 적용한다.


<a id="security-adoption"></a>
## 보안 차용 보강 — 실험 묶음·보조 지표

### 목적·선행조건

ECU-EXP-01에 Q1=A·Q3=A와 N06/N07을 연결한다. 기존 4공격×3구성×100회=1,200 시행과 TC-EXP-005 정상 평가는 유지한다. A5/A6는 보완 통합 사례이며 추가 600회로 확대하지 않는다. Q2 실시간 시험은 [공동 인계](../common/01_연계_의존성.md#security-adoption)의 상세 계약과 양측 준비 후 실시한다.

### 수행 절차 — 데이터·구성

1. Config 1/2/3과 원자료 C0/C1/C2를 대응하고 송신·수신 인증 및 IDS의 실제 활성 상태를 manifest에 기록한다. 기본 안전 기능과 추가 통신 감시가 어떤 구성에서 동작하는지 고정하여 IDS 단독 효과와 계층 전체 효과를 구분한다.
2. A0 정상, A1 Flood, A2 Fuzz, A3 Spoof, A4 Replay, A5 Suspension, A6 정상 주기 대체 위장으로 원자료를 연결한다. 21조합은 시나리오 목록이며 동일 반복 수의 새 공식 인수표가 아니다. A5/A6 반복·강도·준비/복구 구간은 pilot 후 사전 고정한다.
3. raw log·label CSV·manifest를 묶고 JSONL 사건을 보완한다. run/boot/trial/sample/profile/source_mode·seed·코드/입력/모델/규칙 hash·실험 설정·버전·시계·드롭을 연결한다. 실제 Git이 없으면 commit을 만들지 않고 파일 hash로 식별한다.
4. frame·event/window·시행 라벨을 구분한다. train/calibration/final-test는 capture/run 단위로 분리하고 인접 윈도우나 source timestamp·정답 라벨이 학습의 지름길이 되지 않게 한다. 새 seed를 미지 공격으로 부르지 않는다. family/profile holdout 주장에는 실제 분리 목록을 제시한다.
5. 기존 `run_eval.py`는 합성 detector 비교로 유지하고, 예정 `run_ablation.py`와 물리 수집 어댑터에 보강한다. 별도 `run_matrix.py`를 중복 생성하지 않는다. raw·대형 모델은 제외/외부 보존 경로에 두고 최종 증거에는 위치·hash·재현 절차를 남긴다.

### 수행 절차 — N06/N07

혼동행렬은 같은 판단 단위의 TP/FP/TN/FN 원수를 보존한다. 공식 시행 탐지율·프레임 차단율·정상 window FPR를 혼합하지 않는다. 같은 데이터로 계산할 수 있는 보조 지표만 보고한다.

| 지표 | 산식·주의 |
|---|---|
| Precision / Recall | TP/(TP+FP), TP/(TP+FN) |
| FPR / FNR / TNR | FP/(FP+TN), FN/(TP+FN), TN/(TN+FP) |
| F1 / Balanced Accuracy | 2TP/(2TP+FP+FN), (Recall+TNR)/2 |
| MCC | (TP×TN−FP×FN)/sqrt((TP+FP)(TP+FN)(TN+FP)(TN+FN)) |
| 공통 | 분모 0은 N/A, percentage/ratio 단위 표기. IDS 없는 구성의 미정의 지표를 0·PASS로 바꾸지 않음 |

모델 파일 크기·hash, frames/windows 입력·처리·드롭 수, 관찰 지속시간, CPU·RSS·전처리/윈도우 판단 시간과 run별 분포를 수집한다. frames/s와 windows/s를 분리하며 관찰된 처리율을 최대 지속 처리 능력으로 단정하지 않는다. Q3=A에서 부족한 지표는 미산출 사유를 기록하고 지표 전용 대규모 반복은 추가하지 않는다. 기존 공식 성능·자원 검증은 계속 수행한다.

### 검증·실패 대응

[IVI M5](../ivi/M5_성능_UI개선.md#security-adoption)의 구간·분모·시계·unmatched를 인수한 뒤 집계한다. 실패·미검출·timeout·INVALID·Skip·재시도를 원장에 남긴다. capture 손실이나 혼합 버전은 해당 시행을 조용히 제거하지 않고 원인을 해결해 재수집한다. 동일 입력·설정에서 요약 재생성을 확인하고 M7에 원수·산식·원본 hash를 인계한다. 추가 보완 사례나 전체 평균으로 기존 공격별 인수를 대체하지 않는다.

### 완료 체크

- [ ] 기존 공식 매트릭스와 A5/A6 보완 결과·정상 평가 분리
- [ ] raw/label/manifest·분리 목록·실패 원장·재현 절차 인수
- [ ] N06 분모·산식·N/A 및 N07 단위·관찰 범위·미검증 한계 확인
