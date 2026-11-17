"""Kind9 is authenticated sensor evidence, with independent unknown quantities."""
import pytest
from pathlib import Path

from security.can_diagnostic import decode, encode, valid_body
from security.tests.diagnostic_fixtures import fixtures


def body():
    b = bytearray(80)
    b[6], b[8], b[16] = 0x40, 0x80, 1
    b[32:40] = (3).to_bytes(8, "big")
    b[40:44] = (3853100).to_bytes(4, "big")
    b[44:48] = (-371100).to_bytes(4, "big", signed=True)
    b[48:52] = (20125).to_bytes(4, "big")
    b[56:60] = (800).to_bytes(4, "big")
    b[64:70] = bytes((1, 7, 0, 0, 2, 2))
    b[72:76] = (2550).to_bytes(4, "big")
    b[76:80] = (3000).to_bytes(4, "big")
    return b


def test_public_vectors_cross_language_contract():
    ctx, keys, _ = fixtures()
    path = Path(__file__).resolve().parents[2] / "common/testdata/physical-v1-vectors.tsv"
    rows = path.read_text().splitlines()
    assert len(rows) == 4
    for line in rows:
        name, sequence, body_hex, frames_hex = line.split("\t")
        value = bytes.fromhex(body_hex)
        frames = encode(keys, ctx, 0x302, int(sequence), 9, value)
        assert "".join(data.hex() for _, data in frames) == frames_hex, name
        assert decode(keys, ctx, 0x302, frames) == (int(sequence), 9, value)
    assert bytes.fromhex(rows[0].split("\t")[2]) == body()


def test_authenticated_roundtrip_and_zero_is_not_unknown():
    ctx, keys, _ = fixtures()
    b = body()
    frames = encode(keys, ctx, 0x302, 123, 9, bytes(b))
    assert len(frames) == 30
    assert decode(keys, ctx, 0x302, frames[::-1]) == (123, 9, bytes(b))
    assert not valid_body(0x303, 9, b)
    assert b[65] & 8 == 0  # unknown SOC, canonical number zero
    b[65] |= 8
    assert not valid_body(0x302, 9, b)
    b[66] = 1
    assert valid_body(0x302, 9, b)  # explicit valid 0% has a different flag/basis


@pytest.mark.parametrize("at,value", [(6, 0), (8, 0), (64, 2), (65, 1), (66, 2), (67, 1),
                                     (68, 3), (69, 3), (70, 2), (71, 1), (52, 1)])
def test_noncanonical_and_inconsistent_fields_rejected(at, value):
    b = body()
    b[at] = value
    assert not valid_body(0x302, 9, b)


def test_invalid_sensor_fields_are_absent_and_temperature_is_independent():
    b = body()
    b[65], b[69] = 3, 4
    b[48:52] = bytes(4)
    assert valid_body(0x302, 9, b)
    b[48] = 1
    assert not valid_body(0x302, 9, b)


def test_physical_tags_padding_and_missing_frames_rejected():
    ctx, keys, _ = fixtures()
    frames = encode(keys, ctx, 0x302, 123, 9, bytes(body()))
    for bit in range(128):
        changed = list(frames)
        at = 102 + bit // 8
        can_id, frame = changed[at // 4]
        data = bytearray(frame)
        data[4 + at % 4] ^= 1 << (bit % 8)
        changed[at // 4] = can_id, bytes(data)
        with pytest.raises(ValueError):
            decode(keys, ctx, 0x302, changed)
    with pytest.raises(ValueError):
        decode(keys, ctx, 0x302, frames[:-1])
    changed = list(frames)
    changed[-1] = (0x302, changed[-1][1][:-1] + b"\x01")
    with pytest.raises(ValueError):
        decode(keys, ctx, 0x302, changed)
