"""Executable design model only: no sockets, TLS, CAN, verifier or product imports.

Limits and identities come from synthetic fixtures, never deployment settings.
Run from any directory: python -B path/to/check_design.py
"""
import copy
import json
from pathlib import Path
import re
import unittest


FIXTURE = json.loads(Path(__file__).with_name('fixtures.json').read_text(encoding='utf-8'))
LIMITS = FIXTURE['limits']
REASONS = {
    'ACCEPTED': {'VERIFIED'},
    'REJECTED': {'MAC_MISMATCH', 'COUNTER_REJECT'},
    'NOT_EVALUATED': {'ORPHAN_AUTH', 'RAW_EXPIRED', 'RAW_REPLACED', 'FORMAT_INVALID', 'CONFIG_ERROR'},
    'BYPASSED': {'SECURITY_DISABLED'},
}


def uint64(value):
    if not isinstance(value, str) or not re.fullmatch(r'0|[1-9][0-9]{0,19}', value):
        raise ValueError('uint64 string')
    number = int(value)
    if number >= 2**64:
        raise ValueError('overflow')
    return number


def event_check(event):
    # Deliberately models a subset of proposed fields, not a complete wire schema.
    if type(event) is not dict or set(event) != set(FIXTURE['event']):
        raise ValueError('fields')
    if type(event['version']) is not int or event['version'] != 1 or event['kind'] != 'event':
        raise ValueError('version/kind')
    for key in ('node_id', 'producer_epoch', 'connection_id', 'decision', 'reason'):
        if not isinstance(event[key], str) or not 0 < len(event[key]) <= 64:
            raise ValueError('string')
    if event['reason'] not in REASONS.get(event['decision'], set()):
        raise ValueError('decision/reason')
    uint64(event['event_seq'])
    age = uint64(event['emit_mono_ns']) - uint64(event['event_mono_ns'])
    if not 0 <= age <= LIMITS['max_age']:
        raise ValueError('source age')
    return event['decision']


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def bad_constant(value):
    raise ValueError('nonfinite')


class Decoder:
    """Incremental length-bounded model; protocol errors require connection reset."""
    def __init__(self):
        self.buffer = bytearray()
        self.length = None
        self.failed = False

    def feed(self, chunk):
        if self.failed:
            raise ValueError('closed')
        output = []
        try:
            for byte in chunk:
                self.buffer.append(byte)
                if self.length is None and len(self.buffer) == 4:
                    self.length = int.from_bytes(self.buffer, 'big')
                    self.buffer.clear()
                    if not 0 < self.length <= LIMITS['max_body']:
                        raise ValueError('length')
                elif self.length is not None and len(self.buffer) == self.length:
                    obj = json.loads(self.buffer.decode('utf-8'), object_pairs_hook=pairs,
                                     parse_constant=bad_constant)
                    event_check(obj)
                    output.append(obj)
                    self.buffer.clear()
                    self.length = None
        except (ValueError, RecursionError):
            self.failed = True
            self.buffer.clear()
            raise ValueError('invalid frame') from None
        return output

    def eof(self):
        if self.buffer or self.length is not None:
            self.failed = True
            raise ValueError('truncated')


def wire(event):
    body = json.dumps(event, separators=(',', ':')).encode('utf-8')
    return len(body).to_bytes(4, 'big') + body


class Receiver:
    """TLS identity is a supplied test assumption, not cryptographic validation."""
    def __init__(self):
        self.active = False
        self.history_loss = False
        self.consumed = []

    def ready(self, identity, epoch, connection, cutoff, now):
        if self.active or identity != 'TEST_NODE_B':
            return False
        self.active = True
        self.epoch, self.connection = epoch, connection
        self.last = uint64(cutoff)
        self.last_seen = now
        self.status_seq = 0
        self.loss = False
        self.drops = 0
        self.queue = []
        return True

    def receive(self, event, now):
        event_check(event)
        if not self.active or (event['node_id'], event['producer_epoch'], event['connection_id']) != (
                'TEST_NODE_B', self.epoch, self.connection):
            return False
        seq = uint64(event['event_seq'])
        if seq <= self.last:
            return False
        if seq != self.last + 1:
            self.loss = self.history_loss = True
        self.last, self.last_seen = seq, now
        if len(self.queue) >= LIMITS['queue_size']:
            self.loss = self.history_loss = True
            return False
        self.queue.append((copy.deepcopy(event), now))
        return True

    def status(self, seq, drops, now):
        # Invoked only after identity/connection/schema checks in this model.
        if not self.active or seq <= self.status_seq or drops < self.drops:
            return False
        if drops > self.drops:
            self.loss = self.history_loss = True
        self.status_seq, self.drops, self.last_seen = seq, drops, now
        return True

    def state(self, now):
        if not self.active or now - self.last_seen >= LIMITS['heartbeat_timeout']:
            self.disconnect()
            return 'UNAVAILABLE'
        return 'INCOMPLETE' if self.loss else 'AVAILABLE'

    def consume(self, now):
        accepted = []
        for event, received in self.queue:
            if now - received > LIMITS['max_age']:
                self.loss = self.history_loss = True
            else:
                accepted.append((self.epoch, event['event_seq'], event['decision']))
        self.queue.clear()
        self.consumed.extend(accepted)
        return accepted

    def disconnect(self):
        if self.active and self.queue:
            self.history_loss = True
        self.active = False
        self.queue = []


