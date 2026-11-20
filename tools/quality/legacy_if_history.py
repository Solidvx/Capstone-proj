"""Read-only endpoint attribution of preserved legacy/evidence-v2 C3 history.

Does not replay a detector, infer negative windows or calculate IF performance.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

from security.experiments.can_capture import sha256

FILES={'attacker.stderr','ids-console.stderr','observer_b.jsonl','observer_b.stderr','ids-console.jsonl',
    'observer_a.jsonl','ecu.stderr','ids-events.jsonl','ivi.stderr','attacker.jsonl','ecu.jsonl','ivi.jsonl',
    'ids-fetch.stderr','attempts.jsonl','observer_a.stderr'}


def require(condition,message):
    if not condition:raise ValueError(message)


def rows(path):
    with path.open() as stream:
        for line in stream:
            row=json.loads(line)
            require(isinstance(row,dict),'history record must be an object')
            yield row


def analyze(base):
    base=Path(base)
    report={'schema':'legacy360-if-history-v1','root':str(base),'scope':'Preserved legacy/evidence-v2 C3 output endpoints; no current model replay or physical rerun.',
        'clock_scope':'Original experiment designated Node A monotonic IDS/observer_a; no cross-host latency computed.',
        'groups':[],'not_established':['all IF inference windows/negative decisions','IF window contents/boundaries',
            'historical runtime/model fingerprint','binary detector marginal improvement','window FPR/recall','current session-v2 IF acceptance']}
    for attack in ('flooding','fuzzy','replay','spoofing'):
        root=base/('C3-'+attack)/'attempt-001';manifest=json.loads((root/'manifest.json').read_text())
        require(manifest.get('status')=='COMPLETE' and manifest.get('cleanup_confirmed') is True and
            manifest.get('config')==3 and manifest.get('ids_mode')=='rules+if','complete owned C3 history required')
        require(set(manifest.get('files_sha256',{}))==FILES,'history file inventory mismatch')
        for name,expected in manifest['files_sha256'].items():require(sha256(root/name)==expected,'history file hash mismatch: '+name)
        attempts=list(rows(root/'attempts.jsonl'))
        require([r.get('trial') for r in attempts]==list(range(1,31)) and all(
            r.get('trial_completed') is True and r.get('status')=='VALID' for r in attempts),'30 valid ordered historical trials required')
        phases=[r for r in rows(root/'observer_a.jsonl') if r.get('result')=='PHASE']
        require(len(phases)==120,'120 historical phase boundaries required')
        windows=[]
        for index in range(30):
            block=phases[index*4:(index+1)*4]
            require([r.get('phase') for r in block]==['baseline','attack','post','idle'] and
                all(r.get('run_id')==manifest['run_id'] for r in block),'owned ordered phase boundaries required')
            stamps=[r['t'] for r in block]
            require(all(type(t) in (int,float) and math.isfinite(t) and t>=0 for t in stamps) and
                all(a<b for a,b in zip(stamps,stamps[1:])) and (not windows or windows[-1][-1]<=stamps[0]),
                'invalid or overlapping historical phase time')
            windows.append(stamps)
        def locate(t):
            for trial,(baseline,exposure,post,end) in enumerate(windows,1):
                if baseline<=t<end:return trial,'baseline' if t<exposure else 'attack' if t<post else 'post'
            return None,'outside_trial'
        positive=[];rules_count=Counter();result_counts=Counter();starts=[];ready=[];models=0
        per_trial={str(i):{'if_positive_endpoints':[],'rule_attack_codes':[]} for i in range(1,31)}
        for row in rows(root/'ids-events.jsonl'):
            result_counts[row.get('result','?')]+=1
            if row.get('result')=='START':starts.append(row)
            if row.get('result')=='READY':ready.append(row)
            if row.get('result')=='MODEL_EVALUATION':models+=1
            if 'timestamp' not in row:continue
            t=row['timestamp'];require(type(t) in (int,float) and math.isfinite(t) and t>=0,'invalid history timestamp')
            trial,phase=locate(t)
            if row.get('reason')=='IF_ANOMALY':
                item={'timestamp':t,'endpoint_phase':phase,'trial':trial,'logged_score':row.get('anomaly_score'),
                    'score_unit':'not recorded in this historical row','attack_type':row.get('attack_type')}
                if trial:item['trial_bounds']=dict(zip(('baseline','attack','post','idle'),windows[trial-1]))
                positive.append(item)
                if trial:per_trial[str(trial)]['if_positive_endpoints'].append(item)
            elif row.get('attack_type') in (1,2,3,4):
                rules_count[phase]+=1
                if trial and phase=='attack':per_trial[str(trial)]['rule_attack_codes'].append(row['attack_type'])
        require(len(starts)==len(ready)==1 and starts[0].get('mode')=='rules+if' and
            starts[0].get('run_id')==ready[0].get('run_id')==manifest['run_id'] and
            ready[0].get('classification_version')=='evidence-v2','matching evidence-v2 START/READY required')
        for item in per_trial.values():item['rule_attack_codes']=sorted(set(item['rule_attack_codes']))
        report['groups'].append({'attack':attack,'run_id':manifest['run_id'],'trials':30,
            'classification_version':ready[0]['classification_version'],'mode':starts[0]['mode'],
            'calibration':starts[0].get('if_calibration'),'if_positive_endpoints':positive,
            'rule_typed_event_counts_by_endpoint_phase':dict(rules_count),'model_evaluation_records':models,
            'ids_result_counts':dict(result_counts),'trial_endpoints':per_trial,
            'original_manifest_sha256':sha256(root/'manifest.json'),'verified_files_sha256':manifest['files_sha256']})
    report['if_positive_endpoint_total']=sum(len(g['if_positive_endpoints']) for g in report['groups'])
    report['if_positive_attack_endpoint_total']=sum(e['endpoint_phase']=='attack' for g in report['groups'] for e in g['if_positive_endpoints'])
    report['verified_trials']=sum(g['trials'] for g in report['groups'])
    report['analysis_source_sha256']=sha256(__file__)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True,type=Path)
    args=parser.parse_args()
    try:report=analyze(args.root)
    except (OSError,ValueError,KeyError,TypeError) as error:parser.error(str(error))
    print(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':main()
