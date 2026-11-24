"""Capture identity/quality validation before the independent C++ estimator."""
import copy
import json
import pytest

from adaptive_ecu.scripts.estimate_physical_capture import normalize_capture


def row(sample=0):
    at = 1000+sample*1000
    return {'schema': 'physical-sensor-v2', 'sample': sample,
            'capture_id': '11111111-1111-4111-8111-111111111111',
            'clock_id': '22222222-2222-4222-8222-222222222222',
            'sample_started_ms': at, 'sample_completed_ms': at+800,
            'clock': 'host-monotonic-ms', 'physical_accuracy_verified': False,
            'calibration_id': 'PUBLIC-DUMMY', 'shunt_ohm': .1, 'requested_current_lsb_a': .0001,
            'calibration_register': 4096, 'effective_current_lsb_a': .0001,
            'battery_current_sign': -1, 'current_zero_a': 0, 'terminal_offset_v': 0,
            'ina219': {'status': 'OK', 'started_ms': at, 'completed_ms': at+2,
                       'measurement': {'terminal_v': 3.737, 'battery_current_a': -.37}},
            'ds18b20': {'status': 'OK', 'started_ms': at+2, 'completed_ms': at+752,
                        'measurement': {'temperature_c': 25}}}


def encode(rows):return ('\n'.join(json.dumps(r) for r in rows)+'\n').encode()


def test_completed_same_capture_uses_electrical_completion_time_and_original_precision():
    records = [row(), row(1)];before = copy.deepcopy(records)
    normalized, metadata = normalize_capture(encode(records))
    assert normalized.splitlines()[1].startswith('1,1002,3.737')
    assert normalized.splitlines()[2].startswith('2,2002,3.737')
    assert metadata['rows'] == 2 and metadata['missing_electrical_rows'] == 0 and records == before


@pytest.mark.parametrize('mutation', ['capture', 'clock', 'calibration', 'direction', 'sequence',
    'time', 'ina-time', 'temperature-time', 'nan', 'wrong-status', 'error-value',
    'temperature-value', 'fake-accuracy', 'calibration-register'])
def test_mixed_or_invalid_evidence_is_not_an_estimation_input(mutation):
    first, second = row(), row(1)
    if mutation == 'capture':second['capture_id'] = '33333333-3333-4333-8333-333333333333'
    elif mutation == 'clock':second['clock_id'] = '33333333-3333-4333-8333-333333333333'
    elif mutation == 'calibration':second['calibration_id'] = 'OTHER'
    elif mutation == 'direction':second['battery_current_sign'] = 1
    elif mutation == 'sequence':second['sample'] = 0
    elif mutation == 'time':second['sample_started_ms'] = 999
    elif mutation == 'ina-time':second['ina219']['completed_ms'] = 999999
    elif mutation == 'temperature-time':second['ds18b20']['completed_ms'] = 999999
    elif mutation == 'nan':second['ina219']['measurement']['battery_current_a'] = float('nan')
    elif mutation == 'wrong-status':second['ina219']['status'] = 'UNSUPPORTED'
    elif mutation == 'error-value':second['ina219']['status'] = 'IO_ERROR'
    elif mutation == 'temperature-value':second['ds18b20']['measurement']['temperature_c'] = 200
    elif mutation == 'fake-accuracy':second['physical_accuracy_verified'] = True
    elif mutation == 'calibration-register':second['calibration_register'] = 0
    with pytest.raises(ValueError):normalize_capture(encode([first, second]))


def test_missing_electrical_sample_remains_error_but_missing_temperature_is_separate():
    first, second, third = row(), row(1), row(2)
    second['ina219'] = {'status': 'IO_ERROR', 'measurement': None}
    third['ds18b20'] = {'status': 'CRC_ERROR', 'measurement': None}
    normalized, metadata = normalize_capture(encode([first, second, third]))
    assert normalized.splitlines()[2] == '2,2800,,,ERROR'
    assert metadata['missing_electrical_rows'] == 1
    assert metadata['temperature_status_counts'] == {'OK': 2, 'CRC_ERROR': 1}


def test_capture_gaps_are_explicit_and_missing_prefix_or_incomplete_json_is_rejected():
    normalized, metadata = normalize_capture(encode([row(), row(2)]))
    assert metadata['missing_sequence_rows'] == 1 and normalized.splitlines()[-1].startswith('3,3002,')
    for data in (b'', encode([row()])[:-1], encode([row(1)]), b'{}\n', b'{"a":1,"a":2}\n'):
        with pytest.raises(ValueError):normalize_capture(data)


def test_underflowed_calibration_is_a_clear_input_error():
    record = row();record['shunt_ohm'] = record['requested_current_lsb_a'] = 1e-300
    with pytest.raises(ValueError, match='underflow'):normalize_capture(encode([record]))
