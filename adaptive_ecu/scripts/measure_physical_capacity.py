#!/usr/bin/env python3
"""Measure capacity from one stopped ECU log, then prepare a new SOH config.

No sensor, CAN, SSH, charging or load control. The operator must independently
confirm full-charge/discharge endpoints and the same physical cell throughout.
Never use this tool or an estimated SOC as a discharge cutoff controller.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('finite number required')
    return float(value)


def integer(value):
    if type(value) is not int or not 0 <= value < 2**64:
        raise ValueError('unsigned integer required')
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON field')
        result[key] = value
    return result


def bad_constant(_):
    raise ValueError('nonfinite JSON input')


def stable_read(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError('bounded regular input file required')
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    if len(data) > limit or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError('input changed; stop the ECU before evaluating its log')
    return data


def settings_from(data):
    values = {}
    for line in data.decode().splitlines():
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or not key or not value or key in values:
            raise ValueError('invalid or duplicate configuration setting')
        values[key] = value
    return values


def evaluate(data, config_data, start, end, *, cell_id, test_id, endpoint_reference,
             end_voltage_v, endpoint_tolerance_v, charge_noise_tolerance_ah,
             max_charge_current_a, full_discharge_confirmed):
    for label in (cell_id, test_id):
        if not isinstance(label, str) or not re.fullmatch('[A-Za-z0-9_-]{1,64}', label):
            raise ValueError('public cell and test labels required')
    if not full_discharge_confirmed or not endpoint_reference or len(endpoint_reference) > 512 or any(
            ord(c) < 32 for c in endpoint_reference):
        raise ValueError('independent full-discharge endpoint confirmation/reference required')
    if not 0 < finite(end_voltage_v) <= 26 or not 0 <= finite(endpoint_tolerance_v) <= .1:
        raise ValueError('explicit endpoint voltage and bounded comparison tolerance required')
    config = settings_from(config_data)
    nominal = finite(float(config['nominal_capacity_ah']))
    max_interval = int(config['max_interval_ms'])
    if nominal <= 0 or not 1 <= max_interval <= 60000:
        raise ValueError('positive nominal capacity and bounded interval required')
    if not 0 <= finite(charge_noise_tolerance_ah) <= nominal * .01 or not 0 <= finite(max_charge_current_a) <= .02:
        raise ValueError('bounded charge-noise tolerances required')
    if not 1 <= integer(start) < integer(end):
        raise ValueError('explicit increasing sample window required')
    if not data.endswith(b'\n'):
        raise ValueError('incomplete log tail')
    expected_config = hashlib.sha256(config_data).hexdigest()
    rows = []
    identity = None
    previous_sequence = 0
    for line in data.splitlines():
        if len(line) > 16384:
            raise ValueError('oversized log line')
        if not line.startswith(b'{'):
            continue
        row = json.loads(line, object_pairs_hook=unique_object, parse_constant=bad_constant)
        if not isinstance(row, dict):
            raise ValueError('JSON object required')
        if row.get('result') == 'ECU_PHYSICAL_LINEAGE':
            if rows:
                raise ValueError('multiple ECU executions in log')
            continue
        if row.get('result') != 'PHYSICAL_SAMPLE':
            continue
        seq = integer(row.get('sequence'))
        if seq <= previous_sequence:
            raise ValueError('repeated/backward sample sequence')
        previous_sequence = seq
        instance, clock, fingerprint = (row.get(k) for k in ('process_instance_id', 'clock_id', 'model_config_sha256'))
        if not isinstance(instance, str) or not re.fullmatch('[0-9a-f]{32}', instance) or not isinstance(clock, str) or not re.fullmatch(
                '[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', clock) or fingerprint != expected_config:
            raise ValueError('new ECU log with matching configuration/clock/instance required')
        current_identity = (instance, clock, fingerprint)
        if identity is None:
            identity = current_identity
        if identity != current_identity:
            raise ValueError('mixed execution/clock/configuration')
        if not start <= seq <= end:
            continue
        if rows and (seq != rows[-1]['sequence'] + 1 or not 0 < integer(row.get('sample_monotonic_ms')) - rows[-1]['sample_monotonic_ms'] <= max_interval):
            raise ValueError('missing sample or acquisition time gap')
        integer(row.get('sample_monotonic_ms'))
        if not row['sample_monotonic_ms'] or row.get('observation_gap') is not False or row.get('physical_accuracy_verified') is not False:
            raise ValueError('observation gap or unsupported accuracy claim')
        if type(row.get('ina_quality')) is not int or row['ina_quality'] != 2 or type(row.get('temperature_quality')) is not int or row['temperature_quality'] != 2:
            raise ValueError('all capacity-test sensor samples must be valid')
        voltage, current, temperature = (finite(row.get(k)) for k in ('voltage_v', 'current_a', 'temperature_c'))
        if not 0 < voltage <= 26 or abs(current) > 2147 or not -55 <= temperature <= 125:
            raise ValueError('sensor values outside numeric range')
        if current > max_charge_current_a:
            raise ValueError('charging occurred during the discharge interval')
        for key in ('charged_ah', 'discharged_ah'):
            value = finite(row.get(key))
            if value < 0 or (rows and value < rows[-1][key]):
                raise ValueError('invalid or rolled-back charge accumulator')
        rows.append(row)
    if len(rows) < 3 or rows[0]['sequence'] != start or rows[-1]['sequence'] != end:
        raise ValueError('complete explicit window with at least three samples required')
    first, last = rows[0], rows[-1]
    if abs(last['voltage_v'] - end_voltage_v) > endpoint_tolerance_v + 1e-9:
        raise ValueError('last measurement differs from the confirmed discharge endpoint')
    charged = last['charged_ah'] - first['charged_ah']
    discharged = last['discharged_ah'] - first['discharged_ah']
    if charged > charge_noise_tolerance_ah:
        raise ValueError('charge accumulation exceeds the declared noise allowance')
    capacity = discharged - charged
    if not math.isfinite(capacity) or capacity <= 0:
        raise ValueError('positive net discharged capacity required')
    ratio = capacity / nominal
    if not math.isfinite(ratio):
        raise ValueError('capacity ratio outside numeric range')
    report = {'schema': 'physical-capacity-test-v1', 'status': 'MEASURED_WITH_ATTESTED_ENDPOINTS',
              'cell_id': cell_id, 'test_id': test_id, 'endpoint_reference': endpoint_reference,
              'full_discharge_confirmed': True, 'endpoint_verification': 'operator-attested',
              'physical_accuracy_verified': False, 'source_sha256': hashlib.sha256(data).hexdigest(),
              'configuration_sha256': expected_config, 'process_instance_id': identity[0], 'clock_id': identity[1],
              'start_sequence': start, 'end_sequence': end, 'samples': len(rows),
              'duration_s': (last['sample_monotonic_ms'] - first['sample_monotonic_ms']) / 1000,
              'start_voltage_v': first['voltage_v'], 'end_voltage_v': last['voltage_v'],
              'confirmed_end_voltage_v': end_voltage_v, 'endpoint_tolerance_v': endpoint_tolerance_v,
              'minimum_temperature_c': min(row['temperature_c'] for row in rows),
              'maximum_temperature_c': max(row['temperature_c'] for row in rows),
              'charged_ah': charged, 'discharged_ah': discharged,
              'charge_noise_tolerance_ah': charge_noise_tolerance_ah, 'max_charge_current_a': max_charge_current_a,
              'measured_capacity_ah': capacity, 'nominal_capacity_ah': nominal,
              'soh_capacity_ratio': ratio, 'soh_estimate_percent': min(100., ratio * 100),
              'note': 'Net charge from the production meter, not SOC change. Same-cell and full endpoints are operator attestations. No load cutoff, charging, service activation or hardware accuracy verification.'}
    replacements = {'measured_capacity_ah': format(capacity, '.17g'), 'capacity_test_id': test_id}
    if not replacements.keys() <= config.keys():
        raise ValueError('complete physical runtime configuration required')
    output = '\n'.join(line.partition('=')[0] + '=' + replacements[line.partition('=')[0]]
                       if line.partition('=')[0] in replacements else line for line in config_data.decode().splitlines()) + '\n'
    report['output_configuration_sha256'] = hashlib.sha256(output.encode()).hexdigest()
    return report, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--start-sequence', type=int, required=True)
    parser.add_argument('--end-sequence', type=int, required=True)
    parser.add_argument('--cell-id', required=True)
    parser.add_argument('--test-id', required=True)
    parser.add_argument('--endpoint-reference', required=True)
    parser.add_argument('--end-voltage-v', type=float, required=True)
    parser.add_argument('--endpoint-tolerance-v', type=float, required=True)
    parser.add_argument('--charge-noise-tolerance-ah', type=float, required=True)
    parser.add_argument('--max-charge-current-a', type=float, required=True)
    parser.add_argument('--full-discharge-confirmed', action='store_true')
    args = parser.parse_args()
    try:
        report, output = evaluate(stable_read(args.log, 128 * 1024 * 1024), stable_read(args.config, 8192),
            args.start_sequence, args.end_sequence, cell_id=args.cell_id, test_id=args.test_id,
            endpoint_reference=args.endpoint_reference, end_voltage_v=args.end_voltage_v,
            endpoint_tolerance_v=args.endpoint_tolerance_v, charge_noise_tolerance_ah=args.charge_noise_tolerance_ah,
            max_charge_current_a=args.max_charge_current_a, full_discharge_confirmed=args.full_discharge_confirmed)
        args.out.mkdir(mode=0o700, parents=False, exist_ok=False)
        (args.out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        config_path = args.out / 'physical-battery.with-soh.conf'
        fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(output)
        print(json.dumps({'status': report['status'], 'measured_capacity_ah': report['measured_capacity_ah'],
                          'soh_estimate_percent': report['soh_estimate_percent'], 'out': str(args.out)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as error:
        print('capacity test rejected: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
