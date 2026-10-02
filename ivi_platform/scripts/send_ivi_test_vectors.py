#!/usr/bin/env python3
"""Send ICD v1.5 Node B test vectors through can-utils.

Protected data is always followed by its SecOC authentication frame. Use
--dummy-key only on an isolated test bus; it selects the public 00..1f key used
by the C++ unit tests.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import struct
import subprocess
import time
from pathlib import Path

BMS_NORMAL = bytes.fromhex("96 BE 10 68 FF EC 41 00")
FAILSAFE_WARNING = bytes.fromhex("00 01 01 26 46 00 00 00")
IDS_FLOODING = bytes.fromhex("04 96 01 00 00 00 00 01")


def auth_payload(key: bytes, can_id: int, counter: int, payload: bytes) -> bytes:
    authenticated = struct.pack(">HI8s", can_id, counter, payload)
    return hmac.new(key, authenticated, hashlib.sha256).digest()[:4] + struct.pack(">I", counter)


def send(interface: str, can_id: int, payload: bytes) -> None:
    subprocess.run(
        ["cansend", interface, f"{can_id:03X}#{payload.hex().upper()}"], check=True
    )


def load_key(args: argparse.Namespace) -> bytes:
    if args.dummy_key:
        return bytes(range(32))
    if not args.key:
        raise SystemExit("protected scenarios require --key PATH or --dummy-key")
    key = Path(args.key).read_bytes()
    if len(key) != 32:
        raise SystemExit("SecOC key must be exactly 32 bytes")
    return key


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=["bms", "failsafe", "ids", "tamper"])
    parser.add_argument("--interface", default="vcan0")
    parser.add_argument("--counter", type=int, default=0)
    parser.add_argument("--key")
    parser.add_argument("--dummy-key", action="store_true")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--interval-ms", type=float, default=100.0)
    args = parser.parse_args()

    if args.count < 1 or args.interval_ms < 0:
        raise SystemExit("--count must be positive and --interval-ms non-negative")

    if args.scenario == "ids":
        for index in range(args.count):
            send(args.interface, 0x200, IDS_FLOODING)
            if index + 1 < args.count:
                time.sleep(args.interval_ms / 1000.0)
        return

    key = load_key(args)
    for index in range(args.count):
        counter = (args.counter + index) & 0xFFFFFFFF
        if args.scenario == "bms":
            send(args.interface, 0x100, BMS_NORMAL)
            send(args.interface, 0x102, auth_payload(key, 0x100, counter, BMS_NORMAL))
        elif args.scenario == "failsafe":
            send(args.interface, 0x101, FAILSAFE_WARNING)
            send(args.interface, 0x103, auth_payload(key, 0x101, counter, FAILSAFE_WARNING))
        else:
            send(args.interface, 0x100, BMS_NORMAL)
            auth = bytearray(auth_payload(key, 0x100, counter, BMS_NORMAL))
            auth[0] ^= 0x80
            send(args.interface, 0x102, bytes(auth))
        if index + 1 < args.count:
            time.sleep(args.interval_ms / 1000.0)


if __name__ == "__main__":
    main()
