import importlib.util
import os

_SEC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "ablation_core", os.path.join(_SEC, "experiments", "ablation_core.py"))
ablation_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ablation_core)

evaluate = ablation_core.evaluate_synthetic_trial


def test_trial_seed_excludes_config():
    # Same (attack, trial) => identical seed across configs 1/2/3.
    seeds = {ablation_core.trial_seed("spoofing", 7)}
    assert len(seeds) == 1


def test_spoofing_blocked_by_secoc_not_by_config1():
    c1 = evaluate(1, "spoofing", 0)
    c2 = evaluate(2, "spoofing", 0)
    # Config 1 (no defence): manipulated SOC is reflected, nothing blocked.
    assert c1["attack_success"] is True
    assert c1["blocked"] is False
    assert c1["detected"] is False
    # Config 2 (SecOC): forged 0x100 rejected, not reflected.
    assert c2["attack_success"] is False
    assert c2["blocked"] is True


def test_replay_accepted_without_secoc_rejected_with():
    assert evaluate(1, "replay", 0)["attack_success"] is True
    assert evaluate(2, "replay", 0)["attack_success"] is False


def test_detection_only_in_config3():
    for attack in ablation_core.MATRIX_ATTACKS:
        assert evaluate(2, attack, 0)["detected"] is False
    # Config 3 detects at least the volumetric/forgery attacks.
    assert evaluate(3, "flooding", 0)["detected"] is True
    assert evaluate(3, "spoofing", 0)["detected"] is True


def test_flooding_fuzzy_success_unmeasured_synthetically():
    assert evaluate(1, "flooding", 0)["attack_success"] is None
    assert evaluate(1, "fuzzy", 0)["attack_success"] is None


def test_detection_is_not_blocking():
    # IDS may detect while SecOC also blocks, but the two are separate columns.
    row = evaluate(3, "spoofing", 0)
    assert row["blocked"] is True and row["detected"] is True
    assert row["attack_success"] is False  # blocked, so not reflected
