#!/usr/bin/env python3
"""Capture known-normal SocketCAN frames as IDS training JSONL plus manifest."""

from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import re
import time
import uuid
import math
from pathlib import Path

from security.can_socket import SocketCanTransport


def capture_summary(path: Path, duration_s: float, allowed_ids: set[int], *, protocol="ICD-v1.6") -> dict:
    """Check completed, continuous normal BMS/auth input before IF fitting."""
    if not math.isfinite(duration_s) or duration_s < 3:
        raise ValueError("normal capture must span at least 3 seconds")
    required={0x100,0x102}
    if protocol=="session-v2":
        from security.ids.session_detector import SESSION_IDS
        if allowed_ids!=set(SESSION_IDS):raise ValueError("session-v2 capture must include all protocol IDs")
    elif protocol!="ICD-v1.6" or allowed_ids!=required:
        raise ValueError("normal training requires exactly 0x100 and 0x102")
    previous = -1.0
    first_seen, last_seen, counts = {}, {}, {cid: 0 for cid in allowed_ids}
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                record = json.loads(line)
                t, cid = record["t"], record["can_id"]
                data = bytes.fromhex(record["data"])
                if type(t) not in (float, int) or not math.isfinite(t) or not 0 <= t <= duration_s \
                        or t < previous or type(cid) is not int or cid not in allowed_ids \
                        or len(data) != 8 or record.get("dlc", 8) != 8 \
                        or any(record.get(flag, False) for flag in ("extended", "remote", "error")):
                    raise ValueError("invalid frame or timestamp")
                if cid in required and cid in last_seen and t-last_seen[cid] >= 0.3:
                    raise ValueError("normal capture contains a 300ms receive gap")
                if cid == 0x100 and (data[0] > 200 or data[1] > 200 or data[6] > 165 or data[7]):
                    raise ValueError("normal BMS payload out of range")
                first_seen.setdefault(cid, t)
                last_seen[cid] = t
                counts[cid] += 1
                previous = t
            except (ValueError, TypeError, KeyError, AttributeError) as error:
                raise ValueError(f"invalid normal record {number}: {error}") from error
    for cid in required:
        if counts[cid] < 25 or first_seen.get(cid, duration_s) >= 0.3 \
                or duration_s-last_seen.get(cid, 0) >= 0.3:
            raise ValueError("normal capture is empty, short or incomplete")
    return {"accepted_frames": sum(counts.values()), "frames_per_id": {str(k): v for k, v in counts.items()}}


def validate_capture(path: Path, manifest_path: Path) -> dict:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or manifest.get("schema") != "ids-normal-v2" \
                or manifest.get("status") != "COMPLETE" or manifest.get("rejected_frames") != 0:
            raise ValueError("normal manifest is missing, failed or contaminated")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != manifest.get("capture_sha256"):
            raise ValueError("normal capture hash differs from manifest")
        summary = capture_summary(path, manifest["duration_s"], set(manifest["allowed_ids"]),protocol=manifest.get("protocol","ICD-v1.6"))
        if summary["accepted_frames"] != manifest.get("accepted_frames"):
            raise ValueError("normal capture count differs from manifest")
        return manifest
    except (TypeError, KeyError, AttributeError) as error:
        raise ValueError("invalid normal manifest") from error


def parse_ids(value: str) -> set[int]:
    try:
        ids = {int(item, 0) for item in value.split(",") if item}
    except ValueError as error:
        raise argparse.ArgumentTypeError("IDs must be comma-separated integers") from error
    if not ids or any(not 0 <= can_id <= 0x7FF for can_id in ids):
        raise argparse.ArgumentTypeError("IDs must be standard CAN IDs")
    return ids


