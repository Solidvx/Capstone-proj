"""Measure IF-only normal false positives using three session-v2 captures.

Uses the runtime feature/window boundary; does not evaluate authentication,
attack types, rule attribution or blocking. No session keys are needed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from importlib.metadata import version
from pathlib import Path

from security.capture_normal import validate_session_splits
from security.ids.feature_extractor import FEATURE_NAMES
from security.ids.runtime import normal_vectors, train_model


def evaluate(train, train_manifest, calibrate, calibration_manifest, capture, manifest):
    splits = ((train, train_manifest), (calibrate, calibration_manifest), (capture, manifest))
    metadata = validate_session_splits(splits)
    model = train_model(train, calibrate, manifest_path=train_manifest,
                        calibration_manifest=calibration_manifest, protocol='session-v2')
    vectors = normal_vectors(capture, protocol='session-v2')
    scores = [model.anomaly(vector) for vector in vectors]
    if not scores or not all(math.isfinite(score) for score in scores):
        raise ValueError('IF evaluation requires finite nonempty scores')
    false_positives = sum(score > 0 for score in scores)
    root = Path(__file__).resolve().parents[2]
    # Bound evidence to the normal IF decision itself. A green execution status
    # is not a quality threshold or proof of deployed attack detection.
    return {
        'schema': 'session-if-normal-evaluation-v1',
        'status': 'COMPLETE' if len(scores) >= 100 else 'INSUFFICIENT_WINDOWS',
        'protocol': 'session-v2', 'environment': metadata[0]['environment'],
        'captures': {role: {'sha256': row['capture_sha256'], 'run_id': row['run_id'],
                           'duration_s': row['duration_s'], 'frames': row['accepted_frames']}
                     for role, row in zip(('fit', 'calibration', 'evaluation'), metadata)},
        'feature_names': FEATURE_NAMES, 'calibration': model.calibration,
        'model_parameters': model.model.get_params(),
        'runtime_versions': {'python': platform.python_version(),
                             'scikit-learn': version('scikit-learn'), 'numpy': version('numpy')},
        'evaluated_windows': len(scores), 'false_positive_windows': false_positives,
        'if_only_fpr': false_positives / len(scores),
        'adjusted_scores': scores, 'decision': 'adjusted_score > 0',
        'window_policy': 'runtime 1s trailing feature windows; 50ms replay ticks; no invented end padding',
        'official_acceptance': False,
        'not_measured': ['attack_detection_rate', 'attack_type_accuracy', 'blocking_rate',
                         'rules_if_incremental_contribution', 'live_authentication'],
        'source_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                          for name in ('security/experiments/evaluate_session_if.py',
                                       'security/capture_normal.py', 'security/ids/runtime.py',
                                       'security/ids/runtime_detector.py', 'security/ids/if_detector.py',
                                       'security/ids/feature_extractor.py')},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('train', 'train-manifest', 'calibrate', 'calibration-manifest',
                 'evaluate', 'evaluation-manifest', 'out'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args(argv)
    try:
        if Path(args.out).exists():
            raise ValueError('output must be a new file')
        report = evaluate(args.train, args.train_manifest, args.calibrate, args.calibration_manifest,
                          args.evaluate, args.evaluation_manifest)
        with Path(args.out).open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write('\n')
        print(json.dumps({key: report[key] for key in
                          ('status', 'environment', 'evaluated_windows', 'false_positive_windows', 'if_only_fpr')}))
        return 0 if report['status'] == 'COMPLETE' else 1
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print('Session IF evaluation stopped: ' + str(error))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
