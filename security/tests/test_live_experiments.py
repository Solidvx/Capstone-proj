import io
import json
from pathlib import Path
import random
import socket
import struct
import os

import pytest

from security.experiments import can_capture, live_ablation
from security.experiments.can_capture import CaptureSocket, sha256
from security.experiments.evaluate_normal import evaluate, load_capture
from security.experiments.live_receiver import Outcome, ReferenceReceiver
from security.experiments.live_trial import Record, TrialWindows, judge_trial
from security.experiments.mac_fixture import DUMMY_KEY, NORMAL, ALTERED, auth, sequence
from security.experiments.measure_runtime_fpr import generate_normal
from security.experiments.summarize_live import summarize
from security.ids.runtime_detector import Observation


def test_mac_failure_preserves_counter_pending_and_recovery():
    receiver = ReferenceReceiver(True, DUMMY_KEY)
    results = []
    for i, (name, raw, mac) in enumerate(sequence(20)):
        receiver.process(i * .1, 0x100, raw, own=True)
        result = receiver.process(i * .1 + .001, 0x102, mac, own=True)[-1]
        results.append(result.reason)
        if name == "mutated_mac":
            assert receiver.last_counter[0x100] == 20
            assert receiver.pending[0x100].data == ALTERED
    assert results == ["AUTHENTICATED", "MAC_FAIL", "AUTHENTICATED"]
    assert receiver.last_counter[0x100] == 21


def test_receiver_expiry_replay_and_frame_shape():
    receiver = ReferenceReceiver(True, DUMMY_KEY)
    receiver.process(0, 0x100, NORMAL)
    assert receiver.process(.1, 0x102, auth(NORMAL, 7))[-1].reason == "AUTH_TIMEOUT"
    receiver.process(.2, 0x100, NORMAL)
    assert receiver.process(.201, 0x102, auth(NORMAL, 7))[-1].kind == "PUBLISHED"
    receiver.process(.3, 0x100, NORMAL, own=True)
    assert receiver.process(.301, 0x102, auth(NORMAL, 7), own=True)[-1].reason == "COUNTER_REUSE"
    assert receiver.process(.4, 0x100, NORMAL, extended=True)[-1].kind == "PARSE_REJECTED"


def baseline():
    return [Record(.05 + i * .1, 0x100, NORMAL, False,
                   [Outcome("PUBLISHED", 0x100, payload=NORMAL)]) for i in range(10)]


def test_judge_does_not_count_pre_injection_or_clear_alert_as_detection():
    records = baseline() + [Record(1.01, 0x200, bytes([4]) + bytes(7), False),
                            Record(1.1, 0x100, ALTERED, True,
                                   [Outcome("PUBLISHED", 0x100, own=True, payload=ALTERED)]),
                            Record(1.2, 0x200, bytes(8), False)]
    result = judge_trial(3, "spoofing", records, TrialWindows(0, 1, 2, 3, 1.1), 1)
    assert result["status"] == "VALID"
    assert result["attack_success"] is True
    assert result["detected"] is False
    assert result["detect_latency_s"] is None
    assert result["product_verdict"] == "NOT_RUN"


def test_late_detection_retained_and_capture_loss_invalid():
    records = baseline() + [Record(1.1, 0x000, bytes(8), True),
                            Record(4.5, 0x200, bytes([4]) + bytes(7), False)]
    window = TrialWindows(0, 1, 2, 5, 1.1)
    result = judge_trial(3, "flooding", records, window, 1)
    assert result["attack_success"] is None  # no invented 90% threshold
    assert result["detect_latency_s"] == 3.4
    assert result["blocked"] is False
    assert judge_trial(3, "flooding", records, window, 1, rx_dropped=1)["status"] == "INVALID"


def test_fuzzy_parse_valid_frame_is_not_abnormal_acceptance():
    records = baseline() + [Record(1.1, 0x100, NORMAL, True,
                                   [Outcome("PUBLISHED", 0x100, own=True, payload=NORMAL)])]
    row = judge_trial(1, "fuzzy", records, TrialWindows(0, 1, 2, 3, 1.1), 1)
    assert row["attack_success"] is False
    assert row["fuzzy_frames"] == 0


