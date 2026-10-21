"""Bounded SocketCAN ablation runner, one configuration per invocation.

Run from the repository root with python -m security.experiments.live_ablation.
The observer is a separate process from the ECU and IDS. Its reference decisions
are NOT IVI product evidence. Full raw attempts (including failures) are retained.
"""
from __future__ import annotations

import argparse
import errno
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import time

from security.attacks.attack_simulator import ATTACK_TYPES, build_frame, validate
from security.experiments.ablation_core import trial_seed
from security.experiments.can_capture import CaptureSocket, frame_json, inspect_interface, sha256, interrupted
from security.experiments.evaluate_normal import load_capture
from security.experiments.live_receiver import ReferenceReceiver
from security.experiments.live_trial import Record, TrialWindows, judge_trial


class Children:
    """Only stop processes started here; argv lists, no shell or system-wide kill."""
    def __init__(self):
        self.items = []

    def start(self, argv, output):
        stream = Path(output).open("x", encoding="utf-8")
        try:
            process = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT,
                                       start_new_session=True)
        except BaseException:
            stream.close()
            raise
        self.items.append((process, stream))

    def check(self):
        for process, stream in self.items:
            code = process.poll()
            if code is not None:
                raise RuntimeError(f"owned process exited: {Path(stream.name).name}, exit_code={code}; inspect process log")

    def close(self):
        errors = []
        for process, stream in reversed(self.items):
            try:
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGINT)
                    except ProcessLookupError:
                        pass
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait(timeout=3)
            except (OSError, subprocess.SubprocessError) as error:
                errors.append(type(error).__name__)
            finally:
                stream.close()
        return errors


def encode_record(record):
    return {"t": record.t, "can_id": record.can_id, "data": record.data.hex(), "own": record.own,
            "outcomes": [{**asdict(o), "payload": o.payload.hex()} for o in record.outcomes]}


def send_bounded(bus, cid, payload, deadline, stream, clock=time.monotonic,
                 sleep=time.sleep):
    """Retry only transient queue pressure, at most 5ms/5 retries per frame.

    Every failed syscall remains in the raw log. Return False on an uncompleted
    frame; callers retain TX_ERRORS/INVALID for any such frame. None means
    the attack deadline passed before the first syscall; log but do not count
    that unattempted frame as a transmission error.
    """
    limit = min(deadline, clock() + .005)
    retries = 0
    while clock() < (limit if retries else deadline):
        try:
            bus.send(cid, payload)
            stream.write(json.dumps({"tx_t": clock(), "can_id": cid,
                                     "data": payload.hex(), "tx_retries": retries}) + "\n")
            return True
        except OSError as error:
            transient = error.errno in (errno.ENOBUFS, errno.EAGAIN)
            remaining = limit - clock()
            retry = transient and retries < 5 and remaining > .001
            stream.write(json.dumps({"tx_error": type(error).__name__,
                                     "errno": error.errno, "t": clock(),
                                     "can_id": cid, "data": payload.hex(),
                                     "retry_planned": retry}) + "\n")
            if not retry:
                return False
            retries += 1
            sleep(min(.001, remaining))
    if retries:
        return False
    stream.write(json.dumps({"tx_skipped": "ATTACK_DEADLINE", "t": clock(),
                             "can_id": cid, "data": payload.hex()}) + "\n")
    return None


def enforce_attempt_policy(row, continue_invalid):
    if row["status"] != "VALID" and not continue_invalid:
        raise RuntimeError("invalid attempt retained; fix setup before more trials")


def collect(bus, receiver, duration, stream, children, attack=None, rate=1, seed=0,
            replay=None, clock=time.monotonic):
    """Interleave bounded TX and RX; own attribution comes from socket MSG_CONFIRM.

    No catch-up bursts after a late scheduler wakeup. Send failures are retained;
    first injection uses the first confirmed own echo on this same receive clock.
    """
    records = []
    start = clock()
    deadline = start + duration
    next_send = start
    sent = tx_errors = 0
    first = None
    rng = random.Random(seed)
    while clock() < deadline:
        children.check()
        now = clock()
        if attack and now >= next_send:
            frames = replay if attack == "replay" else [build_frame(attack, rng, sent)]
            if not frames:
                raise ValueError("replay requires a captured BMS frame/pair")
            for cid, payload in frames:
                outcome = send_bounded(bus, cid, payload, deadline, stream, clock)
                if outcome is True:
                    sent += 1
                elif outcome is False:
                    tx_errors += 1
                else:
                    break
            # Include send/logging time in the interval. A late iteration sends
            # only one group; it never repays missed deadlines with a burst.
            next_send = now + len(frames) / rate
        wait = min(.01, max(0.000001, deadline - clock()))
        if attack:
            wait = min(wait, max(.000001, next_send - clock()))
        idle_watermark = clock()
        received = bus.receive(wait)
        if received:
            frame, own = received
            if first is None and own and frame.t >= start:
                first = frame.t
            outcomes = receiver.poll(frame.t)
            outcomes += receiver.process(frame.t, frame.can_id, frame.data, own, frame.dlc,
                                         frame.extended, frame.remote, frame.error)
            record = Record(frame.t, frame.can_id, frame.data, own, outcomes)
            records.append(record)
            stream.write(json.dumps({**encode_record(record), "frame": frame_json(frame)}) + "\n")
            if frame.error:
                raise RuntimeError("CAN error frame: run retained; bus recovery required")
        else:
            now = idle_watermark
            outcomes = receiver.poll(now)
            if outcomes:
                record = Record(now, -1, b"", False, outcomes)
                records.append(record)
                stream.write(json.dumps(encode_record(record)) + "\n")
    stream.flush()
    return records, sent, tx_errors, first, start, clock()


