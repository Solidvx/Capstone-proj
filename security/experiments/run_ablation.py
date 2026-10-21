"""Managed CAN defence trials. Run pilot before the 3x4x100 matrix.

Commands are explicit argv arrays in an operator configuration. Receiver and
whole-bus observer MUST share Node B's clock; remote commands must self-expire.
No source timestamps are subtracted from another host's clock.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from security.attack_simulator import ATTACKS, validate_safety
from security.experiments.normal_sender import BMS
from security.experiments.validate_m5_settings import validate as validate_settings

ATTACK_CODES = {'fuzzy': 1, 'replay': 2, 'spoofing': 3, 'flooding': 4}


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def trial_seed(attack, trial):
    return 100000+1000*ATTACKS.index(attack)+trial


class Child:
    def __init__(self, command, root, name):
        self.read_error=None
        self.records=[]
        self.lock=threading.Lock()
        self.output=(root/f'{name}.jsonl').open('x',encoding='utf-8')
        self.errors=(root/f'{name}.stderr').open('x',encoding='utf-8')
        try:
            self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.errors,
                text=True,bufsize=1,start_new_session=True)
        except (OSError,ValueError):
            self.output.close();self.errors.close()
            raise
        self.thread=threading.Thread(target=self._read,daemon=True)
        self.thread.start()

    def _read(self):
        try:
            self._read_lines()
        except OSError as error:
            self.read_error = error

    def _read_lines(self):
        for line in self.process.stdout:
            self.output.write(line); self.output.flush()
            try:
                row=json.loads(line)
                if isinstance(row,dict):
                    with self.lock:self.records.append(row)
            except json.JSONDecodeError:
                pass

    def snapshot(self):
        if self.read_error is not None:raise self.read_error
        with self.lock:return list(self.records)

    def ready(self,run_id,timeout=20):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if any(r.get('result')=='READY' and r.get('run_id')==run_id for r in self.snapshot()):return
            if self.process.poll() is not None:raise RuntimeError('child exited before READY')
            time.sleep(.02)
        raise TimeoutError('child READY timeout')

    def stop(self):
        if self.output.closed:return
        self.process.stdin.close()
        # The remote supervisor observes stdin EOF and reaps its process group.
        if self.process.poll() is None and any(module in ' '.join(self.process.args) for module in ('security.experiments.remote_process', 'security.experiments.trial_observer')):
            try:self.process.wait(timeout=4)
            except subprocess.TimeoutExpired:pass
        if self.process.poll() is None:
            os.killpg(self.process.pid,signal.SIGINT)
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid,signal.SIGTERM)
                try:self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid,signal.SIGKILL);self.process.wait()
        self.thread.join(timeout=3)
        if self.thread.is_alive():raise RuntimeError('child log reader did not close')
        self.process.stdout.close();self.output.close();self.errors.close()


def wait_alive(children,seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if any(c.process.poll() is not None for c in children):
            raise RuntimeError('managed process exited during evaluation')
        time.sleep(min(.05,max(0,deadline-time.monotonic())))


def render_command(template,values):
    if not isinstance(template,list) or not template or any(not isinstance(v,str) for v in template):
        raise ValueError('commands must be nonempty argv arrays')
    if Path(template[0]).name=='ssh' and not any('{lifetime_' in v for v in template):
        raise ValueError('remote commands must include a bounded lifetime placeholder')
    return [v.format_map(values) for v in template]


def summarize_observations(config,attack,tx,bus,receiver,normal):
    """Evaluate observed acceptance separately from detection and auth rejection."""
    fingerprints={(r['can_id'],r['data']) for r in tx if r.get('result')=='TX_ACCEPTED'}
    if not fingerprints:raise ValueError('no successful attack transmission')
    candidates=[r for r in bus if r.get('result')=='BUS_FRAME' and
                (r.get('can_id'),r.get('data')) in fingerprints]
    if attack=='replay':
        # The first copy was the legitimate captured pair. A later identical
        # auth is replay; use auth, not the unchanged normal raw payload.
        auth=[r for r in candidates if r['can_id']==0x102]
        if len(auth)<2:raise ValueError('replayed authentication not observed on Node B')
        auth_ns=int(auth[1]['timestamp_ns'])
        preceding=[r for r in candidates if r['can_id']==0x100 and 0<=auth_ns-int(r['timestamp_ns'])<100_000_000]
        if not preceding:raise ValueError('historic auth has no matching replay raw on Node B')
        start_ns=int(preceding[-1]['timestamp_ns'])
        candidates=auth[1:]
    else:
        if not candidates:raise ValueError('attack not observed on Node B')
        start_ns=int(candidates[0]['timestamp_ns'])
    end_ns=max(int(r['timestamp_ns']) for r in candidates)+500_000_000
    # Same-node sockets can wake in either order. Receiver correlation gets
    # pre-roll; measured alert latency still uses whole-bus observer times.
    frames=[r for r in receiver if r.get('result') in ('FRAME','TIMEOUT') and start_ns-10_000_000<=int(r['timestamp_ns'])<=end_ns]
    # Replay publications are matched by historic auth bytes; raw replay is
    # accepted only in the explicit unprotected experiment receiver.
    attack_records=[]
    for row in frames:
        cid=row['can_id']
        exact=(cid,row['data']) in fingerprints
        matched_raw=(0x100,row.get('source_data')) in fingerprints
        if attack=='replay':
            match=exact and (cid==0x102 if config!=1 else cid==0x100)
        else:
            match=exact or (cid==0x102 and matched_raw)
        if match:attack_records.append(row)
    accepted=[r for r in attack_records if r['process_result']==2]
    if config==1 and attack=='replay':
        # In OFF mode the historic auth is ignored, but it identifies the
        # immediately preceding published raw. Do not label every identical
        # normal SOC75 frame as an attack.
        accepted=[]
        previous=None
        for row in frames:
            if row['can_id']==0x100:previous=row
            if row['can_id']==0x102 and (0x102,row['data']) in fingerprints and previous is not None \
                    and previous['process_result']==2 and int(row['timestamp_ns'])-int(previous['timestamp_ns'])<100_000_000:
                accepted.append(previous);previous=None
    auth_rejected=[r for r in attack_records if r['process_result']==3 and
        any(reason in r.get('message','') for reason in
            ('reason=MAC_FAIL','reason=COUNTER_REUSE','reason=COUNTER_BACKWARD','reason=COUNTER_WINDOW','reason=AUTH_TIMEOUT'))]
    normal_expected=sum(r.get('result')=='NORMAL_TX' and r['can_id']==0x100 for r in normal)
    normal_delivered=sum(r.get('result')=='FRAME' and r.get('process_result')==2 and
                         r.get('source_data')==BMS.hex() and r['can_id']==(0x100 if config==1 else 0x102)
                         for r in receiver)
    if config==1 and attack=='replay':normal_delivered-=len(accepted)
    if normal_delivered>normal_expected:raise ValueError('ambiguous normal/attack attribution')
    alerts=[r for r in bus if r.get('result')=='BUS_FRAME' and r['can_id']==0x200 and
            start_ns<=int(r['timestamp_ns'])<=end_ns and len(r['data'])==16 and
            bytes.fromhex(r['data'])[0] in (1,2,3,4)]
    detected=bool(alerts) if config==3 else False
    latency=(int(alerts[0]['timestamp_ns'])-start_ns)/1e9 if config==3 and alerts else None
    observed_types=[bytes.fromhex(r['data'])[0] for r in alerts] if config==3 else []
    expected_code=ATTACK_CODES[attack]
    matching=[r for r in alerts if bytes.fromhex(r['data'])[0]==expected_code] if config==3 else []
    published_codes=sorted({bytes.fromhex(r['data'])[0] for r in frames
        if r.get('can_id')==0x200 and r.get('process_result')==2 and len(r.get('data',''))==16
        and any(a['data']==r['data'] for a in alerts)}) if config==3 else []
    if attack=='flooding':
        success=normal_delivered<normal_expected
    elif attack=='fuzzy':
        # Invalid parser input must not be counted as SecOC rejection or as
        # successful pollution just because an unrelated event was published.
        success=any(r['can_id'] in (0x100,0x102) and r.get('soc',0)>100 for r in accepted)
    elif attack=='spoofing':success=any(r.get('soc')==100 for r in accepted)
    else:success=bool(accepted)
    return {'status':'VALID','attack_success':success,'blocked':bool(auth_rejected),
        'detected':detected,'latency_s':latency,'latency_reason':None if latency is not None else 'NO_ALERT_OR_IDS_OFF',
        'expected_attack_code':expected_code,
        'observed_attack_codes':sorted(set(observed_types)),
        'first_alert_attack_code':observed_types[0] if observed_types else None,
        'expected_type_detected':bool(matching) if config==3 else None,
        'expected_type_latency_s':(int(matching[0]['timestamp_ns'])-start_ns)/1e9 if matching else None,
        'ivi_published_attack_codes':published_codes,
        'ivi_expected_type_published':expected_code in published_codes if config==3 else None,
        'attack_accepted':len(accepted),'attack_auth_rejected':len(auth_rejected),
        'attack_parser_rejected':sum(r['process_result']==3 for r in attack_records)-len(auth_rejected),
        'normal_expected':normal_expected,'normal_delivered':normal_delivered,
        'attack_observed_frames':len(candidates),'first_attack_rx_ns':start_ns,
        'latency_clock':'Node-B monotonic, whole-bus observer',
        'bus_load_percent':None,'ui_latency_s':None}


def run_trial(settings,args,config,attack,trial,root):
    run_id=f'{args.run_id}-C{config}-{attack}-T{trial:03d}'
    row={'run_id':args.run_id,'trial_run_id':run_id,'config':config,'attack_type':attack,
         'trial':trial,'seed':trial_seed(attack,trial),'environment':args.environment,
         'protocol':'ICD-v1.6','status':'INVALID'}
    children=[]
    lifetime=60
    values={'run_id':run_id,'secoc':'on','lifetime_s':str(lifetime),'lifetime_ms':str(lifetime*1000)}
    try:
        receiver_key='receiver_off' if config==1 else 'receiver_on'
        observer=Child(render_command(settings['observer'],values),root,'bus');children.append(observer)
        receiver=Child(render_command(settings[receiver_key],values),root,'receiver');children.append(receiver)
        observer.ready(run_id);receiver.ready(run_id)
        ready=[r for r in receiver.snapshot() if r.get('result')=='READY'][-1]
        if ready.get('secoc_on')!=(config!=1):raise ValueError('receiver defence mode differs from config')
        normal=Child(render_command(settings['normal_sender'],values),root,'normal');children.append(normal)
        normal.ready(run_id)
        wait_alive(children,args.baseline)
        if config==3:
            ids=Child(render_command(settings['ids'],values),root,'ids-console');children.append(ids)
            ids.ready(run_id)
            ids_ready=[r for r in ids.snapshot() if r.get('result')=='READY'][-1]
            if ids_ready.get('mode')!='rules+if':raise ValueError('Config 3 requires real IF mode')
            wait_alive(children,args.warmup)
        command=[sys.executable,'-m','security.attack_simulator','--type',attack,
                 '--channel',args.interface,'--duration',str(args.attack_duration),
                 '--seed',str(row['seed']),'--trial',str(trial),'--run-id',run_id,
                 '--log',str(root/'attack.json')]
        if attack=='flooding':command+=['--rate',str(args.flood_rate)]
        if args.confirm_isolated_test_bus:command.append('--confirm-isolated-test-bus')
        if attack=='replay':
            source=normal.snapshot()
            auth=next(r for r in source if r.get('result')=='NORMAL_TX' and r['can_id']==0x102)
            pair={'raw':BMS.hex(),'auth':auth['data']}
            with (root/'replay-pair.json').open('x') as stream:json.dump(pair,stream)
            command+=['--replay-mode','authenticated-pair','--replay-pair-file',str(root/'replay-pair.json')]
        with (root/'attack.stdout').open('x') as out:
            completed=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT,timeout=args.attack_duration+10)
        if completed.returncode:raise RuntimeError('attack process failed; preserve attack manifest')
        wait_alive(children,.5)
        normal.stop();children.remove(normal)
        wait_alive(children,args.drain)
        for child in reversed(children):child.stop()
        children=[]
        tx=[json.loads(line) for line in (root/'attack.json.journal.jsonl').read_text().splitlines()]
        attack_manifest=json.loads((root/'attack.json').read_text())
        if attack_manifest['status']!='COMPLETE':raise ValueError('attack manifest incomplete')
        receiver_rows=receiver.snapshot()
        if not any(r.get('result')=='FRAME' and r.get('process_result')==2 and
                   r.get('source_data')==BMS.hex() for r in receiver_rows):
            raise ValueError('no normal baseline publication')
        row.update(summarize_observations(config,attack,tx,observer.snapshot(),receiver_rows,normal.snapshot()))
        row['input_sha256']=hashlib.sha256(json.dumps(
            [(r['can_id'],r['data']) for r in tx if r.get('result')=='TX_ACCEPTED']).encode()).hexdigest()
    except KeyboardInterrupt:
        row.update(status='INVALID',reason='INTERRUPTED',interrupted=True)
    except (OSError,RuntimeError,ValueError,TimeoutError,subprocess.TimeoutExpired,StopIteration,KeyError,TypeError) as error:
        row.update(status='INVALID',reason=str(error) or type(error).__name__)
    finally:
        for child in reversed(children):
            try:child.stop()
            except (OSError,RuntimeError) as error:row.update(status='INVALID',reason=f'cleanup: {error}')
        row['artifact_sha256']={p.name:file_hash(p) for p in root.iterdir() if p.is_file()}
        with (root/'result.json').open('x') as output:json.dump(row,output,indent=2)
    return row


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings',required=True)
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--environment',choices=('vcan','physical-can'),required=True)
    parser.add_argument('--interface',default='vcan0')
    parser.add_argument('--trials',type=int,default=1)
    parser.add_argument('--baseline',type=float,default=2)
    parser.add_argument('--warmup',type=float,default=1.2)
    parser.add_argument('--drain',type=float,default=.5)
    parser.add_argument('--cooldown',type=float,default=1)
    parser.add_argument('--attack-duration',type=float,default=3)
    parser.add_argument('--flood-rate',type=float,default=3000)
    parser.add_argument('--confirm-isolated-test-bus',action='store_true')
    parser.add_argument('--confirm-product-ecu-stopped',action='store_true')
    args=parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',args.run_id):
        parser.error('run-id must be a safe 1..80 character identifier')
    if not 1<=args.trials<=100:parser.error('trials must be in [1,100]')
    if any(not math.isfinite(v) or not .5<=v<=5 for v in (args.baseline,args.warmup,args.drain,args.cooldown)):
        parser.error('fixed pilot phases must be in [0.5,5] seconds')
    validate_safety(args.interface,args.attack_duration,args.flood_rate,args.confirm_isolated_test_bus)
    if (args.environment=='vcan')!=args.interface.startswith('vcan'):parser.error('environment/interface mismatch')
    if not args.confirm_product_ecu_stopped:parser.error('controlled fixture requires --confirm-product-ecu-stopped')
    settings=json.loads(Path(args.settings).read_text())
    try:validate_settings(settings,args.environment)
    except (ValueError,TypeError) as error:parser.error(str(error))
    if not isinstance(settings,dict):parser.error('settings must be a JSON object')
    for name in ('observer','receiver_on','receiver_off','normal_sender','ids'):
        try:render_command(settings[name],{'run_id':args.run_id,'secoc':'on','lifetime_s':'60','lifetime_ms':'60000'})
        except (ValueError,KeyError,TypeError) as error:parser.error(f'{name}: {error}')
    if args.environment=='physical-can' and settings.get('observer_receiver_same_node') is not True:
        parser.error('physical trials require observer_receiver_same_node=true and remote Node B commands')
    if args.environment=='physical-can' and any(Path(settings[name][0]).name!='ssh' for name in ('observer','receiver_on','receiver_off')):
        parser.error('physical Node B observation must use explicit remote SSH commands')
    root=Path(args.output_dir);root.mkdir(parents=True,exist_ok=False)
    manifest={'schema':'ablation-v1','run_id':args.run_id,'environment':args.environment,
              'trials_per_cell':args.trials,'expected_trials':12*args.trials,
              'settings_sha256':file_hash(args.settings),'fixture':'normal-sender-SOC75-signed-all-configs',
              'configuration_variable':'receiver authentication and IDS; sender input is held constant',
              'tool_sha256':{name:file_hash(Path(__file__).parents[1]/name) for name in
                  ('attack_simulator.py','capture_normal.py','ids/runtime.py','secoc_module.py',
                   'experiments/run_ablation.py','experiments/normal_sender.py',
                   'experiments/bus_observer.py','experiments/summarize_ablation.py')},
              'phases':{key:getattr(args,key) for key in ('baseline','warmup','drain','cooldown','attack_duration','flood_rate')}}
    with (root/'manifest.json').open('x') as stream:json.dump(manifest,stream,indent=2)
    with (root/'settings.json').open('xb') as stream:stream.write(Path(args.settings).read_bytes())
    invalid=0
    with (root/'attempts.jsonl').open('x') as ledger:
        for trial in range(args.trials):
            for attack in ATTACKS:
                for config in (1,2,3):
                    directory=root/f'C{config}-{attack}-T{trial:03d}';directory.mkdir()
                    row=run_trial(settings,args,config,attack,trial,directory)
                    invalid+=row['status']!='VALID'
                    ledger.write(json.dumps(row)+'\n');ledger.flush()
                    print(json.dumps({k:row.get(k) for k in ('config','attack_type','trial','status','reason')}),flush=True)
                    if row.get('interrupted'):return 130
                    time.sleep(args.cooldown)
    return 2 if invalid else 0


if __name__=='__main__':raise SystemExit(main())
