import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.experiments import measure_runtime_fpr as m
from security.ids.runtime_detector import Config, KNOWN_IDS


def test_normal_generator_uses_only_known_ids_and_valid_frames():
    frames = m.generate_normal(5.0, random.Random(1))
    assert frames, "expected normal frames"
    for frame in frames:
        assert frame.can_id in KNOWN_IDS
        assert frame.dlc == 8 and len(frame.data) == 8
        assert frame.data[7] == 0 or frame.can_id == 0x102  # BMS reserved byte is 0


def test_150s_capture_gives_at_least_100_complete_windows():
    frames = m.generate_normal(150.0, random.Random(20261003))
    result = m.measure(frames, Config())
    assert result["total_windows"] >= 100


def test_clean_normal_traffic_has_no_rule_false_positives():
    frames = m.generate_normal(120.0, random.Random(7))
    result = m.measure(frames, Config())
    assert result["anomaly_events"] == 0
    assert result["fp_windows"] == 0
    assert result["fpr"] == 0.0
