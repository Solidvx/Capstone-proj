import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from secoc_module import SecOcModule


KEY = bytes(range(32))
PAYLOAD = bytes.fromhex("96BE1068FFEC4100")


def test_sign_counter_zero_vector_shape():
    secoc = SecOcModule(KEY)
    auth = secoc.sign(0x102, 0x100, PAYLOAD)

    assert auth.can_id == 0x102
    assert len(auth.data) == 8
    assert auth.data[:4] == bytes.fromhex("D0DDFC05")
    assert auth.data[4:] == b"\x00\x00\x00\x00"


def test_verify_accepts_first_valid_counter_zero():
    signer = SecOcModule(KEY)
    verifier = SecOcModule(KEY)

    auth = signer.sign(0x102, 0x100, PAYLOAD)

    assert verifier.verify(0x100, PAYLOAD, auth.data)


def test_verify_rejects_tampered_mac():
    signer = SecOcModule(KEY)
    verifier = SecOcModule(KEY)
    auth = signer.sign(0x102, 0x100, PAYLOAD)
    tampered = bytes([auth.data[0] ^ 0xFF]) + auth.data[1:]

    assert not verifier.verify(0x100, PAYLOAD, tampered)


def test_verify_rejects_replay_counter():
    signer = SecOcModule(KEY)
    verifier = SecOcModule(KEY)
    auth = signer.sign(0x102, 0x100, PAYLOAD)

    assert verifier.verify(0x100, PAYLOAD, auth.data)
    assert not verifier.verify(0x100, PAYLOAD, auth.data)


def test_verify_accepts_counter_wrap():
    signer = SecOcModule(KEY)
    verifier = SecOcModule(KEY)
    signer.counter = 0xFFFFFFFF

    last_before_wrap = signer.sign(0x102, 0x100, PAYLOAD)
    wrapped = signer.sign(0x102, 0x100, PAYLOAD)

    assert verifier.verify(0x100, PAYLOAD, last_before_wrap.data)
    assert verifier.verify(0x100, PAYLOAD, wrapped.data)
    assert wrapped.data[4:] == b"\x00\x00\x00\x00"


# Public dummy-key vectors independently generated with HMAC-SHA256.
# No session protocol is exercised by these legacy fixed-key tests.
BOUNDARY_VECTORS = {
    0: bytes.fromhex("d0ddfc0500000000"),
    42: bytes.fromhex("a4b9a2a60000002a"),
    55: bytes.fromhex("96673a5e00000037"),
    56: bytes.fromhex("31004dc000000038"),
    155: bytes.fromhex("f571eb030000009b"),
    156: bytes.fromhex("e51141f10000009c"),
}


def test_counter_window_boundaries_and_rejected_state_preservation():
    for candidate, accepted in [(55, False), (56, True), (155, True), (156, False), (42, False), (0, False)]:
        verifier = SecOcModule(KEY)
        assert verifier.verify(0x100, PAYLOAD, BOUNDARY_VECTORS[55])
        assert verifier.verify(0x100, PAYLOAD, BOUNDARY_VECTORS[candidate]) is accepted
        if not accepted:
            assert verifier.verify(0x100, PAYLOAD, BOUNDARY_VECTORS[56])


def test_invalid_mac_inside_window_does_not_consume_counter():
    verifier = SecOcModule(KEY)
    assert verifier.verify(0x100, PAYLOAD, BOUNDARY_VECTORS[55])
    valid = BOUNDARY_VECTORS[56]
    bad = bytes([valid[0] ^ 1]) + valid[1:]
    assert not verifier.verify(0x100, PAYLOAD, bad)
    assert verifier.verify(0x100, PAYLOAD, valid)


def test_legacy_fresh_receiver_accepts_old_mac_limitation():
    # Characterizes an unresolved security limitation, not security acceptance.
    for old_counter in (42, 0):
        verifier = SecOcModule(KEY)
        assert verifier.verify(0x100, PAYLOAD, BOUNDARY_VECTORS[old_counter])
        assert not verifier.verify(0x100, PAYLOAD, BOUNDARY_VECTORS[old_counter])
