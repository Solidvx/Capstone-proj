"""Resumable test: 3 configurations x 4 attacks x 30 continuous trials per case.

Processes stay alive within a case; only execution errors restart them. Official campaigns are unchanged.
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


def completed_rows(history, count=30):
    completed = {}
    for _, manifest, rows in history:
        for row in rows:
            if row.get('trial_completed'):
                trial = row['trial']
                if trial in completed or not 1 <= trial <= count:
                    raise ValueError('duplicate or invalid completed trial')
                completed[trial] = row
    if sorted(completed) != list(range(1, len(completed)+1)):
        raise ValueError('completed trial sequence has gaps')
    return completed


def summarize(root):
    campaign = json.loads((root/'campaign.json').read_text()) if (root/'campaign.json').exists() else {}
    count = campaign.get('trials', 30)
    rows, sessions, attempted = [], 0, 0
    groups = []
    for config in (1, 2, 3):
        for attack in live.ATTACK_TYPES:
            history = attempts(root / f'C{config}-{attack}')
            sessions += len(history)
            attempted += sum(len(records) for _, _, records in history)
            group_rows = list(completed_rows(history, count).values())
            rows.extend(group_rows)
            groups.append({'config': config, 'attack': attack, 'completed': len(group_rows),
                           'valid': sum(r['status'] == 'VALID' for r in group_rows),
                           'ivi_type_results': dict(Counter(r.get('ivi_type_result', 'INVALID') for r in group_rows)),
                           'ecu_ids_type_results': dict(Counter(r.get('ecu_ids_type_result', 'NOT_EVALUATED') for r in group_rows)),
                           'bus_type_results': dict(Counter(r.get('bus_type_result', 'INVALID') for r in group_rows)),
                           'remote_matching_trials': {node: sum(r.get('remote_arrival', {}).get(node, {}).get('matching_frames', 0) > 0
                                for r in group_rows) for node in ('ecu', 'ivi')}})
    return {'stage': campaign.get('stage', 'test360'), 'planned_trials': 12*count, 'attempts_including_retries': attempted,
            'process_sessions': sessions, 'completed_trials': len(rows), 'remaining_trials': 12*count-len(rows),
            'valid_trials': sum(r['status'] == 'VALID' for r in rows),
            'invalid_trials': sum(r['status'] != 'VALID' for r in rows), 'groups': groups,
            'note': 'Completed includes INVALID; execution failures are separate. Process sessions include startup failures. Type results are measurements, not runner exit status.'}


def execute(settings, args, root, runner=None):
    runner = runner or live.run_case
    count = getattr(args, 'per_case', 30)
    for config in (1, 2, 3):
        for attack in live.ATTACK_TYPES:
            directory = root / f'C{config}-{attack}'
            directory.mkdir(parents=True, exist_ok=True)
            history = attempts(directory)
            retries = 0
            while True:
                completed = completed_rows(history, count)
                if any('ALERT_WITH_IDS_OFF' in r.get('invalid_reason', '') for r in completed.values()):
                    return 'ERROR'
                if history and history[-1][1]['status'] == 'ERROR' and len(completed) == count:
                    return 'ERROR'  # Collection/cleanup failure after final trial still needs investigation.
                if len(completed) == count:break
                trial = len(completed) + 1
                number = len(history) + 1
                segment = directory / f'attempt-{number:03d}'
                local = copy(args)
                local.trials, local.start_trial, local.resilient = count+1-trial, trial, True
                local.run_id = f'{args.run_id}-a{number:03d}'
                status = runner(settings, local, config, attack, segment)
                history = attempts(directory)
                manifest, rows = history[-1][1:]
                completed = completed_rows(history, count)
                save(root / 'checkpoint.json', {'config': config, 'attack': attack,
                     'completed_trials_in_case': len(completed), 'next_trial': len(completed)+1,
                     'attempt': number, 'status': status, 'max_recoveries': args.max_recoveries})
                if status == 'COMPLETE':
                    if len(completed) != count:raise ValueError('completed case must contain all planned trials')
                    continue
                if status == 'INTERRUPTED':return status
                # Progress to a new failing number gives that number its own retry budget.
                if len(completed) >= trial:retries = 0
                if not manifest.get('recoverable') or retries >= args.max_recoveries:
                    return 'ERROR'
                check_health(settings, segment, recover=True)
                retries += 1
                print(json.dumps({'result': 'RETRY', 'config': config, 'attack': attack,
                                  'trial': len(completed)+1, 'next_session': number+1}), flush=True)
    return 'COMPLETE'


def main(argv=None, *, pc=False):
    parser = argparse.ArgumentParser(description='PC controller: keyless remote CAN attacker; pilot / 360 / 1200 trials' if pc else __doc__)
    for name in ('settings', 'out', 'run-id'):parser.add_argument('--'+name, required=True)
    if not pc:parser.add_argument('--key', required=True)
    else:
        parser.add_argument('--stage',choices=('pilot','test360','official'),default='test360')
        parser.add_argument('--pilot-dir')
    parser.add_argument('--interface', default='can0')
    parser.add_argument('--sensor-mode', choices=('constant', 'ads1115'), default='constant')
    for name, default in (('rate', 1000), ('duration', 3), ('baseline', 2), ('post', 1)):
        parser.add_argument('--'+name, type=float, default=default)
    parser.add_argument('--max-recoveries', type=int, choices=range(0, 6), default=2)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--i-am-on-a-test-bus', action='store_true')
    args = parser.parse_args(argv)
    args.stage = args.stage if pc else 'test360'
    args.per_case = {'pilot':1,'test360':30,'official':100}[args.stage]
    try:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,39}', args.run_id):raise ValueError('invalid run-id (max 40 characters)')
        error = live.validate('flooding', args.interface, args.rate, args.duration, args.i_am_on_a_test_bus)
        if error:raise ValueError(error)
        if not all(math.isfinite(v) and 1 <= v <= 60 for v in (args.baseline, args.post)):raise ValueError('invalid phases')
        settings = json.loads(Path(args.settings).read_text())
        if pc:
            from security.experiments.pc_campaign import validate_pc_settings
            validate_pc_settings(settings)
        else:
            validate_extra(settings, live.validate_settings(settings))
            if len(Path(args.key).read_bytes()) != 32:raise ValueError('key must have 32 bytes')
        phases = {k: getattr(args, k) for k in ('rate', 'duration', 'baseline', 'post', 'sensor_mode', 'interface')}
        metadata = {'schema': 'pc-test360-v1' if pc else 'test360-v3-continuous', 'stage': args.stage, 'trials': args.per_case, 'run_id': args.run_id,
                    'settings_sha256': live.sha256(args.settings), 'phases': phases,
                    'source_sha256': {p.as_posix(): live.sha256(p) for p in sorted(Path('security').rglob('*.py'))}}
        if pc and args.stage == 'official':
            if not args.pilot_dir:raise ValueError('PC official stage requires --pilot-dir')
            pilot = Path(args.pilot_dir)
            previous = json.loads((pilot/'campaign.json').read_text())
            result = summarize(pilot)
            if previous.get('schema') != 'pc-test360-v1' or previous.get('stage') != 'pilot' or result['valid_trials'] != 12:
                raise ValueError('12 valid PC pilot trials required')
            if json.loads((pilot/'summary.json').read_text()).get('status') != 'COMPLETE':raise ValueError('pilot must finish cleanly')
            for field in ('settings_sha256','phases','source_sha256'):
                if previous[field] != metadata[field]:raise ValueError('pilot settings/phases/source changed')
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
            if pc:
                from security.experiments.pc_campaign import run_case
                status = execute(settings, args, root, runner=run_case)
            else:
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
        return 130 if status == 'INTERRUPTED' else (0 if status == 'COMPLETE' and result.get('valid_trials') == 12*args.per_case else 2)


if __name__ == '__main__':
    raise SystemExit(main())
