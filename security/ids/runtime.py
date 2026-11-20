"""python -m security.ids.runtime --help (run from repository root)."""
from __future__ import annotations

import argparse
import heapq
import errno
from dataclasses import asdict
from collections import OrderedDict
import json
import math
import os
from pathlib import Path
import socket
import struct
import sys
import time

from .diagnostic_ipc import DiagnosticSender
from .incident_status import IncidentStatus
from .observation_window import ObservationWindow
from .if_detector import IsolationForestDetector
from .runtime_detector import Config, Observation, RuntimeDetector
from .session_detector import SessionDetector, SESSION_IDS
from .startup_identity import snapshot_inputs, source_digest, build_identity, model_digest
from .resource_metrics import measured_run, MeasurementTerminated


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


def normal_vectors(path, *, protocol="legacy-v1"):
    """Use the streaming detector's feature boundary, including idle timer ticks."""
    from .runtime_detector import KNOWN_IDS
    vectors = []
    class Collector:
        def anomaly(self, vector):
            vectors.append(vector)
            return -1.0
    detector = RuntimeDetector(model=Collector())
    known_ids=SESSION_IDS if protocol=="session-v2" else KNOWN_IDS
    detector.known_ids=known_ids
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
        if frame.can_id not in known_ids or frame.dlc!=8 or len(frame.data)!=8 or frame.extended or frame.remote or frame.error:
            raise ValueError("normal training contains invalid frames")
        detector.observe(frame)
        if len(detector.frames)>=4096 or len(vectors)>10000:
            raise ValueError("training capture exceeds bounded capacity")
    if len(vectors)<2:
        raise ValueError("normal training needs at least two completed 1s windows")
    return vectors


def train_model(path, calibration_path=None, *, manifest_path=None, protocol="legacy-v1", calibration_manifest=None):
    if protocol=="session-v2" and manifest_path is None:
        raise ValueError("session-v2 IF requires explicit protocol-matched normal manifest")
    if manifest_path is not None:
        from security.capture_normal import validate_capture
        manifest=validate_capture(Path(path), Path(manifest_path))
        if protocol=="session-v2" and manifest.get("protocol")!="session-v2":
            raise ValueError("session-v2 IF cannot use legacy normal capture")
    if protocol=="session-v2" and calibration_path is not None:
        if calibration_manifest is None:raise ValueError("session-v2 calibration requires explicit manifest")
        from security.capture_normal import validate_capture
        calibration=validate_capture(Path(calibration_path),Path(calibration_manifest))
        if calibration.get("protocol")!="session-v2":raise ValueError("calibration protocol mismatch")
        from security.capture_normal import validate_session_splits
        validate_session_splits(((path, manifest_path), (calibration_path, calibration_manifest)))
    model = IsolationForestDetector().fit(normal_vectors(path,protocol=protocol))
    if calibration_path is not None:
        if Path(path).read_bytes() == Path(calibration_path).read_bytes():
            raise ValueError('training and calibration must be independent')
        model.calibrate(normal_vectors(calibration_path,protocol=protocol))
    return model


class ReceiveClockChanged(RuntimeError):
    """Current socket timing epoch is no longer usable; queued input is uncertain."""


