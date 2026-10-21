"""IT-004 controlled test fixture using ONLY a public dummy key.

Prepare a dummy key with --prepare-key PATH, start an independent IVI test
instance with that key, stop other senders, then run --channel ... --out ... .
Normal traffic, one MAC-bit mutation, then normal recovery with the SAME next
counter test that a MAC failure did not consume the counter. IVI logs/UI are
required for IT-004; the local reference receiver cannot declare product PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import struct
import signal
import subprocess
import time

from security.experiments.can_capture import CaptureSocket, inspect_interface, sha256, interrupted
from security.experiments.live_ablation import Children, collect
from security.experiments.live_receiver import ReferenceReceiver

DUMMY_KEY = b"\x01" * 32  # public fixture only, never deployment credentials
NORMAL = bytes.fromhex("96be1068ffec4100")
ALTERED = bytes.fromhex("c8be1068ffec4100")


def auth(payload, counter):
    message = struct.pack(">HI", 0x100, counter) + payload
    return hmac.new(DUMMY_KEY, message, hashlib.sha256).digest()[:4] + struct.pack(">I", counter)


def sequence(start):
    if not 0 <= start <= 0xFFFFFFFF:
        raise ValueError("counter must be uint32")
    next_counter = (start + 1) & 0xFFFFFFFF
    good = auth(ALTERED, next_counter)
    bad = bytes([good[0] ^ 1]) + good[1:]
    return [("normal", NORMAL, auth(NORMAL, start)),
            ("mutated_mac", ALTERED, bad),
            ("recovery_same_counter", NORMAL, auth(NORMAL, next_counter))]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-key", help="write public dummy key to a NEW file and exit")
    parser.add_argument("--channel")
    parser.add_argument("--environment", choices=["vcan", "physical"])
    parser.add_argument("--out")
    parser.add_argument("--counter-start", type=int, default=0,
                        help="known counter for independent fixture receiver (no product reset)")
    parser.add_argument("--i-am-on-a-test-bus", action="store_true")
    args = parser.parse_args(argv)
    if args.prepare_key:
        try:
            fd = os.open(args.prepare_key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(DUMMY_KEY)
            print("Public dummy key prepared; use only in an independent test instance.")
            return 0
        except OSError as error:
            print(error)
            return 2
    if not args.channel or not args.environment or not args.out:
        parser.error("require --channel, --environment and --out")
    if args.environment == "physical" and not args.i_am_on_a_test_bus:
        parser.error("physical fixture requires isolated test bus acknowledgement")
    try:
        steps = sequence(args.counter_start)
    except ValueError as error:
        parser.error(str(error))
    bus = None
    result = None
    previous_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        info = inspect_interface(args.channel, args.environment)
        root = Path(args.out)
        root.mkdir(parents=True, exist_ok=False)
        result = {"environment": args.environment, "interface": info, "key": "public dummy only",
                  "product_verdict": "NOT_RUN", "status": "INCOMPLETE", "steps": []}
        bus = CaptureSocket(args.channel, transmit=True)
        deadline = time.monotonic() + .5
        while time.monotonic() < deadline:
            if bus.receive():
                raise RuntimeError("fixture requires other transmitters stopped; do not race the ECU")
        receiver = ReferenceReceiver(True, DUMMY_KEY)
        with (root / "frames.jsonl").open("x", encoding="utf-8") as stream:
            for name, payload, mac in steps:
                bus.send(0x100, payload)
                bus.send(0x102, mac)
                records, _, _, _, _, _ = collect(bus, receiver, .1, stream, Children())
                if any(not r.own and r.can_id >= 0 for r in records):
                    raise RuntimeError("foreign traffic invalidates controlled MAC fixture")
                reasons = [o.reason for r in records for o in r.outcomes]
                expected = "MAC_FAIL" if name == "mutated_mac" else "AUTHENTICATED"
                echoes = [r for r in records if r.own]
                passed = len(echoes) == 2 and expected in reasons
                result["steps"].append({"name": name, "expected": expected, "reasons": reasons,
                                        "reference_pass": passed})
                if not passed:
                    raise RuntimeError("fixture timing/echo/auth condition failed; not an IT-004 pass")
        result["status"] = "REFERENCE_PASS"
        print("Reference sequence passed. Attach IVI MAC-failure, unchanged-state and recovery evidence.")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        if result is not None:
            result["error"] = str(error)
        print(f"Fixture stopped: {error}")
        return 2
    except KeyboardInterrupt:
        if result is not None:
            result["status"] = "INTERRUPTED"
        return 130
    finally:
        if bus:
            bus.close()
        if result is not None:
            raw = Path(args.out) / "frames.jsonl"
            result["raw_sha256"] = sha256(raw) if raw.exists() else None
            (Path(args.out) / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        signal.signal(signal.SIGTERM, previous_handler)


if __name__ == "__main__":
    raise SystemExit(main())
