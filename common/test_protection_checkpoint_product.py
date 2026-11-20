"""Actual ECU persistent protection identity checks; existing virtual CAN only.

Uses a public dummy key in a temporary private directory. No services, real
hardware, attack worker, key persistence or real battery are involved.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def state(path):
    header, digest, body = path.read_bytes().split(b'\n', 2)
    assert header == b'CAPSTONE-CHECKPOINT-V1'
    assert hashlib.sha256(body).hexdigest().encode() == digest
    rows = body.decode().splitlines()
    result = {'version': int(rows[0]), 'elapsed': float(rows[5]),
              'risk': int(rows[3].split()[1]), 'reason': int(rows[3].split()[2])}
    if result['version'] == 2:
        assert rows[8] in ('protection 0', 'protection 1')
        if rows[8] == 'protection 1':
            version, lineage, incident, risk, reason, phase, revision = rows[9].split()
            assert int(version) == 1
            result.update(lineage=lineage, incident=incident, phase=int(phase), revision=int(revision))
            assert (int(risk), int(reason)) == (result['risk'], result['reason'])
    return result


def repack(path, change):
    header, _, body = path.read_bytes().split(b'\n', 2)
    rows = body.decode().splitlines()
    change(rows)
    body = ('\n'.join(rows) + '\n').encode()
    path.write_bytes(header + b'\n' + hashlib.sha256(body).hexdigest().encode() + b'\n' + body)


def stop(child):
    if child is not None and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ecu', required=True)
    parser.add_argument('--policy', required=True)
    parser.add_argument('--out-parent', type=Path, required=True)
    args = parser.parse_args()
    interface = os.environ.get('CAPSTONE_SESSION_TEST_INTERFACE', '')
    if not interface:
        return 77
    if not interface.startswith('vcan') or not Path('/sys/devices/virtual/net', interface).is_dir():
        raise ValueError('existing virtual CAN only')
    args.out_parent.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='protection-checkpoint-', dir=args.out_parent))
    report = {'status': 'RUNNING', 'cases': [], 'output': str(output),
              'scope': 'Actual ECU checkpoint/fresh/resume only; not authenticated kind8 publishing or IVI history stitching.'}
    (output/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='protection-checkpoint-private-') as directory:
        private = Path(directory)
        private.chmod(0o700)
        key = private/'public-dummy.key'
        key.write_bytes(bytes(range(32)))
        key.chmod(0o600)
        profile = private/'profile.csv'
        profile.write_text('voltage,current,temperature\n' + '42,-2,56\n'*60)
        checkpoint = private/'state'
        base = [args.ecu, '--interface', interface, '--key', str(key), '--session-policy', args.policy,
                '--sensor-mode', 'profile_csv', '--profile', str(profile),
                '--checkpoint', str(checkpoint), '--checkpoint-period-ms', '100',
                '--checkpoint-flush-ms', '2000', '--checkpoint-max-age-ms', '60000',
                '--restart-wait-ms', '200', '--restart-retry-ms', '50', '--restart-notice-attempts', '3']
        child = None

        def wait(predicate):
            deadline = time.monotonic()+6
            while time.monotonic() < deadline:
                assert child.poll() is None, 'ECU stopped unexpectedly'
                if checkpoint.exists():
                    current = state(checkpoint)
                    if predicate(current):
                        return current
                time.sleep(.02)
            raise AssertionError('checkpoint predicate did not complete')

        def run(name, intent, predicate, kill=False):
            nonlocal child
            with (output/(name+'.log')).open('w') as stream:
                child = subprocess.Popen(base+['--start-intent', intent], stdout=stream, stderr=subprocess.STDOUT)
                current = wait(predicate)
                if kill:
                    child.kill()
                    child.wait(timeout=3)
                else:
                    stop(child)
            (output/(name+'.checkpoint')).write_bytes(checkpoint.read_bytes())
            report['cases'].append({'case': name, 'result': 'PASS', 'state': current, 'exit_code': child.returncode})
            return current

        try:
            first = run('fresh-risk', 'fresh', lambda s:s['risk']==1 and s.get('revision')==1, kill=True)
            after = run('resume-risk', 'resume', lambda s:s['elapsed']>=first['elapsed']+.2)
            assert (after['lineage'], after['incident'], after['revision']) == (first['lineage'], first['incident'], first['revision'])
            fresh = run('explicit-fresh', 'fresh', lambda s:s.get('lineage')!=first['lineage'] and s['risk']==1)
            assert fresh['incident'] != first['incident']

            def legacy(rows):
                rows[0] = '1'
                del rows[8:]
            repack(checkpoint, legacy)
            old = state(checkpoint)
            migrated = run('legacy-resume', 'resume', lambda s:s['version']==2 and s['elapsed']>=old['elapsed']+.2)
            assert migrated['lineage'] != fresh['lineage']
            assert 'Protection continuity unknown' in (output/'legacy-resume.log').read_text()

            def mismatch(rows):
                fields = rows[9].split()
                fields[3:5] = ['2', '2']
                rows[9] = ' '.join(fields)
            repack(checkpoint, mismatch)
            invalid = checkpoint.read_bytes()
            result = subprocess.run(base+['--start-intent', 'resume'], capture_output=True, timeout=5)
            (output/'mismatch.log').write_bytes(result.stdout+result.stderr)
            assert result.returncode == 2 and checkpoint.read_bytes() == invalid
            report['cases'].append({'case': 'valid-checksum-state-mismatch', 'result': 'PASS', 'exit_code': result.returncode})
        except BaseException as error:
            report.update(status='FAIL', error=str(error))
            (output/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
            raise
        finally:
            stop(child)
    report.update(status='PASS', dummy_key_retained=False, actors_reaped=True)
    (output/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
