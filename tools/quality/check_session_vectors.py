"""Compare candidate C++ builds against the independent Python reference.

Only built-in, explicitly public dummy inputs are emitted by these test tools.
No product process is launched and no real key file is read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def parse_rows(rows: str) -> dict[str, str]:
    result = {}
    for row in rows.splitlines():
        name, value = row.split("\t")
        if name in result:
            raise ValueError("duplicate vector name")
        result[name] = value
    if not result:
        raise ValueError("no vectors produced")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecu", type=Path, required=True)
    parser.add_argument("--ivi", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--protocol", choices=("session", "diagnostic"), default="session")
    parser.add_argument("--lima-instance", help="Use already running Lima VM; executable paths must be absolute guest paths")
    args = parser.parse_args()
    if args.protocol == "diagnostic":
        from security.tests.diagnostic_fixtures import dummy_vectors
    else:
        from security.tests.test_can_session_candidate import dummy_vectors
    expected = dummy_vectors()
    fixture_name = "diagnostic-v1-vectors.tsv" if args.protocol == "diagnostic" else "session-v2-vectors.tsv"
    fixture = ROOT / "docs/aidlc/changes/CHG-029" / fixture_name
    if parse_rows(fixture.read_text()) != expected:
        raise RuntimeError("frozen fixture differs from Python reference")
    builds = {}
    for role, path in (("ecu", args.ecu), ("ivi", args.ivi)):
        if args.lima_instance:
            if not path.is_absolute():
                raise ValueError("Lima executables must use absolute guest paths")
            prefix = ["limactl", "shell", args.lima_instance]
            executable = str(path)  # do not resolve guest /tmp to host /private/tmp
        else:
            prefix = []
            executable = str(path.resolve())
        subprocess.run(prefix + [executable], check=True, capture_output=True, text=True, timeout=30)
        emitted = subprocess.run(prefix + [executable, "--emit-dummy-vectors"], check=True,
                                 capture_output=True, text=True, timeout=15)
        if parse_rows(emitted.stdout) != expected:
            raise RuntimeError(role + " differs from Python reference")
        if args.lima_instance:
            hashed = subprocess.run(prefix + ["sha256sum", "--", executable], check=True,
                                    capture_output=True, text=True, timeout=15).stdout.split()[0]
            if len(hashed) != 64 or any(c not in "0123456789abcdef" for c in hashed):
                raise ValueError("invalid guest executable hash")
        else:
            hashed = hashlib.sha256(Path(executable).read_bytes()).hexdigest()
        builds[role] = {"fields": len(expected), "status": "PASS", "executable_sha256": hashed}
    sources = ["common/can_session_crypto.h", "common/can_session_crypto.cpp",
               "common/can_session_frames.h", "common/can_session_frames.cpp",
               "common/test_can_session_candidate.cpp", "security/can_session.py",
               "security/tests/test_can_session_candidate.py", "tools/quality/check_session_vectors.py",
               "docs/aidlc/changes/CHG-029/" + fixture_name]
    if args.protocol == "diagnostic":
        sources += ["common/can_diagnostic.h", "common/can_diagnostic.cpp", "common/test_can_diagnostic.cpp",
                    "security/can_diagnostic.py", "security/tests/diagnostic_fixtures.py", "security/tests/test_can_diagnostic.py",
                    "docs/aidlc/changes/CHG-029/diagnostic-inputs.tsv"]
    result = {"status": "PASS", "scope": "candidate host crypto and framing only; no active product session",
              "protocol": args.protocol,
              "runner": "lima" if args.lima_instance else "native",
              "reference": "independent Python hmac HKDF vs C++ OpenSSL EVP HKDF",
              "builds": builds, "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                                        for name in sources}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "protocol": args.protocol, "vector_fields": len(expected), "builds": list(builds)}))


if __name__ == "__main__":
    main()
