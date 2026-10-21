"""Validate the attempt ledger before computing defence configuration rates."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import csv

from security.attack_simulator import ATTACKS


def summarize(root):
    manifest=json.loads((root/'manifest.json').read_text())
    if not isinstance(manifest,dict) or manifest.get('schema')!='ablation-v1' \
            or type(manifest.get('trials_per_cell')) is not int \
            or not 1<=manifest['trials_per_cell']<=100 \
            or manifest.get('expected_trials')!=12*manifest['trials_per_cell'] \
            or manifest.get('environment') not in ('vcan','physical-can'):
        raise ValueError('invalid matrix manifest')
    if hashlib.sha256((root/'settings.json').read_bytes()).hexdigest()!=manifest.get('settings_sha256'):
        raise ValueError('experiment settings hash mismatch')
    records=[json.loads(line) for line in (root/'attempts.jsonl').read_text().splitlines()]
    seen=set();groups={(config,attack):[] for config in (1,2,3) for attack in ATTACKS}
    hashes={}
    for row in records:
        key=(row['config'],row['attack_type'],row['trial'])
        if key in seen:raise ValueError('duplicate trial; attempts must not overwrite retries')
        if row['run_id']!=manifest['run_id'] or row['environment']!=manifest['environment'] \
                or (key[0],key[1]) not in groups or type(key[2]) is not int \
                or not 0<=key[2]<manifest['trials_per_cell']:
            raise ValueError('trial identity or environment mismatch')
        seen.add(key)
        trial_dir=root/f'C{key[0]}-{key[1]}-T{key[2]:03d}'
        if json.loads((trial_dir/'result.json').read_text())!=row:
            raise ValueError('trial result differs from attempt ledger')
        artifacts=row.get('artifact_sha256')
        if not isinstance(artifacts,dict) or not artifacts:
            raise ValueError('missing trial artifact hashes')
        for name,digest in artifacts.items():
            if not isinstance(name,str) or Path(name).name!=name or name in ('.','..') \
                    or hashlib.sha256((trial_dir/name).read_bytes()).hexdigest()!=digest:
                raise ValueError('invalid or changed trial artifact')
        if row['status'] not in ('VALID','INVALID'):raise ValueError('invalid trial status')
        if row['status']=='VALID':
            for name in ('blocked','attack_success','detected'):
                if type(row[name]) is not bool:raise ValueError('result booleans must be JSON booleans')
            latency=row['latency_s']
            if latency is not None and (type(latency) not in (float,int) or not math.isfinite(latency) or latency<0):
                raise ValueError('invalid detected latency')
            if (row['detected'] and latency is None) or (not row['detected'] and latency is not None):
                raise ValueError('missing or falsely zero-filled detection latency')
            if key[0] in (1,2) and row['detected']:raise ValueError('IDS OFF configuration claims detection')
            if key[0]==1 and row['blocked']:raise ValueError('unprotected configuration claims SecOC blocking')
            hashes.setdefault((key[1],key[2]),set()).add(row['input_sha256'])
        groups[key[:2]].append(row)
    result=[]
    for (config,attack),rows in groups.items():
        valid=[r for r in rows if r['status']=='VALID']
        total=len(valid)
        latencies=[r['latency_s'] for r in valid if r['latency_s'] is not None]
        item={'config':config,'attack_type':attack,'attempts':len(rows),'valid_trials':total,
              'invalid_trials':len(rows)-total,'not_run':manifest['trials_per_cell']-len(rows),
              'input_mismatch_trials':sum(len(hashes.get((attack,r['trial']),set()))>1 for r in valid),
              'undetected_trials':sum(not r['detected'] for r in valid) if config==3 else None,
              'deadline_exceeded':sum(v>3 for v in latencies),
              'avg_detected_latency_s':statistics.mean(latencies) if latencies else None,
              'max_detected_latency_s':max(latencies) if latencies else None}
        classified=[r for r in valid if type(r.get('expected_type_detected')) is bool] if config==3 else []
        item['type_evaluated_trials']=len(classified)
        item['expected_type_detected_count']=sum(r['expected_type_detected'] for r in classified)
        item['expected_type_detected_rate']=(item['expected_type_detected_count']/len(classified)
                                             if classified else None)
        published=[r for r in valid if type(r.get('ivi_expected_type_published')) is bool] if config==3 else []
        item['ivi_type_evaluated_trials']=len(published)
        item['ivi_expected_type_published_count']=sum(r['ivi_expected_type_published'] for r in published)
        item['ivi_expected_type_published_rate']=(item['ivi_expected_type_published_count']/len(published)
                                                  if published else None)
        item['first_alert_type_counts']={str(code):sum(r.get('first_alert_attack_code')==code for r in classified)
                                         for code in (None,1,2,3,4)}
        for name in ('attack_success','blocked','detected'):
            count=sum(r[name] for r in valid)
            item[name+'_count']=count
            item[name+'_rate']=count/total if total else None
        result.append(item)
    complete=len(seen)==manifest['expected_trials'] and all(
        r['invalid_trials']==0 and r['not_run']==0 and r['input_mismatch_trials']==0 for r in result)
    return {'environment':manifest['environment'],'matrix_complete':complete,
            'official_1200_complete':complete and manifest['trials_per_cell']==100 and manifest['environment']=='physical-can',
            'summary':result,'note':'Matrix completeness is not a security acceptance verdict; bus load/UI/FPR/ROC require their own evidence.'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--csv-output',help='optional 12-row summary CSV; ratios remain 0..1, null becomes blank')
    args=parser.parse_args(argv)
    try:
        result=summarize(Path(args.input_dir))
        if args.csv_output and Path(args.csv_output).resolve()==Path(args.output).resolve():
            raise ValueError('JSON and CSV must have distinct output paths')
        if args.csv_output and Path(args.csv_output).exists():raise ValueError('CSV output already exists')
        with Path(args.output).open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
        if args.csv_output:
            rows=[{'environment':result['environment'],**row} for row in result['summary']]
            with Path(args.csv_output).open('x',encoding='utf-8',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
                writer.writeheader();writer.writerows(rows)
        print(json.dumps(result,sort_keys=True))
        return 0 if result['matrix_complete'] else 2
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(json.dumps({'status':'INVALID','reason':str(error)}));return 2


if __name__=='__main__':raise SystemExit(main())
