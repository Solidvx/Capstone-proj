"""Type-specific incident identities derived from measured observation windows."""
import struct
import uuid
from security.can_diagnostic import valid_body


class IncidentStatus:
    def __init__(self):
        self.source = None
        self.tick = 0
        self.incidents = {}

    def update(self, observation, continuity, references=None):
        if not valid_body(0x302, 7, observation):
            raise ValueError('invalid observation body')
        source = observation[:16]
        tick = int.from_bytes(observation[20:24], 'big')
        if self.source is not None and source != self.source:
            raise ValueError('new producer requires a new incident tracker')
        if tick <= self.tick:
            raise ValueError('old observation tick')
        self.source, self.tick = source, tick
        healthy = observation[16] == 1
        mask = observation[48]
        window = int.from_bytes(observation[32:36], 'big')
        frames = int.from_bytes(observation[36:40], 'big')
        output = []
        for attack in range(1, 5):
            bit = 1 << (attack-1)
            if mask & bit and attack not in self.incidents:
                self.incidents[attack] = [uuid.uuid4().bytes, 0]
            if attack not in self.incidents:
                continue
            if not healthy:
                state, quiet = 3, 0
            elif mask & bit:
                state, quiet = 1, 0
            elif continuity.ended_mask & bit:
                state, quiet = 2, continuity.quiet_span_ms[attack-1]
            else:
                # Healthy heartbeat carries the quiet interval; do not claim
                # either an ongoing condition or a completed incident yet.
                continue
            identity, revision = self.incidents[attack]
            if revision == 0xFFFFFFFF:
                raise OverflowError('incident revision exhausted')
            revision += 1
            reference=bytes(44);suspect=0xffff;evidence=0
            candidate=(references or {}).get(attack) if state==1 else None
            if candidate:
                encoded,evidence=candidate
                reference=bytes.fromhex(encoded)
                if len(reference)!=44:raise ValueError('invalid candidate reference')
                suspect=int.from_bytes(reference[4:8],'big')
            body = (source + identity + bytes((attack, state)) + observation[49:51]
                    + struct.pack('>IIIIIHH', revision, tick, window, frames,
                                  quiet, suspect, evidence) + reference)
            if not valid_body(0x302, 4, body):
                raise ValueError('incident contradicts observation coverage')
            self.incidents[attack][1] = revision
            output.append(body)
            if state == 2:
                del self.incidents[attack]
        return output
