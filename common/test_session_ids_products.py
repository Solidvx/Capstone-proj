"""Actual ECU + session IDS + Qt IVI over existing virtual CAN, rules-only.

Injection uses only bus bytes, never the temporary ECU/IVI/IDS test key. This
checks the product transport/classification path, not physical detection rates.
"""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import time

FRAME=struct.Struct('=IB3x8s')
ROOT=Path(__file__).resolve().parent.parent


def stop(child):
    if child.poll() is not None:return
    child.terminate()
    try:child.wait(timeout=3)
    except subprocess.TimeoutExpired:child.kill();child.wait()


def wait_file(path,children,timeout=5):
    end=time.monotonic()+timeout
    while not path.exists():
        if any(child.poll() is not None for child in children) or time.monotonic()>end:
            raise RuntimeError('product readiness failed')
        time.sleep(.02)


def records(path):
    rows=[]
    for line in path.read_text().splitlines():
        try:rows.append(json.loads(line))
        except json.JSONDecodeError:pass  # last live line may be incomplete
    return rows


def wait_mask(path,mask,after,children,timeout=10):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if any(child.poll() is not None for child in children):raise RuntimeError('product exited')
        rows=records(path)
        for row in rows[after:]:
            if row.get('result')=='AUTHENTICATED_DIAGNOSTIC' and row.get('kind')==7 and row.get('condition_mask')==mask and row.get('observation_ready'):
                return len(rows)
        time.sleep(.05)
    raise RuntimeError('authenticated IVI condition mask missing: '+str(mask))


def inject(bus,kind,captured):
    end=time.monotonic()+2
    index=0;sent=0
    while time.monotonic()<end:
        if kind=='flooding':items=[(0x080,bytes(8))];pause=.001
        elif kind=='fuzzy':items=[((0x050,0x060,0x070)[index%3],bytes(8))];pause=.05
        elif kind=='spoofing':items=[(0x100,bytes.fromhex('ffc80f3cffec4100'))];pause=.2
        else:items=captured;pause=.2
        for cid,payload in items:
            bus.send(FRAME.pack(cid,8,payload));sent+=1
        index+=1;time.sleep(pause)
    return sent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ecu',required=True);parser.add_argument('--ivi',required=True)
    parser.add_argument('--policy',required=True);parser.add_argument('--out-parent',type=Path,required=True)
    args=parser.parse_args()
    interface=os.environ.get('CAPSTONE_SESSION_TEST_INTERFACE','')
    if not interface:return 77
    if not interface.startswith('vcan') or not Path('/sys/devices/virtual/net',interface).is_dir():raise ValueError('existing vcan required')
    args.out_parent.mkdir(parents=True,exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix='session-ids-',dir=args.out_parent))
    with tempfile.TemporaryDirectory(prefix='session-ids-private-') as private, ExitStack() as cleanup:
        private=Path(private);key=private/'dummy.key';key.write_bytes(bytes(range(32)));key.chmod(0o600)
        runtime=private/'runtime';runtime.mkdir(mode=0o700)
        reader,writer=os.pipe2(os.O_NONBLOCK|os.O_CLOEXEC)
        cleanup.callback(os.close,reader);cleanup.callback(os.close,writer)
        ready=private/'ids-ready.json';ivi_ready=private/'ivi-ready.json';ipc=private/'ids.sock'
        observations=output/'ivi-observations.jsonl';ids_log=output/'ids.jsonl'
        ids_stream=cleanup.enter_context((output/'ids-process.log').open('w'))
        ids=subprocess.Popen([sys.executable,'-m','security.ids.runtime','--interface',interface,'--rules-only',
            '--protocol','session-v2','--session-context-fd',str(reader),'--secoc-key',str(key),
            '--log',str(ids_log),'--ready-file',str(ready),'--diagnostic-socket',str(ipc),'--duration','100'],
            pass_fds=(reader,),cwd=ROOT,stdout=ids_stream,stderr=subprocess.STDOUT)
        cleanup.callback(stop,ids);wait_file(ready,[ids])
        ivi_stream=cleanup.enter_context((output/'ivi.log').open('w'))
        ivi=subprocess.Popen([args.ivi,'--interface',interface,'--secoc-key',str(key),'--protocol','session-v2',
            '--session-policy',args.policy,'--ready-file',str(ivi_ready),'--observation-jsonl',str(observations),
            '--windowed','--demo-exit-ms','100000'],env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=str(runtime)),
            stdout=ivi_stream,stderr=subprocess.STDOUT)
        cleanup.callback(stop,ivi);wait_file(ivi_ready,[ids,ivi])
        ecu_stream=cleanup.enter_context((output/'ecu.log').open('w'))
        ecu=subprocess.Popen([args.ecu,'--interface',interface,'--key',str(key),'--session-policy',args.policy,
            '--ids-context-fd',str(writer),'--ids-socket',str(ipc),'--ids-pid',str(ids.pid),
            '--ids-frame-budget','2','--ids-expiry-ms','1000'],pass_fds=(writer,),stdout=ecu_stream,stderr=subprocess.STDOUT)
        cleanup.callback(stop,ecu);children=[ecu,ids,ivi]
        wait_mask(observations,0,0,children)
        # Capture raw/auth bytes from the bus; no key is used by the injector.
        bus=cleanup.enter_context(socket.socket(socket.PF_CAN,socket.SOCK_RAW,socket.CAN_RAW));bus.bind((interface,));bus.settimeout(2)
        raw=None;captured=None
        end=time.monotonic()+3
        while time.monotonic()<end:
            cid,dlc,payload=FRAME.unpack(bus.recv(16))
            if cid==0x100 and dlc==8:raw=payload
            if cid==0x102 and dlc==8 and raw is not None:captured=[(0x100,raw),(0x102,payload)];break
        if captured is None:raise RuntimeError('normal pair not observed')
        baseline=records(ids_log)
        if any(row.get('attack_type',0) for row in baseline):raise RuntimeError('normal startup falsely classified')
        checks=[]
        for kind,mask,label in [('fuzzy',1,'Fuzzy'),('spoofing',4,'Spoofing'),('replay',2,'Replay'),('flooding',8,'Flooding')]:
            start=len(records(observations));sent=inject(bus,kind,captured)
            wait_mask(observations,mask,start,children)
            model_rows=[row for row in records(observations)[start:] if row.get('result')=='VIEW_MODEL_PUBLICATION']
            if not any(row.get('security')==label for row in model_rows):raise RuntimeError('actual Qt label missing: '+label)
            checks.append({'attack':kind,'sent_frames':sent,'authenticated_mask':mask,'actual_view_model':label})
            wait_mask(observations,0,len(records(observations)),children,timeout=12)
            checks[-1]["quiet_end_confirmed"]=True
        stop(ecu);stop(ids);stop(ivi)
    summary={'status':'PASS','scope':'actual ECU, Python session-v2 rules IDS and Qt IVI over vcan',
             'normal_startup_typed_events':0,'checks':checks,
             'receive_epoch_resets':sum(row.get('result')=='RECEIVE_EPOCH_RESET' for row in records(ids_log)),'if_enabled':False,'physical_accuracy_measured':False,'key_retained':False}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(summary,output=str(output))))
    return 0


if __name__=='__main__':raise SystemExit(main())
