"""Independent diagnostic-v1 candidate reference, not an active CAN service."""
from __future__ import annotations

import hmac

from security.can_session import SessionContext, context_id, diagnostic_tag

LENGTHS = {1: 56, 2: 56, 3: 40, 4: 104, 5: 80, 6: 52, 7: 52, 8: 56, 9: 80}


def _u(body: bytes, at: int, size: int = 4) -> int:
    return int.from_bytes(body[at:at+size], "big")


def _zero(body: bytes, at: int, size: int) -> bool:
    return body[at:at+size] == bytes(size)


def _uuid(body: bytes, at: int) -> bool:
    return body[at+6] >> 4 == 4 and body[at+8] >> 6 == 2


def _reference(body: bytes, at: int) -> bool:
    ref = body[at:at+44]
    if ref[0] == 0:
        return ref == bytes(44)
    if ref[0] not in (1, 2) or ref[3] != 0 or ref[1] > 8:
        return False
    if ref[0] == 1:
        return ref[2] == 0 and _zero(ref, 8, 4) and _zero(ref, 36, 8) and _zero(ref, 28+ref[1], 8-ref[1])
    return ref[1] == ref[2] == 8 and not _zero(ref, 12, 16) and (_u(ref, 4), _u(ref, 8)) in ((0x100, 0x102), (0x101, 0x103), (0x104, 0x105))


def _state(state: int, present: int, reason: int) -> bool:
    if state not in range(4) or present not in (0, 1):
        return False
    return reason == 0 if not present else reason in ((5, 6), (1, 3, 7), (2,), (4,))[state]


def valid_body(sender: int, kind: int, b: bytes) -> bool:
    if sender not in (0x302, 0x303) or kind not in LENGTHS or len(b) != LENGTHS[kind]:
        return False
    if kind != 6 and kind not in ((1, 2, 4, 7, 8, 9) if sender == 0x302 else (3, 5)):
        return False
    if kind == 9:
        flags = b[65]
        if (not _uuid(b, 0) or _zero(b, 16, 16) or b[64] != 1 or flags > 31
                or b[66] > 2 or b[67] > 2 or b[68] not in range(1, 7)
                or b[69] not in range(1, 7) or b[70] > 1 or b[71]
                or not _u(b, 72) or not 1 <= _u(b, 76) <= 60000):
            return False
        if (flags & 3 not in (0, 3) or bool(flags & 3) != (b[68] == 2)
                or bool(flags & 4) != (b[69] == 2)
                or (flags & 8 and (not flags & 3 or b[66] not in (1, 2)))
                or bool(flags & 16) != (b[67] != 0)
                or (flags & 3 and _u(b, 56) == 0xFFFFFFFF)
                or (flags & 4 and _u(b, 60) == 0xFFFFFFFF)):
            return False
        if not _u(b, 32, 8) and (flags & 15 or b[68] not in (1, 3) or b[69] not in (1, 3)
                                or _u(b, 56) != 0xFFFFFFFF or _u(b, 60) != 0xFFFFFFFF):
            return False
        for i in range(5):
            at, size = (40 + i*4, 4) if i < 3 else (52 + (i-3)*2, 2)
            raw = _u(b, at, size)
            if not flags & (1 << i):
                if raw:
                    return False
                continue
            value = int.from_bytes(b[at:at+size], "big", signed=i < 3)
            if not ((0 <= value <= 26000000) if i == 0 else
                    (abs(value) <= 2147000000) if i == 1 else
                    (-55000 <= value <= 125000) if i == 2 else value <= 10000):
                return False
        return True
    if kind == 1:
        if (not _uuid(b, 0) or not (_zero(b, 16, 16) or _uuid(b, 16)) or b[32] not in range(1, 6)
                or b[33] not in (1, 2) or b[34] not in range(1, 7) or b[38] > 3 or b[39] or b[55]
                or any(b[i] > 1 for i in (52, 53, 54))):
            return False
        if b[35] == 255:
            if b[36] or b[37] or b[54]:
                return False
        elif not _state(b[35], b[36], b[37]):
            return False
        if b[33] == 1 and (b[52] or b[54]):
            return False
        if b[33] == 2 and b[32] == 2 and not (b[52] and b[54]):
            return False
        if b[53] and b[34] != 2:
            return False
        return not b[52] or _u(b, 48) != 0xFFFFFFFF
    if kind == 2:
        if (not _uuid(b, 0) or not _uuid(b, 16) or not (_zero(b, 32, 16) or _uuid(b, 32))
                or b[48] not in (1, 2, 3) or b[50] not in (1, 2, 3) or b[51] or not _u(b, 52)):
            return False
        if b[48] == 1 and (not _uuid(b, 32) or b[50] != 1):
            return False
        return b[49] == (1 if b[48] == 2 else 2)
    if kind == 3:
        return _uuid(b, 0) and _uuid(b, 16) and b[32] == 1 and _zero(b, 33, 3)
    if kind == 4:
        if (not _uuid(b, 0) or not _uuid(b, 16) or b[32] not in range(1, 5) or b[33] not in (1, 2, 3)
                or not _u(b, 34, 2) or not _u(b, 36) or not _u(b, 40) or _u(b, 58, 2) > 31
                or (_u(b, 56, 2) > 0x7FF and _u(b, 56, 2) != 0xFFFF) or not _reference(b, 60)):
            return False
        if b[33] == 1 and (not _u(b, 44) or not _u(b, 48) or _u(b, 48) == 0xFFFFFFFF or _u(b, 52)):
            return False
        if b[33] == 2 and (not _u(b, 44) or _u(b, 48) == 0xFFFFFFFF or _u(b, 52) < 5000):
            return False
        if b[33] == 3 and (_u(b, 52) or (not _u(b, 44) and _u(b, 48) != 0xFFFFFFFF)):
            return False
        return b[60] != 2 or _u(b, 56, 2) == 0xFFFF or _u(b, 56, 2) == _u(b, 64)
    if kind == 5:
        if not _uuid(b, 0) or not _uuid(b, 16) or b[32] not in range(1, 16) or b[33] > 1 or b[35] or not _reference(b, 36):
            return False
        treatment = 4 if b[32] in (4, 5) else 2 if b[32] == 6 else 3 if b[32] == 9 else 5 if b[32] in (12, 13, 14) else 1
        verified = 7 <= b[32] <= 13
        return b[34] == treatment and b[33] == int(verified) and (not verified or b[36] == 2)
    if kind == 6:
        if not _uuid(b, 0) or not _u(b, 16):
            return False
        mask = _u(b, 48)
        if not mask & 1 or mask > 127:
            return False
        if any(bool(mask & (1 << i)) == (_u(b, 20+i*4) == 0xFFFFFFFF) for i in range(7)):
            return False
        if mask & 2 and _u(b, 24) > _u(b, 20):
            return False
        return mask & 24 != 24 or _u(b, 32) <= _u(b, 36)
    if kind == 8:
        if (not _uuid(b, 0) or not _uuid(b, 16) or b[50] > 2 or b[51] > 1
                or not _state(b[48], int(b[49] != 0), b[49])):
            return False
        if b[50] == 0:
            return _zero(b, 32, 16) and _u(b, 52) == 0 and b[48] == b[49] == 0
        return (_uuid(b, 32) and _u(b, 52) != 0
                and (b[48] != 0 if b[50] == 1 else b[48] == 0))
    if (not _uuid(b, 0) or b[16] not in (1, 2, 3) or b[17] > 6 or not _zero(b, 18, 2)
            or not _u(b, 20) or b[48] > 15 or not _u(b, 49, 2) or b[51]):
        return False
    if b[16] == 1:
        return b[17] == 0 and _u(b, 32) > 0 and 0 < _u(b, 36) < 0xFFFFFFFF and _u(b, 40) == 0 and _u(b, 44) >= _u(b, 32)
    return b[17] != 0 and _u(b, 44) == 0 and (_u(b, 32) != 0 or _u(b, 36) == 0xFFFFFFFF)


