#!/usr/bin/env python3
"""Validate captured sensor evidence and use the existing C++ SOC/SOH core offline."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


UUID = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
CALIBRATION_FIELDS = ('calibration_id', 'shunt_ohm', 'requested_current_lsb_a',
                      'calibration_register', 'effective_current_lsb_a',
                      'battery_current_sign', 'current_zero_a', 'terminal_offset_v')
INA_ERRORS = {'OPEN_ERROR', 'START_ERROR', 'IO_ERROR', 'NOT_STARTED', 'CONFIGURATION_CHANGED',
              'OVERFLOW', 'RANGE_ERROR', 'INCONSISTENT_REGISTERS', 'TIMEOUT', 'CHILD_ERROR', 'INTERRUPTED'}
TEMP_ERRORS = {'OPEN_ERROR', 'IO_ERROR', 'MALFORMED', 'CRC_ERROR', 'RETAINED_VALUE', 'RANGE_ERROR',
               'AMBIGUOUS_85C', 'TIMEOUT', 'CHILD_ERROR', 'INTERRUPTED'}


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('finite numeric value required')
    return float(value)


def integer(value):
    if type(value) is not int or not 0 <= value < 2**64:
        raise ValueError('unsigned integer required')
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:raise ValueError('duplicate JSON field')
        result[key] = value
    return result


def reject_constant(_):
    raise ValueError('nonfinite JSON constant')


def normalize_capture(data):
    if not data or not data.endswith(b'\n'):raise ValueError('empty or incomplete capture tail')
    output = ['sequence,monotonic_ms,voltage_v,current_a,status']
    metadata, previous_sample, previous_end, previous_ina = None, -1, 0, 0
    temperatures, missing, dropped = {}, 0, 0
    for line in data.splitlines():
        if not line or len(line) > 8192:raise ValueError('empty or oversized capture row')
        row = json.loads(line, object_pairs_hook=unique_object, parse_constant=reject_constant)
        if not isinstance(row, dict) or row.get('schema') != 'physical-sensor-v2':
            raise ValueError('physical-sensor-v2 capture required; recapture older logs')
        if row.get('clock') != 'host-monotonic-ms' or row.get('physical_accuracy_verified') is not False:
            raise ValueError('unsupported clock or accuracy assertion')
        capture, clock = row.get('capture_id'), row.get('clock_id')
        if not isinstance(capture, str) or not UUID.fullmatch(capture) or not isinstance(clock, str) or not UUID.fullmatch(clock):
            raise ValueError('explicit capture and Linux clock identity required')
        calibration = {key: row[key] for key in CALIBRATION_FIELDS}
        if not isinstance(calibration['calibration_id'], str) or not re.fullmatch('[A-Za-z0-9_-]{1,64}', calibration['calibration_id']):
            raise ValueError('invalid public calibration label')
        shunt = finite(calibration['shunt_ohm']);lsb = finite(calibration['requested_current_lsb_a'])
        if shunt <= 0 or lsb <= 0:raise ValueError('positive shunt/LSB required')
        cal = integer(calibration['calibration_register'])
        scale = shunt*lsb
        if not math.isfinite(scale) or scale <= 0:raise ValueError('capture calibration scale overflow/underflow')
        calculated = .04096/scale
        if not math.isfinite(calculated) or not 2 <= calculated < 65536 or cal != (int(calculated) & 0xfffe):
            raise ValueError('capture calibration differs from declared scale')
        effective = finite(calibration['effective_current_lsb_a'])
        if not math.isclose(effective, .04096/(cal*shunt), rel_tol=1e-9):raise ValueError('invalid effective current scale')
        if type(calibration['battery_current_sign']) is not int or calibration['battery_current_sign'] not in (-1, 1):
            raise ValueError('explicit current direction required')
        finite(calibration['current_zero_a']);finite(calibration['terminal_offset_v'])
        identity = {'capture_id': capture, 'clock_id': clock, 'calibration': calibration}
        if metadata is None:metadata = identity
        elif metadata != identity:raise ValueError('mixed capture/clock/calibration input')
        sample = integer(row.get('sample'));start = integer(row.get('sample_started_ms'));end = integer(row.get('sample_completed_ms'))
        if not start or end < start or start < previous_end or sample <= previous_sample or sample >= 100000:
            raise ValueError('backward sample/time or capture bound exceeded')
        if previous_sample == -1 and sample != 0:raise ValueError('capture prefix missing')
        dropped += sample-previous_sample-1
        previous_sample, previous_end = sample, end
        ina, temp = row.get('ina219'), row.get('ds18b20')
        if not isinstance(ina, dict) or not isinstance(temp, dict):raise ValueError('two channel records required')
        temperature_status = temp.get('status')
        if temperature_status == 'OK':
            value = temp.get('measurement')
            if not isinstance(value, dict) or not -55 <= finite(value.get('temperature_c')) <= 125:
                raise ValueError('invalid temperature measurement')
            t0, t1 = integer(temp.get('started_ms')), integer(temp.get('completed_ms'))
            if not start <= t0 <= t1 <= end:raise ValueError('temperature time outside sample')
        elif temperature_status not in TEMP_ERRORS or temp.get('measurement', True) is not None:
            raise ValueError('invalid temperature error record')
        temperatures[temperature_status] = temperatures.get(temperature_status, 0)+1
        if ina.get('status') == 'OK':
            value = ina.get('measurement')
            if not isinstance(value, dict):raise ValueError('missing INA measurement')
            voltage = finite(value.get('terminal_v'));current = finite(value.get('battery_current_a'))
            t0, t1 = integer(ina.get('started_ms')), integer(ina.get('completed_ms'))
            if not start <= t0 <= t1 <= end or t1 <= previous_ina:
                raise ValueError('new INA acquisition time required')
            if not 0 <= voltage <= 26:raise ValueError('INA voltage out of numeric range')
            previous_ina = t1
            output.append(f'{sample+1},{t1},{voltage:.17g},{current:.17g},OK')
        elif ina.get('status') in INA_ERRORS and ina.get('measurement', True) is None:
            missing += 1;output.append(f'{sample+1},{end},,,ERROR')
        else:raise ValueError('invalid INA error record')
    return '\n'.join(output)+'\n', dict(metadata, rows=len(output)-1, missing_electrical_rows=missing,
                                      missing_sequence_rows=dropped, temperature_status_counts=temperatures)


def run(args):
    if not re.fullmatch('[A-Za-z0-9_-]{1,48}', args.model_id):raise ValueError('public model label required')
    capacity = finite(args.capacity_ah)
    if capacity <= 0 or not 1 <= args.max_interval_ms <= 60000:raise ValueError('positive capacity and bounded interval required')
    if args.initial_soc_percent is not None and not 0 <= finite(args.initial_soc_percent) <= 100:raise ValueError('SOC percent range')
    if not 1 <= args.timeout_s <= 120 or not 1 <= args.max_input_bytes <= 128*1024*1024:raise ValueError('explicit read/time bounds required')
    supplied = args.measured_capacity_ah is not None
    if supplied != args.capacity_test_confirmed or supplied != (args.capacity_test_id is not None):
        raise ValueError('external capacity requires confirmation and test label')
    if supplied and (finite(args.measured_capacity_ah) <= 0 or not re.fullmatch('[A-Za-z0-9_-]{1,64}', args.capacity_test_id)):
        raise ValueError('invalid external capacity basis')
    fd = os.open(args.capture, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > args.max_input_bytes:raise ValueError('bounded regular capture file required')
        data = stream.read(args.max_input_bytes+1);after = os.fstat(stream.fileno())
    if len(data) > args.max_input_bytes or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError('capture changed during read; stop capture first')
    csv, source = normalize_capture(data)
    public_config = {'model_id': args.model_id, 'capacity_ah': capacity, 'initial_soc_percent': args.initial_soc_percent,
                     'max_interval_ms': args.max_interval_ms, 'calibration': source['calibration']}
    config_hash = hashlib.sha256(json.dumps(public_config, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    evaluator = args.evaluator.resolve()
    evaluator_hash = hashlib.sha256(evaluator.read_bytes()).hexdigest()
    command = [str(evaluator), '--model-id', args.model_id+':'+config_hash,
               '--capacity-ah', str(capacity), '--max-interval-ms', str(args.max_interval_ms)]
    if args.initial_soc_percent is not None:command += ['--initial-soc-percent', str(args.initial_soc_percent)]
    if supplied:command += ['--measured-capacity-ah', str(args.measured_capacity_ah), '--capacity-test-confirmed']
    result = subprocess.run(command, input=csv, text=True, capture_output=True, timeout=args.timeout_s)
    if result.returncode not in (0, 1):raise ValueError('numeric evaluator failed: '+result.stderr[-1000:])
    if hashlib.sha256(evaluator.read_bytes()).hexdigest() != evaluator_hash:raise ValueError('evaluator changed during execution')
    estimates = [json.loads(line, object_pairs_hook=unique_object, parse_constant=reject_constant) for line in result.stdout.splitlines()]
    if len(estimates) != source['rows']:raise ValueError('incomplete estimate output')
    args.out.mkdir(mode=0o700, parents=False, exist_ok=False)
    output = result.stdout.encode();(args.out/'estimates.jsonl').write_bytes(output)
    temperature_ok = source['temperature_status_counts'].get('OK', 0) == source['rows']
    status = 'COMPLETE_WITH_GAPS' if result.returncode else 'COMPLETE' if temperature_ok else 'COMPLETE_WITH_SENSOR_ERRORS'
    report = {'schema': 'physical-estimation-v1', 'status': status,
              'source_sha256': hashlib.sha256(data).hexdigest(), 'source': source, 'configuration': public_config,
              'configuration_sha256': config_hash, 'evaluator_sha256': evaluator_hash,
              'estimates_sha256': hashlib.sha256(output).hexdigest(), 'last_estimate': estimates[-1],
              'capacity_test_id': args.capacity_test_id, 'capacity_basis_verification': 'operator-attested' if supplied else 'not-measured',
              'physical_accuracy_verified': False, 'note': 'Offline estimates. Temperature quality is reported separately; no CAN/UI, safety control or discharge cutoff.'}
    (args.out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    return report, 1 if result.returncode or not temperature_ok else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--evaluator', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--model-id', required=True)
    parser.add_argument('--capacity-ah', type=float, required=True)
    parser.add_argument('--initial-soc-percent', type=float)
    parser.add_argument('--max-interval-ms', type=int, required=True)
    parser.add_argument('--max-input-bytes', type=int, required=True)
    parser.add_argument('--timeout-s', type=int, required=True)
    parser.add_argument('--measured-capacity-ah', type=float)
    parser.add_argument('--capacity-test-id')
    parser.add_argument('--capacity-test-confirmed', action='store_true')
    args = parser.parse_args()
    try:
        report, code = run(args)
        print(json.dumps({'status': report['status'], 'rows': report['source']['rows'], 'last_estimate': report['last_estimate'], 'out': str(args.out)}, ensure_ascii=False))
        return code
    except (OSError, ValueError, KeyError, TypeError, OverflowError, subprocess.SubprocessError) as error:
        print('estimation failed: '+str(error), file=sys.stderr);return 2


if __name__ == '__main__':raise SystemExit(main())
