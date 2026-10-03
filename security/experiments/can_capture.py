"""Receive-only Classical SocketCAN capture for normal training/evaluation.

Run as python -m security.experiments.can_capture. All timestamps are relative
host monotonic receive times; no remote clock subtraction or secret key output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import socket
import signal
import struct
import subprocess
import time

from security.ids.runtime_detector import Observation


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def interrupted(signum, frame):
    raise KeyboardInterrupt


def inspect_interface(channel, environment):
    result = subprocess.run(["ip", "-details", "-json", "link", "show", "dev", channel],
                            check=True, capture_output=True, text=True)
    entries = json.loads(result.stdout)
    if len(entries) != 1:
        raise ValueError("expected exactly one CAN interface")
    entry = entries[0]
    kind = entry.get("linkinfo", {}).get("info_kind")
    expected = "vcan" if environment == "vcan" else "can"
    if kind != expected or "UP" not in entry.get("flags", []):
        raise ValueError(f"expected an UP {expected} interface")
    data = entry.get("linkinfo", {}).get("info_data", {})
    # Return only bus metadata, never addresses or credentials.
    return {"kind": kind, "bitrate": data.get("bittiming", {}).get("bitrate"),
            "state": data.get("state")}


class CaptureSocket:
    """RX by default. TX and own-echo attribution require an explicit opt-in.

    MSG_CONFIRM identifies sends by THIS socket, unlike payload equality or
    MSG_DONTROUTE (which also marks sends by other local processes).
    """
    def __init__(self, channel, transmit=False):
        if not hasattr(socket, "AF_CAN"):
            raise RuntimeError("Linux SocketCAN is required")
        self.transmit = transmit
        self.dropped = 0
        self.socket = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
            self.socket.setsockopt(socket.SOL_SOCKET, 40, 1)  # Linux SO_RXQ_OVFL
            self.socket.setsockopt(socket.SOL_CAN_RAW, 2, 0x1FFFFFFF)  # error filter
            if transmit:
                self.socket.setsockopt(socket.SOL_CAN_RAW, 4, 1)  # RECV_OWN_MSGS
            self.socket.bind((channel,))
        except BaseException:
            self.socket.close()
            raise

    def receive(self, timeout=0.01):
        self.socket.settimeout(max(timeout, 0.000001))
        try:
            raw, ancillary, flags, _ = self.socket.recvmsg(72, 128)
        except socket.timeout:
            return None
        if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            raise ValueError("truncated capture")
        for level, kind, value in ancillary:
            if level == socket.SOL_SOCKET and kind == 40:
                self.dropped = struct.unpack("=I", value[:4])[0]
        if len(raw) != 16:
            raise ValueError("expected Classical CAN, not CAN FD")
        cid, dlc, data = struct.unpack("=IB3x8s", raw)
        frame = Observation(time.monotonic(), cid & 0x1FFFFFFF, data[:min(dlc, 8)], dlc,
                            bool(cid & 0x80000000), bool(cid & 0x40000000), bool(cid & 0x20000000))
        return frame, bool(flags & socket.MSG_CONFIRM)

    def send(self, can_id, data):
        if not self.transmit:
            raise RuntimeError("receive-only socket")
        if not 0 <= can_id <= 0x7FF or len(data) != 8:
            raise ValueError("expected standard DLC8 frame")
        self.socket.settimeout(0.05)
        raw = struct.pack("=IB3x8s", can_id, 8, data)
        if self.socket.send(raw) != len(raw):
            raise OSError("short CAN write")

    def close(self):
        self.socket.close()


def frame_json(frame, start=0.0):
    return {"t": frame.t - start, "can_id": frame.can_id, "data": frame.data.hex(),
            "dlc": frame.dlc, "extended": frame.extended,
            "remote": frame.remote, "error": frame.error}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--environment", choices=["vcan", "physical"], required=True)
    parser.add_argument("--duration", type=float, default=150)
    parser.add_argument("--out", required=True, help="new directory")
    parser.add_argument("--normal", action="store_true", help="operator attests attack-free input")
    args = parser.parse_args(argv)
    if not math.isfinite(args.duration) or not 0 < args.duration <= 3600:
        parser.error("duration must be finite and in (0, 3600]")
    bus = None
    previous_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        info = inspect_interface(args.channel, args.environment)
        root = Path(args.out)
        root.mkdir(parents=True, exist_ok=False)
        bus = CaptureSocket(args.channel)
        count = errors = 0
        start = time.monotonic()
        status = "COMPLETE"
        try:
            with (root / "frames.jsonl").open("x", encoding="utf-8") as stream:
                while time.monotonic() - start < args.duration:
                    received = bus.receive()
                    if received:
                        frame, _ = received
                        stream.write(json.dumps(frame_json(frame, start)) + "\n")
                        count += 1
                        errors += int(frame.error)
                stream.write(json.dumps({"tick": time.monotonic() - start}) + "\n")
        except KeyboardInterrupt:
            status = "INTERRUPTED"
        except Exception:
            status = "ERROR"
            raise
        finally:
            manifest = {"environment": args.environment, "channel": args.channel,
                        "interface": info, "normal_attested": args.normal,
                        "status": status, "duration_s": time.monotonic() - start,
                        "frames": count, "error_frames": errors, "rx_dropped": bus.dropped,
                        "clock": "host monotonic receive, relative seconds",
                        "sha256": sha256(root / "frames.jsonl")}
            (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(manifest, indent=2))
        return 0 if status == "COMPLETE" and count and not errors and not bus.dropped else 1
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Capture stopped: {error}")
        return 2
    finally:
        if bus:
            bus.close()
        signal.signal(signal.SIGTERM, previous_handler)


if __name__ == "__main__":
    raise SystemExit(main())
