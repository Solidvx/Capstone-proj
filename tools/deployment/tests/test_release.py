"""Private temporary release roots and public dummy ELF only; no service changes."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import pytest

from tools.deployment.release import current, deploy, hook, inspect_release, policy, stage


def bundle(tmp_path, revision):
    source = tmp_path/revision;source.mkdir();(source/'bin').mkdir()
    files = {}
    for name in ('adaptive_ecu', 'ivi_dashboard'):
        data = bytearray(20);data[:6] = b'\x7fELF\x02\x01';data[18:20] = b'\xb7\x00'
        data.extend(revision.encode());path = source/'bin'/name;path.write_bytes(data)
        files['bin/'+name] = {'sha256': hashlib.sha256(data).hexdigest(), 'mode': 0o555}
    (source/'release.json').write_text(json.dumps({'schema': 'capstone-release-v1', 'revision': revision, 'files': files}))
    return source


@pytest.fixture
def setup(tmp_path):
    script = tmp_path/'public-hook.py';calls = tmp_path/'calls.jsonl';failure = tmp_path/'failure.json'
    script.write_text('''import json,pathlib,sys
operation,target,calls,failure=sys.argv[1:]
record={'operation':operation,'target':target}
with pathlib.Path(calls).open('a') as f:f.write(json.dumps(record)+'\\n')
errors=json.loads(pathlib.Path(failure).read_text()) if pathlib.Path(failure).exists() else []
raise SystemExit(7 if operation in errors else 0)
''')
    hooks = {name: [sys.executable, str(script), name, '{release}', str(calls), str(failure)]
             for name in ('activate', 'health', 'deactivate')}
    hooks['timeout_s'] = 5
    return tmp_path/'installed', hooks, calls, failure


def test_success_is_exact_immutable_hash_and_same_release_no_restart(tmp_path, setup):
    root, hooks, calls, _ = setup;source = bundle(tmp_path, 'first')
    result = deploy(root, source, hooks)
    assert result['status'] == 'COMMITTED'
    identity, manifest = inspect_release(current(root))
    assert identity == result['release']
    assert all((current(root)/name).stat().st_mode & 0o777 == item['mode'] for name, item in manifest['files'].items())
    assert deploy(root, source, hooks)['status'] == 'UNCHANGED'
    assert len(calls.read_text().splitlines()) == 3
    assert json.loads(calls.read_text().splitlines()[-1])['operation'] == 'health'


def test_failed_health_restores_prior_binary_and_reports_rollback_failure(tmp_path, setup):
    root, hooks, calls, failure = setup
    first = deploy(root, bundle(tmp_path, 'first'), hooks)['release']
    failure.write_text(json.dumps(['health']))
    result = deploy(root, bundle(tmp_path, 'second'), hooks)
    assert result['status'] == 'ROLLBACK_FAILED' and current(root).name == first
    assert 'health' in result['activation_error'] and 'health' in result['rollback_error']
    with pytest.raises(ValueError, match='pending'):deploy(root, bundle(tmp_path, 'third'), hooks)
    failure.unlink()
    assert deploy(root, None, hooks, recover=True)['status'] == 'ROLLED_BACK'
    assert current(root).name == first
    assert [json.loads(row)['operation'] for row in calls.read_text().splitlines()][-2:] == ['activate', 'health']


def test_failed_new_health_rolls_back_and_old_health_must_pass(tmp_path, setup):
    root, hooks, _, _ = setup
    first = deploy(root, bundle(tmp_path, 'first'), hooks)['release']
    second = bundle(tmp_path, 'second');bad_id = inspect_release(second)[0]
    check = tmp_path/'selective-health.py'
    check.write_text('import pathlib,sys;raise SystemExit(8 if pathlib.Path(sys.argv[1]).name==sys.argv[2] else 0)')
    hooks['health'] = [sys.executable, str(check), '{release}', bad_id]
    result = deploy(root, second, hooks)
    assert result['status'] == 'ROLLED_BACK' and current(root).name == first
    assert result['release'] == bad_id and result['previous'] == first


def test_initial_failure_deactivates_and_does_not_claim_healthy(tmp_path, setup):
    root, hooks, calls, failure = setup;failure.write_text('["activate"]')
    result = deploy(root, bundle(tmp_path, 'first'), hooks)
    assert result['status'] == 'ROLLED_BACK' and current(root) is None
    assert json.loads(calls.read_text().splitlines()[-1])['operation'] == 'deactivate'


def test_interrupted_switch_requires_explicit_recovery_and_keeps_runtime_state(tmp_path, setup):
    root, hooks, _, _ = setup
    first = deploy(root, bundle(tmp_path, 'first'), hooks)['release']
    runtime = tmp_path/'public-dummy-state';runtime.write_bytes(b'counter-and-checkpoint-preserved')
    second = stage(root, bundle(tmp_path, 'second'))
    row = {'schema': 'release-transaction-v1', 'status': 'PENDING', 'previous': first, 'release': second.name}
    (root/'transaction.json').write_text(json.dumps(row))
    (root/'current').unlink();(root/'current').symlink_to('releases/'+second.name)
    with pytest.raises(ValueError, match='pending'):deploy(root, bundle(tmp_path, 'third'), hooks)
    assert deploy(root, None, hooks, recover=True)['status'] == 'ROLLED_BACK'
    assert current(root).name == first and runtime.read_bytes() == b'counter-and-checkpoint-preserved'


@pytest.mark.parametrize('corruption', ['hash', 'symlink', 'extra', 'traversal', 'architecture', 'mode'])
def test_bad_artifacts_rejected_before_any_service_hook(tmp_path, setup, corruption):
    root, hooks, calls, _ = setup;source = bundle(tmp_path, 'candidate')
    manifest = json.loads((source/'release.json').read_text())
    if corruption == 'hash':(source/'bin/adaptive_ecu').write_bytes(b'changed')
    elif corruption == 'symlink':
        path = source/'bin/adaptive_ecu';path.unlink();path.symlink_to(source/'bin/ivi_dashboard')
    elif corruption == 'extra':(source/'unlisted').write_text('unexpected')
    elif corruption == 'traversal':manifest['files']['../outside'] = manifest['files']['bin/adaptive_ecu']
    elif corruption == 'mode':manifest['files']['bin/adaptive_ecu']['mode'] = 0o777
    else:
        path = source/'bin/adaptive_ecu';path.write_bytes(b'not-arm64')
        manifest['files']['bin/adaptive_ecu']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    (source/'release.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError):deploy(root, source, hooks)
    assert not calls.exists() and not (root/'current').exists()


def test_policy_has_no_operating_account_or_time_defaults():
    with pytest.raises(ValueError):policy({})
    with pytest.raises(ValueError):policy({'activate': ['sh'], 'health': ['/bin/true'], 'deactivate': ['/bin/true'], 'timeout_s': 5})


def test_timeout_does_not_leave_hook_descendants_running(tmp_path):
    marker = tmp_path/'must-not-appear'
    script = tmp_path/'timeout.py'
    script.write_text('import os,pathlib,sys,time\nif os.fork()==0:\n time.sleep(1.5);pathlib.Path(sys.argv[1]).write_text("orphan")\ntime.sleep(30)\n')
    settings = {'activate': [sys.executable, str(script), str(marker)], 'timeout_s': 1}
    with pytest.raises(RuntimeError, match='timed out'):hook(settings, 'activate', None)
    time.sleep(.7)
    assert not marker.exists()


def test_corrupt_journal_cannot_select_path_outside_releases(tmp_path, setup):
    root, hooks, calls, _ = setup
    deploy(root, bundle(tmp_path, 'first'), hooks)
    count = len(calls.read_text().splitlines())
    (root/'transaction.json').write_text(json.dumps({'schema': 'release-transaction-v1',
        'status': 'PENDING', 'release': 'a'*64, 'previous': '../runtime-state'}))
    with pytest.raises(ValueError, match='journal'):deploy(root, None, hooks, recover=True)
    assert len(calls.read_text().splitlines()) == count


def test_changed_installed_permissions_are_not_silently_reused(tmp_path, setup):
    root, hooks, _, _ = setup;source = bundle(tmp_path, 'first')
    deploy(root, source, hooks);installed = current(root)
    (installed/'bin/adaptive_ecu').chmod(0o777)
    with pytest.raises(ValueError, match='permissions'):deploy(root, source, hooks)


def test_same_release_still_requires_healthy_live_data(tmp_path, setup):
    root, hooks, calls, failure = setup;source = bundle(tmp_path, 'first')
    deploy(root, source, hooks);failure.write_text('["health"]')
    with pytest.raises(RuntimeError, match='health'):deploy(root, source, hooks)
    operations = [json.loads(row)['operation'] for row in calls.read_text().splitlines()]
    assert operations == ['activate', 'health', 'health']
