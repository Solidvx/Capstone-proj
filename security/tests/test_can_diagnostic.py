from pathlib import Path

import pytest

from security.can_diagnostic import decode, encode, valid_body
from security.tests.diagnostic_fixtures import dummy_vectors, fixtures, put

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "docs/aidlc/changes/CHG-029"


def test_frozen_public_vectors_and_inputs():
    assert dummy_vectors() == dict(line.split("\t") for line in (RECORD / "diagnostic-v1-vectors.tsv").read_text().splitlines())
    actual = [f"{name}\t{sender}\t{sequence}\t{kind}\t{body.hex()}" for name, sender, sequence, kind, body in fixtures()[2]]
    assert actual == (RECORD / "diagnostic-inputs.tsv").read_text().splitlines()


@pytest.mark.parametrize("index", range(8))
def test_all_schemas_both_fragment_orders(index):
    ctx, keys, samples = fixtures()
    _, sender, sequence, kind, body = samples[index]
    frames = encode(keys, ctx, sender, sequence, kind, body)
    assert decode(keys, ctx, sender, frames) == (sequence, kind, body)
    assert decode(keys, ctx, sender, frames[::-1]) == (sequence, kind, body)
    assert decode(keys, ctx, sender, frames + frames[:1]) == (sequence, kind, body)


def test_all_tag_bits_and_direction_reflection_rejected():
    ctx, keys, samples = fixtures()
    _, sender, sequence, kind, body = samples[6]
    frames = encode(keys, ctx, sender, sequence, kind, body)
    for bit in range(128):
        changed = list(frames)
        offset = 22 + len(body) + bit // 8
        can_id, frame = changed[offset // 4]
        data = bytearray(frame)
        data[4 + offset % 4] ^= 1 << (bit % 8)
        changed[offset // 4] = can_id, bytes(data)
        with pytest.raises(ValueError, match="authentication"):
            decode(keys, ctx, sender, changed)
    with pytest.raises(ValueError, match="authentication"):
        decode(keys, ctx, 0x302, [(0x302, data) for _, data in frames])


@pytest.mark.parametrize("index", range(8))
def test_invalid_uuid_length_and_direction(index):
    ctx, keys, samples = fixtures()
    _, sender, sequence, kind, body = samples[index]
    changed = bytearray(body)
    changed[6] = 0
    for bad in (bytes(changed), body[:-1], body + b"\0"):
        assert not valid_body(sender, kind, bad)
        with pytest.raises(ValueError):
            encode(keys, ctx, sender, sequence, kind, bad)
    if kind != 6:
        assert not valid_body(0x303 if sender == 0x302 else 0x302, kind, body)


def test_typed_semantics_keep_unknown_and_pending_distinct():
    _, _, samples = fixtures()
    metrics = bytearray(samples[5][4])
    put(metrics, 24, 0)
    assert not valid_body(0x302, 6, metrics)  # unknown cannot become measured zero
    incident = bytearray(samples[3][4])
    incident[33] = 2
    assert not valid_body(0x302, 4, incident)
    put(incident, 52, 5000)
    assert valid_body(0x302, 4, incident)
    rejection = bytearray(samples[4][4])
    rejection[32:36] = bytes((6, 0, 2, 0))
    assert valid_body(0x303, 5, rejection)  # MAC budget is pending, not rejected
    rejection[34] = 1
    assert not valid_body(0x303, 5, rejection)
    observation = bytearray(samples[7][4])
    put(observation, 40, 1)
    assert not valid_body(0x302, 7, observation)  # capture loss cannot assert healthy
    observation[16:18] = bytes((2, 1))
    put(observation, 44, 0)
    assert valid_body(0x302, 7, observation)
    plan = bytearray(samples[1][4])
    plan[50] = 2
    assert not valid_body(0x302, 2, plan)  # same shutdown gets only one automatic attempt
    node = bytearray(samples[0][4])
    node[34] = 4
    assert not valid_body(0x302, 1, node)  # last value after an error is not ready
    node[53] = 0
    assert valid_body(0x302, 1, node)
    fatal = bytearray(samples[4][4])
    fatal[32], fatal[34] = 12, 1
    assert not valid_body(0x303, 5, fatal)
    fatal[34] = 5
    assert valid_body(0x303, 5, fatal)
    fatal[48:64] = bytes(16)
    assert not valid_body(0x303, 5, fatal)  # verified pair needs its context


def test_missing_conflicting_and_padding_fragments():
    ctx, keys, samples = fixtures()
    _, sender, sequence, kind, body = samples[0]
    frames = encode(keys, ctx, sender, sequence, kind, body)
    with pytest.raises(ValueError):
        decode(keys, ctx, sender, frames[1:])
    bad = bytearray(frames[0][1])
    bad[4] ^= 1
    with pytest.raises(ValueError, match="mixed"):
        decode(keys, ctx, sender, frames + [(sender, bytes(bad))])
    changed = list(frames)
    last = bytearray(changed[-1][1])
    last[-1] = 1
    changed[-1] = sender, bytes(last)
    with pytest.raises(ValueError, match="padding"):
        decode(keys, ctx, sender, changed)
