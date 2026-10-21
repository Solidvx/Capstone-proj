"""Offline, standard-library evidence rebuild. Does not open CAN or alter raw files."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import platform
import re

from security.experiments.summarize_live import campaign_runs


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def json_rows(path):
    with path.open(encoding="utf-8-sig") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verified_inventory(base):
    inventory = json.loads((base / "inventory.json").read_text(encoding="utf-8"))
    paths = set()
    for row in inventory["files"]:
        path = (base / row["path"]).resolve()
        if not path.is_relative_to(base.resolve()) or row["path"] in paths:
            raise ValueError("invalid inventory path: " + row["path"])
        paths.add(row["path"])
        if digest(path) != row.get("preserved_sha256", row["sha256"]):
            raise ValueError("inventory hash mismatch: " + row["path"])
    raw = {p.relative_to(base).as_posix() for p in (base / "raw").rglob("*") if p.is_file()}
    if raw - paths:
        raise ValueError("unindexed raw evidence")
    return len(paths)


def metric_summary(rows, *, timing_allowed=True, ids_enabled=True):
    valid = [r for r in rows if r["status"] == "VALID"]
    times = [r["detect_latency_s"] for r in valid if r.get("detected") and r.get("detect_latency_s") is not None]
    expected = sum(r.get("normal_expected", 0) for r in valid)
    delivered = sum(r.get("normal_delivered", 0) for r in valid)
    bad_ratio = any(r.get("normal_delivered", 0) > r.get("normal_expected", 0) for r in valid)
    measured = [r["attack_success"] for r in valid if r.get("attack_success") is not None]
    return {
        "attempts": len(rows), "valid": len(valid), "invalid": len(rows) - len(valid),
        "reference_detected": sum(bool(r.get("detected")) for r in valid) if ids_enabled else None,
        "reference_detection_denominator": len(valid) if ids_enabled else None,
        "undetected_valid_trials": sum(not bool(r.get("detected")) for r in valid) if ids_enabled else None,
        "late_over_3s_timing_eligible": sum(t > 3 for t in times) if timing_allowed and ids_enabled else None,
        "rule_events": sum(r.get("rule_events", 0) for r in valid),
        "if_events": sum(r.get("if_events", 0) for r in valid),
        "reference_detection_rate": sum(bool(r.get("detected")) for r in valid) / len(valid) if valid and ids_enabled else None,
        "reference_success_numerator": sum(measured) if measured else None,
        "reference_success_denominator": len(measured),
        "reference_auth_rejection_trials": sum(bool(r.get("blocked")) for r in valid),
        "attack_published": sum(r.get("attack_published", 0) for r in valid),
        "attack_sent": sum(r.get("attack_sent", 0) for r in valid),
        "attack_seen": sum(r.get("attack_seen", 0) for r in valid),
        "normal_expected_recorded": expected, "normal_delivered_recorded": delivered,
        "delivery_ratio": delivered / expected if timing_allowed and expected and not bad_ratio else None,
        "delivery_exclusion": "timing version excluded" if not timing_allowed else ("per-trial delivered exceeds expected" if bad_ratio else None),
        "detected_latency_samples": len(times) if timing_allowed else 0,
        "detected_latency_mean_ms": sum(times) * 1000 / len(times) if times and timing_allowed else None,
        "detected_latency_p95_ms": sorted(times)[math.ceil(len(times) * .95) - 1] * 1000 if times and timing_allowed else None,
        "detected_latency_max_ms": max(times) * 1000 if times and timing_allowed else None,
        "latency_exclusion": None if timing_allowed else "timing version excluded",
        "product_verdict": "NOT_INFERRED_FROM_REFERENCE",
    }


def plan_summary(ordered_rows, planned=100):
    """First recorded attempt per planned number; retries remain in all-attempt data."""
    first = {}
    duplicates = []
    for row in ordered_rows:
        trial = row["trial"]
        if type(trial) is not int or not 1 <= trial <= planned:
            raise ValueError("trial outside campaign plan")
        if trial in first:
            duplicates.append({"trial": trial, "first_run_id": first[trial]["run_id"], "retry_run_id": row["run_id"], "status": row["status"]})
        else:
            first[trial] = row
    return {
        "planned": planned, "recorded": len(first),
        "missing_numbers": sorted(set(range(1, planned + 1)) - set(first)),
        "first_attempt_valid": sum(r["status"] == "VALID" for r in first.values()),
        "first_attempt_invalid": sum(r["status"] == "INVALID" for r in first.values()),
        "retries": duplicates,
    }, list(first.values())


CAN_LINE = re.compile(r"^\(([0-9.]+)\)\s+\S+\s+([0-9A-Fa-f]+)#([0-9A-Fa-f]*)$")
FILTER = {0x100, 0x101, 0x102, 0x103, 0x200}


def can_frames(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            match = CAN_LINE.match(line.strip())
            if not match:
                raise ValueError("unsupported candump line: " + line[:100])
            stamp, cid, data = match.groups()
            yield float(stamp), int(cid, 16), data.lower()


def align_frames(ecu, ivi, lookahead=32):
    """Bounded ordered alignment; identical repeated frame identity stays ambiguous.

    ecu and ivi start with (can_id, data). Unresolvable differences fail closed.
    """
    i = j = 0
    while i < len(ecu) and j < len(ivi):
        if ecu[i][:2] == ivi[j][:2]:
            yield i, j
            i += 1
            j += 1
            continue
        candidates = []
        for skip in range(1, min(lookahead, len(ecu) - i - 1) + 1):
            n = min(8, len(ecu) - i - skip, len(ivi) - j)
            if n >= 4 and all(ecu[i + skip + k][:2] == ivi[j + k][:2] for k in range(n)):
                candidates.append(skip)
        if not candidates:
            raise ValueError(f"unresolved frame alignment at ECU {i}, IVI {j}")
        skip = candidates[0]
        for index in range(i, i + skip):
            yield index, None
        i += skip
    for index in range(i, len(ecu)):
        yield index, None


def crosscheck(root, manifest, receiver):
    """Rebuild frame agreement, injection origins, alert transport and stderr counts."""
    v = receiver.parent
    capture = list(can_frames(v / "candump.log"))
    errors = [(t, cid, data) for t, cid, data in capture if cid & 0x20000000]
    can = [(cid, data) for _, cid, data in capture if not cid & 0x20000000]
    rx = [r for r in json_rows(receiver) if r.get("result") == "FRAME"]
    filtered = [x for x in can if x[0] in FILTER]
    rx_match = all(x == (r["can_id"], r["data"].lower()) for x, r in zip(filtered, rx)) if len(filtered) == len(rx) else False
    ecu = []
    for path in [root / "warmup.jsonl", *sorted(root.glob("*-*.jsonl"))]:
        if not path.exists():
            continue
        for r in json_rows(path):
            if "frame" in r:
                ecu.append((r["can_id"], r["data"].lower(), bool(r["own"]), r["t"]))
    ecu.sort(key=lambda r: r[3])
    mapped = {}
    missing = []
    last = -1
    for i, j in align_frames(ecu, can):
        if j is None:
            missing.append({"ecu_index_example": i, "can_id": ecu[i][0], "data": ecu[i][1], "own": ecu[i][2]})
        else:
            if can[j][0] in FILTER:
                mapped[j] = i
            last = j
    pub = Counter()
    mac = Counter()
    pending = None
    rx_index = 0
    for j, (cid, data) in enumerate(can):
        if cid not in FILTER:
            continue
        r = rx[rx_index] if rx_match else {}
        rx_index += 1
        source = ecu[mapped[j]] if j in mapped else None
        if cid == 0x100:
            pending = source
        if r.get("message") == "Authenticated BMS data published":
            label = "OUTSIDE_ECU_MATCHED_CAPTURE"
            if pending is not None and source is not None:
                label = f"pending_own={pending[2]},auth_own={source[2]},payload_match={pending[1] == r.get('source_data', '').lower()}"
            pub[label] += 1
        if "MAC_FAIL" in r.get("message", ""):
            label = "OUTSIDE_ECU_MATCHED_CAPTURE" if pending is None or source is None else f"pending_own={pending[2]},auth_own={source[2]}"
            mac[label] += 1
    alerts = Counter()
    sent = []
    ids = root / "ids.jsonl"
    if ids.exists():
        for r in json_rows(ids):
            alerts[r.get("result", "UNKNOWN")] += 1
            if r.get("result") == "ALERT_SENT":
                sent.append(r["data"].lower())
    # The full CAN sequence match attributes own injection vs ECU IDS echo;
    # identical alert payloads alone are insufficient proof of origin.
    ecu_ids = [r[1] for r in ecu if r[0] == 0x200 and not r[2]]
    matched_ids = [can[j][1] for j, i in mapped.items() if ecu[i][0] == 0x200 and not ecu[i][2]]
    injected_alerts = sum(r[0] == 0x200 and r[2] for r in ecu)
    warnings = {}
    for path in v.glob("*.stderr"):
        warnings[path.name] = {"bytes": path.stat().st_size, "qt_animation_warnings": path.read_text(encoding="utf-8", errors="replace").count("QUnifiedTimer::stopAnimationDriver: driver is not running")}
    return {
        "run_id": manifest["run_id"], "ecu_frames": len(ecu), "ivi_can_frames": len(can),
        "ivi_receiver_frames": len(rx), "receiver_matches_filtered_can": rx_match,
        "ecu_missing_count": len(missing), "missing_examples": missing,
        "repeated_payload_identity": "counts verified; exact repeated-frame identities may be ambiguous",
        "ivi_tail_frames": len(can) - last - 1, "can_error_frames": errors,
        "authenticated_publish_origins": dict(pub), "mac_fail_origins": dict(mac),
        "ids_log_results": dict(alerts), "ids_sent": len(sent),
        "ids_sent_matches_non_injected_ecu_and_ivi": sent == ecu_ids == matched_ids,
        "injected_id200_frames": injected_alerts, "stderr": warnings,
        "ids_wire_type_counts": dict(Counter(int(data[:2], 16) for data in sent)),
        "origin_method": "ordered CAN alignment plus most recent BMS pending; descriptive association, not cryptographic re-verification",
        "ivi_exit_files": {p.name: p.read_text(encoding="utf-8").strip() for p in v.glob("*exit*.txt")},
        "display_verdict": "NOT_MEASURED", "physical_pixel_latency": None,
    }


def build(base, policy_path, output):
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    inventory_count = verified_inventory(base)
    roots = [p.parent for p in (base / "raw").rglob("attempts.jsonl")]
    ordered = campaign_runs(roots)
    cases = defaultdict(list)
    provenance = {}
    runs = []
    # Capture every input file's hash including manifests/meta/IVI originals.
    for p in sorted((base / "raw").rglob("*")):
        if p.is_file():
            provenance[p.relative_to(base).as_posix()] = digest(p)
    for root, m, rows in ordered:
        rid = m["run_id"]
        exception = policy.get("runs", {}).get(rid, {})
        timing_allowed = not exception.get("exclude_timing", False)
        source_hash = hashlib.sha256(json.dumps(m.get("source_sha256", {}), sort_keys=True).encode()).hexdigest()
        entry = {"run_id": rid, "config": m["config"], "attacks": m["attacks"],
                 "source_set_sha256": source_hash, "source_sha256": m.get("source_sha256", {}),
                 "ecu_sha256": m.get("ecu_sha256"), "clock": m.get("clock"),
                 "previous_run_id": m.get("previous_run_id"), "training_sha256": m.get("training_sha256"),
                 "calibration_sha256": m.get("calibration_sha256"), "exception": exception,
                 "metrics": metric_summary(rows, timing_allowed=timing_allowed, ids_enabled=m["config"] == 3)}
        receivers = [p for p in (base / "raw").rglob("receiver.jsonl") if p.parent.name == rid.lower()]
        if len(receivers) != 1:
            raise ValueError("receiver evidence is missing or ambiguous: " + rid)
        entry["ecu_root"] = root.relative_to(base).as_posix()
        entry["ivi_root"] = receivers[0].parent.relative_to(base).as_posix()
        check = crosscheck(root, m, receivers[0])
        if not check["receiver_matches_filtered_can"]:
            raise ValueError("IVI receiver/candump mismatch: " + rid)
        write_json(output / "runs" / rid / "crosscheck.json", check)
        write_json(output / "runs" / rid / "summary.json", entry)
        runs.append(entry)
        for r in rows:
            cases[(m["config"], r["attack_type"])].append({**r, "timing_allowed": timing_allowed, "source_set_sha256": source_hash})
        print(rid, "verified", len(rows), flush=True)
    summaries = []
    for (config, attack), rows in sorted(cases.items()):
        plan, first = plan_summary(rows, policy["planned_per_case"])
        timing = [r for r in first if r["timing_allowed"]]
        case = {"config": config, "attack": attack, "plan": plan,
                "all_attempts": metric_summary(rows, timing_allowed=False, ids_enabled=config == 3),
                "primary_first_attempts": metric_summary(first, timing_allowed=False, ids_enabled=config == 3),
                "timing_eligible_primary_subset": metric_summary(timing, ids_enabled=config == 3),
                "timing_subset_run_ids": sorted({r["run_id"] for r in timing}),
                "source_strata": sorted({r["source_set_sha256"] for r in rows}),
                "acceptance": "COLLECTED_WITH_LIMITATIONS_NOT_BLANKET_TC_PASS"}
        summaries.append(case)
        case_out = output / "cases" / f"C{config}-{attack}"
        write_json(case_out / "summary.json", case)
        with (case_out / "attempts.jsonl").open("w", encoding="utf-8") as stream:
            for r in rows:
                stream.write(json.dumps(r, ensure_ascii=False) + "\n")
    expected_cases = {(c, a) for c in (1, 2, 3) for a in ("flooding", "fuzzy", "replay", "spoofing")}
    if set(cases) != expected_cases:
        raise ValueError("campaign does not contain all twelve cases")
    write_json(output / "summary.json", {"policy": policy, "cases": summaries, "runs": runs})
    lines = ["# 논문용 실측 집계", "", "자동 생성. 수치는 실행기 참조 지표이며 제품 PASS를 뜻하지 않는다. 최초 시도 기준으로 INVALID를 보존하며 재시도는 별도다.", "", "| 조건 | 전체 시도 V/I | 계획 번호 | 최초 V/I | 참조 탐지/유효(C3만) | 지연 채택 표본 | 조건부 평균/p95 ms |", "|---|---|---|---|---|---|---|"]
    def value(v):
        return "—" if v is None else f"{v:.4f}"
    for c in summaries:
        a, p, t = c["all_attempts"], c["plan"], c["timing_eligible_primary_subset"]
        primary = c["primary_first_attempts"]
        det = "—" if c["config"] != 3 else f"{primary['reference_detected']}/{primary['valid']}"
        lines.append(f"| C{c['config']} {c['attack']} | {a['valid']}/{a['invalid']} | {p['recorded']}/{p['planned']} | {p['first_attempt_valid']}/{p['first_attempt_invalid']} | {det} | {t['detected_latency_samples']} | {value(t['detected_latency_mean_ms'])}/{value(t['detected_latency_p95_ms'])} |")
    lines += ["", "V/I = 실행기 VALID/INVALID. 지연은 탐지된 유효 시행에 조건부이며 미탐지·INVALID는 0ms로 넣지 않는다. p95는 nearest-rank다.", "", "C3 flooding은 구버전 001/002의 지연·전달률을 채택하지 않으며 003의 23개 시행만 지연 부분집합에 포함한다. 전체 구성을 동일 버전·동일 계측으로 비교한 인과 효과를 주장하지 않는다.", "", "C1 flooding trial 7의 재시도 VALID는 원래 INVALID를 대체하지 않는다. 전체 원장과 최초 시도 분모를 함께 제시한다. 상세 출처·예외는 summary.json 및 runs/ 하위 파일을 참조한다."]
    (output / "TABLES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    lines = ["# 정상 전달과 출처 해석", "", "참조 관측의 유효 시행 합계. INVALID는 별도 원장에 보존된다. 수용 여부와 인증 프레임 출처는 runs/*/crosscheck.json을 함께 읽는다.", "", "| 조건 | 정상 전달/기대(채택 부분집합) | 참조 주입 게시(전체 유효) | 참조 성공 판정/측정 시행 |", "|---|---|---|---|"]
    for c in summaries:
        t = c["timing_eligible_primary_subset"]
        a = c["primary_first_attempts"]
        lines.append(f"| C{c['config']} {c['attack']} | {t['normal_delivered_recorded']}/{t['normal_expected_recorded']} | {a['attack_published']} | {a['reference_success_numerator']}/{a['reference_success_denominator']} |")
    lines += ["", "C3 flooding 전달 부분집합은 v8 23회만이다. 주입 payload 게시를 오래된 인증 재수락 또는 위조 MAC 수락으로 해석하지 않는다. reference_success는 기존 실행기의 공격별 정의이며 동일한 의미의 전 구성 단일 성공률이 아니다."]
    (output / "DELIVERY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # A standalone typeset table source avoids introducing plotting dependencies.
    tex = [r"\begin{tabular}{llrrr}", r"Config & Attack & Attempts & Valid & Invalid \\ ", r"\hline"]
    for c in summaries:
        a = c["all_attempts"]
        tex.append(f"C{c['config']} & {c['attack']} & {a['attempts']} & {a['valid']} & {a['invalid']} " + r"\\")
    tex.append(r"\end{tabular}")
    (output / "attempt-counts.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")
    inputs = {"base_inventory": digest(base / "inventory.json"), "raw_files": provenance,
              "policy_sha256": digest(policy_path), "python": platform.python_version(),
              "tool_sha256": {p.name: digest(p) for p in [Path(__file__), Path(__file__).with_name("summarize_live.py")]}}
    write_json(output / "provenance.json", inputs)
    write_json(output / "outputs-sha256.json", {p.relative_to(output).as_posix(): digest(p) for p in sorted(output.rglob("*")) if p.is_file() and p.name != "outputs-sha256.json"})
    print("Inventory verified:", inventory_count, "Cases:", len(summaries), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    args = parser.parse_args(argv)
    if args.out.resolve().is_relative_to((args.base / "raw").resolve()):
        parser.error("output cannot be inside raw")
    args.out.mkdir(parents=True, exist_ok=False)
    build(args.base, args.policy, args.out)


if __name__ == "__main__":
    main()
