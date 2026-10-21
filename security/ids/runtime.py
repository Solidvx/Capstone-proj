"""python -m security.ids.runtime --help (run from repository root)."""
from __future__ import annotations

import argparse
import errno
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import socket
import struct
import sys
import time

from .if_detector import IsolationForestDetector
from .runtime_detector import Config, Observation, RuntimeDetector


def read_records(path):
    with Path(path).open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if "tick" in record:
                    yield float(record["tick"])
                else:
                    data=bytes.fromhex(record["data"])
                    yield Observation(float(record["t"]), int(record["can_id"]), data,
                                      int(record.get("dlc",len(data))),
                                      bool(record.get("extended",False)),
                                      bool(record.get("remote",False)),bool(record.get("error",False)))
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError(f"invalid replay record at line {number}") from error


def normal_vectors(path):
    """Use the streaming detector's feature boundary, including idle timer ticks."""
    from .runtime_detector import KNOWN_IDS
    vectors = []
    class Collector:
        def anomaly(self, vector):
            vectors.append(vector)
            return -1.0
    detector = RuntimeDetector(model=Collector())
    next_tick = 0.05
    previous = float("-inf")
    for frame in read_records(path):
        timestamp = frame.t if isinstance(frame, Observation) else frame
        if not math.isfinite(timestamp) or timestamp < max(0, previous):
            raise ValueError("normal training timestamps must be ordered")
        if timestamp > 10000:
            raise ValueError('normal capture must use bounded relative seconds')
        previous=timestamp
        while next_tick < timestamp:
            detector.tick(next_tick)
            next_tick += .05
        if not isinstance(frame,Observation):
            detector.tick(timestamp)
            continue
        if frame.can_id not in KNOWN_IDS or frame.dlc!=8 or len(frame.data)!=8 or frame.extended or frame.remote or frame.error:
            raise ValueError("normal training contains invalid frames")
        detector.observe(frame)
        if len(detector.frames)>=4096 or len(vectors)>10000:
            raise ValueError("training capture exceeds bounded capacity")
    if len(vectors)<2:
        raise ValueError("normal training needs at least two completed 1s windows")
    return vectors


def train_model(path, calibration_path=None):
    model = IsolationForestDetector().fit(normal_vectors(path))
    if calibration_path is not None:
        if Path(path).read_bytes() == Path(calibration_path).read_bytes():
            raise ValueError('training and calibration must be independent')
        model.calibrate(normal_vectors(calibration_path))
    return model


class SocketCan:
    # Linux asm-generic/socket.h: fixed 64-bit __kernel_timespec ABI.
    TIMESTAMPNS_NEW = 64

    def __init__(self, interface):
        if not hasattr(socket,"AF_CAN"):
            raise RuntimeError("SocketCAN requires Linux; use --replay on this OS")
        self.socket=socket.socket(socket.AF_CAN,socket.SOCK_RAW,socket.CAN_RAW)
        try:
            self.start_time = time.monotonic()
            self.clock_offset_ns = time.monotonic_ns() - time.time_ns()
            self.idle_time = self.start_time
            self.socket.setsockopt(socket.SOL_SOCKET, self.TIMESTAMPNS_NEW, 1)
            self.socket.bind((interface,))
            self.socket.settimeout(0.05)
        except Exception:
            self.socket.close()
            raise

    def receive(self):
        # Use the time BEFORE waiting as the idle watermark. A frame can arrive
        # just after timeout; advancing to post-timeout time would overtake it.
        self.idle_time = time.monotonic()
        try:
            raw, ancillary, flags, _ = self.socket.recvmsg(72, socket.CMSG_SPACE(16))
        except socket.timeout:
            self._check_clock()
            return None
        self._check_clock()
        if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            raise ValueError("truncated CAN frame or receive timestamp")
        stamps = [data for level, kind, data in ancillary
                  if level == socket.SOL_SOCKET and kind == self.TIMESTAMPNS_NEW]
        if len(stamps) != 1 or len(stamps[0]) != 16:
            raise ValueError("missing or invalid kernel receive timestamp")
        seconds, nanoseconds = struct.unpack("=qq", stamps[0])
        if seconds < 0 or not 0 <= nanoseconds < 1_000_000_000:
            raise ValueError("invalid kernel receive timestamp")
        received = (seconds * 1_000_000_000 + nanoseconds + self.clock_offset_ns) / 1e9
        if len(raw)!=16:
            raise ValueError("expected a Classical CAN frame")
        cid,dlc,data=struct.unpack("=IB3x8s",raw)
        return Observation(received,cid&0x1fffffff,data[:min(dlc,8)],dlc,
                           bool(cid&0x80000000),bool(cid&0x40000000),bool(cid&0x20000000))

    def _check_clock(self):
        # Never silently reinterpret a wall-clock step as a CAN timing anomaly.
        offset = time.monotonic_ns() - time.time_ns()
        if abs(offset - self.clock_offset_ns) > 10_000_000:
            raise RuntimeError("receive clock mapping changed by more than 10ms; restart capture")

    def send(self,payload):
        packed=struct.pack("=IB3x8s",0x200,8,payload)
        if self.socket.send(packed, socket.MSG_DONTWAIT)!=len(packed):
            raise OSError("short CAN write")

    def close(self):
        self.socket.close()


