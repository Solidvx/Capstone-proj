import importlib.util
import json
from pathlib import Path
import sys
import os
import tempfile
import pytest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('owned_ids',ROOT/'adaptive_ecu/scripts/owned_ids.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def base(tmp_path):
    logs=tmp_path/'logs';logs.mkdir(mode=0o700)
    return {'python':sys.executable,'repository':str(ROOT),'log_directory':str(logs),
            'mode':'rules-only','frame_budget':2,'expiry_ms':1000}


def load(tmp_path,data):
    path=tmp_path/'settings.json';path.write_text(json.dumps(data));return module.load_settings(path)


def test_rules_mode_requires_explicit_limits_and_private_log_directory(tmp_path):
    data=base(tmp_path);assert load(tmp_path,data)==data
    data['frame_budget']=37
    with pytest.raises(ValueError,match='budget'):load(tmp_path,data)
    data['frame_budget']=2;Path(data['log_directory']).chmod(0o755)
    with pytest.raises(ValueError,match='private'):load(tmp_path,data)


def test_if_configuration_cannot_silently_degrade_to_rules(tmp_path):
    data=base(tmp_path);data['mode']='rules+if'
    with pytest.raises(ValueError,match='IF requires'):load(tmp_path,data)
    for field in ('train_normal','normal_manifest','calibrate_normal','calibration_manifest'):
        data[field]=str(tmp_path/field)
    assert load(tmp_path,data)['mode']=='rules+if'
    data['mode']='rules-only'
    with pytest.raises(ValueError,match='no rule fallback'):load(tmp_path,data)


def test_unknown_or_relative_configuration_is_rejected(tmp_path):
    data=base(tmp_path);data['unexpected']=True
    with pytest.raises(ValueError,match='fields'):load(tmp_path,data)
    del data['unexpected'];data['python']='python3'
    with pytest.raises(ValueError,match='absolute'):load(tmp_path,data)


def test_second_owned_pipe_failure_closes_first_and_runtime(tmp_path,monkeypatch):
    first=[]
    def create(_):
        if first:raise OSError('simulated FD exhaustion')
        result=os.pipe();first.extend(result);return result
    monkeypatch.setattr(module.os,'pipe2',create,raising=False)
    # Keep the separate Unix-socket path constraint out of this FD failure test.
    with tempfile.TemporaryDirectory(prefix='peer-',dir='/tmp') as parent:
        with pytest.raises(OSError,match='exhaustion'):module.OwnedIds(base(tmp_path),parent,'vcan0','public-dummy-key-path')
        assert not list(Path(parent).glob('ids-*'))
    for fd in first:
        with pytest.raises(OSError):os.fstat(fd)


def test_measurement_requires_explicit_boolean_and_defaults_unchanged(tmp_path):
    data=base(tmp_path)
    assert 'measure_resources' not in load(tmp_path,data)
    for value in (True,False):
        data['measure_resources']=value
        assert load(tmp_path,data)['measure_resources'] is value
    for value in (1,'true',None):
        data['measure_resources']=value
        with pytest.raises(ValueError,match='boolean'):load(tmp_path,data)
