"""Opt-in long vcan check: real ECU/Qt/IDS captures, held-out IF, live inference.

No physical interface, installed service, persistent keys or attack-rate claims.
Run manually; three captures each need enough windows for held-out calibration.
"""
import argparse
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

from test_session_ids_products import records, stop, wait_file

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from security.experiments.evaluate_session_if import evaluate


@contextmanager
def preserve_outcome(output):
    """Run outside process cleanup so hashes describe the closed evidence files."""
    try:
        yield
    except BaseException as error:
        summary = {'status': 'INTERRUPTED' if isinstance(error, KeyboardInterrupt) else 'INVALID',
                   'error_type': type(error).__name__, 'error': str(error),
                   'environment': 'vcan', 'protocol': 'session-v2',
                   'physical_accuracy_measured': False, 'attack_contribution_measured': False}
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        raise
    finally:
        hashes = {}
        for path in sorted(output.rglob('*')):
            if path.is_file() and path.name != 'artifact-hashes.json':
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
                hashes[str(path.relative_to(output))] = digest.hexdigest()
        (output / 'artifact-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')


def wait(children, predicate, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        if any(child.poll() is not None for child in children):
            raise RuntimeError('product exited before required evidence')
        time.sleep(.1)
    raise RuntimeError('product evidence timeout')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ecu', 'ivi', 'policy', 'supervisor'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--out-parent', type=Path, required=True)
    parser.add_argument('--capture-seconds', type=int, default=105)
    args = parser.parse_args()
    interface = os.environ.get('CAPSTONE_SESSION_TEST_INTERFACE', '')
    if not interface or os.environ.get('CAPSTONE_IF_LONG_TEST') != '1':
        return 77
    if not interface.startswith('vcan') or not Path('/sys/devices/virtual/net', interface).is_dir():
        raise ValueError('existing virtual CAN required')
    if not 104 <= args.capture_seconds <= 300:
        raise ValueError('capture duration must be 104..300 seconds')
    # Do not silently mix another running test or disturb its processes.
    with socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW) as probe:
        probe.bind((interface,)); probe.settimeout(.5)
        try:
            probe.recv(16)
        except socket.timeout:
            pass
        else:
            raise RuntimeError('vcan already carries traffic; choose an idle test bus')
    args.out_parent.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='session-if-', dir=args.out_parent))
    print(json.dumps({'result': 'START', 'output': str(output)}), flush=True)
    with preserve_outcome(output), tempfile.TemporaryDirectory(prefix='session-if-private-') as private, ExitStack() as cleanup:
        private = Path(private)
        key = private / 'dummy.key'; key.write_bytes(bytes(range(32))); key.chmod(0o600)
        runtime = private / 'runtime'; runtime.mkdir(mode=0o700)
        ready = private / 'ivi-ready.json'; observations = output / 'ivi.jsonl'
        stream = cleanup.enter_context((output / 'ivi.log').open('w'))
        ivi = subprocess.Popen([args.ivi, '--interface', interface, '--secoc-key', str(key),
            '--protocol', 'session-v2', '--session-policy', args.policy, '--ready-file', str(ready),
            '--observation-jsonl', str(observations), '--windowed'], stdout=stream, stderr=subprocess.STDOUT,
            env=dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', XDG_RUNTIME_DIR=str(runtime)))
        cleanup.callback(stop, ivi); wait_file(ready, [ivi])

        def manager(mode, splits=()):
            logs = output / mode; logs.mkdir(mode=0o700)
            settings = {'python': sys.executable, 'repository': str(ROOT), 'log_directory': str(logs),
                        'mode': mode, 'frame_budget': 2, 'expiry_ms': 1000}
            if splits:
                settings.update(train_normal=str(splits[0][0]), normal_manifest=str(splits[0][1]),
                                calibrate_normal=str(splits[1][0]), calibration_manifest=str(splits[1][1]))
            path = private / (mode + '.json'); path.write_text(json.dumps(settings))
            console = cleanup.enter_context((output / (mode + '.log')).open('w'))
            child = subprocess.Popen([sys.executable, args.supervisor, '--ecu', args.ecu,
                '--ids-settings', str(path), '--checkpoint', str(private / (mode + '.state')),
                '--initial-intent', 'fresh', '--stop-timeout', '1', '--startup-timeout', '10',
                '--heartbeat-timeout', '3', '--max-crash-restarts', '0', '--', '--interface', interface,
                '--key', str(key), '--session-policy', args.policy, '--checkpoint-period-ms', '1000',
                '--checkpoint-flush-ms', '1000', '--checkpoint-max-age-ms', '60000',
                '--restart-wait-ms', '200', '--restart-retry-ms', '50', '--restart-notice-attempts', '2'],
                stdout=console, stderr=subprocess.STDOUT)
            cleanup.callback(stop, child)
            return child, logs

        normal, _ = manager('rules-only')
        wait([normal, ivi], lambda: any(row.get('observation_ready') for row in records(observations)), 12)
        splits = []
        for name in ('fit', 'calibration', 'evaluation'):
            frames, manifest = output / (name + '.jsonl'), output / (name + '.manifest.json')
            console = cleanup.enter_context((output / (name + '.log')).open('w'))
            print(json.dumps({'result': 'CAPTURE_START', 'phase': name, 'seconds': args.capture_seconds}), flush=True)
            capture = subprocess.Popen([sys.executable, '-m', 'security.capture_normal', '--interface', interface,
                '--protocol', 'session-v2', '--duration', str(args.capture_seconds), '--output', str(frames),
                '--manifest', str(manifest), '--run-id', output.name + '-' + name], cwd=ROOT,
                stdout=console, stderr=subprocess.STDOUT)
            cleanup.callback(stop, capture)
            wait([normal, ivi], lambda: capture.poll() is not None, args.capture_seconds + 10)
            if capture.returncode:
                raise RuntimeError('normal capture invalid: ' + name)
            splits.append((frames, manifest))
            print(json.dumps({'result': 'CAPTURE_COMPLETE', 'phase': name}), flush=True)
        report = evaluate(*(item for pair in splits for item in pair))
        (output / 'if-normal-report.json').write_text(json.dumps(report, indent=2) + '\n')
        if report['status'] != 'COMPLETE':
            raise RuntimeError('insufficient held-out evaluation windows')
        stop(normal)
        first = len(records(observations))
        live, logs = manager('rules+if', splits)
        wait([live, ivi], lambda: any(row.get('observation_ready') for row in records(observations)[first:]), 15)

        def inferences():
            return [row for path in logs.glob('*.jsonl') for row in records(path)
                    if row.get('result') == 'MODEL_EVALUATION']
        inferred = wait([live, ivi], lambda: (rows if len(rows := inferences()) >= 10 else None), 20)
        stop(live); stop(ivi)
        summary = {'status': 'PASS', 'environment': 'vcan', 'protocol': 'session-v2',
                   'scope': 'real ECU/Qt/IDS capture, independent normal IF evaluation and live inference',
                   'if_only_normal_fpr': report['if_only_fpr'],
                   'heldout_normal_windows': report['evaluated_windows'],
                   'live_inferences_observed': len(inferred),
                   'physical_accuracy_measured': False, 'attack_contribution_measured': False,
                   'key_retained': False, 'output': str(output)}
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps(summary), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
