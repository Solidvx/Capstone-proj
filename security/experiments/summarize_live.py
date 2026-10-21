"""Audit live run directories; preserve invalid/missing attempts and source grade.

Reference observer statistics never grant an IVI product or physical TC PASS.
Per-run summaries preserve identifiers. Campaign aggregation uses explicit run chains.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

from security.experiments.can_capture import sha256


def read_run(directory):
    """Verify a sealed run without rewriting its ledger or inferring missing trials."""
    root = Path(directory)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest["environment"] not in ("physical", "vcan"):
        raise ValueError("unexpected environment grade")
    start, count = manifest.get("start_trial", 1), manifest["trials_per_attack"]
    if type(start) is not int or type(count) is not int or start < 1 or count < 1:
        raise ValueError("invalid trial range")
    for name, digest in manifest["files_sha256"].items():
        if Path(name).name != name or "\\" in name or sha256(root / name) != digest:
            raise ValueError("run file hash mismatch")
    ledger = root / "attempts.jsonl"
    if ledger.exists() and "attempts.jsonl" not in manifest["files_sha256"]:
        raise ValueError("unsealed attempt ledger")
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()] if ledger.exists() else []
    seen = set()
    for row in rows:
        identity = (row["attack_type"], row["trial"])
        if identity in seen:
            raise ValueError("duplicate trial: preserve retries under a new run-id")
        seen.add(identity)
        if any(row[field] != manifest[field] for field in ("run_id", "environment", "config", "ids_mode")):
            raise ValueError("row/manifest identity mismatch")
        if row["attack_type"] not in manifest["attacks"] or not start <= row["trial"] < start + count:
            raise ValueError("invalid trial identity")
        if row["status"] not in ("VALID", "INVALID"):
            raise ValueError("invalid status")
        if row.get("raw_file"):
            name = row["raw_file"]
            if Path(name).name != name or "\\" in name or sha256(root / name) != row["raw_sha256"]:
                raise ValueError("trial raw hash mismatch")
        if row["status"] == "VALID":
            for field in ("attack_success", "blocked", "detected"):
                if row[field] is not None and type(row[field]) is not bool:
                    raise ValueError("non-boolean metric")
            if type(row["detected"]) is not bool or type(row["blocked"]) is not bool:
                raise ValueError("missing required detection/block metric")
            latency = row["detect_latency_s"]
            if latency is not None and (not math.isfinite(latency) or latency < 0):
                raise ValueError("invalid latency")
            if not row["detected"] and latency is not None:
                raise ValueError("undetected trial cannot have detection latency")
    return manifest, rows


def campaign_runs(directories):
    """Order explicit resume chains. Never silently mix unrelated repetitions."""
    runs = {}
    for directory in directories:
        manifest, rows = read_run(directory)
        rid = manifest["run_id"]
        if rid in runs:
            raise ValueError("duplicate run-id")
        runs[rid] = (Path(directory), manifest, rows)
    groups = defaultdict(list)
    for rid, (_, m, _) in runs.items():
        previous = m.get("previous_run_id")
        if previous:
            if previous not in runs:
                raise ValueError("missing predecessor: " + previous)
            old = runs[previous][1]
            for field in ("environment", "config", "ids_mode", "attacks", "rate_fps", "attack_s", "baseline_s", "post_s", "sensor_mode", "training_sha256", "calibration_sha256"):
                if m.get(field) != old.get(field):
                    raise ValueError("resume settings mismatch: " + field)
            if m.get("start_trial", 1) < old.get("start_trial", 1):
                raise ValueError("resume range moves backwards")
        groups[(m["environment"], m["config"], tuple(m["attacks"]))].append(rid)
    ordered = []
    for ids in groups.values():
        roots = [rid for rid in ids if not runs[rid][1].get("previous_run_id")]
        if len(roots) != 1:
            raise ValueError("campaign case requires one root run")
        rid = roots[0]
        visited = set()
        while rid:
            if rid in visited:
                raise ValueError("cyclic resume chain")
            visited.add(rid)
            ordered.append(runs[rid])
            children = [x for x in ids if runs[x][1].get("previous_run_id") == rid]
            if len(children) > 1:
                raise ValueError("branched resume chain")
            rid = children[0] if children else None
        if set(ids) != visited:
            raise ValueError("disconnected resume chain")
    return ordered


def summarize(directories):
    groups = defaultdict(list)
    seen = set()
    comparisons = {}
    for directory in directories:
        root = Path(directory)
        manifest, rows = read_run(root)
        if manifest["environment"] not in ("physical", "vcan"):
            raise ValueError("unexpected environment grade")
        comparison = (manifest["run_id"], manifest["environment"])
        settings = {field: manifest.get(field) for field in (
            "ecu_sha256", "source_sha256", "sensor_mode", "rate_fps", "attack_s", "baseline_s", "post_s")}
        if comparison in comparisons and comparisons[comparison] != settings:
            raise ValueError("mixed source/settings in one comparison")
        comparisons[comparison] = settings
        for attack in manifest["attacks"]:
            groups[(manifest["run_id"], manifest["environment"], manifest["config"],
                    manifest["ids_mode"], attack)]
        for row in rows:
            identity = (row["run_id"], row["config"], row["attack_type"], row["trial"])
            if identity in seen:
                raise ValueError("duplicate trial: preserve retries under a new run-id")
            seen.add(identity)
            groups[(row["run_id"], row["environment"], row["config"], row["ids_mode"], row["attack_type"])].append(row)
    for run_id, environment in comparisons:
        for config in (1, 2, 3):
            modes = {key[3] for key in groups if key[:3] == (run_id, environment, config)}
            for mode in modes or {"off" if config < 3 else "NOT_RUN"}:
                for attack in ("flooding", "fuzzy", "replay", "spoofing"):
                    groups[(run_id, environment, config, mode, attack)]
    result = []
    for key, rows in sorted(groups.items()):
        valid = [r for r in rows if r["status"] == "VALID"]
        measured = [r["attack_success"] for r in valid if r["attack_success"] is not None]
        latencies = [r["detect_latency_s"] for r in valid if r["detected"] and r["detect_latency_s"] is not None]
        expected = sum(r["normal_expected"] for r in valid)
        result.append({"run_id": key[0], "environment": key[1], "config": key[2], "ids_mode": key[3],
                       "attack": key[4], "attempts": len(rows), "valid": len(valid), "invalid": len(rows)-len(valid),
                       "missing_to_100": max(0, 100-len(valid)), "success_measured": len(measured),
                       "success_rate": sum(measured)/len(measured) if measured else None,
                       "auth_rejection_trial_rate": sum(r["blocked"] for r in valid)/len(valid) if valid else None,
                       "detection_rate": sum(r["detected"] for r in valid)/len(valid) if valid else None,
                       "undetected": sum(not r["detected"] for r in valid),
                       "late_over_3s": sum(t > 3 for t in latencies),
                       "latency_mean_s": sum(latencies)/len(latencies) if latencies else None,
                       "latency_max_s": max(latencies) if latencies else None,
                       "bms_delivery_ratio": sum(r["normal_delivered"] for r in valid)/expected if expected else None,
                       "observer": "reference_receiver", "product_verdict": "NOT_RUN",
                       "official_verdict": "NOT_RUN" if len(valid) < 100 else "PENDING_PRODUCT_AND_BUS_EVIDENCE"})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        result = summarize(args.runs)
        with Path(args.out).open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
        for row in result:
            print(row["environment"], row["config"], row["ids_mode"], row["attack"],
                  f"valid={row['valid']} invalid={row['invalid']} missing={row['missing_to_100']}",
                  row["official_verdict"])
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Summary stopped: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