def captured_replay(records, secoc_on):
    """Capture a previously accepted raw/auth pair, never fabricate replay data."""
    pending = None
    for record in records:
        if record.own:
            continue
        if record.can_id == 0x100:
            pending = record
            if not secoc_on and any(o.kind == "PUBLISHED" for o in record.outcomes):
                return [(0x100, record.data)]
        if (secoc_on and record.can_id == 0x102 and pending is not None
                and any(o.kind == "PUBLISHED" and o.can_id == 0x100 for o in record.outcomes)):
            return [(0x100, pending.data), (0x102, record.data)]
    raise ValueError("no accepted BMS frame/pair in baseline for replay")


class IdsEvidenceReader:
    """Read only appended complete lines; preserve a partial final line."""
    def __init__(self, path):
        self.path = Path(path)
        self.offset = 0
        self.pending = []
        self.last_start = float("-inf")

    def count(self, start, end):
        if start < self.last_start:
            raise ValueError("IDS evidence windows must advance")
        self.last_start = start
        self.pending = [r for r in self.pending if r["timestamp"] >= start]
        with self.path.open("rb") as stream:
            limit = os.fstat(stream.fileno()).st_size
            stream.seek(self.offset)
            while stream.tell() < limit:
                line = stream.readline(limit - stream.tell())
                if not line or not line.endswith(b"\n"):
                    break
                self.offset = stream.tell()
                row = json.loads(line)
                if row.get("result") == "ANOMALY" and row.get("timestamp", -1) >= start:
                    self.pending.append(row)
        rows = [r for r in self.pending if start <= r["timestamp"] < end]
        return {"rule_events": sum(r["reason"] != "IF_ANOMALY" for r in rows),
                "if_events": sum(r["reason"] == "IF_ANOMALY" for r in rows)}


def ids_evidence(path, start, end):
    return IdsEvidenceReader(path).count(start, end)


