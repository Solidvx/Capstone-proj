#!/usr/bin/env python3
"""Runtime IDS normal-traffic false-positive rate (EXQ-11, synthetic pre-check).

Config 3 judges detection with the streaming RuntimeDetector's *rule* thresholds
(runtime_detector.py: 50 ms min period, 300 ms missing, 100 frames/s, 3 failures
per second, SOC 20 %p / temp 20 C / current 100 A step). EXQ-11=A keeps those
defaults as the confirmed operating point but requires the normal-only false
positive rate to be measured first, over at least 100 complete windows.

This measures that FPR on *synthetic* Node A normal traffic: steady 0x100 BMS at
10 Hz, each followed by its 0x102 SecOC frame. It is a grade-1 pre-check. The
final TC-EXP-005 FPR is measured on a real-bus normal capture (physical grade),
not here. No attack traffic is generated; this is a normal-only measurement.

A window is one non-overlapping 1 s slice of the capture. A window is a false
positive if the detector emits ANY event with result == "ANOMALY" whose
timestamp falls in that window.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import os
import random
import sys

_SEC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.dirname(_SEC)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from security.ids.runtime_detector import Config, Observation, RuntimeDetector

BMS_PERIOD_S = 0.100
PERIOD_JITTER_S = 0.003      # +/-3 ms, well inside the 50 ms min-period rule
SECOC_GAP_S = 0.001          # 0x102 follows its 0x100 by ~1 ms
WINDOW_S = 1.0


def _bms_payload(soc_raw: int, soh_raw: int, voltage: int, current: int, temp_raw: int) -> bytes:
    # ICD 1.2 layout: SOC, SOH, voltage(u16 BE), current(i16 BE), temp(+40 offset), reserved 0.
    return bytes([soc_raw & 0xFF, soh_raw & 0xFF,
                  (voltage >> 8) & 0xFF, voltage & 0xFF,
                  (current >> 8) & 0xFF, current & 0xFF,
                  temp_raw & 0xFF, 0x00])


def generate_normal(duration_s: float, rng: random.Random) -> list[Observation]:
    """Steady-state Node A normal traffic: 0x100 at ~10 Hz, each with its 0x102.

    BMS values drift by a small random walk kept far under the step thresholds,
    so a correct detector should not flag well-formed normal traffic.
    """
    frames: list[Observation] = []
    t = 0.0
    counter = 0
    soc_raw = 150          # 75.0 %
    temp_raw = 65          # 25 C
    current = -20          # -2.0 A
    while t < duration_s:
        soc_raw = max(2, min(200, soc_raw + rng.choice((-1, 0, 0, 1))))      # +/-0.5 %p
        temp_raw = max(40, min(165, temp_raw + rng.choice((-1, 0, 0, 1))))   # +/-1 C
        current = max(-300, min(300, current + rng.choice((-2, -1, 0, 1, 2))))  # +/-0.2 A
        payload = _bms_payload(soc_raw, 190, 4200, current, temp_raw)
        frames.append(Observation(t, 0x100, payload, 8))
        # 0x102 carries 4-byte MAC placeholder + 4-byte counter; rules mode never
        # inspects the MAC (no key), only the frame's timing and format.
        auth = bytes([0xAA, 0xBB, 0xCC, 0xDD]) + counter.to_bytes(4, "big")
        frames.append(Observation(t + SECOC_GAP_S, 0x102, auth, 8))
        counter = (counter + 1) & 0xFFFFFFFF
        t += BMS_PERIOD_S * (1.0 + rng.uniform(-PERIOD_JITTER_S, PERIOD_JITTER_S) / BMS_PERIOD_S)
    frames.sort(key=lambda f: f.t)
    return frames


def measure(frames: list[Observation], config: Config) -> dict:
    detector = RuntimeDetector(config)
    anomalies: list = []          # (timestamp, reason)
    for frame in frames:
        for event in detector.observe(frame):
            if event.result == "ANOMALY":
                anomalies.append((event.timestamp, event.reason))

    span = frames[-1].t if frames else 0.0
    total_windows = int(span // WINDOW_S)          # only complete 1 s windows
    fp_windows = {int(t // WINDOW_S) for t, _ in anomalies if int(t // WINDOW_S) < total_windows}
    reasons = Counter(r for t, r in anomalies if int(t // WINDOW_S) < total_windows)
    return {
        "frames": len(frames),
        "span_s": round(span, 3),
        "total_windows": total_windows,
        "fp_windows": len(fp_windows),
        "fpr": (len(fp_windows) / total_windows) if total_windows else None,
        "anomaly_events": sum(reasons.values()),
        "reasons": dict(reasons),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Runtime IDS normal FPR (synthetic pre-check)")
    parser.add_argument("--duration", type=float, default=150.0,
                        help="seconds of normal traffic; >=~110 gives >=100 complete windows")
    parser.add_argument("--seed", type=int, default=20261003)
    parser.add_argument("--out", help="optional CSV path for the per-reason ledger; not overwritten")
    args = parser.parse_args(argv)

    if args.out and os.path.exists(args.out):
        parser.error(f"{args.out} exists; refusing to overwrite")

    frames = generate_normal(args.duration, random.Random(args.seed))
    result = measure(frames, Config())

    if result["total_windows"] < 100:
        print(f"창 부족: {result['total_windows']} < 100 (--duration 늘리기)", file=sys.stderr)

    print("환경(grade): 합성(synthetic) — 최종 TC-EXP-005는 물리 CAN 정상 캡처로 판정")
    print(f"탐지기: runtime_detector 규칙 기본 임계(Config 기본값), SecOC 키 없음(규칙 모드)")
    print(f"입력: Node A 정상 0x100+0x102, seed {args.seed}, {result['span_s']}s, {result['frames']}프레임")
    print(f"분모(완료 1초 창): {result['total_windows']}")
    fpr = result["fpr"]
    print(f"오탐 창: {result['fp_windows']}/{result['total_windows']} = "
          f"{fpr:.2%}" if fpr is not None else "오탐 창: N/A")
    print(f"오탐 이벤트 총수: {result['anomaly_events']}  사유별: {result['reasons'] or '없음'}")
    print(f"기준(TC-EXP-005): FPR <= 5%  ->  {'충족' if fpr is not None and fpr <= 0.05 else '미충족/판정불가'}")

    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["metric", "value"])
            for key in ("frames", "span_s", "total_windows", "fp_windows", "fpr", "anomaly_events"):
                writer.writerow([key, result[key]])
            for reason, count in sorted(result["reasons"].items()):
                writer.writerow([f"reason:{reason}", count])
        print(f"원장 기록: {args.out}")

    return 0 if (fpr is not None and result["total_windows"] >= 100) else 1


if __name__ == "__main__":
    raise SystemExit(main())