def test_capture_hash_and_independent_training_input(tmp_path):
    frames = tmp_path / "frames.jsonl"
    frames.write_text(json.dumps({"t": .1, "can_id": 256, "data": NORMAL.hex()}) + "\n", encoding="utf-8")
    manifest = {"status": "COMPLETE", "normal_attested": True, "rx_dropped": 0,
                "error_frames": 0, "duration_s": 2, "sha256": sha256(frames)}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert len(load_capture(tmp_path)[0]) == 1
    frames.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_capture(tmp_path)


def test_normal_evaluation_complete_windows_silence_and_insufficient_duration():
    frames = generate_normal(105, random.Random(42))
    result = evaluate(frames, 105)
    assert result["complete_windows"] == 103
    assert result["status"] == "PASS"
    assert result["false_positive_windows"] == 0
    assert evaluate(frames[:10], 105)["status"] == "INVALID"
    assert evaluate(frames[:10], 3)["status"] == "INVALID"
    assert evaluate(frames[:10], 105, warmup=0)["reasons"]["MESSAGE_MISSING"] > 0


def test_replay_uses_observed_accepted_pair():
    raw = Record(1, 0x100, NORMAL, False)
    mac = auth(NORMAL, 78)
    verified = Record(1.001, 0x102, mac, False, [Outcome("PUBLISHED", 0x100)])
    assert live_ablation.captured_replay([raw, verified], True) == [(0x100, NORMAL), (0x102, mac)]
    with pytest.raises(ValueError):
        live_ablation.captured_replay([raw], True)


@pytest.mark.skipif(not hasattr(socket, "MSG_CONFIRM"), reason="Linux MSG_CONFIRM")
def test_rx_own_attribution_uses_kernel_confirmation_not_matching_payload():
    class Sock:
        flags = socket.MSG_DONTROUTE
        def settimeout(self, _):
            pass
        def recvmsg(self, *_):
            return struct.pack("=IB3x8s", 0x100, 8, NORMAL), [(socket.SOL_SOCKET, 40, struct.pack("=I", 2))], self.flags, None
    bus = CaptureSocket.__new__(CaptureSocket)
    bus.socket = Sock()
    bus.dropped = 0
    assert bus.receive()[1] is False
    bus.socket.flags |= socket.MSG_CONFIRM
    assert bus.receive()[1] is True
    assert bus.dropped == 2


def test_receive_only_socket_rejects_send():
    bus = CaptureSocket.__new__(CaptureSocket)
    bus.transmit = False
    with pytest.raises(RuntimeError, match="receive-only"):
        bus.send(0x100, NORMAL)


def test_collection_schedules_and_retains_send_errors():
    now = [0.0]
    class Bus:
        queue = []
        attempts = 0
        def send(self, cid, data):
            self.attempts += 1
            if self.attempts == 1:
                raise OSError("queue full")
            self.queue.append((Observation(now[0], cid, data), True))
        def receive(self, timeout):
            now[0] += min(.001, timeout)
            return self.queue.pop(0) if self.queue else None
    output = io.StringIO()
    records, sent, errors, first, _, _ = live_ablation.collect(
        Bus(), ReferenceReceiver(False), .1, output, live_ablation.Children(),
        "spoofing", 100, 1, clock=lambda: now[0])
    assert errors == 1
    assert sent == len(records) > 0
    assert first > 0
    assert '"tx_error"' in output.getvalue()


