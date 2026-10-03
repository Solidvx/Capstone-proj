#!/usr/bin/env python3
"""ROC and operating point for the rule IDS, plus the TC-EXP-005 normal FPR.

Threshold selection and final evaluation use disjoint seed sets (M5 3.5.1): the
ROC/operating point come from selection seeds, the reported FPR from evaluation
seeds. matplotlib is optional; without it the ROC points are written as CSV.
"""

from __future__ import annotations

import argparse
import os
import random
import sys

_SEC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("ids", "attacks"):
    sys.path.insert(0, os.path.join(_SEC, sub))

from traffic_gen import ATTACKS, gen_attack, gen_normal        # noqa: E402
from feature_extractor import windows                          # noqa: E402
from rule_baseline import RuleBaseline, roc_auc                # noqa: E402

SELECT_SEEDS = (42, 43, 44)
EVAL_SEEDS = (142, 143, 144)
TARGET_FPR = 0.05


def _dataset(seeds, train_s=90.0, normal_s=60.0, attack_s=30.0):
    rng = random.Random(seeds[0])
    train = [v for v, _, _ in windows(gen_normal(train_s, rng))]
    test = []
    for seed in seeds:
        sr = random.Random(seed)
        test += [(v, y) for v, y, _ in windows(gen_normal(normal_s, sr))]
        for atk in ATTACKS:
            test += [(v, y) for v, y, _ in windows(gen_attack(atk, attack_s, sr))]
    return train, test


def roc_points(scores, labels):
    pos = sum(labels)
    neg = len(labels) - pos
    pts = []
    for thr in sorted(set(scores)):
        tp = sum(s >= thr and y for s, y in zip(scores, labels))
        fp = sum(s >= thr and not y for s, y in zip(scores, labels))
        pts.append((fp / neg if neg else 0.0, tp / pos if pos else 0.0, thr))
    return pts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="tmp")
    args = parser.parse_args(argv)
    os.makedirs(args.out_dir, exist_ok=True)

    train, sel = _dataset(SELECT_SEEDS)
    model = RuleBaseline().fit(train)
    scores = [model.score(v) for v, _ in sel]
    labels = [y for _, y in sel]
    auc = roc_auc(scores, labels)
    pts = roc_points(scores, labels)

    chosen = next((t for fp, tp, t in pts if fp <= TARGET_FPR and tp >= 0.90), None)
    if chosen is None:
        chosen = min(pts, key=lambda p: (abs(p[0] - TARGET_FPR)))[2]
        note = "TPR>=90%&FPR<=5% 동시 만족점 없음; 차선 동작점"
    else:
        note = "TPR>=90% & FPR<=5% 만족"

    # Evaluation FPR on disjoint seeds (TC-EXP-005: normal windows only).
    _, ev = _dataset(EVAL_SEEDS)
    normal_vectors = [v for v, y in ev if y == 0]
    normal_denom = len(normal_vectors)
    normal_fpr = (sum(model.score(v) >= chosen for v in normal_vectors) / normal_denom
                  if normal_denom else 0.0)

    csv_path = os.path.join(args.out_dir, "roc_points.csv")
    with open(csv_path, "w", encoding="utf-8") as handle:
        handle.write("fpr,tpr,threshold\n")
        for fp, tp, t in pts:
            handle.write(f"{fp:.4f},{tp:.4f},{t:.4f}\n")

    print(f"ROC-AUC(선정 seed {SELECT_SEEDS}) = {auc:.3f}")
    print(f"확정 임계 = {chosen:.3f}  ({note})")
    print(f"TC-EXP-005 정상 오탐(평가 seed {EVAL_SEEDS}) = {normal_fpr:.1%} "
          f"(분모 {normal_denom} 윈도우)")
    print(f"ROC 포인트: {csv_path}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.figure(figsize=(6, 5))
        plt.plot([p[0] for p in pts], [p[1] for p in pts], "b-", label=f"Rule (AUC={auc:.3f})")
        plt.plot([0, 1], [0, 1], "k--", linewidth=1)
        plt.xlabel("False Positive Rate"); plt.ylabel("True Positive Rate")
        plt.title("ROC - CAN IDS (synthetic, selection seeds)")
        plt.legend(); plt.grid(True, alpha=0.3); plt.tight_layout()
        png = os.path.join(args.out_dir, "roc_curve.png")
        plt.savefig(png, dpi=150)
        print(f"ROC 그래프: {png}")
    except Exception as exc:  # noqa: BLE001
        print(f"matplotlib 미사용({exc}); CSV만 생성")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
