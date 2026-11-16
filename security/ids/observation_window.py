"""Bounded live runtime observation windows; no keys and no CAN transmission."""
from .observation_status import ObservationStatus


class ObservationWindow:
    def __init__(self, started_ms, *, detector_revision=3):
        self.status = ObservationStatus(started_ms=started_ms, detector_revision=detector_revision)
        self.start = started_ms
        self.previous = started_ms
        self.frames = 0
        self.mask = 0
        self.last_drops = 0
        self.stale_input = False
        self.external_reason = 0
        self.unknown_drops = False
        self.candidates = {}
        self.last_evidence = {}

    def observe(self, now_ms, *, frame_present, events, total_drops, processed_ms=None, unavailable_reason=0, unknown_drops=False):
        if type(now_ms) is not int or now_ms < self.previous:
            raise ValueError('observation clock moved backward')
        if type(total_drops) is not int or total_drops < self.last_drops:
            raise ValueError('drop total moved backward')
        if processed_ms is not None:
            if type(processed_ms) is not int or processed_ms < now_ms:
                raise ValueError('invalid observation processing time')
            self.stale_input |= processed_ms-now_ms >= 3000
        if type(unavailable_reason) is not int or unavailable_reason not in range(7):
            raise ValueError("invalid observation availability reason")
        self.external_reason = self.external_reason or unavailable_reason
        if type(unknown_drops) is not bool:raise ValueError("unknown_drops must be bool")
        self.unknown_drops |= unknown_drops
        self.previous = now_ms
        self.frames += int(frame_present)
        for event in events:
            if event.attack_type in (1, 2, 3, 4):
                self.mask |= 1 << (event.attack_type-1)
                count,reference,bits=self.candidates.get(event.attack_type,(0,'',0))
                self.candidates[event.attack_type]=(min(count+1,2),getattr(event,'reference_hex',''),getattr(event,'evidence_bits',0))
        if now_ms-self.start < 1000:
            return None
        # Delayed producer updates cannot claim continuous timely coverage.
        body, state = self.status.update(
            start_ms=self.start, end_ms=now_ms, frames=self.frames,
            dropped=None if self.unknown_drops else total_drops-self.last_drops, condition_mask=self.mask,
            reason=2 if self.stale_input or now_ms-self.start >= 3000 else self.external_reason)
        self.last_evidence={attack:(reference,bits) for attack,(count,reference,bits) in self.candidates.items()
                            if count==1 and len(reference)==88 and body[16]==1}
        self.candidates={}
        self.start = now_ms
        self.frames = self.mask = 0
        self.stale_input = False
        self.external_reason = 0
        self.unknown_drops = False
        self.last_drops = total_drops
        return body, state
