"""per-ID 사양기반 IDS (Specification-based, 순수 Python).

규칙 베이스라인(`rule_baseline.py`)이 윈도우 전역 특징을 쓰는 탓에 5개 ID 중 1개만
위장하는 masquerade를 희석·간과하는 한계를, **per-ID 사양 모델**로 보완한다.

정상 트래픽에서 ID별 (윈도우 카운트 상한, payload 평균 변화량)을 학습하고 다음을 위반으로
탐지한다:
  1) 화이트리스트 위반 — 학습에 없던 CAN ID (flooding 0x000·fuzzy 랜덤 ID)
  2) per-ID 주기 위반 — 윈도우 카운트가 학습 상한 초과 (replay/spoofing 추가 주입, 표적 DoS)
  3) payload 동결 — 정상적으로 변하는 ID의 payload가 거의 고정 (masquerade 시그니처)

산업 근거: 사양기반 IDS는 결정적·저오탐으로 안전표준(ISO 26262/21434) 친화적이며,
per-ID 모델링은 CIDS(Cho & Shin, USENIX'16)류 송신자 단위 탐지와 같은 계열이다.
"""

from __future__ import annotations

import statistics as st
from collections import defaultdict


def _payload_changes(window_frames):
    """윈도우 내 ID별 연속 payload 변화 바이트수 리스트."""
    prev: dict[int, bytes] = {}
    pc: dict[int, list[int]] = defaultdict(list)
    for f in window_frames:
        if f.can_id in prev:
            pc[f.can_id].append(sum(1 for a, b in zip(prev[f.can_id], f.data) if a != b))
        prev[f.can_id] = f.data
    return pc


class SpecDetector:
    def __init__(self, count_ratio: float = 1.4, freeze_frac: float = 0.15) -> None:
        self.known: set[int] = set()
        self.count_hi: dict[int, float] = {}   # per-ID 윈도우 카운트 허용 상한
        self.chg_mean: dict[int, float] = {}   # per-ID 정상 payload 평균 변화량
        self.count_ratio = count_ratio
        self.freeze_frac = freeze_frac

    def fit(self, normal_frame_windows) -> "SpecDetector":
        counts: dict[int, list[int]] = defaultdict(list)
        chgs: dict[int, list[float]] = defaultdict(list)
        wins = list(normal_frame_windows)
        for wf in wins:
            per: dict[int, int] = defaultdict(int)
            for f in wf:
                self.known.add(f.can_id)
                per[f.can_id] += 1
            for cid in self.known:
                counts[cid].append(per.get(cid, 0))
            for cid, v in _payload_changes(wf).items():
                if v:
                    chgs[cid].append(st.mean(v))
        for cid in self.known:
            m = st.mean(counts[cid]) if counts[cid] else 0.0
            self.count_hi[cid] = max(m * self.count_ratio, m + 3.0)
            self.chg_mean[cid] = st.mean(chgs[cid]) if chgs[cid] else 0.0
        return self

    def flag(self, window_frames) -> int:
        """윈도우 이상 여부(0/1)."""
        per: dict[int, int] = defaultdict(int)
        for f in window_frames:
            per[f.can_id] += 1
        # 1) 화이트리스트 위반
        for cid in per:
            if cid not in self.known:
                return 1
        # 2) per-ID 주기(카운트) 상한 초과
        for cid, c in per.items():
            if c > self.count_hi.get(cid, float("inf")):
                return 1
        # 3) payload 동결 (정상적으로 변하는 ID가 거의 고정)
        for cid, v in _payload_changes(window_frames).items():
            base = self.chg_mean.get(cid, 0.0)
            if base > 1.0 and v and st.mean(v) < base * self.freeze_frac:
                return 1
        return 0
