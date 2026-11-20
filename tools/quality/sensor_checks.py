"""Log-only checks of known synthetic profiles, never a runtime IDS policy."""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path

from tools.quality import sensor_scenarios as source

FIELDS = {'schema', 'voltage_tolerance_v', 'current_tolerance_a',
          'max_voltage_step_v', 'freeze_hold_s', 'freeze_tolerance_v',
          'minimum_expected_change_v'}


def validate(policy):
    if not isinstance(policy, dict) or set(policy) != FIELDS or policy['schema'] != 'synthetic-sensor-checks-v1':
        raise ValueError('explicit synthetic-sensor-checks-v1 policy required')
    for key in FIELDS - {'schema'}:
        value = policy[key]
        try: finite = type(value) in (int, float) and math.isfinite(value)
        except OverflowError: finite = False
        if not finite or value <= 0:
            raise ValueError('finite positive explicit sensor check parameter required')
    return policy


class Checks:
    """Only observations and a predeclared reference enter the checks, no labels."""
    def __init__(self, policy):
        self.policy = dict(validate(policy))
        self.previous = None
        self.anchor = None

    def observe(self, t, voltage, current, expected_voltage, expected_current):
        try: finite = all(type(v) in (int, float) and math.isfinite(v)
                          for v in (t, voltage, current, expected_voltage, expected_current))
        except OverflowError: finite = False
        if not finite or t < 0:
            raise ValueError('finite synthetic observations/reference required')
        if self.previous is not None and t <= self.previous[0]:
            raise ValueError('strictly increasing profile time required')
        reasons = []
        p = self.policy
        if abs(voltage - expected_voltage) > p['voltage_tolerance_v']:
            reasons.append('VOLTAGE_PROFILE_MISMATCH')
        if abs(current - expected_current) > p['current_tolerance_a']:
            reasons.append('CURRENT_PROFILE_MISMATCH')
        if self.previous is not None and abs(voltage - self.previous[1]) > p['max_voltage_step_v']:
            reasons.append('VOLTAGE_JUMP')
        if self.anchor is None or abs(voltage - self.anchor[1]) > p['freeze_tolerance_v']:
            self.anchor = (t, voltage, expected_voltage)
        if (t - self.anchor[0] >= p['freeze_hold_s'] and
                abs(expected_voltage - self.anchor[2]) > p['minimum_expected_change_v']):
            reasons.append('VOLTAGE_FROZEN_AGAINST_PROFILE')
        self.previous = (t, voltage)
        return reasons


def run(input_root, output, policy):
    policy = dict(validate(policy))
    input_root, output = Path(input_root), Path(output)
    report_path = input_root / 'report.json'
    original = source.sha256(report_path)
    report = json.loads(report_path.read_text())
    if report.get('schema') != 'sensor-source-evaluation-v1' or report.get('status') != 'COMPLETE':
        raise ValueError('complete native sensor source evaluation required')
    manifest = source.validate_inputs(input_root, report['settings'])
    if source.sha256(input_root / 'inputs.json') != report['inputs_sha256']:
        raise ValueError('source manifest changed')
    native_hashes = {}
    for case in source.CASES:
        name = case + '/native.csv'
        native_hashes[name] = source.sha256(input_root / name)
        if native_hashes[name] != report['files_sha256'].get(name):
            raise ValueError('native observations changed')
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    result = {'schema': 'synthetic-sensor-checks-result-v1', 'status': 'INCOMPLETE',
              'environment': 'synthetic', 'policy': policy, 'cases': [],
              'input_report_sha256': original, 'native_sha256': native_hashes,
              'source_sha256': {name: source.sha256(source.ROOT / name) for name in
                  ('tools/quality/sensor_checks.py', 'tools/quality/sensor_scenarios.py', 'tools/quality/bms_profile.py')},
              'scope': 'Known-profile, log-only checks. No physical thresholds, CAN attack classification or UI alert.',
              'labels_used_by_checks': False, 'runtime_enabled': False}
    try:
        for case in source.CASES:
            checks = Checks(policy)
            counts = Counter()
            count = 0
            with (input_root / case / 'native.csv').open(newline='') as stream, (output / (case + '.jsonl')).open('x') as log:
                reader = csv.DictReader(stream)
                if reader.fieldnames != source.PRED + ['bms_payload_hex']:
                    raise ValueError('native observation header mismatch')
                for index, row in enumerate(reader):
                    if index >= report['settings']['samples']:
                        raise ValueError('extra native observations')
                    t = float(row['time_s'])
                    if abs(t - (index + 1) * .1) > 1e-9:
                        raise ValueError('native profile time mismatch')
                    # Allowed constant is a separate predeclared input profile.
                    # No fault labels or event start/end enter the checker.
                    expected_v = source.pack_voltage(source.reference(1 if case == 'allowed_constant' else index + 1))
                    voltage, current = float(row['observed_voltage_v']), float(row['observed_current_a'])
                    reasons = checks.observe(t, voltage, current, expected_v, -2.)
                    counts.update(reasons)
                    log.write(json.dumps({'sample_index': index, 'time_s': t, 'voltage_v': voltage,
                        'current_a': current, 'reference_voltage_v': expected_v, 'reference_current_a': -2.,
                        'reasons': reasons, 'domain': 'synthetic-sensor-input',
                        'severity': 'log-only', 'can_attack_type': None}, allow_nan=False) + '\n')
                    count += 1
            if count != report['settings']['samples']:
                raise ValueError('incomplete native observations')
            result['cases'].append({'case': case, 'samples': count, 'reason_counts': dict(counts)})
        source.validate_inputs(input_root, manifest['settings'])
        if source.sha256(report_path) != original or any(source.sha256(input_root / name) != digest
                for name, digest in native_hashes.items()) or any(source.sha256(source.ROOT / name) != digest
                for name, digest in result['source_sha256'].items()):
            raise ValueError('input/source changed during checks')
        result['status'] = 'COMPLETE'
    except (ValueError, OSError, KeyError, TypeError) as error:
        result['status'] = 'INVALID'
        result['error'] = str(error)
    except KeyboardInterrupt:
        result['status'] = 'INTERRUPTED'
    result['files_sha256'] = {p.name: source.sha256(p) for p in output.iterdir() if p.is_file()}
    source.save(output / 'report.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root', required=True, type=Path)
    parser.add_argument('--settings', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = run(args.input_root, args.output_dir, json.loads(args.settings.read_text()))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps(result))
    return 0 if result['status'] == 'COMPLETE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
