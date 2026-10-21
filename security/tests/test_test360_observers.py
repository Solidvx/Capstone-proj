import io
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from security.experiments import can_health, trial_observer
from security.experiments.run_ablation import Child


def test_observer_drains_old_phase_then_ack_and_stops_on_eof(monkeypatch, capsys):
    frame = SimpleNamespace(t=0, can_id=123, data=bytes(1), dlc=1, extended=False, remote=False, error=False)
    bus = Mock(dropped=0)
    bus.receive.side_effect = [(frame, False), None, None]
    monkeypatch.setattr(trial_observer, 'healthy', lambda c: None)
    monkeypatch.setattr(trial_observer, 'CaptureSocket', lambda c: bus)
    monkeypatch.setattr(trial_observer.select, 'select', lambda *a: ([0], [], []))
    monkeypatch.setattr(trial_observer.os, 'read', Mock(side_effect=[b'{"phase":"attack"}\n', b'']))
    trial_observer.observe('can0', 10, 'dummy')
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [r['result'] for r in rows] == ['READY', 'OBS_FRAME', 'PHASE', 'OBSERVER_STOPPED']
    assert rows[1]['phase'] == 'idle' and rows[2]['phase'] == 'attack'
    bus.close.assert_called_once()


@pytest.mark.parametrize('state,expected_calls', [('ERROR-ACTIVE', 1), ('BUS-OFF', 4)])
def test_health_resets_only_failed_can(monkeypatch, state, expected_calls):
    value = [{'flags':['UP'], 'linkinfo': {'info_kind':'can','info_data': {
        'state':state,'bittiming':{'bitrate':500000}, 'ctrlmode':[]}}}]
    run = Mock(return_value=SimpleNamespace(stdout=json.dumps(value)))
    monkeypatch.setattr(can_health.subprocess, 'run', run)
    monkeypatch.setattr(can_health, 'inspect_interface', lambda *a: {'state':'ERROR-ACTIVE','bitrate':500000})
    result = can_health.check('can0', recover=True)
    assert run.call_count == expected_calls
    assert result['reset'] == (state == 'BUS-OFF')


def test_health_wrong_bitrate_does_not_reset(monkeypatch):
    value = [{'flags':['UP'], 'linkinfo': {'info_kind':'can','info_data': {'bittiming':{'bitrate':250000}}}}]
    run = Mock(return_value=SimpleNamespace(stdout=json.dumps(value)))
    monkeypatch.setattr(can_health.subprocess, 'run', run)
    with pytest.raises(ValueError, match='bitrate'):can_health.check('can0', recover=True)
    assert run.call_count == 1


def test_log_storage_failure_surfaces_to_controller():
    child = Child.__new__(Child)
    child.process = SimpleNamespace(stdout=io.StringIO('{}\n'))
    child.output = Mock(); child.output.write.side_effect = OSError('disk full')
    child._read()
    with pytest.raises(OSError, match='disk full'):child.snapshot()
