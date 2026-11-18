"""Bounded observation of physical CAN messages. Assembly alone proves no MAC."""
from dataclasses import dataclass
import math

from security.can_diagnostic import LENGTHS


@dataclass(frozen=True)
class Message:
    frames: tuple
    content: bytes
    protected: bool
    started: float
    completed: float

    @property
    def kind(self):
        return self.content[20] if self.protected else 9

    @property
    def body(self):
        return self.content[22:-16] if self.protected else self.content


class Assembler:
    def __init__(self, protected, timeout=1.0, capacity=4):
        if not math.isfinite(timeout) or timeout <= 0 or not 1 <= capacity <= 8:
            raise ValueError("invalid physical assembly limits")
        self.protected = protected
        self.timeout = timeout
        self.capacity = capacity
        self.pending = {}
        self.now = None
        self.dropped = 0

    def observe(self, frame):
        if not math.isfinite(frame.t) or (self.now is not None and frame.t < self.now):
            raise ValueError("physical observation clock moved backward")
        self.now = frame.t
        expired = [key for key, entry in self.pending.items() if frame.t-entry[0] >= self.timeout]
        for key in expired:
            del self.pending[key]
            self.dropped += 1
        data = frame.data
        marker = 0xd1 if self.protected else 0xd0
        if (frame.can_id != 0x302 or frame.dlc != 8 or len(data) != 8 or
                frame.extended or frame.remote or frame.error or data[0] != marker):
            return None
        index = data[1]
        if index >= (36 if self.protected else 20):
            return None
        transfer = data[2:4]
        if transfer not in self.pending:
            if (not self.protected and index != 0) or len(self.pending) >= self.capacity:
                self.dropped += 1
                return None
            self.pending[transfer] = (frame.t, {})
        started, chunks = self.pending[transfer]
        if index in chunks and chunks[index] != data:
            del self.pending[transfer]
            self.dropped += 1
            return None
        if not self.protected and index != len(chunks):
            del self.pending[transfer]
            self.dropped += 1
            return None
        chunks[index] = data
        length = 80
        if self.protected:
            if 5 not in chunks:
                return None
            kind, body_length = chunks[5][4:6]
            if kind not in LENGTHS or body_length != LENGTHS[kind]:
                del self.pending[transfer]
                self.dropped += 1
                return None
            length = 38 + body_length
        count = (length + 3) // 4
        if any(part >= count for part in chunks):
            del self.pending[transfer]
            self.dropped += 1
            return None
        if len(chunks) != count:
            return None
        del self.pending[transfer]
        padded = b"".join(chunks[i][4:] for i in range(count))
        if any(padded[length:]):
            self.dropped += 1
            return None
        return Message(tuple((0x302, chunks[i]) for i in range(count)), padded[:length],
                       self.protected, started, frame.t)
