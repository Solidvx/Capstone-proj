"""Public startup fingerprints for reproducible IDS runs, never key material.

These are local file/model identities, not remote attestation. Snapshot declared
normal inputs before training and compare again afterwards; do not fingerprint
the key, runtime context, private settings file or arbitrary CLI arguments.
"""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import stat
import sys


def file_digest(path, limit=512*1024*1024):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size>limit:
            raise ValueError('IDS identity requires a bounded regular file')
        size=0
        while True:
            block=stream.read(65536)
            if not block:break
            size+=len(block)
            if size>limit:raise ValueError('IDS identity file exceeds bound')
            digest.update(block)
        after=os.fstat(stream.fileno())
        if (size!=before.st_size or
            (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=
            (after.st_size,after.st_mtime_ns,after.st_ctime_ns)):
            raise ValueError('IDS identity file changed during read')
    return {'sha256':digest.hexdigest(),'bytes':size}


def snapshot_inputs(inputs):
    allowed={'train_normal','normal_manifest','calibrate_normal','calibration_manifest'}
    if set(inputs)-allowed:raise ValueError('only declared normal captures/manifests may be fingerprinted')
    return {name:file_digest(path) for name,path in sorted(inputs.items()) if path is not None}


def source_digest():
    root=Path(__file__).resolve().parents[1]
    files={path.relative_to(root).as_posix():file_digest(path)
           for path in sorted(root.rglob('*.py')) if 'tests' not in path.relative_to(root).parts}
    return hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def model_digest(detector):
    """Fingerprint actual fitted trees/scaling/threshold; no pickle serialization.

    Structured tree arrays are hashed field by field to exclude uninitialized
    padding bytes. Keep dtype/shape and fitted feature subsets in the digest.
    """
    import numpy as np
    digest=hashlib.sha256()
    def scalar(value):
        raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        digest.update(len(raw).to_bytes(8,'big'));digest.update(raw)
    def array(value):
        value=np.asarray(value)
        scalar({'shape':list(value.shape),'dtype':value.dtype.descr if value.dtype.names else value.dtype.str})
        if value.dtype.names:
            for name in value.dtype.names:scalar(name);array(value[name])
        else:
            if value.dtype.hasobject:raise ValueError('object arrays cannot identify an IF model')
            raw=np.ascontiguousarray(value).tobytes()
            digest.update(len(raw).to_bytes(8,'big'));digest.update(raw)
    forest=detector.model
    scalar({'schema':'isolation-forest-state-v1','params':forest.get_params(deep=False),
        'threshold':float(detector.threshold),'calibration':detector.calibration,
        'lo':float(detector._lo),'hi':float(detector._hi),'offset':float(forest.offset_),
        'max_samples':int(forest.max_samples_),'n_features':int(forest.n_features_in_),
        'estimators':len(forest.estimators_)})
    for estimator,features in zip(forest.estimators_,forest.estimators_features_):
        array(features)
        state=estimator.tree_.__getstate__()
        for name in sorted(state):
            scalar(name)
            if isinstance(state[name],np.ndarray):array(state[name])
            else:scalar(state[name])
    # Recent sklearn versions cache these arrays and use them during scoring.
    for name in ('_average_path_length_per_tree','_decision_path_lengths'):
        values=getattr(forest,name,None);scalar({'cache':name,'present':values is not None})
        if values is not None:
            scalar(len(values))
            for value in values:array(value)
    return digest.hexdigest()


def build_identity(config,model,inputs,before,source_before):
    if snapshot_inputs(inputs)!=before or source_digest()!=source_before:
        raise ValueError('IDS source/normal inputs changed while training')
    dependencies={}
    if model is not None:
        for name in ('numpy','scipy','scikit-learn'):dependencies[name]=importlib.metadata.version(name)
    return {'schema':'ids-startup-v1','python':platform.python_version(),
        'interpreter':file_digest(sys.executable),'source_sha256':source_before,
        'config':config,'mode':'rules+if' if model is not None else 'rules-only',
        'normal_inputs':before,'dependencies':dependencies,
        'trained_model_sha256':model_digest(model) if model is not None else None}
