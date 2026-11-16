"""IDS 오프라인 실측 러너 (규칙 vs 사양기반 + 재현성 + 방어 계층화).

정상 트래픽으로 규칙·사양기반 탐지기를 학습하고, 정상+5종 공격 합성 트래픽에서
탐지율/오탐율/ROC-AUC/공격별 탐지율/탐지지연을 산출한다. 멀티 seed로 재현성 편차도
측정한다(문서 §6). seed 고정으로 결정적.

실행: python security/experiments/run_eval.py
sklearn 가용 시 Isolation Forest 비교도 함께 출력(없으면 SKIPPED).
"""

from __future__ import annotations

import os
import math
import random
import sys

try:  # Windows 콘솔(cp949)에서 유니코드 출력 보호
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_SEC = os.path.dirname(_HERE)
for sub in ("ids", "attacks", "analysis"):
    sys.path.insert(0, os.path.join(_SEC, sub))

from traffic_gen import ATTACKS, gen_attack, gen_normal  # noqa: E402
from feature_extractor import raw_windows, windows  # noqa: E402
from rule_baseline import RuleBaseline, confusion_metrics, metrics_at, roc_auc  # noqa: E402
from spec_detector import SpecDetector  # noqa: E402

SEED = 42
TRAIN_S = 90.0
CALIBRATION_S = 60.0  # 합성 runner의 별도 정상 보정 구간; 실물 운영값 아님
NORMAL_EVAL_S = 60.0
ATTACK_S = 30.0
TARGET_FPR = 0.01  # 운영점: 정상 오탐율 ~1%


def format_metric(value, specification=".3f"):
    """미정의 지표를 성공/실패 수치 대신 N/A로 표시한다."""
    return "N/A" if value is None else format(value, specification)


def _percentile(values: list[float], q: float) -> float:
    if not values or any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        raise ValueError("calibration needs nonempty finite scores")
    if type(q) not in (int, float) or not math.isfinite(q) or not 0 <= q <= 1:
        raise ValueError("percentile must be in [0, 1]")
    s = sorted(values)
    idx = min(len(s) - 1, int(round(q * (len(s) - 1))))
    return s[idx]


def build_dataset(rng: random.Random):
    train = [v for v, _, _ in windows(gen_normal(TRAIN_S, rng))]
    test = []  # (vec, label, atype)
    for v, y, a in windows(gen_normal(NORMAL_EVAL_S, rng)):
        test.append((v, y, a))
    for atk in ATTACKS:
        for v, y, a in windows(gen_attack(atk, ATTACK_S, rng)):
            test.append((v, y, a))
    return train, test


def prepare_rule_evaluation(rng: random.Random):
    """기존 학습/평가 draw 뒤 별도 정상 draw로 임계만 보정한다.

    평가 점수/라벨은 임계 선정에 전달하지 않는다. 원래 학습/평가 자료를
    보존하기 위해 새 보정 draw를 뒤에 생성한다. 실제 capture 분리는 아니다.
    """
    train, test = build_dataset(rng)
    calibration = [v for v, _, _ in windows(gen_normal(CALIBRATION_S, rng))]
    model = RuleBaseline().fit(train)
    threshold = _percentile([model.score(v) for v in calibration], 1.0 - TARGET_FPR)
    return model, train, calibration, test, threshold


def detection_latency(rng: random.Random, model, threshold: float) -> dict:
    """공격 세그먼트 시작 후 첫 탐지까지 윈도우 수(=초)."""
    out = {}
    for atk in ATTACKS:
        wins = list(windows(gen_attack(atk, ATTACK_S, rng)))
        latency = None
        for i, (v, y, a) in enumerate(wins):
            if y == 1 and model.score(v) >= threshold:
                # 첫 공격 윈도우 인덱스 기준 지연
                first_atk = next(j for j, (_, yy, _) in enumerate(wins) if yy == 1)
                latency = i - first_atk
                break
        out[atk] = latency
    return out


def eval_rule(rng: random.Random):
    """규칙 베이스라인: (per_attack 탐지율, fpr, auc, recall) 산출."""
    model, _, calibration, test, thr = prepare_rule_evaluation(rng)
    scores = [model.score(v) for v, _, _ in test]
    labels = [y for _, y, _ in test]
    atypes = [a for _, _, a in test]
    m = metrics_at(scores, labels, atypes, thr)
    return {**m, "auc": roc_auc(scores, labels), "threshold": thr,
            "calibration_windows": len(calibration),
            "threshold_selection": "separate synthetic normal calibration; no evaluation scores"}


def eval_spec(rng: random.Random):
    """사양기반 탐지기: 정상 학습 → 정상+공격 윈도우 탐지. per-ID 프레임 사용."""
    spec = SpecDetector().fit(w for w, _, _ in raw_windows(gen_normal(TRAIN_S, rng)))
    tp = fp = tn = fn = 0
    per_hit: dict[str, list[int]] = {}
    def _run(frame_windows):
        nonlocal tp, fp, tn, fn
        for wf, y, at in frame_windows:
            pred = spec.flag(wf)
            if y == 1:
                per_hit.setdefault(at, [0, 0])
                per_hit[at][0] += pred
                per_hit[at][1] += 1
                if pred:
                    tp += 1
                else:
                    fn += 1
            else:
                if pred:
                    fp += 1
                else:
                    tn += 1
    _run(raw_windows(gen_normal(NORMAL_EVAL_S, rng)))
    for atk in ATTACKS:
        _run(raw_windows(gen_attack(atk, ATTACK_S, rng)))
    return {"per_attack": {a: h[0] / h[1] for a, h in per_hit.items()},
            **confusion_metrics(tp, fp, tn, fn)}


