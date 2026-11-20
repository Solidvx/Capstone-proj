#!/usr/bin/env python3
"""Summarize IVI stage timestamps or a legacy latency_ms CSV."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from collections import defaultdict

CURRENT_FIELDS=['run_id','boot_id','sample_id','stage','timestamp_ns','status','reason','frame_id']
PAIRS={'T1-T4':('T1','T4'),'T1-T2':('T1','T2'),'T2-T3':('T2','T3'),'T3-T4':('T3','T4')}


def current_report(rows,expected=None):
    """Analyze current recorder evidence, never infer physical display success."""
    if any(set(row)!=set(CURRENT_FIELDS) or any(value is None for value in row.values()) for row in rows):
        raise ValueError('exact current eight-column latency CSV required')
    if expected is not None and (type(expected) is not int or expected<=0):raise ValueError('positive expected completion count required')
    if not rows:
        return {'schema':'ivi-latency-status-v1','status':'INCOMPLETE','run_id':None,'boot_id':None,
            'observed_samples':0,'unobserved_sample_ids':0,
            'counts':{name:0 for name in ('FRAME_SWAPPED','NOT_RENDERED','INDETERMINATE','UNFINISHED_PENDING')},
            'expected_completed':expected or 0,'completion_shortfall':expected or 0,
            'intervals':{name:{'samples':0,'avg_ms':None,'p95_ms':None,'p99_ms':None,'max_ms':None} for name in PAIRS},
            'note':'No sample/clock identity observed. Zero observed samples are not a successful measurement.'}
    runs={(row['run_id'],row['boot_id']) for row in rows}
    if len(runs)!=1:raise ValueError('mixed run/boot clocks cannot be aggregated')
    run,boot=next(iter(runs))
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',run) or run=='development' or
        not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',boot)):
        raise ValueError('explicit run and Linux boot UUID required')
    def number(value):
        if not re.fullmatch('[1-9][0-9]{0,19}',value) or int(value)>=2**64:
            raise ValueError('positive uint64 timestamp/identity required')
        return int(value)
    samples={};frames=set();last_new_id=0;last_frame=0;last_t4=0;unobserved=0
    for row in rows:
        sample=number(row['sample_id']);stage=row['stage']
        if stage=='T1':
            if sample<=last_new_id or sample in samples:raise ValueError('duplicate/backward sample identity')
            unobserved+=sample-last_new_id-1
            samples[sample]={};last_new_id=sample
        if sample not in samples:raise ValueError('sample stage without original T1')
        stages=samples[sample]
        if 'terminal' in stages:raise ValueError('sample already has a final outcome')
        if stage in ('T1','T2','T3'):
            if (len(stages)>=3 or stage!=('T1','T2','T3')[len(stages)] or
                row['status']!='PENDING' or row['reason'] or row['frame_id']):
                raise ValueError('duplicate/out-of-order pending stage or metadata')
            stages[stage]=number(row['timestamp_ns']);continue
        if not {'T1','T2','T3'}<=stages.keys():raise ValueError('final result lacks pending stages')
        if stage=='T4':
            frame=number(row['frame_id']);timestamp=number(row['timestamp_ns'])
            if (row['status']!='FRAME_SWAPPED' or row['reason']!='QT_SIGNAL_PROXY_ONLY' or frame in frames or
                frame<=last_frame or timestamp<last_t4):
                raise ValueError('invalid or duplicate completed render frame')
            if not stages['T1']<=stages['T2']<=stages['T3']<=timestamp:
                raise ValueError('completed timestamps moved backward')
            frames.add(frame);last_frame=frame;last_t4=timestamp
            stages['T4']=timestamp;stages['terminal']='FRAME_SWAPPED'
        elif stage=='RESULT' and not row['timestamp_ns']:
            if row['status']=='NOT_RENDERED' and row['reason']=='COALESCED_BEFORE_SYNC':
                number(row['frame_id']);stages['terminal']='NOT_RENDERED'
            elif row['status']=='INDETERMINATE' and row['reason'] in (
                    'WINDOW_NOT_EXPOSED','TIMESTAMP_ORDER','NO_MATCHING_SWAP_BEFORE_EXIT'):
                if row['reason']=='NO_MATCHING_SWAP_BEFORE_EXIT':
                    if row['frame_id']:raise ValueError('unmatched exit cannot claim render frame')
                else:number(row['frame_id'])
                stages['terminal']='INDETERMINATE'
            else:raise ValueError('unknown final latency status/reason')
        else:raise ValueError('unknown latency stage/metadata')
    counts={name:sum(stages.get('terminal')==name for stages in samples.values())
            for name in ('FRAME_SWAPPED','NOT_RENDERED','INDETERMINATE')}
    unfinished=sum('terminal' not in stages for stages in samples.values())
    counts['INDETERMINATE']+=unfinished;counts['UNFINISHED_PENDING']=unfinished
    metrics={}
    for name,(start,end) in PAIRS.items():
        values=[(stage[end]-stage[start])/1e6 for stage in samples.values() if stage.get('terminal')=='FRAME_SWAPPED']
        stats=summary(values) if values else (0,None,None,None,None)
        metrics[name]=dict(zip(('samples','avg_ms','p95_ms','p99_ms','max_ms'),stats))
    expected=len(samples) if expected is None else expected
    shortfall=max(0,expected-counts['FRAME_SWAPPED'])
    incomplete=bool(shortfall or unobserved or counts['NOT_RENDERED'] or counts['INDETERMINATE'])
    return {'schema':'ivi-latency-status-v1','status':'INCOMPLETE' if incomplete else 'COMPLETE',
        'run_id':run,'boot_id':boot,'observed_samples':len(samples),'unobserved_sample_ids':unobserved,'counts':counts,
        'expected_completed':expected,'completion_shortfall':shortfall,'intervals':metrics,
        'note':'T4 is Qt frameSwapped proxy, not panel pixels. Missing CAN/Service publications require separate receive-log correlation. COMPLETE is not physical performance acceptance.'}


def write_current(path,report):
    with open(path,'x',newline='',encoding='utf-8') as target:
        writer=csv.writer(target)
        writer.writerow(['interval','samples','avg_ms','p95_ms','p99_ms','max_ms','run_id','boot_id',
            'observed_samples','frame_swapped','not_rendered','indeterminate','unfinished_pending',
            'unobserved_sample_ids','expected_completed','completion_shortfall','measurement_status'])
        for name,metrics in report['intervals'].items():
            writer.writerow([name,metrics['samples'],*[metrics[field] for field in ('avg_ms','p95_ms','p99_ms','max_ms')],
                report['run_id'],report['boot_id'],report['observed_samples'],report['counts']['FRAME_SWAPPED'],
                report['counts']['NOT_RENDERED'],report['counts']['INDETERMINATE'],report['counts']['UNFINISHED_PENDING'],
                report['unobserved_sample_ids'],report['expected_completed'],report['completion_shortfall'],report['status']])


def percentile(samples: list[float], fraction: float) -> float:
    return samples[math.ceil(fraction * len(samples)) - 1]


def summary(samples: list[float]) -> tuple[int, float, float, float, float]:
    if not samples:
        raise SystemExit("no complete latency samples")
    if any(not math.isfinite(sample) or sample < 0 for sample in samples):
        raise SystemExit("latency samples must be finite and non-negative")
    samples.sort()
    return (
        len(samples),
        statistics.mean(samples),
        percentile(samples, 0.95),
        percentile(samples, 0.99),
        max(samples),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-samples", type=int)
    args = parser.parse_args()

    with open(args.input, newline="", encoding="utf-8") as source:
        reader=csv.DictReader(source);fields=reader.fieldnames;rows=list(reader)
    if fields==CURRENT_FIELDS:
        try:
            report=current_report(rows,args.expected_samples)
            write_current(args.output,report)
        except (OSError,ValueError) as error:raise SystemExit(str(error)) from None
        print(json.dumps(report,allow_nan=False))
        if report['status']!='COMPLETE':raise SystemExit('incomplete render measurement; summary preserved')
        return
    if fields and any(name in fields for name in ('status','reason','frame_id')):
        raise SystemExit('current status CSV requires exact eight-column header')
    if not rows:raise SystemExit('no latency rows')

    intervals: dict[str, list[float]] = {}
    complete = 0
    incomplete = 0
    if "latency_ms" in rows[0]:
        intervals["latency"] = [float(row["latency_ms"]) for row in rows]
        complete = len(rows)
    else:
        required = {"run_id", "boot_id", "sample_id", "stage", "timestamp_ns"}
        if not required.issubset(rows[0]):
            raise SystemExit("stage CSV is missing required columns")
        samples: dict[tuple[str, str, str], dict[str, int]] = defaultdict(dict)
        for row in rows:
            key = (row["run_id"], row["boot_id"], row["sample_id"])
            stage = row["stage"].upper()
            if stage in samples[key]:
                raise SystemExit(f"duplicate stage {stage} for sample {key}")
            samples[key][stage] = int(row["timestamp_ns"])
        interval_pairs = {
            "T1-T4": ("T1", "T4"),
            "T1-T2": ("T1", "T2"),
            "T2-T3": ("T2", "T3"),
            "T3-T4": ("T3", "T4"),
        }
        intervals = {name: [] for name in interval_pairs}
        for stages in samples.values():
            if not {"T1", "T2", "T3", "T4"}.issubset(stages):
                incomplete += 1
                continue
            if not (stages["T1"] <= stages["T2"] <= stages["T3"] <= stages["T4"]):
                raise SystemExit("timestamps are not monotonic within a sample")
            complete += 1
            for name, (start, end) in interval_pairs.items():
                intervals[name].append((stages[end] - stages[start]) / 1_000_000.0)

    expected = args.expected_samples if args.expected_samples is not None else complete + incomplete
    missing = max(expected - complete, 0)
    with open(args.output, "w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(
            ["interval", "samples", "avg_ms", "p95_ms", "p99_ms", "max_ms", "missing"]
        )
        for name, samples in intervals.items():
            count, average, p95, p99, maximum = summary(samples)
            writer.writerow(
                [name, count, f"{average:.3f}", f"{p95:.3f}", f"{p99:.3f}",
                 f"{maximum:.3f}", missing]
            )
            print(
                f"{name}: samples={count} avg={average:.3f}ms p95={p95:.3f}ms "
                f"p99={p99:.3f}ms max={maximum:.3f}ms missing={missing}"
            )
    if incomplete or missing:
        raise SystemExit(f"incomplete measurement: incomplete={incomplete} missing={missing}")


if __name__ == "__main__":
    main()
