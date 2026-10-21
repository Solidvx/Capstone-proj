import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from security.experiments import live_three_node as live
from security.experiments import live_three_node_test360 as test360
from security.experiments import test360_support as support


def settings():
    path = Path(__file__).parents[1] / 'experiments/live-three-node-test360-settings.template.json'
    return json.loads(path.read_text().replace('REPLACE_', 'test_'))


def arguments(tmp_path):
    cfg = tmp_path / 'settings.json'
    cfg.write_text(json.dumps(settings()))
    key = tmp_path / 'dummy.key'
    key.write_bytes(bytes(32))
    return ['--settings', str(cfg), '--out', str(tmp_path / 'run'),
            '--run-id', 'test360', '--key', str(key), '--i-am-on-a-test-bus']


def install_fake(monkeypatch, outcomes=None):
    calls = []
    outcomes = iter(outcomes or [])
    def run(settings, args, config, attack, root):
        root.mkdir()
        status, valid, recoverable = next(outcomes, ('COMPLETE', True, False))
        calls.append((config, attack, args.start_trial))
        manifest = {'status': status, 'cleanup_confirmed': True, 'recoverable': recoverable}
        row = {'status': 'VALID' if valid else 'INVALID', 'ivi_type_result': 'MATCH' if config == 3 else 'NOT_EVALUATED'}
        (root/'manifest.json').write_text(json.dumps(manifest))
        (root/'attempts.jsonl').write_text(json.dumps(row)+'\n')
        return status
    def read(root):
        return json.loads((root/'manifest.json').read_text()), [json.loads((root/'attempts.jsonl').read_text())]
    monkeypatch.setattr(live, 'run_case', run)
    monkeypatch.setattr(live, 'read_run', read)
    health = Mock()
    monkeypatch.setattr(test360, 'check_health', health)
    return calls, health


def test_360_independent_trials_continue_invalid_and_resume_skips_all(tmp_path, monkeypatch):
    calls, _ = install_fake(monkeypatch, [('COMPLETE', False, False)])
    argv = arguments(tmp_path)
    assert test360.main(argv) == 2
    assert len(calls) == len(set(calls)) == 360
    result = json.loads((tmp_path/'run/summary.json').read_text())
    assert result['completed_trials'] == 360
    assert result['valid_trials'] == 359
    assert result['invalid_trials'] == 1
    assert test360.main(argv+['--resume']) == 2
    assert len(calls) == 360


def test_recoverable_failure_is_preserved_and_retried(tmp_path, monkeypatch):
    calls, health = install_fake(monkeypatch, [('ERROR', False, True)])
    assert test360.main(arguments(tmp_path)) == 0
    assert len(calls) == 361 and calls[0] == calls[1]
    assert health.call_count == 2
    assert health.call_args.kwargs == {'recover': True}
    result = json.loads((tmp_path/'run/summary.json').read_text())
    assert result['attempts_including_retries'] == 361


def test_retry_budget_and_resume_pending(tmp_path, monkeypatch):
    calls, health = install_fake(monkeypatch, [('ERROR', False, True)]*3)
    argv = arguments(tmp_path)
    assert test360.main(argv) == 2
    assert len(calls) == 3 and health.call_count == 3
    assert test360.main(argv+['--resume']) == 0
    assert len(calls) == 363


@pytest.mark.parametrize('status,code', [('ERROR', 2), ('INTERRUPTED', 130)])
def test_terminal_or_interrupt_does_not_retry(tmp_path, monkeypatch, status, code):
    calls, health = install_fake(monkeypatch, [(status, False, False)])
    assert test360.main(arguments(tmp_path)) == code
    assert len(calls) == health.call_count == 1


def test_resume_rejects_changed_settings_and_unsealed_attempt(tmp_path, monkeypatch):
    calls, health = install_fake(monkeypatch, [('ERROR', False, False)])
    argv = arguments(tmp_path)
    assert test360.main(argv) == 2
    campaign = tmp_path/'run/campaign.json'
    original = campaign.read_text()
    campaign.write_text('{}')
    with pytest.raises(SystemExit):test360.main(argv+['--resume'])
    campaign.write_text(original)
    next((tmp_path/'run').glob('C*/trial-*/attempt-*/manifest.json')).unlink()
    assert test360.main(argv+['--resume']) == 2
    assert len(calls) == health.call_count == 1


@pytest.mark.parametrize('flag', ['--stage', '--trials'])
def test_fixed_count_and_stage(tmp_path, flag):
    with pytest.raises(SystemExit):test360.main(arguments(tmp_path)+[flag, '100'])


def test_test_bus_required(tmp_path):
    with pytest.raises(SystemExit):test360.main(arguments(tmp_path)[:-1])


def test_template_and_supervisor_run_id():
    cfg = settings()
    support.validate_extra(cfg, live.validate_settings(cfg))
    cfg['ids'][-1] = cfg['ids'][-1].replace('remote_process --run-id {run_id}', 'remote_process')
    with pytest.raises(ValueError, match='cleanup'):support.validate_extra(cfg, live.validate_settings(cfg))


@pytest.mark.parametrize('codes,expected', [([], 'MISSED'), ([1], 'MISMATCH'), ([4], 'MATCH'), ([1,4], 'COMPOUND')])
def test_type_classification(codes, expected):
    assert support.classification(codes, 4) == expected


def test_local_echo_alone_does_not_prove_remote_arrival():
    row = {'config': 3, 'status': 'VALID', 'expected_attack_code': 4,
           'observed_attack_codes': [4], 'ivi_published_attack_codes': [4]}
    observer = Mock(); observer.snapshot.return_value = []
    support.add_evidence(row, [SimpleNamespace(own=True, can_id=0, data=bytes(8))], [observer, observer])
    assert row['status'] == row['ivi_type_result'] == 'INVALID'


def test_remote_arrival_and_compound_are_distinct():
    row = {'config': 3, 'status': 'VALID', 'expected_attack_code': 4,
           'observed_attack_codes': [4], 'ivi_published_attack_codes': [1,4]}
    observer = Mock();observer.snapshot.return_value = [{'result':'OBS_FRAME', 'phase':'attack', 'can_id':0, 'data':bytes(8).hex()}]
    support.add_evidence(row, [SimpleNamespace(own=True, can_id=0, data=bytes(8))], [observer, observer])
    assert row['status'] == 'VALID'
    assert row['ivi_type_result'] == 'COMPOUND'
    assert row['remote_arrival']['ecu']['matching_frames'] == 1


@pytest.mark.parametrize('error', [OSError('disk full'), ValueError('bad key'), RuntimeError('clock changed'), RuntimeError('child exited before READY')])
def test_unknown_or_configuration_or_storage_errors_not_retried(error):
    assert not support.recoverable(error)


def test_cleanup_uncertain_cannot_resume(tmp_path, monkeypatch):
    path = tmp_path/'attempt-001';path.mkdir()
    (path/'manifest.json').write_text('{}')
    monkeypatch.setattr(live, 'read_run', lambda p: ({'cleanup_confirmed': False}, []))
    with pytest.raises(ValueError, match='cleanup unconfirmed'):test360.attempts(tmp_path)
