"""Sender-suspension acceptance must refuse before actor or socket startup."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('interface,acknowledged,message',[
    ('can0',True,'physical buses refused'),
    ('vcan0/../can0',True,'physical buses refused'),
    ('vcan0',False,'confirmation required'),
])
def test_rejects_before_any_actor_or_output(tmp_path,interface,acknowledged,message):
    output=tmp_path/'not-created'
    # Nonexistent executables make accidental actor launch an observable failure.
    command=[sys.executable,str(ROOT/'common/test_sender_scenarios_product.py'),
        '--ecu',str(tmp_path/'missing-product'),'--fixture',str(tmp_path/'missing-fixture'),
        '--ivi',str(tmp_path/'missing-ivi'),'--policy',str(tmp_path/'missing-policy'),
        '--out-parent',str(output)]
    if acknowledged:command.append('--i-am-on-a-test-bus')
    result=subprocess.run(command,env=dict(os.environ,CAPSTONE_SESSION_TEST_INTERFACE=interface),
        capture_output=True,text=True,timeout=3)
    assert result.returncode==2 and message in result.stderr
    assert not output.exists() and not result.stdout
