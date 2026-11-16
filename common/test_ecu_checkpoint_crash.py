"""Real ECU periodic checkpoint survives SIGKILL; virtual CAN only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def read_state(path):
    data=path.read_bytes()
    header,digest,body=data.split(b'\n',2)
    if header!=b'CAPSTONE-CHECKPOINT-V1' or hashlib.sha256(body).hexdigest().encode()!=digest:
        raise ValueError('checkpoint is not complete')
    rows=body.decode().splitlines()
    return {'elapsed':float(rows[5]),'capacity':float(rows[2].split()[2]),
            'soc':float(rows[1].split()[1]),'risk':int(rows[3].split()[1])}


def wait_state(child,path,predicate):
    end=time.monotonic()+5
    while time.monotonic()<end:
        if child.poll() is not None:raise RuntimeError('ECU stopped unexpectedly')
        if path.exists():
            state=read_state(path)
            if predicate(state):return state
        time.sleep(.02)
    raise RuntimeError('checkpoint did not advance')


def stop(child):
    if child is None or child.poll() is not None:return
    child.terminate()
    try:child.wait(timeout=3)
    except subprocess.TimeoutExpired:child.kill();child.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ecu',required=True)
    parser.add_argument('--policy',required=True)
    parser.add_argument('--out-parent',type=Path,required=True)
    args=parser.parse_args()
    interface=os.environ.get('CAPSTONE_SESSION_TEST_INTERFACE','')
    if not interface:return 77
    if not interface.startswith('vcan') or not Path('/sys/devices/virtual/net',interface).is_dir():
        raise ValueError('existing virtual CAN only')
    args.out_parent.mkdir(parents=True,exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix='checkpoint-crash-',dir=args.out_parent))
    with tempfile.TemporaryDirectory(prefix='ecu-checkpoint-private-') as folder:
        private=Path(folder);key=private/'dummy.key';checkpoint=private/'state';soh=private/'soh.csv'
        key.write_bytes(bytes(range(32)));key.chmod(0o600)
        soh.write_text('elapsed_s,estimated_capacity_ah\n0,50\n0.3,45\n')
        base=[args.ecu,'--interface',interface,'--key',str(key),'--session-policy',args.policy,
              '--checkpoint',str(checkpoint),'--checkpoint-period-ms','100','--checkpoint-flush-ms','2000',
              '--checkpoint-max-age-ms','60000','--restart-wait-ms','200','--restart-retry-ms','50',
              '--restart-notice-attempts','3','--soh-profile',str(soh)]
        child=None
        try:
            with (output/'fresh.log').open('w') as log:
                child=subprocess.Popen(base+['--start-intent','fresh'],stdout=log,stderr=subprocess.STDOUT)
                before=wait_state(child,checkpoint,lambda state:state['elapsed']>=.5 and state['capacity']==45)
                child.kill();child.wait(timeout=3)
            before=read_state(checkpoint)
            with (output/'resume.log').open('w') as log:
                child=subprocess.Popen(base+['--start-intent','resume'],stdout=log,stderr=subprocess.STDOUT)
                after=wait_state(child,checkpoint,lambda state:state['elapsed']>=before['elapsed']+.3)
                assert after['capacity']==45 and after['risk']==before['risk'],(before,after)
                stop(child)
            assert 'Recovery: calculation and protection restored' in (output/'resume.log').read_text()
            # Stale snapshots do not become a new demo silently.
            os.utime(checkpoint,(time.time()-120,time.time()-120))
            rejected=subprocess.run(base+['--start-intent','resume'],capture_output=True,text=True,timeout=5)
            assert rejected.returncode==2 and 'checkpoint age rejected' in rejected.stderr,rejected.stderr
        finally:stop(child)
    result={'status':'PASS','scope':'real ECU vcan SIGKILL and explicit resume; not automatic crash retry',
            'before':before,'after':after,'stale_checkpoint_rejected':True,'key_retained':False}
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(result,output=str(output))))
    return 0


if __name__=='__main__':raise SystemExit(main())