def test_summary_refuses_duplicates_and_does_not_count_invalid(tmp_path):
    row = judge_trial(1, "spoofing", baseline() + [Record(1.1, 0x100, ALTERED, True)],
                      TrialWindows(0, 1, 2, 3, 1.1), 1)
    row.update(run_id="test", environment="vcan", config=1, ids_mode="off", attack_type="spoofing", trial=1)
    ledger = tmp_path / "attempts.jsonl"
    ledger.write_text(json.dumps(row) + "\n" + json.dumps({**row, "trial": 2, "status": "INVALID"}) + "\n", encoding="utf-8")
    manifest = {"run_id": "test", "environment": "vcan", "config": 1, "ids_mode": "off",
                "attacks": ["spoofing", "replay"], "trials_per_attack": 2,
                "files_sha256": {"attempts.jsonl": sha256(ledger)}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = summarize([tmp_path])
    spoof = next(r for r in result if r["attack"] == "spoofing")
    assert spoof["valid"] == 1 and spoof["invalid"] == 1 and spoof["missing_to_100"] == 99
    assert spoof["official_verdict"] == "NOT_RUN"
    assert next(r for r in result if r["attack"] == "replay")["valid"] == 0
    with pytest.raises(ValueError, match="duplicate trial"):
        summarize([tmp_path, tmp_path])


@pytest.mark.skipif(os.name != "posix", reason="Linux process groups")
def test_children_reaped_on_close(tmp_path):
    children = live_ablation.Children()
    import sys
    children.start([sys.executable, "-c", "import time; time.sleep(60)"], tmp_path / "child.log")
    process = children.items[0][0]
    children.close()
    assert process.poll() is not None


def test_capture_exception_not_marked_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(can_capture, "inspect_interface", lambda *_: {"kind": "vcan"})
    class Broken:
        dropped = 0
        def __init__(self, *_):
            pass
        def receive(self):
            raise OSError("disconnected")
        def close(self):
            pass
    monkeypatch.setattr(can_capture, "CaptureSocket", Broken)
    out = tmp_path / "capture"
    assert can_capture.main(["--channel", "vcan0", "--environment", "vcan", "--out", str(out)]) == 2
    assert json.loads((out / "manifest.json").read_text())["status"] == "ERROR"


@pytest.mark.parametrize("send_failure", [False, True])
def test_full_runner_writes_attempts_and_cleans_up_on_success_and_failure(tmp_path, monkeypatch, send_failure):
    now = [0.0]
    active = [False]
    closed = []
    class Owned:
        def start(self, argv, output):
            active[0] = True
            Path(output).write_text("test process fixture", encoding="utf-8")
        def check(self):
            pass
        def close(self):
            closed.append("children")
    class Bus:
        dropped = 0
        def __init__(self, *_args, **_kwargs):
            self.queue = []
            self.last_normal = 0
        def send(self, cid, data):
            if send_failure:
                raise OSError("simulated queue failure")
            self.queue.append((Observation(now[0], cid, data), True))
        def receive(self, timeout=.01):
            now[0] += max(.00001, min(timeout, .01))
            if self.queue:
                return self.queue.pop(0)
            if active[0] and now[0]-self.last_normal >= .1:
                self.last_normal = now[0]
                return Observation(now[0], 0x100, NORMAL), False
            return None
        def close(self):
            closed.append("socket")
    monkeypatch.setattr(live_ablation.time, "monotonic", lambda: now[0])
    # collect's default clock was bound at definition; inject the test clock.
    original_collect = live_ablation.collect
    monkeypatch.setattr(live_ablation, "collect", lambda *a, **kw: original_collect(*a, **kw, clock=lambda: now[0]))
    monkeypatch.setattr(live_ablation, "Children", Owned)
    monkeypatch.setattr(live_ablation, "CaptureSocket", Bus)
    monkeypatch.setattr(live_ablation, "inspect_interface", lambda *_: {"kind": "vcan"})
    ecu = tmp_path / "ecu"
    ecu.write_text("mock executable", encoding="utf-8")
    out = tmp_path / "run"
    code = live_ablation.main(["--channel", "vcan0", "--environment", "vcan", "--config", "1",
                              "--attack", "spoofing", "--rate", "10", "--duration", ".3",
                              "--ecu", str(ecu), "--out", str(out), "--run-id", "mock"])
    manifest = json.loads((out / "manifest.json").read_text())
    attempts = [json.loads(line) for line in (out / "attempts.jsonl").read_text().splitlines()]
    assert closed == ["children", "socket"]
    assert len(attempts) == 1
    assert code == (2 if send_failure else 0)
    assert attempts[0]["status"] == ("INVALID" if send_failure else "VALID")
    assert manifest["status"] == ("ERROR" if send_failure else "COMPLETE")
    assert attempts[0]["product_verdict"] == "NOT_RUN"


def test_adc_summary_preserves_outliers_errors_and_missing_samples():
    from security.experiments.analyze_adc import summarize as adc_summary
    rows = [{"sample": str(i), "raw": str(value), "status": "OK"} for i, value in enumerate([-33, 0, 26433])]
    result = adc_summary(rows)
    assert result["outside_current_tolerance"] == 2
    assert result["complete_1000"] is False
    with pytest.raises(ValueError):
        adc_summary(rows[1:])


def test_synthetic_summary_does_not_pool_environments():
    from security.experiments.summarize_ablation import summarise
    row = {"config": "1", "attack_type": "replay", "attack_success": "True", "blocked": "False", "detected": "False"}
    assert len(summarise([{**row, "environment": "synthetic"}, {**row, "environment": "vcan"}])) == 2
    with pytest.raises(ValueError):
        summarise([{**row, "blocked": "bad"}])
