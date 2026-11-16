"""Public dummy vectors only. The candidate does not activate product CAN IDs."""
import pathlib

import pytest

from security.can_session import (SessionContext, _derive32, control_tag, data_mac,
                                  derive_keys, fragment, state_receipt_tag, tag_matches)

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "docs/aidlc/changes/CHG-029/session-v2-vectors.tsv"


def dummy_vectors():
    context = SessionContext(0x1234, b"B" * 16, b"A" * 16)
    keys = derive_keys(bytes(range(32)), context)
    out = {"transcript": context.transcript().hex()}
    # Freeze the original six-role fixture. New diagnostic roles have their own
    # independent fixture; do not rewrite the earlier53-field evidence.
    out.update({"key." + role: key.hex() for role, key in keys.items()
                if role in ("offer", "confirm", "ack", "data", "ready", "state-receipt")})
    tags = {role: control_tag(keys, context, role) for role in ("offer", "confirm", "ack", "ready")}
    out.update({"tag." + role: tag.hex() for role, tag in tags.items()})
    for can_id in (0x100, 0x101, 0x104):
        for counter in (0, 99, 0xFFFFFFFF):
            out[f"mac.{can_id}.{counter}"] = data_mac(keys["data"], can_id, counter,
                                                      bytes.fromhex("96c81068ffec4100")).hex()
    receipt = state_receipt_tag(keys, context, 7, bytes.fromhex("0201020000000000"))
    out["state.raw"] = "260:0201020000000000"
    out["state.auth"] = "261:" + data_mac(keys["data"], 0x104, 7, bytes.fromhex("0201020000000000")).hex() + "00000007"
    out["tag.receipt"] = receipt.hex()
    bodies = (bytes(4), context.nonce_b, context.nonce_a + tags["offer"],
              tags["confirm"], tags["ack"], tags["ready"], b"\0\0\0\x07" + receipt)
    for kind, body in enumerate(bodies):
        for index, (can_id, frame) in enumerate(fragment(kind, 0 if kind == 0 else context.transfer_id, body)):
            out[f"frame.{kind}.{index}"] = f"{can_id}:{frame.hex()}"
    return out


def test_independent_python_reference_matches_frozen_dummy_vectors():
    expected = dict(line.split("\t") for line in FIXTURE.read_text().splitlines())
    assert dummy_vectors() == expected


def test_reference_hkdf_against_rfc5869_case1_first_32_bytes():
    # RFC5869 Appendix A.1 with L=32: the first block of its L=42 output.
    assert _derive32(bytes.fromhex("0b" * 22), bytes(range(13)), bytes(range(0xF0, 0xFA))).hex() == (
        "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf")


@pytest.mark.parametrize("role", ("offer", "confirm", "ack", "ready"))
def test_role_tags_bind_transcript_and_reject_all_single_bit_mutations(role):
    ctx = SessionContext(0x1234, b"B" * 16, b"A" * 16)
    keys = derive_keys(bytes(range(32)), ctx)
    tag = control_tag(keys, ctx, role)
    assert tag_matches(tag, tag)
    assert not tag_matches(tag, tag[:-1])
    for bit in range(128):
        mutated = bytearray(tag)
        mutated[bit // 8] ^= 1 << (bit % 8)
        assert not tag_matches(tag, bytes(mutated))
    assert not tag_matches(tag, control_tag(keys, SessionContext(0x1235, ctx.nonce_b, ctx.nonce_a), role))
    assert not tag_matches(tag, control_tag(keys, SessionContext(ctx.transfer_id, b"C" * 16, ctx.nonce_a), role))
    old = SessionContext(ctx.transfer_id, ctx.nonce_b, b"C" * 16)
    assert not tag_matches(tag, control_tag(derive_keys(bytes(range(32)), old), old, role))


def test_receipt_requires_exact_current_state_and_counter():
    ctx = SessionContext(1, b"B" * 16, b"A" * 16)
    keys = derive_keys(bytes(range(32)), ctx)
    payload = bytes.fromhex("0201020000000000")
    expected = state_receipt_tag(keys, ctx, 7, payload)
    assert expected != state_receipt_tag(keys, ctx, 8, payload)
    assert expected != state_receipt_tag(keys, ctx, 7, bytes(8))
    assert expected != control_tag(keys, ctx, "ready")
    for invalid in ("data", "state-receipt", "unknown"):
        with pytest.raises(ValueError):
            control_tag(keys, ctx, invalid)


@pytest.mark.parametrize("ctx", (SessionContext(-1, bytes(16), bytes(16)),
                                  SessionContext(65536, bytes(16), bytes(16)),
                                  SessionContext(1, bytes(15), bytes(16)),
                                  SessionContext(1, bytes(16), bytes(17))))
def test_invalid_context_rejected(ctx):
    with pytest.raises(ValueError):
        derive_keys(bytes(32), ctx)


def test_invalid_key_frame_counter_and_request_rejected():
    with pytest.raises(ValueError):
        derive_keys(bytes(31), SessionContext(1, bytes(16), bytes(16)))
    for key, can_id, counter, payload in ((bytes(31), 0x100, 0, bytes(8)),
                                        (bytes(32), 0x800, 0, bytes(8)),
                                        (bytes(32), 0x100, -1, bytes(8)),
                                        (bytes(32), 0x100, 0x100000000, bytes(8)),
                                        (bytes(32), 0x100, 0, bytes(7))):
        with pytest.raises(ValueError):
            data_mac(key, can_id, counter, payload)
    for kind, transfer, body in ((7, 0, bytes(4)), (0, 1, bytes(4)),
                                  (0, 0, bytes([1, 0, 0, 0])), (2, 1, bytes(31))):
        with pytest.raises(ValueError):
            fragment(kind, transfer, body)
