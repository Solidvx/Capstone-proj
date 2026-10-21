"""Evidence and bounded recovery helpers for the continuous-trial test campaign."""
import json
import subprocess
import time
from pathlib import Path

from security.experiments.run_ablation import render_command
from security.experiments.validate_m5_settings import ssh_target


def recoverable(error):
    # Configuration, storage, clock and unknown failures require operator action.
    return isinstance(error, (RuntimeError, TimeoutError)) and any(
        text in str(error) for text in ('CAN error frame', 'baseline ECU/reference not ready',
                                      'remote actor exited', 'observer phase timeout'))


def phase_barrier(observers, phase, actors):
    offsets = [len(child.snapshot()) for child in observers]
    for child in observers:
        child.process.stdin.write(json.dumps({'phase': phase}) + '\n')
        child.process.stdin.flush()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        actors.check()
        if all(any(r.get('result') == 'PHASE' and r.get('phase') == phase
                   for r in child.snapshot()[offset:]) for child, offset in zip(observers, offsets)):
            return
        time.sleep(.01)
    raise TimeoutError('observer phase timeout')


def classification(codes, expected):
    codes = set(codes)
    if not codes:return 'MISSED'
    if expected not in codes:return 'MISMATCH'
    return 'MATCH' if codes == {expected} else 'COMPOUND'


def add_evidence(row, injection, observers, offsets=None):
    signatures = {(r.can_id, r.data.hex()) for r in injection if r.own}
    arrivals = {}
    for name, child, offset in zip(('ecu', 'ivi'), observers, offsets or [0, 0]):
        records = child.snapshot()[offset:]
        baseline_drop = next((r.get('rx_dropped', 0) for r in records if r.get('result') == 'PHASE' and r.get('phase') == 'baseline'), 0)
        baseline = {(r.get('can_id'), r.get('data')) for r in records
                    if r.get('result') == 'OBS_FRAME' and r.get('phase') == 'baseline'}
        candidates = [r for r in records if r.get('result') == 'OBS_FRAME'
                      and r.get('phase') in ('attack', 'post')
                      and (r.get('can_id'), r.get('data')) in signatures]
        arrivals[name] = {
            'matching_frames': len(candidates),
            'distinct_from_baseline_frames': sum((r['can_id'], r['data']) not in baseline for r in candidates),
            'rx_dropped': max((r.get('rx_dropped', 0) for r in records), default=baseline_drop) - baseline_drop,
            'error_frames': sum(bool(r.get('error')) for r in records),
        }
    row['remote_arrival'] = arrivals
    row['arrival_note'] = ('Payload matches in remote attack/post windows, not authenticated sender identity. '
                           'Repeated baseline/replay payloads are ambiguous; no cross-host time subtraction.')
    if any(not r['matching_frames'] or r['rx_dropped'] or r['error_frames'] for r in arrivals.values()):
        row['status'] = 'INVALID'
        row['invalid_reason'] = ','.join(filter(None, [row.get('invalid_reason'), 'REMOTE_ARRIVAL_UNVERIFIED']))
    expected = row['expected_attack_code']
    row['bus_type_result'] = classification(row['observed_attack_codes'], expected) if row['config'] == 3 else 'NOT_EVALUATED'
    row['ivi_type_result'] = classification(row['ivi_published_attack_codes'], expected) if row['config'] == 3 else 'NOT_EVALUATED'
    if row['status'] != 'VALID':
        row['bus_type_result'] = row['ivi_type_result'] = 'INVALID'


def validate_extra(settings, targets):
    values = {'run_id': 'check', 'lifetime_s': '60'}
    for suffix, target in (('a', targets['ecu']), ('b', targets['receiver_on'])):
        role = 'observer_' + suffix
        command = settings[role]
        render_command(command, values)
        text = ' '.join(command)
        if (Path(command[0]).name != 'ssh' or any(v in command for v in ('-n', '-t', '-tt'))
                or ssh_target(command) != target or 'REPLACE_' in text
                or 'security.experiments.trial_observer' not in text
                or 'security.experiments.remote_process' in text or '{run_id}' not in text):
            raise ValueError(f'{role}: direct non-PTY observer SSH on the corresponding node required')
    for role in ('ecu', 'ids', 'receiver_on', 'receiver_off'):
        supervisor = ' '.join(settings[role]).split(' -- ', 1)[0]
        if '--run-id {run_id}' not in supervisor:
            raise ValueError(f'{role}: remote_process needs --run-id {{run_id}} for cleanup acknowledgement')
    for role in ('health_a', 'health_b', 'health_c'):
        command = settings[role]
        if not isinstance(command, list) or not command or not all(isinstance(v, str) for v in command):
            raise ValueError(f'{role}: argv array required')
        if 'REPLACE_' in ' '.join(command) or 'security.experiments.can_health' not in ' '.join(command):
            raise ValueError(f'{role}: resolve CAN health command')
        if role != 'health_c' and (Path(command[0]).name != 'ssh' or ssh_target(command) != targets['ecu' if role == 'health_a' else 'receiver_on']):
            raise ValueError(f'{role}: incorrect node')
        if '--recover' in command or '--recover' in ' '.join(command):
            raise ValueError('health commands must omit --recover; runner adds it only after cleanup')


def check_health(settings, directory, recover=False):
    results = {}
    for role in ('health_c', 'health_a', 'health_b'):
        command = list(settings[role])
        if recover:
            if Path(command[0]).name == 'ssh':command[-1] += ' --recover'
            else:command.append('--recover')
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        # Keep diagnostics in the private run directory, never in the repository.
        results[role] = {'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
        (directory / ('health-recovery.json' if recover else 'health.json')).write_text(json.dumps(results, indent=2))
        if result.returncode:
            raise RuntimeError(f'{role}: CAN health check failed; inspect preserved health log')
        if not any(json.loads(line).get('result') == 'CAN_HEALTHY' for line in result.stdout.splitlines() if line.startswith('{')):
            raise RuntimeError(f'{role}: missing CAN health acknowledgement')
