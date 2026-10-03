"""Leakage-checked IF window ROC. Not live alert or trial detection acceptance."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from collections import defaultdict

from security.attack_simulator import ATTACKS

SCOPE='offline-if-1s-nonoverlap-v1'


def digest(value):
    return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def metrics(rows,threshold):
    counts={'tp':0,'fp':0,'tn':0,'fn':0}
    per={name:{'detected':0,'windows':0,'tpr':None} for name in ATTACKS}
    for row in rows:
        positive=row['score']>threshold
        counts[('tp' if positive else 'fn') if row['label'] else ('fp' if positive else 'tn')]+=1
        if row['label']:
            item=per[row['attack_type']];item['windows']+=1;item['detected']+=positive
    for item in per.values():
        if item['windows']:item['tpr']=item['detected']/item['windows']
    normal=counts['fp']+counts['tn'];attack=counts['tp']+counts['fn']
    tp,fp,tn,fn=(counts[k] for k in ('tp','fp','tn','fn'))
    ratio=lambda a,b:a/b if b else None
    mcc_den=(tp+fp)*(tp+fn)*(tn+fp)*(tn+fn)
    return {**counts,'normal_windows':normal,'attack_windows':attack,
            'fpr':counts['fp']/normal if normal else None,
            'tpr':counts['tp']/attack if attack else None,'per_attack':per,
            'precision':ratio(tp,tp+fp),'recall':ratio(tp,tp+fn),
            'fnr':ratio(fn,attack),'tnr':ratio(tn,normal),'f1':ratio(2*tp,2*tp+fp+fn),
            'balanced_accuracy':(tp/attack+tn/normal)/2 if attack and normal else None,
            'mcc':(tp*tn-fp*fn)/math.sqrt(mcc_den) if mcc_den else None}


def roc(rows):
    if not any(r['label']==0 for r in rows) or not any(r['label']==1 for r in rows):
        raise ValueError('ROC requires explicit normal and attack windows')
    bins=defaultdict(list)
    for row in rows:bins[row['score']].append(row)
    scores=sorted(bins,reverse=True)
    normal=sum(r['label']==0 for r in rows);attack=len(rows)-normal
    totals={name:sum(r['attack_type']==name for r in rows) for name in ATTACKS}
    hits={name:0 for name in ATTACKS};fp=tp=0;points=[]
    def point(threshold):
        return {'threshold':threshold,'fpr':fp/normal,'tpr':tp/attack,
                'per_attack':{name:hits[name]/totals[name] if totals[name] else None for name in ATTACKS}}
    for score in scores:
        points.append(point(score))  # strict > excludes this tied score group
        for row in bins[score]:
            if row['label']:tp+=1;hits[row['attack_type']]+=1
            else:fp+=1
    points.append(point(math.nextafter(scores[-1],-math.inf)))
    area=sum((b['fpr']-a['fpr'])*(a['tpr']+b['tpr'])/2 for a,b in zip(points,points[1:]))
    return points,area


def validate_rows(rows,manifest):
    if not isinstance(manifest,dict) or manifest.get('schema')!='ids-window-evaluation-v1' \
            or manifest.get('scope')!=SCOPE or manifest.get('environment') not in ('synthetic','vcan','physical-can') \
            or not digest(manifest.get('model_id')):
        raise ValueError('invalid window evaluation manifest')
    train_ids=manifest.get('training_run_ids');train_hashes=manifest.get('training_capture_sha256s')
    if not isinstance(train_ids,list) or not train_ids or any(not isinstance(v,str) or not v for v in train_ids) \
            or not isinstance(train_hashes,list) or not train_hashes or any(not digest(v) for v in train_hashes):
        raise ValueError('explicit training run IDs and capture hashes required')
    if not isinstance(rows,list) or len(rows)>20000:raise ValueError('window dataset capacity exceeded')
    seen=set();runs={};hashes={};indices_by_run=defaultdict(list);purposes={'calibration':[],'evaluation':[]}
    for row in rows:
        if not isinstance(row,dict):raise ValueError('window must be an object')
        purpose=row.get('purpose');run=row.get('run_id');source=row.get('source_sha256')
        if purpose not in purposes or not isinstance(run,str) or not run or run in train_ids \
                or not digest(source) or source in train_hashes:
            raise ValueError('invalid identity or training/evaluation leakage')
        if runs.get(run,(purpose,source))!=(purpose,source) or hashes.get(source,run)!=run:
            raise ValueError('capture/run reused across splits or duplicated under another name')
        runs[run]=(purpose,source);hashes[source]=run
        window=row.get('window_id');score=row.get('score');label=row.get('label')
        if type(window) is not int or window<0 or (run,window) in seen or row.get('complete') is not True \
                or type(score) not in (int,float) or not math.isfinite(score) or abs(score)>1e6 \
                or type(label) is not int or label not in (0,1):
            raise ValueError('duplicate, incomplete or invalid scored window')
        if row.get('attack_type') not in (ATTACKS if label else ('',)):
            raise ValueError('ground truth attack type is required; do not infer it from alerts')
        seen.add((run,window));indices_by_run[run].append(window);purposes[purpose].append(row)
    if not all(purposes.values()):raise ValueError('separate calibration and evaluation required')
    for run in runs:
        indices=sorted(indices_by_run[run])
        if indices!=list(range(len(indices))):raise ValueError('missing window IDs')
    return purposes


def analyze(rows,manifest,max_fpr=.05,min_tpr=.9):
    if not 0<=max_fpr<=1 or not 0<=min_tpr<=1:raise ValueError('invalid rate bounds')
    splits=validate_rows(rows,manifest)
    points,cal_auc=roc(splits['calibration'])
    evaluation_points,eval_auc=roc(splits['evaluation'])
    feasible=[]
    for point in points:
        if point['fpr']<=max_fpr and all(v is not None and v>=min_tpr for v in point['per_attack'].values()):
            feasible.append(point['threshold'])
    threshold=max(feasible) if feasible else None
    evaluation=metrics(splits['evaluation'],threshold) if threshold is not None else None
    return {'schema':'ids-roc-result-v1','scope':SCOPE,'environment':manifest['environment'],
            'model_id':manifest['model_id'],'status':'CANDIDATE_SELECTED' if threshold is not None else 'NO_FEASIBLE_THRESHOLD',
            'decision':'score > threshold','selection':'highest feasible threshold; calibration only; every four attack types constrained',
            'threshold_candidate':threshold,'bounds':{'max_fpr':max_fpr,'min_attack_tpr':min_tpr},
            'calibration':metrics(splits['calibration'],threshold) if threshold is not None else None,
            'calibration_auc':cal_auc,'calibration_roc':points,
            'evaluation':evaluation,'evaluation_auc':eval_auc,'evaluation_roc':evaluation_points,
            'normal_100_window_minimum_met':sum(r['label']==0 for r in splits['evaluation'])>=100,
            'independent_window_targets_met':bool(evaluation and evaluation['normal_windows']>=100 and
                evaluation['fpr']<=max_fpr and all(v['tpr'] is not None and v['tpr']>=min_tpr for v in evaluation['per_attack'].values())),
            'official_trial_acceptance':False,
            'note':'Offline IF window comparison only. No live 0x200, SecOC blocking, UI latency or trial rate claim. Candidate is not automatically applied to runtime.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:
        path=Path(args.manifest);manifest=json.loads(path.read_text())
        if not isinstance(manifest,dict):raise ValueError('manifest must be an object')
        source=(path.parent/manifest['scores_file']).resolve();raw=source.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=manifest.get('scores_sha256'):raise ValueError('score file hash mismatch')
        result=analyze([json.loads(line) for line in raw.decode('utf-8').splitlines()],manifest)
        with Path(args.output).open('x',encoding='utf-8') as output:json.dump(result,output,indent=2,allow_nan=False)
        print(json.dumps({'status':result['status'],'output':args.output}));return 0 if result['threshold_candidate'] is not None else 2
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(json.dumps({'status':'INVALID','reason':str(error)}));return 2


if __name__=='__main__':raise SystemExit(main())
