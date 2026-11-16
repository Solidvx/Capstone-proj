"""Public provenance tests: fitted-state identity, input drift and runtime binding."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
import time

import pytest

from security.ids import startup_identity as identity
from security.ids.if_detector import IsolationForestDetector
from security.ids.runtime_detector import Config


def test_real_forest_identity_is_repeatable_and_tracks_fitted_state_and_threshold():
    vectors=[[float(i%11),float(i%7),float(i%3)] for i in range(120)]
    first=IsolationForestDetector(n_estimators=5).fit(vectors)
    second=IsolationForestDetector(n_estimators=5).fit(vectors)
    first.calibrate(vectors);second.calibrate(vectors)
    original=identity.model_digest(first)
    assert identity.model_digest(second)==original
    second.threshold+=.001
    assert identity.model_digest(second)!=original
    second.threshold=first.threshold
    second.model.estimators_[0].tree_.threshold[0]+=.01
    assert identity.model_digest(second)!=original
    second=deepcopy(first)
    if hasattr(second.model,'_decision_path_lengths'):
        second.model._decision_path_lengths[0][0]+=1
        assert identity.model_digest(second)!=original


def test_structured_tree_padding_does_not_make_identical_models_differ():
    import numpy as np
    # The fitted tree's structured node array may contain undefined padding.
    model=IsolationForestDetector(n_estimators=2).fit([[float(i),i%2] for i in range(30)])
    copy=deepcopy(model)
    assert identity.model_digest(copy)==identity.model_digest(model)
    assert all(not estimator.tree_.__getstate__()['nodes'].dtype.hasobject for estimator in model.model.estimators_)


def test_rules_identity_contains_no_private_paths_or_key_file_reads(tmp_path,monkeypatch):
    (tmp_path/'DO-NOT-READ.key').write_bytes(b'not-a-real-key')
    monkeypatch.setattr(identity,'source_digest',lambda:'a'*64)
    result=identity.build_identity(asdict(Config()),None,{}, {},'a'*64)
    assert result['schema']=='ids-startup-v1' and result['mode']=='rules-only'
    assert result['normal_inputs']=={} and result['trained_model_sha256'] is None
    assert result['dependencies']=={}
    assert str(tmp_path) not in json.dumps(result) and 'DO-NOT-READ' not in json.dumps(result)
    with pytest.raises(ValueError,match='only declared'):
        identity.snapshot_inputs({'key':tmp_path/'DO-NOT-READ.key'})


def test_changed_normal_file_or_source_during_training_refuses_identity(tmp_path,monkeypatch):
    path=tmp_path/'fit.jsonl';path.write_text('original dummy normal capture\n')
    inputs={'train_normal':path};before=identity.snapshot_inputs(inputs)
    assert before['train_normal']['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    assert str(path) not in json.dumps(before)
    monkeypatch.setattr(identity,'source_digest',lambda:'b'*64)
    with pytest.raises(ValueError,match='changed while training'):
        identity.build_identity(asdict(Config()),None,inputs,before,'a'*64)
    path.write_text('different dummy normal capture\n')
    with pytest.raises(ValueError,match='changed while training'):
        identity.build_identity(asdict(Config()),None,inputs,before,'b'*64)
    with pytest.raises(ValueError,match='bounded regular'):
        identity.file_digest(path,limit=1)


def test_actual_runtime_start_ready_and_ready_file_share_identity(tmp_path,monkeypatch):
    from security.ids import runtime
    class Transport:
        def __init__(self,*_):self.start_time=time.monotonic();self.clock_offset_ns=0;self.rx_dropped=0
        @property
        def idle_time(self):return time.monotonic()
        def receive(self):return None
        def close(self):pass
    monkeypatch.setattr(runtime,'OrderedSocketCan',Transport)
    key=tmp_path/'dummy.key';key.write_bytes(bytes(range(32)))
    events=tmp_path/'events.jsonl';ready=tmp_path/'ready.json'
    reader,writer=os.pipe();os.set_blocking(reader,False)
    try:
        assert runtime.main(['--interface','dummy','--protocol','session-v2','--session-context-fd',str(reader),
            '--secoc-key',str(key),'--rules-only','--duration','.005','--log',str(events),'--ready-file',str(ready)])==0
    finally:os.close(reader);os.close(writer)
    rows=[json.loads(line) for line in events.read_text().splitlines()]
    started=rows[0]['startup_identity'];record=next(row for row in rows if row.get('result')=='READY')
    assert started==record['startup_identity']==json.loads(ready.read_text())['startup_identity']
    assert started['mode']=='rules-only' and len(started['source_sha256'])==64
    assert str(key) not in json.dumps(started) and key.read_bytes().hex() not in json.dumps(started)
