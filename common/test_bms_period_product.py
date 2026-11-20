"""Raw BMS inter-arrival measurement from actual ECU/session-v2/Qt on vcan.

Read-only observer. All raw frames and failed/invalid intervals are preserved.
This does not authorize physical CAN injection, change VM time or prove ECU TX.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import select
import socket
import struct
import subprocess
import sys
import tempfile
import time

from test_session_ids_products import stop,wait_file

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tools.quality.bms_period import evaluate


def interface_drops(name):
    rows=json.loads(subprocess.check_output(['ip','-json','-details','-statistics','link','show','dev',name],text=True))
    if len(rows)!=1 or rows[0].get('linkinfo',{}).get('info_kind')!='vcan' or 'UP' not in rows[0]['flags']:
        raise ValueError('UP virtual CAN required')
    return rows[0]['stats64']['rx']['dropped']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('ecu','ivi','policy'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--out-parent',type=Path,required=True)
    args=parser.parse_args();interface=os.environ.get('CAPSTONE_SESSION_TEST_INTERFACE','')
    if not interface:return 77
    if not re.fullmatch('vcan[0-9]+',interface) or not Path('/sys/devices/virtual/net',interface).is_dir():
        raise ValueError('existing explicit virtual CAN required')
    initial_drops=interface_drops(interface)
    source_paths=(Path(__file__).resolve(),ROOT/'tools/quality/bms_period.py')
    source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    executables={name:Path(getattr(args,name)) for name in ('ecu','ivi')}
    executable_hashes={name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in executables.items()}
    policy_hash=hashlib.sha256(Path(args.policy).read_bytes()).hexdigest()
    args.out_parent.mkdir(parents=True,exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix='bms-period-',dir=args.out_parent))
    manifest=dict(schema='bms-period-capture-v1',environment='vcan',
        clock='kernel-realtime-mapped-to-local-monotonic-ns',boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        normal_attested=True,status='INCOMPLETE',rx_dropped=0,interface_rx_dropped=0,clock_mapping_max_change_ns=0)
    offset=time.monotonic_ns()-time.time_ns();last_drop=0;matched=0
    try:
        with tempfile.TemporaryDirectory(prefix='period-private-') as temporary,ExitStack() as cleanup:
            private=Path(temporary);key=private/'dummy.key';key.write_bytes(bytes(range(32)));key.chmod(0o600)
            runtime=private/'runtime';runtime.mkdir(mode=0o700);ready=private/'ready'
            bus=cleanup.enter_context(socket.socket(socket.AF_CAN,socket.SOCK_RAW,socket.CAN_RAW))
            bus.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1024*1024)
            bus.setsockopt(socket.SOL_SOCKET,40,1) # SO_RXQ_OVFL
            bus.setsockopt(socket.SOL_SOCKET,64,1) # SO_TIMESTAMPNS_NEW
            bus.setsockopt(socket.SOL_CAN_RAW,2,0x1fffffff) # CAN error frames, no TX
            bus.bind((interface,));bus.setblocking(False);manifest['start_ns']=time.monotonic_ns()
            ivi_stream=cleanup.enter_context((output/'ivi.log').open('w'))
            ivi=subprocess.Popen([args.ivi,'--interface',interface,'--protocol','session-v2','--secoc-key',str(key),
                '--session-policy',args.policy,'--run-id','VCAN-BMS-PERIOD','--ready-file',str(ready),
                '--observation-jsonl',str(output/'receiver.jsonl'),'--windowed','--demo-exit-ms','25000'],
                env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=str(runtime)),
                stdout=ivi_stream,stderr=subprocess.STDOUT)
            cleanup.callback(stop,ivi);wait_file(ready,[ivi])
            ecu_stream=cleanup.enter_context((output/'ecu.log').open('w'))
            ecu=subprocess.Popen([args.ecu,'--interface',interface,'--sensor-mode','constant','--protocol','session-v2',
                '--secoc','on','--key',str(key),'--session-policy',args.policy],stdout=ecu_stream,stderr=subprocess.STDOUT)
            cleanup.callback(stop,ecu);deadline=time.monotonic()+15
            with (output/'frames.jsonl').open('x') as stream:
                while matched<101:
                    if time.monotonic()>deadline or any(child.poll() is not None for child in (ecu,ivi)):
                        raise RuntimeError('ACTOR_EXIT_OR_CAPTURE_DEADLINE')
                    change=abs(time.monotonic_ns()-time.time_ns()-offset)
                    manifest['clock_mapping_max_change_ns']=max(change,manifest['clock_mapping_max_change_ns'])
                    if change>10_000_000:raise RuntimeError('CLOCK_MAPPING_CHANGED')
                    if not select.select([bus],[],[],.02)[0]:continue
                    raw,ancillary,flags,_=bus.recvmsg(72,128)
                    if len(raw)!=16 or flags&(socket.MSG_TRUNC|socket.MSG_CTRUNC):raise RuntimeError('TRUNCATED_CAPTURE')
                    stamps=[]
                    for level,kind,value in ancillary:
                        if level==socket.SOL_SOCKET and kind==64:stamps.append(value)
                        if level==socket.SOL_SOCKET and kind==40:
                            if len(value)!=4:raise RuntimeError('INVALID_DROP_MEASUREMENT')
                            current=struct.unpack('=I',value)[0]
                            manifest['rx_dropped']+=(current-last_drop)&0xffffffff;last_drop=current
                    if len(stamps)!=1 or len(stamps[0])!=16:raise RuntimeError('MISSING_KERNEL_TIMESTAMP')
                    seconds,nanos=struct.unpack('=qq',stamps[0])
                    if seconds<0 or not 0<=nanos<10**9:raise RuntimeError('INVALID_KERNEL_TIMESTAMP')
                    cid,dlc,data=struct.unpack('=IB3x8s',raw)
                    if dlc>8:raise RuntimeError('NON_CLASSICAL_FRAME')
                    row=dict(received_ns=seconds*10**9+nanos+offset,can_id=cid&0x1fffffff,
                        dlc=dlc,data=data[:dlc].hex(),extended=bool(cid&0x80000000),
                        remote=bool(cid&0x40000000),error=bool(cid&0x20000000))
                    stream.write(json.dumps(row)+'\n')
                    matched+=int(row['can_id']==0x100 and dlc==8 and not (row['extended'] or row['remote'] or row['error']))
            manifest['status']='COMPLETE'
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        manifest['status']='ERROR';manifest['error']=str(error)
    finally:
        manifest['end_ns']=time.monotonic_ns()
        final_change=abs(time.monotonic_ns()-time.time_ns()-offset)
        manifest['clock_mapping_max_change_ns']=max(final_change,manifest['clock_mapping_max_change_ns'])
        manifest['interface_rx_dropped']=interface_drops(interface)-initial_drops
        raw=output/'frames.jsonl'
        if not raw.exists():raw.touch(exist_ok=False)
        manifest['frames_sha256']=hashlib.sha256(raw.read_bytes()).hexdigest()
        (output/'capture.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if (source_hashes!={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths} or
            executable_hashes!={name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in executables.items()} or
            policy_hash!=hashlib.sha256(Path(args.policy).read_bytes()).hexdigest()):
        manifest['status']='ERROR';manifest['error']='SOURCE_OR_EXECUTABLE_CHANGED'
        (output/'capture.json').write_text(json.dumps(manifest,indent=2)+'\n')
    report=evaluate(output,output/'period-report.json')
    result=dict(status=report['status'],report=report,key_retained=False,
        source_sha256=source_hashes,executables_sha256=executable_hashes,policy_sha256=policy_hash,
        files_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir()) if p.is_file()})
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(result,output=str(output))))
    return {'PASS':0,'FAIL':1,'INVALID':2}[report['status']]


if __name__=='__main__':raise SystemExit(main())
