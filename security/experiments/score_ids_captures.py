"""Generate real sklearn IF scores from separate, explicitly labelled captures.

Nonoverlapping complete one-second windows are an offline comparison protocol,
not the variable scheduling of the live streaming detector. No pickle loading.
"""
import argparse
import hashlib
import importlib.metadata
import json
import math
import sys
from pathlib import Path

from security.capture_normal import validate_capture
from security.ids.runtime import train_model
from security.ids.runtime_detector import Observation
from security.ids.feature_extractor import extract, FEATURE_NAMES
from security.experiments.analyze_roc import SCOPE, analyze


def hash_file(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def read_frames(path,duration):
    if type(duration) not in (int,float) or not math.isfinite(duration) or not 1<=duration<=10000:
        raise ValueError('capture duration must be in [1,10000] seconds')
    frames=[];previous=-1
    for line in path.read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        if not isinstance(row,dict):raise ValueError('capture record must be an object')
        t=row['t'];cid=row['can_id'];data=bytes.fromhex(row['data']);dlc=row.get('dlc',len(data))
        flags=[row.get(n,False) for n in ('extended','remote','error')]
        if type(t) not in (float,int) or not math.isfinite(t) or not 0<=t<=duration or t<previous \
                or type(cid) is not int or not 0<=cid<=(0x1fffffff if flags[0] else 0x7ff) \
                or type(dlc) is not int or dlc!=len(data) or not 0<=dlc<=8 or any(type(v) is not bool for v in flags):
            raise ValueError('invalid capture frame/timestamp')
        frames.append(Observation(t,cid,data,dlc,*flags));previous=t
        if len(frames)>1_000_000:raise ValueError('bounded capture capacity exceeded')
    if not frames:raise ValueError('empty capture')
    return frames


def score_dataset(dataset_path,output):
    dataset=json.loads(dataset_path.read_text())
    if not isinstance(dataset,dict) or dataset.get('schema')!='ids-capture-evaluation-v1' \
            or dataset.get('environment') not in ('synthetic','vcan','physical-can'):
        raise ValueError('invalid capture dataset manifest')
    base=dataset_path.parent;training=dataset['training']
    train_path=(base/training['capture']).resolve();train_manifest=(base/training['manifest']).resolve()
    metadata=validate_capture(train_path,train_manifest)
    if metadata.get('environment')!=dataset['environment']:raise ValueError('training/capture environment mismatch')
    if not isinstance(metadata.get('run_id'),str) or not metadata['run_id']:raise ValueError('training run_id required')
    model=train_model(train_path,manifest_path=train_manifest)
    versions={'sklearn':importlib.metadata.version('scikit-learn'),
              'numpy':importlib.metadata.version('numpy'),'python':sys.version,
              'normal_sha256':hash_file(train_path),'normal_manifest_sha256':hash_file(train_manifest),
              'feature_names':FEATURE_NAMES,'model_params':model.model.get_params(),
              'fit_scope':'security.ids.runtime.train_model'}
    source_root=Path(__file__).resolve().parents[1]
    versions['source_sha256']={name:hash_file(source_root/name) for name in (
        'ids/runtime.py','ids/feature_extractor.py','ids/if_detector.py')}
    identity=hashlib.sha256(json.dumps(versions,sort_keys=True).encode()).hexdigest()
    manifest={'schema':'ids-window-evaluation-v1','scope':SCOPE,'model_id':identity,
              'environment':dataset['environment'],'training_run_ids':[metadata['run_id']],
              'training_capture_sha256s':[hash_file(train_path)],'model_definition':versions,
              'window_policy':'[n,n+1), length=slide=1s; complete windows only; empty windows retained; no alert stream',
              'scores_file':'window-scores.jsonl'}
    rows=[]
    captures=dataset['captures']
    if not isinstance(captures,list) or not captures:raise ValueError('capture descriptors required')
    for entry in captures:
        if not isinstance(entry,dict) or entry.get('environment')!=dataset['environment'] or entry.get('status')!='COMPLETE':
            raise ValueError('capture must explicitly be complete and in the dataset environment')
        path=(base/entry['path']).resolve();source=hash_file(path)
        if source!=entry['sha256']:raise ValueError('capture descriptor hash mismatch')
        frames=read_frames(path,entry['duration_s'])
        # Linear window assignment, bounded 4096 accepted frames/window like
        # runtime capacity. Do not let malformed/IDS-own frames train IF.
        buckets=[[] for _ in range(math.floor(entry['duration_s']))]
        for frame in frames:
            index=math.floor(frame.t)
            if index>=len(buckets):continue  # explicitly discard partial tail
            if not frame.extended and not frame.remote and not frame.error and frame.dlc==8 and frame.can_id!=0x200:
                buckets[index].append(frame)
                if len(buckets[index])>4096:raise ValueError('window exceeds 4096 frame capacity; do not silently truncate')
        for index,bucket in enumerate(buckets):
            rows.append({'run_id':entry['run_id'],'purpose':entry['purpose'],'label':entry['label'],
                'attack_type':entry['attack_type'],'source_sha256':source,'window_id':index,
                'complete':True,'frames':len(bucket),'score':model.anomaly(extract(bucket))})
            if len(rows)>20000:raise ValueError('bounded score capacity exceeded')
    result=analyze(rows,manifest)
    output.mkdir(parents=True,exist_ok=False)
    raw=''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows).encode()
    manifest['scores_sha256']=hashlib.sha256(raw).hexdigest()
    manifest['dataset_sha256']=hash_file(dataset_path)
    (output/'window-scores.jsonl').write_bytes(raw)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False),encoding='utf-8')
    (output/'roc-result.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',required=True)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args()
    try:
        result=score_dataset(Path(args.dataset),Path(args.output_dir))
        print(json.dumps({'status':result['status'],'output_dir':args.output_dir}));return 0 if result['threshold_candidate'] is not None else 2
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as error:
        print(json.dumps({'status':'INVALID','reason':str(error)}));return 2


if __name__=='__main__':raise SystemExit(main())
