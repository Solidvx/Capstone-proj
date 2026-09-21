"""규칙기반 IDS 베이스라인 (순수 Python, 통계 임계).

정상 윈도우로 특징별 mean/std를 학습하고, 방향성 z-score의 최댓값을 이상 점수로
사용한다. "왜 ML(Isolation Forest)인가"를 정량 비교할 산업 표준 베이스라인.
공격은 대체로 특징을 증가시키므로(단 mean_iat는 감소) 방향을 반영한다.
"""

from __future__ import annotations

import math

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


def roc_auc(scores: list[float], labels: list[int]) -> float:
    """임계 스윕 사다리꼴 AUC."""
    pos = sum(labels)
    neg = len(labels) - pos
    if pos == 0 or neg == 0:
        return float("nan")
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
    """운영 임계에서 precision/recall/F1/FPR + 공격유형별 탐지율."""
    tp = fp = tn = fn = 0
    per_attack_hit: dict[str, list[int]] = {}
    for s, y, at in zip(scores, labels, attack_types):
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
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {
        "precision": precision, "recall": recall, "f1": f1, "fpr": fpr,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "per_attack": {a: h[0] / h[1] for a, h in per_attack_hit.items()},
    }
