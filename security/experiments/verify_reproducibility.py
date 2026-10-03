"""REP-1=A: independent validated matrices, success-rate change <=5 percentage points."""
import argparse
import json
from pathlib import Path

from security.experiments.summarize_ablation import summarize


def compare(previous,current):
    if previous.resolve()==current.resolve():raise ValueError('two distinct runs required')
    summaries=[summarize(path) for path in (previous,current)]
    if not all(s['matrix_complete'] for s in summaries):raise ValueError('complete valid matrices required')
    manifests=[json.loads((path/'manifest.json').read_text()) for path in (previous,current)]
    left,right=manifests
    if left.get('run_id')==right.get('run_id'):raise ValueError('distinct run IDs required')
    for key in ('environment','trials_per_cell','fixture','configuration_variable','settings_sha256','tool_sha256','phases'):
        if key not in left or key not in right or left[key]!=right[key]:raise ValueError('comparison contract mismatch: '+key)
    inputs=[]
    for path in (previous,current):
        rows=[json.loads(v) for v in (path/'attempts.jsonl').read_text().splitlines()]
        inputs.append({(r['config'],r['attack_type'],r['trial']):(r['seed'],r['input_sha256']) for r in rows})
    if inputs[0]!=inputs[1]:raise ValueError('trial seeds/actual delivered input hashes differ')
    rows=[]
    for a,b in zip(summaries[0]['summary'],summaries[1]['summary']):
        if (a['config'],a['attack_type'])!=(b['config'],b['attack_type']):raise ValueError('matrix ordering mismatch')
        diff=abs(b['attack_success_rate']-a['attack_success_rate'])*100
        rows.append({'config':a['config'],'attack_type':a['attack_type'],
            'previous_success_percent':a['attack_success_rate']*100,
            'current_success_percent':b['attack_success_rate']*100,
            'difference_percentage_points':diff,'status':'PASS' if diff<=5+1e-12 else 'FAIL',
            'trials_per_run':a['valid_trials']})
    return {'schema':'ablation-reproducibility-v1','status':'PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',
        'environment':left['environment'],'previous_run':left['run_id'],'current_run':right['run_id'],
        'threshold_percentage_points':5,'official_100_trials_per_cell':left['trials_per_cell']==100,
        'rows':rows,'official_acceptance':False,
        'note':'REP-1 success-rate stability only; not security acceptance, statistical confidence, UI latency or physical bus-load proof.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous',required=True);parser.add_argument('--current',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    try:result=compare(Path(args.previous),Path(args.current))
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as error:
        result={'status':'INVALID','reason':str(error),'official_acceptance':False}
    try:
        with Path(args.output).open('x',encoding='utf-8') as out:json.dump(result,out,indent=2,allow_nan=False)
    except (OSError,ValueError) as error:
        print(json.dumps({'status':'INVALID','reason':str(error)}));return 2
    print(json.dumps({'status':result['status'],'output':args.output}));return 0 if result['status']=='PASS' else 2


if __name__=='__main__':raise SystemExit(main())
