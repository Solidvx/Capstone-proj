"""Run from repository root after rebuilding publication; read-only verification."""
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from security.experiments.publication import verified_inventory

ROOT = Path.cwd()
BASE = ROOT / "docs/development/experiments"
FORMAL = BASE / "physical-ablation-formal-2026-10-04"
OUT = FORMAL / "publication"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


counts = {b.name: verified_inventory(b) for b in BASE.glob("*2026*")}
summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
assert len(summary["cases"]) == 12 and len(summary["runs"]) == 16
assert sum(c["all_attempts"]["attempts"] for c in summary["cases"]) == 1201
assert sum(c["all_attempts"]["invalid"] for c in summary["cases"]) == 4
assert sum(c["plan"]["first_attempt_valid"] for c in summary["cases"]) == 1196
assert all(not c["plan"]["missing_numbers"] for c in summary["cases"])
flood = next(c for c in summary["cases"] if c["config"] == 3 and c["attack"] == "flooding")
assert flood["timing_eligible_primary_subset"]["valid"] == 23
assert flood["timing_subset_run_ids"] == ["ABLATION-FORMAL-C3-FLOOD-003"]
hashes = json.loads((OUT / "outputs-sha256.json").read_text(encoding="utf-8"))
assert all(sha(OUT / name) == digest for name, digest in hashes.items())
provenance = json.loads((OUT / "provenance.json").read_text(encoding="utf-8"))
assert provenance["policy_sha256"] == sha(FORMAL / "publication-policy.json")
assert all(sha(ROOT / "security/experiments" / name) == digest for name, digest in provenance["tool_sha256"].items())
checks = [json.loads(p.read_text(encoding="utf-8")) for p in OUT.glob("runs/*/crosscheck.json")]
assert all(c["receiver_matches_filtered_can"] for c in checks)
assert all(c["ids_sent_matches_non_injected_ecu_and_ivi"] for c in checks)
assert sum(c["ecu_missing_count"] for c in checks) == 3
legacy = FORMAL / "tools/legacy-analysis"
scripts = json.loads((legacy / "manifest.json").read_text(encoding="utf-8"))
assert len(scripts) == 38 and all(sha(legacy / r["preserved"]) == r["sha256"] for r in scripts)

files = [*BASE.rglob("*.md"), *Path(__file__).parent.glob("*.md"),
         *Path("docs/aidlc/changes/CHG-014").glob("*.md")]
files += [Path(p) for p in ["docs/SRS.md", "docs/SDD-ECU.md", "docs/SDD-IVI.md", "docs/TARA.md", "docs/TEST_PLAN.md", "docs/development/README.md", "docs/development/playbooks/live-security-validation.md", "docs/aidlc/structure/document-map.md", "plan/ECU.md", "plan/IVI.md"]]
bad = []
fences = []
for p in files:
    if "raw" in p.parts:
        continue
    text = p.read_text(encoding="utf-8-sig")
    if len(re.findall(r"^```", text, re.M)) % 2:
        fences.append(str(p))
    for target in re.findall(r"\]\(([^)]+)\)", text):
        target = target.split("#")[0].strip("<>")
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        if not (p.parent / target).exists():
            bad.append([str(p), target])
assert not bad, bad
assert not fences, fences
print(json.dumps({"inventory_counts": counts, "output_hashes_verified": len(hashes),
                  "case_count": 12, "run_count": 16, "attempts": 1201,
                  "first_attempt_valid": 1196, "invalid": 4,
                  "receiver_matches": len(checks), "missing_ecu_frames_in_ivi": 3,
                  "legacy_scripts_verified": len(scripts), "broken_local_links": bad,
                  "unbalanced_fences": fences}, ensure_ascii=False, indent=2))