def ids_ready(path, expected_mode):
    if not Path(path).exists():
        return False
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            return False
    return (any(r.get("result") == "START" and r.get("mode") == expected_mode
                and r.get("secoc_observation") for r in rows)
            and any(r.get("result") == "NORMAL" for r in rows))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--environment", choices=["vcan", "physical"], required=True)
    parser.add_argument("--config", type=int, choices=[1, 2, 3], required=True)
    parser.add_argument("--attack", choices=ATTACK_TYPES, nargs="+", default=list(ATTACK_TYPES))
    parser.add_argument("--trials", type=int, default=1, help="number of trials in this new run")
    parser.add_argument("--start-trial", type=int, default=1,
                        help="first planned trial/seed index, 1..100; never overwrites old runs")
    parser.add_argument("--previous-run-id", help="provenance link to the prior interrupted run")
    parser.add_argument("--continue-invalid", action="store_true",
                        help="retain judged INVALID trials and continue planned indices; fatal exceptions still stop")
    parser.add_argument("--rate", type=float, default=1000)
    parser.add_argument("--duration", type=float, default=3)
    parser.add_argument("--baseline", type=float, default=2)
    parser.add_argument("--post", type=float, default=1)
    parser.add_argument("--out", required=True, help="new run directory")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--key", help="32-byte key file, never logged")
    parser.add_argument("--ecu", required=True, help="ECU executable to start and own")
    parser.add_argument("--sensor-mode", choices=["constant", "ads1115"], default="constant")
    parser.add_argument("--train", help="normal capture directory for rules+IF in config 3")
    parser.add_argument('--calibrate', help='independent normal calibration capture directory')
    parser.add_argument("--rules-only", action="store_true", help="explicit pilot only; IF remains NOT_RUN")
    parser.add_argument("--ivi-run-id", help="corresponding external IVI evidence run, not a PASS claim")
    parser.add_argument("--i-am-on-a-test-bus", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.start_trial <= 100 or args.start_trial + args.trials - 1 > 100:
        parser.error("planned trial range must stay within 1..100")
    if args.start_trial > 1 and not args.previous_run_id:
        parser.error("--start-trial > 1 requires --previous-run-id")
    if not 1 <= args.trials <= 100 or len(set(args.attack)) != len(args.attack):
        parser.error("trials must be 1..100; attack names must be unique")
    if not all(math.isfinite(v) and 1 <= v <= 60 for v in (args.baseline, args.post)):
        parser.error("baseline/post must be finite seconds in [1,60]")
    error = validate(args.attack[0], args.channel, args.rate, args.duration, args.i_am_on_a_test_bus)
    if error:
        parser.error(error)
    if args.config == 3 and bool(args.train) == bool(args.rules_only):
        parser.error("config 3 requires exactly one of --train or --rules-only")
    if args.config != 3 and (args.train or args.rules_only):
        parser.error("IDS mode only applies to config 3")
    if args.calibrate and not args.train:
        parser.error('--calibrate requires --train')
    if args.environment == 'physical' and args.train and not args.calibrate:
        parser.error('physical IF requires an independent --calibrate capture')
    if args.environment == "physical" and not args.ivi_run_id:
        parser.error("physical run requires --ivi-run-id to link the separate product evidence")
    root = Path(args.out)
    children = Children()
    bus = None
    manifest = None
    ledger = None
    active_attempt = None
    status = "COMPLETE"
    previous_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        info = inspect_interface(args.channel, args.environment)
        ecu = Path(args.ecu).resolve(strict=True)
        key = Path(args.key).read_bytes() if args.key else None
        if args.config > 1 and (key is None or len(key) != 32):
            raise ValueError("SecOC configurations require a 32-byte key file")
        training_path = None
        training_hash = None
        calibration_path = None
        calibration_hash = None
        if args.train:
            _, training_manifest, training_path = load_capture(args.train)
            if training_manifest['environment'] != args.environment:
                raise ValueError('training environment must match the experiment')
            training_hash = training_manifest["sha256"]
        if args.calibrate:
            _, calibration_manifest, calibration_path = load_capture(args.calibrate)
            if calibration_manifest['environment'] != args.environment:
                raise ValueError('calibration environment must match the experiment')
            calibration_hash = calibration_manifest['sha256']
            if calibration_hash == training_hash:
                raise ValueError('training and calibration captures must be independent')
            # Fail before ECU transmission if calibration cannot be fitted.
            from security.ids.runtime import train_model
            train_model(training_path, calibration_path)
        root.mkdir(parents=True, exist_ok=False)
        manifest = {"run_id": args.run_id, "environment": args.environment, "interface": info,
                    "config": args.config, "channel": args.channel, "attacks": args.attack,
                    "trials_per_attack": args.trials, "start_trial": args.start_trial,
                    "previous_run_id": args.previous_run_id,
                    "continue_invalid": args.continue_invalid,
                    "tx_policy": "nonblocking; ENOBUFS/EAGAIN max5 retries/5ms; raw errors retained",
                    "rate_fps": args.rate, "attack_s": args.duration,
                    "baseline_s": args.baseline, "post_s": args.post, "sensor_mode": args.sensor_mode,
                    "observer": "reference_receiver", "product_verdict": "NOT_RUN",
                    "ivi_run_id": args.ivi_run_id, "training_sha256": training_hash,
                    "calibration_sha256": calibration_hash,
                    "ids_mode": "rules+if" if args.train else "rules-only" if args.config == 3 else "off",
                    "ecu_sha256": sha256(ecu), "clock": "SO_TIMESTAMPNS_NEW mapped to monotonic; own echo is injection origin",
                    "source_sha256": {p.as_posix(): sha256(p) for p in sorted(Path("security").rglob("*.py"))}}
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        bus = CaptureSocket(args.channel, transmit=True)
        # Do not kill/reconfigure existing ECU or IDS processes. Require a quiet
        # test setup before launching our own; all detected traffic is retained.
        quiet_end = time.monotonic() + .5
        while time.monotonic() < quiet_end:
            if bus.receive():
                raise RuntimeError("bus already active; stop the test sender/IDS explicitly before this run")
        command = [str(ecu), "--interface", args.channel, "--sensor-mode", args.sensor_mode,
                   "--secoc", "on" if args.config > 1 else "off"]
        if args.key:
            command += ["--key", args.key]
        children.start(command, root / "ecu.log")
        if args.config == 3:
            # Parent owns shutdown; no guessed per-trial wall-clock budget.
            command = [sys.executable, "-m", "security.ids.runtime", "--interface", args.channel,
                       "--secoc-key", args.key, "--log", str(root / "ids.jsonl"),
                       "--send-alerts", "--parent-pid", str(os.getpid())]
            command += ["--train-normal", str(training_path)] if training_path else ["--rules-only"]
            if calibration_path:
                command += ['--calibrate-normal', str(calibration_path)]
            children.start(command, root / "ids-process.log")
        evidence_reader = IdsEvidenceReader(root / "ids.jsonl")
        receiver = ReferenceReceiver(args.config > 1, key)
        with (root / "warmup.jsonl").open("x", encoding="utf-8") as stream:
            # IF fit time varies; use observed readiness with a finite deadline,
            # not a fixed sleep as proof of readiness.
            ready_deadline = time.monotonic() + 30
            while True:
                warmed = collect(bus, receiver, max(3, args.baseline), stream, children)
                receiver_ready = sum(o.kind == "PUBLISHED" and o.can_id == 0x100
                                     for r in warmed[0] for o in r.outcomes) >= 10
                detector_ready = args.config != 3 or ids_ready(root / "ids.jsonl", manifest["ids_mode"])
                if receiver_ready and detector_ready:
                    break
                if time.monotonic() >= ready_deadline:
                    raise RuntimeError("ECU/receiver/IDS readiness timeout")
        ledger = (root / "attempts.jsonl").open("x", encoding="utf-8")
        for attack in args.attack:
            for trial in range(args.start_trial, args.start_trial + args.trials):
                active_attempt = {"run_id": args.run_id, "environment": args.environment,
                                  "config": args.config, "attack_type": attack, "trial": trial,
                                  "seed": trial_seed(attack, trial), "ids_mode": manifest["ids_mode"]}
                raw_path = root / f"{attack}-{trial:03d}.jsonl"
                with raw_path.open("x", encoding="utf-8") as stream:
                    baseline = collect(bus, receiver, args.baseline, stream, children)
                    baseline_published = sum(o.kind == "PUBLISHED" and o.can_id == 0x100
                                             for r in baseline[0] for o in r.outcomes)
                    if baseline_published < 5 * args.baseline:
                        raise RuntimeError("normal receiver readiness failed before injection")
                    if any(r.can_id == 0x200 for r in baseline[0]):
                        raise RuntimeError("baseline IDS alerts; inspect normal traffic before injection")
                    if args.config == 3:
                        evidence_reader.count(baseline[4], baseline[5])
                    replay = captured_replay(baseline[0], args.config > 1) if attack == "replay" else None
                    injected = collect(bus, receiver, args.duration, stream, children, attack,
                                       args.rate, active_attempt["seed"], replay)
                    post = collect(bus, receiver, args.post, stream, children)
                window = TrialWindows(baseline[4], injected[4], post[4], post[5], injected[3])
                row = judge_trial(args.config, attack, baseline[0] + injected[0] + post[0], window,
                                  injected[1], injected[2], bus.dropped)
                if args.config == 3:
                    row.update(evidence_reader.count(injected[3] or injected[4], post[5]))
                tx_log = [json.loads(line) for line in raw_path.read_text().splitlines()]
                row["tx_deadline_skipped"] = sum("tx_skipped" in item for item in tx_log)
                row["tx_syscall_errors"] = sum("tx_error" in item for item in tx_log)
                row["tx_recovered_frames"] = sum(item.get("tx_retries", 0) > 0 for item in tx_log)
                row["tx_retry_planned_count"] = sum(bool(item.get("retry_planned")) for item in tx_log)
                row.update(active_attempt)
                row.update({"raw_file": raw_path.name, "raw_sha256": sha256(raw_path)})
                ledger.write(json.dumps(row) + "\n")
                ledger.flush()
                print(f"{attack} {trial}/{args.start_trial + args.trials - 1}: {row['status']}", flush=True)
                active_attempt = None
                enforce_attempt_policy(row, args.continue_invalid)
    except KeyboardInterrupt:
        status = "INTERRUPTED"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        status = "ERROR"
        print(f"Run stopped: {error}", file=sys.stderr)
        if manifest is not None:
            manifest["error"] = str(error)
    finally:
        cleanup_errors = children.close()
        if cleanup_errors:
            status = "ERROR"
            if manifest is not None:
                manifest["cleanup_errors"] = cleanup_errors
        if bus:
            bus.close()
        if ledger:
            if active_attempt is not None:
                ledger.write(json.dumps({**active_attempt, "status": "INVALID",
                                         "invalid_reason": status}) + "\n")
            ledger.close()
        if manifest is not None:
            manifest["status"] = status
            manifest["files_sha256"] = {p.name: sha256(p) for p in root.iterdir()
                                        if p.is_file() and p.name != "manifest.json"}
            (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        signal.signal(signal.SIGTERM, previous_handler)
    return 0 if status == "COMPLETE" else 130 if status == "INTERRUPTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
