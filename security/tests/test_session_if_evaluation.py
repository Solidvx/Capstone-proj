"""Synthetic capture fixtures test the evaluator, not physical IF performance."""
import hashlib
import json
from unittest.mock import patch

import pytest

from security.capture_normal import validate_session_splits
from security.experiments.evaluate_session_if import evaluate, main
from security.ids.runtime import train_model
from security.ids.session_detector import SESSION_IDS


def capture(root, name, ordinal, duration=104):
    path, manifest = root / (name + '.jsonl'), root / (name + '.manifest.json')
    rows = []
    for i in range(duration * 10):
        rows.append({'t': i * .1, 'can_id': 0x100, 'data': '64c80f3cffec4100'})
        # Dummy auth data: this tool measures features, not authentication.
        rows.append({'t': i * .1 + .002, 'can_id': 0x102,
                     'data': ((ordinal << 32) + i).to_bytes(8, 'big').hex()})
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    manifest.write_text(json.dumps({'schema': 'ids-normal-v2', 'status': 'COMPLETE',
        'protocol': 'session-v2', 'environment': 'vcan', 'run_id': name,
        'started_epoch_ns': ordinal * 200_000_000_000, 'duration_s': duration,
        'allowed_ids': sorted(SESSION_IDS), 'accepted_frames': len(rows), 'rejected_frames': 0,
        'capture_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))
    return path, manifest


def change(path, **values):
    row = json.loads(path.read_text()); row.update(values); path.write_text(json.dumps(row))


@pytest.mark.parametrize('damage', ['duplicate', 'same_run', 'overlap', 'environment', 'missing_time', 'bad_hash'])
def test_mixed_or_reused_session_training_is_rejected_before_fit(tmp_path, damage):
    first = capture(tmp_path, 'fit', 1, 4)
    second = capture(tmp_path, 'calibration', 2, 4)
    if damage == 'duplicate':
        second = first
    elif damage == 'same_run': change(second[1], run_id='fit')
    elif damage == 'overlap': change(second[1], started_epoch_ns=201_000_000_000)
    elif damage == 'environment': change(second[1], environment='physical-can')
    elif damage == 'missing_time': change(second[1], started_epoch_ns=None)
    elif damage == 'bad_hash': change(second[1], capture_sha256='0' * 64)
    with patch('security.ids.runtime.IsolationForestDetector') as model:
        with pytest.raises(ValueError):
            train_model(first[0], second[0], manifest_path=first[1],
                        calibration_manifest=second[1], protocol='session-v2')
        model.assert_not_called()


def test_real_if_heldout_report_and_cli_keep_scope_and_preserve_output(tmp_path):
    splits = [capture(tmp_path, name, i) for i, name in enumerate(('fit', 'calibration', 'evaluation'), 1)]
    report = evaluate(*(path for pair in splits for path in pair))
    assert report['status'] == 'COMPLETE'
    assert report['environment'] == 'vcan' and report['official_acceptance'] is False
    assert report['evaluated_windows'] >= 100
    assert report['calibration']['windows'] >= 99
    assert 0 <= report['if_only_fpr'] <= 1
    assert len(report['adjusted_scores']) == report['evaluated_windows']
    assert 'rules_if_incremental_contribution' in report['not_measured']
    assert set(report['captures']) == {'fit', 'calibration', 'evaluation'}
    assert len(set(row['sha256'] for row in report['captures'].values())) == 3
    assert len(report['source_sha256']) == 6
    assert report['model_parameters']['random_state'] == 42
    assert report['model_parameters']['n_estimators'] == 100
    assert set(report['runtime_versions']) == {'python', 'scikit-learn', 'numpy'}
    output = tmp_path / 'report.json'; output.write_text('existing evidence')
    names = ('train', 'train-manifest', 'calibrate', 'calibration-manifest', 'evaluate', 'evaluation-manifest')
    args = [value for name, path in zip(names, (p for pair in splits for p in pair))
            for value in ('--' + name, str(path))]
    assert main(args + ['--out', str(output)]) == 2
    assert output.read_text() == 'existing evidence'


def test_nonfinite_model_scores_cannot_be_reported_as_zero_false_positives(tmp_path):
    splits = [capture(tmp_path, name, i, 4) for i, name in enumerate(('fit', 'calibration', 'evaluation'), 1)]
    with patch('security.experiments.evaluate_session_if.train_model') as factory:
        factory.return_value.anomaly.return_value = float('nan')
        with pytest.raises(ValueError, match='finite'):
            evaluate(*(path for pair in splits for path in pair))


def test_evaluation_leakage_and_missing_independence_are_not_quality_results(tmp_path):
    first, second = capture(tmp_path, 'fit', 1, 4), capture(tmp_path, 'calibration', 2, 4)
    with patch('security.experiments.evaluate_session_if.train_model') as model:
        with pytest.raises(ValueError, match='independent'):
            evaluate(*first, *second, *first)
        model.assert_not_called()
    with pytest.raises(ValueError, match='at least two'):
        validate_session_splits([first])
