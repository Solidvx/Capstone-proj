"""PC-owned CAN campaign: SSH management, keyless Pi3 injection, ECU/IVI defence.

Run on macOS/Linux PC (or WSL). PC needs no CAN device or SecOC key.
"""
import json
import math
import shlex
from pathlib import Path
import subprocess
import time

from security.experiments.live_three_node import Actors, validate_settings
from security.experiments.run_ablation import render_command
from security.experiments.can_capture import sha256
from security.experiments.ablation_core import trial_seed
from security.experiments.test360_support import phase_barrier, classification, validate_extra
from security.experiments.validate_m5_settings import ssh_target

CODES={'fuzzy':1,'replay':2,'spoofing':3,'flooding':4}


def validate_pc_settings(settings):
    if not isinstance(settings,dict) or settings.get('protocol')!='legacy-v1':
        raise ValueError('pc_campaign is legacy-v1 only; select protocol=legacy-v1 explicitly. '
                         'session-v2 is not implemented in this runner')
    targets=validate_settings(settings)
    validate_extra(settings,targets)
    for role in ('ecu','ids','receiver_on','receiver_off'):
        tokens=shlex.split(settings[role][-1])
        positions=[index for index,value in enumerate(tokens) if value=='--protocol']
        if len(positions)!=1 or positions[0]+1>=len(tokens) or tokens[positions[0]+1]!='legacy-v1':
            raise ValueError(f'{role}: explicit --protocol legacy-v1 required; mixed/default protocols rejected')
        if any(value.split('=',1)[0] in ('--session-policy','--session-context-fd','--ids-settings') for value in tokens):
            raise ValueError(f'{role}: session-v2 options are incompatible with this legacy campaign')
    values={'run_id':'check','lifetime_s':'60','lifetime_ms':'60000','secoc':'on','sensor_mode':'constant'}
    required=('attacker','health_c','ids_fetch')
    for role in required:
        command=settings[role]
        if not isinstance(command,list) or not command or not all(isinstance(v,str) for v in command):
            raise ValueError(f'{role}: SSH argv required')
        text=' '.join(command)
        if Path(command[0]).name!='ssh' or any(v in command for v in ('-n','-t','-tt')) or 'REPLACE_' in text:
            raise ValueError(f'{role}: resolved non-PTY SSH required')
        for part in command:part.format_map(values)
        target=ssh_target(command)
        if role=='ids_fetch' and target!=targets['ecu']:raise ValueError('IDS log must be fetched from ECU')
        if role=='attacker':
            render_command(command,values)
            if ('security.experiments.can_attack_worker' not in text or 'remote_process' in text
                or '{run_id}' not in text or '--i-am-on-a-test-bus' not in text):
                raise ValueError('direct bounded keyless attacker required')
            if '--key' in text or '--secoc-key' in text:raise ValueError('Pi3 must not receive a SecOC key')
            targets['attacker']=target
    if ssh_target(settings['health_c'])!=targets['attacker'] or targets['attacker'] in (targets['ecu'],targets['receiver_on']):
        raise ValueError('attacker must be distinct Node C; health_c must use its SSH target')
    return targets


def wait_for(actors, duration, child=None, trial=None):
    deadline=time.monotonic()+duration
    while time.monotonic()<deadline:
        actors.check()
        if child is not None:
            done=[r for r in child.snapshot() if r.get('result')=='ATTACK_DONE' and r.get('trial')==trial]
            if done:return done[-1]
        time.sleep(.01)
    if child is not None:raise RuntimeError('attack worker timeout')


def observer_window(records):
    def barrier(phase):
        return next(r['t'] for r in records if r.get('result')=='PHASE' and r.get('phase')==phase)
    return barrier('baseline'),barrier('attack'),barrier('idle')


def unexpected_off_alert(records, worker, trial):
    """Exclude payloads injected by this trial; this is not sender authentication."""
    injected = {(r['can_id'], r['data']) for r in worker
                if r.get('result') == 'TX' and r.get('trial') == trial}
    return any(r.get('result') == 'OBS_FRAME' and r.get('can_id') == 0x200
               and (r['can_id'], r.get('data')) not in injected for r in records)


