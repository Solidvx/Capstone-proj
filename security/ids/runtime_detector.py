"""Node A streaming IDS. Local reason codes do not alter ICD 0x200.

Thresholds are configurable engineering defaults, not measured detection guarantees.
SecOC here is an independent bus observation, never a claim about Node B's verifier.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import hmac
import math
import struct

from .feature_extractor import extract

KNOWN_IDS = frozenset((0x100, 0x101, 0x102, 0x103, 0x200))
AUTH_ORIGINAL = {0x102: 0x100, 0x103: 0x101}


@dataclass(frozen=True)
class Observation:
    t: float  # monotonic seconds; replay uses a relative monotonic clock
    can_id: int
    data: bytes
    dlc: int = 8
    extended: bool = False
    remote: bool = False
    error: bool = False


@dataclass(frozen=True)
class Event:
    timestamp: float
    can_id: int
    reason: str
    attack_type: int = 0  # 0: unattributed diagnostic, never transmit a clearing alert
    anomaly_score: float = 1.0
    result: str = "ANOMALY"

    def alert_payload(self, epoch_seconds: int) -> bytes | None:
        if not self.attack_type:
            return None
        return struct.pack(">BBHI", self.attack_type,
                           max(0, min(255, round(self.anomaly_score * 100))),
                           self.can_id if 0 <= self.can_id <= 0x7ff else 0xffff,
                           epoch_seconds & 0xffffffff)


@dataclass(frozen=True)
class Config:
    missing_s: float = 0.300
    pending_s: float = 0.100
    min_period_s: float = 0.050
    max_frames_per_second: int = 100
    failure_repeat_count: int = 3
    max_soc_step: float = 20.0
    max_temperature_step: float = 20.0
    max_current_step: float = 100.0

    def __post_init__(self):
        for value in (self.missing_s, self.pending_s, self.min_period_s,
                      self.max_soc_step, self.max_temperature_step, self.max_current_step):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("IDS thresholds must be finite and positive")
        if not 1 <= self.max_frames_per_second <= 4096 or self.failure_repeat_count < 2:
            raise ValueError("invalid count thresholds")


class RuntimeDetector:
    def __init__(self, config: Config = Config(), key: bytes | None = None,
                 model=None, start_time: float = 0.0):
        if key is not None and len(key) != 32:
            raise ValueError("SecOC key must be exactly 32 bytes")
        if not math.isfinite(start_time):
            raise ValueError("start time must be finite")
        self.config, self.key, self.model = config, key, model
        self.now = self.started = start_time
        self.last_seen: dict[int, float] = {}
        self.missing: set[int] = set()
        self.pending: dict[int, Observation] = {}
        self.counters: dict[int, int] = {}
        self.last_bms: tuple[float, float, float] | None = None
        self.frames: deque[Observation] = deque(maxlen=4096)
        self.failures: deque[float] = deque(maxlen=4096)
        self.last_model_check = start_time
        self.rate_latched = False

    def _failure(self, now, cid, reason, attack_type=0):
        self.failures.append(now)
        while self.failures and now-self.failures[0] >= 1.0:
            self.failures.popleft()
        events = [Event(now, cid, reason, attack_type)]
        if len(self.failures) == self.config.failure_repeat_count:
            events.append(Event(now, cid, "SECOC_FAILURE_BURST"))
        return events

    def tick(self, now: float) -> list[Event]:
        if not math.isfinite(now) or now < self.now:
            raise ValueError("timestamps must be finite and nondecreasing")
        self.now = now
        events = []
        for cid in (0x100, 0x102):
            if now-self.last_seen.get(cid, self.started) >= self.config.missing_s and cid not in self.missing:
                self.missing.add(cid)
                events.append(Event(now, cid, "MESSAGE_MISSING"))
        for cid, original in list(self.pending.items()):
            if now-original.t >= self.config.pending_s:
                del self.pending[cid]
                events.extend(self._failure(now, cid, "AUTH_TIMEOUT"))
        while self.frames and now-self.frames[0].t >= 1.0:
            self.frames.popleft()
        if len(self.frames) < self.config.max_frames_per_second:
            self.rate_latched = False
        if self.model is not None and now-self.last_model_check >= 1.0:
            self.last_model_check = now
            if self.frames:
                features = extract(list(self.frames))
                if self.model.anomaly(features) > 0:
                    events.append(Event(now, 0xffff, "IF_ANOMALY", 0,
                                        self.model.wire_score(features)/100))
        return events

    def observe(self, frame: Observation) -> list[Event]:
        events = self.tick(frame.t)
        cid, data = frame.can_id, frame.data
        if frame.extended or frame.remote or frame.error or not 0 <= cid <= 0x7ff:
            return events + [Event(frame.t, cid, "FRAME_FORMAT", 1)]
        if cid not in KNOWN_IDS:
            events.append(Event(frame.t, cid, "UNKNOWN_ID", 1))
        if frame.dlc != 8 or len(data) != 8:
            return events + [Event(frame.t, cid, "DLC", 1)]
        # Do not learn/trigger on the IDS's own alert stream.
        if cid == 0x200:
            return events
        self.frames.append(frame)
        if len(self.frames) >= self.config.max_frames_per_second and not self.rate_latched:
            self.rate_latched = True
            events.append(Event(frame.t, cid, "FRAME_RATE", 4))
        if cid not in KNOWN_IDS:
            return events
        previous = self.last_seen.get(cid)
        self.last_seen[cid] = frame.t
        self.missing.discard(cid)
        if cid in (0x100, 0x102) and previous is not None and frame.t-previous < self.config.min_period_s:
            events.append(Event(frame.t, cid, "PERIOD_TOO_SHORT", 4))
        if cid == 0x100:
            if data[0] > 200 or data[1] > 200 or data[6] > 165 or data[7] != 0:
                return events + [Event(frame.t, cid, "BMS_RANGE", 3)]
            values = (data[0]*0.5, data[6]-40, int.from_bytes(data[4:6],"big",signed=True)*0.1)
            if self.last_bms is not None:
                limits=(self.config.max_soc_step,self.config.max_temperature_step,self.config.max_current_step)
                if any(abs(a-b)>limit for a,b,limit in zip(values,self.last_bms,limits)):
                    events.append(Event(frame.t,cid,"BMS_STEP",3))
            self.last_bms=values  # raw observation, not authenticated application state
        if cid == 0x101 and (data[0]>3 or data[1]>3 or not 1<=data[2]<=7 or data[3]>200 or data[4]>165 or any(data[5:])):
            return events + [Event(frame.t,cid,"FAILSAFE_RANGE",3)]
        if self.key is None:
            return events
        if cid in (0x100,0x101):
            if cid in self.pending:
                events.append(Event(frame.t,cid,"PENDING_REPLACED",result="DIAGNOSTIC"))
            self.pending[cid]=frame
        elif cid in AUTH_ORIGINAL:
            original_id=AUTH_ORIGINAL[cid]
            original=self.pending.get(original_id)
            if original is None:
                return events+self._failure(frame.t,original_id,"AUTH_ORPHAN")
            counter=int.from_bytes(data[4:],"big")
            last=self.counters.get(original_id)
            if last is not None:
                delta=(counter-last)&0xffffffff
                if not 1<=delta<=100:
                    reason="COUNTER_REUSE" if delta==0 else "COUNTER_BACKWARD" if delta>0x80000000 else "COUNTER_WINDOW"
                    return events+self._failure(frame.t,original_id,reason,2)
            expected=hmac.new(self.key,struct.pack(">HI",original_id,counter)+original.data,hashlib.sha256).digest()[:4]
            if not hmac.compare_digest(expected,data[:4]):
                return events+self._failure(frame.t,original_id,"MAC_FAIL",3)
            self.counters[original_id]=counter
            del self.pending[original_id]
        return events
