#!/usr/bin/env python3
"""Strict TC-PERF-002 analysis of normalized 0x100 receive timestamps."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics


MIN_INTERVALS = 100
LOWER_MS = 90.0
UPPER_MS = 110.0


class InvalidMeasurement(ValueError):
    pass


def analyze(input_path: Path, manifest_path: Path) -> dict:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw = input_path.read_bytes()
        rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    except (OSError, UnicodeError, json.JSONDecodeError, csv.Error) as error:
        raise InvalidMeasurement(f"unreadable input: {error}") from error
    required_manifest = {
        "schema", "run_id", "boot_id", "clock", "target_can_id", "row_count",
        "csv_sha256", "rx_errors_before", "rx_errors_after",
        "rx_dropped_before", "rx_dropped_after", "bus_off_before", "bus_off_after",
    }
    if not isinstance(manifest, dict) or not required_manifest.issubset(manifest):
        raise InvalidMeasurement("manifest is missing required fields")
    if manifest["schema"] != "period-capture-v2":
        raise InvalidMeasurement("unsupported manifest schema")
    if type(manifest["target_can_id"]) is not int or manifest["target_can_id"] != 0x100:
        raise InvalidMeasurement("TC-PERF-002 target must be 0x100")
    if type(manifest["row_count"]) is not int or manifest["row_count"] < 1:
        raise InvalidMeasurement("invalid manifest row count")
    if any(not isinstance(manifest[name], str) or not manifest[name].strip()
           for name in ("run_id", "boot_id", "clock", "csv_sha256")):
        raise InvalidMeasurement("invalid manifest identity or clock")
    if hashlib.sha256(raw).hexdigest() != manifest["csv_sha256"]:
        raise InvalidMeasurement("CSV hash does not match manifest")
    if len(rows) != manifest["row_count"]:
        raise InvalidMeasurement("CSV row count does not match manifest")
    if manifest["clock"] not in ("candump-absolute-realtime", "monotonic"):
        raise InvalidMeasurement("unsupported or unknown clock")
    for before, after, label in (
        (manifest["rx_errors_before"], manifest["rx_errors_after"], "RX errors"),
        (manifest["rx_dropped_before"], manifest["rx_dropped_after"], "RX drops"),
        (manifest["bus_off_before"], manifest["bus_off_after"], "bus-off"),
    ):
        if type(before) is not int or type(after) is not int or before < 0 or after < before:
            raise InvalidMeasurement(f"invalid {label} counters")
        if after != before:
            raise InvalidMeasurement(f"{label} changed during capture")

    required_columns = {"run_id", "boot_id", "sample_id", "can_id", "timestamp_ns", "dlc", "frame_kind"}
    if not rows or not required_columns.issubset(rows[0]):
        raise InvalidMeasurement("CSV is empty or missing required columns")
    target_id = manifest["target_can_id"]
    samples = []
    seen_ids = set()
    previous_ns = None
    for index, row in enumerate(rows):
        if None in row or any(value is None for value in row.values()):
            raise InvalidMeasurement("damaged CSV row")
        if row["run_id"] != manifest["run_id"] or row["boot_id"] != manifest["boot_id"]:
            raise InvalidMeasurement("run or boot ID differs from manifest")
        try:
            sample_id = int(row["sample_id"])
            can_id = int(row["can_id"])
            received_ns = int(row["timestamp_ns"])
            dlc = int(row["dlc"])
        except (ValueError, TypeError) as error:
            raise InvalidMeasurement("CSV contains a non-integer field") from error
        if sample_id in seen_ids or sample_id != index or received_ns < 0:
            raise InvalidMeasurement("sample IDs or timestamps are invalid")
        seen_ids.add(sample_id)
        if not 0 <= can_id <= 0x7FF or not 0 <= dlc <= 8 or row["frame_kind"] != "standard-data":
            raise InvalidMeasurement("invalid Classical standard data frame")
        if previous_ns is not None and received_ns < previous_ns:
            raise InvalidMeasurement("capture timestamps moved backwards")
        previous_ns = received_ns
        if can_id == target_id:
            if dlc != 8:
                raise InvalidMeasurement("BMS 0x100 must have DLC 8")
            samples.append(received_ns)
    if len(samples) < MIN_INTERVALS + 1:
        raise InvalidMeasurement(
            f"need at least {MIN_INTERVALS + 1} target frames, got {len(samples)}"
        )
    if any(current <= previous for previous, current in zip(samples, samples[1:])):
        raise InvalidMeasurement("target timestamps are duplicated or moved backwards")
    intervals = [(current-previous)/1_000_000.0
                 for previous, current in zip(samples, samples[1:])]
    if any(not math.isfinite(value) or value <= 0 for value in intervals):
        raise InvalidMeasurement("intervals must be finite and positive")
    outliers = [value for value in intervals if not LOWER_MS <= value <= UPPER_MS]
    return {
        "status": "PASS" if not outliers else "FAIL",
        "target_can_id": target_id,
        "frames": len(samples),
        "intervals": len(intervals),
        "mean_ms": statistics.mean(intervals),
        "stdev_ms": statistics.pstdev(intervals),
        "min_ms": min(intervals),
        "max_ms": max(intervals),
        "outlier_count": len(outliers),
        "limits_ms": [LOWER_MS, UPPER_MS],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze TC-PERF-002 period capture")
    parser.add_argument("--input", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", help="new JSON result path")
    args = parser.parse_args(argv)
    try:
        result = analyze(Path(args.input), Path(args.manifest))
        if args.output:
            with Path(args.output).open("x", encoding="utf-8") as stream:
                json.dump(result, stream, indent=2, sort_keys=True)
                stream.write("\n")
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "PASS" else 1
    except (InvalidMeasurement, OSError) as error:
        print(json.dumps({"status": "INVALID", "reason": str(error)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