def reproducibility(seeds):
    """멀티 seed로 규칙·사양기반의 masquerade 탐지율·FPR 편차 측정(문서 §6)."""
    rule_m, spec_m, rule_fpr, spec_fpr = [], [], [], []
    for s in seeds:
        r = eval_rule(random.Random(s))
        sp = eval_spec(random.Random(s))
        rule_m.append(r["per_attack"].get("masquerade", 0.0))
        spec_m.append(sp["per_attack"].get("masquerade", 0.0))
        rule_fpr.append(r["fpr"])
        spec_fpr.append(sp["fpr"])
    def ms(xs):
        import statistics as st
        return (st.mean(xs), st.pstdev(xs) if len(xs) > 1 else 0.0)
    return {"seeds": list(seeds), "rule_masq": ms(rule_m), "spec_masq": ms(spec_m),
            "rule_fpr": ms(rule_fpr), "spec_fpr": ms(spec_fpr)}


def main() -> None:
    rng = random.Random(SEED)
    model, train, calibration, test, thr = prepare_rule_evaluation(rng)
    scores = [model.score(v) for v, _, _ in test]
    labels = [y for _, y, _ in test]
    atypes = [a for _, _, a in test]

    auc = roc_auc(scores, labels)
    m = metrics_at(scores, labels, atypes, thr)
    lat = detection_latency(random.Random(SEED + 1), model, thr)

    print("=" * 64)
    print("규칙기반 IDS 베이스라인 — 독립 보정 합성 평가 (seed=%d)" % SEED)
    print("=" * 64)
    print(f"학습 정상 {len(train)} · 별도 정상 보정 {len(calibration)} · 평가 윈도우 {len(test)} "
          f"(정상 {labels.count(0)} / 공격 {labels.count(1)})")
    print(f"합성 보정 임계(z) = {thr:.2f}  (보정 목표 FPR {TARGET_FPR:.0%}; 평가 FPR 보장 아님)\n")
    print("판단 단위: 합성 입력의 1초 윈도우 · 지표 단위: ratio · 분모0: N/A")
    print(f"ROC-AUC        : {format_metric(auc)}")
    print(f"Precision      : {format_metric(m['precision'])}")
    print(f"Recall(탐지율) : {format_metric(m['recall'])}")
    print(f"F1             : {format_metric(m['f1'])}")
    print(f"FNR / TNR      : {format_metric(m['fnr'])} / {format_metric(m['tnr'])}")
    print(f"Balanced Acc.  : {format_metric(m['balanced_accuracy'])}")
    print(f"MCC            : {format_metric(m['mcc'])}")
    print(f"오탐율(FPR)    : {format_metric(m['fpr'])}   (TP={m['tp']} FP={m['fp']} TN={m['tn']} FN={m['fn']})")
    print("\n공격 유형별 탐지율 · 탐지지연(초):")
    for atk in ATTACKS:
        r = m["per_attack"].get(atk)
        d = lat.get(atk)
        dtxt = f"{d}s" if d is not None else "미탐지"
        print(f"  {atk:9s}: 탐지율 {format_metric(r, '5.1%')}   지연 {dtxt}")

    print("\n[범위] 위 수치는 생성한 합성 윈도우의 결과다. 임계는 별도 정상 자료로 고정했으며, "
          "공격별 결과와 미탐지/오탐을 그대로 보고한다. 실시간 CAN 탐지/차단이나 IF 추가 효과의 인수가 아니다.")

    # ── 사양기반(per-ID) 탐지기 — masquerade 보완 ──────────────────────────
    print("\n" + "=" * 64)
    print("per-ID 사양기반 탐지기 — 규칙이 놓친 masquerade 보완")
    print("=" * 64)
    sp = eval_spec(random.Random(SEED))
    print(f"오탐율(FPR) {format_metric(sp['fpr'])}  (TP={sp['tp']} FP={sp['fp']} TN={sp['tn']} FN={sp['fn']})")
    print("공격 유형별 탐지율 (규칙 → 사양기반):")
    for atk in ATTACKS:
        r = m["per_attack"].get(atk, 0.0)
        s = sp["per_attack"].get(atk, 0.0)
        mark = "  ← 규칙 놓침, 사양기반 회복" if (r < 0.5 <= s) else ""
        print(f"  {atk:11s}: {r:5.1%} → {s:5.1%}{mark}")

    # ── 재현성 (멀티 seed 편차, 문서 §6) ──────────────────────────────────
    print("\n" + "-" * 64)
    repro = reproducibility([42, 43, 44, 45, 46])
    rm, rms = repro["rule_masq"]
    sm, sms = repro["spec_masq"]
    sf, sfs = repro["spec_fpr"]
    print(f"재현성(seed {repro['seeds']}): masquerade 탐지율 "
          f"규칙 {rm:.1%}±{rms:.1%}  vs  사양기반 {sm:.1%}±{sms:.1%} · "
          f"사양기반 FPR {sf:.3f}±{sfs:.3f}")

    # ── Isolation Forest 비교 (가용 시) ───────────────────────────────────
    print("\n" + "-" * 64)
    try:
        sys.path.insert(0, os.path.join(_SEC, "ids"))
        from if_detector import IsolationForestDetector, sklearn_available
        if not sklearn_available():
            raise RuntimeError("scikit-learn 미설치")
        ifd = IsolationForestDetector().fit(train)
        if_scores = [ifd.anomaly(v) for v, _, _ in test]
        print(f"Isolation Forest ROC-AUC : {format_metric(roc_auc(if_scores, labels))} (참고 비교)")
    except Exception as e:
        print(f"Isolation Forest 비교: SKIPPED ({e}) — 설치 후 재실행하면 자동 비교")


if __name__ == "__main__":
    main()
