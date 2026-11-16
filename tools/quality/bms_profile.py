"""TC-BMS-002/S-21 fixed CSV inputs and actual native product-path scoring.

Truth never enters the native evaluator. All seven predeclared cases, including
unfavourable sensitivity results, remain in the report. No CAN, key or device.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
POLICY={'samples':36000,'dt_s':0.1,'initial_soc':0.8,'capacity_ah':50.,'true_current_a':-2.,
    'cells_series':10,'ocv_coefficients':[2.1667,-3.7321,2.7655,3.0],
    'temperature_c':25,'seed':None,'observations_at':'interval end; first update at0.1s',
    'truth_at':'t0 and each interval end; never passed to estimator'}
CASES=[{'name':'control','role':'control','current_bias_a':0.,'cell_voltage_bias_v':0.}]
for current,label in ((.1,'plus'),(-.1,'minus')):
    CASES.append({'name':'current_'+label,'role':'primary','current_bias_a':current,'cell_voltage_bias_v':0.})
for current,label in ((.1,'plus'),(-.1,'minus')):
    for voltage,vlabel in ((.01,'plus'),(-.01,'minus')):
        CASES.append({'name':'current_'+label+'_voltage_'+vlabel,'role':'sensitivity',
            'current_bias_a':current,'cell_voltage_bias_v':voltage})
OBS=['voltage_v','current_a','temperature_c']
TRUTH=['time_s','reference_soc_pct']
PRED=['time_s','observed_voltage_v','observed_current_a','estimated_soc_pct','coulomb_soc_pct']
SOURCES=('adaptive_ecu/tools/evaluate_soc_profile.cpp','adaptive_ecu/src/app/ekf_soc_estimator.cpp',
    'adaptive_ecu/include/ekf_soc_estimator.h','adaptive_ecu/include/virtual_battery.h',
    'adaptive_ecu/src/app/sensor_simulator.cpp','adaptive_ecu/include/sensor_simulator.h',
    'tools/quality/bms_profile.py')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,value):
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')


def reference(k):return .8-2.*(k*.1)/(50.*3600.)


def pack_voltage(soc):return 10.*(((2.1667*soc-3.7321)*soc+2.7655)*soc+3.)


def generate(root):
    root.mkdir(parents=True,exist_ok=False)
    with (root/'truth.csv').open('x',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n');writer.writerow(TRUTH)
        for k in range(POLICY['samples']+1):writer.writerow([format(k*.1,'.17g'),format(reference(k)*100,'.17g')])
    for case in CASES:
        path=root/case['name'];path.mkdir()
        with (path/'observations.csv').open('x',newline='') as stream:
            writer=csv.writer(stream,lineterminator='\n');writer.writerow(OBS)
            for k in range(1,POLICY['samples']+1):
                writer.writerow([format(pack_voltage(reference(k))+10*case['cell_voltage_bias_v'],'.17g'),
                    format(-2.+case['current_bias_a'],'.17g'),'25'])
    files=['truth.csv']+[case['name']+'/observations.csv' for case in CASES]
    manifest={'schema':'bms-s21-input-v1','environment':'synthetic','policy':POLICY,'cases':CASES,
        'files_sha256':{name:digest(root/name) for name in files},
        'note':'Virtual model consistency, not independently measured cell/OCV accuracy. No post-result tuning.'}
    save(root/'inputs.json',manifest)
    return manifest


def read_rows(path,header,limit):
    if path.stat().st_size>12*1024*1024:raise ValueError('CSV exceeds bounded size')
    rows=[]
    with path.open(newline='') as stream:
        reader=csv.reader(stream)
        if next(reader,None)!=header:raise ValueError('CSV header mismatch')
        for raw in reader:
            if len(raw)!=len(header) or len(rows)>=limit:raise ValueError('CSV row count/width mismatch')
            values=tuple(float(value) for value in raw)
            if not all(math.isfinite(value) for value in values):raise ValueError('CSV nonfinite value')
            rows.append(values)
    return rows


def validate_inputs(root):
    manifest=json.loads((root/'inputs.json').read_text())
    names={'truth.csv'}|{case['name']+'/observations.csv' for case in CASES}
    if (manifest.get('schema')!='bms-s21-input-v1' or manifest.get('environment')!='synthetic' or
        manifest.get('policy')!=POLICY or manifest.get('cases')!=CASES or set(manifest.get('files_sha256',{}))!=names):
        raise ValueError('fixed S-21 input manifest mismatch')
    if any(digest(root/name)!=manifest['files_sha256'][name] for name in names):raise ValueError('S-21 input hash mismatch')
    truth=read_rows(root/'truth.csv',TRUTH,POLICY['samples']+1)
    if len(truth)!=POLICY['samples']+1:raise ValueError('separate truth row count mismatch')
    for k,row in enumerate(truth):
        if row[0]!=k*.1 or not math.isclose(row[1],reference(k)*100,rel_tol=0,abs_tol=1e-11):
            raise ValueError('truth does not match independent fixed charge balance')
    return manifest,truth


def score(root,case):
    _,truth=validate_inputs(root)
    observed=read_rows(root/case['name']/'observations.csv',OBS,POLICY['samples'])
    predictions=read_rows(root/case['name']/'predictions.csv',PRED,POLICY['samples'])
    if len(predictions)!=POLICY['samples'] or len(observed)!=POLICY['samples']:
        raise ValueError('incomplete observations/predictions')
    errors=[[],[]]
    def float32(value):return struct.unpack('f',struct.pack('f',value))[0]
    for k,(sample,pred) in enumerate(zip(observed,predictions),1):
        voltage,current,temp=sample
        expected_voltage=pack_voltage(reference(k))+10*case['cell_voltage_bias_v']
        if (not math.isclose(voltage,expected_voltage,rel_tol=0,abs_tol=1e-12) or
            current!=-2.+case['current_bias_a'] or temp!=25):
            raise ValueError('observation does not match predeclared S-21 case')
        if (abs(pred[0]-truth[k][0])>1e-9 or pred[1]!=float32(voltage) or pred[2]!=float32(current)):
            raise ValueError('native timestep/actual quantized observation mismatch')
        if not all(0<=value<=100 for value in pred[3:]):raise ValueError('estimated SOC out of range')
        for index,value in enumerate(pred[3:]):errors[index].append(value-truth[k][1])
    metrics=[{'rmse_pp':math.sqrt(math.fsum(e*e for e in values)/len(values)),
              'max_absolute_error_pp':max(map(abs,values)),
              'final_soc_pct':predictions[-1][3+index]} for index,values in enumerate(errors)]
    better=metrics[0]['rmse_pp']<metrics[1]['rmse_pp']
    # Existing unit-test numerical consistency guard, not a cell accuracy goal.
    roundoff_guard_pp=100*POLICY['samples']*2**-23
    control_ok=all(value['max_absolute_error_pp']<roundoff_guard_pp for value in metrics)
    passed=better if case['role']=='primary' else control_ok if case['role']=='control' else True
    return {**case,'samples':len(predictions),'duration_s':predictions[-1][0],
        'reference_final_soc_pct':truth[-1][1],'ekf':metrics[0],'coulomb':metrics[1],
        'strict_improvement_required':case['role']=='primary','ekf_better_than_coulomb':better,
        'control_roundoff_guard_pp':roundoff_guard_pp if case['role']=='control' else None,
        'criterion':'strict EKF RMSE improvement' if case['role']=='primary' else
            'numerical consistency' if case['role']=='control' else 'report all sensitivity outcomes',
        'status':'PASS' if passed else 'FAIL'}


def run(executable,root):
    executable=Path(executable).resolve();root=Path(root)
    if not executable.is_file():raise ValueError('built native evaluator required')
    generate(root)
    inputs_digest=digest(root/'inputs.json')
    identity={'executable_sha256':digest(executable),'source_sha256':{name:digest(ROOT/name) for name in SOURCES}}
    rows=[];status='INVALID';error=None
    try:
        for case in CASES:
            if digest(root/'inputs.json')!=inputs_digest:raise ValueError('input manifest changed during evaluation')
            validate_inputs(root)
            folder=root/case['name']
            # Native child receives only public observations and sample count.
            command=[str(executable),'--profile',str((folder/'observations.csv').resolve()),'--samples',str(POLICY['samples'])]
            with (folder/'predictions.csv').open('xb') as output,(folder/'process.log').open('xb') as stderr:
                completed=subprocess.run(command,stdout=output,stderr=stderr,timeout=30)
            if completed.returncode:raise ValueError('native evaluator failed; partial output retained')
            if digest(executable)!=identity['executable_sha256']:raise ValueError('native executable changed during run')
            rows.append(score(root,case))
        if digest(root/'inputs.json')!=inputs_digest:raise ValueError('input manifest changed during evaluation')
        if {name:digest(ROOT/name) for name in SOURCES}!=identity['source_sha256']:
            raise ValueError('source changed during evaluation')
        status='PASS' if all(row['status']=='PASS' for row in rows) else 'FAIL'
    except KeyboardInterrupt:status='INTERRUPTED';error='interrupted; partial artifacts retained'
    except (OSError,ValueError,subprocess.SubprocessError) as failure:error=str(failure)
    report={'schema':'bms-s21-profile-result-v1','environment':'synthetic','status':status,
        'scope':'Actual SensorSimulator PROFILE_CSV and product EKF; no CAN/main-loop or hardware acceptance',
        'tc_id':'TC-BMS-002','policy':POLICY,'cases':rows,'planned_cases':len(CASES),'completed_cases':len(rows),
        'runtime':{'python':platform.python_version(),'system':platform.system(),'architecture':platform.machine()},
        'identity':identity,'inputs_manifest_sha256':inputs_digest,
        'files_sha256':{p.relative_to(root).as_posix():digest(p) for p in sorted(root.rglob('*')) if p.is_file()},
        'not_measured':['independent physical OCV/cell validity','NASA replay','CAN/ADS1115/display behaviour'],
        'note':'Sensitivity reversals remain visible. Passing fixed synthetic criteria is not general battery accuracy.'}
    if error:report['error']=error
    save(root/'report.json',report)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(argv)
    try:report=run(args.executable,args.output_dir)
    except (OSError,ValueError) as failure:
        print(json.dumps({'status':'INVALID','error':str(failure)}));return 2
    print(json.dumps({key:report[key] for key in ('status','environment','planned_cases','completed_cases')}))
    return 0 if report['status']=='PASS' else 1 if report['status']=='FAIL' else 2


if __name__=='__main__':raise SystemExit(main())
