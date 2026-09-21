"""Candidate-2 checks against fixed fixtures and adversarial traces."""
import copy
import itertools
import json
from pathlib import Path
import unittest

from protocol_model import LIMITS, SCHEMA, ProducerLedger, Session, decode_body, number, validate

MESSAGES = json.loads(Path(__file__).with_name('protocol_fixtures.json').read_text(encoding='utf-8'))['messages']


def message(kind, **patch):
    return dict(copy.deepcopy(MESSAGES[kind]), **patch)


class ProtocolTests(unittest.TestCase):
    def active(self):
        session = Session()
        self.assertTrue(session.start('TEST_NODE_B', 'TEST_CONN_1', 0))
        self.assertEqual(session.accept(message('hello'), 1), message('challenge'))
        self.assertTrue(session.accept(message('ready'), 2))
        self.assertEqual(session.state(2), 'UNAVAILABLE')
        self.assertTrue(session.accept(message('status'), 3))
        return session

    def test_five_wire_bodies_round_trip(self):
        for kind in MESSAGES:
            with self.subTest(kind=kind):
                sample = message(kind)
                self.assertEqual(decode_body(json.dumps(sample).encode()), sample)

    def test_every_required_field_missing_and_extras_rejected(self):
        for kind, sample in MESSAGES.items():
            for key in sample:
                with self.subTest(kind=kind, missing=key):
                    modified = dict(sample)
                    del modified[key]
                    with self.assertRaises(ValueError):
                        validate(modified)
            with self.assertRaises(ValueError):
                validate(dict(sample, future_field=1))

    def test_bad_types_uint64_and_json(self):
        for value in ('01', '-1', '1.0', '١', 1, True, str(2**64)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                number(value)
        self.assertEqual(number(str(2**64 - 1)), 2**64 - 1)
        for body in (b'{"version":1,"version":1}', b'{"x":NaN}', b'\xff', b'[]', b'x' * (LIMITS['max_body'] + 1)):
            with self.assertRaises(ValueError):
                decode_body(body)
        for patch in ({'version': True}, {'counter': True}, {'raw_id': True}, {'counter_trusted': 1}, {'connection_id': None}):
            with self.assertRaises(ValueError):
                validate(message('event', **patch))

    def test_counter_trust_pairs_profiles_and_nullable_outcomes(self):
        for patch in ({'auth_id': 259}, {'raw_id': 512}, {'counter': None}, {'counter_trusted': False},
                      {'decision': 'REJECTED', 'reason': 'MAC_MISMATCH'}, {'contract_profile': 'UNKNOWN'}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate(message('event', **patch))
        validate(message('event', decision='REJECTED', reason='COUNTER_REJECT', counter_trusted=False))
        validate(message('event', decision='NOT_EVALUATED', reason='ORPHAN_AUTH', raw_id=None, counter_trusted=False))
        validate(message('event', decision='NOT_EVALUATED', reason='RAW_EXPIRED', auth_id=None, counter=None, counter_trusted=False))
        validate(message('event', contract_profile='TEST_C0', decision='BYPASSED', reason='SECURITY_DISABLED', auth_id=None, counter=None, counter_trusted=False))

    def test_ledger_conservation_and_profile_totals(self):
        for patch in ({'generated_total': '1'}, {'queue_depth': '1'}, {'offered_total': '1'},
                      {'last_offered_seq': '1'}, {'status_seq': '0'},
                      {'generated_total': '1', 'bypassed_total': '1', 'reset_total': '1'}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate(message('status', **patch))
        with self.assertRaises(ValueError):
            validate(message('ready', cutoff_seq='1'))

    def test_initial_status_required_and_wrong_phase_closes(self):
        session = Session()
        session.start('TEST_NODE_B', 'TEST_CONN_1', 0)
        self.assertFalse(session.accept(message('event'), 1))
        self.assertEqual(session.phase, 'DISCONNECTED')
        session = self.active()
        self.assertFalse(session.accept(message('ready'), 4))
        self.assertEqual(session.phase, 'DISCONNECTED')

    def test_identity_epoch_profile_version_binding(self):
        for patch in ({'node_id': 'OTHER'}, {'producer_epoch': 'OTHER'}, {'connection_id': 'OLD'},
                      {'contract_profile': 'TEST_C0'}, {'verifier_version': 'OTHER'}):
            session = self.active()
            self.assertFalse(session.accept(message('status', status_seq='2', **patch), 4))
            self.assertEqual(session.state(4), 'UNAVAILABLE')
        session = Session()
        self.assertFalse(session.start('OTHER', 'TEST_CONN_1', 0))
        session = self.active()
        self.assertFalse(session.start('TEST_NODE_B', 'NEW', 4))
        self.assertEqual(session.phase, 'ACTIVE')

    def test_handshake_heartbeat_status_deadlines_and_clock_regression(self):
        session = Session()
        session.start('TEST_NODE_B', 'TEST_CONN_1', 0)
        self.assertTrue(session.tick(4))
        self.assertFalse(session.accept(message('hello'), 5))
        session = self.active()
        self.assertTrue(session.accept(message('event'), 22))
        # Events cannot indefinitely mask absence of fresh status.
        self.assertFalse(session.accept(message('event', event_seq='2'), 23))
        session = self.active()
        self.assertFalse(session.tick(2))

    def test_duplicate_status_does_not_refresh_and_bad_counters_close(self):
        session = self.active()
        self.assertFalse(session.accept(message('status'), 22))
        self.assertEqual(session.state(23), 'UNAVAILABLE')
        session = self.active()
        status = message('status', status_seq='2', generated_total='1', accepted_total='1', reset_total='1')
        self.assertTrue(session.accept(status, 4))
        self.assertEqual(session.state(4), 'INCOMPLETE')
        self.assertFalse(session.accept(message('status', status_seq='3'), 5))
        self.assertEqual(session.phase, 'DISCONNECTED')

    def test_event_gap_and_status_watermark_prevent_delayed_replay(self):
        session = self.active()
        self.assertTrue(session.accept(message('event', event_seq='2'), 4))
        self.assertEqual(session.state(4), 'INCOMPLETE')
        self.assertFalse(session.accept(message('event'), 5))
        session = self.active()
        status = message('status', status_seq='2', generated_total='1', accepted_total='1', offered_total='1', last_offered_seq='1')
        self.assertTrue(session.accept(status, 4))
        self.assertEqual(session.state(4), 'INCOMPLETE')
        self.assertFalse(session.accept(message('event'), 5))
        self.assertEqual(session.consume(5), [])

    def test_status_cannot_precede_received_event(self):
        session = self.active()
        session.accept(message('event'), 4)
        self.assertFalse(session.accept(message('status', status_seq='2'), 5))
        self.assertEqual(session.phase, 'DISCONNECTED')

    def test_receive_consume_drops_separate_from_producer(self):
        session = self.active()
        for seq in ('1', '2', '3'):
            session.accept(message('event', event_seq=seq), 4)
        self.assertEqual(session.receiver_drops['overflow'], 1)
        self.assertEqual(session.previous['overflow_total'], 0)
        self.assertEqual(session.consume(15), [])
        self.assertEqual(session.receiver_drops['expired'], 2)
        self.assertEqual(session.consumed, [])

    def test_ready_cut_partitions_all_serial_interleavings(self):
        # All placements of a single atomic ready relative to two generates.
        for actions in set(itertools.permutations(('generate', 'generate', 'ready'))):
            producer = ProducerLedger()
            for action in actions:
                if action == 'generate':
                    producer.generate()
                else:
                    cutoff, baseline = producer.ready_cut()
                    validate(message('ready', cutoff_seq=str(cutoff), **baseline))
            pending = list(producer.queue)
            self.assertTrue(all(seq > cutoff for seq in pending))
            self.assertEqual(producer.totals['reset_total'], cutoff)
            self.assertEqual(len(pending) + cutoff, 2)

    def test_overflow_offer_and_reset_are_disjoint(self):
        producer = ProducerLedger()
        for _ in range(3):
            producer.generate()
        self.assertEqual(producer.offer(), 1)
        cutoff, totals = producer.ready_cut()
        self.assertEqual((totals['offered_total'], totals['overflow_total'], totals['reset_total']), ('1', '1', '1'))
        validate(message('ready', cutoff_seq=str(cutoff), **totals))
        self.assertEqual(totals['generated_total'], '3')

    def test_reconnect_baseline_and_previous_loss_history(self):
        session = self.active()
        session.accept(message('event'), 4)
        session.close()
        self.assertEqual(session.receiver_drops['reset'], 1)
        session.start('TEST_NODE_B', 'TEST_CONN_2', 5)
        session.accept(message('hello'), 6)
        ready = message('ready', connection_id='TEST_CONN_2', cutoff_seq='5', generated_total='5', accepted_total='5', reset_total='5')
        self.assertTrue(session.accept(ready, 7))
        status = message('status', connection_id='TEST_CONN_2', generated_total='5', accepted_total='5', reset_total='5')
        self.assertTrue(session.accept(status, 8))
        self.assertEqual(session.state(8), 'AVAILABLE')
        self.assertTrue(session.history_loss)
        self.assertFalse(session.accept(message('event', connection_id='TEST_CONN_2', event_seq='5'), 9))
        self.assertTrue(session.accept(message('event', connection_id='TEST_CONN_2', event_seq='6'), 10))
        self.assertEqual(session.consume(11), [('TEST_EPOCH_1', '6', 'ACCEPTED')])

    def test_sequence_exhaustion_requires_epoch_change(self):
        producer = ProducerLedger()
        producer.totals['generated_total'] = 2**64 - 1
        with self.assertRaises(ValueError):
            producer.generate()

    def test_same_epoch_reconnect_cannot_reset_totals_or_sequence(self):
        session = self.active()
        session.accept(message('event'), 4)
        session.close()
        session.start('TEST_NODE_B', 'TEST_CONN_2', 5)
        session.accept(message('hello'), 6)
        self.assertFalse(session.accept(message('ready', connection_id='TEST_CONN_2'), 7))
        self.assertEqual(session.phase, 'DISCONNECTED')

    def test_status_offer_watermark_consistency(self):
        session = Session()
        session.start('TEST_NODE_B', 'TEST_CONN_1', 0)
        session.accept(message('hello'), 1)
        # Five old results, all already handed to the old transport.
        baseline = dict(generated_total='5', accepted_total='5', offered_total='5', last_offered_seq='5')
        session.accept(message('ready', cutoff_seq='5', **baseline), 2)
        session.accept(message('status', **baseline), 3)
        # An increased offer count cannot retain its old watermark.
        invalid = message('status', status_seq='2', generated_total='6', accepted_total='6', offered_total='6', last_offered_seq='6')
        self.assertTrue(session.accept(invalid, 4))
        self.assertEqual(session.state(4), 'INCOMPLETE')
        # A later watermark without any additional offer is impossible.
        invalid.update(status_seq='3', generated_total='7', accepted_total='7', reset_total='1', last_offered_seq='7')
        self.assertFalse(session.accept(invalid, 5))


if __name__ == '__main__':
    unittest.main(verbosity=2)
