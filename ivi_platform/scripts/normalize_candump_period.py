#!/usr/bin/env python3
"""Normalize `candump -L` absolute timestamps for TC-PERF-002."""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re


LINE = re.compile(
    r"^\((?P<timestamp>[0-9]+(?:\.[0-9]+)?)\)\s+"
    r"(?P<interface>[A-Za-z0-9_.-]+)\s+"
    r"(?P<can_id>[0-9A-Fa-f]{3})#(?P<data>[0-9A-Fa-f]*)\s*$"
)


def timestamp_ns(value: str) -> int:
    try:
        timestamp = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("invalid candump timestamp") from error
    nanoseconds = timestamp * Decimal(1_000_000_000)
    if timestamp < 0 or nanoseconds != nanoseconds.to_integral_value():
        raise ValueError("timestamp must be non-negative with at most ns precision")
    return int(nanoseconds)


def parse_log(path: Path, expected_interface: str) -> list[tuple[int, int, int]]:
    rows = []
    previous = None
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            match = LINE.fullmatch(line.strip())
            if not match:
                raise ValueError(f"unsupported or damaged candump line {line_number}")
            if match.group("interface") != expected_interface:
                raise ValueError(f"unexpected interface at line {line_number}")
            data = match.group("data")
            if len(data) > 16 or len(data) % 2:
                raise ValueError(f"invalid Classical CAN payload at line {line_number}")
            can_id = int(match.group("can_id"), 16)
            if not 0 <= can_id <= 0x7FF:
                raise ValueError(f"non-standard CAN ID at line {line_number}")
            current = timestamp_ns(match.group("timestamp"))
            if previous is not None and current < previous:
                raise ValueError(f"timestamp moved backwards at line {line_number}")
            previous = current
            rows.append((can_id, current, len(data)//2))
    if not rows:
        raise ValueError("candump input contains no frames")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize candump -L for period analysis")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--boot-id", required=True)
    parser.add_argument("--interface", default="can0")
    parser.add_argument("--rx-errors-before", type=int, required=True)
    parser.add_argument("--rx-errors-after", type=int, required=True)
    parser.add_argument("--rx-dropped-before", type=int, required=True)
    parser.add_argument("--rx-dropped-after", type=int, required=True)
    parser.add_argument("--bus-off-before", type=int, required=True)
    parser.add_argument("--bus-off-after", type=int, required=True)
    args = parser.parse_args(argv)
    source = Path(args.input)
    output = Path(args.output)
    manifest_path = Path(args.manifest)
    if output.exists() or manifest_path.exists():
        parser.error("output and manifest must be new files")
    counters = (
        args.rx_errors_before, args.rx_errors_after,
        args.rx_dropped_before, args.rx_dropped_after,
        args.bus_off_before, args.bus_off_after,
    )
    if any(value < 0 for value in counters):
        parser.error("CAN statistics must be non-negative")
    try:
        rows = parse_log(source, args.interface)
        with output.open("x", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["run_id", "boot_id", "sample_id", "can_id", "timestamp_ns", "dlc", "frame_kind"])
            for sample_id, (can_id, received_ns, dlc) in enumerate(rows):
                writer.writerow([args.run_id, args.boot_id, sample_id, can_id, received_ns, dlc, "standard-data"])
        csv_hash = hashlib.sha256(output.read_bytes()).hexdigest()
        manifest = {
            "schema": "period-capture-v2",
            "run_id": args.run_id,
            "boot_id": args.boot_id,
            "clock": "candump-absolute-realtime",
            "interface": args.interface,
            "target_can_id": 0x100,
            "row_count": len(rows),
            "target_row_count": sum(can_id == 0x100 for can_id, _, _ in rows),
            "tool": "normalize_candump_period-v2",
            "environment": "physical-can" if args.interface.startswith("can") else "vcan",
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "csv_sha256": csv_hash,
            "rx_errors_before": args.rx_errors_before,
            "rx_errors_after": args.rx_errors_after,
            "rx_dropped_before": args.rx_dropped_before,
            "rx_dropped_after": args.rx_dropped_after,
            "bus_off_before": args.bus_off_before,
            "bus_off_after": args.bus_off_after,
        }
        with manifest_path.open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, indent=2, sort_keys=True)
            stream.write("\n")
        print(json.dumps(manifest, sort_keys=True))
        return 0
    except (OSError, ValueError) as error:
        parser.exit(2, f"normalization invalid: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
