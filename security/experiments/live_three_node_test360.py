"""Resumable test: 3 configurations x 4 attacks x 30 independent trials.

Each attempt owns fresh ECU/IDS/IVI processes. Official campaigns are unchanged.
"""
import argparse
from collections import Counter
from copy import copy
import fcntl
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess

from security.experiments import live_three_node as live
from security.experiments.test360_support import check_health, validate_extra


def save(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def attempts(directory):
    found = []
    for path in sorted(directory.glob('attempt-*'), key=lambda p: int(p.name.split('-')[1])):
        if not (path / 'manifest.json').exists():
            raise ValueError(f'unsealed attempt: {path}; verify remote cleanup manually before a new campaign')
        manifest, rows = live.read_run(path)
        if not manifest.get('cleanup_confirmed'):
            raise ValueError(f'remote cleanup unconfirmed: {path}; operator investigation required')
        found.append((path, manifest, rows))
    return found


def summarize(root):
    rows, total_attempts, completed = [], 0, 0
    groups = []
    for config in (1, 2, 3):
        for attack in live.ATTACK_TYPES:
            group_rows = []
            for trial in range(1, 31):
                history = attempts(root / f'C{config}-{attack}' / f'trial-{trial:03d}')
                total_attempts += len(history)
                if history and history[-1][1]['status'] == 'COMPLETE':
                    completed += 1
                    group_rows.extend(history[-1][2])
            rows.extend(group_rows)
            groups.append({'config': config, 'attack': attack, 'completed': len(group_rows),
                           'valid': sum(r['status'] == 'VALID' for r in group_rows),
                           'ivi_type_results': dict(Counter(r.get('ivi_type_result', 'INVALID') for r in group_rows)),
                           'bus_type_results': dict(Counter(r.get('bus_type_result', 'INVALID') for r in group_rows)),
                           'remote_matching_trials': {node: sum(r.get('remote_arrival', {}).get(node, {}).get('matching_frames', 0) > 0
                                for r in group_rows) for node in ('ecu', 'ivi')}})
    return {'stage': 'test360', 'planned_trials': 360, 'attempts_including_retries': total_attempts,
            'completed_trials': completed, 'remaining_trials': 360-completed,
            'valid_trials': sum(r['status'] == 'VALID' for r in rows),
            'invalid_trials': sum(r['status'] != 'VALID' for r in rows), 'groups': groups,
            'note': 'Completed includes INVALID. MATCH/COMPOUND/MISMATCH/MISSED are measurements, not runner exit status. All failed attempts remain on disk.'}


def execute(settings, args, root):
    for config in (1, 2, 3):
        for attack in live.ATTACK_TYPES:
            for trial in range(1, 31):
                directory = root / f'C{config}-{attack}' / f'trial-{trial:03d}'
                directory.mkdir(parents=True, exist_ok=True)
                history = attempts(directory)
                if history and history[-1][1]['status'] == 'COMPLETE':
                    if any('ALERT_WITH_IDS_OFF' in r.get('invalid_reason', '') for r in history[-1][2]):
                        return 'ERROR'
                    continue
                for recovery in range(args.max_recoveries + 1):
                    number = len(history) + 1
                    segment = directory / f'attempt-{number:03d}'
                    local = copy(args)
                    local.trials, local.start_trial, local.resilient = 1, trial, True
                    local.run_id = f'{args.run_id}-t{trial:03d}-a{number:03d}'
                    status = live.run_case(settings, local, config, attack, segment)
                    # Verify sealed files before considering any automatic recovery.
                    history = attempts(directory)
                    manifest, rows = history[-1][1:]
                    save(root / 'checkpoint.json', {'config': config, 'attack': attack, 'trial': trial,
                         'attempt': number, 'status': status, 'max_recoveries': args.max_recoveries})
                    if status == 'COMPLETE':
                        if len(rows) != 1:raise ValueError('completed attempt must contain exactly one trial')
                        if 'ALERT_WITH_IDS_OFF' in rows[0].get('invalid_reason', ''):
                            return 'ERROR'  # Defence configuration drift is not a trial result.
                        break
                    if status == 'INTERRUPTED':return status
                    if not manifest.get('recoverable') or recovery == args.max_recoveries:
                        return 'ERROR'
                    check_health(settings, segment, recover=True)
                    print(json.dumps({'result': 'RETRY', 'config': config, 'attack': attack,
                                      'trial': trial, 'next_attempt': number+1}), flush=True)
    return 'COMPLETE'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('settings', 'out', 'run-id', 'key'):parser.add_argument('--'+name, required=True)
    parser.add_argument('--interface', default='can0')
    parser.add_argument('--sensor-mode', choices=('constant', 'ads1115'), default='constant')
    for name, default in (('rate', 1000), ('duration', 3), ('baseline', 2), ('post', 1)):
        parser.add_argument('--'+name, type=float, default=default)
    parser.add_argument('--max-recoveries', type=int, choices=range(0, 6), default=2)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--i-am-on-a-test-bus', action='store_true')
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,39}', args.run_id):raise ValueError('invalid run-id (max 40 characters)')
        error = live.validate('flooding', args.interface, args.rate, args.duration, args.i_am_on_a_test_bus)
        if error:raise ValueError(error)
        if not all(math.isfinite(v) and 1 <= v <= 60 for v in (args.baseline, args.post)):raise ValueError('invalid phases')
        settings = json.loads(Path(args.settings).read_text())
        validate_extra(settings, live.validate_settings(settings))
        if len(Path(args.key).read_bytes()) != 32:raise ValueError('key must have 32 bytes')
        phases = {k: getattr(args, k) for k in ('rate', 'duration', 'baseline', 'post', 'sensor_mode', 'interface')}
        metadata = {'schema': 'test360-v2', 'stage': 'test360', 'trials': 30, 'run_id': args.run_id,
                    'settings_sha256': live.sha256(args.settings), 'phases': phases,
                    'source_sha256': {p.as_posix(): live.sha256(p) for p in sorted(Path('security').rglob('*.py'))}}
        root = Path(args.out)
        if args.resume:
            if live.sha256(root/'settings.json') != metadata['settings_sha256']:raise ValueError('saved settings hash mismatch')
            if json.loads((root/'campaign.json').read_text()) != metadata:raise ValueError('resume requires unchanged sources, settings, phases and run-id')
        else:
            root.mkdir(parents=True, exist_ok=False)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    with (root / 'campaign.lock').open('a') as lock:
        try:fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:parser.error('campaign already running')
        if not args.resume:
            (root/'settings.json').write_bytes(Path(args.settings).read_bytes())
            save(root/'campaign.json', metadata)
        old = signal.signal(signal.SIGTERM, live.interrupted)
        status, error = 'ERROR', None
        try:
            summarize(root)  # Refuse unsealed or cleanup-uncertain resume before touching hardware.
            check_health(settings, root)
            status = execute(settings, args, root)
        except KeyboardInterrupt:status = 'INTERRUPTED'
        except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as failure:
            error = str(failure)
        finally:
            signal.signal(signal.SIGTERM, old)
        try:result = summarize(root)
        except (OSError, ValueError) as failure:
            result = {'stage': 'test360', 'planned_trials': 360, 'evidence_error': str(failure)}
        result['status'] = status
        if error:result['error'] = error
        save(root/'summary.json', result)
        print(json.dumps(result), flush=True)
        return 130 if status == 'INTERRUPTED' else (0 if status == 'COMPLETE' and result.get('valid_trials') == 360 else 2)


if __name__ == '__main__':
    raise SystemExit(main())