def evaluate(config,attack,trial,worker,observers,ivi,ids_events=None):
    """Remote arrival and IVI service evidence; never infer attacker-key reference metrics."""
    tx=[r for r in worker if r.get('result')=='TX' and r.get('trial')==trial]
    done=next(r for r in worker if r.get('result')=='ATTACK_DONE' and r.get('trial')==trial)
    signatures={(r['can_id'],r['data']) for r in tx}
    reasons=[]
    if not tx:reasons.append('NO_INJECTION')
    if done['tx_errors']:reasons.append('TX_ERRORS')
    arrivals={}
    codes=set()
    for name,records in zip(('ecu','ivi'),observers):
        baseline,attack_start,end=observer_window(records)
        frames=[r for r in records if r.get('result')=='OBS_FRAME']
        base=[r for r in frames if r.get('phase')=='baseline']
        attack_frames=[r for r in frames if r.get('phase') in ('attack','post')]
        candidates=[r for r in attack_frames if (r['can_id'],r['data']) in signatures]
        drops=[r.get('rx_dropped',0) for r in records if 'rx_dropped' in r]
        dropped=max(drops,default=0)-min(drops,default=0)
        arrivals[name]={'matching_frames':len(candidates),'rx_dropped':dropped,
                        'baseline_bms_frames':sum(r['can_id']==0x100 for r in base),
                        'distinct_from_baseline_frames':sum((r['can_id'],r['data']) not in
                            {(b['can_id'],b['data']) for b in base} for r in candidates)}
        if not candidates:reasons.append(name.upper()+'_ARRIVAL_UNVERIFIED')
        if dropped or any(r.get('error') for r in frames):reasons.append(name.upper()+'_CAPTURE_ERROR')
        if not arrivals[name]['baseline_bms_frames']:reasons.append(name.upper()+'_NO_BASELINE')
        if any(r['can_id']==0x200 for r in base):reasons.append('BASELINE_ALERTS')
        if name=='ivi':
            codes={int(r['data'][:2],16) for r in attack_frames if r['can_id']==0x200 and r.get('data')}
            # Both observer and IVI timestamps are Linux CLOCK_MONOTONIC on Node B.
            baseline_published=[r for r in ivi if r.get('result')=='FRAME' and r.get('can_id')==(0x100 if config==1 else 0x102)
                and r.get('process_result')==2 and baseline<=int(r['timestamp_ns'])/1e9<attack_start]
            if not baseline_published:reasons.append('IVI_BASELINE_NOT_PUBLISHED')
            published={int(r['data'][:2],16) for r in ivi if r.get('result')=='FRAME'
                and r.get('can_id')==0x200 and r.get('process_result')==2
                and attack_start<=int(r['timestamp_ns'])/1e9<=end and r.get('data')}
    if config!=3 and any(unexpected_off_alert(records,worker,trial) for records in observers):
        reasons.append('ALERT_WITH_IDS_OFF')
    expected=CODES[attack]
    ids_codes=set();sent_payloads=set();linked_codes=set()
    if config==3:
        if ids_events is None:reasons.append('IDS_LOG_UNAVAILABLE')
        else:
            _,a_start,a_end=observer_window(observers[0])
            scoped=[r for r in ids_events if a_start<=r.get('timestamp',-1)<=a_end]
            ids_codes={r['attack_type'] for r in scoped if r.get('result')=='ANOMALY' and r.get('attack_type') in (1,2,3,4)}
            sent_payloads={r['data'] for r in scoped if r.get('result')=='ALERT_SENT'}
            _,b_start,b_end=observer_window(observers[1])
            linked_codes={int(r['data'][:2],16) for r in ivi if r.get('result')=='FRAME' and r.get('can_id')==0x200
                and r.get('process_result')==2 and r.get('data') in sent_payloads
                and b_start<=int(r['timestamp_ns'])/1e9<=b_end}
    status='INVALID' if reasons else 'VALID'
    return {'status':status,'invalid_reason':'|'.join(sorted(set(reasons))), 'trial_completed':True,
            'expected_attack_code':expected,'observed_attack_codes':sorted(codes),
            'ivi_published_attack_codes':sorted(published),'ecu_ids_attack_codes':sorted(ids_codes),
            'ivi_ids_linked_codes':sorted(linked_codes),
            'ecu_ids_type_result':('INVALID' if reasons else classification(ids_codes,expected)) if config==3 else 'NOT_EVALUATED','attack_sent':len(tx),'attack_tx_errors':done['tx_errors'],
            'remote_arrival':arrivals,'detected':bool(codes),'blocked':None,'attack_success':None,
            'detect_latency_s':None,'blocking_evaluated':False,
            'bus_type_result':('INVALID' if reasons else classification(codes,expected)) if config==3 else 'NOT_EVALUATED',
            'ivi_type_result':('INVALID' if reasons else classification(linked_codes,expected)) if config==3 else 'NOT_EVALUATED',
            'arrival_note':'Remote payload matches are arrival candidates, not authenticated sender identity; replay/baseline collisions remain ambiguous.',
            'metric_note':'No attacker-side SecOC verification. Blocking/success/latency not evaluated; IVI publication uses Node B monotonic windows.'}


