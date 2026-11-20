"""Read one IDS generation's N07 measurements in bounded memory.

This is a process-generation report, never a trial confusion matrix or a maximum
throughput benchmark. SIGKILL/no final record remains INCOMPLETE even when the
log was successfully collected and its file hash is valid.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import uuid

from security.ids.resource_metrics import Duration, RuntimeMetrics


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError('nonnegative integer measurement required')
    return value


def finite(value):
    if type(value) not in (int,float) or not math.isfinite(value) or value < 0:
        raise ValueError('finite nonnegative measurement required')
    return value


def near(left, right):
    if not math.isclose(finite(left), finite(right), rel_tol=1e-9, abs_tol=1e-12):
        raise ValueError('measurement denominator or unit mismatch')


def validate_sample(row, started, prior, logged_models, logged_skips):
    if (row.get('schema')!='ids-resource-v1' or row.get('run_id')!=started.get('run_id')
        or row.get('protocol')!=started.get('protocol') or type(row.get('final')) is not bool
        or row['final']!=(row['result']=='RESOURCE_SUMMARY')):
        raise ValueError('measurement identity/schema mismatch')
    if integer(row.get('pid'))==0:raise ValueError('missing measurement process')
    identifier=row.get('measurement_id')
    if not isinstance(identifier,str) or len(identifier)!=32 or uuid.UUID(hex=identifier).version!=4:
        raise ValueError('measurement UUIDv4 required')
    if row.get('source') not in ('live','replay'):raise ValueError('invalid measurement source')
    if row.get('status') not in ('IN_PROGRESS','COMPLETE','INTERRUPTED','ERROR'):
        raise ValueError('measurement has no valid loop interval')
    if (row['final'] and row['status']=='IN_PROGRESS') or (not row['final'] and row['status']!='IN_PROGRESS'):
        raise ValueError('measurement status/final mismatch')
    start,end=integer(row['host_monotonic_start_ns']),integer(row['host_monotonic_end_ns'])
    if end<=start:raise ValueError('measurement interval is empty/regressed')
    elapsed=(end-start)/1e9
    near(row['elapsed_s'],elapsed)
    near(row['cpu_percent_one_core'],finite(row['cpu_process_s'])/elapsed*100)
    counts=row['counts']
    expected=set(RuntimeMetrics('','','').counts)
    if not isinstance(counts,dict) or set(counts)!=expected:
        raise ValueError('measurement counter schema mismatch')
    for value in counts.values():integer(value)
    for suffix in ('frames','ticks'):
        # A signal may interrupt between processing and completion accounting.
        pending=counts['input_'+suffix]-counts['completed_'+suffix]-counts['failed_'+suffix]
        if pending<0 or pending>1 or (pending and row['status'] not in ('INTERRUPTED','ERROR')):
            raise ValueError('measurement input/completion denominator mismatch')
    if counts['incomplete_model_windows']>counts['model_evaluations']:
        raise ValueError('invalid incomplete window count')
    if (counts['model_evaluations']<logged_models or counts['model_skipped']<logged_skips
        or (row['status'] in ('IN_PROGRESS','COMPLETE') and
            (counts['model_evaluations']!=logged_models or counts['model_skipped']!=logged_skips))):
        raise ValueError('model log/measurement counts differ')
    durations=row['durations']
    if set(durations)!=set(RuntimeMetrics.stages):raise ValueError('measurement stages differ')
    for value in durations.values():
        calls=integer(value['calls']);failed=integer(value['failed_calls']);total=integer(value['total_ns'])
        if failed>calls:raise ValueError('failed stage count exceeds calls')
        bins=value['histogram_counts']
        if (value['histogram_upper_inclusive_ns']!=list(Duration.upper_ns)+[None]
            or not isinstance(bins,list) or len(bins)!=8 or sum(integer(v) for v in bins)!=calls):
            raise ValueError('stage histogram denominator mismatch')
        if calls:
            low,high=integer(value['minimum_ns']),integer(value['maximum_ns'])
            if not low<=high or not low*calls<=total<=high*calls:
                raise ValueError('stage duration range mismatch')
            near(value['mean_ns'],total/calls)
        elif total or any(value[k] is not None for k in ('minimum_ns','maximum_ns','mean_ns')):
            raise ValueError('empty stage is not N/A')
    near(row['rates']['completed_frames_per_host_second'],counts['completed_frames']/elapsed)
    near(row['rates']['model_windows_per_host_second'],counts['model_evaluations']/elapsed)
    if row['source_clock']['used_as_host_elapsed'] is not False:
        raise ValueError('source replay/event clock cannot be elapsed time')
    for memory in (row['memory_start'],row['memory_end']):
        if not isinstance(memory,dict):raise ValueError('memory snapshot required')
        for key in ('rss_bytes','process_lifetime_peak_rss_bytes'):
            if memory[key] is not None:integer(memory[key])
    model=row['model_artifact']
    if model['file_bytes'] is not None or model['file_sha256'] is not None:
        raise ValueError('runtime does not load model files; do not invent file size')
    if started['mode']=='rules-only':
        if model['storage']!='disabled' or model['state_sha256'] is not None or counts['model_evaluations']:
            raise ValueError('disabled model has fabricated inference')
    else:
        state=model['state_sha256']
        if (model['storage']!='trained_in_memory' or not isinstance(state,str) or len(state)!=64
            or any(c not in '0123456789abcdef' for c in state)):
            raise ValueError('actual model state fingerprint required')
    identity=started.get('startup_identity')
    if identity and (identity.get('resource_measurement') is not True or identity.get('trained_model_sha256')!=model['state_sha256']):
        raise ValueError('measurement differs from startup identity')
    if prior:
        for key in ('pid','measurement_id','protocol','source','host_monotonic_start_ns','memory_start','model_artifact'):
            if prior[key]!=row[key]:raise ValueError('mixed measurement lifetimes')
        if end<prior['host_monotonic_end_ns'] or row['cpu_process_s']<prior['cpu_process_s']:
            raise ValueError('measurement clock regressed')
        if any(counts[k]<prior['counts'][k] for k in counts):raise ValueError('measurement counter regressed')
        for name,value in durations.items():
            before=prior['durations'][name]
            if any(value[k]<before[k] for k in ('calls','failed_calls','total_ns')):
                raise ValueError('stage counter regressed')


def analyze(path, *, max_bytes=64*1024*1024):
    if type(max_bytes) is not int or max_bytes<1:raise ValueError('explicit positive file budget required')
    path=Path(path);digest=hashlib.sha256();started=prior=None
    total=records=measurements=models=skipped=ended=0;final=False
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno())
        if before.st_size>max_bytes:raise ValueError('resource input exceeds selected file budget')
        while True:
            raw=stream.readline(65538)
            if not raw:break
            total+=len(raw)
            if total>max_bytes or len(raw)-1>65536 or not raw.endswith(b'\n'):
                raise ValueError('incomplete/oversized resource input')
            digest.update(raw);row=json.loads(raw)
            if not isinstance(row,dict):raise ValueError('IDS record must be an object')
            records+=1;kind=row.get('result')
            if final:raise ValueError('records after final measurement')
            if started is None:
                if (kind!='START' or not isinstance(row.get('run_id'),str)
                    or row.get('mode') not in ('rules-only','rules+if')
                    or row.get('protocol') not in ('legacy-v1','session-v2')):
                    raise ValueError('one IDS START required')
                started=row
            elif kind=='START':raise ValueError('mixed IDS generations')
            if kind=='END':ended+=1
            if kind=='MODEL_EVALUATION':models+=1
            if kind=='MODEL_SKIPPED':skipped+=1
            if kind in ('RESOURCE_SAMPLE','RESOURCE_SUMMARY'):
                if started.get('resource_measurement') is not True:
                    raise ValueError('measurement not selected in START')
                validate_sample(row,started,prior,models,skipped)
                prior=row;measurements+=1;final=row['final']
        after=os.fstat(stream.fileno());named=path.stat()
        signature=lambda info:(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
        if signature(before)!=signature(after) or signature(after)!=signature(named) or total!=before.st_size:
            raise ValueError('IDS resource log changed during analysis')
    if started is None:raise ValueError('IDS START missing')
    if ended>1 or (final and prior['status']=='COMPLETE' and ended!=1):
        raise ValueError('completed measurement needs exactly one END')
    status=prior['status'] if final else 'INCOMPLETE' if started.get('resource_measurement') else 'NOT_MEASURED'
    return {'schema':'ids-resource-analysis-v1','status':status,'run_id':started['run_id'],
            'protocol':started['protocol'],'mode':started['mode'],
            'source_log':{'sha256':digest.hexdigest(),'bytes':total,'records':records},
            'available_measurements':measurements,'final_summary_available':final,
            'last_measurement':prior,'logged_model_evaluations':models,'logged_model_skipped':skipped,
            'scope':'One IDS process generation; periodic samples are cumulative. INCOMPLETE is not a complete lifetime. '
                    'No trial/attack rate attribution, maximum throughput, physical performance or IF effectiveness acceptance.',
            'official_acceptance':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events',required=True,type=Path)
    parser.add_argument('--max-bytes',type=int,default=64*1024*1024,help='match the selected collection budget')
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        if args.out.exists():raise ValueError('resource output must be new')
        result=analyze(args.events,max_bytes=args.max_bytes)
        with args.out.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
        print(json.dumps({'status':result['status'],'run_id':result['run_id']}))
        return 0 if result['status']=='COMPLETE' else 1
    except (OSError,ValueError,TypeError,KeyError,OverflowError) as error:
        print(json.dumps({'status':'INVALID','error':str(error)}));return 2


if __name__=='__main__':raise SystemExit(main())
