"""합성 CAN 트래픽 생성기 (정상 + 4종 공격, 라벨 포함, seed 고정).

실 데이터셋(HCRL/ROAD/SynCAN) 확보 전 오프라인 실측용. 실 데이터셋 연동은
`security/ids/if_detector.py` 주석 및 `tmp/보안모델_확장_개선안.md` §4 참조.

Frame = (t_sec, can_id, dlc, data(bytes), label, attack_type)
  label: 0=정상, 1=공격 / attack_type: "" | flooding | fuzzy | replay | spoofing
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Frame:
    t: float
    can_id: int
    dlc: int
    data: bytes
    label: int
    attack_type: str


# 정상 주기 메시지 정의: (CAN ID, 주기 ms). 실차 파워트레인/BMS 도메인 모사.
NORMAL_SCHEDULE = [
    (0x100, 100),  # BMS_Status
    (0x1B0, 10),   # 고빈도 제어
    (0x2A0, 20),
    (0x3F1, 50),
    (0x4C2, 200),
]


def _rand_payload(rng: random.Random, base: bytes | None = None, jitter: int = 2) -> bytes:
    if base is None:
        return bytes(rng.getrandbits(8) for _ in range(8))
    out = bytearray(base)
    for i in range(len(out)):
        out[i] = (out[i] + rng.randint(-jitter, jitter)) & 0xFF
    return bytes(out)


def gen_normal(duration: float, rng: random.Random, t0: float = 0.0,
               exclude_ids: set[int] | None = None) -> list[Frame]:
    """정상 주기 트래픽. 각 ID는 주기 ± 소량 지터.

    exclude_ids: masquerade(피해 ECU 정지) 모사를 위해 특정 ID를 배경에서 제외.
    """
    exclude_ids = exclude_ids or set()
    frames: list[Frame] = []
    base = {cid: bytes((cid >> 8, cid & 0xFF, 0x10, 0x68, 0xFF, 0xEC, 0x41, 0x00))
            for cid, _ in NORMAL_SCHEDULE}
    for cid, period_ms in NORMAL_SCHEDULE:
        if cid in exclude_ids:
            continue
        p = period_ms / 1000.0
        t = t0 + rng.uniform(0, p)
        while t < t0 + duration:
            frames.append(Frame(t, cid, 8, _rand_payload(rng, base[cid]), 0, ""))
            t += p * (1.0 + rng.uniform(-0.03, 0.03))  # 3% 지터
    frames.sort(key=lambda f: f.t)
    return frames


def gen_attack(attack: str, duration: float, rng: random.Random, t0: float = 0.0) -> list[Frame]:
    """정상 배경 위에 공격 프레임을 겹쳐 라벨된 세그먼트 생성."""
    frames = gen_normal(duration, rng, t0)  # 배경은 정상으로 라벨됨
    atk: list[Frame] = []

    if attack == "flooding":
        # 최고 우선순위 ID를 고율 주입 (bus-load 관점: 물리한계 이하로 설정)
        rate = 3000  # fps (8B 프레임 물리 상한 ~3700 이하)
        t = t0
        while t < t0 + duration:
            atk.append(Frame(t, 0x000, 8, b"\x00" * 8, 1, "flooding"))
            t += 1.0 / rate
    elif attack == "fuzzy":
        rate = 500
        t = t0
        while t < t0 + duration:
            cid = rng.getrandbits(11)
            atk.append(Frame(t, cid, 8, _rand_payload(rng), 1, "fuzzy"))
            t += 1.0 / rate
    elif attack == "replay":
        # 사전 캡처한 정상 0x100 프레임을 원 주기보다 빠르게 재생 (masquerade성)
        captured = [f for f in gen_normal(2.0, rng, 0.0) if f.can_id == 0x100][:5]
        rate = 20  # 정상 10Hz보다 약간 빠르게
        t, i = t0, 0
        while t < t0 + duration and captured:
            src = captured[i % len(captured)]
            atk.append(Frame(t, 0x100, 8, src.data, 1, "replay"))
            t += 1.0 / rate
            i += 1
    elif attack == "spoofing":
        # Fabrication형: 정상 0x100(10Hz) 위에 조작 페이로드(SOC=100%: raw 200=0xC8) 추가 주입
        rate = 12
        t = t0
        while t < t0 + duration:
            atk.append(Frame(t, 0x100, 8, b"\xC8\xBE\x10\x68\xFF\xEC\x41\x00", 1, "spoofing"))
            t += 1.0 / rate
    elif attack == "masquerade":
        # Stealthy(Cho&Shin): 피해 ECU(0x100) 정지 + 같은 10Hz·고정 페이로드로 위장.
        # 배경에서 0x100 제거 후 조작 프레임을 정상 주기로 주입 → 볼륨/율은 정상.
        frames = gen_normal(duration, rng, t0, exclude_ids={0x100})
        rate = 10  # 정상 0x100과 동일 주기
        t = t0 + rng.uniform(0, 0.1)
        while t < t0 + duration:
            atk.append(Frame(t, 0x100, 8, b"\xC8\xBE\x10\x68\xFF\xEC\x41\x00", 1, "masquerade"))
            t += 0.1 * (1.0 + rng.uniform(-0.03, 0.03))
    else:
        raise ValueError(f"unknown attack: {attack}")

    frames.extend(atk)
    frames.sort(key=lambda f: f.t)
    return frames


# fabrication형(볼륨↑ → rate 기반 탐지 용이) + stealthy masquerade(볼륨 정상 → 회피)
ATTACKS = ["flooding", "fuzzy", "replay", "spoofing", "masquerade"]
