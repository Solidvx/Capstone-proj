import json

import pytest

from security.experiments.publication import align_frames, metric_summary, plan_summary
from security.experiments.summarize_live import campaign_runs, read_run, summarize
from security.experiments.can_capture import sha256
from security.experiments.evidence_bundle import create, verify


def make_run(tmp_path, name, start=1, count=100, previous=None, numbers=None, **settings):
    root = tmp_path / name
    root.mkdir()
    rows = [dict(run_id=name, environment="physical", config=3, ids_mode="rules+if",
                 attack_type="flooding", trial=n, status="INVALID", invalid_reason="ERROR")
            for n in (numbers if numbers is not None else [start])]
    ledger = root / "attempts.jsonl"
    ledger.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    manifest = dict(run_id=name, environment="physical", config=3, ids_mode="rules+if",
                    attacks=["flooding"], start_trial=start, trials_per_attack=count,
                    previous_run_id=previous, rate_fps=2800,
                    files_sha256={"attempts.jsonl": sha256(ledger)}, **settings)
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def test_resume_78_through_100_and_boundary(tmp_path):
    root = make_run(tmp_path, "r", start=78, count=23, numbers=[78, 100])
    assert len(read_run(root)[1]) == 2
    assert next(r for r in summarize([root]) if r["config"] == 3 and r["attack"] == "flooding")["invalid"] == 2
    bad = make_run(tmp_path, "bad", start=78, count=23, numbers=[101])
    with pytest.raises(ValueError, match="invalid trial identity"):
        read_run(bad)


def test_chain_order_missing_predecessor_and_settings(tmp_path):
    first = make_run(tmp_path, "a")
    second = make_run(tmp_path, "b", start=2, count=99, previous="a")
    assert [m["run_id"] for _, m, _ in campaign_runs([second, first])] == ["a", "b"]
    with pytest.raises(ValueError, match="missing predecessor"):
        campaign_runs([second])
    p = second / "manifest.json"
    m = json.loads(p.read_text()); m["rate_fps"] = 1000
    p.write_text(json.dumps(m))
    with pytest.raises(ValueError, match="settings mismatch"):
        campaign_runs([first, second])


def test_tamper_and_duplicate_are_rejected(tmp_path):
    root = make_run(tmp_path, "a")
    with pytest.raises(ValueError, match="duplicate run"):
        campaign_runs([root, root])
    (root / "attempts.jsonl").write_text("{}")
    with pytest.raises(ValueError, match="hash mismatch"):
        read_run(root)


def test_retry_does_not_erase_invalid_first_attempt():
    rows = [dict(trial=7, run_id="a", status="INVALID"), dict(trial=7, run_id="b", status="VALID")]
    plan, primary = plan_summary(rows)
    assert plan["recorded"] == 1 and plan["first_attempt_invalid"] == 1
    assert len(plan["retries"]) == 1 and primary[0]["status"] == "INVALID"


def test_mixed_clock_metrics_excluded_without_changing_original():
    row = dict(status="VALID", detected=True, detect_latency_s=.1, attack_success=None,
               normal_expected=30, normal_delivered=73)
    assert metric_summary([row])["delivery_ratio"] is None
    excluded = metric_summary([row], timing_allowed=False)
    assert excluded["detected_latency_mean_ms"] is None and excluded["normal_delivered_recorded"] == 73
    assert row["normal_delivered"] == 73


def test_undetected_not_zero_latency_and_ids_off_not_false_negative():
    rows = [dict(status="VALID", detected=True, detect_latency_s=.01),
            dict(status="VALID", detected=False, detect_latency_s=None), dict(status="INVALID")]
    result = metric_summary(rows)
    assert result["reference_detection_rate"] == .5
    assert result["detected_latency_samples"] == 1 and result["detected_latency_mean_ms"] == 10
    assert metric_summary(rows, ids_enabled=False)["reference_detection_rate"] is None


def test_alignment_counts_missing_frames_and_refuses_unknown_drift():
    normal = [(256, str(i)) for i in range(12)]
    result = list(align_frames(normal, normal[:3] + normal[4:]))
    assert [i for i, j in result if j is None] == [3]
    with pytest.raises(ValueError, match="unresolved"):
        list(align_frames(normal, [(512, "unknown")] + normal))


def test_branching_retries_require_explicit_policy(tmp_path):
    a = make_run(tmp_path, "a")
    b = make_run(tmp_path, "b", previous="a")
    c = make_run(tmp_path, "c", previous="a")
    with pytest.raises(ValueError, match="branched"):
        campaign_runs([a, b, c])


def test_recovery_archive_verifies_contents_and_never_overwrites(tmp_path):
    evidence = tmp_path / "docs/development/experiments/example/raw"
    evidence.mkdir(parents=True)
    (evidence / "capture.jsonl").write_text('{"data":"test"}\n')
    archive = tmp_path / "backup.zip"
    create(tmp_path, archive)
    assert verify(archive) == 1
    with pytest.raises(FileExistsError):
        create(tmp_path, archive)
    import zipfile
    with zipfile.ZipFile(archive, "a") as bundle:
        bundle.writestr("unexpected.txt", "untracked")
    with pytest.raises(ValueError, match="members mismatch"):
        verify(archive)
