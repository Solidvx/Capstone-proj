from pathlib import Path
import json

import pytest

from tools.quality.sensor_checks import Checks, run, validate
from tools.quality import sensor_scenarios as source


def policy():
    return dict(schema='synthetic-sensor-checks-v1', voltage_tolerance_v=.01,
                current_tolerance_a=.1, max_voltage_step_v=.5, freeze_hold_s=1.,
                freeze_tolerance_v=.00001, minimum_expected_change_v=.0001)


def test_constant_input_is_allowed_but_frozen_changing_reference_is_logged():
    fixed, frozen = Checks(policy()), Checks(policy())
    for index in range(30):
        assert fixed.observe(index / 10, 40, -2, 40, -2) == []
        reasons = frozen.observe(index / 10, 40, -2, 40 + index * .0001, -2)
    assert reasons == ['VOLTAGE_FROZEN_AGAINST_PROFILE']


def test_jump_and_current_model_mismatch_are_separate_sensor_reasons():
    checks = Checks(policy())
    assert checks.observe(0, 40, -2, 40, -2) == []
    assert set(checks.observe(.1, 35, 2, 40, -2)) == {
        'VOLTAGE_PROFILE_MISMATCH', 'CURRENT_PROFILE_MISMATCH', 'VOLTAGE_JUMP'}


@pytest.mark.parametrize('value', [True, 0, -1, float('nan'), float('inf'), 10**1000])
def test_no_implicit_or_nonfinite_thresholds(value):
    p = policy(); p['freeze_hold_s'] = value
    with pytest.raises(ValueError): validate(p)


def test_clock_and_nonfinite_inputs_are_not_sensor_findings():
    checks = Checks(policy()); checks.observe(1, 40, -2, 40, -2)
    for t, v in [(1, 40), (.5, 40), (2, float('nan'))]:
        with pytest.raises(ValueError): checks.observe(t, v, -2, 40, -2)


def native_fixture(root):
    settings = dict(schema='sensor-source-supplement-v1', samples=30, event_start=5,
                    event_end=25, drift_final_bias_v=-.5, jump_bias_v=-6., mismatch_current_bias_a=4.)
    source.generate(root, settings)
    for case in source.CASES:
        lines = [','.join(source.PRED + ['bms_payload_hex'])]
        for i in range(settings['samples']):
            (v, c, _), _label = source.sample(settings, case, i)
            lines.append(f'{(i+1)*.1:.10f},{v:.17g},{c:.17g},80,80,0000000000000000')
        (root / case / 'native.csv').write_text('\n'.join(lines) + '\n')
    report = dict(schema='sensor-source-evaluation-v1', status='COMPLETE', settings=settings,
                  inputs_sha256=source.sha256(root/'inputs.json'),
                  files_sha256={case+'/native.csv': source.sha256(root/case/'native.csv') for case in source.CASES})
    (root/'report.json').write_text(json.dumps(report))


def test_run_retains_details_and_never_labels_a_CAN_attack(tmp_path):
    root = tmp_path/'input'; native_fixture(root)
    result = run(root, tmp_path/'output', policy())
    assert result['status'] == 'COMPLETE'
    assert not result['runtime_enabled'] and not result['labels_used_by_checks']
    assert result['cases'][1]['reason_counts'] == {}
    rows = [json.loads(row) for row in (tmp_path/'output/voltage_jump.jsonl').read_text().splitlines()]
    assert any('VOLTAGE_JUMP' in row['reasons'] for row in rows)
    assert all(row['can_attack_type'] is None and row['severity'] == 'log-only' for row in rows)
    with pytest.raises(FileExistsError): run(root, tmp_path/'output', policy())


def test_changed_and_truncated_native_input_cannot_pass(tmp_path):
    root = tmp_path/'input'; native_fixture(root)
    path = root/'voltage_jump/native.csv'; path.write_text(path.read_text().splitlines()[0]+'\n')
    with pytest.raises(ValueError, match='changed'): run(root, tmp_path/'output', policy())
    report = json.loads((root/'report.json').read_text())
    report['files_sha256']['voltage_jump/native.csv'] = source.sha256(path)
    (root/'report.json').write_text(json.dumps(report))
    assert run(root, tmp_path/'output', policy())['status'] == 'INVALID'
