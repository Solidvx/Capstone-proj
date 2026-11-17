"""Actual ECU/owned worker/vcan authentication, public synthetic syscall input."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("ecu", "rx_fixture", "worker_fixture", "peer", "policy", "config_example", "out_parent"):
        p.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = p.parse_args()
    interface = os.environ.get("CAPSTONE_SESSION_TEST_INTERFACE", "")
    if not interface:
        print("SKIP: explicit existing vcan required")
        return 77
    if not interface.startswith("vcan") or "/" in interface or not Path("/sys/devices/virtual/net", interface).is_dir():
        raise ValueError("virtual interface only")
    args.out_parent.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix="physical-product-", dir=args.out_parent))
    cases = []
    with tempfile.TemporaryDirectory(prefix="physical-input-") as directory:
        root = Path(directory)
        root.chmod(0o700)
        ecu = root / "adaptive_ecu"
        shutil.copyfile(args.ecu, ecu)
        ecu.chmod(0o700)
        worker = root / "physical_battery_worker"
        shutil.copyfile(args.worker_fixture, worker)
        worker.chmod(0o700)
        key = root / "public-dummy-key.bin"
        key.write_bytes(bytes(range(32)))
        key.chmod(0o600)
        device = root / "public-i2c-device"
        device.write_bytes(b"")
        probe = root / "28-000000000000"
        probe.mkdir()
        measured_config = None
        for case in ("normal", "measured", "temperature-error", "electrical-error", "known", "receive-error", "unknown", "auto-rest"):
            shutil.copyfile(args.rx_fixture if case == "receive-error" else args.ecu, ecu)
            (probe / "w1_slave").write_text("3c 01 7f 80 7f ff 04 10 cf : crc=cf YES\n"
                "3c 01 7f 80 7f ff 04 10 cf t=19750\n" if case != "temperature-error" else "NO\n")
            values = dict(line.split("=", 1) for line in args.config_example.read_text().splitlines()
                          if line and not line.startswith("#"))
            values.update(i2c_device=str(device if case != "electrical-error" else root / "missing-device"),
                          w1_root=str(root), period_ms="100", read_timeout_ms="1000", freshness_ms="1000", max_interval_ms="1000")
            if case == "known":
                values.update(initial_soc_percent="80", measured_capacity_ah="2.295", capacity_test_id="PUBLIC-TEST-ONLY")
            elif case == "unknown":
                values.update(initial_soc_percent="unknown")
            config = root / "physical.conf"
            config.write_text(measured_config if case == "measured" else "".join(f"{k}={v}\n" for k, v in values.items()))
            log = out / (case + ".log")
            with log.open("w+") as stream:
                child = subprocess.Popen([str(ecu), "--interface", interface, "--sensor-mode", "physical",
                    "--physical-config", str(config), "--protocol", "session-v2", "--session-policy", str(args.policy),
                    "--key", str(key)], stdout=stream, stderr=subprocess.STDOUT,
                    env=dict(os.environ, CAPSTONE_TEST_INA_ZERO_CURRENT="1" if case == "auto-rest" else "0"))
                try:
                    option = "--ivi-physical" if case == "normal" else "--ivi-physical-" + case
                    result = subprocess.run([str(args.peer), option], capture_output=True, text=True,
                                            timeout=85 if case == "auto-rest" else 28)
                    (out / (case + "-peer.log")).write_text(result.stdout + result.stderr)
                    assert result.returncode == 0, result.stdout + result.stderr
                    assert child.poll() is None
                finally:
                    if child.poll() is None:
                        child.terminate()
                        try:
                            child.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            child.wait(timeout=3)
                    stream.flush()
                stream.seek(0)
                text = stream.read()
            assert child.returncode == 0, text
            samples = [json.loads(line) for line in text.splitlines() if line.startswith('{"result":"PHYSICAL_SAMPLE"')]
            assert len(samples) >= 3, text
            last = samples[-1]
            assert (last["soc_estimate_percent"] is not None) == (case in ("known", "auto-rest"))
            assert (last["soh_estimate_percent"] is not None) == (case in ("known", "measured"))
            assert "SOH virtual capacity" not in text
            assert last["soc_basis"] == (1 if case == "known" else 0 if case == "unknown" else 2)
            if case == "auto-rest":
                assert any(row["soc_update"] == "initialized" for row in samples)
                assert 10 < last["soc_estimate_percent"] < 15
            if case == "normal":
                valid = [row for row in samples if row['ina_quality'] == row['temperature_quality'] == 2 and row['voltage_v'] is not None]
                assert len(valid) >= 3
                capacity_script = Path(__file__).resolve().parents[1] / 'scripts/measure_physical_capacity.py'
                result = subprocess.run([sys.executable, str(capacity_script), '--log', str(log), '--config', str(config),
                    '--out', str(out / 'capacity'), '--start-sequence', str(valid[0]['sequence']),
                    '--end-sequence', str(valid[-1]['sequence']), '--cell-id', 'PUBLIC-SYSCALL-FIXTURE',
                    '--test-id', 'PUBLIC-SYNTHETIC-CAPACITY', '--endpoint-reference', 'PUBLIC-FIXTURE-NOT-PHYSICAL-ENDPOINTS',
                    '--end-voltage-v', str(valid[-1]['voltage_v']), '--endpoint-tolerance-v', '0.001',
                    '--charge-noise-tolerance-ah', '0', '--max-charge-current-a', '0', '--full-discharge-confirmed'],
                    capture_output=True, text=True, timeout=5)
                assert result.returncode == 0, result.stderr
                measured_config = (out / 'capacity/physical-battery.with-soh.conf').read_text()
                measured = json.loads((out / 'capacity/report.json').read_text())
                assert measured['measured_capacity_ah'] > 0 and measured['physical_accuracy_verified'] is False
            if case == "receive-error":
                assert "ERR_WATCHDOG_MAX_RESTART task=can-rx" in text
                assert "Fail-safe transition:" not in text
            cases.append({"case": case, "ecu_exit": child.returncode, "peer_exit": result.returncode,
                          "sample_rows": len(samples), "last_sample": last})
        bad = subprocess.run([str(ecu), "--sensor-mode", "physical", "--physical-config", str(config),
                              "--protocol", "legacy-v1", "--secoc", "off"], capture_output=True, text=True, timeout=3)
        assert bad.returncode == 2 and "physical mode requires" in bad.stderr
    report = {"status": "PASS", "physical_hardware_tested": False, "cases": cases}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "cases": len(cases), "out": str(out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
