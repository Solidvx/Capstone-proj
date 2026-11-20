"""Local continuity accounting for diagnostic-v1 observation producers.

Times are local monotonic milliseconds. A missing sample is never evidence of
quiet traffic. The caller supplies actual capture coverage, not wall-clock age.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Continuity:
    healthy_span_ms: int
    quiet_span_ms: tuple
    ended_mask: int


class ObservationContinuity:
    """Track four independent conditions across complete observation windows."""

    def __init__(self):
        self._end = None
        self._healthy = 0
        self._quiet = [0] * 4
        self._active = 0

    def update(self, *, start_ms: int, end_ms: int, condition_mask: int,
               frames: int, dropped: int, healthy: bool) -> Continuity:
        values = (start_ms, end_ms, condition_mask, frames, dropped)
        if any(type(value) is not int for value in values):
            raise ValueError("observation values must be integers")
        if (start_ms < 0 or end_ms <= start_ms or condition_mask not in range(16)
                or frames < 0 or dropped < 0 or type(healthy) is not bool):
            raise ValueError("invalid observation interval or counters")
        if self._end is not None and start_ms < self._end:
            raise ValueError("overlapping or backward observation window")
        contiguous = self._end is None or start_ms == self._end
        self._end = end_ms
        duration = end_ms - start_ms
        valid = healthy and frames > 0 and dropped == 0
        if not contiguous or not valid:
            self._healthy = 0
            self._quiet = [0] * 4
        # An observed condition remains active across uncertainty; only a
        # continuous measured quiet interval may end it.
        self._active |= condition_mask
        ended = 0
        if valid:
            self._healthy += duration
            for index in range(4):
                bit = 1 << index
                if condition_mask & bit:
                    self._quiet[index] = 0
                elif self._active & bit:
                    self._quiet[index] += duration
                    if self._quiet[index] >= 5000:
                        ended |= bit
                        self._active &= ~bit
        return Continuity(self._healthy, tuple(self._quiet), ended)
