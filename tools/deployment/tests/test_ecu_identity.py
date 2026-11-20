import hashlib
import json
import os

import pytest

from tools.deployment import ecu_identity as identity


@pytest.fixture
def process(tmp_path, monkeypatch):
    folder = tmp_path/'proc';folder.mkdir();(folder/'fdinfo').mkdir();(folder/'fd').mkdir()
    executable = b'public dummy executable';(folder/'exe').write_bytes(executable)
    (folder/'cmdline').write_bytes(b'/dummy\0--protocol\0session-v2\0--secoc\0on\0--interface\0vcan0\0')
    record = {'result': 'ECU_INPUT_LINEAGE', 'schema': 'ecu-input-lineage-v1',
              'instance_id': '112233445566478899aabbccddeeff00'}
    output = tmp_path/'stdout';output.write_text(json.dumps(record)+'\n');output.chmod(0o600)
    os.link(output, folder/'fd/1')
    (folder/'fdinfo/1').write_text('pos:\t'+str(output.stat().st_size)+'\nflags:\t01\n')
    monkeypatch.setattr(identity, 'process_identity', lambda _: (folder, '100', os.getuid()))
    return folder, output, record, hashlib.sha256(executable).hexdigest()


def test_exact_executable_and_process_owned_lineage_require_fresh_peer_binding(process):
    _, output, record, expected = process
    result = identity.check(123, expected, output, 4096)
    assert result['status'] == 'IDENTIFIED' and result['instance_id'] == record['instance_id']
    health = {'status': 'PASS', 'ecu_instance_id': record['instance_id'], 'interface': 'vcan0', 'artifact_sha256': 'b'*64}
    assert identity.bind(health, result)['status'] == 'PASS'
    # Names are node-local: can0 on one host may connect to can1 on the other.
    assert identity.bind(dict(health, interface='can1'), result)['status'] == 'PASS'
    for patch in ({'ecu_instance_id': 'OTHER'}, {'interface': ''}, {'status': 'FAIL'}, {'artifact_sha256': None}):
        with pytest.raises(ValueError):identity.bind(dict(health, **patch), result)


@pytest.mark.parametrize('bad', ['hash', 'append', 'old-output', 'not-ready', 'partial', 'duplicate',
                                  'instance', 'protocol', 'protection', 'permissions'])
def test_live_process_or_an_old_log_is_not_new_ecu_identity(process, bad):
    folder, output, record, expected = process
    if bad == 'hash':expected = '0'*64
    elif bad == 'append':(folder/'fdinfo/1').write_text('pos:\t1\nflags:\t02001\n')
    elif bad == 'old-output':
        old = output.parent/'old';old.write_text(output.read_text());old.chmod(0o600);output = old
    elif bad == 'not-ready':(folder/'fdinfo/1').write_text('pos:\t0\nflags:\t01\n')
    elif bad in ('partial', 'duplicate', 'instance'):
        if bad == 'partial':output.write_text(json.dumps(record))
        elif bad == 'duplicate':output.write_text((json.dumps(record)+'\n')*2)
        else:record['instance_id'] = '0'*32;output.write_text(json.dumps(record)+'\n')
        (folder/'fdinfo/1').write_text('pos:\t'+str(output.stat().st_size)+'\nflags:\t01\n')
    elif bad in ('protocol', 'protection'):
        data = (folder/'cmdline').read_bytes().replace(b'session-v2', b'legacy-v1') if bad == 'protocol' else (folder/'cmdline').read_bytes().replace(b'\0on\0', b'\0off\0')
        (folder/'cmdline').write_bytes(data)
    else:output.chmod(0o666)
    with pytest.raises(ValueError):identity.check(123, expected, output, 4096)


def test_pid_reuse_during_ecu_read_is_rejected(process, monkeypatch):
    folder, output, _, expected = process;starts = iter(('100', '101'))
    monkeypatch.setattr(identity, 'process_identity', lambda _: (folder, next(starts), os.getuid()))
    with pytest.raises(ValueError, match='changed'):identity.check(123, expected, output, 4096)
