"""Per-trial judging for the live ablation (pure; no CAN socket required).

A trial is: baseline window -> attack window -> post window, all on one host
clock. The harness feeds every received frame through ReferenceReceiver and
keeps (t, can_id, own, outcomes) records; this module turns the records of one
trial into one ledger row. Attack success, blocking and detection are judged
independently (M5 3.1); detection is never treated as blocking.

Detection is the reception of an IDS_Alert (0x200) from Node A on this host,
so first_injection -> first 0x200 is also the TC-PERF-003 latency for the trial.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from security.experiments.live_receiver import parse_bms_ok, parse_failsafe_ok

BMS_PERIOD_S = 0.100
MIN_BASELINE_BMS_PER_S = 5  # a live ECU sends 10/s; fewer means the setup is broken

LEDGER_FIELDS = [
    "run_id", "environment", "channel", "config", "attack_type", "trial", "seed",
    "status", "invalid_reason", "attack_success", "blocked", "detected", "detect_latency_s",
    "attack_sent", "attack_tx_errors", "attack_seen", "attack_published",
    "attack_auth_rejected", "attack_parse_rejected",
    "normal_expected", "normal_seen", "normal_delivered", "delivery_ratio",
    "baseline_alerts", "alerts_in_window",
    "t_baseline_start", "t_attack_start", "first_injection", "t_attack_end", "t_post_end",
    "first_alert",
]


@dataclass
class Record:
    t: float                      # host monotonic seconds
    can_id: int
    data: bytes
    own: bool
    outcomes: list = field(default_factory=list)


@dataclass
class TrialWindows:
    baseline_start: float
    attack_start: float
    attack_end: float
    post_end: float
    first_injection: float | None = None


def _in(t: float, start: float, end: float) -> bool:
    return start <= t < end


def judge_trial(config: int, attack: str, records: list[Record], w: TrialWindows,
                attack_sent: int, attack_tx_errors: int = 0, rx_dropped: int = 0) -> dict:
    if config not in (1, 2, 3):
        raise ValueError("invalid defence configuration")
    times = [w.baseline_start, w.attack_start, w.attack_end, w.post_end]
    if not all(math.isfinite(t) for t in times) or not all(a < b for a, b in zip(times, times[1:])):
        raise ValueError("invalid trial windows")
    if w.first_injection is not None and not w.attack_start <= w.first_injection < w.attack_end:
        raise ValueError("injection outside attack window")
    ids_on = config == 3
    baseline = [r for r in records if _in(r.t, w.baseline_start, w.attack_start)]
    judged = [r for r in records if _in(r.t, w.attack_start, w.post_end)]
    attack_window = [r for r in records if _in(r.t, w.attack_start, w.attack_end)]

    outcomes = [o for r in judged for o in r.outcomes]
    attack_published = [o for o in outcomes if o.kind == "PUBLISHED" and o.own]
    attack_auth_rejected = sum(o.kind == "REJECTED" and o.own and o.reason in (
        "AUTH_TIMEOUT", "MAC_FAIL", "COUNTER_REUSE", "COUNTER_BACKWARD", "COUNTER_WINDOW")
        for o in outcomes)
    attack_parse_rejected = sum(o.kind == "PARSE_REJECTED" and o.own for o in outcomes)
    attack_seen = sum(r.own for r in judged)

    normal_seen = sum(r.can_id == 0x100 and not r.own for r in attack_window)
    normal_delivered = sum(o.kind == "PUBLISHED" and o.can_id == 0x100 and not o.own
                           and _in(o.original_t if o.original_t is not None else r.t,
                                   w.attack_start, w.attack_end)
                           for r in judged for o in r.outcomes)
    duration = max(w.attack_end - w.attack_start, 0.0)
    normal_expected = round(duration / BMS_PERIOD_S)
    ratio = normal_delivered / normal_expected if normal_expected else None

    def alerts(rs):
        return [r for r in rs if r.can_id == 0x200 and not r.own and len(r.data) == 8
                and 1 <= r.data[0] <= 4]

    baseline_alerts = alerts(baseline)
    window_alerts = [r for r in alerts(judged) if w.first_injection is not None
                     and r.t >= w.first_injection]
    first_alert = window_alerts[0].t if window_alerts else None

    # Validity: the run must actually inject, see its own frames, and have a live ECU.
    reasons = []
    if attack_sent <= 0:
        reasons.append("NO_INJECTION")
    elif attack_seen != attack_sent:
        reasons.append("INJECTION_ECHO_MISMATCH")
    if w.first_injection is None:
        reasons.append("NO_INJECTION_TIMESTAMP")
    if rx_dropped:
        reasons.append("RX_OVERFLOW")
    baseline_s = max(w.attack_start - w.baseline_start, 1e-9)
    baseline_bms = sum(r.can_id == 0x100 and not r.own for r in baseline)
    if baseline_bms < MIN_BASELINE_BMS_PER_S * baseline_s:
        reasons.append("NO_LIVE_ECU")
    baseline_published = sum(o.kind == "PUBLISHED" and o.can_id == 0x100 and not o.own
                             for r in baseline for o in r.outcomes)
    if baseline_published < MIN_BASELINE_BMS_PER_S * baseline_s:
        reasons.append("RECEIVER_NOT_READY")
    if baseline_alerts:
        reasons.append("BASELINE_ALERTS")
    if not ids_on and window_alerts:
        reasons.append("ALERT_WITH_IDS_OFF")  # configuration did not switch (M5 5)

    if attack == "spoofing":
        success: bool | None = any(o.can_id == 0x100 and o.payload[:1] == b"\xc8"
                                   for o in attack_published)
    elif attack == "replay":
        success = bool(attack_published)
    elif attack == "fuzzy":
        success = any((o.can_id == 0x100 and not parse_bms_ok(o.payload)) or
                      (o.can_id == 0x101 and not parse_failsafe_ok(o.payload))
                      for o in attack_published)
    elif attack == "flooding":
        # TC-EXP-003 specifies delivery rate, not a 90% binary success threshold.
        success = None
    else:
        raise ValueError(attack)

    latency = None
    if first_alert is not None and w.first_injection is not None:
        latency = first_alert - w.first_injection

    return {
        "status": "INVALID" if reasons else "VALID",
        "invalid_reason": "|".join(reasons),
        "attack_success": success,
        "blocked": attack_auth_rejected > 0,
        "detected": bool(window_alerts) if ids_on else False,
        "detect_latency_s": None if latency is None else round(latency, 6),
        "attack_sent": attack_sent, "attack_tx_errors": attack_tx_errors,
        "attack_seen": attack_seen, "attack_published": len(attack_published),
        "observer": "reference_receiver", "product_verdict": "NOT_RUN",
        "rx_dropped": rx_dropped, "baseline_published": baseline_published,
        "fuzzy_frames": sum(r.own and r.can_id in (0x100, 0x101) and
                             not (parse_bms_ok(r.data) if r.can_id == 0x100 else parse_failsafe_ok(r.data))
                             for r in judged) if attack == "fuzzy" else 0,
        "attack_auth_rejected": attack_auth_rejected, "attack_parse_rejected": attack_parse_rejected,
        "normal_expected": normal_expected, "normal_seen": normal_seen,
        "normal_delivered": normal_delivered,
        "delivery_ratio": None if ratio is None else round(ratio, 4),
        "baseline_alerts": len(baseline_alerts), "alerts_in_window": len(window_alerts),
        "t_baseline_start": w.baseline_start, "t_attack_start": w.attack_start,
        "first_injection": w.first_injection, "t_attack_end": w.attack_end,
        "t_post_end": w.post_end, "first_alert": first_alert,
    }
