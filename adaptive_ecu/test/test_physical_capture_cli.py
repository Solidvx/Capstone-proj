"""Actual standalone binary against explicit file fixtures, never a real sensor."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', required=True)
    parser.add_argument('--fixture', required=True)
    parser.add_argument('--evaluator', required=True)
    args = parser.parse_args()
    capture = str(Path(args.capture).resolve())
    assert subprocess.run([capture, '--help'], capture_output=True).returncode == 0
    assert subprocess.run([capture], capture_output=True).returncode == 2
    with tempfile.TemporaryDirectory(prefix='public-sensor-fixture-') as folder:
        root = Path(folder)
        sensor = root/'28-000000000000';sensor.mkdir()
        path = sensor/'w1_slave'
        base = [capture, '--i2c-device', str(root/'absent-i2c'), '--ina-address', '64',
                '--shunt-ohm', '.1', '--current-lsb-a', '.0001', '--battery-current-sign', '-1',
                '--current-zero-a', '0', '--terminal-offset-v', '0', '--temperature-device', sensor.name,
                '--calibration-id', 'PUBLIC-FILE-FIXTURE', '--w1-root', str(root),
                '--count', '1', '--period-ms', '1', '--read-timeout-ms', '500']
        # Official-style 25C scratchpad with CRC 33, not a live measurement.
        line = '90 01 4b 46 7f ff 0c 10 33'
        path.write_text(line+' : crc=33 YES\n'+line+' t=25000\n')
        result = subprocess.run(base, text=True, capture_output=True, timeout=5)
        assert result.returncode == 1, result.stderr
        row = json.loads(result.stdout)
        assert row['ina219']['status'] == 'OPEN_ERROR' and row['ina219']['measurement'] is None
        assert row['ds18b20']['measurement'] == {'temperature_c': 25}
        assert row['physical_accuracy_verified'] is False
        assert row['ds18b20']['completed_ms'] >= row['ds18b20']['started_ms']
        # The physical check exposed a variable internal scratchpad byte 6.
        # Exercise the actual CLI/file parser, retaining CRC and t= agreement.
        observed = '3b 01 7f 80 7f ff 05 10 db'
        path.write_text(observed+' : crc=db YES\n'+observed+' t=19687\n')
        varied = subprocess.run(base, text=True, capture_output=True, timeout=5)
        varied_row = json.loads(varied.stdout)
        assert varied.returncode == 1  # INA device is intentionally absent.
        assert varied_row['ds18b20']['status'] == 'OK'
        assert varied_row['ds18b20']['measurement'] == {'temperature_c': 19.687}
        assert varied_row['ds18b20']['scratchpad'] == '3b017f807fff0510db'
        path.write_text(line+' : crc=33 YES\n'+line+' t=25000\n')
        mocked = base.copy();mocked[0] = str(Path(args.fixture).resolve())
        device = root/'public-i2c-file';device.touch()
        mocked[mocked.index('--i2c-device')+1] = str(device)
        result = subprocess.run(mocked, text=True, capture_output=True, timeout=5)
        assert result.returncode == 0, result.stderr
        row = json.loads(result.stdout)
        assert row['ina219']['status'] == row['ds18b20']['status'] == 'OK'
        assert abs(row['ina219']['measurement']['terminal_v']-3.737) < 1e-9
        assert abs(row['ina219']['measurement']['battery_current_a']+.37) < 1e-9
        assert row['ina219']['measurement']['shunt_raw'] == 3700
        assert row['physical_accuracy_verified'] is False
        # Actual capture fixture -> strict Python evidence bridge -> C++ meter.
        capture_log = root/'capture.jsonl';capture_log.write_text(result.stdout)
        script = Path(__file__).resolve().parents[1]/'scripts/estimate_physical_capture.py'
        bridge = [__import__('sys').executable, str(script), '--capture', str(capture_log),
                  '--evaluator', str(Path(args.evaluator).resolve()), '--out', str(root/'estimate'),
                  '--model-id', 'PUBLIC-MODEL', '--capacity-ah', '2.55', '--initial-soc-percent', '80',
                  '--max-interval-ms', '2000', '--max-input-bytes', '65536', '--timeout-s', '5']
        estimate = subprocess.run(bridge, text=True, capture_output=True, timeout=10)
        assert estimate.returncode == 0, estimate.stderr
        report = json.loads((root/'estimate/report.json').read_text())
        assert report['last_estimate']['soc_estimate_percent'] == 80
        assert report['last_estimate']['soh_estimate_percent'] is None
        assert report['source']['capture_id'] == row['capture_id']
        assert row['schema'] == 'physical-sensor-v2'
        # A lost INA sample must not integrate the unobserved interval.
        records = []
        for i in range(4):
            record = json.loads(result.stdout);record['sample'] = i
            for key in ('sample_started_ms', 'sample_completed_ms'):record[key] += i*1000
            for key in ('ina219', 'ds18b20'):
                for field in ('started_ms', 'completed_ms'):record[key][field] += i*1000
            if i == 1:record['ina219'] = {'status': 'IO_ERROR', 'measurement': None}
            records.append(record)
        capture_log.write_text(''.join(json.dumps(r)+'\n' for r in records))
        bridge[bridge.index('--out')+1] = str(root/'gap-estimate')
        estimate = subprocess.run(bridge, text=True, capture_output=True, timeout=10)
        assert estimate.returncode == 1, estimate.stderr
        report = json.loads((root/'gap-estimate/report.json').read_text())
        assert report['last_estimate']['observation_gap'] is True
        assert abs(report['last_estimate']['discharged_ah']-.37/3600) < 1e-10
        assert report['last_estimate']['soc_estimate_percent'] < 80
        bridge[bridge.index('--out')+1] = str(root/'with-capacity')
        estimate = subprocess.run(bridge+['--measured-capacity-ah', '2.295', '--capacity-test-id', 'PUBLIC-CAPACITY',
                                         '--capacity-test-confirmed'], text=True, capture_output=True, timeout=10)
        assert estimate.returncode == 1, estimate.stderr  # Electrical gap remains visible.
        report = json.loads((root/'with-capacity/report.json').read_text())
        assert abs(report['last_estimate']['soh_estimate_percent']-90) < 1e-10
        assert report['capacity_basis_verification'] == 'operator-attested'
        # A single healthy capture can retain unknown initial SOC honestly.
        capture_log.write_text(result.stdout)
        unknown = bridge.copy();at = unknown.index('--initial-soc-percent');del unknown[at:at+2]
        unknown[unknown.index('--out')+1] = str(root/'unknown-soc')
        estimate = subprocess.run(unknown, text=True, capture_output=True, timeout=10)
        assert estimate.returncode == 0, estimate.stderr
        assert json.loads((root/'unknown-soc/report.json').read_text())['last_estimate']['soc_estimate_percent'] is None
        temperature_error = json.loads(result.stdout)
        temperature_error['ds18b20'] = {'status': 'CRC_ERROR', 'measurement': None}
        capture_log.write_text(json.dumps(temperature_error)+'\n')
        bridge[bridge.index('--out')+1] = str(root/'temperature-error')
        estimate = subprocess.run(bridge, text=True, capture_output=True, timeout=10)
        assert estimate.returncode == 1, estimate.stderr
        report = json.loads((root/'temperature-error/report.json').read_text())
        assert report['status'] == 'COMPLETE_WITH_SENSOR_ERRORS'
        assert report['last_estimate']['soc_input_valid'] is True
        capture_log.write_text(result.stdout)
        bridge[bridge.index('--out')+1] = str(root/'invalid-capacity')
        estimate = subprocess.run(bridge+['--measured-capacity-ah', '2.295'], capture_output=True, timeout=10)
        assert estimate.returncode == 2 and not (root/'invalid-capacity').exists()
        estimate = subprocess.run(unknown, capture_output=True, timeout=10)
        assert estimate.returncode == 2, 'existing output must not be overwritten'
        path.write_text(line+' : crc=33 NO\n'+line+' t=25000\n')
        result = subprocess.run(base, text=True, capture_output=True, timeout=5)
        row = json.loads(result.stdout)
        assert result.returncode == 1 and row['ds18b20']['status'] == 'CRC_ERROR'
        assert row['ds18b20']['measurement'] is None
        path.unlink()
        result = subprocess.run(base, text=True, capture_output=True, timeout=5)
        assert result.returncode == 1 and json.loads(result.stdout)['ds18b20']['status'] == 'OPEN_ERROR'
        os.mkfifo(path)
        blocked = base.copy();blocked[blocked.index('--read-timeout-ms')+1] = '30'
        result = subprocess.run(blocked, text=True, capture_output=True, timeout=5)
        assert result.returncode == 1 and json.loads(result.stdout)['ds18b20']['status'] == 'TIMEOUT'
        process = subprocess.Popen(base, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            # Wait for the bounded reader to exist before stopping its owner.
            children = Path('/proc')/str(process.pid)/'task'/str(process.pid)/'children'
            deadline = time.monotonic()+2
            observed = []
            while time.monotonic() < deadline:
                observed = children.read_text().split() if children.exists() else []
                if observed:break
                time.sleep(.005)
            assert observed, 'no bounded reader started'
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=3)
            assert process.returncode == 130
            assert all(not Path('/proc', pid).exists() for pid in observed), 'reader not reaped'
        finally:
            if process.poll() is None:process.kill();process.communicate()
        for flag, value in [('--shunt-ohm', 'nan'), ('--ina-address', '72'),
                            ('--temperature-device', '../other'), ('--current-lsb-a', '0')]:
            command = base.copy();command[command.index(flag)+1] = value
            result = subprocess.run(command, capture_output=True, timeout=5)
            # 72 is an allowed INA219 jumper address, so device absence is 1.
            assert result.returncode == (1 if flag == '--ina-address' else 2)
    print(json.dumps({'status': 'PASS', 'scope': 'public file/absent-device/FIFO fixtures only',
                      'physical_accuracy_verified': False, 'can_used': False}))


if __name__ == '__main__':
    main()
