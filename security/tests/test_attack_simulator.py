import random

from security.attacks.attack_simulator import (
    ATTACK_TYPES,
    MAX_DURATION_S,
    MAX_RATE_FPS,
    build_frame,
    is_test_bus,
    validate,
)


def test_vcan_always_allowed_real_can_requires_ack():
    assert is_test_bus("vcan0", False)
    assert not is_test_bus("can0", False)
    assert is_test_bus("can0", True)
    assert not is_test_bus("eth0", True)


def test_validate_refuses_bad_targets_and_limits():
    assert validate("flooding", "vcan0", 1000, 5, False) is None
    assert validate("flooding", "can0", 1000, 5, False) is not None      # no ack
    assert validate("nope", "vcan0", 1000, 5, False) is not None         # bad type
    assert validate("fuzzy", "vcan0", MAX_RATE_FPS + 1, 5, False) is not None
    assert validate("fuzzy", "vcan0", 0, 5, False) is not None
    assert validate("fuzzy", "vcan0", 1000, MAX_DURATION_S + 1, False) is not None
    assert validate("fuzzy", "vcan0", 1000, 0, False) is not None


def test_build_frame_shapes_and_determinism():
    rng = random.Random(1)
    for attack in ATTACK_TYPES:
        can_id, data = build_frame(attack, rng, 0)
        assert 0 <= can_id <= 0x7FF
        assert len(data) == 8
    assert build_frame("flooding", rng, 0)[0] == 0x000
    assert build_frame("spoofing", rng, 0)[1][0] == 200       # SOC raw 100%
    assert build_frame("replay", rng, 0)[0] == 0x100
    # Fuzzy is deterministic for a fixed seed.
    assert build_frame("fuzzy", random.Random(5), 0) == build_frame("fuzzy", random.Random(5), 0)
