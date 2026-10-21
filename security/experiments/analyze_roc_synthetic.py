#!/usr/bin/env python3
"""ROC, operating point and normal FPR for the offline rule baseline (synthetic).

Scope: this is the window-level z-score baseline (rule_baseline.RuleBaseline),
the same detector family as run_eval.py. It is NOT the streaming IDS
(security.ids.runtime_detector) used for Ablation Config 3; that detector has
its own fixed test thresholds.

Judgement follows NFR-SEC-003 (each official attack >= 90%) and NFR-SEC-004 /
TC-EXP-005 (normal FPR <= 5%) on the four official attacks only. Masquerade is
outside the official matrix and is reported separately as a reference, together
with the spec-based detector. Operating point selection and evaluation use
disjoint seed sets (M5 3.5.1). matplotlib is optional.
"""

from __future__ import annotations

import argparse
import os
import random
import sys

_SEC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("ids", "attacks"):
    sys.path.insert(0, os.path.join(_SEC, sub))

from traffic_gen import gen_attack, gen_normal                 # noqa: E402
from feature_extractor import raw_windows, windows             # noqa: E402
from rule_baseline import RuleBaseline, roc_auc                # noqa: E402
from spec_detector import SpecDetector                         # noqa: E402

OFFICIAL_ATTACKS = ["flooding", "fuzzy", "replay", "spoofing"]
REFERENCE_ATTACK = "masquerade"
SELECT_SEEDS = (42, 43, 44)
EVAL_SEEDS = (142, 143, 144)
TRAIN_SEED = 7
MAX_FPR = 0.05      # NFR-SEC-004 / TC-EXP-005
MIN_TPR = 0.90      # NFR-SEC-003, per attack


def _scored(model, seeds, attacks, normal_s=60.0, attack_s=30.0):
    """(score, label, attack_type) per window for the given seeds."""
    rows = []
    for seed in seeds:
        rng = random.Random(seed)
        rows += [(model.score(v), y, a) for v, y, a in windows(gen_normal(normal_s, rng))]
        for atk in attacks:
            rows += [(model.score(v), y, a) for v, y, a in windows(gen_attack(atk, attack_s, rng))]
    return rows


def _rates(rows, thr, attacks):
    normal = [s for s, y, _ in rows if y == 0]
    fpr = sum(s >= thr for s in normal) / len(normal) if normal else 0.0
    per = {}
    for atk in attacks:
        hits = [s >= thr for s, y, a in rows if y == 1 and a == atk]
        per[atk] = sum(hits) / len(hits) if hits else 0.0
    return fpr, per, len(normal)


def roc_points(rows):
    scores = [s for s, _, _ in rows]
    labels = [y for _, y, _ in rows]
    pos = sum(labels)
    neg = len(labels) - pos
    pts = []
    for thr in sorted(set(scores)):
        tp = sum(s >= thr and y for s, y in zip(scores, labels))
        fp = sum(s >= thr and not y for s, y in zip(scores, labels))
        pts.append((fp / neg if neg else 0.0, tp / pos if pos else 0.0, thr))
    return pts


def select_threshold(rows):
    """Lowest threshold whose selection-set normal FPR is <= MAX_FPR."""
    for thr in sorted({s for s, _, _ in rows}):
        fpr, _, _ = _rates(rows, thr, [])
        if fpr <= MAX_FPR:
            return thr
    return max(s for s, _, _ in rows)


