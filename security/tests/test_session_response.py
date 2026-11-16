from copy import deepcopy
from types import SimpleNamespace

import pytest

from security.experiments.session_campaign_evidence import evaluate
from security.ids.incident_status import IncidentStatus
from security.tests.test_session_campaign_evidence import fixture, RUN

CLOCK = '00000000-0000-4000-8000-000000000002'


def evidence():
    f = fixture()
    for row in f['observers'][1]:
        if row.get('result') == 'PHASE': row['clock_id'] = CLOCK
    observation = next(row for row in f['ivi'] if row.get('kind') == 7 and row['condition_mask'] == 8)
    body = IncidentStatus().update(bytes.fromhex(observation['body_hex']),
        SimpleNamespace(ended_mask=0, quiet_span_ms=[0]*4))[0]
    row = dict(observation, kind=4, body_hex=body.hex(), run_id=RUN, clock_id=CLOCK,
               received_monotonic_ms='102550', verified_monotonic_ms='102551',
               semantic_verified_monotonic_ns='102551000000', incident_semantic_accepted=True)
    f['ivi'].append(row)
    f['ids'].append(dict(result='DIAGNOSTIC_IPC', kind=4, body_hex=body.hex(),
                         timestamp=10002.55, local_accepted=True))
    return f


def response(f):
    row = evaluate(**f)
    assert row['status'] == 'VALID', row
    return row['attack_response']


def test_same_IVI_clock_endpoint_uses_semantic_completion_not_other_host_TX():
    f = evidence()
    result = response(f)
    assert result['status'] == 'PASS' and result['latency_s'] == pytest.approx(.451)
    assert result['start_ns'] == 102100000000 and result['end_ns'] == 102551000000
    assert evaluate(**f)['detect_latency_s'] == result['latency_s']
    f['worker'][0]['t'] = 99999999999
    assert response(f) == result


def test_late_and_missed_detections_remain_measurements():
    f = evidence(); f['ivi'][-1]['semantic_verified_monotonic_ns'] = '105551000000'
    assert response(f)['status'] == 'FAIL'
    f['ivi'].pop()
    assert response(f)['status'] == 'MISSED'


@pytest.mark.parametrize('damage,expected', [
    ('replay', 'UNMEASURABLE'), ('baseline_copy', 'UNMEASURABLE'),
    ('prior_incident', 'UNMEASURABLE'), ('not_accepted', 'MISSED'),
    ('clock', 'INVALID'), ('run', 'INVALID'), ('time_order', 'INVALID'),
    ('ipc', 'INVALID'), ('missing_clock', 'INVALID'), ('drop', 'INVALID')])
def test_no_success_from_ambiguous_starts_old_incidents_or_missing_proof(damage, expected):
    f = evidence(); row = f['ivi'][-1]
    if damage == 'replay': f['attack'] = 'replay'
    if damage == 'baseline_copy': f['observers'][1].append(dict(f['observers'][1][-1], t=101.))
    if damage == 'prior_incident':
        f['ivi'].append(dict(row, received_monotonic_ms='101500', verified_monotonic_ms='101501'))
    if damage == 'not_accepted': row['incident_semantic_accepted'] = False
    if damage == 'clock': row['clock_id'] = '00000000-0000-4000-8000-000000000003'
    if damage == 'run': row['run_id'] = 'other-run'
    if damage == 'time_order': row['semantic_verified_monotonic_ns'] = '102000000000'
    if damage == 'ipc': f['ids'].pop()
    if damage == 'missing_clock': f['observers'][1][0].pop('clock_id')
    if damage == 'drop': f['observers'][1][-1]['rx_dropped'] = 1
    result = evaluate(**f)['attack_response']
    assert result['status'] == expected and result['latency_s'] is None


def test_payload_match_with_wrong_CAN_metadata_is_not_a_start():
    f=evidence();f['observers'][1][-1]['extended']=True
    assert response(f)['reason']=='ATTACK_FRAME_METADATA_UNVERIFIED'


def test_only_same_attack_type_active_new_incident_finishes_the_metric():
    f = evidence()
    body = bytearray.fromhex(f['ivi'][-1]['body_hex']); body[32] = 1
    f['ivi'][-1]['body_hex'] = body.hex()
    assert response(f)['status'] == 'MISSED'


def test_too_short_window_does_not_claim_a_miss():
    f = evidence(); f['ivi'].pop()
    # Keep the observer/health window valid while moving first observed attack.
    f['observers'][1][-1]['t'] = 104.5
    assert response(f)['status'] == 'INVALID'


