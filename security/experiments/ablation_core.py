"""Ablation judging shared by the synthetic pre-check and the live SocketCAN run.

Three defence configurations see the *same* attack trial (config is not part of
the trial seed). Attack success, SecOC blocking, and IDS detection are observed
independently (M5 3.1): detection is not blocking. Values that a synthetic
receiver cannot honestly measure (flooding/fuzzy availability on a real bus) are
left as None and must come from the physical run.
"""

from __future__ import annotations

import os
import random
import sys

_SEC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.dirname(_SEC)
for path in (_ROOT, _SEC, os.path.join(_SEC, "attacks")):
    if path not in sys.path:
        sys.path.insert(0, path)

from secoc_module import SecOcModule          # security/secoc_module.py
from traffic_gen import ATTACKS, gen_attack   # security/attacks/
# runtime_detector uses a package-relative import, so load it as security.ids.*
from security.ids.runtime_detector import Config, Observation, RuntimeDetector

CONFIGS = {1: (False, False), 2: (True, False), 3: (True, True)}  # (secoc_on, ids_on)
# Official matrix attacks; masquerade is a detector-comparison case, not in the 1,200.
MATRIX_ATTACKS = ["fuzzy", "replay", "spoofing", "flooding"]
TRIALS = 100
DUMMY_KEY = b"\x01" * 32  # experiment-only key; never a real SecOC key


def trial_seed(attack: str, trial: int) -> int:
    """Config is intentionally absent: configs 1/2/3 share identical input."""
    return 100_000 + 1_000 * MATRIX_ATTACKS.index(attack) + trial


def _ids_detected(frames, ids_on: bool) -> bool:
    """Config 3 only: did the rule IDS flag anything in this trial?

    Normal-only false positives are measured separately (TC-EXP-005), so here a
    produced ANOMALY on an attack trial counts as a detection.
    """
    if not ids_on:
        return False
    detector = RuntimeDetector(Config())
    for frame in frames:
        for event in detector.observe(Observation(frame.t, frame.can_id, frame.data, frame.dlc)):
            if event.result == "ANOMALY":
                return True
    return False


def evaluate_synthetic_trial(config: int, attack: str, trial: int) -> dict:
    """One synthetic trial row. Receiver uses the real SecOcModule rules."""
    secoc_on, ids_on = CONFIGS[config]
    seed = trial_seed(attack, trial)
    frames = sorted(gen_attack(attack, 3.0, random.Random(seed)), key=lambda f: f.t)

    signer = SecOcModule(DUMMY_KEY)
    verifier = SecOcModule(DUMMY_KEY) if secoc_on else None
    accepted = rejected = attack_auth_rejected = normal_delivered = 0
    spoof_reflected = replay_accepted = False

    for frame in frames:
        if frame.can_id != 0x100:
            continue  # non-0x100 attack traffic (flooding 0x000, most fuzzy IDs)
        if secoc_on:
            # Only genuine BMS frames get a valid 0x102; attack 0x100 has none.
            auth = signer.sign(0x102, 0x100, frame.data) if frame.label == 0 else None
            ok = bool(auth) and verifier.verify(0x100, frame.data, auth.data)
        else:
            ok = True  # Config 1: no authentication
        if ok:
            accepted += 1
            if frame.label == 0:
                normal_delivered += 1
            if frame.data[0] == 200:            # manipulated SOC 100% reflected
                spoof_reflected = True
            if frame.attack_type == "replay":
                replay_accepted = True
        else:
            rejected += 1
            if frame.label == 1:
                attack_auth_rejected += 1

    # Attack-specific success (M5 table). None = not measurable synthetically.
    if attack == "spoofing":
        success: bool | None = spoof_reflected
    elif attack == "replay":
        success = replay_accepted
    else:  # flooding (bus availability), fuzzy (parser acceptance): physical only
        success = None

    return {
        "config": config, "attack_type": attack, "trial": trial, "seed": seed,
        "environment": "synthetic",
        "attack_success": success,
        "blocked": attack_auth_rejected > 0,
        "detected": _ids_detected(frames, ids_on),
        "rx_accepted": accepted, "rx_rejected": rejected,
        "attack_auth_rejected": attack_auth_rejected,
        "normal_delivered": normal_delivered,
    }


CSV_FIELDS = ["config", "attack_type", "trial", "seed", "environment",
              "attack_success", "blocked", "detected",
              "rx_accepted", "rx_rejected", "attack_auth_rejected", "normal_delivered"]