class SocketCan:
    # Linux asm-generic/socket.h: fixed 64-bit __kernel_timespec ABI.
    TIMESTAMPNS_NEW = 64
    RXQ_OVFL = 40  # Linux SO_RXQ_OVFL: cumulative uint32 socket drops

    def __init__(self, interface):
        if not hasattr(socket,"AF_CAN"):
            raise RuntimeError("SocketCAN requires Linux; use --replay on this OS")
        self.socket=socket.socket(socket.AF_CAN,socket.SOCK_RAW,socket.CAN_RAW)
        try:
            self.rx_dropped = 0
            self._drop_counter = 0
            self.socket.setsockopt(socket.SOL_SOCKET, self.RXQ_OVFL, 1)
            self.start_time = time.monotonic()
            self.clock_offset_ns = self._clock_offset()
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
            raw, ancillary, flags, _ = self.socket.recvmsg(72, socket.CMSG_SPACE(16) + socket.CMSG_SPACE(4))
        except socket.timeout:
            self._check_clock()
            return None
        self._check_clock()
        if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            raise ValueError("truncated CAN frame or receive timestamp")
        self._record_drops(ancillary)
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

    def _record_drops(self, ancillary):
        counters = [data for level, kind, data in ancillary
                    if level == socket.SOL_SOCKET and kind == self.RXQ_OVFL]
        if not counters:
            return
        if len(counters) != 1 or len(counters[0]) != 4:
            raise ValueError("invalid receive overflow counter")
        current = struct.unpack("=I", counters[0])[0]
        self.rx_dropped += (current - self._drop_counter) & 0xFFFFFFFF
        self._drop_counter = current

    @staticmethod
    def _clock_offset():
        # Bracket CLOCK_REALTIME with two monotonic reads. Scheduling between
        # clocks must not be mistaken for a wall-clock step. Retry at most3
        # bounded samples; uncertainty above1ms still fails closed.
        for _ in range(3):
            before=time.monotonic_ns();wall=time.time_ns();after=time.monotonic_ns()
            if after<before:raise RuntimeError("monotonic clock moved backward")
            if after-before<=1_000_000:return (before+after)//2-wall
        raise RuntimeError("receive clock mapping sampling uncertainty exceeds 1ms")

    def _check_clock(self):
        # Never silently reinterpret a wall-clock step as a CAN timing anomaly.
        offset = self._clock_offset()
        if abs(offset - self.clock_offset_ns) > 10_000_000:
            raise ReceiveClockChanged("receive clock mapping changed by more than 10ms; restart capture (delta_ns="+str(offset-self.clock_offset_ns)+")")

    def send(self,payload):
        packed=struct.pack("=IB3x8s",0x200,8,payload)
        if self.socket.send(packed, socket.MSG_DONTWAIT)!=len(packed):
            raise OSError("short CAN write")

    def close(self):
        self.socket.close()


RECEIVE_ORDER_HOLD_S = .001
RECEIVE_ORDER_CAPACITY = 4096


class OrderedSocketCan(SocketCan):
    """Bounded receive-time ordering; never rewrite a kernel timestamp.

    A frame older than the released watermark still invalidates the epoch.
    The 1ms hold is a local ordering budget, not a relaxed wall-clock guard.
    """
    ORDER_HOLD_S = RECEIVE_ORDER_HOLD_S
    ORDER_CAPACITY = RECEIVE_ORDER_CAPACITY

    def __init__(self, interface):
        super().__init__(interface)
        self._ordered = []
        self._order_sequence = 0
        self._order_high = self.start_time
        self._order_released = self.start_time
        self.reordered_frames = 0
        self._order_last_arrival = self.start_time

    def receive(self):
        # Keep timeout ticks behind buffered data and behind the hold window.
        while True:
            if self._ordered and self._ordered[0][0] <= self._order_high - self.ORDER_HOLD_S:
                stamp, _, result = heapq.heappop(self._ordered)
                self._order_released = stamp
                return result
            frame = super().receive()
            if frame is not None:
                if frame.t < self._order_released:
                    raise ReceiveClockChanged(
                        'receive timestamp predates released watermark '
                        f'(received={frame.t:.9f}, watermark={self._order_released:.9f}, '
                        f'can_id={frame.can_id}, buffered={len(self._ordered)})')
                if len(self._ordered) >= self.ORDER_CAPACITY:
                    raise ReceiveClockChanged('receive ordering capacity exhausted; coverage uncertain')
                self.reordered_frames += int(frame.t < self._order_last_arrival)
                self._order_last_arrival = frame.t
                self._order_sequence += 1
                heapq.heappush(self._ordered, (frame.t, self._order_sequence, frame))
                self._order_high = max(self._order_high, frame.t)
            else:
                self._order_high = max(self._order_high, self.idle_time)
            safe = self._order_high - self.ORDER_HOLD_S
            if self._ordered and self._ordered[0][0] <= safe:
                stamp, _, result = heapq.heappop(self._ordered)
                self._order_released = stamp
                return result
            if frame is None:
                self.idle_time = max(self._order_released, min(safe,
                    self._ordered[0][0] if self._ordered else safe))
                self._order_released = self.idle_time
                return None