def replay_evidence():
    from security.tests.test_session_campaign_evidence import CONTEXT, SOURCE
    f = evidence()
    raw, auth = '64c80f3cffec4100', '0102030400000005'
    def sample(stamp, cid, data):
        return dict(result='OBS_FRAME', t=stamp, can_id=cid, data=data, dlc=8,
                    extended=False, remote=False, error=False, rx_dropped=0)
    frames = [sample(101., 0x100, raw), sample(101.001, 0x102, auth),
              sample(103., 0x100, raw), sample(103.001, 0x102, auth)]
    ref = bytes((2, 8, 8, 0)) + bytes.fromhex('0000010000000102') + bytes.fromhex(CONTEXT+raw+auth)
    rejection = SOURCE.bytes * 2 + bytes((7, 1, 1, 0)) + ref
    witness = dict(result='LOCAL_REJECTION_RECORD', body_hex=rejection.hex(),
                   run_id=RUN, clock_id=CLOCK, recorded_monotonic_ns='103005000000')
    original = dict(result='SESSION_PUBLICATION', run_id=RUN, clock_id=CLOCK,
        secoc_verified=True, valid=True, stale=False, bms_context_id=CONTEXT,
        bms_raw_hex=raw, bms_auth_hex=auth, t1_received_ns='101000000000',
        bms_auth_received_ns='101001000000', t2_published_ns='101005000000')
    row = f['ivi'][-1]
    body = bytearray.fromhex(row['body_hex']); body[32] = 2
    row.update(body_hex=body.hex(), received_monotonic_ms='103550', verified_monotonic_ms='103551',
               semantic_verified_monotonic_ns='103551000000', session_id=CONTEXT)
    args = dict(attack='replay', code=2, run_id=RUN, signatures={(0x100, raw), (0x102, auth)},
                observer=[r for r in f['observers'][1] if r.get('result')=='PHASE'] + frames,
                window=(100., 102., 104., 106.), diagnostics=[(103.55, row, bytes(body))],
                accepted={(4, body.hex())}, valid=True, rejections=[witness, original])
    return args


def test_replay_dates_first_repeated_auth_only_with_independent_verified_rejection():
    from security.experiments.session_response import measure
    args = replay_evidence()
    result = measure(**args)
    assert result['status'] == 'PASS'
    assert result['start_basis'] == 'FIRST_REPEATED_AUTH_WITH_VERIFIED_REJECTION'
    assert result['start_ns'] == 103001000000
    assert result['latency_s'] == pytest.approx(.550)
    # A replayed raw payload alone is not the identifiable auth start.
    assert result['start_ns'] != 103000000000


@pytest.mark.parametrize('damage', ['missing_witness','no_prior_original','wrong_run','wrong_clock',
    'unverified_mac','wrong_context','wrong_pair','outside_window','only_original',
    'missing_original_acceptance','different_original','late_original','old_original'])
def test_replay_missing_or_ambiguous_proof_never_becomes_a_latency_success(damage):
    from security.experiments.session_response import measure
    args = replay_evidence(); witness = args['rejections'][0]
    if damage == 'missing_witness': args['rejections'] = []
    if damage == 'no_prior_original': args['observer'] = [r for r in args['observer'] if r.get('result')!='OBS_FRAME' or r['t']>=102]
    if damage == 'wrong_run': witness['run_id'] = 'other'
    if damage == 'wrong_clock': witness['clock_id'] = '00000000-0000-4000-8000-000000000003'
    if damage in ('unverified_mac','wrong_context','wrong_pair'):
        body = bytearray.fromhex(witness['body_hex'])
        body[{'unverified_mac':33,'wrong_context':48,'wrong_pair':72}[damage]] ^= 1
        witness['body_hex'] = body.hex()
    if damage == 'outside_window': witness['recorded_monotonic_ns'] = '107000000000'
    if damage == 'only_original': args['observer'] = [r for r in args['observer'] if r.get('result')!='OBS_FRAME' or r['t']<102]
    if damage == 'missing_original_acceptance': args['rejections'].pop()
    if damage == 'different_original': args['rejections'][1]['bms_auth_hex']='00'*8
    if damage == 'late_original':
        args['rejections'][1]['t2_published_ns']='103100000000'
        args['observer'].append(dict(args['observer'][-1],t=103.2))
    if damage == 'old_original': args['rejections'][1]['bms_auth_received_ns']='99000000000'
    result = measure(**args)
    assert result['status'] == 'UNMEASURABLE' and result['latency_s'] is None


def test_replay_observer_time_regression_and_malformed_witness_fail_closed():
    from security.experiments.session_response import measure
    args=replay_evidence(); args['observer'][-1]['t']=100.
    assert measure(**args)['reason']=='IVI_OBSERVER_TIME_ORDER_INVALID'
    args=replay_evidence(); args['rejections'][0]['recorded_monotonic_ns']='bad'
    assert measure(**args)['status']=='INVALID'
