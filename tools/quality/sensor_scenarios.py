"""N02 synthetic source-fault cases; labels never enter the native product/IDS.

Caller supplies fixture size, event interval and biases explicitly. This is not
a CAN attack tool, freeze policy, physical model acceptance or IF evaluation.
"""
import argparse
from collections import Counter
import csv
import hashlib
from dataclasses import asdict
import json
import math
from pathlib import Path
import struct
import subprocess

from tools.quality.bms_profile import reference,pack_voltage,OBS,PRED
from security.experiments.can_capture import sha256
from security.secoc_module import SecOcModule
from security.can_session import SessionContext,derive_keys,data_mac
from security.ids.runtime_detector import RuntimeDetector,Config,Observation
from security.ids.session_detector import SessionDetector

ROOT=Path(__file__).resolve().parents[2]
CASES=('control','allowed_constant','voltage_drift','voltage_jump','voltage_freeze','voltage_current_mismatch')
FIELDS={'schema','samples','event_start','event_end','drift_final_bias_v','jump_bias_v','mismatch_current_bias_a'}
BASELINE='Existing S-21 virtual50Ah/initial80%/-2A/pack OCV; not physical ground truth'
BOUNDS='zero-based inclusive start/exclusive end; first native interval ends at0.1s'
SOURCES=('tools/quality/sensor_scenarios.py','tools/quality/bms_profile.py',
    'adaptive_ecu/tools/evaluate_soc_profile.cpp','adaptive_ecu/src/app/sensor_simulator.cpp',
    'adaptive_ecu/src/app/input_lineage.cpp','adaptive_ecu/src/app/ekf_soc_estimator.cpp',
    'adaptive_ecu/src/bsw/can_publisher.cpp','security/ids/runtime_detector.py',
    'security/ids/session_detector.py','security/can_session.py','security/secoc_module.py')


def validate(settings):
    if not isinstance(settings,dict) or set(settings)!=FIELDS or settings['schema']!='sensor-source-supplement-v1':
        raise ValueError('explicit sensor-source-supplement-v1 settings required')
    if any(type(settings[key]) is not int for key in ('samples','event_start','event_end')) or not (
        1<=settings['event_start']<settings['event_end']<settings['samples']<=36000):
        raise ValueError('zero-based start/end must leave baseline and recovery; at most36000 samples')
    for key in ('drift_final_bias_v','jump_bias_v','mismatch_current_bias_a'):
        try:finite=type(settings[key]) in (int,float) and math.isfinite(settings[key])
        except OverflowError:finite=False
        if not finite or settings[key]==0:
            raise ValueError('explicit finite nonzero fixture biases required')
    return settings


def sample(settings,case,index):
    if case not in CASES or not 0<=index<settings['samples']:raise ValueError('invalid case/sample')
    voltage=pack_voltage(reference(index+1));current=-2.;temperature=25.
    expected=(voltage,current,temperature)
    active=settings['event_start']<=index<settings['event_end'] and case not in ('control','allowed_constant')
    if case=='allowed_constant':voltage=pack_voltage(reference(1))
    elif active:
        if case=='voltage_drift':
            voltage+=settings['drift_final_bias_v']*((index-settings['event_start']+1)/(settings['event_end']-settings['event_start']))
        elif case=='voltage_jump':voltage+=settings['jump_bias_v']
        elif case=='voltage_freeze':voltage=pack_voltage(reference(settings['event_start']))
        elif case=='voltage_current_mismatch':current+=settings['mismatch_current_bias_a']
    observed=(voltage,current,temperature)
    # Control is an allowed steady input, not an assertion about a real cell.
    if case=='allowed_constant':expected=observed
    label={'sample_index':index,'interval_end_s':(index+1)*.1,'domain':'synthetic-sensor-input',
        'sensor_fault_injected':active,'condition':case if active else 'no_fault_injected','can_attack':None,
        'reference_values':expected,'observed_values':observed,
        'delta':[a-b for a,b in zip(observed,expected)]}
    return observed,label


