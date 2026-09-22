#!/usr/bin/env python3
"""Summarize a latency CSV whose required column is latency_ms."""

from __future__ import annotations

import argparse
import csv
import math
import statistics


def percentile(samples: list[float], fraction: float) -> float:
    return samples[math.ceil(fraction * len(samples)) - 1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.input, newline="", encoding="utf-8") as source:
        samples = [float(row["latency_ms"]) for row in csv.DictReader(source)]
    if not samples:
        raise SystemExit("no latency samples")
    if any(not math.isfinite(sample) or sample < 0 for sample in samples):
        raise SystemExit("latency samples must be finite and non-negative")

    samples.sort()
    values = [
        len(samples),
        statistics.mean(samples),
        percentile(samples, 0.95),
        percentile(samples, 0.99),
        max(samples),
    ]
    with open(args.output, "w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(["samples", "avg_ms", "p95_ms", "p99_ms", "max_ms"])
        writer.writerow([values[0], *(f"{value:.3f}" for value in values[1:])])
    print(
        f"samples={values[0]} avg={values[1]:.3f}ms p95={values[2]:.3f}ms "
        f"p99={values[3]:.3f}ms max={values[4]:.3f}ms"
    )


if __name__ == "__main__":
    main()
