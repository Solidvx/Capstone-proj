"""Source-fault labels and native-evidence safeguards, never detection targets."""
from copy import deepcopy
import csv
import json
from types import SimpleNamespace

import pytest

from tools.quality import sensor_scenarios as source


def settings():
    return {'schema':'sensor-source-supplement-v1','samples':20,'event_start':5,'event_end':15,
        'drift_final_bias_v':-.5,'jump_bias_v':-6.,'mismatch_current_bias_a':4.}


@pytest.mark.parametrize('key,value',[
    ('samples',True),('samples',36001),('event_start',0),('event_end',20),('event_end',5),
    ('jump_bias_v',0),('drift_final_bias_v',float('nan')),('mismatch_current_bias_a',True),
    ('jump_bias_v',10**1000),('schema','unknown')])
def test_no_implicit_parameters_or_nonfinite_inputs(key,value):
    s=settings();s[key]=value
    with pytest.raises(ValueError):source.validate(s)
    s=settings();s.pop('event_start')
    with pytest.raises(ValueError):source.validate(s)


def test_deterministic_cases_fault_phase_and_no_CAN_attack_labels(tmp_path):
    s=settings();a=source.generate(tmp_path/'a',s);b=source.generate(tmp_path/'b',s)
    assert a==b and a['cases']==list(source.CASES) and not a['can_attack_injected']
    source.validate_inputs(tmp_path/'a',s)
    for case in source.CASES:
        labels=[json.loads(line) for line in (tmp_path/'a'/case/'labels.jsonl').read_text().splitlines()]
        assert all(row['can_attack'] is None for row in labels)
        faulty=[row['sample_index'] for row in labels if row['sensor_fault_injected']]
        assert faulty==([] if case in ('control','allowed_constant') else list(range(5,15)))
    frozen=[source.sample(s,'voltage_freeze',i)[0][0] for i in range(5,15)]
    assert len(set(frozen))==1
    assert frozen[0]==source.sample(s,'control',4)[0][0]
    last=source.sample(s,'voltage_drift',14)[1]
    assert last['delta'][0]==pytest.approx(-.5)
    assert source.sample(s,'voltage_jump',15)[1]['delta']==[0,0,0]
    with pytest.raises(FileExistsError):source.generate(tmp_path/'a',s)


@pytest.mark.parametrize('repair_hash',[False,True])
def test_relabeling_fault_as_attack_or_rewriting_values_is_refused(tmp_path,repair_hash):
    s=settings();root=tmp_path/'a';source.generate(root,s)
    name='voltage_freeze/labels.jsonl';path=root/name
    rows=[json.loads(line) for line in path.read_text().splitlines()];rows[5]['can_attack']='replay'
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    if repair_hash:
        manifest=json.loads((root/'inputs.json').read_text());manifest['files_sha256'][name]=source.sha256(path)
        (root/'inputs.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError):source.validate_inputs(root,s)


def test_wrong_units_or_manifest_clock_are_not_accepted(tmp_path):
    s=settings();root=tmp_path/'a';source.generate(root,s)
    path=root/'inputs.json';manifest=json.loads(path.read_text())
    for key,value in (('units',{'voltage_v':'mV'}),('dt_s',1.),('event_bounds','unknown')):
        changed=deepcopy(manifest);changed[key]=value;path.write_text(json.dumps(changed))
        with pytest.raises(ValueError):source.validate_inputs(root,s)


@pytest.mark.parametrize('returncode,status',[(2,'COMPLETE_WITH_REJECTIONS'),(9,'INVALID')])
def test_native_rejections_and_crashes_are_preserved_without_stopping_other_cases(tmp_path,monkeypatch,returncode,status):
    executable=tmp_path/'dummy-native';executable.write_text('public mock fixture')
    calls=[]
    def reject(command,stdout,stderr,timeout):
        calls.append(command);stderr.write(b'dummy rejection\n');return SimpleNamespace(returncode=returncode)
    monkeypatch.setattr(source.subprocess,'run',reject)
    result=source.run(executable,tmp_path/'out',settings())
    assert result['status']==status and len(result['cases'])==len(calls)==6
    assert all('--emit-bms' in c and 'labels.jsonl' not in ' '.join(c) for c in calls)
    assert all(row['returncode']==returncode for row in result['cases'])
    assert not any((tmp_path/'out'/case/'events.jsonl').exists() for case in source.CASES)


def test_truncated_native_output_cannot_be_silently_filled(tmp_path):
    path=tmp_path/'native.csv'
    path.write_text(','.join(source.PRED+['bms_payload_hex'])+'\n')
    with pytest.raises(ValueError,match='incomplete'):source.inspect_native(path,settings(),'control',tmp_path/'events.jsonl')