def run_replay(detector,records,output,metrics=None):
    count=0
    for record in records:
        frame = record if isinstance(record,Observation) else None
        now = frame.t if frame is not None else record
        events = (metrics.process(detector,frame,now) if metrics else
                  detector.observe(record) if frame is not None else detector.tick(record))
        if isinstance(record,Observation) and not events:
            output.write(json.dumps({"timestamp":record.t,"can_id":record.can_id,
                                     "result":"NORMAL","reason":"NO_RULE_VIOLATION",
                                     "anomaly_score":0.0})+"\n")
        for event in events:
            output.write(json.dumps(asdict(event),sort_keys=True)+"\n")
            count+=1
    return count


def send_alert(transport, payload, timestamp, last_attempt, output, *, run_id=None, event=None):
    """Bound alert attempts, including failures; never block CAN observation."""
    if timestamp - last_attempt.get("all", float("-inf")) < 0.1:
        return
    last_attempt["all"] = timestamp
    record = {"timestamp": timestamp, "can_id": 0x200, "data": payload.hex()}
    if run_id is not None:
        record["run_id"] = run_id
    if event is not None:
        record.update(reason=event.reason, attack_type=event.attack_type)
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


def submit_diagnostic(sender, kind, body, output, observed_at_ms):
    if sender is None:
        return
    outcome = sender.send(kind, body, observed_at_ms=observed_at_ms)
    output.write(json.dumps({"result":"DIAGNOSTIC_IPC", "kind":kind,
                             "timestamp":observed_at_ms/1000,
                             "body_hex":body.hex(),
                             "local_accepted":outcome["accepted"],
                             "errno":outcome["errno"], "can_delivery":"unconfirmed"})+"\n")


def measurement_model(model, identity):
    # No pickle/model artifact is loaded. Hash the actual fitted state using the
    # existing public identity routine without scoring again or inventing bytes.
    return {'storage':'trained_in_memory' if model else 'disabled',
            'file_bytes':None,'file_sha256':None,
            'file_unavailable_reason':'no model file is loaded; trained from declared normal captures' if model else 'IF disabled',
            'state_sha256':(identity['trained_model_sha256'] if identity else model_digest(model)) if model else None}


