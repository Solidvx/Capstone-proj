"""Real worker observes/replays bus bytes; actual session-v2 IVI rejects them.

Supplemental local vcan acceptance, not a physical campaign or attack rate.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from test_session_ids_products import records,stop,wait_file
from test_sender_scenarios_product import Witness
from security.experiments.can_capture import CaptureSocket,inspect_interface


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('ecu','ivi','policy'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--out-parent',type=Path,required=True)
    parser.add_argument('--i-am-on-a-test-bus',action='store_true')
    args=parser.parse_args();interface=os.environ.get('CAPSTONE_SESSION_TEST_INTERFACE','')
    if (not args.i_am_on_a_test_bus or not interface.startswith('vcan') or
        not Path('/sys/devices/virtual/net',interface).is_dir()):
        parser.error('explicit existing vcan and confirmation required; physical buses refused')
    inspect_interface(interface,'vcan')
    args.out_parent.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='keyless-replay-',dir=args.out_parent))
    report={'scope':'Actual local worker/ECU/Qt over existing vcan, no physical campaign/IF claims','status':'INCOMPLETE'}
    with tempfile.TemporaryDirectory(prefix='replay-private-') as temporary,ExitStack() as cleanup:
        private=Path(temporary);key=private/'dummy.key';key.write_bytes(bytes(range(32)));key.chmod(0o600)
        runtime=private/'runtime';runtime.mkdir(mode=0o700)
        bus=CaptureSocket(interface);cleanup.callback(bus.close)
        if bus.receive(.1):raise RuntimeError('test bus not quiet before actors')
        def launch(command,log,**options):
            stream=cleanup.enter_context((out/log).open('x'))
            child=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,**options)
            cleanup.callback(stop,child);return child
        observations=out/'ivi.jsonl'
        ivi=launch([args.ivi,'--interface',interface,'--protocol','session-v2','--secoc-key',str(key),
            '--session-policy',args.policy,'--ready-file',str(private/'ivi.ready'),
            '--observation-jsonl',str(observations),'--windowed','--demo-exit-ms','20000'],'ivi.log',
            env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=str(runtime)))
        wait_file(private/'ivi.ready',[ivi])
        ecu=launch([args.ecu,'--interface',interface,'--key',str(key),'--session-policy',args.policy],'ecu.log')
        worker_command=[sys.executable,'-u','-m','security.experiments.can_attack_worker',
            '--interface',interface,'--environment','vcan','--duration','10','--run-id','STREAM-REPLAY',
            '--i-am-on-a-test-bus']
        assert not any(flag in worker_command for flag in ('--key','--secoc-key'))
        child=launch(worker_command,'worker.jsonl',cwd=ROOT,stdin=subprocess.PIPE)
        frames=cleanup.enter_context((out/'frames.jsonl').open('x'))
        witness=Witness(bus,frames,[ecu,ivi,child])
        published=lambda:[r for r in records(observations) if r.get('result')=='SESSION_PUBLICATION']
        witness.until(lambda:len(published())>=3 and any(r.get('result')=='READY' for r in records(out/'worker.jsonl')))
        baseline=len(published())
        request={'trial':1,'attack':'replay','rate':5,'duration':.4,'seed':101001,
            'interface':interface,'secoc':True,'profile':'isolated-session-v1'}
        started=time.monotonic();child.stdin.write((json.dumps(request)+'\n').encode());child.stdin.flush()
        witness.until(lambda:any(r.get('result')=='ATTACK_DONE' for r in records(out/'worker.jsonl')),timeout=5)
        worker_rows=records(out/'worker.jsonl')
        source=next(r for r in worker_rows if r.get('result')=='REPLAY_SOURCE')
        tx=[r for r in worker_rows if r.get('result')=='TX'];done=next(r for r in worker_rows if r.get('result')=='ATTACK_DONE')
        assert source['authenticated'] is False # Observed bytes, not a MAC verifier.
        pair=[(r['can_id'],r['data']) for r in source['frames']]
        assert [cid for cid,_ in pair]==[0x100,0x102]
        assert len(tx)>=2 and len(tx)%2==0 and done['sent']==len(tx) and done['tx_errors']==0
        assert [(r['can_id'],r['data']) for r in tx]==pair*(len(tx)//2)
        assert time.monotonic()-started>=1 # Entire original capture window was consumed.
        def matching_rejections():
            result=[]
            for row in records(observations):
                if row.get('result')!='LOCAL_REJECTION_RECORD':continue
                body=bytes.fromhex(row['body_hex'])
                if (len(body)==80 and body[32:35]==bytes((7,1,1)) and body[36]==2 and
                    body[64:72].hex()==pair[0][1] and body[72:80].hex()==pair[1][1]):result.append(body)
            return result
        witness.until(lambda:bool(matching_rejections()) and len(published())>=baseline+3)
        # One original auth plus repeated identical worker auths on a controlled
        # sole-sender/worker bus. Not general attacker attribution by payload.
        auth_observed=sum(r['can_id']==0x102 and r['data']==pair[1][1] for r in witness.rows)
        assert auth_observed>=len(tx)//2+1
        child.stdin.close();child.wait(timeout=2);assert child.returncode==0
        stop(ecu);stop(ivi)
        report.update(status='PASS',worker_tx_frames=len(tx),tx_errors=done['tx_errors'],
            source_frames=source['frames'],independent_identical_auth_observations=auth_observed,
            exact_pair_mac_verified_rejections=len(matching_rejections()),normal_publications=len(published()),
            observer_dropped=bus.dropped,worker_input_has_no_key=True,dummy_key_retained=False,
            limits=['Same-host controlled vcan fixture, not Pi3 filesystem/process isolation.',
                'Only one replay example, not detection/blocking rate or physical timing.',
                'No IDS/IF is started; actual verifier rejection is the asserted endpoint.'])
    report['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        (Path(__file__),ROOT/'security/experiments/can_attack_worker.py')}
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(report,output=str(out))))


if __name__=='__main__':main()
