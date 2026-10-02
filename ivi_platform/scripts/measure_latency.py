#!/usr/bin/env python3
"""Summarize IVI stage timestamps or a legacy latency_ms CSV."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict


def percentile(samples: list[float], fraction: float) -> float:
    return samples[math.ceil(fraction * len(samples)) - 1]


def summary(samples: list[float]) -> tuple[int, float, float, float, float]:
    if not samples:
        raise SystemExit("no complete latency samples")
    if any(not math.isfinite(sample) or sample < 0 for sample in samples):
        raise SystemExit("latency samples must be finite and non-negative")
    samples.sort()
    return (
        len(samples),
        statistics.mean(samples),
        percentile(samples, 0.95),
        percentile(samples, 0.99),
        max(samples),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-samples", type=int)
    args = parser.parse_args()

    with open(args.input, newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        raise SystemExit("no latency rows")

    intervals: dict[str, list[float]] = {}
    complete = 0
    incomplete = 0
    if "latency_ms" in rows[0]:
        intervals["latency"] = [float(row["latency_ms"]) for row in rows]
        complete = len(rows)
    else:
        required = {"run_id", "boot_id", "sample_id", "stage", "timestamp_ns"}
        if not required.issubset(rows[0]):
            raise SystemExit("stage CSV is missing required columns")
        samples: dict[tuple[str, str, str], dict[str, int]] = defaultdict(dict)
        for row in rows:
            key = (row["run_id"], row["boot_id"], row["sample_id"])
            stage = row["stage"].upper()
            if stage in samples[key]:
                raise SystemExit(f"duplicate stage {stage} for sample {key}")
            samples[key][stage] = int(row["timestamp_ns"])
        interval_pairs = {
            "T1-T4": ("T1", "T4"),
            "T1-T2": ("T1", "T2"),
            "T2-T3": ("T2", "T3"),
            "T3-T4": ("T3", "T4"),
        }
        intervals = {name: [] for name in interval_pairs}
        for stages in samples.values():
            if not {"T1", "T2", "T3", "T4"}.issubset(stages):
                incomplete += 1
                continue
            if not (stages["T1"] <= stages["T2"] <= stages["T3"] <= stages["T4"]):
                raise SystemExit("timestamps are not monotonic within a sample")
            complete += 1
            for name, (start, end) in interval_pairs.items():
                intervals[name].append((stages[end] - stages[start]) / 1_000_000.0)

    expected = args.expected_samples if args.expected_samples is not None else complete + incomplete
    missing = max(expected - complete, 0)
    with open(args.output, "w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(
            ["interval", "samples", "avg_ms", "p95_ms", "p99_ms", "max_ms", "missing"]
        )
        for name, samples in intervals.items():
            count, average, p95, p99, maximum = summary(samples)
            writer.writerow(
                [name, count, f"{average:.3f}", f"{p95:.3f}", f"{p99:.3f}",
                 f"{maximum:.3f}", missing]
            )
            print(
                f"{name}: samples={count} avg={average:.3f}ms p95={p95:.3f}ms "
                f"p99={p99:.3f}ms max={maximum:.3f}ms missing={missing}"
            )
    if incomplete or missing:
        raise SystemExit(f"incomplete measurement: incomplete={incomplete} missing={missing}")


if __name__ == "__main__":
    main()
