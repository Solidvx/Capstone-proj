from __future__ import annotations

import hmac
import hashlib
from dataclasses import dataclass
from pathlib import Path


KEY_SIZE = 32


@dataclass(frozen=True)
class AuthFrame:
    can_id: int
    data: bytes


class SecOcModule:
    """RollingCounter is independent per authenticated stream (ICD 1.4/2.4):
    0x102 (for 0x100) and 0x103 (for 0x101) never share a counter."""

    def __init__(self, key: bytes | None = None) -> None:
        self.key = key or b""
        self.counters: dict[int, int] = {}       # auth CAN ID -> next counter
        self.last_verified: dict[int, int] = {}  # original CAN ID -> last accepted

    @classmethod
    def from_key_file(cls, path: str | Path) -> "SecOcModule":
        key = Path(path).read_bytes()
        if len(key) != KEY_SIZE:
            raise ValueError("SecOC key must be 32 bytes")
        return cls(key)

    def sign(self, auth_can_id: int, original_can_id: int, payload: bytes) -> AuthFrame:
        self._require_key()
        if len(payload) != 8:
            raise ValueError("SecOC payload must be 8 bytes")

        rolling_counter = self.counters.get(auth_can_id, 0)
        self.counters[auth_can_id] = (rolling_counter + 1) & 0xFFFFFFFF
        mac = self._mac(original_can_id, rolling_counter, payload)
        return AuthFrame(auth_can_id, mac + rolling_counter.to_bytes(4, "big"))

    def verify(self, original_can_id: int, payload: bytes, auth_data: bytes) -> bool:
        self._require_key()
        if len(payload) != 8 or len(auth_data) != 8:
            return False

        rolling_counter = int.from_bytes(auth_data[4:8], "big")
        last = self.last_verified.get(original_can_id)
        if last is not None:
            delta = (rolling_counter - last) & 0xFFFFFFFF
            if delta == 0 or delta > 100:
                return False

        expected = self._mac(original_can_id, rolling_counter, payload)
        if not hmac.compare_digest(expected, auth_data[:4]):
            return False

        self.last_verified[original_can_id] = rolling_counter
        return True

    def _mac(self, original_can_id: int, rolling_counter: int, payload: bytes) -> bytes:
        hmac_input = (
            original_can_id.to_bytes(2, "big")
            + rolling_counter.to_bytes(4, "big")
            + payload
        )
        return hmac.new(self.key, hmac_input, hashlib.sha256).digest()[:4]

    def _require_key(self) -> None:
        if len(self.key) != KEY_SIZE:
            raise ValueError("SecOC key must be 32 bytes")