def run_case(settings,args,config,attack,root):
    root.mkdir()
    run_id=f'{args.run_id}-C{config}-{attack}'
    lifetime=math.ceil(120+args.trials*(args.baseline+args.duration+args.post+25))
    values={'run_id':run_id,'lifetime_s':str(lifetime),'lifetime_ms':str(lifetime*1000),
            'sensor_mode':args.sensor_mode,'secoc':'off' if config==1 else 'on'}
    manifest={'run_id':run_id,'environment':'physical','protocol':'legacy-v1','config':config,'ids_mode':'rules+if' if config==3 else 'off',
              'attacks':[attack],'start_trial':args.start_trial,'trials_per_attack':args.trials,
              'settings_sha256':sha256(args.settings),'controller':'PC','attacker':'keyless CAN worker',
              'recoverable':False,'cleanup_confirmed':False}
    actors=Actors();observers=[];pending=[];active=None;receiver=None;status='COMPLETE';ids_started=False
    try:
        for role in ('observer_a','observer_b'):
            child=actors.start(render_command(settings[role],values),root,role)
            child.ready(run_id);observers.append(child)
        # No owned transmitter yet: reject an already active test bus.
        wait_for(actors,.5)
        if any(r.get('result')=='OBS_FRAME' for c in observers for r in c.snapshot()):
            raise ValueError('bus active before owned ECU start')
        receiver=actors.start(render_command(settings['receiver_off' if config==1 else 'receiver_on'],values),root,'ivi')
        receiver.ready(run_id)
        ready=next(r for r in receiver.snapshot() if r.get('result')=='READY')
        if ready.get('secoc_on')!=(config!=1):raise ValueError('IVI defence mode mismatch')
        actors.start(render_command(settings['ecu'],values),root,'ecu')
        if config==3:
            ids=actors.start(render_command(settings['ids'],values),root,'ids-console');ids_started=True
            ids.ready(run_id,timeout=60)
            ready=next(r for r in ids.snapshot() if r.get('result')=='READY')
            if getattr(args,'attack_profile','mixed-v1')=='isolated-v1' and ready.get('classification_version')!='evidence-v3':
                raise ValueError('update ECU IDS: evidence-v3 required')
            if ready.get('mode')!='rules+if' or not ready.get('send_alerts'):raise ValueError('IDS mode mismatch')
        attacker=actors.start(render_command(settings['attacker'],values),root,'attacker')
        attacker.ready(run_id)
        if not any(r.get('role')=='keyless-can-attacker' for r in attacker.snapshot()):raise ValueError('wrong attacker worker')
        profile = getattr(args,'attack_profile','mixed-v1')
        if profile == 'isolated-v1' and not any(profile in r.get('profiles',[]) for r in attacker.snapshot()):
            raise ValueError('update Pi3 worker: isolated-v1 profile unsupported')
        wait_for(actors,max(3,args.baseline))
        for trial in range(args.start_trial,args.start_trial+args.trials):
            active={'run_id':run_id,'environment':'physical','config':config,'ids_mode':manifest['ids_mode'],
                    'attack_type':attack,'trial':trial,'seed':trial_seed(attack,trial)}
            offsets=[len(c.snapshot()) for c in observers]
            phase_barrier(observers,'baseline',actors)
            wait_for(actors,args.baseline)
            if any(not any(r.get('result')=='OBS_FRAME' and r.get('can_id')==0x100
                           for r in c.snapshot()[offset:]) for c,offset in zip(observers,offsets)):
                raise RuntimeError('baseline ECU/reference not ready')
            b_start=next(r['t'] for r in observers[1].snapshot()[offsets[1]:]
                         if r.get('result')=='PHASE' and r.get('phase')=='baseline')
            baseline_deadline=time.monotonic()+5
            while not any(r.get('result')=='FRAME' and r.get('can_id')==(0x100 if config==1 else 0x102)
                          and r.get('process_result')==2 and int(r['timestamp_ns'])/1e9>=b_start
                          for r in receiver.snapshot()):
                actors.check()
                if time.monotonic()>=baseline_deadline:
                    raise ValueError('IVI baseline not published: inspect keys, configuration and receiver log before attacking')
                time.sleep(.02)
            phase_barrier(observers,'attack',actors)
            request={'trial':trial,'attack':attack,'rate':(args.rate if profile=='mixed-v1' or attack=='flooding' else 5),'duration':args.duration,'profile':profile,
                     'seed':active['seed'],'interface':args.interface,'secoc':config!=1}
            attacker.process.stdin.write(json.dumps(request)+'\n');attacker.process.stdin.flush()
            wait_for(actors,args.duration+10,attacker,trial)
            phase_barrier(observers,'post',actors);wait_for(actors,args.post)
            phase_barrier(observers,'idle',actors)
            captures=[c.snapshot()[offset:] for c,offset in zip(observers,offsets)]
            pending.append((active,captures))
            print(json.dumps({'result':'TRIAL_COLLECTED',**active}),flush=True)
            active=None
            if config!=3 and any(unexpected_off_alert(records,attacker.snapshot(),trial) for records in captures):
                raise ValueError('IDS OFF configuration emitted alerts')
    except KeyboardInterrupt:status='INTERRUPTED'
    except (OSError,ValueError,RuntimeError,TimeoutError) as error:
        status='ERROR';manifest['error']=str(error)
        manifest['recoverable']=isinstance(error,(RuntimeError,TimeoutError)) and any(s in str(error) for s in
            ('remote actor exited','baseline ECU/reference not ready','attack worker timeout','observer phase timeout'))
    finally:
        errors=actors.close()
        try:
            manifest['cleanup_confirmed']=not errors and all(any(r.get('run_id')==run_id and r.get('result') in
                ('REMOTE_STOPPED','OBSERVER_STOPPED','ATTACKER_STOPPED') for r in child.snapshot()) for child in actors.children)
        except OSError:manifest['cleanup_confirmed']=False
        if not manifest['cleanup_confirmed']:status='ERROR';manifest['cleanup_errors']=errors or ['missing remote cleanup acknowledgement']
        elif status=='COMPLETE' and any(r.get('result')=='REMOTE_STOPPED' and r.get('exit_code',0)!=0
                                       for c in actors.children for r in c.snapshot()):
            status='ERROR';manifest['error']='remote process exited unsuccessfully';manifest['recoverable']=False
    # All process logs now drained; fetch the ECU's original IDS event log as well.
    if ids_started:
        try:
            with (root/'ids-events.jsonl').open('x') as output, (root/'ids-fetch.stderr').open('x') as error_log:
                command=[v.format_map(values) for v in settings['ids_fetch']]
                subprocess.run(command,stdout=output,stderr=error_log,check=True,timeout=60)
        except (OSError,subprocess.SubprocessError) as error:
            status='ERROR';manifest['error']='IDS log collection failed: '+str(error);manifest['recoverable']=False
    ids_events=None
    if ids_started and (root/'ids-events.jsonl').exists():
        try:
            ids_events=[json.loads(line) for line in (root/'ids-events.jsonl').read_text().splitlines() if line.strip()]
            if not any(r.get('result')=='START' and r.get('run_id')==run_id for r in ids_events):
                raise ValueError('missing IDS log START/run_id')
        except (ValueError,OSError) as error:
            status='ERROR';manifest['error']='invalid IDS event log: '+str(error);manifest['recoverable']=False;ids_events=None
    with (root/'attempts.jsonl').open('x') as ledger:
        for identity,captures in pending:
            row=evaluate(config,attack,identity['trial'],attacker.snapshot(),captures,receiver.snapshot(),ids_events)
            row.update(identity)
            ledger.write(json.dumps(row)+'\n')
        if active:ledger.write(json.dumps({**active,'status':'INVALID','invalid_reason':status,'trial_completed':False})+'\n')
    manifest['status']=status
    manifest['files_sha256']={p.name:sha256(p) for p in root.iterdir() if p.is_file()}
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return status


def main(argv=None):
    from security.experiments.live_three_node_test360 import main as campaign
    return campaign(argv,pc=True)


if __name__=='__main__':raise SystemExit(main())
