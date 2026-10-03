"""python -m security.ids.runtime --help (run from repository root)."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import socket
import struct
import sys
import time
from collections import OrderedDict

from .feature_extractor import extract
from .if_detector import IsolationForestDetector
from .runtime_detector import Config, Observation, RuntimeDetector


class AlertThrottle:
    """Fair FIFO of at most four attack types; codes are not priorities."""

    def __init__(self, cooldown_s=0.1):
        if not math.isfinite(cooldown_s) or cooldown_s <= 0:
            raise ValueError("cooldown must be finite and positive")
        self.cooldown_s = cooldown_s
        self.last_sent = float("-inf")
        self.pending = OrderedDict()

    def offer(self, event):
        if event.attack_type not in (1, 2, 3, 4):
            return
        # Replacing a same-type event never changes its position in the queue.
        self.pending[event.attack_type] = event

    def pop_ready(self, now):
        if not self.pending or now-self.last_sent < self.cooldown_s:
            return None
        _, event = self.pending.popitem(last=False)
        self.last_sent = now
        return event


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


def train_model(path, manifest_path):
    """Fit only explicitly supplied normal traffic, in nonoverlapping 1s windows."""
    from .runtime_detector import KNOWN_IDS
    from security.capture_normal import validate_capture
    validate_capture(Path(path), Path(manifest_path))
    vectors, bucket = [], []
    start = None
    previous = float("-inf")
    for frame in read_records(path):
        if not isinstance(frame,Observation):
            continue
        if not math.isfinite(frame.t) or frame.t < previous:
            raise ValueError("normal training timestamps must be ordered")
        previous=frame.t
        if frame.can_id not in KNOWN_IDS or frame.dlc!=8 or len(frame.data)!=8 or frame.extended or frame.remote or frame.error:
            raise ValueError("normal training contains invalid frames")
        if frame.can_id==0x200:
            continue
        if start is None:
            start=frame.t
        if frame.t-start >= 1:
            vectors.append(extract(bucket))
            bucket=[]
            start=frame.t
        bucket.append(frame)
        if len(bucket)>4096 or len(vectors)>10000:
            raise ValueError("training capture exceeds bounded capacity")
    if len(vectors)<2:
        raise ValueError("normal training needs at least two completed 1s windows")
    return IsolationForestDetector().fit(vectors)


class SocketCan:
    def __init__(self, interface):
        if not hasattr(socket,"AF_CAN"):
            raise RuntimeError("SocketCAN requires Linux; use --replay on this OS")
        self.socket=socket.socket(socket.AF_CAN,socket.SOCK_RAW,socket.CAN_RAW)
        try:
            self.socket.bind((interface,))
            self.socket.settimeout(0.05)
        except Exception:
            self.socket.close()
            raise

    def receive(self):
        try:
            raw=self.socket.recv(72)
        except socket.timeout:
            return None
        if len(raw)!=16:
            raise ValueError("expected a Classical CAN frame")
        cid,dlc,data=struct.unpack("=IB3x8s",raw)
        return Observation(time.monotonic(),cid&0x1fffffff,data[:min(dlc,8)],dlc,
                           bool(cid&0x80000000),bool(cid&0x40000000),bool(cid&0x20000000))

    def send(self,payload):
        packed=struct.pack("=IB3x8s",0x200,8,payload)
        if self.socket.send(packed)!=len(packed):
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


def main(argv=None):
    parser=argparse.ArgumentParser(description="Node A CAN IDS: offline replay or live SocketCAN")
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--replay",help="JSONL frames and explicit timer ticks")
    source.add_argument("--interface",help="Linux SocketCAN interface, opened only when selected")
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--train-normal",help="separate known-normal JSONL capture for mandatory IF mode")
    mode.add_argument("--rules-only",action="store_true",help="explicit rule-only development/ablation mode")
    parser.add_argument("--secoc-key",help="32-byte key file for independent local SecOC observation")
    parser.add_argument("--normal-manifest",help="validated manifest for --train-normal")
    parser.add_argument("--run-id",default="development",help="shared trial/run identifier")
    parser.add_argument("--ready-file",help="new JSON readiness file written after SocketCAN opens")
    parser.add_argument("--config",help="JSON Config overrides; thresholds require deployment calibration")
    parser.add_argument("--log",required=True,help="new output JSONL path; existing files are not overwritten")
    parser.add_argument("--send-alerts",action="store_true",help="opt in to ICD 0x200 transmission on --interface")
    parser.add_argument("--duration",type=float,default=30.0)
    args=parser.parse_args(argv)
    if args.send_alerts and not args.interface:
        parser.error("--send-alerts requires --interface")
    if bool(args.train_normal) != bool(args.normal_manifest):
        parser.error("--train-normal and --normal-manifest must be supplied together")
    if args.ready_file and not args.interface:
        parser.error("--ready-file requires --interface")
    if not 0<args.duration<86400:
        parser.error("duration must be between 0 and 86400 seconds")
    transport=None
    try:
        config=Config(**(json.loads(Path(args.config).read_text()) if args.config else {}))
        key=Path(args.secoc_key).read_bytes() if args.secoc_key else None
        if args.ready_file and Path(args.ready_file).exists():
            raise ValueError("ready file already exists")
        model=train_model(args.train_normal,args.normal_manifest) if args.train_normal else None
        detector=RuntimeDetector(config,key,model,time.monotonic() if args.interface else 0.0)
        with Path(args.log).open("x",encoding="utf-8") as output:
            output.write(json.dumps({"result":"START","run_id":args.run_id,"mode":"rules+if" if model else "rules-only",
                                     "secoc_observation":key is not None,"config":asdict(config)})+"\n")
            if args.replay:
                count=run_replay(detector,read_records(args.replay),output)
                output.write(json.dumps({"result":"END","events":count})+"\n")
            else:
                transport=SocketCan(args.interface)
                ready={"result":"READY","run_id":args.run_id,"interface":args.interface,
                       "timestamp":time.monotonic(),"mode":"rules+if" if model else "rules-only",
                       "send_alerts":args.send_alerts}
                output.write(json.dumps(ready)+"\n")
                output.flush()
                if args.ready_file:
                    with Path(args.ready_file).open("x",encoding="utf-8") as ready_output:
                        json.dump(ready,ready_output)
                print(json.dumps(ready),flush=True)
                deadline=time.monotonic()+args.duration
                alert_throttle=AlertThrottle()
                while time.monotonic()<deadline:
                    frame=transport.receive()
                    now=frame.t if frame else time.monotonic()
                    events=detector.observe(frame) if frame else detector.tick(now)
                    if frame and not events:
                        output.write(json.dumps({"timestamp":frame.t,"can_id":frame.can_id,
                                                 "result":"NORMAL","reason":"NO_RULE_VIOLATION",
                                                 "anomaly_score":0.0})+"\n")
                    for event in events:
                        output.write(json.dumps(asdict(event),sort_keys=True)+"\n")
                        alert_throttle.offer(event)
                    # Four bounded type slots, FIFO and global rate limiting.
                    selected=alert_throttle.pop_ready(now) if args.send_alerts else None
                    if selected:
                        payload=selected.alert_payload(int(time.time()))
                        transport.send(payload)
                        output.write(json.dumps({"result":"ALERT_SENT","can_id":0x200,
                                                 "timestamp":now,"run_id":args.run_id,
                                                 "reason":selected.reason,
                                                 "attack_type":selected.attack_type,
                                                 "data":payload.hex()})+"\n")
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
