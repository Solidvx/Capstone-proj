#!/usr/bin/env python3
"""Summarise an ablation CSV into per (config, attack) rates.

Denominators are explicit. attack_success can be blank (synthetic cannot measure
flooding/fuzzy availability); those rows are counted as measured=0 so a rate is
never invented from missing data. Detection and block rates use the full trial
count. The raw CSV stays the ledger; this only aggregates it.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict


def _as_bool(value: str):
    if value in ("True", "False"):
        return value == "True"
    if value in ("", "None", None):
        return None
    raise ValueError(f"invalid boolean metric: {value!r}")


def summarise(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row.get("environment", "unknown"), int(row["config"]), row["attack_type"])].append(row)

    out = []
    for (environment, config, attack) in sorted(groups):
        trials = groups[(environment, config, attack)]
        total = len(trials)
        success = [_as_bool(r["attack_success"]) for r in trials]
        measured = [s for s in success if s is not None]
        blocked = sum(_as_bool(r["blocked"]) is True for r in trials)
        detected = sum(_as_bool(r["detected"]) is True for r in trials)
        out.append({
            "environment": environment, "config": config, "attack": attack, "total": total,
            "success_measured": len(measured),
            "success": sum(s for s in measured),
            "success_rate": (sum(measured) / len(measured) * 100) if measured else None,
            "blocked": blocked, "block_rate": blocked / total * 100,
            "detected": detected, "detection_rate": detected / total * 100,
        })
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    args = parser.parse_args(argv)
    with open(args.csv_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    env = sorted({r.get("environment", "?") for r in rows})
    print(f"환경(grade): {', '.join(env)}  |  전체 {len(rows)}행")
    print(f"{'environment':>12} {'Cfg':>3} {'attack':>9} {'total':>5} {'success':>14} {'block%':>7} {'detect%':>8}")
    for s in summarise(rows):
        sr = f"{s['success']}/{s['success_measured']}" if s["success_measured"] else "미측정"
        srp = f"({s['success_rate']:.0f}%)" if s["success_rate"] is not None else ""
        print(f"{s['environment']:>12} {s['config']:>3} {s['attack']:>9} {s['total']:>5} {sr:>9}{srp:>5} "
              f"{s['block_rate']:>6.0f} {s['detection_rate']:>7.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
