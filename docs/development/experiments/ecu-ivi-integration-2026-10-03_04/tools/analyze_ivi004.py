"""004 latency CSV diagnostics. Never grants a formal physical-test PASS."""
import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import uuid
from collections import Counter
from pathlib import Path

FIELDS = 'run_id boot_id sample_id stage timestamp_ns status reason frame_id'.split()


def analyze(path, expected=300):
    if expected <= 0:
        raise ValueError('expected must be positive')
    samples = {}
    identity = None
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != FIELDS:
            raise ValueError('expected exact 004 eight-column header')
        for line, r in enumerate(reader, 2):
            if None in r or any(v is None for v in r.values()):
                raise ValueError(f'line {line}: malformed row')
            run, boot = r['run_id'], r['boot_id']
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', run) or run in ('development', 'ivi-p4'):
                raise ValueError('invalid or placeholder run identity')
            if str(uuid.UUID(boot)) != boot.lower():
                raise ValueError('invalid boot UUID')
            if identity is None:
                identity = (run, boot)
            if identity != (run, boot):
                raise ValueError('mixed run or boot identities')
            sid = int(r['sample_id'])
            if sid <= 0:
                raise ValueError('nonpositive sample ID')
            rows = samples.setdefault(sid, {})
            stage = r['stage']
            if stage not in ('T1', 'T2', 'T3', 'T4', 'RESULT') or stage in rows:
                raise ValueError('unknown or duplicate stage')
            if 'T4' in rows or 'RESULT' in rows:
                raise ValueError('row after final result')
            if r['frame_id'] and int(r['frame_id']) <= 0:
                raise ValueError('invalid frame ID')
            if stage in ('T1', 'T2', 'T3'):
                if r['status'] != 'PENDING' or r['reason'] or r['frame_id']:
                    raise ValueError('invalid pending row')
                if stage != ('T1', 'T2', 'T3')[len(rows)]:
                    raise ValueError('out of order initial stages')
            elif stage == 'T4':
                if (r['status'], r['reason']) != ('FRAME_SWAPPED', 'QT_SIGNAL_PROXY_ONLY') or not r['frame_id']:
                    raise ValueError('invalid T4 result')
            else:
                allowed = {'NOT_RENDERED': {'COALESCED_BEFORE_SYNC'},
                           'INDETERMINATE': {'WINDOW_NOT_EXPOSED', 'TIMESTAMP_ORDER', 'NO_MATCHING_SWAP_BEFORE_EXIT'}}
                if r['timestamp_ns'] or r['reason'] not in allowed.get(r['status'], set()):
                    raise ValueError('invalid RESULT row')
            if stage != 'RESULT' and (not r['timestamp_ns'].isdigit()):
                raise ValueError('invalid stage timestamp')
            rows[stage] = r
    if not samples:
        raise ValueError('empty CSV')
    counts, reasons = Counter(), Counter()
    intervals = {k: [] for k in ('T1-T4', 'T1-T2', 'T2-T3', 'T3-T4')}
    frame_ids = set()
    shared_times = Counter()
    for sid, rows in samples.items():
        final = rows.get('T4', rows.get('RESULT'))
        if final is None:
            counts['INDETERMINATE'] += 1
            reasons['UNRESOLVED_PENDING'] += 1
            continue
        if not {'T1', 'T2', 'T3'}.issubset(rows):
            raise ValueError('final result without initial stages')
        counts[final['status']] += 1
        reasons[final['reason']] += 1
        if final['status'] != 'FRAME_SWAPPED':
            continue
        times = [int(rows[k]['timestamp_ns']) for k in ('T1', 'T2', 'T3', 'T4')]
        if times != sorted(times):
            raise ValueError('FRAME_SWAPPED timestamps out of order')
        fid = int(final['frame_id'])
        if fid in frame_ids:
            raise ValueError('multiple completed samples for one frame')
        frame_ids.add(fid)
        shared_times[times[-1]] += 1
        for name in intervals:
            start, end = name.split('-')
            intervals[name].append((int(rows[end]['timestamp_ns'])-int(rows[start]['timestamp_ns']))/1e6)
    stats = {}
    for name, values in intervals.items():
        values.sort()
        stats[name] = {'count': len(values), 'mean_ms': statistics.mean(values) if values else None,
                       'max_ms': max(values) if values else None,
                       'p99_ms': values[math.ceil(.99*len(values))-1] if values else None}
    completed = counts['FRAME_SWAPPED']
    observed = len(samples)
    notes = []
    if completed < expected: notes.append('TARGET_SHORTFALL')
    if counts['NOT_RENDERED']: notes.append('NOT_RENDERED_PRESENT')
    if counts['INDETERMINATE']: notes.append('INDETERMINATE_PRESENT')
    if any(n > 1 for n in shared_times.values()): notes.append('SHARED_T4_TIMESTAMP_REVIEW')
    t14 = stats['T1-T4']
    if completed and (t14['mean_ms'] > 50 or t14['max_ms'] > 100): notes.append('LATENCY_TARGET_EXCEEDED')
    return {'source_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'run_id': identity[0], 'boot_id': identity[1], 'expected_completed': expected,
            'observed_samples': observed, 'counts': {k: counts[k] for k in ('FRAME_SWAPPED','NOT_RENDERED','INDETERMINATE')},
            'reasons': dict(reasons), 'completion_fraction_of_recorded': completed/observed,
            'shortfall': max(0, expected-completed), 'intervals': stats, 'review_flags': notes,
            'formal_verdict': 'NOT_ASSESSED',
            'limits': 'Qt signal proxy only. CSV cannot establish physical pixels or detect samples absent before T1 recording. Reconcile receiver/CAN logs, visibility and loss separately. Formal test requires >=1000 valid samples.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('--expected', type=int, default=300)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    report = analyze(args.input, args.expected)
    with args.out.open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