def main(argv=None):
    parser=argparse.ArgumentParser(description="Node A CAN IDS: offline replay or live SocketCAN")
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--replay",help="JSONL frames and explicit timer ticks")
    source.add_argument("--interface",help="Linux SocketCAN interface, opened only when selected")
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--train-normal",help="separate known-normal JSONL capture for mandatory IF mode")
    mode.add_argument("--rules-only",action="store_true",help="explicit rule-only development/ablation mode")
    parser.add_argument('--calibrate-normal', help='independent normal JSONL, at least 100 model windows')
    parser.add_argument("--calibration-manifest",help="explicit session-v2 calibration capture manifest")
    parser.add_argument("--normal-manifest", help="ids-normal-v2 manifest; local capture directories use their manifest.json")
    parser.add_argument("--run-id", default="development", help="shared trial/run identifier")
    parser.add_argument("--ready-file", help="new JSON readiness file written after SocketCAN opens")
    parser.add_argument("--secoc-key",help="32-byte key file for independent local SecOC observation")
    parser.add_argument("--config",help="JSON Config overrides; thresholds require deployment calibration")
    parser.add_argument("--log",required=True,help="new output JSONL path; existing files are not overwritten")
    parser.add_argument('--measure-resources', action='store_true',
                        help='opt-in loop CPU/RSS, counts and stage times in the same log; not maximum throughput')
    parser.add_argument("--send-alerts",action="store_true",help="opt in to ICD 0x200 transmission on --interface")
    parser.add_argument("--parent-pid", type=int, help="owned live run: stop when parent exits instead of duration")
    parser.add_argument("--duration",type=float,default=30.0)
    parser.add_argument("--diagnostic-socket", help="ECU-local Unix datagram destination; acceptance is not CAN delivery")
    parser.add_argument("--protocol", choices=("legacy-v1","session-v2"), default="legacy-v1",
                        help="historical experiments default to legacy-v1; product IDS explicitly selects session-v2")
    parser.add_argument("--session-context-fd", type=int, help="inherited nonblocking ECU-owned public context pipe")
    parser.add_argument("--peer-rejection-fd", type=int, help="inherited ECU-owned authenticated IVI rejection pipe, diagnostic only")
    args=parser.parse_args(argv)
    if args.protocol=="session-v2" and (not args.interface or not args.secoc_key or args.session_context_fd is None):
        parser.error("session-v2 requires live interface, local key and ECU-owned context pipe")
    if args.protocol!="session-v2" and args.session_context_fd is not None:
        parser.error("context fd requires session-v2")
    if args.peer_rejection_fd is not None and (args.protocol!='session-v2' or args.peer_rejection_fd==args.session_context_fd):
        parser.error('peer rejection pipe requires distinct session-v2 context pipe')
    if args.diagnostic_socket and not args.interface:
        parser.error("--diagnostic-socket requires --interface")
    if args.send_alerts and not args.interface:
        parser.error("--send-alerts requires --interface")
    if args.calibration_manifest and not args.calibrate_normal:
        parser.error("--calibration-manifest requires --calibrate-normal")
    if args.calibrate_normal and not args.train_normal:
        parser.error('--calibrate-normal requires --train-normal')
    if not 0<args.duration<86400:
        parser.error("duration must be between 0 and 86400 seconds")
    if args.parent_pid is not None and (not args.interface or args.parent_pid != os.getppid()):
        parser.error("--parent-pid must identify the current parent of a live IDS")
    if args.normal_manifest and not args.train_normal:
        parser.error("--normal-manifest requires --train-normal")
    if args.ready_file and not args.interface:
        parser.error("--ready-file requires --interface")
    transport=None
    diagnostic_sender=None
    peer_source=None
    try:
        config=Config(**(json.loads(Path(args.config).read_text()) if args.config else {}))
        key=Path(args.secoc_key).read_bytes() if args.secoc_key else None
        if args.ready_file and Path(args.ready_file).exists():
            raise ValueError("ready file already exists")
        if args.train_normal and not args.normal_manifest:
            from security.experiments.evaluate_normal import load_capture
            _, _, validated = load_capture(Path(args.train_normal).parent)
            if validated.resolve() != Path(args.train_normal).resolve():
                raise ValueError("training path must match its capture manifest")
        if args.calibrate_normal and not args.calibration_manifest:
            from security.experiments.evaluate_normal import load_capture
            _, _, validated = load_capture(Path(args.calibrate_normal).parent)
            if validated.resolve() != Path(args.calibrate_normal).resolve():
                raise ValueError("calibration path must match its capture manifest")
        identity=None
        if args.protocol=='session-v2':
            identity_inputs={name:getattr(args,name) for name in
                ('train_normal','normal_manifest','calibrate_normal','calibration_manifest')}
            input_snapshot=snapshot_inputs(identity_inputs);source_snapshot=source_digest()
        model=train_model(args.train_normal, args.calibrate_normal, manifest_path=args.normal_manifest,protocol=args.protocol,calibration_manifest=args.calibration_manifest) if args.train_normal else None
        if args.protocol=='session-v2':
            identity=build_identity(asdict(config),model,identity_inputs,input_snapshot,source_snapshot)
            identity['resource_measurement']=args.measure_resources
        context_source=None
        if args.protocol=="session-v2":
            from .session_context import ContextSource
            context_source=ContextSource(args.session_context_fd,key,clock=time.monotonic)
            if args.peer_rejection_fd is not None:
                from .peer_diagnostic import PeerDiagnostics
                peer_source=PeerDiagnostics(args.peer_rejection_fd,context_source)
        def make_detector(start):
            created = SessionDetector(config,context_source,model,start) if context_source else RuntimeDetector(config,key,model,start)
            created.metrics = metrics
            return created
        metrics = None
        detector=make_detector(time.monotonic() if args.interface else 0.0)
        with Path(args.log).open("x",encoding="utf-8") as output:
            with measured_run(args.measure_resources, output, args.run_id, args.protocol,
                              "live" if args.interface else "replay") as metrics:
                output.write(json.dumps({"result":"START","run_id":args.run_id,"mode":"rules+if" if model else "rules-only",
                                         "secoc_observation":key is not None,"config":asdict(config),"protocol":args.protocol,
                                         "peer_diagnostic_channel":peer_source is not None,
                                         "finding_schema":"ids-finding-v1",
                                         "resource_measurement":args.measure_resources,
                                         "finding_source_id":detector.finding_source_id if args.replay else None,
                                         "if_calibration":model.calibration if model else None,
                                         **({'startup_identity':identity} if identity is not None else {})})+"\n")
                if args.replay:
                    detector.metrics = metrics
                    if metrics:
                        metrics.start(measurement_model(model, identity))
                    count=run_replay(detector,read_records(args.replay),output,metrics)
                    output.write(json.dumps({"result":"END","events":count})+"\n")
                else:
                    if args.diagnostic_socket:
                        diagnostic_sender=DiagnosticSender(args.diagnostic_socket)
                    transport=OrderedSocketCan(args.interface)
                    detector=make_detector(transport.start_time)
                    if metrics:metrics.start(measurement_model(model, identity))
                    output.write(json.dumps({"result":"CLOCK", "source":"SO_TIMESTAMPNS_NEW",
                                             "mapping":"fixed realtime to monotonic",
                                             "offset_ns":transport.clock_offset_ns,
                                             "ordering_hold_s":RECEIVE_ORDER_HOLD_S,
                                             "ordering_capacity":RECEIVE_ORDER_CAPACITY})+"\n")
                    ready={"result":"READY","run_id":args.run_id,"interface":args.interface,
                           "timestamp":transport.start_time,"mode":"rules+if" if model else "rules-only",
                           "send_alerts":args.send_alerts,"classification_version":"session-observation-v1" if context_source else "evidence-v3"}
                    ready['finding_schema']='ids-finding-v1';ready['finding_source_id']=detector.finding_source_id
                    ready['resource_measurement']=args.measure_resources
                    if identity is not None:ready['startup_identity']=identity
                    output.write(json.dumps(ready)+"\n")
                    output.flush()
                    if args.ready_file:
                        with Path(args.ready_file).open("x", encoding="utf-8") as ready_output:
                            json.dump(ready, ready_output)
                    print(json.dumps(ready), flush=True)
                    incident_status=IncidentStatus()
                    observation_window=ObservationWindow(int(transport.start_time*1000),detector_revision=4 if context_source else 3)
                    alert_throttle=AlertThrottle()
                    deadline=time.monotonic()+args.duration
                    last_sent={}
                    previous_socket_drops=0
                    while (os.getppid() == args.parent_pid if args.parent_pid is not None else time.monotonic()<deadline):
                        receive_fault=False
                        try:
                            frame=transport.receive()
                            if frame is not None and frame.t<detector.now:
                                raise ReceiveClockChanged(
                                    f"receive timestamp predates processed watermark (received={frame.t:.9f}, "
                                    f"watermark={detector.now:.9f}, can_id={frame.can_id})")
                        except ReceiveClockChanged as error:
                            previous_socket_drops+=transport.rx_dropped
                            transport.close()
                            transport=OrderedSocketCan(args.interface)
                            detector.begin_live_epoch(transport.start_time)
                            alert_throttle=AlertThrottle()
                            receive_fault=True;frame=None
                            output.write(json.dumps({"result":"RECEIVE_EPOCH_RESET","reason":str(error),
                                "timestamp":transport.start_time,"coverage":"uncertain","discarded_queue_count":"unknown"})+"\n")
                        if context_source:detector.update_context(time.monotonic())
                        if peer_source:
                            for record in peer_source.poll(time.monotonic_ns()):
                                output.write(json.dumps(record,sort_keys=True)+"\n")
                        if metrics:metrics.receive_status(previous_socket_drops+transport.rx_dropped,reset=receive_fault)
                        events=(metrics.process(detector,frame,frame.t if frame else transport.idle_time) if metrics else
                                detector.observe(frame) if frame else detector.tick(transport.idle_time))
                        if frame and not events:
                            output.write(json.dumps({"timestamp":frame.t,"can_id":frame.can_id,
                                                     "result":"NORMAL","reason":"NO_RULE_VIOLATION",
                                                     "anomaly_score":0.0})+"\n")
                        for event in events:
                            output.write(json.dumps(asdict(event),sort_keys=True)+"\n")
                            alert_throttle.offer(event)
                        now = frame.t if frame else transport.idle_time
                        observation = observation_window.observe(
                            int(now*1000), frame_present=frame is not None,
                            events=events, total_drops=previous_socket_drops+transport.rx_dropped,
                            unknown_drops=receive_fault,
                            processed_ms=max(int(now*1000), time.monotonic_ns()//1_000_000),
                            unavailable_reason=3 if receive_fault else detector.unavailable_reason(now) if context_source else 0)
                        if observation:
                            body, continuity = observation
                            output.write(json.dumps({"result":"OBSERVATION_STATUS",
                                "protocol":"diagnostic-v1", "body_hex":body.hex(),
                                "ended_mask":continuity.ended_mask,
                                "delivery":"local-log-only"})+"\n")
                            submit_diagnostic(diagnostic_sender, 7, body, output, int(now*1000))
                            for incident in incident_status.update(body, continuity, observation_window.last_evidence):
                                output.write(json.dumps({"result":"INCIDENT_STATUS",
                                    "protocol":"diagnostic-v1", "body_hex":incident.hex(),
                                    "delivery":"local-log-only"})+"\n")
                                submit_diagnostic(diagnostic_sender, 4, incident, output, int(now*1000))
                        selected = alert_throttle.pop_ready(now) if args.send_alerts else None
                        if selected:
                            payload = selected.alert_payload(int(time.time()))
                            # Pop once: backpressure is recorded, never requeued or retried.
                            send_alert(transport, payload, now, last_sent, output,
                                       run_id=args.run_id, event=selected)
                        output.flush()
                        if metrics and time.monotonic_ns()>=metrics.next_sample_ns:
                            output.write(json.dumps(metrics.report('IN_PROGRESS'),allow_nan=False)+'\n')
                            metrics.next_sample_ns=time.monotonic_ns()+1_000_000_000
                            output.flush()
                    ordered_count=getattr(transport,"reordered_frames",None)
                    output.write(json.dumps({"result":"END","receive_order_reordered":ordered_count if type(ordered_count) is int else None})+"\n")
    except (OSError,ValueError,TypeError,RuntimeError) as error:
        print(f"IDS stopped: {error}",file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except MeasurementTerminated:
        return 143
    finally:
        if peer_source:
            peer_source.close()
        if diagnostic_sender:
            diagnostic_sender.close()
        if transport:
            transport.close()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
