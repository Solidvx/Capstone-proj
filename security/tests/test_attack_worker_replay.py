"""Replay selection and full-window observation without retaining all frames."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from security.experiments import can_attack_worker as worker

ROOT=Path(__file__).resolve().parents[2]


def frame(cid,t,data):
    return SimpleNamespace(can_id=cid,t=t,data=data,error=False)


def test_first_valid_pair_and_plain_last_raw_are_preserved():
    rows=[frame(0x102,0,b'orphan--'),frame(0x100,.1,b'first---'),
          frame(0x102,.11,b'auth-one'),frame(0x100,.2,b'last----'),frame(0x102,.21,b'auth-two')]
    assert worker.replay_pair(iter(rows),True)==[(0x100,b'first---'),(0x102,b'auth-one')]
    assert worker.replay_pair(iter(rows),False)==[(0x100,b'last----')]


@pytest.mark.parametrize('auth_time',[-.01,.100001])
def test_pair_time_boundary_still_refuses_unpaired_frames(auth_time):
    with pytest.raises(RuntimeError,match='no observed replay pair'):
        worker.replay_pair(iter([frame(0x100,0,b'raw-----'),frame(0x102,auth_time,b'auth----')]),True)


def test_large_capture_completes_entire_window_with_bounded_traced_memory():
    # A separate interpreter keeps tracemalloc/time injection private to this test.
    # Actual inject(), not just its selector, must avoid a captured-frame list.
    program=r'''
import json,tracemalloc
from types import SimpleNamespace
from security.experiments import can_attack_worker as worker
class Bus:
    dropped=0
    def __init__(self):self.received=0;self.now=0.;self.sent=[]
    def receive(self,timeout):
        self.received+=1;self.now=self.received/100000
        if self.received>100000:return None
        cid=0x100 if self.received==1 else 0x102 if self.received==2 else 0x123
        return SimpleNamespace(can_id=cid,t=self.now,data=bytes([cid&255])*8,error=False),False
    def send(self,cid,data):self.sent.append((cid,data.hex()))
bus=Bus();worker.time=SimpleNamespace(monotonic=lambda:bus.now);worker.emit=lambda row:None
request={'attack':'replay','interface':'vcan0','rate':5,'duration':.000001,'trial':1,
         'seed':1,'secoc':True,'profile':'isolated-session-v1'}
tracemalloc.start()
worker.inject(bus,request,SimpleNamespace(poll=lambda:None),5,True)
_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
print(json.dumps({'synthetic_capture_frames':100000,'receive_calls':bus.received,
                  'sent':bus.sent,'traced_peak_bytes':peak}))
'''
    result=subprocess.run([sys.executable,'-c',program],cwd=ROOT,
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    observed=json.loads(result.stdout)
    assert observed['receive_calls']==100001,observed
    assert observed['sent']==[[0x100,'00'*8],[0x102,'02'*8]],observed
    assert observed['traced_peak_bytes']<1024*1024,observed


@pytest.mark.parametrize('failure,exception',[('disconnect',EOFError),('error',RuntimeError),('command',ValueError)])
def test_late_observation_failure_after_first_pair_still_prevents_any_send(monkeypatch,failure,exception):
    clock=[0.];sent=[];read=[0]
    bad=frame(0x123,.03,b'error---');bad.error=True
    rows=iter([frame(0x100,.01,b'raw-----'),frame(0x102,.02,b'auth----'),bad])
    def receive(_):
        clock[0]+=.01;read[0]+=1
        return next(rows),False
    def poll():
        if read[0]>=2:
            if failure=='disconnect':raise EOFError('controller disconnected during observation')
            if failure=='command':return {}
    monkeypatch.setattr(worker,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    monkeypatch.setattr(worker,'emit',lambda _:None)
    request={'attack':'replay','interface':'vcan0','rate':5,'duration':1,'trial':1,
             'seed':1,'secoc':True,'profile':'isolated-session-v1'}
    with pytest.raises(exception):
        worker.inject(SimpleNamespace(receive=receive,send=lambda *args:sent.append(args)),request,
            SimpleNamespace(poll=poll),5,True)
    assert sent==[]
