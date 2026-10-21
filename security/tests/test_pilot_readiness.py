import io
import json
import random

import pytest

from security.experiments import can_capture, live_ablation
from security.experiments.evaluate_normal import evaluate
from security.experiments.live_receiver import ReferenceReceiver
from security.experiments.measure_runtime_fpr import generate_normal
from security.ids.runtime import normal_vectors, train_model


def write_normal(path, seed, duration=150):
    frames = generate_normal(duration, random.Random(seed))
    path.write_text(''.join(json.dumps({'t': f.t, 'can_id': f.can_id,
                                      'data': f.data.hex()})+'\n' for f in frames)
                    + json.dumps({'tick': duration})+'\n', encoding='utf-8')
    return frames


def test_training_uses_runtime_vectors(tmp_path):
    path = tmp_path/'normal.jsonl'
    frames = write_normal(path, 3101)
    class Recorder:
        def __init__(self): self.vectors = []
        def anomaly(self, vector):
            self.vectors.append(vector)
            return -1
    model = Recorder()
    evaluate(frames, 150, model=model)
    assert normal_vectors(path) == model.vectors


def test_independent_calibration_and_insufficient_data(tmp_path):
    fit, cal = tmp_path/'fit.jsonl', tmp_path/'cal.jsonl'
    write_normal(fit, 3101)
    write_normal(cal, 3102)
    model = train_model(fit, cal)
    assert model.calibration['windows'] >= 100
    assert model.calibration['alpha'] == .01
    assert model.anomaly([3000, .0003, .00001, 20, 4, 7, 2000]) > 0
    with pytest.raises(ValueError, match='independent'):
        train_model(fit, fit)
    write_normal(cal, 3102, duration=5)
    with pytest.raises(ValueError, match='insufficient'):
        train_model(fit, cal)


def test_submillisecond_receive_wait_is_not_rounded(monkeypatch):
    bus = can_capture.CaptureSocket.__new__(can_capture.CaptureSocket)
    bus.socket = object()
    waits = []
    def select(read, write, error, timeout):
        waits.append(timeout)
        return [], [], []
    monkeypatch.setattr(can_capture.select, 'select', select)
    assert bus.receive(.0002) is None
    assert waits == [.0002]


def test_send_processing_time_is_included_without_catchup():
    now, sends = [0.0], []
    class Bus:
        def send(self, cid, data):
            sends.append(now[0])
            now[0] += .0004 if len(sends) != 5 else .005
        def receive(self, timeout):
            now[0] += timeout
            return None
    live_ablation.collect(Bus(), ReferenceReceiver(False), .03, io.StringIO(),
                          live_ablation.Children(), 'flooding', 1000,
                          clock=lambda: now[0])
    assert sends[1]-sends[0] == pytest.approx(.001)
    assert len(sends) >= 24
    assert all(b-a >= .000999 for a,b in zip(sends,sends[1:]))