def encode(keys: dict[str, bytes], context: SessionContext, sender: int,
           sequence: int, kind: int, body: bytes) -> list[tuple[int, bytes]]:
    if not 0 <= sequence <= 0xFFFFFFFF or not valid_body(sender, kind, body):
        raise ValueError("diagnostic sequence, direction or body")
    unsigned = context_id(context) + sequence.to_bytes(4, "big") + bytes((kind, len(body))) + body
    envelope = unsigned + diagnostic_tag(keys, sender, unsigned)
    padded = envelope + bytes((-len(envelope)) % 4)
    transfer = (sequence & 0xFFFF).to_bytes(2, "big")
    return [(sender, b"\xD1" + bytes((i // 4,)) + transfer + padded[i:i+4])
            for i in range(0, len(padded), 4)]


def decode(keys: dict[str, bytes], context: SessionContext, sender: int,
           frames: list[tuple[int, bytes]]) -> tuple[int, int, bytes]:
    """Pure full-message reference; streaming limits/replay are C++ tests."""
    chunks = {}
    transfer = None
    for can_id, data in frames:
        if can_id != sender or len(data) != 8 or data[0] != 0xD1 or data[1] >= 36:
            raise ValueError("diagnostic frame")
        if transfer is None:
            transfer = data[2:4]
        if data[2:4] != transfer or (data[1] in chunks and chunks[data[1]] != data[4:]):
            raise ValueError("mixed diagnostic message")
        chunks[data[1]] = data[4:]
    if 5 not in chunks:
        raise ValueError("missing diagnostic header")
    kind, length = chunks[5][:2]
    if kind not in LENGTHS or length != LENGTHS[kind]:
        raise ValueError("diagnostic type/length")
    count = (38 + length + 3) // 4
    if set(chunks) != set(range(count)):
        raise ValueError("missing/extra diagnostic fragment")
    padded = b"".join(chunks[i] for i in range(count))
    total = 38 + length
    if any(padded[total:]):
        raise ValueError("nonzero diagnostic padding")
    envelope = padded[:total]
    sequence = int.from_bytes(envelope[16:20], "big")
    body = envelope[22:-16]
    if envelope[:16] != context_id(context) or (sequence & 0xFFFF).to_bytes(2, "big") != transfer:
        raise ValueError("diagnostic session/sequence")
    if not valid_body(sender, kind, body) or not hmac.compare_digest(diagnostic_tag(keys, sender, envelope[:-16]), envelope[-16:]):
        raise ValueError("diagnostic body/authentication")
    return sequence, kind, body
