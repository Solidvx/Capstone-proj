"""Real ECU supervisor: SIGKILL, stalled task, bounded retries and manual stop."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

from test_ecu_checkpoint_crash import read_state


def wait_for(child,predicate,timeout=6):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        value=predicate()
        if value:return value
        if child.poll() is not None:raise RuntimeError('supervisor exited before expected progress')
        time.sleep(.02)
    raise RuntimeError('supervisor progress timeout')


def child_pid(log,owner):
    matches=re.findall(r'ECU_SUPERVISOR: started pid=(\d+)',log.read_text(errors='replace'))
    if not matches:return None
    pid=int(matches[-1])
    status=Path('/proc')/str(pid)/'status'
    if not status.exists():return None
    if re.search(r'^PPid:\s+'+str(owner)+r'$',status.read_text(),re.M):return pid
    return None


def stop(manager):
    if manager.poll() is None:
        manager.terminate()
        try:manager.wait(timeout=4)
        except subprocess.TimeoutExpired:manager.kill();manager.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ecu',required=True)
    parser.add_argument('--policy',required=True)
    parser.add_argument('--supervisor',required=True)
    parser.add_argument('--out-parent',type=Path,required=True)
    args=parser.parse_args()
    interface=os.environ.get('CAPSTONE_SESSION_TEST_INTERFACE','')
    if not interface:return 77
    if not interface.startswith('vcan') or not Path('/sys/devices/virtual/net',interface).is_dir():
        raise ValueError('existing virtual CAN only')
    args.out_parent.mkdir(parents=True,exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix='supervisor-',dir=args.out_parent))
    with tempfile.TemporaryDirectory(prefix='ecu-supervisor-private-') as folder:
        private=Path(folder);checkpoint=private/'state';key=private/'dummy.key';soh=private/'soh.csv'
        key.write_bytes(bytes(range(32)));key.chmod(0o600)
        soh.write_text('elapsed_s,estimated_capacity_ah\n0,50\n0.2,45\n')
        command=[sys.executable,args.supervisor,'--ecu',args.ecu,'--checkpoint',str(checkpoint),
            '--initial-intent','fresh','--stop-timeout','.3','--startup-timeout','3',
            '--heartbeat-timeout','.4','--max-crash-restarts','3','--',
            '--interface',interface,'--key',str(key),'--session-policy',args.policy,
            '--soh-profile',str(soh),'--checkpoint-period-ms','100','--checkpoint-flush-ms','200',
            '--checkpoint-max-age-ms','60000','--restart-wait-ms','100',
            '--restart-retry-ms','50','--restart-notice-attempts','2']
        log=output/'supervisor.log'
        with log.open('w') as stream:
            manager=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT)
            try:
                wait_for(manager,lambda:checkpoint.exists() and read_state(checkpoint)['capacity']==45)
                for index,fault in enumerate((signal.SIGKILL,signal.SIGSTOP,signal.SIGKILL,signal.SIGKILL)):
                    old=wait_for(manager,lambda:child_pid(log,manager.pid))
                    prior=read_state(checkpoint)
                    os.kill(old,fault)
                    if index==3:break
                    new=wait_for(manager,lambda:(pid if (pid:=child_pid(log,manager.pid)) and pid!=old else None))
                    wait_for(manager,lambda:read_state(checkpoint)['elapsed']>prior['elapsed']+.1)
                    assert read_state(checkpoint)['capacity']==45,'SOH was reset'
                    assert not Path('/proc',str(old)).exists(),'previous ECU not reaped'
                code=manager.wait(timeout=6)
                assert code==1,log.read_text()
                text=log.read_text()
                assert text.count('crash recovery attempt=')==3,text
                assert text.count('intent=resume')==3,text
                assert 'reason=heartbeat-timeout' in text and 'recovery budget exhausted' in text,text
                assert child_pid(log,manager.pid) is None,'ECU left alive'
            finally:stop(manager)
        # New explicit manual fresh invocation resets calculations; stopping the
        # manager must reclaim its child and never create an automatic restart.
        manual_soh=private/'manual-soh.csv'
        manual_soh.write_text('elapsed_s,estimated_capacity_ah\n0,50\n10,45\n')
        manual_command=command.copy();manual_command[manual_command.index('--soh-profile')+1]=str(manual_soh)
        manual_log=output/'manual.log'
        with manual_log.open('w') as stream:
            manager=subprocess.Popen(manual_command,stdout=stream,stderr=subprocess.STDOUT)
            try:
                pid=wait_for(manager,lambda:child_pid(manual_log,manager.pid))
                wait_for(manager,lambda:read_state(checkpoint)['capacity']==50 and read_state(checkpoint)['elapsed']<1)
                stop(manager)
                assert manager.returncode==0
                assert not Path('/proc',str(pid)).exists(),'manual stop left ECU alive'
                assert 'crash recovery attempt=' not in manual_log.read_text()
            finally:stop(manager)
        storage_log=output/'storage-failure.log'
        with storage_log.open('w') as stream:
            manager=subprocess.Popen(manual_command,stdout=stream,stderr=subprocess.STDOUT)
            try:
                wait_for(manager,lambda:child_pid(storage_log,manager.pid))
                private.chmod(0o500)
                assert manager.wait(timeout=6)==2,storage_log.read_text()
                text=storage_log.read_text()
                assert 'stopped storage-unavailable' in text,text
                assert 'crash recovery attempt=' not in text,text
            finally:
                private.chmod(0o700);stop(manager)
        assert key.read_bytes()==bytes(range(32)),'fresh start changed key'
    result={'status':'PASS','scope':'real ECU and supervisor over Linux vcan',
        'crash_restarts':3,'stalled_process_reclaimed':True,'retry_budget_enforced':True,
        'soh_45ah_preserved':True,'manual_fresh_reset':True,'storage_failure_stops_without_retry':True,
        'manual_stop_reclaimed_without_restart':True,'key_retained':False}
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(result,output=str(output))))
    return 0


if __name__=='__main__':raise SystemExit(main())
