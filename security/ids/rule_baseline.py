"""규칙기반 IDS 베이스라인 (순수 Python, 통계 임계).

정상 윈도우로 특징별 mean/std를 학습하고, 방향성 z-score의 최댓값을 이상 점수로
사용한다. "왜 ML(Isolation Forest)인가"를 정량 비교할 산업 표준 베이스라인.
공격은 대체로 특징을 증가시키므로(단 mean_iat는 감소) 방향을 반영한다.
"""

from __future__ import annotations

import math
from numbers import Integral, Real

if __package__:
    from .feature_extractor import FEATURE_NAMES
else:
    from feature_extractor import FEATURE_NAMES

# +1: 값이 커지면 이상, -1: 값이 작아지면 이상(정상 대비)
_DIRECTION = {
    "msg_rate": +1, "mean_iat": -1, "std_iat": +1, "unique_ids": +1,
    "id_entropy": +1, "payload_change": +1, "max_id_burst": +1,
}


class RuleBaseline:
    def __init__(self) -> None:
        self.mean: list[float] = []
        self.std: list[float] = []

    def fit(self, normal_vectors: list[list[float]]) -> "RuleBaseline":
        n = len(normal_vectors)
        cols = list(zip(*normal_vectors))
        self.mean = [sum(c) / n for c in cols]
        self.std = [
            max(math.sqrt(sum((x - m) ** 2 for x in c) / n), 1e-9)
            for c, m in zip(cols, self.mean)
        ]
        return self

    def score(self, vec: list[float]) -> float:
        """방향성 z-score의 최댓값(연속 이상 점수)."""
        best = 0.0
        for i, name in enumerate(FEATURE_NAMES):
            z = (vec[i] - self.mean[i]) / self.std[i] * _DIRECTION[name]
            best = max(best, z)
        return best


def confusion_metrics(tp: int, fp: int, tn: int, fn: int) -> dict:
    """같은 판단 단위의 원수 → ratio 지표. 분모0은 None(N/A)."""
    counts = {"tp": tp, "fp": fp, "tn": tn, "fn": fn}
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError("confusion counts must be nonnegative integers")
    normal, attack = fp + tn, tp + fn
    def ratio(numerator, denominator):
        return numerator / denominator if denominator else None
    recall, tnr = ratio(tp, attack), ratio(tn, normal)
    mcc_denominator = (tp + fp) * attack * normal * (tn + fn)
    return {
        **counts,
        "precision": ratio(tp, tp + fp), "recall": recall,
        "fpr": ratio(fp, normal), "fnr": ratio(fn, attack), "tnr": tnr,
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
        "balanced_accuracy": (recall + tnr) / 2 if attack and normal else None,
        "mcc": (tp * tn - fp * fn) / math.sqrt(mcc_denominator) if mcc_denominator else None,
    }


def _finite_score(value):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("scores and threshold must be finite real numbers")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("scores and threshold must be finite real numbers")
    return value


def _scored_rows(scores, labels):
    scores, labels = list(scores), list(labels)
    if len(scores) != len(labels):
        raise ValueError("score/label lengths differ; partial evaluation is not allowed")
    if any(isinstance(label, bool) or not isinstance(label, Integral) or label not in (0, 1)
           for label in labels):
        raise ValueError("labels must be integer 0 or 1")
    return [(_finite_score(score), int(label)) for score, label in zip(scores, labels)]


def roc_auc(scores: list[float], labels: list[int]) -> float | None:
    """임계 스윕 사다리꼴 AUC. 한 클래스/빈 입력은 미정의."""
    rows = _scored_rows(scores, labels)
    scores, labels = [row[0] for row in rows], [row[1] for row in rows]
    pos = sum(labels)
    neg = len(labels) - pos
    if pos == 0 or neg == 0:
        return None
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    tp = fp = 0
    prev_fpr = prev_tpr = 0.0
    auc = 0.0
    prev_score = None
    for i in order:
        if scores[i] != prev_score:
            tpr, fpr = tp / pos, fp / neg
            auc += (fpr - prev_fpr) * (tpr + prev_tpr) / 2
            prev_fpr, prev_tpr = fpr, tpr
            prev_score = scores[i]
        if labels[i] == 1:
            tp += 1
        else:
            fp += 1
    tpr, fpr = tp / pos, fp / neg
    auc += (fpr - prev_fpr) * (tpr + prev_tpr) / 2
    return auc


def metrics_at(scores, labels, attack_types, threshold: float) -> dict:
    """기존 score >= threshold 경계의 윈도우 원수/ratio. 미정의는 None."""
    rows, attack_types = _scored_rows(scores, labels), list(attack_types)
    threshold = _finite_score(threshold)
    if len(rows) != len(attack_types):
        raise ValueError("attack-type length differs; partial evaluation is not allowed")
    if any(not isinstance(kind, str) or (not kind if label else bool(kind))
           for (_, label), kind in zip(rows, attack_types)):
        raise ValueError("attack labels need a nonempty type; normal labels need an empty type")
    tp = fp = tn = fn = 0
    per_attack_hit: dict[str, list[int]] = {}
    for (s, y), at in zip(rows, attack_types):
        pred = 1 if s >= threshold else 0
        if y == 1 and pred == 1:
            tp += 1
        elif y == 1 and pred == 0:
            fn += 1
        elif y == 0 and pred == 1:
            fp += 1
        else:
            tn += 1
        if y == 1:
            per_attack_hit.setdefault(at, [0, 0])
            per_attack_hit[at][0] += pred
            per_attack_hit[at][1] += 1
    return {
        **confusion_metrics(tp, fp, tn, fn),
        "normal_windows": fp + tn, "attack_windows": tp + fn,
        "metric_unit": "ratio", "decision": "score >= threshold",
        "per_attack_counts": {a: {"detected": h[0], "windows": h[1]}
                              for a, h in per_attack_hit.items()},
        "per_attack": {a: h[0] / h[1] for a, h in per_attack_hit.items()},
    }
