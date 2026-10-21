#!/usr/bin/env python3
"""Controlled IT-004 sequence: baseline, bad MAC, same-counter recovery.

Run only with the product ECU stopped.  Restart the receiver immediately before
the fixture so the explicit start counter is the receiver's first history.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import struct
import time
import uuid
from pathlib import Path

from security.can_socket import SocketCanTransport


BASELINE = bytes.fromhex("96 BE 10 68 FF EC 41 00")  # SOC 75%
TAMPERED = bytes.fromhex("C8 BE 10 68 FF EC 41 00")  # forged SOC 100%
RECOVERY = bytes.fromhex("8C BE 10 68 FF EC 41 00")  # SOC 70%


def auth_payload(key: bytes, counter: int, payload: bytes) -> bytes:
    message = struct.pack(">HI8s", 0x100, counter, payload)
    return hmac.new(key, message, hashlib.sha256).digest()[:4] + struct.pack(">I", counter)


def build_sequence(key: bytes, counter_start: int) -> list[tuple[int, bytes, str]]:
    if len(key) != 32:
        raise ValueError("SecOC key must be exactly 32 bytes")
    if not 0 <= counter_start <= 0xFFFFFFFF:
        raise ValueError("counter start must be uint32")
    rejected_counter = (counter_start + 1) & 0xFFFFFFFF
    bad_auth = bytearray(auth_payload(key, rejected_counter, TAMPERED))
    bad_auth[0] ^= 0x01
    return [
        (0x100, BASELINE, "baseline_raw"),
        (0x102, auth_payload(key, counter_start, BASELINE), "baseline_auth"),
        (0x100, TAMPERED, "tampered_raw"),
        (0x102, bytes(bad_auth), "tampered_auth"),
        (0x100, RECOVERY, "recovery_raw"),
        (0x102, auth_payload(key, rejected_counter, RECOVERY), "recovery_auth"),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Controlled SecOC MAC rejection fixture")
    parser.add_argument("--interface", default="vcan0")
    parser.add_argument("--key", required=True)
    parser.add_argument("--counter-start", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--inter-pair-delay", type=float, default=1.0,
                        help="seconds between completed raw/auth pairs (0.05..5)")
    parser.add_argument("--log", help="new JSON manifest path")
    parser.add_argument("--confirm-ecu-stopped", action="store_true")
    parser.add_argument("--confirm-receiver-reset", action="store_true")
    parser.add_argument("--confirm-isolated-test-bus", action="store_true")
    args = parser.parse_args(argv)
    if re.fullmatch(r"(?:v?can)[0-9]+", args.interface) is None:
        parser.error("interface must be canN or vcanN")
    if not args.confirm_ecu_stopped or not args.confirm_receiver_reset:
        parser.error("--confirm-ecu-stopped and --confirm-receiver-reset are required")
    if args.interface.startswith("can") and not args.confirm_isolated_test_bus:
        parser.error("physical CAN requires --confirm-isolated-test-bus")
    if not 0.05 <= args.inter_pair_delay <= 5.0:
        parser.error("inter-pair delay must be in [0.05, 5] seconds")
    if args.log and Path(args.log).exists():
        parser.error("log path already exists")
    try:
        key = Path(args.key).read_bytes()
        sequence = build_sequence(key, args.counter_start)
        sent = []
        with SocketCanTransport(args.interface) as transport:
            for index, (can_id, payload, label) in enumerate(sequence):
                transport.send(can_id, payload)
                sent.append({"label": label, "can_id": can_id, "epoch_ns": time.time_ns()})
                if index + 1 < len(sequence):
                    time.sleep(0.002 if index % 2 == 0 else args.inter_pair_delay)
        result = {
            "run_id": str(uuid.uuid4()),
            "protocol": "ICD-v1.6",
            "interface": args.interface,
            "counter_start": args.counter_start,
            "inter_pair_delay_s": args.inter_pair_delay,
            "expected": {
                "baseline_soc_percent": 75.0,
                "tampered_soc_percent_not_published": 100.0,
                "recovery_soc_percent": 70.0,
                "mac_failure_count": 1,
            },
            "sent": sent,
        }
        if args.log:
            with Path(args.log).open("x", encoding="utf-8") as stream:
                json.dump(result, stream, indent=2, sort_keys=True)
                stream.write("\n")
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(2, f"tamper fixture stopped: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