def save(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')


def generate(root,settings):
    validate(settings);root.mkdir(parents=True,exist_ok=False,mode=0o700)
    files={}
    for case in CASES:
        folder=root/case;folder.mkdir()
        with (folder/'observations.csv').open('x',newline='') as obs,(folder/'labels.jsonl').open('x') as truth:
            writer=csv.writer(obs,lineterminator='\n');writer.writerow(OBS)
            for index in range(settings['samples']):
                values,label=sample(settings,case,index)
                writer.writerow([format(value,'.17g') for value in values])
                truth.write(json.dumps(label,allow_nan=False)+'\n')
        for name in ('observations.csv','labels.jsonl'):files[case+'/'+name]=sha256(folder/name)
    manifest={'schema':'sensor-source-inputs-v1','environment':'synthetic','settings':settings,'cases':list(CASES),
        'units':dict(zip(OBS,('V','A','degC'))),'dt_s':.1,
        'baseline':BASELINE,'event_bounds':BOUNDS,
        'can_attack_injected':False,'files_sha256':files}
    save(root/'inputs.json',manifest)
    return manifest


def validate_inputs(root,settings):
    manifest=json.loads((root/'inputs.json').read_text())
    names={case+'/'+name for case in CASES for name in ('observations.csv','labels.jsonl')}
    if (manifest.get('schema')!='sensor-source-inputs-v1' or manifest.get('environment')!='synthetic' or
        manifest.get('settings')!=settings or manifest.get('cases')!=list(CASES) or
        manifest.get('units')!=dict(zip(OBS,('V','A','degC'))) or manifest.get('dt_s')!=.1 or
        manifest.get('baseline')!=BASELINE or manifest.get('event_bounds')!=BOUNDS or
        manifest.get('can_attack_injected') is not False or set(manifest.get('files_sha256',{}))!=names):
        raise ValueError('source input manifest mismatch')
    for name in names:
        if sha256(root/name)!=manifest['files_sha256'][name]:raise ValueError('source input hash mismatch')
    for case in CASES:
        with (root/case/'observations.csv').open(newline='') as obs,(root/case/'labels.jsonl').open() as truth:
            reader=csv.reader(obs)
            if next(reader,None)!=OBS:raise ValueError('source observation header mismatch')
            for index in range(settings['samples']):
                values,label=sample(settings,case,index)
                actual=next(reader,None);raw=truth.readline()
                if actual!=[format(v,'.17g') for v in values] or not raw or json.loads(raw)!=json.loads(json.dumps(label)):
                    raise ValueError('source observations/labels differ from predeclared case')
            if next(reader,None) is not None or truth.readline():raise ValueError('source input count mismatch')
    return manifest


class FixtureContext:
    """Public deterministic test context only; never a remote ECU context pipe."""
    def __init__(self):
        self.context=SessionContext(7,bytes(range(16)),bytes(range(16,32)))
        self.keys=derive_keys(bytes(range(32)),self.context);self.generation=1;self.boundary_ns=0
    def ready(self,now):return True


def inspect_native(path,settings,case,events_path):
    legacy=RuntimeDetector(key=bytes(range(32)));session=SessionDetector(Config(),FixtureContext())
    signer=SecOcModule(bytes(range(32)));counts={name:Counter() for name in ('legacy','session')}
    types={name:Counter() for name in counts};verified={name:0 for name in counts}
    index=0;repeated=longest=0;previous=None
    raw_digest=hashlib.sha256();frame_digests={name:hashlib.sha256() for name in counts}
    with path.open(newline='') as stream,events_path.open('x') as output:
        reader=csv.DictReader(stream)
        if reader.fieldnames!=PRED+['bms_payload_hex']:raise ValueError('native source result header mismatch')
        for index,row in enumerate(reader,1):
            if index>settings['samples']:raise ValueError('extra native source result')
            expected,_=sample(settings,case,index-1)
            f32=lambda value:struct.unpack('f',struct.pack('f',value))[0]
            time=float(row['time_s']);voltage=float(row['observed_voltage_v']);current=float(row['observed_current_a'])
            soc=float(row['estimated_soc_pct']);coulomb=float(row['coulomb_soc_pct'])
            if (not all(map(math.isfinite,(time,voltage,current,soc,coulomb))) or abs(time-index*.1)>1e-9 or
                voltage!=f32(expected[0]) or current!=f32(expected[1]) or not 0<=soc<=100 or not 0<=coulomb<=100):
                raise ValueError('native actual input/time/state mismatch')
            payload=bytes.fromhex(row['bms_payload_hex'])
            if len(payload)!=8:raise ValueError('native BMS payload width mismatch')
            raw_digest.update(struct.pack('>d',time)+payload)
            repeated=repeated+1 if payload==previous else 1;longest=max(longest,repeated);previous=payload
            auths={'legacy':signer.sign(0x102,0x100,payload).data,
                   'session':data_mac(session.source.keys['data'],0x100,index,payload)+index.to_bytes(4,'big')}
            for name,detector in (('legacy',legacy),('session',session)):
                frame_digests[name].update(struct.pack('>dH',time,0x100)+payload)
                frame_digests[name].update(struct.pack('>dH',time+.001,0x102)+auths[name])
                for event in detector.observe(Observation(time,0x100,payload))+detector.observe(Observation(time+.001,0x102,auths[name])):
                    counts[name][event.reason]+=1
                    if event.attack_type:types[name][str(event.attack_type)]+=1
                    output.write(json.dumps(dict(profile=name,**asdict(event)),allow_nan=False)+'\n')
                authenticated=(detector.counters.get(0x100)==index-1) if name=='legacy' else (
                    detector.highest==index and detector.last_authenticated==time+.001)
                verified[name]+=int(authenticated)
    if index!=settings['samples']:raise ValueError('incomplete native source result')
    return {'status':'COMPLETE','samples':index,'legacy_reasons':dict(counts['legacy']),'session_reasons':dict(counts['session']),
        'legacy_attack_type_counts':dict(types['legacy']),'session_attack_type_counts':dict(types['session']),
        'dummy_authenticated_pairs':verified,'longest_equal_raw_run_samples':longest,
        'raw_timed_payload_sha256':raw_digest.hexdigest(),
        'dummy_frame_stream_sha256':{name:digest.hexdigest() for name,digest in frame_digests.items()},
        'raw_interval_s':.1,'labels_used_by_detectors':False,'node_b_verifier_evaluated':False,'if_evaluated':False}


def run(executable,root,settings):
    validate(settings);executable=Path(executable).resolve();root=Path(root)
    if not executable.is_file():raise ValueError('built native evaluator required')
    before={name:sha256(ROOT/name) for name in SOURCES};binary=sha256(executable)
    generate(root,settings);manifest_hash=sha256(root/'inputs.json')
    report={'schema':'sensor-source-evaluation-v1','environment':'synthetic','status':'INCOMPLETE','cases':[],
        'settings':settings,'source_sha256':before,'native_executable_sha256':binary,
        'scope':'Native CSV/EKF/BMS encoder and offline existing raw rules with public dummy authentication. No actual CAN attacks or ECU/IVI session.',
        'not_measured':['physical sensor normality','CAN attack detection/blocking rates','IF effect','operational freeze/plausibility thresholds']}
    try:
        for case in CASES:
            validate_inputs(root,settings)
            if sha256(root/'inputs.json')!=manifest_hash or sha256(executable)!=binary:raise ValueError('source/executable changed')
            folder=root/case
            command=[str(executable),'--profile',str((folder/'observations.csv').resolve()),'--samples',str(settings['samples']),'--emit-bms']
            with (folder/'native.csv').open('xb') as stdout,(folder/'native.log').open('xb') as stderr:
                child=subprocess.run(command,stdout=stdout,stderr=stderr,timeout=30)
            if child.returncode:
                row={'status':'NATIVE_REJECTED' if child.returncode==2 else 'NATIVE_FAILED','returncode':child.returncode}
            else:
                try:row=inspect_native(folder/'native.csv',settings,case,folder/'events.jsonl')
                except (OSError,ValueError,KeyError,TypeError,OverflowError) as error:
                    row={'status':'INVALID_NATIVE_EVIDENCE','error':str(error)}
            row['case']=case;report['cases'].append(row)
        validate_inputs(root,settings)
        if before!={name:sha256(ROOT/name) for name in SOURCES} or sha256(executable)!=binary:
            raise ValueError('source/executable changed during evaluation')
        statuses={r['status'] for r in report['cases']}
        report['status']='COMPLETE' if statuses=={'COMPLETE'} else (
            'COMPLETE_WITH_REJECTIONS' if statuses<={'COMPLETE','NATIVE_REJECTED'} else 'INVALID')
        groups={}
        for row in report['cases']:
            if row['status']=='COMPLETE':groups.setdefault(row['raw_timed_payload_sha256'],[]).append(row['case'])
        report['identical_raw_timed_payload_groups']=[names for names in groups.values() if len(names)>1]
        report['stream_digest_format']='raw: big-endian float64 time +8B payload; dummy frames: big-endian float64 time +uint16 ID +8B payload'
    except KeyboardInterrupt:report['status']='INTERRUPTED'
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        report['status']='INVALID';report['error']=str(error)
    report['inputs_sha256']=manifest_hash
    report['files_sha256']={p.relative_to(root).as_posix():sha256(p) for p in root.rglob('*') if p.is_file()}
    save(root/'report.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',required=True,type=Path);parser.add_argument('--settings',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args()
    try:report=run(args.executable,args.output_dir,json.loads(args.settings.read_text()))
    except (OSError,ValueError) as error:parser.error(str(error))
    print(json.dumps({'status':report['status'],'cases':report['cases'],'output':str(args.output_dir)}))
    return 0 if report['status']=='COMPLETE' else 2


if __name__=='__main__':raise SystemExit(main())
