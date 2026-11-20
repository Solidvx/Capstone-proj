"""Encode measured IDS observation health for the approved diagnostic contract.

This produces a body only. The ECU-owned authenticated CAN publisher supplies
session identity, message sequence and authentication; this module holds no key.
"""
import struct
import uuid
from security.can_diagnostic import valid_body
from .observation_continuity import ObservationContinuity


class ObservationStatus:
    def __init__(self, source_instance=None, *, started_ms=0, detector_revision=3):
        if type(started_ms) is not int or started_ms < 0:
            raise ValueError("invalid process start time")
        if type(detector_revision) is not int or not 1<=detector_revision<=65535:
            raise ValueError("invalid detector revision")
        self.detector_revision=detector_revision
        self.started_ms = started_ms
        self.source = source_instance or uuid.uuid4()
        if not isinstance(self.source, uuid.UUID) or self.source.version != 4:
            raise ValueError('source instance must be UUIDv4')
        self.tick = 0
        self.continuity = ObservationContinuity()

    def update(self, *, start_ms, end_ms, frames, dropped, condition_mask,
               reason=0):
        # reason is the actual producer health reason defined by the ICD.
        values = (start_ms, end_ms, frames, condition_mask, reason)
        if any(type(value) is not int for value in values):
            raise ValueError('integer observation fields required')
        if (not self.started_ms <= start_ms < end_ms <= 0xFFFFFFFFFFFFFFFF
                or end_ms-start_ms > 0xFFFFFFFF or not 0 <= frames < 0xFFFFFFFF
                or not (dropped is None or type(dropped) is int and 0 <= dropped < 0xFFFFFFFF) or condition_mask not in range(16)
                or reason not in range(7)):
            raise ValueError('invalid observation fields')
        if self.tick == 0xFFFFFFFF:
            raise OverflowError('new source instance required before tick reuse')
        effective_reason = reason or (3 if dropped is None else 1 if dropped else 2 if not frames else 0)
        continuity = self.continuity.update(
            start_ms=start_ms, end_ms=end_ms, frames=frames, dropped=dropped or 0,
            condition_mask=condition_mask, healthy=effective_reason == 0)
        self.tick += 1
        body = (self.source.bytes + bytes((1 if effective_reason == 0 else 2,
                                          effective_reason, 0, 0))
                + struct.pack('>IQIIII', self.tick, end_ms-self.started_ms, end_ms-start_ms,
                              frames, 0xFFFFFFFF if dropped is None else dropped, min(continuity.healthy_span_ms, 0xFFFFFFFF))
                + bytes((condition_mask,)) + struct.pack('>H', self.detector_revision) + b'\0')
        if not valid_body(0x302, 7, body):
            raise RuntimeError('observation body violates diagnostic contract')
        return body, continuity
