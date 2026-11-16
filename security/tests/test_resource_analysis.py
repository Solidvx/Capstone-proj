"""Bounded N07 generation analysis refuses mixed/forged denominators."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from security.experiments.summarize_resources import analyze, main
from security.ids.resource_metrics import RuntimeMetrics


def fixture():
    clock=iter((1_000_000_000,2_000_000_000,3_000_000_000))
    cpu=iter((1_000_000,2_000_000,3_000_000))
    memory=lambda:{'rss_bytes':4096,'process_lifetime_peak_rss_bytes':8192}
    metrics=RuntimeMetrics('fixture','legacy-v1','replay',clock=lambda:next(clock),cpu_clock=lambda:next(cpu),memory=memory)
    metrics.start({'storage':'disabled','file_bytes':None,'file_sha256':None,'state_sha256':None})
    start={'result':'START','run_id':'fixture','protocol':'legacy-v1','mode':'rules-only','resource_measurement':True}
    return [start,metrics.report('IN_PROGRESS'),{'result':'END'},metrics.report('COMPLETE',final=True)]


def write(root,rows,name='events.jsonl'):
    path=root/name;path.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows));return path


def test_complete_partial_and_disabled_are_distinct(tmp_path):
    rows=fixture();path=write(tmp_path,rows)
    report=analyze(path)
    assert report['status']=='COMPLETE' and report['available_measurements']==2
    assert report['source_log']['bytes']==path.stat().st_size
    assert report['official_acceptance'] is False
    path=write(tmp_path,rows[:2],'partial.jsonl')
    report=analyze(path);assert report['status']=='INCOMPLETE' and report['final_summary_available'] is False
    assert report['last_measurement']['elapsed_s']==1
    rows[0]['resource_measurement']=False
    report=analyze(write(tmp_path,[rows[0],{'result':'END'}],'disabled.jsonl'))
    assert report['status']=='NOT_MEASURED' and report['last_measurement'] is None


def test_interrupted_and_error_never_become_complete(tmp_path):
    for status in ('INTERRUPTED','ERROR'):
        rows=fixture();rows.pop(2);rows[-1]['status']=status
        report=analyze(write(tmp_path,rows,status+'.jsonl'))
        assert report['status']==status and report['final_summary_available']


@pytest.mark.parametrize('field,value',[
    ('run_id','other'),('pid',0),('final',False),('status','NOT_STARTED'),
    ('elapsed_s',1000),('cpu_percent_one_core',-1),('measurement_id','wrong'),
    ('protocol','session-v2'),('source','vehicle'),('host_monotonic_end_ns',0),
])
def test_bad_identity_or_time_denominator_refused(tmp_path,field,value):
    rows=fixture();rows[-1][field]=value
    with pytest.raises((ValueError,TypeError)):analyze(write(tmp_path,rows))


def test_missing_end_mixed_generation_and_trailing_records_refused(tmp_path):
    original=fixture()
    variants=[original[:2]+original[3:],original+[{'result':'END'}],
              [original[0],original[0]]+original[1:]]
    rows=deepcopy(original);rows[-1]['measurement_id']='00000000000040008000000000000001';variants.append(rows)
    rows=deepcopy(original);rows[-1]['counts']['completed_frames']=1;variants.append(rows)
    rows=deepcopy(original);rows[-1]['counts']['input_frames']=True;variants.append(rows)
    rows=deepcopy(original);rows[-1]['durations']['model_anomaly']['calls']=1;variants.append(rows)
    rows=deepcopy(original);rows[-1]['model_artifact']['file_bytes']=1024;variants.append(rows)
    rows=deepcopy(original);rows[-1]['source_clock']['used_as_host_elapsed']=True;variants.append(rows)
    rows=deepcopy(original);rows[0]['resource_measurement']=False;variants.append(rows)
    rows=deepcopy(original);rows.insert(2,{'result':'MODEL_EVALUATION'});variants.append(rows)
    for i,rows in enumerate(variants):
        with pytest.raises(ValueError):analyze(write(tmp_path,rows,str(i)+'.jsonl'))


def test_capacity_partial_line_corruption_and_no_overwrite(tmp_path,capsys):
    path=write(tmp_path,fixture())
    with pytest.raises(ValueError):analyze(path,max_bytes=path.stat().st_size-1)
    output=tmp_path/'summary.json'
    assert main(['--events',str(path),'--out',str(output)])==0
    before=output.read_bytes()
    assert main(['--events',str(path),'--out',str(output)])==2
    assert output.read_bytes()==before
    path.write_bytes(path.read_bytes()[:-1])
    with pytest.raises(ValueError):analyze(path)
    path.write_text('x'*65537+'\n')
    with pytest.raises(ValueError):analyze(path)
    path.write_text('{broken}\n')
    with pytest.raises(ValueError):analyze(path)
