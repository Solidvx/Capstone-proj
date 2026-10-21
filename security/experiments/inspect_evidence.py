"""Read-only returned-log intake: integrity, period, Fail-safe and MAC recovery.

Wire presence is never treated as receiver acceptance. Receiver JSONL is required
for security checks. Optional --seal writes only new hash metadata; no key/CAN/SSH operations.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from ivi_platform.scripts.normalize_candump_period import LINE, timestamp_ns, parse_log
from ivi_platform.scripts.analyze_period import analyze as analyze_period
from security.experiments.summarize_ablation import summarize


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def intake(root,required):
    manifest=json.loads((root/'evidence-manifest.json').read_text())
    if not isinstance(manifest,dict) or manifest.get('schema')!='can-evidence-v1' \
            or not isinstance(manifest.get('run_id'),str) or not manifest['run_id'] \
            or manifest.get('environment') not in ('vcan','physical-can') \
            or manifest.get('protocol')!='ICD-v1.6' \
            or not isinstance(manifest.get('interface'),str) \
            or re.fullmatch(r'(?:vcan|can)[0-9]+',manifest['interface']) is None \
            or (manifest['environment']=='vcan')!=manifest['interface'].startswith('vcan'):
        raise ValueError('invalid evidence identity/environment/protocol')
    files=manifest.get('files')
    if not isinstance(files,dict) or not set(required)<=set(files):raise ValueError('required evidence files missing from manifest')
    for name,digest in files.items():
        if not isinstance(name,str) or Path(name).name!=name or name in ('.','..'):
            raise ValueError('artifact paths must be plain filenames')
        path=root/name
        if path.is_symlink() or not path.is_file() or sha(path)!=digest:
            raise ValueError(f'missing/changed/unsafe artifact: {name}')
    return manifest


def wire_pairs(path,interface,original,auth):
    parse_log(path,interface)  # strict DLC/frame syntax/whole-capture time validation
    pairs=[];pending=None;bms_auth_count=0;bms_pending=None
    for line in path.read_text().splitlines():
        if not line.strip():continue
        match=LINE.fullmatch(line.strip());cid=int(match['can_id'],16)
        at=timestamp_ns(match['timestamp']);data=bytes.fromhex(match['data'])
        if cid==0x100:bms_pending=(at,data)
        if cid==0x102:
            if len(data)==8 and bms_pending is not None and len(bms_pending[1])==8 and 0<=at-bms_pending[0]<100_000_000:
                bms_auth_count+=1
            bms_pending=None
        if cid==original:
            if len(data)!=8:raise ValueError('original DLC must be 8')
            pending=(at,data)
        elif cid==auth:
            if len(data)!=8 or pending is None or not 0<=at-pending[0]<100_000_000:
                raise ValueError('orphan, late or damaged authentication pair')
            pairs.append({'at_ns':at,'raw':pending[1].hex(),'auth':data.hex(),
                          'counter':int.from_bytes(data[4:],'big'),'bms_auth_count':bms_auth_count})
            pending=None
    return pairs


def receiver_rows(root,manifest,cid):
    records=[json.loads(line) for line in (root/'receiver.jsonl').read_text().splitlines()]
    result=[]
    for row in records:
        if not isinstance(row,dict):raise ValueError('receiver record must be an object')
        if row.get('result')=='FRAME' and row.get('can_id')==cid:
            if row.get('run_id')!=manifest['run_id'] or row.get('secoc_on') is not True \
                    or type(row.get('process_result')) is not int or row['process_result'] not in (0,1,2,3):
                raise ValueError('receiver run/mode/result mismatch')
            result.append(row)
    return result


def match_rows(pairs,rows):
    matched=[];position=0
    for row in rows:
        found=next((i for i in range(position,len(pairs)) if pairs[i]['auth']==row.get('data') and
                    pairs[i]['raw']==row.get('source_data')),None)
        if found is None:raise ValueError('receiver result has no ordered matching wire pair')
        matched.append((pairs[found],row));position=found+1
    return matched


def inspect(root,mode):
    if mode=='ablation':
        result=summarize(root)
        return {'status':'COMPLETE' if result['matrix_complete'] else 'INCOMPLETE','kind':mode,'result':result}
    required=('candump.log','period.csv','period.manifest.json') if mode=='period' else ('candump.log','receiver.jsonl')
    manifest=intake(root,required)
    if mode=='period':
        period=json.loads((root/'period.manifest.json').read_text())
        if not isinstance(period,dict) or period.get('run_id')!=manifest['run_id'] \
                or period.get('interface')!=manifest['interface'] or period.get('source_sha256')!=sha(root/'candump.log'):
            raise ValueError('normalized period source/identity mismatch')
        result=analyze_period(root/'period.csv',root/'period.manifest.json')
        return {'kind':mode,'status':result['status'],'run_id':manifest['run_id'],'environment':manifest['environment'],'result':result}
    original,auth=(0x101,0x103) if mode=='failsafe' else (0x100,0x102)
    pairs=wire_pairs(root/'candump.log',manifest['interface'],original,auth)
    rows=receiver_rows(root,manifest,auth)
    matched=match_rows(pairs,rows)
    if mode=='failsafe':
        accepted=[item for item in matched if item[1]['process_result']==2]
        if len(accepted)<2:raise ValueError('two accepted Fail-safe events required; wire-only evidence is insufficient')
        first,second=[item[0] for item in accepted[:2]]
        gap=(second['at_ns']-first['at_ns'])/1e9
        delta=(second['counter']-first['counter'])&0xffffffff
        between=second['bms_auth_count']-first['bms_auth_count']
        states=[list(bytes.fromhex(item['raw'])[:2]) for item in (first,second)]
        if gap<=10 or between<=100 or delta!=1 or states!=[[0,1],[1,2]]:
            return {'kind':mode,'status':'FAIL','reason':'long-gap WARNING→CRITICAL independent counter conditions not met',
                    'gap_s':gap,'bms_auth_between':between,'failsafe_counter_delta':delta,'states':states}
        result={'gap_s':gap,'bms_auth_between':between,'failsafe_counters':[first['counter'],second['counter']],
                'states':states,'receiver_accepted':2}
    else:
        if len(matched)!=3:raise ValueError('isolated tamper fixture must have exactly three receiver auth results')
        wire=[item[0] for item in matched];receiver=[item[1] for item in matched]
        if [item['process_result'] for item in receiver]!=[2,3,2] \
                or [item.get('soc') for item in receiver]!=[75,75,70] \
                or [bytes.fromhex(item['raw'])[0] for item in wire]!=[150,200,140] \
                or 'reason=MAC_FAIL' not in receiver[1].get('message','') \
                or (wire[1]['counter']-wire[0]['counter'])&0xffffffff!=1 \
                or wire[1]['counter']!=wire[2]['counter']:
            return {'kind':mode,'status':'FAIL','reason':'baseline75→MAC_FAIL/last-good75→same-counter recovery70 conditions not met'}
        result={'baseline_soc':75,'tampered_soc_not_published':100,'last_good_preserved':75,
                'recovery_soc':70,'recovery_counter':wire[2]['counter'],'mac_failures':1}
    return {'kind':mode,'status':'CONFIRMED','run_id':manifest['run_id'],'environment':manifest['environment'],
            'result':result,'note':'Wire and Service publication confirmed, not pixel presentation/UI latency or complete security acceptance.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',required=True)
    parser.add_argument('--mode',choices=('period','failsafe','tamper','ablation'),required=True)
    parser.add_argument('--output-dir')
    parser.add_argument('--seal',action='store_true',help='create new evidence-manifest.json after capture; no result inferred')
    parser.add_argument('--run-id')
    parser.add_argument('--environment',choices=('vcan','physical-can'))
    parser.add_argument('--interface',default='can0')
    args=parser.parse_args()
    if args.seal:
        if args.mode=='ablation' or not args.run_id or not args.environment:
            parser.error('seal requires period/failsafe/tamper, run-id and environment')
        if re.fullmatch(r'(?:vcan|can)[0-9]+',args.interface) is None or \
                (args.environment=='vcan')!=args.interface.startswith('vcan'):
            parser.error('interface must match the evidence environment')
        required=('candump.log','period.csv','period.manifest.json') if args.mode=='period' else ('candump.log','receiver.jsonl')
        root=Path(args.input_dir)
        try:
            files={}
            for name in required:
                path=root/name
                if path.is_symlink() or not path.is_file():raise ValueError('required regular artifact missing')
                files[name]=sha(path)
            manifest={'schema':'can-evidence-v1','run_id':args.run_id,'environment':args.environment,
                      'interface':args.interface,'protocol':'ICD-v1.6','files':files,
                      'note':'Integrity since seal, not cryptographic proof of capture provenance. Preserve original source logs.'}
            with (root/'evidence-manifest.json').open('x',encoding='utf-8') as output:json.dump(manifest,output,indent=2)
            print(json.dumps({'status':'SEALED','files':len(files)}));return 0
        except (OSError,ValueError,TypeError) as error:
            print(json.dumps({'status':'INVALID','reason':str(error)}));return 2
    if not args.output_dir:parser.error('validation requires --output-dir')
    try:result=inspect(Path(args.input_dir),args.mode)
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as error:
        result={'kind':args.mode,'status':'INVALID','reason':str(error)}
    try:
        output=Path(args.output_dir);output.mkdir(parents=True,exist_ok=False)
        (output/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
        text=f"# CAN evidence intake\n\n| Item | Result |\n|---|---|\n| Mode | {args.mode} |\n| Status | {result['status']} |\n\nSee result.json for source-linked diagnostics. No live Pi access was performed.\n"
        (output/'report.md').write_text(text,encoding='utf-8')
        print(json.dumps({'status':result['status'],'output_dir':args.output_dir}))
        return 0 if result['status'] in ('PASS','CONFIRMED','COMPLETE') else 2
    except OSError as error:
        print(json.dumps({'status':'INVALID','reason':str(error)}));return 2


if __name__=='__main__':raise SystemExit(main())
