"""IDS 하네스 스모크·회귀 테스트 (순수 Python, pytest 없이도 함수 직접 실행 가능).

합성 데이터에서 규칙 베이스라인이 최소 성능(AUC·볼륨형 탐지율)을 넘는지 고정 seed로
검증한다. 회귀 방지용 하한만 확인(정확한 값은 run_eval.py 출력 참조).
"""

from __future__ import annotations

import os
import random
import sys

_SEC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("ids", "attacks"):
    sys.path.insert(0, os.path.join(_SEC, sub))

from traffic_gen import ATTACKS, gen_attack, gen_normal  # noqa: E402
from feature_extractor import FEATURE_NAMES, extract, raw_windows, windows  # noqa: E402
from rule_baseline import RuleBaseline, metrics_at, roc_auc  # noqa: E402
from spec_detector import SpecDetector  # noqa: E402


def _fit_eval(seed: int = 42):
    rng = random.Random(seed)
    train = [v for v, _, _ in windows(gen_normal(90.0, rng))]
    model = RuleBaseline().fit(train)
    rows = list(windows(gen_normal(60.0, rng)))
    for atk in ATTACKS:
        rows += list(windows(gen_attack(atk, 30.0, rng)))
    scores = [model.score(v) for v, _, _ in rows]
    labels = [y for _, y, _ in rows]
    atypes = [a for _, _, a in rows]
    return model, scores, labels, atypes


def test_feature_vector_shape():
    rng = random.Random(1)
    frames = gen_normal(2.0, rng)
    vec = extract(frames)
    assert len(vec) == len(FEATURE_NAMES) == 7
    assert vec[0] > 0  # msg_rate


def test_baseline_auc_above_floor():
    _, scores, labels, _ = _fit_eval()
    auc = roc_auc(scores, labels)
    assert auc >= 0.75, f"AUC too low: {auc}"


def test_volumetric_attacks_detected():
    model, scores, labels, atypes = _fit_eval()
    # 정상 점수 99분위를 임계로
    ns = sorted(s for s, y in zip(scores, labels) if y == 0)
    thr = ns[int(0.99 * (len(ns) - 1))]
    m = metrics_at(scores, labels, atypes, thr)
    assert m["per_attack"].get("flooding", 0) >= 0.9
    assert m["per_attack"].get("fuzzy", 0) >= 0.9
    assert m["fpr"] <= 0.05


def _spec_eval(seed: int = 42):
    rng = random.Random(seed)
    spec = SpecDetector().fit(w for w, _, _ in raw_windows(gen_normal(90.0, rng)))
    per = {}
    fp = tn = 0
    def run(fw):
        nonlocal fp, tn
        for wf, y, at in fw:
            pred = spec.flag(wf)
            if y == 1:
                per.setdefault(at, [0, 0])
                per[at][0] += pred
                per[at][1] += 1
            elif pred:
                fp += 1
            else:
                tn += 1
    run(raw_windows(gen_normal(60.0, rng)))
    for atk in ATTACKS:
        run(raw_windows(gen_attack(atk, 30.0, rng)))
    return {a: h[0] / h[1] for a, h in per.items()}, fp / (fp + tn)


def test_spec_recovers_masquerade():
    """규칙이 놓친 masquerade를 사양기반이 회복하고 오탐은 낮게 유지."""
    _, r_scores, r_labels, r_atypes = _fit_eval()
    ns = sorted(s for s, y in zip(r_scores, r_labels) if y == 0)
    thr = ns[int(0.99 * (len(ns) - 1))]
    rule = metrics_at(r_scores, r_labels, r_atypes, thr)["per_attack"]
    spec, spec_fpr = _spec_eval()
    assert rule.get("masquerade", 1.0) < 0.5      # 규칙은 masquerade를 놓친다
    assert spec.get("masquerade", 0.0) >= 0.9     # 사양기반이 회복
    assert spec_fpr <= 0.05                        # 오탐 낮음
    for atk in ATTACKS:                            # 다른 공격도 유지
        assert spec.get(atk, 0.0) >= 0.9


def test_reproducibility_across_seeds():
    """멀티 seed에서 사양기반 masquerade 탐지가 안정적(편차 작음)."""
    vals = [_spec_eval(s)[0].get("masquerade", 0.0) for s in (42, 43, 44)]
    assert min(vals) >= 0.9


if __name__ == "__main__":
    test_feature_vector_shape()
    test_baseline_auc_above_floor()
    test_volumetric_attacks_detected()
    test_spec_recovers_masquerade()
    test_reproducibility_across_seeds()
    print("PASS: IDS 하네스 스모크·회귀 테스트 5건")