class DesignTests(unittest.TestCase):
    def base(self, seq='11', **changes):
        return dict(FIXTURE['event'], event_seq=seq, **changes)

    def receiver(self):
        result = Receiver()
        self.assertTrue(result.ready('TEST_NODE_B', 'TEST_EPOCH_1', 'TEST_CONN_1', '10', 0))
        return result

    def test_fixture_decisions_and_boundaries(self):
        for case in FIXTURE['cases']:
            with self.subTest(case=case['id']):
                event = dict(FIXTURE['event'], **case['patch'])
                if case['expected'] == 'ERROR':
                    with self.assertRaises(ValueError):
                        event_check(event)
                else:
                    self.assertEqual(event_check(event), case['expected'])

    def test_fragmentation_every_split_and_concatenation(self):
        payload = wire(self.base()) + wire(self.base('12'))
        for split in range(len(payload) + 1):
            decoder = Decoder()
            self.assertEqual(decoder.feed(payload[:split]) + decoder.feed(payload[split:]),
                             [self.base(), self.base('12')])
            decoder.eof()

    def test_reject_duplicate_utf8_nonfinite_nested_and_missing(self):
        for body in (b'{"version":1,"version":1}', b'\xff', b'{"x":NaN}', b'[]', b'{}',
                     b'[' * 2000 + b']' * 2000):
            with self.subTest(body=body[:20]):
                with self.assertRaises(ValueError):
                    Decoder().feed(len(body).to_bytes(4, 'big') + body)

    def test_length_and_truncated_stream(self):
        for length in (0, LIMITS['max_body'] + 1, 2**32 - 1):
            decoder = Decoder()
            with self.assertRaises(ValueError):
                decoder.feed(length.to_bytes(4, 'big'))
            self.assertEqual(len(decoder.buffer), 0)
        decoder = Decoder()
        decoder.feed(wire(self.base())[:-1])
        with self.assertRaises(ValueError):
            decoder.eof()

    def test_unauthorized_identity_and_duplicate_connection(self):
        receiver = Receiver()
        self.assertFalse(receiver.ready('UNAUTHORIZED_TEST_PEER', 'e', 'c', '0', 0))
        receiver = self.receiver()
        self.assertFalse(receiver.ready('TEST_NODE_B', 'NEW', 'NEW', '0', 0))
        self.assertTrue(receiver.receive(self.base(), 1))

    def test_cutoff_duplicate_reverse_gap_and_invalid_no_refresh(self):
        receiver = self.receiver()
        self.assertFalse(receiver.receive(self.base('10'), 1))
        self.assertTrue(receiver.receive(self.base('11'), 2))
        self.assertFalse(receiver.receive(self.base('11'), 19))
        self.assertEqual(receiver.last_seen, 2)
        self.assertTrue(receiver.receive(self.base('13'), 3))
        self.assertEqual(receiver.state(4), 'INCOMPLETE')
        self.assertEqual(len(receiver.consume(4)), 2)

    def test_old_connection_epoch_and_node_rejected(self):
        receiver = self.receiver()
        for patch in ({'connection_id': 'OLD'}, {'producer_epoch': 'OLD'}, {'node_id': 'OTHER'}):
            self.assertFalse(receiver.receive(self.base(**patch), 1))
        self.assertEqual(receiver.last, 10)

    def test_reconnect_drops_backlog_and_keeps_loss_history(self):
        receiver = self.receiver()
        receiver.receive(self.base(), 1)
        receiver.disconnect()
        self.assertTrue(receiver.ready('TEST_NODE_B', 'TEST_EPOCH_1', 'TEST_CONN_2', '15', 2))
        self.assertFalse(receiver.receive(self.base(), 3))
        self.assertEqual(receiver.consume(3), [])
        self.assertTrue(receiver.receive(self.base('16', connection_id='TEST_CONN_2'), 4))
        self.assertEqual(receiver.state(4), 'AVAILABLE')
        self.assertTrue(receiver.history_loss)

    def test_receiver_restart_and_new_producer_epoch(self):
        receiver = Receiver()
        self.assertTrue(receiver.ready('TEST_NODE_B', 'TEST_EPOCH_2', 'TEST_CONN_2', '0', 0))
        self.assertFalse(receiver.receive(self.base(), 1))
        self.assertTrue(receiver.receive(self.base('1', producer_epoch='TEST_EPOCH_2', connection_id='TEST_CONN_2'), 2))

    def test_bounded_queue_and_expired_consumer(self):
        receiver = self.receiver()
        self.assertTrue(receiver.receive(self.base(), 0))
        self.assertTrue(receiver.receive(self.base('12'), 0))
        self.assertFalse(receiver.receive(self.base('13'), 0))
        self.assertEqual(len(receiver.queue), 2)
        self.assertEqual(receiver.consume(11), [])
        self.assertEqual(receiver.state(11), 'INCOMPLETE')

    def test_status_duplicate_timeout_boundary_and_drop_monotonicity(self):
        receiver = self.receiver()
        self.assertTrue(receiver.status(1, 0, 5))
        self.assertFalse(receiver.status(1, 0, 24))
        self.assertEqual(receiver.state(24), 'AVAILABLE')
        self.assertEqual(receiver.state(25), 'UNAVAILABLE')
        receiver = self.receiver()
        self.assertTrue(receiver.status(1, 2, 1))
        self.assertFalse(receiver.status(2, 1, 2))
        self.assertEqual(receiver.state(2), 'INCOMPLETE')

    def test_clock_domains_and_receive_is_not_consume(self):
        receiver = self.receiver()
        self.assertTrue(receiver.receive(self.base(), 1_000_000))
        self.assertEqual(receiver.consumed, [])
        self.assertEqual(receiver.consume(1_000_001), [('TEST_EPOCH_1', '11', 'ACCEPTED')])
        self.assertTrue(receiver.status(1, 0, 1_000_002))
        # Availability has no CAN freshness or vehicle state output.
        self.assertEqual(receiver.state(1_000_003), 'AVAILABLE')


if __name__ == '__main__':
    unittest.main(verbosity=2)
