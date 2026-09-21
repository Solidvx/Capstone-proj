"""Q2 candidate-2 executable specification. No product, network or TLS code."""
import copy
import json
from pathlib import Path
import re

SCHEMA = json.loads(Path(__file__).with_name('protocol_schema.json').read_text(encoding='utf-8'))
LIMITS = SCHEMA['limits']  # Synthetic test values only.
TOTALS = set(SCHEMA['kinds']['ready']) - {'cutoff_seq'}
IDENTITY = ('node_id', 'producer_epoch', 'contract_profile', 'verifier_version')


def number(value):
    if not isinstance(value, str) or not re.fullmatch(r'0|[1-9][0-9]{0,19}', value):
        raise ValueError('canonical uint64 string required')
    if int(value) >= 2**64:
        raise ValueError('uint64 overflow')
    return int(value)


def typed(value, kind):
    if kind.startswith('nullable_'):
        return value is None or typed(value, kind[9:])
    if kind == 'u64':
        number(value)
        return True
    if kind == 'id':
        return isinstance(value, str) and bool(re.fullmatch(r'[A-Za-z0-9_.-]{1,' + str(LIMITS['max_id']) + '}', value))
    if kind == 'version':
        return type(value) is int and value == 1
    if kind in ('can', 'u32'):
        return type(value) is int and 0 <= value <= (0x7ff if kind == 'can' else 2**32 - 1)
    if kind == 'bool':
        return type(value) is bool
    if kind == 'kind':
        return isinstance(value, str) and value in SCHEMA['kinds']
    if kind == 'decision':
        return isinstance(value, str) and value in SCHEMA['reasons']
    if kind == 'reason':
        return isinstance(value, str) and any(value in options for options in SCHEMA['reasons'].values())
    raise ValueError('unknown schema type')


def validate(message):
    if type(message) is not dict or not typed(message.get('kind'), 'kind'):
        raise ValueError('message kind')
    kind = message['kind']
    fields = dict(SCHEMA['common'], **SCHEMA['kinds'][kind])
    if set(message) != set(fields):
        raise ValueError('missing/extra fields')
    for key, type_name in fields.items():
        if not typed(message[key], type_name):
            raise ValueError('field: ' + key)
    if (message['connection_id'] is None) != (kind == 'hello'):
        raise ValueError('connection binding')
    if message['contract_profile'] not in SCHEMA['profiles']:
        raise ValueError('unsupported profile')
    if kind == 'event':
        decision, reason = message['decision'], message['reason']
        if reason not in SCHEMA['reasons'][decision] or number(message['event_seq']) == 0:
            raise ValueError('event semantics')
        secure = SCHEMA['profiles'][message['contract_profile']]['mode'] == 'secure'
        if (decision == 'BYPASSED') == secure:
            raise ValueError('profile/decision')
        raw, auth = message['raw_id'], message['auth_id']
        pairs = SCHEMA['profiles'][message['contract_profile']]['pairs']
        if raw is not None and raw not in [p[0] for p in pairs]:
            raise ValueError('raw id')
        if auth is not None and auth not in [p[1] for p in pairs]:
            raise ValueError('auth id')
        if raw is not None and auth is not None and [raw, auth] not in pairs:
            raise ValueError('id pair')
        if decision in ('ACCEPTED', 'REJECTED') and (raw is None or auth is None or message['counter'] is None):
            raise ValueError('missing verification input')
        if message['counter_trusted'] != (decision == 'ACCEPTED'):
            raise ValueError('counter trust')
        if auth is None and message['counter'] is not None:
            raise ValueError('counter without auth')
        if reason in ('RAW_EXPIRED', 'RAW_REPLACED') and (raw is None or auth is not None):
            raise ValueError('raw terminal outcome')
        if reason == 'ORPHAN_AUTH' and (raw is not None or auth is None):
            raise ValueError('orphan outcome')
        if decision == 'BYPASSED' and (raw is None or auth is not None or message['counter'] is not None):
            raise ValueError('bypass outcome')
        age = number(message['emit_mono_ns']) - number(message['event_mono_ns'])
        if not 0 <= age <= LIMITS['source_age']:
            raise ValueError('source age')
    if kind in ('ready', 'status'):
        n = {key: number(message[key]) for key in TOTALS}
        if sum(n[k] for k in ('accepted_total', 'rejected_total', 'not_evaluated_total', 'bypassed_total')) != n['generated_total']:
            raise ValueError('decision totals')
        if sum(n[k] for k in ('offered_total', 'overflow_total', 'expired_total', 'reset_total', 'queue_depth')) != n['generated_total']:
            raise ValueError('delivery totals')
        if n['queue_depth'] > LIMITS['queue_size'] or not n['offered_total'] <= n['last_offered_seq'] <= n['generated_total']:
            raise ValueError('queue/watermark')
        if (n['offered_total'] == 0) != (n['last_offered_seq'] == 0):
            raise ValueError('offered watermark')
        if kind == 'ready' and (n['queue_depth'] != 0 or number(message['cutoff_seq']) != n['generated_total']):
            raise ValueError('ready boundary')
        if kind == 'status' and number(message['status_seq']) == 0:
            raise ValueError('status sequence')
        bypass = SCHEMA['profiles'][message['contract_profile']]['mode'] == 'bypass'
        if (bypass and n['bypassed_total'] != n['generated_total']) or (not bypass and n['bypassed_total'] != 0):
            raise ValueError('profile totals')
    return message


def unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('nonfinite')


def decode_body(body):
    if not 0 < len(body) <= LIMITS['max_body']:
        raise ValueError('body size')
    try:
        message = json.loads(body.decode('utf-8'), object_pairs_hook=unique_pairs, parse_constant=reject_constant)
        return validate(message)
    except (RecursionError, UnicodeError, ValueError):
        raise ValueError('invalid body') from None


class Session:
    """Node A model. authenticated_peer/connection supplied by a trusted TLS stub.

    Messages must be delivered in serialized stream order. No thread simulation.
    """
    def __init__(self):
        self.phase = 'DISCONNECTED'
        self.history_loss = False
        self.queue = []
        self.consumed = []
        self.receiver_drops = {'overflow': 0, 'expired': 0, 'reset': 0}
        self.remembered = None  # Only the most recent epoch; bounded process memory.

    def start(self, authenticated_peer, connection, now):
        if self.phase != 'DISCONNECTED' or authenticated_peer != 'TEST_NODE_B' or not typed(connection, 'id'):
            return False
        self.peer, self.connection = authenticated_peer, connection
        self.phase, self.started, self.clock = 'WAIT_HELLO', now, now
        self.loss = False
        self.status_seq = 0
        self.status_time = None
        return True

    def close(self):
        if self.phase in ('WAIT_STATUS', 'ACTIVE'):
            self.remembered = (self.identity, dict(self.previous), max(self.floor, self.last_event))
        self.receiver_drops['reset'] += len(self.queue)
        self.history_loss |= bool(self.queue)
        self.queue.clear()
        self.phase = 'DISCONNECTED'

    def tick(self, now):
        if self.phase == 'DISCONNECTED':
            return False
        if now < self.clock:
            self.close()
            return False
        self.clock = now
        expired = (self.phase in ('WAIT_HELLO', 'WAIT_READY') and now - self.started >= LIMITS['handshake_timeout'])
        if self.phase in ('WAIT_STATUS', 'ACTIVE'):
            expired = now - self.last_seen >= LIMITS['heartbeat_timeout'] or now - self.last_status >= LIMITS['heartbeat_timeout']
        if expired:
            self.close()
        return not expired

    def accept(self, message, now):
        if not self.tick(now):
            return False
        try:
            validate(message)
            if message['node_id'] != self.peer:
                raise ValueError('peer')
            kind = message['kind']
            if self.phase == 'WAIT_HELLO':
                if kind != 'hello':
                    raise ValueError('hello required')
                self.identity = tuple(message[k] for k in IDENTITY)
                self.phase = 'WAIT_READY'
                return dict(message, kind='challenge', connection_id=self.connection)
            if tuple(message[k] for k in IDENTITY) != self.identity or message['connection_id'] != self.connection:
                raise ValueError('binding')
            if self.phase == 'WAIT_READY':
                if kind != 'ready':
                    raise ValueError('ready required')
                baseline = {key: number(message[key]) for key in TOTALS}
                if self.remembered is not None and self.remembered[0] == self.identity:
                    _, old, watermark = self.remembered
                    if any(baseline[k] < old[k] for k in TOTALS - {'queue_depth'}) or number(message['cutoff_seq']) < watermark:
                        raise ValueError('same epoch reset')
                self.previous = baseline
                self.last_event = self.floor = number(message['cutoff_seq'])
                self.cutoff = self.floor
                self.last_seen = self.last_status = now
                self.phase = 'WAIT_STATUS'
                self.history_loss |= any(self.previous[k] for k in ('overflow_total', 'expired_total', 'reset_total'))
                return True
            if self.phase == 'WAIT_STATUS' and kind != 'status':
                raise ValueError('initial status required')
            if kind == 'status':
                seq = number(message['status_seq'])
                if seq <= self.status_seq:
                    return False
                totals = {key: number(message[key]) for key in TOTALS}
                snapshot = number(message['snapshot_mono_ns'])
                if self.status_time is not None and snapshot < self.status_time:
                    raise ValueError('snapshot regression')
                if any(totals[k] < self.previous[k] for k in TOTALS - {'queue_depth'}):
                    raise ValueError('counter regression')
                new_offers = totals['offered_total'] - self.previous['offered_total']
                if new_offers and totals['last_offered_seq'] <= max(self.cutoff, self.previous['last_offered_seq']):
                    raise ValueError('pre-ready offer')
                if not new_offers and totals['last_offered_seq'] != self.previous['last_offered_seq']:
                    raise ValueError('watermark without offer')
                if totals['last_offered_seq'] < self.last_event and self.last_event > self.floor:
                    raise ValueError('snapshot precedes received event')
                lost = any(totals[k] > self.previous[k] for k in ('overflow_total', 'expired_total', 'reset_total'))
                # FIFO serialization: offered events must precede this status.
                lost |= totals['last_offered_seq'] > max(self.floor, self.last_event)
                self.loss |= lost
                self.history_loss |= lost
                self.floor = max(self.floor, totals['last_offered_seq'])
                self.previous = totals
                self.status_seq, self.status_time = seq, snapshot
                self.last_seen = self.last_status = now
                self.phase = 'ACTIVE'
                return True
            if kind != 'event' or self.phase != 'ACTIVE':
                raise ValueError('unexpected message')
            seq = number(message['event_seq'])
            if seq <= max(self.last_event, self.floor):
                return False
            if seq != max(self.last_event, self.floor) + 1:
                self.loss = self.history_loss = True
            self.last_event, self.last_seen = seq, now
            if len(self.queue) == LIMITS['queue_size']:
                self.receiver_drops['overflow'] += 1
                self.loss = self.history_loss = True
                return False
            self.queue.append((copy.deepcopy(message), now))
            return True
        except ValueError:
            self.close()
            return False

    def state(self, now):
        if not self.tick(now) or self.phase != 'ACTIVE':
            return 'UNAVAILABLE'
        return 'INCOMPLETE' if self.loss else 'AVAILABLE'

    def consume(self, now):
        if not self.tick(now) or self.phase != 'ACTIVE':
            return []
        result = []
        for event, received in self.queue:
            if now - received > LIMITS['consumer_age']:
                self.receiver_drops['expired'] += 1
                self.loss = self.history_loss = True
            else:
                result.append((event['producer_epoch'], event['event_seq'], event['decision']))
        self.queue.clear()
        self.consumed.extend(result)
        return result


class ProducerLedger:
    """Serial ledger proving ready partition, not a thread-safe implementation."""
    def __init__(self):
        self.totals = {key: 0 for key in TOTALS}
        self.queue = []

    def generate(self):
        if self.totals['generated_total'] == 2**64 - 1:
            raise ValueError('new epoch required')
        self.totals['generated_total'] += 1
        self.totals['accepted_total'] += 1
        seq = self.totals['generated_total']
        if len(self.queue) == LIMITS['queue_size']:
            self.totals['overflow_total'] += 1
        else:
            self.queue.append(seq)
        self.totals['queue_depth'] = len(self.queue)
        return seq

    def ready_cut(self):
        self.totals['reset_total'] += len(self.queue)
        self.queue.clear()
        self.totals['queue_depth'] = 0
        return self.totals['generated_total'], self.snapshot()

    def offer(self):
        seq = self.queue.pop(0)
        self.totals['offered_total'] += 1
        self.totals['last_offered_seq'] = seq
        self.totals['queue_depth'] = len(self.queue)
        return seq

    def snapshot(self):
        return {key: str(value) for key, value in self.totals.items()}
