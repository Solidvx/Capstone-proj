"""Normal-only 0x200 wire-alert windows. Never equate this with IF-score FPR."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from security.experiments.validate_m5_settings import validate

STATS=('rx_dropped','rx_errors','tx_errors')
POLICY={'length_ns':1_000_000_000,'slide_ns':1_000_000_000,
        'min_frames_per_id_per_window':8,'max_gap_ns':300_000_000,
        'empty_windows':'INVALID, not silently excluded'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def timestamp(row):
    value=row.get('timestamp_ns')
    if not isinstance(value,str) or not value.isdigit():raise ValueError('integer string monotonic timestamp required')
    return int(value)


def analyze(root):
    manifest=json.loads((root/'manifest.json').read_text())
    if not isinstance(manifest,dict) or manifest.get('schema')!='normal-wire-fpr-v1' \
            or manifest.get('status')!='COMPLETE' or manifest.get('normal_only') is not True \
            or manifest.get('managed_alive_until_capture_end') is not True \
            or manifest.get('environment') not in ('vcan','physical-can') \
            or not isinstance(manifest.get('run_id'),str) or not manifest['run_id'] \
            or manifest.get('window_policy')!=POLICY:
        raise ValueError('invalid normal-only/supervision/window-policy manifest')
    interface=manifest.get('interface')
    if not isinstance(interface,str) or re.fullmatch(r'(?:vcan|can)[0-9]+',interface) is None \
            or (manifest['environment']=='vcan')!=interface.startswith('vcan'):
        raise ValueError('interface/environment mismatch')
    files=manifest.get('files')
    required={'bus.jsonl','ids-console.jsonl','normal.jsonl','receiver.jsonl','settings.json'}
    if not isinstance(files,dict) or not required<=set(files):raise ValueError('missing evidence hashes')
    for name,digest in files.items():
        if not isinstance(name,str) or Path(name).name!=name or name in ('.','..'):
            raise ValueError('unsafe evidence path')
        path=root/name
        if path.is_symlink() or not path.is_file() or sha(path)!=digest:raise ValueError('changed/missing evidence: '+name)
    run=manifest['run_id']
    validate(json.loads((root/'settings.json').read_text()),manifest['environment'])
    for name,expected in (('ids-console.jsonl',{'mode':'rules+if','send_alerts':True}),
                          ('normal.jsonl',{'secoc_on':True}),('receiver.jsonl',{'secoc_on':True})):
        records=[json.loads(v) for v in (root/name).read_text().splitlines()]
        if any(not isinstance(r,dict) for r in records):raise ValueError('invalid child record')
        ready=[r for r in records if r.get('result')=='READY']
        if len(ready)!=1 or ready[0].get('run_id')!=run or any(
                type(ready[0].get(k)) is not type(v) or ready[0][k]!=v for k,v in expected.items()):
            raise ValueError('missing/mismatched child readiness: '+name)
    rows=[json.loads(v) for v in (root/'bus.jsonl').read_text().splitlines()]
    if len(rows)<2 or any(not isinstance(r,dict) or r.get('run_id')!=run for r in rows) \
            or rows[0].get('result')!='READY' or rows[-1].get('result')!='END' \
            or any(r.get('result')!='BUS_FRAME' for r in rows[1:-1]):
        raise ValueError('missing/invalid capture lifecycle')
    ready,end=rows[0],rows[-1];started=timestamp(ready);ended=timestamp(end)
    duration=ready.get('requested_duration_s')
    if ready.get('interface')!=interface or end.get('interface')!=interface \
            or ready.get('rx_overflow_tracking') is not True or end.get('status')!='COMPLETE' \
            or type(end.get('rx_overflow')) is not int or end['rx_overflow']!=0 \
            or type(duration) not in (float,int) or not 0<duration<=300 \
            or ended-started<round(duration*1e9):
        raise ValueError('incomplete capture or socket loss')
    before=ready.get('stats_before');after=end.get('stats_after')
    if not isinstance(before,dict) or not isinstance(after,dict) or any(
            type(before.get(k)) is not int or before[k]<0 or type(after.get(k)) is not int or after[k]!=before[k]
            for k in STATS):raise ValueError('unavailable/reset/increased interface error/drop counters')
    warmup=manifest.get('warmup_ns');count=manifest.get('windows')
    if type(warmup) is not int or not 0<=warmup<=60_000_000_000 or type(count) is not int or not 1<=count<=280:
        raise ValueError('invalid prespecified window bounds')
    first=started+warmup;last=first+count*POLICY['length_ns']
    if last>ended or last>started+round(duration*1e9):raise ValueError('not all requested windows complete')
    buckets=[{'window_id':i,'bms_frames':0,'auth_frames':0,'alerts':0,'attack_types':[]} for i in range(count)]
    normal_times={0x100:[],0x102:[]};previous=started;alerts_by_type={str(i):0 for i in range(1,5)}
    for row in rows[1:-1]:
        at=timestamp(row);cid=row.get('can_id');dlc=row.get('dlc')
        if not previous<=at<=ended or type(cid) is not int or not 0<=cid<=0x7ff \
                or type(dlc) is not int or not 0<=dlc<=8 or any(row.get(k) is not False for k in ('extended','remote','error')):
            raise ValueError('invalid/error frame or unordered capture')
        data=bytes.fromhex(row['data'])
        if len(data)!=dlc:raise ValueError('DLC/payload mismatch')
        previous=at
        if cid not in (0x100,0x101,0x102,0x103,0x200) or dlc!=8:
            raise ValueError('unexpected traffic in declared normal-only capture')
        if first<=at<last:
            bucket=buckets[(at-first)//POLICY['length_ns']]
            if cid in normal_times:
                normal_times[cid].append(at)
                bucket['bms_frames' if cid==0x100 else 'auth_frames']+=1
            if cid==0x200:
                kind=data[0]
                if kind>4:raise ValueError('invalid ICD AttackType')
                if kind:
                    bucket['alerts']+=1;alerts_by_type[str(kind)]+=1
                    if kind not in bucket['attack_types']:bucket['attack_types'].append(kind)
    if type(end.get('frames')) is not int or end['frames']!=len(rows)-2:
        raise ValueError('capture frame count mismatch')
    for times in normal_times.values():
        boundaries=[first,*times,last]
        if max(b-a for a,b in zip(boundaries,boundaries[1:]))>POLICY['max_gap_ns']:
            raise ValueError('normal input silence/loss; do not count it as true negative')
    if any(b['bms_frames']<8 or b['auth_frames']<8 for b in buckets):
        raise ValueError('normal window coverage below policy; preserve and recollect')
    fp=sum(b['alerts']>0 for b in buckets);fpr=fp/count;minimum=count>=100;target=minimum and fpr<=.05
    return {'schema':'normal-wire-fpr-result-v1','scope':'0x200-wire-normal-window',
            'status':('PASS' if target else 'FAIL') if minimum else 'INSUFFICIENT_WINDOWS',
            'run_id':run,'environment':manifest['environment'],'normal_windows':count,
            'fp_windows':fp,'tn_windows':count-fp,'fpr':fpr,'alerts_by_type':alerts_by_type,
            'minimum_100_windows_met':minimum,'observed_window_target_met':target,
            'physical_evidence_target_met':target and manifest['environment']=='physical-can',
            'official_acceptance':False,'window_policy':POLICY,'windows':buckets,
            'note':'0x200 is unauthenticated. Controlled normal fixture, supervised IDS process, not IF-only scores or pixel/UI FPR. Operator must verify normal-only provenance and physical representativeness before official acceptance.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:result=analyze(Path(args.input_dir))
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as error:
        result={'status':'INVALID','reason':str(error),'official_acceptance':False}
    try:
        with Path(args.output).open('x',encoding='utf-8') as out:json.dump(result,out,indent=2,allow_nan=False)
    except (OSError,ValueError) as error:
        print(json.dumps({'status':'INVALID','reason':str(error)}));return 2
    print(json.dumps({'status':result['status'],'output':args.output}))
    return 0 if result['status']=='PASS' else 2


if __name__=='__main__':raise SystemExit(main())
