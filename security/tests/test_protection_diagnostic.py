"""Public dummy vectors for the approved ProtectionStatus wire contract.

This validates the codec, not ECU checkpoint or IVI incident continuity.
"""
from pathlib import Path

import pytest

from security.can_diagnostic import decode, encode, valid_body
from security.tests.diagnostic_fixtures import fixtures, put, uuid_bytes


VECTOR_PATH = Path(__file__).resolve().parents[2] / 'docs/aidlc/changes/CHG-029/protection-v1-vectors.tsv'


def bodies():
    cases = []
    for name, state, reason, phase, resumed, revision in (
        ('fresh', 0, 0, 0, 0, 0), ('resume', 0, 0, 0, 1, 0),
        ('warning', 1, 7, 1, 0, 1), ('critical', 2, 2, 1, 1, 2),
        ('hot', 3, 4, 1, 1, 3), ('closed', 0, 6, 2, 1, 4),
    ):
        body = bytearray(56)
        body[:16], body[16:32] = uuid_bytes(0x11), uuid_bytes(0x22)
        if phase:
            body[32:48] = uuid_bytes(0x77)
        body[48:52] = bytes((state, reason, phase, resumed))
        put(body, 52, revision)
        cases.append((name, bytes(body)))
    return cases


def public_vectors():
    ctx, keys, _ = fixtures()
    values = {}
    for index, (name, body) in enumerate(bodies()):
        frames = encode(keys, ctx, 0x302, 64 + index, 8, body)
        values['body.' + name] = body.hex()
        values['envelope.' + name] = b''.join(data[4:] for _, data in frames)[:94].hex()
        for i, (cid, data) in enumerate(frames):
            values[f'frame.{name}.{i}'] = f'{cid}:{data.hex()}'
    return values


def test_independent_frozen_protection_vectors():
    expected = dict(line.split('\t') for line in VECTOR_PATH.read_text().splitlines())
    assert public_vectors() == expected


@pytest.mark.parametrize('index', range(6))
def test_phase_authentication_fragment_order_and_exact_size(index):
    ctx, keys, _ = fixtures()
    _, body = bodies()[index]
    frames = encode(keys, ctx, 0x302, 64 + index, 8, body)
    assert len(frames) == 24
    assert all(cid == 0x302 and len(data) == 8 for cid, data in frames)
    assert decode(keys, ctx, 0x302, frames[::-1]) == (64 + index, 8, body)
    assert decode(keys, ctx, 0x302, frames + frames[:1]) == (64 + index, 8, body)
    for bit in range(128):
        changed = list(frames)
        offset = 78 + bit // 8
        cid, data = changed[offset // 4]
        damaged = bytearray(data)
        damaged[4 + offset % 4] ^= 1 << (bit % 8)
        changed[offset // 4] = cid, bytes(damaged)
        with pytest.raises(ValueError, match='authentication'):
            decode(keys, ctx, 0x302, changed)


def test_all_state_reason_phase_combinations():
    body = bytearray(bodies()[2][1])
    allowed_reasons = ({0, 5, 6}, {0, 1, 3, 7}, {0, 2}, {0, 4})
    for phase in range(4):
        for state in range(5):
            for reason in range(9):
                body[48:51] = bytes((state, reason, phase))
                expected = (phase in (1, 2) and state < 4
                            and reason in allowed_reasons[state]
                            and (state != 0 if phase == 1 else state == 0))
                assert valid_body(0x302, 8, bytes(body)) == expected
    body = bytearray(bodies()[0][1])
    for reason in (5, 6):
        body[49] = reason
        assert not valid_body(0x302, 8, bytes(body))


def test_identity_revision_reserved_direction_and_length_boundaries():
    ctx, keys, _ = fixtures()
    original = bodies()[2][1]
    for at in (0, 16, 32):
        bad = bytearray(original)
        bad[at:at+16] = bytes(16)
        assert not valid_body(0x302, 8, bad)
        bad[at:at+16] = uuid_bytes(0x11)
        bad[at+8] = 0
        assert not valid_body(0x302, 8, bad)
    for flag in (2, 128, 255):
        bad = bytearray(original)
        bad[51] = flag
        assert not valid_body(0x302, 8, bad)
    bad = bytearray(original)
    put(bad, 52, 0)
    assert not valid_body(0x302, 8, bad)
    put(bad, 52, 0xFFFFFFFF)
    assert valid_body(0x302, 8, bad)  # representable last revision, never wrap it
    for bad in (original[:-1], original + b'\0'):
        with pytest.raises(ValueError):
            encode(keys, ctx, 0x302, 0, 8, bad)
    assert not valid_body(0x303, 8, original)
    for kind in (0, 9, 255):
        assert not valid_body(0x302, kind, original)


def test_other_session_and_missing_fragment_do_not_become_current_evidence():
    from security.can_session import SessionContext
    ctx, keys, _ = fixtures()
    frames = encode(keys, ctx, 0x302, 64, 8, bodies()[2][1])
    with pytest.raises(ValueError, match='session'):
        decode(keys, SessionContext(ctx.transfer_id, b'C' * 16, b'D' * 16), 0x302, frames)
    with pytest.raises(ValueError, match='fragment'):
        decode(keys, ctx, 0x302, frames[:-1])


def test_normal_protection_wire_is_not_misclassified_as_an_attack():
    from security.ids.runtime_detector import Config, Observation
    from security.ids.session_detector import SessionDetector

    ctx, keys, _ = fixtures()

    class Source:
        generation = 1
        context = ctx
        boundary_ns = 0

        def poll(self, now):
            return False

        def ready(self, now):
            return True

    source = Source()
    source.keys = keys
    detector = SessionDetector(Config(), source)
    observed = []
    t = 0.0
    for index, (_, body) in enumerate(bodies()):
        for cid, data in encode(keys, ctx, 0x302, 64 + index, 8, body):
            observed.extend(detector.observe(Observation(t, cid, data)))
            t += .005
    observed.extend(detector.tick(t))
    assert not [event for event in observed if event.attack_type]
