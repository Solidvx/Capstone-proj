"""Isolation Forest IDS 골격 (SDD-ECU §3.9, scikit-learn).

오프라인(sklearn 미설치) 환경에서는 실행 불가하므로, 가용 시에만 동작하도록
가드 처리한다. 규칙 베이스라인(`rule_baseline.py`)과 동일한 특징/평가 인터페이스를
사용해 Ablation·성능 비교(문서 §6)에 바로 투입할 수 있게 설계했다.
"""

from __future__ import annotations

RANDOM_STATE = 42  # 재현성 고정 (문서 §6)


def sklearn_available() -> bool:
    try:
        import sklearn  # noqa: F401
        return True
    except Exception:
        return False


class IsolationForestDetector:
    """decision_function → wire AnomalyScore 매핑 포함 (U-22 해소).

    ICD AnomalyScore는 unsigned 0.00~2.55인데 IsolationForest.decision_function은
    음수 가능 → clamp/정규화로 명시 매핑한다.
    """

    def __init__(self, n_estimators: int = 100, contamination: float = 0.05) -> None:
        if not sklearn_available():
            raise RuntimeError(
                "scikit-learn 미설치 — `pip install -r security/requirements.txt` 후 실행")
        from sklearn.ensemble import IsolationForest
        self.model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=RANDOM_STATE,
        )
        self._lo = 0.0
        self._hi = 1.0

    def fit(self, normal_vectors: list[list[float]]) -> "IsolationForestDetector":
        self.model.fit(normal_vectors)
        raw = self.model.decision_function(normal_vectors)  # 정상 캘리브레이션 범위
        self._lo, self._hi = min(raw), max(raw)
        return self

    def anomaly(self, vec: list[float]) -> float:
        """이상 점수(높을수록 이상). decision_function 부호 반전."""
        return -float(self.model.decision_function([vec])[0])

    def wire_score(self, vec: list[float]) -> int:
        """ICD 0x200 AnomalyScore(uint8, ×0.01, 0.00~2.55)로 정규화 매핑 (U-22)."""
        raw = float(self.model.decision_function([vec])[0])
        span = (self._hi - self._lo) or 1.0
        norm = max(0.0, min(1.0, (self._hi - raw) / span))  # 0=정상, 1=최대이상
        return max(0, min(255, round(norm * 255)))
