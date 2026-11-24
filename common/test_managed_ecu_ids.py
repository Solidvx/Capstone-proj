"""Real supervisor owns ECU/IDS: IDS loss degrades coverage, ECU loss resumes."""
import argparse
from collections import defaultdict,deque
import hashlib
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from test_session_ids_products import records,stop,wait_file

ROOT=Path(__file__).resolve().parent.parent


class TxWireWitness:
    """Test-only independent vcan socket, bounded lifetime and record count."""
    def __init__(self,interface,path):
        self.path=path;self.error=None;self.stopping=threading.Event();self.closed=False
        self.socket=socket.socket(socket.PF_CAN,socket.SOCK_RAW,socket.CAN_RAW)
        self.socket.bind((interface,));self.socket.settimeout(.1)
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()

    def run(self):
        try:
            with self.path.open('w') as output:
                count=0
                while not self.stopping.is_set():
                    try:raw=self.socket.recv(16)
                    except socket.timeout:continue
                    received_ns=time.monotonic_ns()
                    can_id,dlc,data=struct.unpack('=IB3x8s',raw)
                    count+=1
                    if count>20000:raise ValueError('test witness record budget exceeded')
                    output.write(json.dumps({'can_id':can_id,'dlc':dlc,'data':data[:dlc].hex(),
                        'received_ns':received_ns})+'\n')
        except Exception as error:self.error=str(error)

    def close(self):
        if self.closed:return
        self.stopping.set();self.thread.join(timeout=1);self.socket.close();self.closed=True
        if self.thread.is_alive():raise RuntimeError('test witness did not stop')
        if self.error:raise RuntimeError('test witness failed: '+self.error)


def wait(owner,predicate,timeout=8):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        found=predicate()
        if found:return found
        if owner.poll() is not None:raise RuntimeError('manager exited')
        time.sleep(.03)
    raise RuntimeError('managed product condition timed out')


