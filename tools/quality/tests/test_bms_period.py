"""Fixed period criterion and capture integrity; no physical performance claim."""
from copy import deepcopy
import hashlib
import json

import pytest
from tools.quality.bms_period import analyze,evaluate


def capture(gaps=None):
    start=10**12;stamp=start;rows=[]
    for gap in [0]+([100_000_000]*100 if gaps is None else gaps):
        stamp+=gap
        rows.append(dict(received_ns=stamp,can_id=0x100,dlc=8,data='00'*8,extended=False,remote=False,error=False))
    manifest=dict(schema='bms-period-capture-v1',environment='vcan',clock='kernel-realtime-mapped-to-local-monotonic-ns',
        boot_id='11111111-2222-4333-8444-555555555555',start_ns=start,end_ns=stamp+1,
        rx_dropped=0,interface_rx_dropped=0,clock_mapping_max_change_ns=0,status='COMPLETE',normal_attested=True)
    return rows,manifest


def test_every_interval_inclusive_bounds_and_auth_frames_excluded():
    rows,meta=capture([90_000_000,110_000_000]*50)
    for row in rows[::2]:
        auth=deepcopy(row);auth['can_id']=0x102;rows.insert(rows.index(row)+1,auth)
    report=analyze(rows,meta)
    assert report['status']=='PASS' and report['intervals']==100 and report['frames_total']>101
    assert report['metrics']['mean_ms']==100 and not report['physical_tc_acceptance']


def test_right_average_does_not_hide_out_of_range_intervals():
    rows,meta=capture([80_000_000,120_000_000]+[100_000_000]*98)
    report=analyze(rows,meta)
    assert report['status']=='FAIL' and report['metrics']['mean_ms']==100
    assert [v['interval'] for v in report['violations']]==[1,2]


@pytest.mark.parametrize('damage',['short','drop','interface_drop','clock','partial','unknown_normal','error','malformed'])
def test_invalid_evidence_never_becomes_a_pass(damage):
    rows,meta=capture()
    if damage=='short':rows.pop()
    elif damage=='drop':meta['rx_dropped']=1
    elif damage=='interface_drop':meta['interface_rx_dropped']=1
    elif damage=='clock':meta['clock_mapping_max_change_ns']=10_000_001
    elif damage=='partial':meta['status']='INTERRUPTED'
    elif damage=='unknown_normal':meta['normal_attested']=False
    elif damage=='error':rows[-1]['error']=True
    elif damage=='malformed':rows[-1]['extended']=True
    assert analyze(rows,meta)['status']=='INVALID'


@pytest.mark.parametrize('damage',['reverse','boundary','clock_kind','boot','boolean_time','payload'])
def test_unparseable_or_ambiguous_times_are_rejected(damage):
    rows,meta=capture()
    if damage=='reverse':rows[1]['received_ns']=rows[0]['received_ns']-1;meta['start_ns']-=2
    elif damage=='boundary':meta['end_ns']=rows[-1]['received_ns']-1
    elif damage=='clock_kind':meta['clock']='unknown'
    elif damage=='boot':meta['boot_id']='unknown'
    elif damage=='boolean_time':rows[0]['received_ns']=True
    elif damage=='payload':rows[0]['data']='ff'
    with pytest.raises(ValueError):analyze(rows,meta)


def test_hash_lineage_and_output_preservation(tmp_path):
    rows,meta=capture();raw=tmp_path/'frames.jsonl'
    raw.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    meta['frames_sha256']=hashlib.sha256(raw.read_bytes()).hexdigest()
    (tmp_path/'capture.json').write_text(json.dumps(meta));out=tmp_path/'report.json'
    assert evaluate(tmp_path,out)['status']=='PASS';before=out.read_bytes()
    with pytest.raises(FileExistsError):evaluate(tmp_path,out)
    assert out.read_bytes()==before
    raw.write_text(raw.read_text()+'{}\n')
    with pytest.raises(ValueError,match='hash'):evaluate(tmp_path,tmp_path/'new.json')