def _spec_reference(attacks):
    spec = SpecDetector().fit(w for w, _, _ in raw_windows(gen_normal(90.0, random.Random(TRAIN_SEED))))
    hit, total, fp, tn = {}, {}, 0, 0
    for seed in EVAL_SEEDS:
        rng = random.Random(seed)
        for w, _, _ in raw_windows(gen_normal(60.0, rng)):
            flagged = spec.flag(w)
            fp += flagged
            tn += not flagged
        for atk in attacks:
            for w, y, _ in raw_windows(gen_attack(atk, 30.0, rng)):
                if y:
                    hit[atk] = hit.get(atk, 0) + spec.flag(w)
                    total[atk] = total.get(atk, 0) + 1
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return fpr, {a: hit[a] / total[a] for a in total}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="tmp")
    args = parser.parse_args(argv)
    os.makedirs(args.out_dir, exist_ok=True)

    train = [v for v, _, _ in windows(gen_normal(90.0, random.Random(TRAIN_SEED)))]
    model = RuleBaseline().fit(train)

    # 1) Operating point on the selection seeds, official attacks only.
    sel = _scored(model, SELECT_SEEDS, OFFICIAL_ATTACKS)
    auc = roc_auc([s for s, _, _ in sel], [y for _, y, _ in sel])
    thr = select_threshold(sel)
    pts = roc_points(sel)

    # 2) Frozen threshold evaluated on disjoint seeds.
    ev = _scored(model, EVAL_SEEDS, OFFICIAL_ATTACKS + [REFERENCE_ATTACK])
    fpr, per, denom = _rates(ev, thr, OFFICIAL_ATTACKS + [REFERENCE_ATTACK])
    meets = fpr <= MAX_FPR and all(per[a] >= MIN_TPR for a in OFFICIAL_ATTACKS)

    print("대상: 오프라인 규칙 베이스라인(z-score), 합성 트래픽 — Ablation Config 3의 실시간 IDS와 별개")
    print(f"[공식 4종] ROC-AUC(선정 seed {SELECT_SEEDS}) = {auc:.3f}")
    print(f"[공식 4종] 확정 임계 = {thr:.3f} (선정 seed에서 정상 오탐 ≤{MAX_FPR:.0%}인 가장 낮은 임계)")
    print(f"[공식 4종] 평가 seed {EVAL_SEEDS}: 정상 오탐 {fpr:.1%} (분모 {denom} 윈도우), " +
          ", ".join(f"{a} {per[a]:.1%}" for a in OFFICIAL_ATTACKS))
    print(f"[공식 4종] NFR-SEC-003·004 기준(공격별 ≥{MIN_TPR:.0%}, 오탐 ≤{MAX_FPR:.0%}): "
          f"{'충족' if meets else '미충족'}")
    spec_fpr, spec_per = _spec_reference([REFERENCE_ATTACK])
    print(f"[참고·공식 외] masquerade 탐지: 규칙 {per[REFERENCE_ATTACK]:.1%} / "
          f"사양기반 {spec_per[REFERENCE_ATTACK]:.1%} (사양기반 정상 오탐 {spec_fpr:.1%})")

    import csv
    with open(os.path.join(args.out_dir, "detector_reference.csv"), "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["environment", "scope", "attack", "detector",
                                                   "unit", "detection_rate", "normal_fpr", "normal_windows"])
        writer.writeheader()
        for detector, detection, normal_fpr in (
                ("rule_baseline", per[REFERENCE_ATTACK], fpr),
                ("spec_detector", spec_per[REFERENCE_ATTACK], spec_fpr)):
            writer.writerow({"environment": "synthetic", "scope": "reference_not_official_matrix",
                             "attack": REFERENCE_ATTACK, "detector": detector, "unit": "window",
                             "detection_rate": detection, "normal_fpr": normal_fpr, "normal_windows": denom})

    csv_path = os.path.join(args.out_dir, "roc_points.csv")
    with open(csv_path, "w", encoding="utf-8") as handle:
        handle.write("fpr,tpr,threshold\n")
        for fp, tp, t in pts:
            handle.write(f"{fp:.4f},{tp:.4f},{t:.4f}\n")
    print(f"ROC 포인트(공식 4종, 선정 seed): {csv_path}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.figure(figsize=(6, 5))
        plt.plot([p[0] for p in pts], [p[1] for p in pts], "b-", label=f"Rule (AUC={auc:.3f})")
        plt.plot([0, 1], [0, 1], "k--", linewidth=1)
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.title("ROC - rule baseline, 4 official attacks (synthetic)")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        png = os.path.join(args.out_dir, "roc_curve.png")
        plt.savefig(png, dpi=150)
        print(f"ROC 그래프: {png}")
    except Exception as exc:  # noqa: BLE001
        print(f"matplotlib 미사용({exc}); CSV만 생성")
    return 0 if meets else 1


if __name__ == "__main__":
    raise SystemExit(main())
