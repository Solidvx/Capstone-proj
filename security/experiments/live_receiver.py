"""Reference receiver for the live (vcan / physical CAN) ablation.

Mirrors the Node B product rules in ivi_platform/service/vehicle_data_service.cpp
and ivi_platform/hal/can_parser.cpp so a harness on the bus can observe what a
receiver with each defence configuration would accept:

- 0x100 / 0x101 are range-parsed, then held as *pending* for 100 ms (ICD 2.3).
- 0x102 / 0x103 verify HMAC-SHA256[:4] over CAN_ID(2)||counter(4)||payload(8)
  against the pending original; counter window 1..100 per original CAN ID; a
  rejected auth does not consume the counter or clear the pending original.
- A newer original replaces the pending one (PENDING_REPLACED, not a rejection).
- SecOC OFF (Config 1): a parse-valid original is published immediately.

Each published or rejected item carries the *origin* of the frame(s) involved
(own = injected by this harness, otherwise genuine bus traffic), so the trial
judge can attribute acceptance and authentication rejection to the attack.
This is an observation model, not the product receiver; the IVI log is the
product evidence (EXQ-8 B).
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import struct

PENDING_TIMEOUT_S = 0.100
COUNTER_WINDOW = 100
AUTH_FOR = {0x102: 0x100, 0x103: 0x101}
ORIGINALS = (0x100, 0x101)
IDS_ALERT_ID = 0x200


def parse_bms_ok(data: bytes) -> bool:
    return len(data) == 8 and data[0] <= 200 and data[1] <= 200 and data[6] <= 165 and data[7] == 0


def parse_failsafe_ok(data: bytes) -> bool:
    return (len(data) == 8 and data[0] <= 3 and data[1] <= 3 and data[2] <= 7 and data[3] <= 200
            and data[4] <= 165 and data[5] == 0 and data[6] == 0 and data[7] == 0)


@dataclass(frozen=True)
class Outcome:
    """One receiver decision. kind: PUBLISHED | REJECTED | PARSE_REJECTED | PENDING | IGNORED | ALERT."""
    kind: str
    can_id: int                 # original ID for auth results, else the frame ID
    reason: str = ""
    own: bool = False           # the frame/pending that this outcome is about was injected
    auth_own: bool = False      # the auth frame (0x102/0x103) itself was injected
    payload: bytes = b""
    original_t: float | None = None


class _Pending:
    __slots__ = ("data", "t", "own")

    def __init__(self, data: bytes, t: float, own: bool):
        self.data, self.t, self.own = data, t, own


class ReferenceReceiver:
    def __init__(self, secoc_on: bool, key: bytes | None = None):
        if secoc_on and (key is None or len(key) != 32):
            raise ValueError("SecOC ON needs a 32-byte key")
        self.secoc_on = secoc_on
        self.key = key
        self.pending: dict[int, _Pending] = {}
        self.last_counter: dict[int, int] = {}

    def _expire(self, original_id: int, now: float) -> list[Outcome]:
        pending = self.pending.get(original_id)
        if pending is None or now < pending.t or now - pending.t < PENDING_TIMEOUT_S:
            return []
        del self.pending[original_id]
        return [Outcome("REJECTED", original_id, "AUTH_TIMEOUT", own=pending.own, payload=pending.data)]

    def poll(self, now: float) -> list[Outcome]:
        out: list[Outcome] = []
        for original_id in ORIGINALS:
            out.extend(self._expire(original_id, now))
        return out

    def process(self, t: float, can_id: int, data: bytes, own: bool = False,
                dlc: int | None = None, extended: bool = False,
                remote: bool = False, error: bool = False) -> list[Outcome]:
        if extended or remote or error or not 0 <= can_id <= 0x7ff:
            return [Outcome("PARSE_REJECTED", can_id, "FRAME_FORMAT", own=own)]
        if (dlc if dlc is not None else len(data)) != 8 or len(data) != 8:
            return [Outcome("PARSE_REJECTED", can_id, "DLC", own=own)]
        if can_id == IDS_ALERT_ID:
            return [Outcome("ALERT", can_id, own=own, payload=data)]
        if can_id in ORIGINALS:
            ok = parse_bms_ok(data) if can_id == 0x100 else parse_failsafe_ok(data)
            if not ok:
                return [Outcome("PARSE_REJECTED", can_id, "RANGE", own=own, payload=data)]
            if not self.secoc_on:
                return [Outcome("PUBLISHED", can_id, "NO_SECOC", own=own, payload=data, original_t=t)]
            out = self._expire(can_id, t)
            if can_id in self.pending:
                out.append(Outcome("PENDING", can_id, "PENDING_REPLACED", own=self.pending[can_id].own))
            self.pending[can_id] = _Pending(data, t, own)
            return out + [Outcome("PENDING", can_id, "PENDING_AUTH", own=own)]
        if can_id in AUTH_FOR:
            if not self.secoc_on:
                return [Outcome("IGNORED", can_id, "NO_SECOC", own=own)]
            return self._auth(t, AUTH_FOR[can_id], data, own)
        return [Outcome("IGNORED", can_id, "UNSUPPORTED_ID", own=own)]

    def _auth(self, t: float, original_id: int, data: bytes, auth_own: bool) -> list[Outcome]:
        pending = self.pending.get(original_id)
        if pending is None:
            return [Outcome("REJECTED", original_id, "AUTH_ORPHAN", own=auth_own, auth_own=auth_own)]
        expired = self._expire(original_id, t)
        if expired:
            return expired
        counter = int.from_bytes(data[4:8], "big")
        last = self.last_counter.get(original_id)
        involved_own = pending.own or auth_own
        if last is not None:
            delta = (counter - last) & 0xFFFFFFFF
            if not 1 <= delta <= COUNTER_WINDOW:
                reason = ("COUNTER_REUSE" if delta == 0 else
                          "COUNTER_BACKWARD" if delta > 0x80000000 else "COUNTER_WINDOW")
                return [Outcome("REJECTED", original_id, reason, own=involved_own,
                                auth_own=auth_own, payload=pending.data)]
        expected = hmac.new(self.key, struct.pack(">HI", original_id, counter) + pending.data,
                            hashlib.sha256).digest()[:4]
        if not hmac.compare_digest(expected, data[:4]):
            return [Outcome("REJECTED", original_id, "MAC_FAIL", own=involved_own,
                            auth_own=auth_own, payload=pending.data)]
        self.last_counter[original_id] = counter
        del self.pending[original_id]
        return [Outcome("PUBLISHED", original_id, "AUTHENTICATED", own=pending.own,
                        auth_own=auth_own, payload=pending.data, original_t=pending.t)]
