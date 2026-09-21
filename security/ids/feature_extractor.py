"""1초 슬라이딩 윈도우 7차원 특징 추출 (순수 Python, SDD-ECU §3.9.1 정합).

CAN IDS 표준 특징: 메시지율, IAT 통계, ID 다양성/엔트로피, 페이로드 변화율, 버스트.
Isolation Forest / 규칙 베이스라인 공통 입력.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict

FEATURE_NAMES = [
    "msg_rate",        # 윈도우 내 프레임 수
    "mean_iat",        # 평균 프레임 간 간격(s)
    "std_iat",         # IAT 표준편차
    "unique_ids",      # 고유 CAN ID 수
    "id_entropy",      # ID 분포 Shannon 엔트로피(bit)
    "payload_change",  # 동일 ID 연속 페이로드 평균 변화 바이트수
    "max_id_burst",    # 단일 ID 최대 프레임 수(버스트)
]


def _entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    h = 0.0
    for c in counts:
        if c:
            p = c / total
            h -= p * math.log2(p)
    return h


def extract(window_frames: list) -> list[float]:
    """window_frames: t 오름차순 Frame 리스트 → 7차원 특징 벡터."""
    n = len(window_frames)
    if n == 0:
        return [0.0] * len(FEATURE_NAMES)

    times = [f.t for f in window_frames]
    iats = [times[i] - times[i - 1] for i in range(1, n)]
    mean_iat = sum(iats) / len(iats) if iats else 0.0
    std_iat = (
        math.sqrt(sum((x - mean_iat) ** 2 for x in iats) / len(iats)) if iats else 0.0
    )

    id_counts = Counter(f.can_id for f in window_frames)
    unique_ids = len(id_counts)
    id_entropy = _entropy(list(id_counts.values()))
    max_id_burst = max(id_counts.values())

    # 동일 ID 연속 페이로드 변화 바이트수 평균
    last_payload: dict[int, bytes] = {}
    changes: list[int] = []
    for f in window_frames:
        prev = last_payload.get(f.can_id)
        if prev is not None:
            changes.append(sum(1 for a, b in zip(prev, f.data) if a != b))
        last_payload[f.can_id] = f.data
    payload_change = sum(changes) / len(changes) if changes else 0.0

    return [
        float(n),
        mean_iat,
        std_iat,
        float(unique_ids),
        id_entropy,
        payload_change,
        float(max_id_burst),
    ]


def raw_windows(frames: list, window_s: float = 1.0, slide_s: float = 1.0):
    """프레임 스트림을 (프레임리스트, label, attack_type) 윈도우로 분할.

    윈도우 label = 공격 프레임을 하나라도 포함하면 1.
    per-ID 사양기반 탐지기(원본 프레임 필요)와 특징 추출이 공통으로 사용한다.
    """
    if not frames:
        return
    t_start = frames[0].t
    t_end = frames[-1].t
    w0 = t_start
    while w0 < t_end:
        w1 = w0 + window_s
        bucket = [f for f in frames if w0 <= f.t < w1]
        if bucket:
            label = 1 if any(f.label == 1 for f in bucket) else 0
            atypes = {f.attack_type for f in bucket if f.attack_type}
            atype = next(iter(atypes)) if atypes else ""
            yield bucket, label, atype
        w0 += slide_s


def windows(frames: list, window_s: float = 1.0, slide_s: float = 1.0):
    """프레임 스트림을 (특징벡터, label, attack_type) 윈도우로 분할."""
    for bucket, label, atype in raw_windows(frames, window_s, slide_s):
        yield extract(bucket), label, atype
