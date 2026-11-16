"""Thermal SHUTDOWN keeps real ECU alive; existing Linux virtual CAN only."""
from contextlib import ExitStack
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def stop_child(child):
    if child.poll() is None:
        child.terminate()
        try:child.wait(timeout=3)
        except subprocess.TimeoutExpired:child.kill();child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ecu', required=True)
    parser.add_argument('--policy', required=True)
    parser.add_argument('--ivi')
    parser.add_argument('--cooling',action='store_true')
    parser.add_argument('--supervisor', required=True)
    parser.add_argument('--out-parent', type=Path, required=True)
    args = parser.parse_args()
    interface = os.environ.get('CAPSTONE_SESSION_TEST_INTERFACE', '')
    if not interface:
        return 77
    if not interface.startswith('vcan') or not Path('/sys/devices/virtual/net', interface).is_dir():
        raise ValueError('existing virtual CAN only')
    args.out_parent.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='restart-', dir=args.out_parent))
    with tempfile.TemporaryDirectory(prefix='ecu-restart-private-') as folder, ExitStack() as cleanup:
        private = Path(folder)
        key = private / 'dummy.key'
        key.write_bytes(bytes(range(32)))
        key.chmod(0o600)
        profile = private / 'hot.csv'
        profile.write_text('voltage,current,temperature\n' + '42,-2,25\n'*5 + '42,-2,65\n'*10 + ('42,-2,55\n'*70 if args.cooling else ''))
        checkpoint = private / 'state'
        log = output / 'ecu.log'
        command = [sys.executable, args.supervisor, '--ecu', args.ecu,
                   '--checkpoint', str(checkpoint), '--initial-intent', 'fresh', '--stop-timeout', '3',
                   '--startup-timeout', '3', '--heartbeat-timeout', '1', '--max-crash-restarts', '3', '--',
                   '--interface', interface, '--sensor-mode', 'profile_csv', '--profile', str(profile),
                   '--key', str(key), '--session-policy', args.policy,
                   '--checkpoint-period-ms', '100', '--checkpoint-flush-ms', '2000',
                   '--checkpoint-max-age-ms', '60000', '--restart-wait-ms', '1000' if args.ivi else '200',
                   '--restart-retry-ms', '50', '--restart-notice-attempts', '3']
        ivi = None
        if args.ivi:
            runtime=private/'runtime';runtime.mkdir(mode=0o700)
            ready=private/'ready.json'
            observations=output/'observations.jsonl'
            ivi_log=cleanup.enter_context((output/'ivi.log').open('w'))
            ivi=subprocess.Popen([args.ivi,'--interface',interface,'--secoc-key',str(key),
                '--protocol','session-v2','--session-policy',args.policy,'--ready-file',str(ready),
                '--observation-jsonl',str(observations),'--windowed','--demo-exit-ms','12000'],
                env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=str(runtime)),
                stdout=ivi_log,stderr=subprocess.STDOUT)
            cleanup.callback(stop_child,ivi)
            deadline=time.monotonic()+5
            while not ready.exists():
                if ivi.poll() is not None or time.monotonic()>deadline:raise RuntimeError('IVI not READY')
                time.sleep(.02)
        with log.open('w') as stream:
            child = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 6
                while not checkpoint.exists():
                    if child.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError('running ECU never stored checkpoint')
                    time.sleep(.02)
                time.sleep(8 if args.cooling else 2)
                if child.poll() is not None:
                    raise RuntimeError('thermal protection stopped ECU unexpectedly')
            finally:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
        if ivi is not None:
            ivi.terminate()
            try:ivi.wait(timeout=3)
            except subprocess.TimeoutExpired:ivi.kill();ivi.wait()
            ivi_log.close()
            rows=[json.loads(line) for line in observations.read_text().splitlines() if line.strip()]
            diagnostics=[row for row in rows if row.get('result')=='AUTHENTICATED_DIAGNOSTIC']
            assert not any(row['kind']==2 for row in diagnostics), 'thermal state incorrectly announced a restart'
            statuses=[bytes.fromhex(row['body_hex']) for row in diagnostics if row['kind']==1]
            assert any(body[33]==1 and body[35]==3 and body[53]==1 for body in statuses), 'no live thermal protection status'
            models=[row for row in rows if row.get('result')=='VIEW_MODEL_PUBLICATION']
            assert models, 'actual Qt publication missing'
            assert not any(row['connection']=='ECU 프로그램 복구 완료' for row in models), 'thermal condition mislabeled as process recovery'
        text = log.read_text()
        assert child.returncode == 0, text
        assert 'RESTART_READY' not in text, text
        assert 'Recovery: calculation and protection restored' not in text, text
        assert 'ECU_SUPERVISOR: planned restart' not in text, text
        assert checkpoint.read_text().splitlines()[5] == ('2 0 5 0' if args.cooling else '2 3 4 0'), 'thermal state did not match expected recovery'
        if args.cooling:
            assert '3 -> 0 reason=0x5' in text, 'actual ECU cooling transition missing'
            if args.ivi:
                assert statuses[-1][35]==0, 'final recovered NodeStatus missing'
        # A changed source must never silently restore or fresh-start.
        profile.write_text('voltage,current,temperature\n42,-2,25\n')
        rejected = subprocess.run([args.ecu] + command[command.index('--interface'):] +
                                  ['--checkpoint', str(checkpoint), '--start-intent', 'resume'],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=5)
        assert rejected.returncode == 2 and 'checkpoint restore rejected' in rejected.stdout, rejected.stdout
        (output / 'changed-input.log').write_text(rejected.stdout)
    result = {'status': 'PASS', 'scope': 'real ECU and supervisor over vcan', 'ivi_live_protection_ui': bool(args.ivi),
              'restart_decision': 'none-thermal-protection', 'automatic_resume': 0, 'shutdown_preserved': not args.cooling, 'thermal_recovered':args.cooling,
              'changed_input_rejected': True, 'secrets_retained': False}
    (output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(result, output=str(output))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
