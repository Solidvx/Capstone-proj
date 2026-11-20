"""Scoring/lineage error tests; synthetic stubs do not establish BMS accuracy."""
import csv
import json
from pathlib import Path
import struct
from types import SimpleNamespace

import pytest
from tools.quality import bms_profile as profile


@pytest.fixture
def dataset(tmp_path,monkeypatch):
    # Short fixtures test the evaluator's safeguards, never official36,000 rows.
    monkeypatch.setitem(profile.POLICY,'samples',20)
    root=tmp_path/'data';profile.generate(root)
    return root


def predictions(root,case,ekf_error=0.,cc_error=.1,write=True):
    observed=profile.read_rows(root/case['name']/'observations.csv',profile.OBS,20)
    def f32(value):return struct.unpack('f',struct.pack('f',value))[0]
    rows=[[k*.1,f32(obs[0]),f32(obs[1]),profile.reference(k)*100+ekf_error,
           profile.reference(k)*100+cc_error] for k,obs in enumerate(observed,1)]
    if write:write_predictions(root,case,rows)
    return rows


def write_predictions(root,case,rows):
    with (root/case['name']/'predictions.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(profile.PRED);writer.writerows(rows)


def test_fixed_inputs_are_deterministic_and_truth_is_separate(dataset,tmp_path):
    first,truth=profile.validate_inputs(dataset)
    other=tmp_path/'again';second=profile.generate(other)
    assert first==second and len(truth)==21
    assert truth[0]==(0.,80.)
    assert truth[-1][1]==profile.reference(20)*100
    assert len(first['cases'])==7
    assert [case['role'] for case in first['cases']].count('primary')==2
    assert [case['role'] for case in first['cases']].count('sensitivity')==4
    assert len(set(first['files_sha256'].values()))==8
    for case in profile.CASES:
        assert (dataset/case['name']/'observations.csv').read_text().splitlines()[0]=='voltage_v,current_a,temperature_c'
    before=(dataset/'truth.csv').read_bytes()
    with pytest.raises(FileExistsError):profile.generate(dataset)
    assert (dataset/'truth.csv').read_bytes()==before


def test_primary_requires_strict_improvement_and_sensitivity_reversals_remain(dataset):
    primary=profile.CASES[1]
    predictions(dataset,primary)
    result=profile.score(dataset,primary)
    assert result['status']=='PASS' and result['ekf_better_than_coulomb']
    predictions(dataset,primary,ekf_error=.1,cc_error=.1)
    assert profile.score(dataset,primary)['status']=='FAIL'
    sensitivity=profile.CASES[3]
    predictions(dataset,sensitivity,ekf_error=1.,cc_error=.1)
    result=profile.score(dataset,sensitivity)
    assert result['status']=='PASS' and not result['ekf_better_than_coulomb']
    assert result['ekf']['rmse_pp']>result['coulomb']['rmse_pp']
    assert result['criterion']=='report all sensitivity outcomes'


def test_control_checks_numerical_consistency_without_demanding_ekf_superiority(dataset):
    case=profile.CASES[0]
    predictions(dataset,case,ekf_error=0.,cc_error=0.)
    result=profile.score(dataset,case)
    assert result['status']=='PASS' and not result['strict_improvement_required']
    predictions(dataset,case,ekf_error=5.,cc_error=0.)
    assert profile.score(dataset,case)['status']=='FAIL'


@pytest.mark.parametrize('damage',['short','extra','nan','range','time','voltage','current','header'])
def test_incomplete_or_unrelated_native_rows_are_not_measurements(dataset,damage):
    case=profile.CASES[1];rows=predictions(dataset,case)
    if damage=='short':rows.pop()
    elif damage=='extra':rows.append(rows[-1])
    elif damage=='nan':rows[1][3]=float('nan')
    elif damage=='range':rows[1][3]=101
    elif damage=='time':rows[1][0]=rows[0][0]
    elif damage=='voltage':rows[1][1]+=.001
    elif damage=='current':rows[1][2]+=.001
    write_predictions(dataset,case,rows)
    if damage=='header':
        path=dataset/case['name']/'predictions.csv';path.write_text(path.read_text().replace('time_s','wrong',1))
    with pytest.raises(ValueError):profile.score(dataset,case)


@pytest.mark.parametrize('repair_hash',[False,True])
def test_truth_tampering_is_rejected_even_if_file_hash_is_rewritten(dataset,repair_hash):
    path=dataset/'truth.csv';path.write_text(path.read_text().replace('80\n','79\n',1))
    if repair_hash:
        manifest=json.loads((dataset/'inputs.json').read_text())
        manifest['files_sha256']['truth.csv']=profile.digest(path)
        (dataset/'inputs.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError):profile.validate_inputs(dataset)


def test_failed_native_run_retains_logs_and_does_not_claim_completed_cases(tmp_path,monkeypatch):
    monkeypatch.setitem(profile.POLICY,'samples',20)
    binary=tmp_path/'dummy-native';binary.write_bytes(b'not a real executable')
    calls=[]
    def fail(command,stdout,stderr,timeout):
        calls.append(command);stdout.write(b'partial rows');stderr.write(b'injected failure')
        return SimpleNamespace(returncode=2)
    monkeypatch.setattr(profile.subprocess,'run',fail)
    out=tmp_path/'failed';result=profile.run(binary,out)
    assert result['status']=='INVALID' and result['completed_cases']==0
    assert len(calls)==1 and len(calls[0])==5 and '--profile' in calls[0]
    assert all('truth' not in arg and '--key' not in arg for arg in calls[0])
    assert (out/'control/predictions.csv').read_bytes()==b'partial rows'
    assert (out/'control/process.log').read_bytes()==b'injected failure'
    assert result['files_sha256']['control/predictions.csv']==profile.digest(out/'control/predictions.csv')
    assert json.loads((out/'report.json').read_text())['status']=='INVALID'


def test_runner_records_criteria_failure_without_hiding_later_sensitivity_cases(tmp_path,monkeypatch):
    monkeypatch.setitem(profile.POLICY,'samples',20)
    binary=tmp_path/'dummy-native';binary.write_bytes(b'not a real executable')
    def emitted(command,stdout,stderr,timeout):
        root=Path(command[2]).parent.parent
        case=next(c for c in profile.CASES if c['name']==Path(command[2]).parent.name)
        rows=predictions(root,case,ekf_error=0. if case['role']=='control' else 1.,cc_error=0.,write=False)
        # The runner already owns this output file; emulate the native writer.
        import io
        text=io.StringIO();writer=csv.writer(text);writer.writerow(profile.PRED);writer.writerows(rows)
        stdout.write(text.getvalue().encode());return SimpleNamespace(returncode=0)
    monkeypatch.setattr(profile.subprocess,'run',emitted)
    result=profile.run(binary,tmp_path/'all')
    assert result['status']=='FAIL' and result['completed_cases']==7
    assert len([r for r in result['cases'] if r['role']=='sensitivity' and not r['ekf_better_than_coulomb']])==4
