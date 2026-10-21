"""Product ECU campaign: attacker Pi owns injection; ECU/IDS and IVI run remotely.

Reference metrics retain the live_ablation definitions. IVI alert publication
is separate evidence; clocks from different hosts are never subtracted.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import signal
import statistics
import time

from security.attacks.attack_simulator import ATTACK_TYPES, validate
from security.experiments.ablation_core import trial_seed
from security.experiments.can_capture import CaptureSocket, inspect_interface, sha256, interrupted
from security.experiments.live_ablation import collect, captured_replay
from security.experiments.live_receiver import ReferenceReceiver
from security.experiments.live_trial import TrialWindows, judge_trial
from security.experiments.run_ablation import Child, render_command
from security.experiments.summarize_live import read_run
from security.experiments.validate_m5_settings import ssh_target


def validate_settings(settings):
    values = {'run_id':'check','lifetime_s':'60','lifetime_ms':'60000','secoc':'on','sensor_mode':'constant'}
    targets = {}
    for role in ('ecu','ids','receiver_on','receiver_off'):
        command = settings.get(role)
        render_command(command, values)
        if Path(command[0]).name != 'ssh' or '-n' in command or '-t' in command or '-tt' in command:
            raise ValueError(f'{role}: non-PTY SSH with connected stdin is required')
        text = ' '.join(command)
        if 'REPLACE_' in text or 'security.experiments.remote_process' not in text:
            raise ValueError(f'{role}: resolve placeholders and use remote_process')
        if '{run_id}' not in text or '{lifetime_s}' not in text:
            raise ValueError(f'{role}: run_id and lifetime placeholders required')
        targets[role] = ssh_target(command)
    if targets['ecu'] != targets['ids'] or targets['receiver_on'] != targets['receiver_off'] or targets['ecu'] == targets['receiver_on']:
        raise ValueError('ECU/IDS must share A; both receivers must share distinct B')
    if '{secoc}' not in ' '.join(settings['ecu']) or '{sensor_mode}' not in ' '.join(settings['ecu']):
        raise ValueError('ECU command must expose defence and sensor mode')
    if '--train-normal' not in ' '.join(settings['ids']) or '--calibrate-normal' not in ' '.join(settings['ids']):
        raise ValueError('physical campaign requires independent IF training/calibration on A')
    return targets


class Actors:
    def __init__(self):
        self.children = []

    def start(self, command, root, name):
        child = Child(command, root, name)
        self.children.append(child)
        return child

    def check(self):
        for child in self.children:
            if child.read_error is not None:raise child.read_error
        if any(c.process.poll() is not None for c in self.children):
            raise RuntimeError('remote actor exited; inspect preserved process logs')

    def close(self):
        errors = []
        for child in reversed(self.children):
            try:child.stop()
            except (OSError, RuntimeError) as error:errors.append(str(error))
        return errors


def run_case(settings, args, config, attack, root):
    root.mkdir()
    run_id = f'{args.run_id}-C{config}-{attack}'
    lifetime = math.ceil(120 + args.trials * (args.baseline + args.duration + args.post))
    values = {'run_id':run_id,'lifetime_s':str(lifetime),'lifetime_ms':str(lifetime*1000),
              'secoc':'off' if config == 1 else 'on','sensor_mode':args.sensor_mode}
    manifest = {'run_id':run_id,'environment':'physical','config':config,'ids_mode':'rules+if' if config==3 else 'off',
                'attacks':[attack],'trials_per_attack':args.trials,'start_trial':getattr(args,'start_trial',1),'previous_run_id':None,
                'rate_fps':args.rate,'attack_s':args.duration,'baseline_s':args.baseline,'post_s':args.post,
                'sensor_mode':args.sensor_mode,'observer':'reference_receiver_on_attacker',
                'product_verdict':'NOT_RUN','settings_sha256':sha256(args.settings),
                'clock':'attacker kernel receive clock; injection is MSG_CONFIRM own echo',
                'ids_rule_event_counts':None,'ids_log_note':'Original IDS event log remains on Node A; no cross-host timestamp slicing.'}
    actors, bus, active, status = Actors(), None, None, 'COMPLETE'
    resilient = getattr(args, 'resilient', False)
    observers = []
    pending_row = None
    with (root/'attempts.jsonl').open('x') as ledger:
        try:
            key = Path(args.key).read_bytes()
            if len(key)!=32:raise ValueError('reference verification requires a 32-byte key file')
            bus = CaptureSocket(args.interface, transmit=True)
            quiet_end = time.monotonic()+.5
            while time.monotonic()<quiet_end:
                if bus.receive():raise RuntimeError('bus active before owned ECU start')
            if resilient:
                for role in ('observer_a', 'observer_b'):
                    observer = actors.start(render_command(settings[role], values), root, role)
                    observer.ready(run_id)
                    observers.append(observer)
            receiver = actors.start(render_command(settings['receiver_off' if config==1 else 'receiver_on'],values),root,'ivi')
            receiver.ready(run_id)
            ready = [r for r in receiver.snapshot() if r.get('result')=='READY'][-1]
            if ready.get('secoc_on') != (config!=1):raise ValueError('IVI defence mode mismatch')
            actors.start(render_command(settings['ecu'],values),root,'ecu')
            if config==3:
                ids = actors.start(render_command(settings['ids'],values),root,'ids-console')
                ids.ready(run_id,timeout=60)
                ready = [r for r in ids.snapshot() if r.get('result')=='READY'][-1]
                if ready.get('mode')!='rules+if' or not ready.get('send_alerts'):
                    raise ValueError('IDS must be rules+if with alert transmission')
            reference = ReferenceReceiver(config!=1,key)
            with (root/'warmup.jsonl').open('x') as stream:
                collect(bus,reference,max(3,args.baseline),stream,actors)
            for trial in range(manifest['start_trial'],manifest['start_trial']+args.trials):
                active={'run_id':run_id,'environment':'physical','config':config,'ids_mode':manifest['ids_mode'],
                        'attack_type':attack,'trial':trial,'seed':trial_seed(attack,trial)}
                raw=root/f'{attack}-{trial:03d}.jsonl'
                before=len(receiver.snapshot())
                with raw.open('x') as stream:
                    if resilient:
                        from security.experiments.test360_support import phase_barrier
                        phase_barrier(observers, 'baseline', actors)
                    baseline=collect(bus,reference,args.baseline,stream,actors)
                    if sum(o.kind=='PUBLISHED' and o.can_id==0x100 for r in baseline[0] for o in r.outcomes)<5*args.baseline:
                        raise RuntimeError('baseline ECU/reference not ready')
                    if not resilient and any(r.can_id==0x200 for r in baseline[0]):raise RuntimeError('baseline IDS alert')
                    replay=captured_replay(baseline[0],config!=1) if attack=='replay' else None
                    if resilient:phase_barrier(observers, 'attack', actors)
                    injection=collect(bus,reference,args.duration,stream,actors,attack,args.rate,active['seed'],replay)
                    if resilient:phase_barrier(observers, 'post', actors)
                    post=collect(bus,reference,args.post,stream,actors)
                if resilient:phase_barrier(observers, 'idle', actors)
                window=TrialWindows(baseline[4],injection[4],post[4],post[5],injection[3])
                row=judge_trial(config,attack,baseline[0]+injection[0]+post[0],window,injection[1],injection[2],bus.dropped)
                alerts={r.data.hex() for r in injection[0]+post[0] if r.can_id==0x200 and not r.own
                        and injection[3] is not None and r.t>=injection[3]}
                published={bytes.fromhex(r['data'])[0] for r in receiver.snapshot()[before:]
                           if r.get('result')=='FRAME' and r.get('can_id')==0x200 and r.get('process_result')==2
                           and r.get('data') in alerts}
                row.update(ivi_published_attack_codes=sorted(published),
                           ivi_expected_type_published=row['expected_attack_code'] in published if config==3 else None,
                           ivi_evidence='same alert payload in B publication log; no remote clock subtraction; pixels NOT_RUN')
                if resilient:
                    from security.experiments.test360_support import add_evidence
                    row.update(active)
                    add_evidence(row, injection[0], observers)
                row.update(active,raw_file=raw.name,raw_sha256=sha256(raw))
                if resilient:
                    pending_row = row
                else:
                    ledger.write(json.dumps(row)+'\n');ledger.flush()
                print(json.dumps({k:row[k] for k in ('config','attack_type','trial','status')}),flush=True)
                active=None
        except KeyboardInterrupt:
            status='INTERRUPTED'
        except (OSError,ValueError,RuntimeError,TimeoutError) as error:
            status='ERROR';manifest['error']=str(error)
            if resilient:
                from security.experiments.test360_support import recoverable
                manifest['recoverable'] = recoverable(error)
        finally:
            errors=actors.close()
            if resilient:
                try:
                    manifest['cleanup_confirmed'] = all(any(r.get('result') in ('REMOTE_STOPPED', 'OBSERVER_STOPPED')
                        and r.get('run_id') == run_id for r in child.snapshot()) for child in actors.children)
                except OSError:
                    manifest['cleanup_confirmed'] = False
                if not manifest['cleanup_confirmed']:errors.append('remote cleanup acknowledgement missing')
            if errors:status='ERROR';manifest['cleanup_errors']=errors
            if bus:bus.close()
            if pending_row is not None:
                # Read the complete IVI log after SSH/log threads have drained.
                from security.experiments.test360_support import classification
                published={bytes.fromhex(r['data'])[0] for r in receiver.snapshot()[before:]
                           if r.get('result')=='FRAME' and r.get('can_id')==0x200
                           and r.get('process_result')==2 and r.get('data') in alerts}
                pending_row['ivi_published_attack_codes']=sorted(published)
                pending_row['ivi_expected_type_published']=pending_row['expected_attack_code'] in published if config==3 else None
                pending_row['ivi_type_result']=(classification(published,pending_row['expected_attack_code']) if config==3
                    else 'NOT_EVALUATED') if pending_row['status']=='VALID' else 'INVALID'
                ledger.write(json.dumps(pending_row)+'\n');ledger.flush()
            if active:ledger.write(json.dumps({**active,'status':'INVALID','invalid_reason':status})+'\n')
    manifest['status']=status
    manifest['files_sha256']={p.name:sha256(p) for p in root.iterdir() if p.is_file()}
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return status


def summarize_campaign(root):
    campaign=json.loads((root/'campaign.json').read_text())
    if sha256(root/'settings.json')!=campaign['settings_sha256']:raise ValueError('settings hash mismatch')
    groups=[]
    complete_cases=0
    for config in (1,2,3):
        for attack in ATTACK_TYPES:
            directory=root/f'C{config}-{attack}'
            rows=[]
            if (directory/'manifest.json').exists():
                manifest,rows=read_run(directory)
                if manifest['settings_sha256']!=campaign['settings_sha256']:raise ValueError('case settings changed')
                if manifest['status']=='COMPLETE' and len(rows)==campaign['trials']:complete_cases+=1
            valid=[r for r in rows if r['status']=='VALID']
            measured=[r['attack_success'] for r in valid if r['attack_success'] is not None]
            latencies=[r['detect_latency_s'] for r in valid if r['detect_latency_s'] is not None]
            deliveries=[r['delivery_ratio'] for r in valid if r.get('delivery_ratio') is not None]
            groups.append({'config':config,'attack':attack,'attempts':len(rows),'valid':len(valid),
                           'invalid':len(rows)-len(valid),'not_run':campaign['trials']-len(rows),
                           'detected':sum(r['detected'] for r in valid),
                           'detection_rate':sum(r['detected'] for r in valid)/len(valid) if valid else None,
                           'blocked_rate':sum(r['blocked'] for r in valid)/len(valid) if valid else None,
                           'attack_success_evaluated':len(measured),
                           'attack_success_rate':sum(measured)/len(measured) if measured else None,
                           'mean_delivery_ratio':statistics.mean(deliveries) if deliveries else None,
                           'mean_detected_latency_s':statistics.mean(latencies) if latencies else None,
                           'first_alert_type_counts':{str(code):sum(r.get('first_alert_attack_code')==code for r in valid) for code in (None,1,2,3,4)} if config==3 else None,
                           'expected_type_detected':sum(r.get('expected_type_detected') is True for r in valid) if config==3 else None,
                           'ivi_expected_type_published':sum(r.get('ivi_expected_type_published') is True for r in valid) if config==3 else None})
    return {'planned_trials':12*campaign['trials'],'attempted_trials':sum(r['attempts'] for r in groups),
            'complete_cases':complete_cases,
            'valid_trials':sum(r['valid'] for r in groups),'summary':groups,
            'note':'Reference defence metrics and IVI publications are distinct. Collection completeness is not acceptance.'}


def main(argv=None, *, test360=False):
    description = ('Test-only campaign: 3 configurations x 4 attacks x 30 trials = 360. '
                   'No pilot required; this is not the official campaign.') if test360 else __doc__
    parser=argparse.ArgumentParser(description=description)
    for name in ('settings','out','run-id','key'):parser.add_argument('--'+name,required=True)
    if test360:
        parser.set_defaults(stage='test360')
    else:
        parser.add_argument('--stage',choices=('pilot','official'),required=True)
        parser.add_argument('--pilot-dir')
    parser.add_argument('--interface',default='can0')
    parser.add_argument('--sensor-mode',choices=('constant','ads1115'),default='constant')
    for name,default in (('rate',1000),('duration',3),('baseline',2),('post',1)):
        parser.add_argument('--'+name,type=float,default=default)
    parser.add_argument('--i-am-on-a-test-bus',action='store_true')
    args=parser.parse_args(argv)
    args.trials={'pilot':1,'official':100,'test360':30}[args.stage]
    try:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,59}',args.run_id):raise ValueError('invalid run-id')
        error=validate('flooding',args.interface,args.rate,args.duration,args.i_am_on_a_test_bus)
        if error:raise ValueError(error)
        if not all(math.isfinite(v) and 1<=v<=60 for v in (args.baseline,args.post)):raise ValueError('invalid phases')
        settings=json.loads(Path(args.settings).read_text());validate_settings(settings)
        phases={k:getattr(args,k) for k in ('rate','duration','baseline','post','sensor_mode','interface')}
        if args.stage=='official':
            if not args.pilot_dir:raise ValueError('official stage requires a physical pilot')
            pilot=Path(args.pilot_dir)
            summary=summarize_campaign(pilot)
            previous=json.loads((pilot/'campaign.json').read_text())
            if previous['trials']!=1 or summary['valid_trials']!=12 or summary['complete_cases']!=12:
                raise ValueError('12 valid pilot trials with clean case completion required')
            if previous['settings_sha256']!=sha256(args.settings) or previous['phases']!=phases:
                raise ValueError('settings/phases differ from pilot')
        inspect_interface(args.interface,'physical')
        if len(Path(args.key).read_bytes())!=32:raise ValueError('key must have 32 bytes')
    except (OSError,ValueError,KeyError,TypeError) as error:parser.error(str(error))
    root=Path(args.out);root.mkdir(parents=True,exist_ok=False)
    (root/'settings.json').write_bytes(Path(args.settings).read_bytes())
    campaign={'run_id':args.run_id,'stage':args.stage,'trials':args.trials,'phases':phases,'settings_sha256':sha256(args.settings),
              'source_sha256':{p.as_posix():sha256(p) for p in sorted(Path('security').rglob('*.py'))}}
    (root/'campaign.json').write_text(json.dumps(campaign,indent=2)+'\n')
    old=signal.signal(signal.SIGTERM,interrupted)
    status='COMPLETE'
    try:
        for config in (1,2,3):
            for attack in ATTACK_TYPES:
                status=run_case(settings,args,config,attack,root/f'C{config}-{attack}')
                if status!='COMPLETE':break
            if status!='COMPLETE':break
    except KeyboardInterrupt:status='INTERRUPTED'
    finally:
        signal.signal(signal.SIGTERM,old)
        result=summarize_campaign(root)
        result['status']=status
        result['stage']=args.stage
        (root/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    return 130 if status=='INTERRUPTED' else 2 if status!='COMPLETE' or result['valid_trials']!=12*args.trials else 0


if __name__=='__main__':raise SystemExit(main())
