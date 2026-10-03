import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from ivi_platform.scripts.analyze_period import InvalidMeasurement, analyze
from ivi_platform.scripts.normalize_candump_period import parse_log


def write_capture(root: Path, intervals_ms: list[float], extra_id: bool = False):
    csv_path = root / "period.csv"
    manifest_path = root / "manifest.json"
    timestamp = 1_000_000_000
    rows = []
    sample_id = 0
    rows.append(["run", "boot", sample_id, 0x100, timestamp, 8, "standard-data"])
    sample_id += 1
    for interval in intervals_ms:
        if extra_id:
            rows.append(["run", "boot", sample_id, 0x102, timestamp + 1_000_000, 8, "standard-data"])
            sample_id += 1
        timestamp += round(interval * 1_000_000)
        rows.append(["run", "boot", sample_id, 0x100, timestamp, 8, "standard-data"])
        sample_id += 1
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["run_id", "boot_id", "sample_id", "can_id", "timestamp_ns", "dlc", "frame_kind"])
        writer.writerows(rows)
    raw = csv_path.read_bytes()
    manifest = {
        "schema": "period-capture-v2", "run_id": "run", "boot_id": "boot",
        "clock": "monotonic", "target_can_id": 0x100, "row_count": len(rows),
        "csv_sha256": hashlib.sha256(raw).hexdigest(),
        "rx_errors_before": 0, "rx_errors_after": 0,
        "rx_dropped_before": 0, "rx_dropped_after": 0,
        "bus_off_before": 0, "bus_off_after": 0,
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return csv_path, manifest_path


class PeriodAnalysisTests(unittest.TestCase):
    def test_all_intervals_inclusive_boundaries_pass_with_mixed_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            values = [90.0, 110.0] + [100.0] * 98
            capture, manifest = write_capture(Path(directory), values, extra_id=True)
            result = analyze(capture, manifest)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["intervals"], 100)
            self.assertEqual(result["outlier_count"], 0)

    def test_single_outlier_fails_instead_of_using_percentage(self):
        with tempfile.TemporaryDirectory() as directory:
            capture, manifest = write_capture(Path(directory), [100.0] * 99 + [110.1])
            result = analyze(capture, manifest)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["outlier_count"], 1)

    def test_short_or_damaged_capture_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            capture, manifest = write_capture(Path(directory), [100.0] * 99)
            with self.assertRaises(InvalidMeasurement):
                analyze(capture, manifest)
            data = json.loads(manifest.read_text())
            data["row_count"] += 1
            manifest.write_text(json.dumps(data))
            with self.assertRaises(InvalidMeasurement):
                analyze(capture, manifest)

    def test_candump_absolute_parser_rejects_relative_verbose_and_backwards(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.log"
            path.write_text("(1000.000000001) can0 100#0011223344556677\n"
                            "(1000.100000001) can0 102#0011223344556677\n")
            self.assertEqual(parse_log(path, "can0"),
                             [(0x100, 1000000000001, 8), (0x102, 1000100000001, 8)])
            path.write_text("(1.0) can0 100 [8] 00 11 22 33 44 55 66 77\n")
            with self.assertRaises(ValueError):
                parse_log(path, "can0")
            path.write_text("(2.0) can0 100#00\n(1.0) can0 100#00\n")
            with self.assertRaises(ValueError):parse_log(path,"can0")
            path.write_text("(2.0) can0 00000100#0011223344556677\n")
            with self.assertRaises(ValueError):parse_log(path,"can0")

    def test_bad_dlc_wrong_target_and_malformed_manifest_are_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            capture, manifest = write_capture(Path(directory), [100]*100)
            metadata=json.loads(manifest.read_text())
            original=capture.read_text()
            capture.write_text(original.replace(",8,standard-data", ",1,standard-data"))
            metadata['csv_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
            manifest.write_text(json.dumps(metadata))
            with self.assertRaises(InvalidMeasurement):analyze(capture,manifest)
            capture.write_text(original)
            metadata['csv_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
            metadata['target_can_id']=0x102
            manifest.write_text(json.dumps(metadata))
            with self.assertRaises(InvalidMeasurement):analyze(capture,manifest)
            for value in (None, [], 123):
                manifest.write_text(json.dumps(value))
                with self.assertRaises(InvalidMeasurement):analyze(capture,manifest)


if __name__ == "__main__":
    unittest.main()