def owned_pid(log,parent,kind):
    matches=re.findall('ECU_SUPERVISOR: '+kind+r' pid=(\d+)',log.read_text())
    if not matches:return None
    pid=int(matches[-1]);path=Path('/proc',str(pid),'status')
    if not path.exists():return None
    return pid if re.search(r'^PPid:\s+'+str(parent)+r'$',path.read_text(),re.M) else None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for option in ('ecu','ivi','policy','supervisor'):parser.add_argument('--'+option,required=True)
    parser.add_argument('--out-parent',required=True,type=Path)
    parser.add_argument('--measure-resources',action='store_true',help='opt-in N07 measured IDS generation acceptance')
    parser.add_argument('--trace-can-tx',action='store_true',help='opt-in nonblocking CAN syscall trace acceptance')
    args=parser.parse_args();interface=os.environ.get('CAPSTONE_SESSION_TEST_INTERFACE','')
    if not interface:return 77
    if not interface.startswith('vcan') or not Path('/sys/devices/virtual/net',interface).is_dir():raise ValueError('existing vcan required')
    args.out_parent.mkdir(parents=True,exist_ok=True)
    output=Path(tempfile.mkdtemp(prefix='managed-ids-',dir=args.out_parent))
    with tempfile.TemporaryDirectory(prefix='managed-ids-private-') as private,ExitStack() as cleanup:
        private=Path(private);key=private/'dummy.key';key.write_bytes(bytes(range(32)));key.chmod(0o600)
        logs=output/'ids';logs.mkdir(mode=0o700)
        settings=private/'ids.json';settings.write_text(json.dumps({'python':sys.executable,'repository':str(ROOT),
            'log_directory':str(logs),'mode':'rules-only','frame_budget':2,'expiry_ms':1000,
            **({'measure_resources':True} if args.measure_resources else {})}))
        runtime=private/'runtime';runtime.mkdir(mode=0o700)
        witness=TxWireWitness(interface,output/'tx-wire-witness.jsonl') if args.trace_can_tx else None
        if witness:cleanup.callback(witness.close)
        observations=output/'observations.jsonl';ready=private/'ready.json'
        ivi_log=cleanup.enter_context((output/'ivi.log').open('w'))
        ivi=subprocess.Popen([args.ivi,'--interface',interface,'--secoc-key',str(key),'--protocol','session-v2',
            '--session-policy',args.policy,'--observation-jsonl',str(observations),'--ready-file',str(ready),
            '--windowed','--demo-exit-ms','60000'],env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=str(runtime)),
            stdout=ivi_log,stderr=subprocess.STDOUT)
        cleanup.callback(stop,ivi);wait_file(ready,[ivi])
        log=output/'manager.log';stream=cleanup.enter_context(log.open('w'))
        manager=subprocess.Popen([sys.executable,args.supervisor,'--ecu',args.ecu,'--ids-settings',str(settings),
            '--checkpoint',str(private/'state'),'--initial-intent','fresh','--stop-timeout','1','--startup-timeout','5',
            '--heartbeat-timeout','1','--max-crash-restarts','1']+(['--trace-can-tx'] if args.trace_can_tx else [])+['--','--interface',interface,'--key',str(key),
            '--session-policy',args.policy,'--checkpoint-period-ms','100','--checkpoint-flush-ms','1000',
            '--checkpoint-max-age-ms','60000','--restart-wait-ms','200','--restart-retry-ms','50','--restart-notice-attempts','2'],
            stdout=stream,stderr=subprocess.STDOUT)
        cleanup.callback(stop,manager)
        ecu_pid=wait(manager,lambda:owned_pid(log,manager.pid,'started'))
        ids_pid=wait(manager,lambda:owned_pid(log,manager.pid,'IDS started'))
        wait(manager,lambda:any(row.get('observation_ready') for row in records(observations)))
        first=next(row for row in records(log) if row.get('result')=='OWNED_IDS_READY')
        if args.measure_resources:
            assert first['resource_measurement'] is True
            assert first['startup_identity']['resource_measurement'] is True
            wait(manager,lambda:any(row.get('result')=='RESOURCE_SAMPLE'
                 for row in records(logs/('ids-'+first['generation'])/'events.jsonl')))
        active_collection=subprocess.run([sys.executable,'-m','security.experiments.session_ids_log',
            '--log-root',str(logs),'--generation',first['generation']],cwd=ROOT,capture_output=True,timeout=5)
        assert active_collection.returncode==2 and not active_collection.stdout
        assert 'still active' in json.loads(active_collection.stderr)['error']
        # Leave an active incident behind before the IDS/ECU generation changes.
        with socket.socket(socket.PF_CAN,socket.SOCK_RAW,socket.CAN_RAW) as attacker:
            attacker.bind((interface,))
            for index in range(12):
                attacker.send(struct.pack('=IB3x8s',(0x050,0x060,0x070)[index%3],8,bytes(8)))
                time.sleep(.01)
        wait(manager,lambda:any(row.get('kind')==7 and row.get('condition_mask')==1 and row.get('observation_ready') for row in records(observations)))
        start=len(records(observations));os.kill(ids_pid,signal.SIGKILL)
        wait(manager,lambda:not Path('/proc',str(ids_pid)).exists())
        wait(manager,lambda:any(row.get('result')=='VIEW_MODEL_PUBLICATION' and '현재 감시 상태를 확인' in row.get('security_description','') for row in records(observations)[start:]))
        assert owned_pid(log,manager.pid,'started')==ecu_pid,'IDS loss restarted the battery process'
        wait(manager,lambda:len([row for row in records(observations)[start:] if row.get('result')=='SESSION_PUBLICATION'])>=20)
        start=len(records(observations));os.kill(ecu_pid,signal.SIGKILL)
        new_ecu=wait(manager,lambda:(pid if (pid:=owned_pid(log,manager.pid,'started')) and pid!=ecu_pid else None))
        new_ids=wait(manager,lambda:(pid if (pid:=owned_pid(log,manager.pid,'IDS started')) and pid!=ids_pid else None))
        wait(manager,lambda:any(row.get('observation_ready') for row in records(observations)[start:]))
        wait(manager,lambda:any(row.get('result')=='VIEW_MODEL_PUBLICATION' and row.get('connection')=='ECU 프로그램 복구 완료' for row in records(observations)[start:]))
        wait(manager,lambda:any(row.get('result')=='VIEW_MODEL_PUBLICATION' and row.get('security')=='새 공격 징후 없음' for row in records(observations)[start:]),timeout=12)
        stop(manager)
        assert manager.returncode==0 and not Path('/proc',str(new_ecu)).exists() and not Path('/proc',str(new_ids)).exists()
        generations=[row for row in records(log) if row.get('result')=='OWNED_IDS_READY']
        assert len(generations)==2 and len({row['generation'] for row in generations})==2
        assert {row['ids_pid'] for row in generations}=={ids_pid,new_ids}
        executables=[row for row in records(log) if row.get('result')=='ECU_PROCESS_STARTED']
        assert len(executables)==2 and {row['pid'] for row in executables}=={ecu_pid,new_ecu}
        assert all(row['executable_sha256']==hashlib.sha256(Path(args.ecu).read_bytes()).hexdigest() for row in executables)
        assert generations[0]['startup_identity']==generations[1]['startup_identity']
        if args.trace_can_tx:
            # Stop only after the sender is reaped; allow the independent socket
            # to drain. Times are same-host userspace observations, not wire latency.
            time.sleep(.2);witness.close()
            all_rows=records(log)
            attempts=[row for row in all_rows if row.get('result')=='ECU_CAN_TX']
            ends=[row for row in all_rows if row.get('result')=='ECU_CAN_TX_CAPTURE_END']
            assert attempts and {row['ecu_pid'] for row in attempts}=={ecu_pid,new_ecu}
            assert {row['instance_id'] for row in attempts}=={row['instance_id'] for row in all_rows if row.get('result')=='ECU_INPUT_LINEAGE'}
            assert all(row['syscall_attempted'] and row['returned_bytes']==16 and row['error_number']==0 and row['kernel_accepted'] for row in attempts)
            assert any(row['can_id']==0x100 and row['counter'] is None for row in attempts)
            assert any(row['can_id']==0x102 and type(row['counter']) is int for row in attempts)
            assert len(ends)==2
            assert next(row for row in ends if row['ecu_pid']==ecu_pid)['status']=='INCOMPLETE'
            assert next(row for row in ends if row['ecu_pid']==new_ecu)['status']=='COMPLETE'
            assert all(row['trace_can_tx'] is True for row in executables)
            arrivals=defaultdict(deque)
            for row in records(witness.path):
                arrivals[(row['can_id'],row['dlc'],row['data'])].append(row['received_ns'])
            matched=0
            for row in attempts:
                candidates=arrivals[(row['can_id'],row['dlc'],row['data'])]
                while candidates and candidates[0]<row['started_ns']:candidates.popleft()
                assert candidates,'kernel-accepted attempt missing from independent vcan witness'
                candidates.popleft();matched+=1
            (output/'tx-trace-summary.json').write_text(json.dumps({'attempt_records':len(attempts),'capture_ends':ends,
                'witness_matched_records':matched,'witness_sha256':hashlib.sha256(witness.path.read_bytes()).hexdigest(),
                'note':'Independent same-host vcan socket ID/DLC/data occurrence matching after each attempt start. Not physical CAN/IVI application latency. SIGKILL lacks final trace; graceful stop is complete.'},indent=2)+'\n')
        collected=[];measurements=[]
        for generation in generations:
            assert generation['mode']=='rules-only' and generation['protocol']=='session-v2'
            for kind in ('events','process'):
                result=subprocess.run([sys.executable,'-m','security.experiments.session_ids_log',
                    '--log-root',str(logs),'--generation',generation['generation'],'--kind',kind],
                    cwd=ROOT,capture_output=True,timeout=5)
                metadata=json.loads(result.stderr)
                assert metadata['schema']=='owned-ids-log-v1' and metadata['generation']==generation['generation']
                assert metadata['sha256']==hashlib.sha256(result.stdout).hexdigest()
                assert result.returncode==(0 if metadata['status']=='COMPLETE' else 2)
                if kind=='events':
                    started=json.loads(result.stdout.splitlines()[0])
                    assert started['startup_identity']==generation['startup_identity']
                    if args.measure_resources:
                        event_rows=[json.loads(line) for line in result.stdout.splitlines()]
                        reports=[row for row in event_rows if row.get('result') in ('RESOURCE_SAMPLE','RESOURCE_SUMMARY')]
                        assert reports and all(row['run_id']==started['run_id'] and row['pid']==generation['ids_pid'] for row in reports)
                        assert all(row['counts']['completed_frames']>0 and row['memory_end']['rss_bytes']>0 for row in reports)
                        assert all(row['loss']['wire_or_interface_loss'] is None for row in reports)
                        if generation['ids_pid']==ids_pid:
                            assert not any(row['final'] for row in reports),'SIGKILL cannot claim a complete lifetime'
                            assert reports[-1]['status']=='IN_PROGRESS'
                        else:
                            assert reports[-1]['final'] and reports[-1]['status']=='INTERRUPTED'
                            assert reports[-1]['counts']['failed_frames']==0
                            assert reports[-1]['durations']['model_anomaly']['calls']==0
                        measurements.append({'generation':generation['generation'],'pid':generation['ids_pid'],
                                             'available_reports':len(reports),'last':reports[-1],
                                             'final_summary_available':reports[-1]['final']})
                (output/(generation['generation']+'-'+kind+'.log')).write_bytes(result.stdout)
                collected.append(metadata)
        (output/'collected-logs.json').write_text(json.dumps(collected,indent=2)+'\n')
        if args.measure_resources:(output/'resource-measurements.json').write_text(json.dumps(measurements,indent=2)+'\n')
    result={'status':'PASS','scope':'real ECU/IDS manager and Qt over vcan','ids_loss_keeps_ecu':True,
            'coverage_becomes_unknown':True,'ecu_crash_replaces_both':True,'restored_program_and_ids_ready':True,
            'prior_unknown_incident_reconciled_after_new_healthy_observation':True,
            'manual_stop_reaps_both':True,'mode':'rules-only','key_retained':False,
            'owned_generations':2,'closed_generation_files_collected':len(collected),'active_collection_refused':True,
            'native_executable_identity_verified':True,'ids_ready_start_identity_verified':True}
    if args.measure_resources:
        result.update(resource_measurement=True,resource_generations=len(measurements),
                      sigkill_no_complete_summary=True,sigterm_partial_summary_preserved=True)
    if args.trace_can_tx:result.update(trace_can_tx=True,trace_generation_identity_verified=True,trace_final_partial_separated=True)
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(result,output=str(output))))
    return 0


if __name__=='__main__':raise SystemExit(main())
