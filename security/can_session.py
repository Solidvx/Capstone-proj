"""Approved session-v2 independent Python crypto reference.

The transcript/roles follow docs/ICD-CAN-SESSION.md. The separate legacy-v1
profile is unchanged; this module does not run a CAN client.
"""
from __future__ import annotations

import hmac
import hashlib
from dataclasses import dataclass


ROLES = ("offer", "confirm", "ack", "data", "ready", "state-receipt", "diag-ecu", "diag-ivi")


def _derive32(key: bytes, salt: bytes, info: bytes) -> bytes:
    prk = hmac.digest(salt, key, "sha256")
    return hmac.digest(prk, info + b"\x01", "sha256")


@dataclass(frozen=True)
class SessionContext:
    transfer_id: int
    nonce_b: bytes
    nonce_a: bytes

    def transcript(self) -> bytes:
        if not 0 <= self.transfer_id <= 0xFFFF:
            raise ValueError("session transfer ID range")
        if len(self.nonce_b) != 16 or len(self.nonce_a) != 16:
            raise ValueError("session nonces must each be 16 bytes")
        return (b"CAPSTONE-CAN-SESSION\x02\x03\x00\x03\x01"
                + self.transfer_id.to_bytes(2, "big") + self.nonce_b + self.nonce_a)


def derive_keys(shared_key: bytes, context: SessionContext) -> dict[str, bytes]:
    if len(shared_key) != 32:
        raise ValueError("session shared key must be 32 bytes")
    transcript = context.transcript()
    # All candidate role outputs are one SHA-256 block (L=32).
    return {role: _derive32(shared_key, context.nonce_b + context.nonce_a,
                            role.encode("ascii") + transcript)
            for role in ROLES}


def control_tag(keys: dict[str, bytes], context: SessionContext, role: str) -> bytes:
    if role not in ("offer", "confirm", "ack", "ready"):
        raise ValueError("control role required")
    return hmac.digest(keys[role], context.transcript(), "sha256")[:16]


def _data_input(can_id: int, counter: int, payload: bytes) -> bytes:
    if not 0 <= can_id <= 0x7FF or not 0 <= counter <= 0xFFFFFFFF or len(payload) != 8:
        raise ValueError("standard CAN ID, uint32 counter and 8-byte payload required")
    return can_id.to_bytes(2, "big") + counter.to_bytes(4, "big") + payload


def data_mac(key: bytes, can_id: int, counter: int, payload: bytes) -> bytes:
    if len(key) != 32:
        raise ValueError("data key must be 32 bytes")
    return hmac.digest(key, _data_input(can_id, counter, payload), "sha256")[:4]


def state_receipt_tag(keys: dict[str, bytes], context: SessionContext,
                      counter: int, payload: bytes) -> bytes:
    body = context.transcript() + _data_input(0x104, counter, payload)
    return hmac.digest(keys["state-receipt"], body, "sha256")[:16]


def tag_matches(expected: bytes, received: bytes) -> bool:
    return len(expected) == len(received) and hmac.compare_digest(expected, received)


def fragment(kind: int, transfer_id: int, body: bytes) -> list[tuple[int, bytes]]:
    lengths = (4, 16, 32, 16, 16, 16, 20)
    if kind not in range(7) or not 0 <= transfer_id <= 0xFFFF or len(body) != lengths[kind]:
        raise ValueError("session frame kind, transfer or body length")
    if kind == 0 and (transfer_id != 0 or body != bytes(4)):
        raise ValueError("REQUEST must use zero transfer and body")
    can_id = 0x300 if kind in (0, 2, 4) else 0x301
    return [(can_id, bytes((0x20 | kind, i // 4)) + transfer_id.to_bytes(2, "big") + body[i:i+4])
            for i in range(0, len(body), 4)]


def context_id(context: SessionContext) -> bytes:
    return hashlib.sha256(context.transcript()).digest()[:16]


def diagnostic_tag(keys: dict[str, bytes], sender_id: int, envelope: bytes) -> bytes:
    if sender_id not in (0x302, 0x303) or not 22 <= len(envelope) <= 126:
        raise ValueError("diagnostic direction or envelope size")
    role = "diag-ecu" if sender_id == 0x302 else "diag-ivi"
    return hmac.digest(keys[role], b"CAPSTONE-CAN-DIAG\x01" + sender_id.to_bytes(2, "big") + envelope,
                       "sha256")[:16]
