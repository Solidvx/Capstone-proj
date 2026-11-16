"""Current recorder CSV integrity/counting, independent of physical performance."""
from copy import deepcopy
import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/measure_latency.py'
spec=importlib.util.spec_from_file_location('measure_latency',SCRIPT)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
BOOT='11111111-2222-4333-8444-555555555555' # public dummy identity


def row(sample,stage,time='',status='PENDING',reason='',frame=''):
    return dict(zip(module.CURRENT_FIELDS,['dummy-run',BOOT,str(sample),stage,str(time),status,reason,str(frame)]))


def pending(sample=1,start=1000000):
    return [row(sample,'T1',start),row(sample,'T2',start+1000000),row(sample,'T3',start+2000000)]


def completed(sample=1,start=1000000,frame=1):
    return pending(sample,start)+[row(sample,'T4',start+3000000,'FRAME_SWAPPED','QT_SIGNAL_PROXY_ONLY',frame)]


def test_one_frame_does_not_turn_coalesced_pending_into_completions():
    rows=pending(1)+pending(2)+pending(3)
    rows+=[row(1,'RESULT','','NOT_RENDERED','COALESCED_BEFORE_SYNC',7),
           row(2,'RESULT','','NOT_RENDERED','COALESCED_BEFORE_SYNC',7),
           row(3,'T4',4000000,'FRAME_SWAPPED','QT_SIGNAL_PROXY_ONLY',7)]
    report=module.current_report(rows,1)
    assert report['status']=='INCOMPLETE' and report['observed_samples']==3
    assert report['counts']=={'FRAME_SWAPPED':1,'NOT_RENDERED':2,'INDETERMINATE':0,'UNFINISHED_PENDING':0}
    assert report['completion_shortfall']==0 # Target count does not hide observed lost renders.
    assert report['intervals']['T1-T4']=={'samples':1,'avg_ms':3.,'p95_ms':3.,'p99_ms':3.,'max_ms':3.}


def test_unfinished_and_zero_completed_still_produce_preserved_na_summary(tmp_path):
    rows=pending(1)+pending(2)
    rows.append(row(1,'RESULT','','INDETERMINATE','NO_MATCHING_SWAP_BEFORE_EXIT'))
    report=module.current_report(rows,2)
    assert report['counts']['INDETERMINATE']==2 and report['counts']['UNFINISHED_PENDING']==1
    assert report['intervals']['T1-T4']['avg_ms'] is None and report['completion_shortfall']==2
    path=tmp_path/'summary.csv';module.write_current(path,report)
    saved=list(csv.DictReader(path.open()))
    assert len(saved)==4 and all(r['samples']=='0' and r['avg_ms']=='' and r['measurement_status']=='INCOMPLETE' for r in saved)
    before=path.read_bytes()
    with pytest.raises(FileExistsError):module.write_current(path,report)
    assert path.read_bytes()==before


def test_completed_metrics_and_shortfall_do_not_infer_unseen_can_loss():
    report=module.current_report(completed(),2)
    assert report['observed_samples']==1 and report['completion_shortfall']==1
    assert report['counts']['NOT_RENDERED']==0 and report['status']=='INCOMPLETE'
    assert 'separate receive-log' in report['note']
    assert module.current_report(completed(),1)['status']=='COMPLETE'


def test_service_sample_identity_gaps_are_not_hidden_by_target_count():
    report=module.current_report(completed()+completed(3,5000000,2),2)
    assert report['status']=='INCOMPLETE' and report['counts']['FRAME_SWAPPED']==2
    assert report['completion_shortfall']==0 and report['unobserved_sample_ids']==1


def test_empty_current_capture_is_reported_without_inventing_clock_identity(tmp_path):
    path=tmp_path/'empty.csv';path.write_text(','.join(module.CURRENT_FIELDS)+'\n')
    target=tmp_path/'summary.csv'
    result=subprocess.run([sys.executable,str(SCRIPT),'--input',str(path),'--output',str(target),
        '--expected-samples','300'],capture_output=True,text=True,timeout=5)
    report=json.loads(result.stdout)
    assert result.returncode!=0 and report['observed_samples']==0 and report['completion_shortfall']==300
    assert report['run_id'] is None and report['boot_id'] is None and target.exists()


@pytest.mark.parametrize('damage',['run','boot','uuid','duplicate','time','frame','frame_backward',
    'timestamp_backward','unknown_status','reason','early_final','pending_frame','width','sample_backward'])
def test_mixed_or_impossible_current_evidence_is_rejected(damage):
    rows=completed()+completed(2,5000000,2)
    if damage=='run':rows[-1]['run_id']='another'
    elif damage=='boot':rows[-1]['boot_id']='22222222-2222-4333-8444-555555555555'
    elif damage=='uuid':
        for r in rows:r['boot_id']='fixed-placeholder'
    elif damage=='duplicate':rows.append(deepcopy(rows[-1]))
    elif damage=='time':rows[-1]['timestamp_ns']='5000000'
    elif damage=='frame':rows[-1]['frame_id']='1'
    elif damage=='frame_backward':rows[3]['frame_id']='3'
    elif damage=='timestamp_backward':rows[3]['timestamp_ns']='9000000'
    elif damage=='unknown_status':rows[-1]['status']='PASS'
    elif damage=='reason':rows[-1]['reason']='looks-rendered'
    elif damage=='early_final':rows.pop(-2)
    elif damage=='pending_frame':rows[0]['frame_id']='1'
    elif damage=='width':rows[0]['unexpected']='x'
    elif damage=='sample_backward':rows[4]['sample_id']='1'
    with pytest.raises(ValueError):module.current_report(rows,2)


def test_current_cli_preserves_incomplete_report_and_refuses_existing_output(tmp_path):
    source=tmp_path/'current.csv'
    with source.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,module.CURRENT_FIELDS);writer.writeheader();writer.writerows(pending())
    target=tmp_path/'summary.csv'
    command=[sys.executable,str(SCRIPT),'--input',str(source),'--output',str(target),'--expected-samples','1']
    result=subprocess.run(command,capture_output=True,text=True,timeout=5)
    assert result.returncode!=0 and target.exists()
    report=json.loads(result.stdout)
    assert report['status']=='INCOMPLETE' and report['counts']['UNFINISHED_PENDING']==1
    before=target.read_bytes();assert subprocess.run(command,capture_output=True,timeout=5).returncode!=0
    assert target.read_bytes()==before