def run_replay(detector,records,output):
    count=0
    for record in records:
        events=detector.observe(record) if isinstance(record,Observation) else detector.tick(record)
        if isinstance(record,Observation) and not events:
            output.write(json.dumps({"timestamp":record.t,"can_id":record.can_id,
                                     "result":"NORMAL","reason":"NO_RULE_VIOLATION",
                                     "anomaly_score":0.0})+"\n")
        for event in events:
            output.write(json.dumps(asdict(event),sort_keys=True)+"\n")
            count+=1
    return count


def send_alert(transport, payload, timestamp, last_attempt, output):
    """Bound alert attempts, including failures; never block CAN observation."""
    if timestamp - last_attempt.get("all", float("-inf")) < 0.1:
        return
    last_attempt["all"] = timestamp
    record = {"timestamp": timestamp, "can_id": 0x200, "data": payload.hex()}
    try:
        transport.send(payload)
    except OSError as error:
        if error.errno not in (errno.ENOBUFS, errno.EAGAIN, errno.EWOULDBLOCK):
            raise
        record.update(result="ALERT_TX_FAILED", errno=error.errno,
                      reason="TX_BACKPRESSURE", retry=False)
    else:
        # Socket acceptance is not evidence of delivery to the IVI.
        record.update(result="ALERT_SENT")
    output.write(json.dumps(record) + "\n")


def main(argv=None):
    parser=argparse.ArgumentParser(description="Node A CAN IDS: offline replay or live SocketCAN")
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--replay",help="JSONL frames and explicit timer ticks")
    source.add_argument("--interface",help="Linux SocketCAN interface, opened only when selected")
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--train-normal",help="separate known-normal JSONL capture for mandatory IF mode")
    mode.add_argument("--rules-only",action="store_true",help="explicit rule-only development/ablation mode")
    parser.add_argument('--calibrate-normal', help='independent normal JSONL, at least 100 model windows')
    parser.add_argument("--secoc-key",help="32-byte key file for independent local SecOC observation")
    parser.add_argument("--config",help="JSON Config overrides; thresholds require deployment calibration")
    parser.add_argument("--log",required=True,help="new output JSONL path; existing files are not overwritten")
    parser.add_argument("--send-alerts",action="store_true",help="opt in to ICD 0x200 transmission on --interface")
    parser.add_argument("--parent-pid", type=int, help="owned live run: stop when parent exits instead of duration")
    parser.add_argument("--duration",type=float,default=30.0)
    args=parser.parse_args(argv)
    if args.send_alerts and not args.interface:
        parser.error("--send-alerts requires --interface")
    if args.calibrate_normal and not args.train_normal:
        parser.error('--calibrate-normal requires --train-normal')
    if not 0<args.duration<86400:
        parser.error("duration must be between 0 and 86400 seconds")
    if args.parent_pid is not None and (not args.interface or args.parent_pid != os.getppid()):
        parser.error("--parent-pid must identify the current parent of a live IDS")
    transport=None
    try:
        config=Config(**(json.loads(Path(args.config).read_text()) if args.config else {}))
        key=Path(args.secoc_key).read_bytes() if args.secoc_key else None
        model=train_model(args.train_normal, args.calibrate_normal) if args.train_normal else None
        detector=RuntimeDetector(config,key,model,time.monotonic() if args.interface else 0.0)
        with Path(args.log).open("x",encoding="utf-8") as output:
            output.write(json.dumps({"result":"START","mode":"rules+if" if model else "rules-only",
                                     "secoc_observation":key is not None,"config":asdict(config),
                                     "if_calibration":model.calibration if model else None})+"\n")
            if args.replay:
                count=run_replay(detector,read_records(args.replay),output)
                output.write(json.dumps({"result":"END","events":count})+"\n")
            else:
                transport=SocketCan(args.interface)
                detector=RuntimeDetector(config,key,model,transport.start_time)
                output.write(json.dumps({"result":"CLOCK", "source":"SO_TIMESTAMPNS_NEW",
                                         "mapping":"fixed realtime to monotonic",
                                         "offset_ns":transport.clock_offset_ns})+"\n")
                deadline=time.monotonic()+args.duration
                last_sent={}
                while (os.getppid() == args.parent_pid if args.parent_pid is not None else time.monotonic()<deadline):
                    frame=transport.receive()
                    events=detector.observe(frame) if frame else detector.tick(transport.idle_time)
                    if frame and not events:
                        output.write(json.dumps({"timestamp":frame.t,"can_id":frame.can_id,
                                                 "result":"NORMAL","reason":"NO_RULE_VIOLATION",
                                                 "anomaly_score":0.0})+"\n")
                    for event in events:
                        output.write(json.dumps(asdict(event),sort_keys=True)+"\n")
                        # Global 100ms cooldown prevents IDS amplification of an attack.
                        payload=event.alert_payload(int(time.time()))
                        if args.send_alerts and payload:
                            send_alert(transport, payload, event.timestamp, last_sent, output)
                    output.flush()
                output.write(json.dumps({"result":"END"})+"\n")
    except (OSError,ValueError,TypeError,RuntimeError) as error:
        print(f"IDS stopped: {error}",file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    finally:
        if transport:
            transport.close()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
