import json
from unittest.mock import Mock

import pytest

from security.experiments import live_three_node as live
from security.experiments import live_three_node_test360 as test360
from security.tests.test_live_three_node import settings


def arguments(tmp_path):
    cfg = tmp_path / 'settings.json'
    cfg.write_text(json.dumps(settings()))
    key = tmp_path / 'dummy.key'
    key.write_bytes(bytes(32))
    return ['--settings', str(cfg), '--out', str(tmp_path / 'run'),
            '--run-id', 'test360', '--key', str(key), '--i-am-on-a-test-bus']


def test_schedules_30_per_case_and_labels_test_evidence(tmp_path, monkeypatch):
    argv = arguments(tmp_path)
    monkeypatch.setattr(live, 'inspect_interface', lambda *a: None)
    calls = []

    def run_case(settings, args, config, attack, root):
        calls.append((config, attack, args.trials))
        return 'COMPLETE'

    monkeypatch.setattr(live, 'run_case', run_case)
    monkeypatch.setattr(live, 'summarize_campaign', lambda root: {
        'planned_trials': 360, 'valid_trials': 360, 'complete_cases': 12})
    assert test360.main(argv) == 0
    assert len(calls) == len(set(calls)) == 12
    assert {n for _, _, n in calls} == {30}
    assert sum(n for _, _, n in calls) == 360
    campaign = json.loads((tmp_path / 'run/campaign.json').read_text())
    summary = json.loads((tmp_path / 'run/summary.json').read_text())
    assert campaign['stage'] == summary['stage'] == 'test360'
    assert campaign['trials'] == 30
    with pytest.raises(FileExistsError):
        test360.main(argv)


@pytest.mark.parametrize('flag', ['--stage', '--trials'])
def test_cannot_override_fixed_stage_or_count(tmp_path, flag):
    with pytest.raises(SystemExit) as exc:
        test360.main(arguments(tmp_path) + [flag, '100'])
    assert exc.value.code == 2
    assert not (tmp_path / 'run').exists()


def test_test_bus_confirmation_still_required(tmp_path):
    with pytest.raises(SystemExit) as exc:
        test360.main(arguments(tmp_path)[:-1])
    assert exc.value.code == 2
    assert not (tmp_path / 'run').exists()


@pytest.mark.parametrize('case_status,expected', [('ERROR', 2), ('INTERRUPTED', 130)])
def test_stops_remaining_cases_on_failure(tmp_path, monkeypatch, case_status, expected):
    monkeypatch.setattr(live, 'inspect_interface', lambda *a: None)
    runner = Mock(return_value=case_status)
    monkeypatch.setattr(live, 'run_case', runner)
    monkeypatch.setattr(live, 'summarize_campaign', lambda root: {'valid_trials': 0})
    assert test360.main(arguments(tmp_path)) == expected
    runner.assert_called_once()
    summary = json.loads((tmp_path / 'run/summary.json').read_text())
    assert summary['status'] == case_status
    assert summary['stage'] == 'test360'


def test_360_result_cannot_replace_official_pilot(tmp_path, monkeypatch):
    argv = arguments(tmp_path)
    pilot = tmp_path / 'test-result'
    pilot.mkdir()
    (pilot / 'campaign.json').write_text(json.dumps({'trials': 30, 'stage': 'test360'}))
    monkeypatch.setattr(live, 'summarize_campaign', lambda root: {
        'valid_trials': 12, 'complete_cases': 12})
    runner = Mock()
    monkeypatch.setattr(live, 'run_case', runner)
    with pytest.raises(SystemExit) as exc:
        live.main(argv + ['--stage', 'official', '--pilot-dir', str(pilot)])
    assert exc.value.code == 2
    runner.assert_not_called()


def test_invalid_trials_do_not_report_success(tmp_path, monkeypatch):
    monkeypatch.setattr(live, 'inspect_interface', lambda *a: None)
    monkeypatch.setattr(live, 'run_case', lambda *a: 'COMPLETE')
    monkeypatch.setattr(live, 'summarize_campaign', lambda root: {
        'planned_trials': 360, 'valid_trials': 359, 'complete_cases': 12})
    assert test360.main(arguments(tmp_path)) == 2
