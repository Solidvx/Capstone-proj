#!/usr/bin/env python3
"""Ablation runner: 3 configs x 4 attacks x N trials.

Synthetic mode runs fully offline (M5 grade 1, pre-check) and is the default so a
machine without CAN can produce the full matrix. Physical judging reuses
ablation_core on frames captured from a real bus; that path is driven on the
RPis and is not invoked here. Every row carries its environment grade.
"""

from __future__ import annotations

import argparse
import csv
import os

from ablation_core import CONFIGS, CSV_FIELDS, MATRIX_ATTACKS, evaluate_synthetic_trial


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="SecOC/IDS ablation (synthetic pre-check)")
    parser.add_argument("--mode", choices=["synthetic"], default="synthetic",
                        help="synthetic is the offline pre-check; physical judging runs on the RPis")
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--out", required=True, help="new CSV path; existing files are not overwritten")
    args = parser.parse_args(argv)

    if args.trials < 1:
        parser.error("--trials must be positive")
    if os.path.exists(args.out):
        parser.error(f"{args.out} exists; refusing to overwrite")

    rows = []
    for config in sorted(CONFIGS):
        for attack in MATRIX_ATTACKS:
            for trial in range(args.trials):
                rows.append(evaluate_synthetic_trial(config, attack, trial))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    expected = len(CONFIGS) * len(MATRIX_ATTACKS) * args.trials
    print(f"wrote {len(rows)} rows to {args.out} (expected {expected})")
    return 0 if len(rows) == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
