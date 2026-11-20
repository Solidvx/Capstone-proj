import copy
from pathlib import Path

import pytest

from tools.deployment.health import check, evaluate, validate_ready
from tools.deployment import health


@pytest.mark.parametrize('platform', [None, 'offscreen', 'wayland', 'xcb'])
def test_ready_preserves_required_fields_with_optional_display_metadata(platform):
    record = {'result': 'READY', 'run_id': 'PUBLIC-DUMMY', 'secoc_on': True}
    if platform is not None:record['display_platform'] = platform
    before = copy.deepcopy(record)
    validate_ready(record, 'PUBLIC-DUMMY')
    assert record == before


@pytest.mark.parametrize('mutation', ['wrong-run', 'not-ready', 'missing-security',
    'unprotected', 'numeric-security', 'unknown-field', 'empty-platform',
    'invalid-platform', 'oversized-platform', 'nontext-platform', 'not-object'])
def test_display_metadata_cannot_bypass_protected_readiness(mutation):
    record = {'result': 'READY', 'run_id': 'PUBLIC-DUMMY', 'secoc_on': True,
              'display_platform': 'offscreen'}
    if mutation == 'wrong-run':record['run_id'] = 'OTHER'
    elif mutation == 'not-ready':record['result'] = 'STARTING'
    elif mutation == 'missing-security':record.pop('secoc_on')
    elif mutation == 'unprotected':record['secoc_on'] = False
    elif mutation == 'numeric-security':record['secoc_on'] = 1
    elif mutation == 'unknown-field':record['skip_authentication'] = True
    elif mutation == 'empty-platform':record['display_platform'] = ''
    elif mutation == 'invalid-platform':record['display_platform'] = 'offscreen\n'
    elif mutation == 'oversized-platform':record['display_platform'] = 'x'*65
    elif mutation == 'nontext-platform':record['display_platform'] = True
    elif mutation == 'not-object':record = []
    with pytest.raises(ValueError):validate_ready(record, 'PUBLIC-DUMMY')


def rows():
    instance = bytes.fromhex('112233445566478899aabbccddeeff00')
    lineage = bytes.fromhex('2233445566774899aabbccddeeff0011')
    node = bytearray(56);node[:16] = instance
    node[32:35] = bytes((2, 1, 2));node[53] = 1
    protection = instance+lineage+bytes(24)
    common = {'result': 'AUTHENTICATED_DIAGNOSTIC', 'session_id': 'aa'*16,
              'received_monotonic_ms': '4000', 'verified_monotonic_ms': '4001'}
    return [{**common, 'kind': 1, 'sequence': '1', 'body_hex': node.hex()},
            {**common, 'kind': 8, 'sequence': '2', 'body_hex': protection.hex()},
            {'result': 'SESSION_PUBLICATION', 'run_id': 'PUBLIC-DUMMY', 'measurement_sequence': '10',
             'session_id': 'aa'*16, 'valid': True, 'stale': False, 'secoc_verified': True,
             'state_confirmed': True, 'protection_confirmed': True, 'battery_state': 0, 'battery_reason': 0,
             't1_received_ns': '4500000000', 't2_published_ns': '4501000000'}]


def test_fresh_verified_publication_requires_matching_current_diagnostics():
    result = evaluate(rows(), 'PUBLIC-DUMMY', 5_000_000_000, 2000)
    assert result['status'] == 'PASS' and result['publication_age_ms'] == 500
    assert result['battery_state'] == 0


@pytest.mark.parametrize('mutation', ['stale', 'unverified', 'unconfirmed', 'wrong-run', 'future',
    'clock-order', 'old-diagnostic', 'missing-diagnostic', 'foreign-session', 'different-instance',
    'input-error', 'restoring', 'invalid-body', 'negative-counter', 'missing-session', 'risk-mismatch'])
def test_active_process_is_not_sufficient_for_health(mutation):
    data = rows();p = data[-1]
    if mutation == 'stale':p['stale'] = True
    elif mutation == 'unverified':p['secoc_verified'] = False
    elif mutation == 'unconfirmed':p['protection_confirmed'] = False
    elif mutation == 'wrong-run':p['run_id'] = 'OTHER'
    elif mutation == 'future':p['t1_received_ns'] = p['t2_published_ns'] = '6000000000'
    elif mutation == 'clock-order':p['t2_published_ns'] = '4000000000'
    elif mutation == 'old-diagnostic':data[0]['received_monotonic_ms'] = '1'
    elif mutation == 'missing-diagnostic':del data[0]
    elif mutation == 'foreign-session':data[0]['session_id'] = 'bb'*16
    elif mutation == 'different-instance':
        body = bytearray.fromhex(data[0]['body_hex']);body[0] ^= 1;data[0]['body_hex'] = body.hex()
    elif mutation == 'input-error':
        body = bytearray.fromhex(data[0]['body_hex']);body[34] = 3;body[53] = 0;data[0]['body_hex'] = body.hex()
    elif mutation == 'restoring':
        body = bytearray.fromhex(data[0]['body_hex']);body[32] = 3;data[0]['body_hex'] = body.hex()
    elif mutation == 'invalid-body':data[1]['body_hex'] = '00'
    elif mutation == 'negative-counter':p['measurement_sequence'] = '-1'
    elif mutation == 'missing-session':p.pop('session_id')
    elif mutation == 'risk-mismatch':p['battery_state'] = 3
    with pytest.raises(ValueError):evaluate(data, 'PUBLIC-DUMMY', 5_000_000_000, 2000)


def test_old_out_of_order_diagnostic_cannot_overwrite_fresh_current_state():
    data = rows();old = copy.deepcopy(data[0]);old['sequence'] = '0';old['body_hex'] = '00'
    data.append(old)
    assert evaluate(data, 'PUBLIC-DUMMY', 5_000_000_000, 2000)['status'] == 'PASS'


def test_protection_state_is_preserved_and_never_reset_as_a_health_fix():
    data = rows()
    node = bytearray.fromhex(data[0]['body_hex']);node[35:38] = bytes((3, 1, 4))
    protection = bytearray.fromhex(data[1]['body_hex'])
    protection[32:48] = bytes.fromhex('33445566778849aabbccddeeff001122')
    protection[48:51] = bytes((3, 4, 1));protection[55] = 1
    data[0]['body_hex'] = node.hex();data[1]['body_hex'] = protection.hex()
    data[-1].update(battery_state=3, battery_reason=4)
    before = copy.deepcopy(data)
    result = evaluate(data, 'PUBLIC-DUMMY', 5_000_000_000, 2000)
    assert result['status'] == 'PASS' and result['battery_state'] == 3 and data == before


def test_no_key_file_is_opened_to_validate_health(tmp_path, monkeypatch):
    # Invalid artifact is rejected before evidence or any secret can be read.
    monkeypatch.setattr(health, 'process_identity', lambda _: (tmp_path, '100', __import__('os').getuid()))
    def read(path):
        assert path == tmp_path/'exe', 'must not read any key or evidence after artifact mismatch'
        return b'public-dummy-executable'
    monkeypatch.setattr(Path, 'read_bytes', read)
    with pytest.raises(ValueError, match='artifact'):
        check(__import__('os').getpid(), '0'*64, tmp_path/'ready', tmp_path/'observations', 'DUMMY', 2000, 4096)
