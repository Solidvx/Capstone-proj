"""Evaluate a separately captured normal run, with rules and optional rules+IF.

Complete fixed 1s windows after a declared warmup; empty windows invalidate the
capture (retained in the report). Timer ticks are replayed even across silence.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
import math
from pathlib import Path

from security.experiments.can_capture import sha256
from security.ids.runtime import read_records, train_model
from security.ids.runtime_detector import Config, Observation, RuntimeDetector


def load_capture(directory):
    root = Path(directory)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    path = root / "frames.jsonl"
    if (manifest["status"] != "COMPLETE" or not manifest["normal_attested"]
            or manifest["rx_dropped"] or manifest["error_frames"] or manifest["sha256"] != sha256(path)):
        raise ValueError("normal capture incomplete, unconfirmed, lost, or hash mismatch")
    records = list(read_records(path))
    previous = 0.0
    frames = []
    end = manifest["duration_s"]
    if not math.isfinite(end) or end <= 0:
        raise ValueError("invalid capture duration")
    for item in records:
        t = item.t if isinstance(item, Observation) else item
        if not math.isfinite(t) or not previous <= t <= end:
            raise ValueError("invalid capture timestamps")
        previous = t
        if isinstance(item, Observation):
            frames.append(item)
    if not frames:
        raise ValueError("empty normal capture")
    return frames, manifest, path


def evaluate(frames, end, warmup=2, model=None, key=None):
    if not math.isfinite(end) or not math.isfinite(warmup) or warmup < 0 or end <= warmup:
        raise ValueError("invalid evaluation interval")
    detector = RuntimeDetector(Config(), key, model)
    windows = [{"window": i, "frames": 0, "reasons": []} for i in range(int(end - warmup))]
    reasons = Counter()

    def collect(events):
        for event in events:
            i = math.floor(event.timestamp - warmup)
            if 0 <= i < len(windows) and event.result == "ANOMALY":
                windows[i]["reasons"].append(event.reason)
                reasons[event.reason] += 1

    next_tick = 0.05
    previous = 0.0
    for frame in frames:
        if not math.isfinite(frame.t) or not previous <= frame.t <= end:
            raise ValueError("unordered frame")
        previous = frame.t
        while next_tick < frame.t:
            collect(detector.tick(next_tick))
            next_tick += 0.05
        collect(detector.observe(frame))
        i = math.floor(frame.t - warmup)
        if 0 <= i < len(windows) and frame.can_id != 0x200:
            windows[i]["frames"] += 1
    while next_tick <= end:
        collect(detector.tick(next_tick))
        next_tick += 0.05
    empty = sum(w["frames"] == 0 for w in windows)
    fp = sum(bool(w["reasons"]) for w in windows)
    fpr = fp / len(windows) if windows else None
    return {"mode": "rules+if" if model is not None else "rules-only", "config": asdict(Config()),
            "warmup_s": warmup, "complete_windows": len(windows), "empty_windows": empty,
            "false_positive_windows": fp, "fpr": fpr, "reasons": dict(reasons), "windows": windows,
            "status": "INVALID" if empty or len(windows) < 100 else "PASS" if fpr <= .05 else "FAIL"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", help="evaluation capture directory")
    parser.add_argument("--train", help="different normal capture directory for IF")
    parser.add_argument("--key", help="optional key file; content never written")
    parser.add_argument("--warmup", type=float, default=2)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        frames, manifest, path = load_capture(args.capture)
        key = Path(args.key).read_bytes() if args.key else None
        results = [evaluate(frames, manifest["duration_s"], args.warmup, key=key)]
        train_hash = None
        if args.train:
            _, train_manifest, train_path = load_capture(args.train)
            if path.resolve() == train_path.resolve() or manifest["sha256"] == train_manifest["sha256"]:
                raise ValueError("training and evaluation captures must be independent")
            train_hash = train_manifest["sha256"]
            results.append(evaluate(frames, manifest["duration_s"], args.warmup,
                                    train_model(train_path), key))
        report = {"environment": manifest["environment"], "capture_sha256": manifest["sha256"],
                  "training_sha256": train_hash, "secoc_observation": key is not None, "results": results}
        with Path(args.out).open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
        for row in results:
            print(row["mode"], row["status"], row["false_positive_windows"], "/", row["complete_windows"])
        return 0 if all(r["status"] == "PASS" for r in results) else 1
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print(f"Evaluation stopped: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
