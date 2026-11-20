"""Exercise deployment health against actual ECU/ordinary Qt IVI on explicit vcan.

Creates/removes a public dummy key in a private temporary directory. Never uses
physical CAN or changes system services. Explicit budgets are test inputs.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.deployment.health import check
from tools.deployment.ecu_identity import check as ecu_check, bind


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:process.wait(timeout=3)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)


def run(ecu, ivi, policy, interface, output, max_age_ms, startup_timeout_s):
    if not re.fullmatch('vcan[0-9]+', interface) or not Path('/sys/devices/virtual/net', interface).is_dir():
        raise ValueError('explicit existing virtual CAN required')
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    run_id = 'PUBLIC-DEPLOYMENT-HEALTH'
    ready, observations = output/'ready.json', output/'receiver.jsonl'
    expected = hashlib.sha256(ivi.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='health-private-') as temporary, ExitStack() as cleanup:
        private = Path(temporary);key = private/'dummy.key';key.write_bytes(bytes(range(32)));key.chmod(0o600)
        runtime = private/'runtime';runtime.mkdir(mode=0o700)
        log = cleanup.enter_context((output/'ivi.log').open('w'))
        receiver = subprocess.Popen([str(ivi), '--interface', interface, '--protocol', 'session-v2',
            '--secoc-key', str(key), '--session-policy', str(policy), '--run-id', run_id,
            '--ready-file', str(ready), '--observation-jsonl', str(observations), '--windowed'],
            env=dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                     XDG_RUNTIME_DIR=str(runtime)), stdout=log, stderr=subprocess.STDOUT, umask=0o077)
        cleanup.callback(stop, receiver)
        log = cleanup.enter_context((output/'ecu.log').open('w'))
        (output/'ecu.log').chmod(0o600)
        sender = subprocess.Popen([str(ecu), '--interface', interface, '--sensor-mode', 'constant',
            '--protocol', 'session-v2', '--secoc', 'on', '--key', str(key), '--session-policy', str(policy)],
            stdout=log, stderr=subprocess.STDOUT)
        cleanup.callback(stop, sender)
        deadline = time.monotonic()+startup_timeout_s;last_error = None
        while time.monotonic() < deadline:
            if receiver.poll() is not None or sender.poll() is not None:raise RuntimeError('real product exited during startup')
            try:
                healthy = check(receiver.pid, expected, ready, observations, run_id, max_age_ms, 4*1024*1024)
                break
            except (OSError, ValueError) as error:last_error = str(error);time.sleep(.05)
        else:raise RuntimeError('health never became ready: '+str(last_error))
        expected_ecu = hashlib.sha256(ecu.read_bytes()).hexdigest()
        identity = ecu_check(sender.pid, expected_ecu, output/'ecu.log', 65536)
        paired = bind(healthy, identity)
        negatives = {}
        try:ecu_check(sender.pid, '0'*64, output/'ecu.log', 65536)
        except (OSError, ValueError) as error:negatives['ecu-artifact'] = str(error)
        else:raise AssertionError('wrong ECU artifact passed')
        for name, wrong_hash, wrong_run, wrong_ready, wrong_observation in (
            ('artifact', '0'*64, run_id, ready, observations),
            ('run', expected, 'OTHER', ready, observations),
            ('ready-binding', expected, run_id, output/'other-ready', observations),
            ('observation-binding', expected, run_id, ready, output/'other-log')):
            try:check(receiver.pid, wrong_hash, wrong_ready, wrong_observation, wrong_run, max_age_ms, 4*1024*1024)
            except (OSError, ValueError) as error:negatives[name] = str(error)
            else:raise AssertionError('invalid process binding passed: '+name)
        stop(sender)
        try:ecu_check(sender.pid, expected_ecu, output/'ecu.log', 65536)
        except (OSError, ValueError) as error:negatives['ecu-stopped'] = str(error)
        else:raise AssertionError('stopped ECU process passed identity check')
        time.sleep(max_age_ms/1000+.2)
        assert receiver.poll() is None, 'receiver must stay live for stale-data negative test'
        try:check(receiver.pid, expected, ready, observations, run_id, max_age_ms, 4*1024*1024)
        except (OSError, ValueError) as error:negatives['live-but-stale'] = str(error)
        else:raise AssertionError('live process without fresh sender incorrectly passed')
    result = {'status': 'PASS', 'scope': 'Actual ordinary Qt IVI and ECU over same-host vcan; no service/Pi acceptance',
              'healthy': healthy, 'ecu_identity': identity, 'paired': paired,
              'negatives': negatives, 'dummy_key_retained': False,
              'explicit_max_age_ms': max_age_ms, 'startup_timeout_s': startup_timeout_s,
              'binary_sha256': {'ecu': hashlib.sha256(ecu.read_bytes()).hexdigest(), 'ivi': expected}}
    (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ecu', 'ivi', 'policy', 'out'):parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--interface', required=True)
    parser.add_argument('--max-age-ms', type=int, required=True)
    parser.add_argument('--startup-timeout-s', type=int, required=True)
    args = parser.parse_args()
    if not 1 <= args.startup_timeout_s <= 120 or not 1 <= args.max_age_ms <= 60000:
        parser.error('explicit bounded test time inputs required')
    result = run(args.ecu.resolve(), args.ivi.resolve(), args.policy.resolve(), args.interface,
                 args.out.absolute(), args.max_age_ms, args.startup_timeout_s)
    print(json.dumps(result));return 0


if __name__ == '__main__':raise SystemExit(main())
