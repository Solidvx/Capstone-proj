"""A5/A6 supplementary product cases on an explicitly selected, empty vcan.

Only the test ECU binary accepts the inherited sender gate. The existing
keyless worker injects plausible 0x100 at nominal10fps; it receives no key or
sender-control FD. No physical bus, production control API or official matrix.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

from test_session_ids_products import records,stop,wait_file

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from security.experiments.can_capture import CaptureSocket,frame_json,inspect_interface

CASES=('A5','A6','controller-loss','invalid-command','pause-deadline')


class Witness:
    def __init__(self,bus,stream,children):
        self.bus,self.stream,self.children=bus,stream,children
        self.rows=[]

    def poll(self):
        if any(child.poll() is not None for child in self.children):raise RuntimeError('PRODUCT_EXITED')
        value=self.bus.receive(.01)
        if value:
            frame,_=value
            row=frame_json(frame);self.rows.append(row)
            self.stream.write(json.dumps(row)+'\n');self.stream.flush()
            if frame.error or frame.extended or frame.remote or frame.dlc!=8:
                raise RuntimeError('UNEXPECTED_OR_ERROR_FRAME')
        if self.bus.dropped:raise RuntimeError('OBSERVER_RX_DROPPED')

    def until(self,predicate,timeout=3):
        deadline=time.monotonic()+timeout
        while not predicate():
            if time.monotonic()>=deadline:raise RuntimeError('OBSERVATION_DEADLINE')
            self.poll()

    def interval(self,seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:self.poll()


def case(args,interface,output,name):
    directory=output/name;directory.mkdir()
    result={'case':name,'status':'INCOMPLETE','normal_sender_recovered':False}
    failure=None;writer=None;worker=None;ecu=None;witness=None
    with tempfile.TemporaryDirectory(prefix='sender-private-') as temporary,ExitStack() as cleanup:
        private=Path(temporary);key=private/'dummy.key';key.write_bytes(bytes(range(32)));key.chmod(0o600)
        runtime=private/'runtime';runtime.mkdir(mode=0o700)
        ecu_log=directory/'ecu.log';ids_log=directory/'ids.jsonl';observations=directory/'ivi.jsonl'
        bus=CaptureSocket(interface);cleanup.callback(bus.close)
        if bus.receive(.1) is not None:raise RuntimeError('BUS_NOT_QUIET_BEFORE_ACTOR_START')
        reader,writer=os.pipe2(os.O_NONBLOCK|os.O_CLOEXEC)
        context_reader,context_writer=os.pipe2(os.O_NONBLOCK|os.O_CLOEXEC)
        # Callbacks accept already-closed descriptors without reusing any FD.
        owned={reader,writer,context_reader,context_writer}
        def close_fd(fd):
            if fd in owned:owned.remove(fd);os.close(fd)
        cleanup.callback(lambda:[close_fd(fd) for fd in list(owned)])
        def launch(command,log,**options):
            stream=cleanup.enter_context(log.open('x'))
            child=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,**options)
            cleanup.callback(stop,child);return child
        ids=launch([sys.executable,'-m','security.ids.runtime','--interface',interface,'--rules-only',
            '--protocol','session-v2','--session-context-fd',str(context_reader),'--secoc-key',str(key),
            '--diagnostic-socket',str(private/'ids.sock'),'--log',str(ids_log),
            '--ready-file',str(private/'ids.ready'),'--duration','20'],directory/'ids-process.log',
            cwd=ROOT,pass_fds=(context_reader,))
        close_fd(context_reader);wait_file(private/'ids.ready',[ids])
        ivi=launch([args.ivi,'--interface',interface,'--protocol','session-v2','--secoc-key',str(key),
            '--session-policy',args.policy,'--run-id','SENDER-'+name,'--ready-file',str(private/'ivi.ready'),
            '--observation-jsonl',str(observations),'--windowed','--demo-exit-ms','20000'],directory/'ivi.log',
            env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=str(runtime)))
        wait_file(private/'ivi.ready',[ids,ivi])
        ecu=launch([args.fixture,'--interface',interface,'--key',str(key),'--session-policy',args.policy,
            '--ids-context-fd',str(context_writer),'--ids-socket',str(private/'ids.sock'),'--ids-pid',str(ids.pid),
            '--ids-frame-budget','2','--ids-expiry-ms','1000','--test-sender-control-fd',str(reader)],ecu_log,
            pass_fds=(reader,context_writer))
        close_fd(reader);close_fd(context_writer)
        result['actor_pids']={'ecu':ecu.pid,'ids':ids.pid,'ivi':ivi.pid}
        stream=cleanup.enter_context((directory/'frames.jsonl').open('x'))
        witness=Witness(bus,stream,[ecu,ids,ivi])
        publications=lambda:[row for row in records(observations) if row.get('result')=='SESSION_PUBLICATION']
        gate=lambda paused:[row for row in records(ecu_log) if row.get('result')=='TEST_SENDER_GATE' and row['paused']==paused]
        try:
            witness.until(lambda:len(publications())>=3)
            baseline=publications();generation=baseline[-1]['session_generation']
            if name=='A6':
                worker=launch([sys.executable,'-u','-m','security.experiments.can_attack_worker',
                    '--interface',interface,'--environment','vcan','--duration','8','--run-id','A6-REPLACEMENT',
                    '--i-am-on-a-test-bus'],directory/'worker.jsonl',stdin=subprocess.PIPE,cwd=ROOT)
                witness.until(lambda:any(row.get('result')=='READY' for row in records(directory/'worker.jsonl')))
            result['pause_requested_ns']=time.monotonic_ns();os.write(writer,b'P')
            witness.until(lambda:bool(gate(True)))
            result['pause_ack']=gate(True)[-1]
            witness.interval(.2) # Drain any frame queued before the acknowledged test gate.
            start=time.monotonic();result['quiet_observation_start']=start
            pub_start=len(publications());frame_start=len(witness.rows)
            if name=='A6':
                request=dict(trial=1,attack='spoofing',rate=10,duration=.7,seed=106001,
                             interface=interface,secoc=False,profile='mixed-v1')
                worker.stdin.write((json.dumps(request)+'\n').encode());worker.stdin.flush()
                witness.until(lambda:any(row.get('result')=='ATTACK_DONE' for row in records(directory/'worker.jsonl')))
                worker.stdin.close();worker.wait(timeout=2)
                if worker.returncode!=0:raise RuntimeError('KEYLESS_WORKER_FAILED')
                rows=records(directory/'worker.jsonl');tx=[row for row in rows if row.get('result')=='TX']
                done=next(row for row in rows if row.get('result')=='ATTACK_DONE')
                if done['tx_errors'] or done['rx_dropped'] or len(tx)<4 or done['sent']!=len(tx):
                    raise RuntimeError('INCOMPLETE_REPLACEMENT_INJECTION')
                result.update(nominal_rate_fps=10,worker_done=done,first_injection=tx[0]['t'],last_injection=tx[-1]['t'])
                result['worker_intervals_ms']=[(b['t']-a['t'])*1000 for a,b in zip(tx,tx[1:])]
                witness.interval(.1)
            else:
                witness.interval(.6)
            end=time.monotonic();result['quiet_observation_end']=end
            exposed=witness.rows[frame_start:]
            raws=[row for row in exposed if row['can_id']==0x100]
            auths=[row for row in exposed if row['can_id']==0x102]
            if auths:raise RuntimeError('NORMAL_AUTH_STILL_TRANSMITTED_DURING_PAUSE')
            if not any(row['can_id']==0x302 for row in exposed):raise RuntimeError('ECU_DIAGNOSTICS_STOPPED')
            if len(publications())!=pub_start:raise RuntimeError('UNAUTHENTICATED_OR_PAUSED_DATA_PUBLISHED')
            if name=='A6':
                if Counter(row['data'] for row in raws)!=Counter(row['data'] for row in tx):
                    raise RuntimeError('REPLACEMENT_TX_AND_INDEPENDENT_OBSERVER_MISMATCH')
            elif raws:raise RuntimeError('NORMAL_RAW_STILL_TRANSMITTED_DURING_PAUSE')
            result.update(observed_raw=len(raws),observed_auth=len(auths),
                diagnostics_continued=True,unauthenticated_publications=0,
                last_baseline_bms_received_ns=int(baseline[-1]['t1_received_ns']))
            if name=='controller-loss':close_fd(writer);writer=None
            elif name=='invalid-command':os.write(writer,b'!')
            elif name=='pause-deadline':
                # Repeated pause does not renew the first 2s guard.
                os.write(writer,b'P')
                witness.until(lambda:bool(gate(False)),timeout=2)
            else:os.write(writer,b'R')
        except BaseException as error:
            failure=error;result['error']=type(error).__name__+': '+str(error)
        finally:
            # Stop injection before restoring the normal sender, even on failure.
            if worker is not None:stop(worker)
            before=len(publications())
            try:
                if writer is not None:
                    # A gate that closed on deadline/invalid input has already resumed.
                    if not gate(False):os.write(writer,b'R')
                    close_fd(writer);writer=None
                witness.until(lambda:len(publications())>=before+3,timeout=4)
                after=publications()[before:]
                if any(not row['valid'] or row['stale'] for row in after) or len({row['session_generation'] for row in after})!=1:
                    raise RuntimeError('RECOVERY_NOT_VALID_IN_STABLE_SESSION')
                result.update(normal_sender_recovered=True,resumed_authenticated_publications=len(after),
                    first_recovered_bms_received_ns=int(after[0]['t1_received_ns']),
                    baseline_session_generation=generation,recovered_session_generation=after[0]['session_generation'],
                    same_session_generation=after[0]['session_generation']==generation,
                    ecu_pid=ecu.pid,program_restarts=0,resume_ack=gate(False)[-1])
                expected={'controller-loss':'controller-eof','invalid-command':'invalid-command','pause-deadline':'deadline'}.get(name,'resume')
                if result['resume_ack']['reason']!=expected and failure is None:
                    raise RuntimeError('UNEXPECTED_GATE_RECOVERY_REASON')
            except BaseException as error:
                result['recovery_error']=type(error).__name__+': '+str(error)
                if failure is None:failure=error
            result['ids_events']=[{k:row.get(k) for k in ('timestamp','can_id','reason','attack_type')}
                for row in records(ids_log) if row.get('result')=='ANOMALY' and
                result.get('quiet_observation_start',float('inf'))<=row['timestamp']<=time.monotonic()]
            if failure is None:result['status']='PASS'
            else:result['status']='FAIL'
            (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('ecu','fixture','ivi','policy'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--out-parent',type=Path,required=True)
    parser.add_argument('--case',choices=CASES,action='append')
    parser.add_argument('--i-am-on-a-test-bus',action='store_true')
    args=parser.parse_args(argv);interface=os.environ.get('CAPSTONE_SESSION_TEST_INTERFACE','')
    if not args.i_am_on_a_test_bus:parser.error('explicit isolated virtual bus confirmation required')
    if not re.fullmatch(r'vcan[0-9]+',interface) or not Path('/sys/devices/virtual/net',interface).is_dir():
        parser.error('explicit existing virtual CAN required; physical buses refused')
    inspect_interface(interface,'vcan')
    # Verify absence of the test API in the real product, without opening CAN.
    rejected=subprocess.run([args.ecu,'--test-sender-control-fd','3'],capture_output=True,text=True,timeout=3)
    if rejected.returncode!=2 or 'Unsupported option' not in rejected.stderr:
        raise RuntimeError('PRODUCT_EXPOSES_TEST_SENDER_CONTROL')
    args.out_parent.mkdir(parents=True,exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix='sender-cases-',dir=args.out_parent))
    sources=[Path(__file__),ROOT/'adaptive_ecu/main.cpp',ROOT/'adaptive_ecu/test/ecu_sender_gate.h',
             ROOT/'security/experiments/can_attack_worker.py',ROOT/'security/ids/runtime.py',ROOT/'security/ids/session_detector.py']
    inputs=sources+[Path(getattr(args,name)) for name in ('ecu','fixture','ivi','policy')]
    identities={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    result={'schema':'supplementary-sender-cases-v1','status':'INCOMPLETE','environment':'vcan',
        'clock':'same-host monotonic receive; no cross-host or physical TX latency claim',
        'case_selection':args.case or list(CASES),'input_sha256':identities,
        'production_gate_refused':True,'keyless_worker':'existing spoofing mixed-v1 nominal10fps; A6 only',
        'key_retained':False,'physical_acceptance':False,'cases':[]}
    (output/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    interrupted=[]
    def interrupt(signum,_frame):
        if not interrupted:
            interrupted.append(signum)
            raise KeyboardInterrupt('controller signal '+str(signum))
    previous={sig:signal.signal(sig,interrupt) for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT)}
    try:
        for name in result['case_selection']:
            measured=case(args,interface,output,name);result['cases'].append(measured)
            if measured['status']!='PASS':raise RuntimeError('FAILED_CASE: '+name)
        if identities!={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}:
            raise RuntimeError('SOURCE_OR_EXECUTABLE_CHANGED')
        result['status']='PASS'
    except BaseException as error:
        result.update(status='FAIL',error=type(error).__name__+': '+str(error))
    finally:
        # Repeated stop signals must not interrupt sender recovery/child reaping.
        for sig,handler in previous.items():signal.signal(sig,signal.SIG_IGN if interrupted else handler)
    result['files_sha256']={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted(output.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'cases':[(r['case'],r['status']) for r in result['cases']],
                      'output':str(output),'error':result.get('error')}))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