def validate_session_splits(captures):
    """Validate distinct, non-overlapping attested fit/calibration/eval runs.

    Manifest timing is acquisition metadata, not cryptographic proof that an
    operator labelled normal traffic correctly. Never mix vcan and physical CAN.
    """
    manifests, paths, hashes, runs, spans = [], set(), set(), set(), []
    environment = None
    for path, manifest_path in captures:
        path = Path(path)
        manifest = validate_capture(path, Path(manifest_path))
        if manifest.get('protocol') != 'session-v2':
            raise ValueError('session splits require session-v2 captures')
        current = manifest.get('environment')
        if current not in ('vcan', 'physical-can') or environment not in (None, current):
            raise ValueError('session split environments must match')
        environment = current
        run = manifest.get('run_id')
        start = manifest.get('started_epoch_ns')
        if not isinstance(run, str) or not run or type(start) is not int or start < 0:
            raise ValueError('session splits require run identity and acquisition time')
        end = start + math.ceil(manifest['duration_s'] * 1_000_000_000)
        digest = manifest['capture_sha256']
        if path.resolve() in paths or digest in hashes or run in runs:
            raise ValueError('session splits must be independent runs and contents')
        if any(start < other_end and other_start < end for other_start, other_end in spans):
            raise ValueError('session split acquisition intervals overlap')
        paths.add(path.resolve()); hashes.add(digest); runs.add(run); spans.append((start, end))
        manifests.append(manifest)
    if len(manifests) < 2:
        raise ValueError('at least two independent session captures required')
    return manifests


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture normal CAN input for IDS training")
    parser.add_argument("--interface", default="can0")
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--ids", type=parse_ids)
    parser.add_argument("--protocol",choices=("ICD-v1.6","session-v2"),default="ICD-v1.6")
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    if args.ids is None:
        if args.protocol=="session-v2":
            from security.ids.session_detector import SESSION_IDS
            args.ids=set(SESSION_IDS)
        else:args.ids={0x100,0x102}
    if re.fullmatch(r"(?:v?can)[0-9]+", args.interface) is None:
        parser.error("interface must be canN or vcanN")
    if not 3 <= args.duration <= 86400:
        parser.error("duration must be in [3, 86400] seconds")

    output_path = Path(args.output)
    manifest_path = Path(args.manifest)
    if output_path.exists() or manifest_path.exists():
        parser.error("output and manifest must be new files")

    run_id = args.run_id or str(uuid.uuid4())
    started_epoch_ns = time.time_ns()
    started = time.monotonic()
    accepted = rejected = 0
    failure = None
    try:
        if args.protocol=="session-v2":
            from security.ids.runtime import SocketCan
            transport_factory=lambda name: closing(SocketCan(name))
        else:transport_factory=SocketCanTransport
        with output_path.open("x", encoding="utf-8") as output, \
                transport_factory(args.interface) as transport:
            if args.protocol=="session-v2":started=transport.start_time
            while time.monotonic() - started < args.duration:
                frame = transport.receive()
                if frame is None:
                    continue
                if frame.extended or frame.remote or frame.error or frame.dlc != 8 \
                        or frame.can_id not in args.ids:
                    rejected += 1
                    continue
                record = {
                    "t": frame.t-started if args.protocol=="session-v2" else time.monotonic()-started,
                    "can_id": frame.can_id,
                    "data": frame.data.hex(),
                    "dlc": frame.dlc,
                }
                output.write(json.dumps(record, separators=(",", ":")) + "\n")
                accepted += 1
            if args.protocol=="session-v2" and transport.rx_dropped:
                raise ValueError("normal session capture has socket drops")
    except (OSError, RuntimeError, ValueError, KeyboardInterrupt) as error:
        failure = str(error) or "interrupted"
    ended_duration = time.monotonic() - started
    if not output_path.exists():
        parser.exit(2, f"capture stopped: {failure}\n")
    try:
        capture_summary(output_path, ended_duration, args.ids,protocol=args.protocol)
        if rejected:
            raise ValueError("unexpected frames occurred during normal capture")
    except (ValueError, OSError) as error:
        failure = failure or str(error)

    hasher = hashlib.sha256()
    with output_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    manifest = {
        "schema": "ids-normal-v2",
        "status": "INVALID" if failure else "COMPLETE",
        "failure": failure,
        "run_id": run_id,
        "protocol": args.protocol,
        "environment": "physical-can" if args.interface.startswith("can") else "vcan",
        "interface": args.interface,
        "duration_s": ended_duration,
        "started_epoch_ns": started_epoch_ns,
        "allowed_ids": sorted(args.ids),
        "accepted_frames": accepted,
        "rejected_frames": rejected,
        "capture_sha256": digest,
    }
    try:
        with manifest_path.open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except OSError as error:
        parser.exit(2, f"manifest write failed: {error}\n")
    print(json.dumps(manifest, sort_keys=True))
    return 2 if failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
