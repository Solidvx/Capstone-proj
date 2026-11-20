"""Test-only calculation fault dependency in production ECU main; virtual CAN only."""
import argparse
from contextlib import ExitStack
import json
import os
import re
import socket
import struct
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from test_ecu_checkpoint_crash import read_state, stop
from test_ecu_ivi_products import inject_virtual_attack


def records(path):
    if not path.exists():return []
    rows=[]
    for line in path.read_text().splitlines():
        try:rows.append(json.loads(line))
        except json.JSONDecodeError:pass # final live line may be incomplete
    return rows


def recovered_product(args,interface,out,ivi,manager,state,observations,injector):
    """Successful new work in the same ECU process, not merely a new thread."""
    text_path=out/'ecu.log';tag='CAN_RX_RECOVERY' if args.can_receive else 'BMS_RECOVERY'
    pattern=re.compile(r'^'+tag+r' event=(\d+) attempts=(\d+) failures=(\d+) generation=(\d+) monotonic_ms=(\d+)(?: frames=(\d+))?$',re.M)
    baseline=None;baseline_threads=None;fault_sent=False;probe_sent=False;rejection_start=0
    deadline=time.monotonic()+18
    while time.monotonic()<deadline:
        assert manager.poll() is None and ivi.poll() is None,'product exited during task recovery'
        text=text_path.read_text();log_rows=records(text_path);rows=records(observations)
        processes=[row for row in log_rows if row.get('result')=='ECU_PROCESS_STARTED']
        assert len(processes)<=1,'task recovery restarted the ECU process'
        publications=[row for row in rows if row.get('result')=='SESSION_PUBLICATION']
        if baseline is None and len(publications)>=3 and processes:
            baseline=publications[-1];pid=processes[0]['pid']
            baseline_threads={int(p.name) for p in Path('/proc',str(pid),'task').iterdir()}
        events=[{'event':int(m[1]),'attempts':int(m[2]),'failures':int(m[3]),
                 'generation':int(m[4]),'monotonic_ms':int(m[5]),'frames':int(m[6]) if m[6] else None}
                for m in pattern.finditer(text)]
        if args.can_receive and baseline is not None and not fault_sent:
            # A single callback failure; future normal/authenticated frames remain available.
            injector.send(struct.pack('=IB3x8s',0x123,8,bytes(8)));fault_sent=True
        if args.can_receive and any(row['event']==1 for row in events) and not probe_sent:
            rejection_start=len(rows)
            inject_virtual_attack(interface,'replay',one_pair=True) # bus bytes only, no key argument
            probe_sent=True
        recovered=[row for row in events if row['event']==2]
        if baseline is not None and recovered:
            last=recovered[-1];bound=last['monotonic_ms']*1_000_000
            after=[row for row in publications if int(row['t1_received_ns'])>=bound]
            statuses=[bytes.fromhex(row['body_hex']) for row in rows
                if row.get('result')=='AUTHENTICATED_DIAGNOSTIC' and row.get('kind')==1
                and int(row['verified_monotonic_ms'])>=last['monotonic_ms']]
            running=any(body[32]==2 and body[34]==2 and body[35]==1 and body[37]==3 for body in statuses)
            matched=[]
            for row in rows[rejection_start:]:
                if row.get('result')=='LOCAL_REJECTION_RECORD':
                    body=bytes.fromhex(row['body_hex']);identity=body[16:32].hex()
                    if body[32]==7 and body[33]==1 and body[34]==1 and 'record_id='+identity in text:
                        matched.append(identity)
            if len(after)>=3 and running and (not args.can_receive or matched):break
        time.sleep(.01)
    else:raise RuntimeError('actual task recovery/new authenticated work not observed: '+str(out))
    starts=[row for row in events if row['event']==1]
    assert len(starts)==len(recovered)==1 and [row['event'] for row in events]==[1,2],events
    assert all(row['attempts']==1 and row['failures']==0 and row['generation']==1 for row in events),events
    assert starts[0]['monotonic_ms']<=last['monotonic_ms'],events
    assert 'ERR_WATCHDOG_MAX_RESTART' not in text and 'crash recovery' not in text and 'planned restart' not in text,text
    assert all(row['valid'] and not row['stale'] for row in after),after
    assert state.read_text().splitlines()[5]=='2 1 3 0','healthy task recovery erased battery warning'
    active_threads={int(p.name) for p in Path('/proc',str(pid),'task').iterdir()}
    result={'status':'PASS','scope':'actual same-process task recovery and authenticated IVI processing over vcan',
        'task':'can-rx' if args.can_receive else 'bms-calculation','ecu_pid':pid,
        'supervisor_process_restarts':0,'recovery_events':events,'actual_worker_restart_failures':0,
        'authenticated_post_recovery_bms':len(after),'first_post_recovery_bms_ns':int(after[0]['t1_received_ns']),
        'battery_warning_preserved':True,'checkpoint_risk_reason':'WARNING/0x03',
        'authenticated_running_status':True,'max_restart_error_log_count':0,'secrets_retained':False}
    if args.can_receive:
        assert len(baseline_threads-active_threads)==len(active_threads-baseline_threads)==1,(baseline_threads,active_threads)
        assert last['frames']>0,'receive recovery accepted a new thread without a new callback'
        result.update(reclaimed_thread_ids=sorted(baseline_threads-active_threads),
                      new_thread_ids=sorted(active_threads-baseline_threads),
                      authenticated_ivi_rejection_ids=matched,keyless_probe='one observed raw/auth replay pair')
    else:
        work=[row for row in log_rows if row.get('result')=='TEST_BMS_WORK']
        assert [row['phase'] for row in work]==['initial','fault','late-completed','completed'],work
        initial,fault,late,completed=work
        assert initial['tid']==fault['tid'] and initial['generation']==fault['generation']==0
        assert completed['generation']==1 and completed['tid']!=fault['tid'] and completed['tid'] in active_threads
        assert late['tid']==fault['tid'] and late['generation']==0
        blocked=late['monotonic_ms']-fault['monotonic_ms'];assert blocked>=4000,'required4s blocking not exercised'
        assert fault['tid'] not in active_threads,'old worker still alive after replacement'
        timeout=re.search(r'BMS_RECOVERY timeout; stopping old task sampled_ms=(\d+) monotonic_ms=(\d+)',text)
        assert timeout and int(timeout[1])==fault['sampled_ms'],text
        elapsed=int(timeout[2])-int(timeout[1]);assert elapsed>=3000,'timeout detected before the required3s'
        assert int(timeout[2])<=late['monotonic_ms']<=starts[0]['monotonic_ms']<=completed['monotonic_ms']<=last['monotonic_ms'],(events,work)
        assert not any(fault['monotonic_ms']*1_000_000<=int(row['t1_received_ns'])<completed['monotonic_ms']*1_000_000 for row in publications),'late old result was published'
        result.update(work=work,timeout_from_sample_ms=elapsed,
                      injected_block_observed_ms=blocked,late_generation_result_discarded=True,
                      reclaimed_thread_ids=[fault['tid']],new_thread_ids=[completed['tid']])
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('ecu','ivi','policy','supervisor'):p.add_argument('--'+name,required=True)
    p.add_argument('--out-parent',type=Path,required=True)
    p.add_argument('--unreclaimed',action='store_true')
    p.add_argument('--can-receive',action='store_true')
    p.add_argument('--recover-once',action='store_true',help='test-only single fault followed by real successful work')
    a=p.parse_args();interface=os.environ.get('CAPSTONE_SESSION_TEST_INTERFACE','')
    if not interface:return 77
    if a.unreclaimed and a.can_receive:raise ValueError('separate fault scenarios required')
    if a.unreclaimed and a.recover_once:raise ValueError('unreclaimed and successful recovery are separate scenarios')
    if not interface.startswith('vcan') or not Path('/sys/devices/virtual/net',interface).is_dir():
        raise ValueError('existing virtual CAN only')
    a.out_parent.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='bms-recovery-',dir=a.out_parent))
    with tempfile.TemporaryDirectory(prefix='bms-private-') as private_name,ExitStack() as cleanup:
        private=Path(private_name);key=private/'dummy.key';key.write_bytes(bytes(range(32)));key.chmod(0o600)
        state=private/'state';runtime=private/'runtime';runtime.mkdir(mode=0o700)
        ready=private/'ivi-ready';observations=out/'ivi.jsonl'
        profile=private/'warning.csv'
        if a.recover_once:profile.write_text('voltage,current,temperature\n42,-2,56\n')
        log=cleanup.enter_context((out/'ivi.log').open('w'))
        ivi=subprocess.Popen([a.ivi,'--interface',interface,'--protocol','session-v2',
            '--session-policy',a.policy,'--secoc-key',str(key),'--ready-file',str(ready),
            '--observation-jsonl',str(observations),'--windowed']+
            (['--rejection-queue','4','--rejection-frame-budget','2','--rejection-expiry-ms','5000'] if a.recover_once and a.can_receive else []),stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=str(runtime)))
        cleanup.callback(stop,ivi)
        deadline=time.monotonic()+5
        while not ready.exists():
            if ivi.poll() is not None or time.monotonic()>deadline:raise RuntimeError('IVI did not start')
            time.sleep(.02)
        log=cleanup.enter_context((out/'ecu.log').open('w'))
        ecu=subprocess.Popen([sys.executable,a.supervisor,'--ecu',a.ecu,'--checkpoint',str(state),
            '--initial-intent','fresh','--stop-timeout','2','--startup-timeout','3','--heartbeat-timeout','1',
            '--max-crash-restarts','3','--','--interface',interface,
            '--sensor-mode','profile_csv' if a.recover_once else 'constant',
            *(['--profile',str(profile)] if a.recover_once else []),
            '--key',str(key),'--session-policy',a.policy,'--checkpoint-period-ms','100',
            '--checkpoint-flush-ms','2000','--checkpoint-max-age-ms','60000',
            '--restart-wait-ms','200','--restart-retry-ms','50','--restart-notice-attempts','3'],
            stdout=log,stderr=subprocess.STDOUT)
        cleanup.callback(stop,ecu)
        injector=None
        if a.can_receive:
            injector=cleanup.enter_context(socket.socket(socket.PF_CAN,socket.SOCK_RAW,socket.CAN_RAW))
            injector.bind((interface,))
        if a.recover_once:
            result=recovered_product(a,interface,out,ivi,ecu,state,observations,injector)
            # Persist the same final checkpoint before private key/state cleanup.
            stop(ecu)
            assert ecu.returncode==0 and state.read_text().splitlines()[5]=='2 1 3 0'
            (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(dict(result,output=str(out))))
            return 0
        deadline=time.monotonic()+23
        while time.monotonic()<deadline:
            if ecu.poll() is not None:raise RuntimeError('ECU supervisor exited before warning')
            rows=[]
            if observations.exists():
                for line in observations.read_text().splitlines():
                    try:rows.append(json.loads(line))
                    except json.JSONDecodeError:pass # concurrently appended final line
            if injector and any(row.get('result')=='VIEW_MODEL_PUBLICATION' for row in rows):
                injector.send(struct.pack('=IB3x8s',0x123,8,bytes(8)))
            if state.exists() and read_state(state)['risk']==(0 if a.unreclaimed else 1):
                statuses=[bytes.fromhex(x['body_hex']) for x in rows
                          if x.get('result')=='AUTHENTICATED_DIAGNOSTIC' and x['kind']==1]
                if any(b[32]==5 and b[35]==(0 if a.unreclaimed else 1) and b[37]==(0 if a.unreclaimed else 7) for b in statuses):break
            time.sleep(.05)
        else:raise RuntimeError('no authenticated recovery-exhausted WARNING')
        time.sleep(.3)
        assert ecu.poll() is None and ivi.poll() is None,'independent process/communication stopped'
        text=(out/'ecu.log').read_text()
        if a.can_receive:
            assert 'CAN_RX_RECOVERY event=4 attempts=3 failures=3' in text,text
        assert ('event=5 attempts=0 failures=0' if a.unreclaimed else 'attempts=3 failures=3') in text,text
        error_tag='ERR_WATCHDOG_MAX_RESTART'
        if a.unreclaimed:
            assert error_tag not in text,'unreclaimed worker was falsely logged as three failed restarts'
        else:
            task='can-rx' if a.can_receive else 'bms-calculation'
            assert text.count(error_tag)==1 and error_tag+' task='+task+' attempts=3 failures=3' in text,text
        if a.unreclaimed:assert 'BMS_RECOVERY event=1 ' not in text,'duplicate worker started'
        assert 'crash recovery' not in text and 'planned restart' not in text,text
        assert any(x.get('result')=='VIEW_MODEL_PUBLICATION' for x in rows),'no initial real BMS publication'
        assert state.read_text().splitlines()[5]==('2 0 0 0' if a.unreclaimed else '2 1 7 0'),'protection checkpoint mismatch'
    result={'status':'PASS','scope':'production main with test-only failing '+('CAN receive' if a.can_receive else 'calculation')+' dependency; vcan',
            'actual_worker_restart_failures':0 if a.unreclaimed else 3,'authenticated_warning_reason':None if a.unreclaimed else 7,
            'unreclaimed_operator_required':a.unreclaimed,
            'max_restart_error_log_count':text.count(error_tag),
            'supervisor_process_restarts':0,'checkpointed_warning':not a.unreclaimed,'secrets_retained':False}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(result,output=str(out))))
    return 0

if __name__=='__main__':raise SystemExit(main())
