"""Read-only diagnostic of the preserved synthetic IF smoke; no tuning."""
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import sklearn
from security.experiments.evaluate_normal import evaluate, load_capture
from security.ids.feature_extractor import FEATURE_NAMES
from security.ids.if_detector import IsolationForestDetector
from security.ids.runtime import train_model

root = Path('tmp/chg014-if')
captured = []
original_fit = IsolationForestDetector.fit


def record_fit(self, vectors):
    captured.extend(vectors)
    return original_fit(self, vectors)


class Recorder:
    def __init__(self, model):
        self.model = model
        self.rows = []

    def anomaly(self, vector):
        score = self.model.anomaly(vector)
        self.rows.append({'vector': vector, 'anomaly': score})
        return score

    def wire_score(self, vector):
        return self.model.wire_score(vector)


with patch.object(IsolationForestDetector, 'fit', record_fit):
    model = train_model(root / 'train/frames.jsonl')
train = np.array(captured)
key = (root / 'dummy.bin').read_bytes()
report = {'sklearn': sklearn.__version__, 'training_vectors': len(train),
          'training_negative_decisions': int(sum(model.model.decision_function(train) < 0)),
          'captures': {}}
for name in ('train', 'eval'):
    frames, manifest, _ = load_capture(root / name)
    recorder = Recorder(model)
    result = evaluate(frames, manifest['duration_s'], model=recorder, key=key)
    vectors = np.array([r['vector'] for r in recorder.rows])
    bad = np.array([r['anomaly'] > 0 for r in recorder.rows])
    stats = []
    for i, feature in enumerate(FEATURE_NAMES):
        lo, hi = train[:, i].min(), train[:, i].max()
        outside = (vectors[:, i] < lo) | (vectors[:, i] > hi)
        stats.append({'feature': feature, 'train_min': float(lo), 'train_max': float(hi),
                      'runtime_min': float(vectors[:, i].min()), 'runtime_max': float(vectors[:, i].max()),
                      'outside_train_range': int(outside.sum()),
                      'outside_and_anomalous': int((outside & bad).sum())})
    report['captures'][name] = {'sha256': manifest['sha256'],
        'status': result['status'], 'fp_windows': result['false_positive_windows'],
        'complete_windows': result['complete_windows'], 'reasons': result['reasons'],
        'runtime_checks_including_warmup': len(vectors),
        'anomalous_checks_including_warmup': int(bad.sum()), 'features': stats,
        'fp_window_indices': [w['window'] for w in result['windows'] if w['reasons']]}
old = json.loads((root / 'report.json').read_text())['results'][1]
new = report['captures']['eval']
assert new['fp_windows'] == old['false_positive_windows'] == 16
assert new['complete_windows'] == old['complete_windows'] == 108
assert new['reasons'] == old['reasons']
out = Path('tmp/chg014-if-diagnosis.json')
with out.open('x', encoding='utf-8') as stream:
    json.dump(report, stream, indent=2)
print(json.dumps(report, indent=2))
