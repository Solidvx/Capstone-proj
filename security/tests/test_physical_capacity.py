"""Synthetic public meter logs; no discharge, sensor, network or private key."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from adaptive_ecu.scripts.measure_physical_capacity import evaluate, stable_read


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'adaptive_ecu/scripts/measure_physical_capacity.py'
CONFIG = (ROOT / 'adaptive_ecu/data/physical-battery.conf.example').read_bytes()


def rows():
    return [{'result': 'PHYSICAL_SAMPLE', 'sequence': n, 'sample_monotonic_ms': n * 1000,
             'process_instance_id': 'a' * 32, 'clock_id': '00000000-0000-4000-8000-000000000001',
             'model_config_sha256': hashlib.sha256(CONFIG).hexdigest(),
             'voltage_v': 4.1 - n * .1, 'current_a': -.37, 'temperature_c': 20,
             'ina_quality': 2, 'temperature_quality': 2,
             'charged_ah': 0, 'discharged_ah': (n - 1) * .37 / 3600,
             'observation_gap': False, 'physical_accuracy_verified': False} for n in range(1, 9)]


def encode(items):
    return (''.join(json.dumps(row) + '\n' for row in items)).encode()


def options():
    return dict(cell_id='PUBLIC-CELL', test_id='PUBLIC-TEST', endpoint_reference='PUBLIC-SYNTHETIC-ENDPOINTS',
                end_voltage_v=3.3, endpoint_tolerance_v=.01, charge_noise_tolerance_ah=0,
                max_charge_current_a=.001, full_discharge_confirmed=True)


def test_measured_charge_is_independent_of_soc_and_config_is_prepared_without_overwrite():
    samples = rows()
    for row in samples:
        row['soc_estimate_percent'] = 100  # Must never supply the capacity basis.
    report, config = evaluate(encode(samples), CONFIG, 1, 8, **options())
    capacity = .37 * 7 / 3600
    assert report['measured_capacity_ah'] == pytest.approx(capacity)
    assert report['soh_estimate_percent'] == pytest.approx(capacity / 2.55 * 100)
    assert report['physical_accuracy_verified'] is False
    assert report['samples'] == 8 and report['duration_s'] == 7
    assert report['endpoint_verification'] == 'operator-attested'
    assert 'capacity_test_id=PUBLIC-TEST\n' in config
    assert f'measured_capacity_ah={capacity:.17g}\n' in config
    assert 'initial_soc_percent=auto-ekf-adi-liion-v1' in config
    assert report['output_configuration_sha256'] == hashlib.sha256(config.encode()).hexdigest()
    assert CONFIG.endswith(b'capacity_test_id=unknown\n')


@pytest.mark.parametrize('problem', ['gap', 'sensor', 'temperature', 'missing', 'duplicate', 'clock', 'instance',
    'config', 'time', 'rollback', 'charging', 'accumulated-charge', 'old-log', 'nan', 'negative-time', 'accuracy'])
def test_incomplete_or_mixed_evidence_cannot_produce_soh(problem):
    samples = rows()
    row = samples[3]
    if problem == 'gap': row['observation_gap'] = True
    elif problem == 'sensor': row['ina_quality'] = 3
    elif problem == 'temperature': row['temperature_c'] = None
    elif problem == 'missing': del samples[3]
    elif problem == 'duplicate': row['sequence'] -= 1
    elif problem == 'clock': row['clock_id'] = '00000000-0000-4000-8000-000000000002'
    elif problem == 'instance': row['process_instance_id'] = 'b' * 32
    elif problem == 'config': row['model_config_sha256'] = 'b' * 64
    elif problem == 'time': row['sample_monotonic_ms'] += 10000
    elif problem == 'negative-time': row['sample_monotonic_ms'] = -1
    elif problem == 'rollback': row['discharged_ah'] = 0
    elif problem == 'charging': row['current_a'] = .2
    elif problem == 'accumulated-charge':
        for row in samples[3:]: row['charged_ah'] = .0001
    elif problem == 'old-log': del row['sample_monotonic_ms']
    elif problem == 'nan': row['current_a'] = float('nan')
    elif problem == 'accuracy': row['physical_accuracy_verified'] = True
    with pytest.raises((ValueError, KeyError, TypeError)):
        evaluate(encode(samples), CONFIG, 1, 8, **options())


@pytest.mark.parametrize('problem', ['confirmation', 'reference', 'endpoint', 'window', 'config', 'tail', 'label', 'noise'])
def test_explicit_full_cycle_and_endpoint_inputs_are_required(problem):
    opt = options();config = CONFIG;start, end = 1, 8;data = encode(rows())
    if problem == 'confirmation': opt['full_discharge_confirmed'] = False
    elif problem == 'reference': opt['endpoint_reference'] = ''
    elif problem == 'endpoint': opt['end_voltage_v'] = 3.0
    elif problem == 'window': end = 9
    elif problem == 'config': config = CONFIG.replace(b'current_zero_a=0', b'current_zero_a=0.1')
    elif problem == 'tail': data = data.rstrip()
    elif problem == 'label': opt['test_id'] = '../unsafe'
    elif problem == 'noise': opt['charge_noise_tolerance_ah'] = 1.
    with pytest.raises(ValueError):
        evaluate(data, config, start, end, **opt)


def test_restart_and_duplicate_json_are_rejected():
    samples = rows()
    samples.insert(3, {'result': 'ECU_PHYSICAL_LINEAGE'})
    with pytest.raises(ValueError, match='multiple ECU'):
        evaluate(encode(samples), CONFIG, 1, 8, **options())
    data = encode(rows()).replace(b'"sequence": 4', b'"sequence": 4, "sequence": 4')
    with pytest.raises(ValueError, match='duplicate JSON'):
        evaluate(data, CONFIG, 1, 8, **options())


def test_tiny_charge_noise_is_subtracted_not_added_to_capacity():
    samples = rows()
    for row in samples[3:]: row['charged_ah'] = .0000001
    opt = options();opt['charge_noise_tolerance_ah'] = .000001
    report, _ = evaluate(encode(samples), CONFIG, 1, 8, **opt)
    assert report['measured_capacity_ah'] == pytest.approx(.37 * 7 / 3600 - .0000001)


def test_cli_emits_report_and_private_new_config_then_refuses_replacement(tmp_path):
    log = tmp_path / 'ecu.log';log.write_bytes(encode(rows()))
    config = tmp_path / 'physical.conf';config.write_bytes(CONFIG)
    out = tmp_path / 'capacity'
    command = [sys.executable, str(SCRIPT), '--log', str(log), '--config', str(config), '--out', str(out),
               '--start-sequence', '1', '--end-sequence', '8', '--cell-id', 'PUBLIC-CELL', '--test-id', 'PUBLIC-TEST',
               '--endpoint-reference', 'PUBLIC-SYNTHETIC-ENDPOINTS', '--end-voltage-v', '3.3',
               '--endpoint-tolerance-v', '.01', '--charge-noise-tolerance-ah', '0', '--max-charge-current-a', '.001',
               '--full-discharge-confirmed']
    result = subprocess.run(command, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['status'] == 'MEASURED_WITH_ATTESTED_ENDPOINTS'
    generated = out / 'physical-battery.with-soh.conf'
    assert generated.stat().st_mode & 0o777 == 0o600
    assert config.read_bytes() == CONFIG
    assert json.loads((out / 'report.json').read_text())['physical_accuracy_verified'] is False
    assert subprocess.run(command, capture_output=True, timeout=5).returncode == 2
    link = tmp_path / 'link';link.symlink_to(log)
    with pytest.raises(OSError): stable_read(link, 65536)
    with pytest.raises(ValueError): stable_read(log, 1)
