"""PC controller for raw C1 and authenticated session-v2 C2/C3 campaigns.

PC owns SSH management only. The remote Pi3 worker alone injects on CAN and
receives no SecOC key. Measured evidence is evaluated after confirmed cleanup.
"""
import argparse
from collections import Counter
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import shlex
import signal
import subprocess
import sys
import time
import uuid

from security.experiments.ablation_core import trial_seed
from security.experiments.can_capture import sha256, interrupted
from security.experiments.live_three_node import Actors
from security.experiments.session_campaign_evidence import evaluate, CODES, IndexedIdsLog, phases
from security.experiments.session_ids_log import MAX_BYTES
from security.experiments.summarize_resources import analyze as analyze_resources
from security.experiments.test360_support import phase_barrier
from security.experiments.validate_m5_settings import ssh_target

ROLES=('ecu_off','ecu_on','ecu_ids','receiver_off','receiver_on','observer_a','observer_b',
       'attacker','ids_fetch','health_a','health_b','health_c')
START_ROLES=set(ROLES)-{'ids_fetch','health_a','health_b','health_c'}
VALUES={'run_id':'STATIC-C1-fuzzy-s001','lifetime_s':'120','lifetime_ms':'120000',
        'interface':'can0','sensor_mode':'constant','ids_generation':'0'*32,'log_kind':'events',
        'ids_max_bytes':str(MAX_BYTES)}


class CaseFailure(RuntimeError):
    def __init__(self,message,recoverable=False):
        super().__init__(message);self.recoverable=recoverable


def save(path,value):
    temporary=path.with_suffix(path.suffix+'.pending')
    with temporary.open('x') as stream:
        os.fchmod(stream.fileno(),0o600)
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)


def render(command,values):
    return [part.format_map(values) for part in command]


def option(tokens,flag):
    indexes=[i for i,v in enumerate(tokens) if v==flag]
    if len(indexes)!=1 or indexes[0]+1>=len(tokens):raise ValueError('one explicit '+flag+' required')
    return tokens[indexes[0]+1]


def validate_settings(settings):
    if not isinstance(settings,dict) or settings.get('schema')!='pc-session-campaign-v1' or settings.get('protocol')!='session-v2':
        raise ValueError('pc-session-campaign-v1/session-v2 settings required')
    if settings.get('environment') not in ('physical-can','vcan') or settings.get('ids_mode') not in ('rules-only','rules+if'):
        raise ValueError('explicit environment and IDS mode required')
    commands=settings['commands']
    display=settings.get('display')
    if display is not None and display!={'mode':'wayland-single-owner'}:
        raise ValueError('explicit wayland-single-owner display mode required')
    if set(commands)!=set(ROLES)|({'display_owner'} if display else set()):
        raise ValueError('exact session campaign command roles required')
    targets={};tokens={}
    for role,command in commands.items():
        if not isinstance(command,list) or not command or not all(isinstance(v,str) and v for v in command):
            raise ValueError(role+': SSH argv required')
        if Path(command[0]).name!='ssh' or '-T' not in command or any(v in command for v in ('-t','-tt','-n')):
            raise ValueError(role+': explicit non-PTY connected SSH required')
        if any('REPLACE_' in v for v in command):raise ValueError(role+': unresolved template')
        render(command,VALUES);targets[role]=ssh_target(command);tokens[role]=shlex.split(command[-1])
        text=' '.join(command)
        if role=='display_owner' and ('dashboard_handoff.py' not in text or option(tokens[role],'--mode')!='lease'
                or option(tokens[role],'--run-id')!='{run_id}' or option(tokens[role],'--duration')!='{lifetime_s}'
                or 'remote_process' in text):
            raise ValueError('display_owner: direct PC-stdin-bounded lease required')
        if role in START_ROLES and ('{run_id}' not in text or '{lifetime_s}' not in text):
            raise ValueError(role+': owned run ID and lifetime required')
        if role in ('ecu_off','ecu_on','ecu_ids','receiver_off','receiver_on'):
            if 'security.experiments.remote_process' not in text or '--run-id {run_id}' not in text:
                raise ValueError(role+': bounded acknowledged remote process required')
        if role.startswith('observer_') or role=='attacker':
            module='trial_observer' if role.startswith('observer_') else 'can_attack_worker'
            if 'security.experiments.'+module not in text or 'remote_process' in text:
                raise ValueError(role+': direct stdin-controlled actor required')
            expected='vcan' if settings['environment']=='vcan' else 'physical'
            if option(tokens[role],'--environment')!=expected:raise ValueError(role+': explicit matching bus environment required')
        if role.startswith('health_') and ('security.experiments.can_health' not in text or '--recover' in tokens[role]):
            raise ValueError(role+': read-only CAN health required')
    a=targets['ecu_on'];b=targets['receiver_on'];c=targets['attacker']
    if len({a,b,c})!=3:raise ValueError('three distinct role targets required')
    for role in ('ecu_off','ecu_ids','observer_a','health_a','ids_fetch'):
        if targets[role]!=a:raise ValueError(role+': must target ECU')
    for role in ('receiver_off','observer_b','health_b'):
        if targets[role]!=b:raise ValueError(role+': must target IVI')
    if targets['health_c']!=c:raise ValueError('health_c: must target Pi3')
    if display:
        if targets['display_owner']!=b:raise ValueError('display lease must target IVI')
        for role in ('receiver_off','receiver_on'):
            text=' '.join(commands[role])
            if ('dashboard_handoff.py' not in text or option(tokens[role],'--mode')!='launch'
                    or 'offscreen' in text or 'sudo' in tokens[role]):
                raise ValueError('visible receiver requires desktop-user lease-aware Wayland launch')
    for role in ('ecu_off','receiver_off'):
        if option(tokens[role],'--protocol')!='legacy-v1':raise ValueError('C1 requires explicit raw legacy experiment')
    if (option(tokens['ecu_off'],'--secoc')!='off' or '--experiment-secoc-off' not in tokens['receiver_off'] or
        '--confirm-isolated-test-bus' not in tokens['receiver_off']):
        raise ValueError('C1 defence must explicitly be off')
    for role in ('ecu_on','ecu_ids','receiver_on'):
        if option(tokens[role],'--protocol')!='session-v2' or '--session-policy' not in tokens[role]:
            raise ValueError(role+': session-v2 policy required')
    for role in ('ecu_on','ecu_ids'):
        if option(tokens[role],'--secoc')!='on':raise ValueError(role+': explicit protection on required')
        if not any(v.endswith('supervise_ecu.py') for v in tokens[role]) or option(tokens[role],'--max-crash-restarts')!='0':
            raise ValueError(role+': campaign owns case recovery; supervised ECU with crash budget0 required')
        if option(tokens[role],'--initial-intent')!='fresh':raise ValueError('new case session starts explicitly fresh')
    if '--ids-settings' not in tokens['ecu_ids'] or '--ids-settings' in tokens['ecu_on']:
        raise ValueError('only C3 may enable managed IDS')
    if '--experiment-secoc-off' in tokens['receiver_on']:raise ValueError('protected receiver must verify SecOC')
    for role in ('ecu_off','ecu_on','ecu_ids'):
        if '{sensor_mode}' not in ' '.join(commands[role]):raise ValueError(role+': sensor mode placeholder required')
    attacker=tokens['attacker']
    if '--i-am-on-a-test-bus' not in attacker or any(v.split('=',1)[0] in ('--key','--secoc-key') for v in attacker):
        raise ValueError('Pi3 must be acknowledged and keyless')
    if 'security.experiments.session_ids_log' not in ' '.join(commands['ids_fetch']) or \
       '{ids_generation}' not in commands['ids_fetch'][-1] or '{log_kind}' not in commands['ids_fetch'][-1]:
        raise ValueError('generation-specific bounded IDS collector required')
    collection=settings.get('ids_collection')
    fetch=tokens['ids_fetch']
    if collection is not None:
        if (not isinstance(collection,dict) or set(collection)!={'mode','max_event_bytes'} or
            collection['mode']!='stream-v2' or type(collection['max_event_bytes']) is not int or
            not 1<=collection['max_event_bytes']<=sys.maxsize):
            raise ValueError('explicit stream-v2 IDS event byte budget required')
        if fetch.count('--stream')!=1 or option(fetch,'--max-total-bytes')!='{ids_max_bytes}':
            raise ValueError('stream collector requires matching byte-budget placeholder')
    elif '--stream' in fetch or any(v.split('=',1)[0]=='--max-total-bytes' for v in fetch):
        raise ValueError('stream collector requires explicit ids_collection policy')
    return targets


def wait_record(actors,child,predicate,timeout,after=0):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        actors.check()
        snapshot=child.snapshot();rows=snapshot[after:];after=len(snapshot)
        if any(row.get('result')=='OWNED_IDS_UNAVAILABLE' for row in rows):raise CaseFailure('managed IDS unavailable')
        found=next((row for row in reversed(rows) if predicate(row)),None)
        if found is not None:return found
        time.sleep(.02)
    raise CaseFailure('owned actor readiness/phase timeout',True)


def wait_seconds(actors,seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        actors.check();time.sleep(min(.02,max(0,end-time.monotonic())))


def prepare(actors,receiver,config,timeout):
    offset=len(receiver.snapshot())
    def ready(row):
        if config==1:return row.get('result')=='FRAME' and row.get('can_id')==0x100 and row.get('process_result')==2
        return row.get('result')=='SESSION_PUBLICATION' and row.get('valid') is True and row.get('stale') is False
    wait_record(actors,receiver,ready,timeout,after=offset)
    if config==3:
        offset=len(receiver.snapshot())
        def quiet(row):
            if row.get('result')!='AUTHENTICATED_DIAGNOSTIC' or row.get('kind')!=7:return False
            body=bytes.fromhex(row['body_hex'])
            return (len(body)==52 and body[16]==1 and body[48]==0 and row.get('observation_ready') is True
                    and row.get('condition_mask')==0 and int.from_bytes(body[44:48],'big')>=5000)
        wait_record(actors,receiver,quiet,timeout,after=offset)


def check_health(commands,values,root):
    reports={}
    for role in ('health_a','health_b','health_c'):
        completed=subprocess.run(render(commands[role],values),capture_output=True,text=True,timeout=30)
        reports[role]={'returncode':completed.returncode,'stdout':completed.stdout,'stderr':completed.stderr}
        save(root/'health.json',reports)
        if completed.returncode or not any(json.loads(line).get('result')=='CAN_HEALTHY'
                for line in completed.stdout.splitlines() if line.startswith('{')):
            raise CaseFailure(role+': CAN health unavailable')


def fetch_ids(command,*,stdout,stderr,max_bytes,timeout=60):
    """Bound the PC receive files too, including a broken/incompatible collector."""
    child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    counts={'stdout':0,'stderr':0};deadline=time.monotonic()+timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout,selectors.EVENT_READ,('stdout',stdout,max_bytes))
            selector.register(child.stderr,selectors.EVENT_READ,('stderr',stderr,65536))
            while selector.get_map():
                remaining=deadline-time.monotonic()
                if remaining<=0:raise subprocess.TimeoutExpired(command,timeout)
                for key,_ in selector.select(min(remaining,1)):
                    chunk=os.read(key.fd,65536)
                    if not chunk:
                        selector.unregister(key.fileobj);continue
                    name,sink,bound=key.data
                    allowed=min(len(chunk),bound-counts[name])
                    if allowed:sink.write(chunk[:allowed])
                    counts[name]+=len(chunk)
                    if counts[name]>bound:raise ValueError('IDS '+name+' exceeds PC collection bound')
            remaining=deadline-time.monotonic()
            if remaining<=0:raise subprocess.TimeoutExpired(command,timeout)
            return subprocess.CompletedProcess(command,child.wait(timeout=remaining))
    finally:
        if child.poll() is None:child.kill()
        child.wait(timeout=5);child.stdout.close();child.stderr.close()


def collect_ids(command,values,generations,root,mode,collection=None,windows=()):
    logs={}
    for descriptor in generations:
        generation=descriptor['generation']
        if not re.fullmatch('[0-9a-f]{32}',generation) or uuid.UUID(hex=generation).version!=4:
            raise CaseFailure('invalid owned IDS generation')
        if descriptor.get('protocol')!='session-v2' or descriptor.get('mode')!=mode:
            raise CaseFailure('owned IDS mode/protocol mismatch')
        for kind in ('events','process'):
            bound=collection['max_event_bytes'] if collection is not None and kind=='events' else MAX_BYTES
            path=root/f'ids-{generation}-{kind}.log';error=root/f'ids-{generation}-{kind}.metadata'
            with path.open('xb') as output,error.open('xb') as stderr:
                os.fchmod(output.fileno(),0o600);os.fchmod(stderr.fileno(),0o600)
                completed=fetch_ids(render(command,dict(values,ids_generation=generation,log_kind=kind,ids_max_bytes=str(bound))),
                                    stdout=output,stderr=stderr,max_bytes=bound)
            manifests=[json.loads(line) for line in error.read_text().splitlines() if line.startswith('{')]
            schema='owned-ids-log-v2' if collection is not None else 'owned-ids-log-v1'
            matches=[r for r in manifests if r.get('schema')==schema]
            manifest=matches[0] if len(matches)==1 else None
            if (completed.returncode or manifest is None or manifest.get('status')!='COMPLETE' or
                manifest.get('generation')!=generation or manifest.get('file')!=('events.jsonl' if kind=='events' else 'process.log') or
                manifest.get('bytes')!=path.stat().st_size or path.stat().st_size>bound or
                (collection is not None and (manifest.get('stream') is not True or manifest.get('max_total_bytes')!=bound))):
                raise CaseFailure('IDS collection incomplete; original files retained on ECU')
            if kind=='events':
                rows=IndexedIdsLog(path,windows)
                if rows.sha256!=manifest.get('sha256'):raise CaseFailure('IDS collection hash mismatch')
                first=rows.first
                if first.get('run_id')!='owned-ids-'+generation:raise CaseFailure('IDS file generation mismatch')
                identity=descriptor.get('startup_identity')
                if (not isinstance(identity,dict) or identity.get('schema')!='ids-startup-v1' or identity.get('mode')!=mode
                    or first.get('startup_identity')!=identity or first.get('protocol')!='session-v2'
                    or first.get('mode')!=mode):
                    raise CaseFailure('IDS startup identity differs between READY and collected START')
                if 'records' in manifest and manifest['records']!=rows.records:raise CaseFailure('IDS record count mismatch')
                measured=first.get('resource_measurement',False)
                if (type(measured) is not bool or measured!=identity.get('resource_measurement',False)
                    or measured!=descriptor.get('resource_measurement',False)):
                    raise CaseFailure('IDS measurement selection differs between START/READY')
                if measured:
                    resources=analyze_resources(path,max_bytes=bound)
                    # Interrupted/partial generations retain their status. File
                    # collection success is not complete resource coverage.
                    save(root/f'ids-{generation}-resources.json',resources)
                logs[generation]=rows
            elif manifest.get('sha256')!=sha256(path):raise CaseFailure('IDS collection hash mismatch')
    return logs


def validate_input_configuration(value):
    expected={'source_mode','ground_truth_label','calculation_dt_s','sensor_units','voltage_semantics','sensor','soh'}
    if (not isinstance(value,dict) or set(value)!=expected or
        value['ground_truth_label']!='unattested' or type(value['calculation_dt_s']) not in (int,float) or
        value['calculation_dt_s']!=.1 or value['sensor_units']!={'voltage':'V','current':'A','temperature':'degC'} or
        value['voltage_semantics']!='product_interprets_as_pack_voltage'):
        raise ValueError('ECU input configuration/units unavailable')
    mode=value['source_mode'];sensor=value['sensor'];soh=value['soh']
    origins={'constant':'virtual_constant','profile_csv':'csv_values_not_physically_attested',
        'random_walk':'virtual_random_walk','ads1115':'real_adc_with_virtual_pack_mapping'}
    if mode not in origins or not isinstance(sensor,dict) or sensor.get('origin')!=origins[mode]:
        raise ValueError('ECU sensor source mode/origin mismatch')
    fields={
        'constant':{'origin','values'},
        'profile_csv':{'origin','input','rows','columns','temperature_conversion','temperature_bounds_degC','row_clock','end_policy','empty_policy'},
        'random_walk':{'origin','seed','engine','distribution','cross_library_bitwise_reproducible','initial_values','delta_stddev','bounds','temperature_conversion'},
        'ads1115':{'origin','channel','i2c_address','device_binding_sha256','adc_lsb_v','nominal_adc_v','nominal_codes',
            'endpoint_tolerance_codes','endpoint_policy','virtual_pack_v','mapping','virtual_current_a',
            'virtual_temperature_degC','freshness_ms','startup_recovery_gate'}}
    if set(sensor)!=fields[mode]:raise ValueError('ECU sensor lineage fields unavailable/unknown')
    def file_identity(item):
        if (not isinstance(item,dict) or set(item)!={'bytes','sha256'} or type(item['bytes']) is not int or
            not 0<=item['bytes']<=16*1024*1024 or not isinstance(item['sha256'],str) or
            not re.fullmatch('[0-9a-f]{64}',item['sha256'])):
            raise ValueError('ECU parsed input fingerprint unavailable')
    if mode=='profile_csv':
        file_identity(sensor.get('input'))
        if type(sensor.get('rows')) is not int or sensor['rows']<0:raise ValueError('ECU profile rows unavailable')
    if mode=='random_walk' and (type(sensor.get('seed')) is not int or
        sensor.get('engine')!='std::mt19937' or sensor.get('cross_library_bitwise_reproducible') is not False):
        raise ValueError('ECU random source identity unavailable')
    if mode=='ads1115' and (not isinstance(sensor['device_binding_sha256'],str) or
        not re.fullmatch('[0-9a-f]{64}',sensor['device_binding_sha256'])):
        raise ValueError('ECU ADC device binding unavailable')
    if (not isinstance(soh,dict) or soh.get('origin')!='virtual_capacity_scenario' or
        set(soh)!={'origin','initial_capacity_ah','input','steps','units','step_policy','clock'} or
        type(soh.get('initial_capacity_ah')) not in (int,float) or soh['initial_capacity_ah']!=50 or
        type(soh.get('steps')) is not int or soh['steps']<1 or soh.get('units')!={'elapsed':'s','capacity':'Ah'}):
        raise ValueError('ECU virtual SOH input identity unavailable')
    if soh.get('input') is not None:file_identity(soh['input'])
    json.dumps(value,allow_nan=False)
    return value


def validate_input_lineage(row):
    if (not isinstance(row,dict) or row.get('result')!='ECU_INPUT_LINEAGE' or row.get('schema')!='ecu-input-lineage-v1' or
        not isinstance(row.get('instance_id'),str) or not re.fullmatch('[0-9a-f]{32}',row['instance_id']) or
        uuid.UUID(hex=row['instance_id']).version!=4 or row.get('start_intent') not in ('standalone','fresh','resume')):
        raise ValueError('ECU input lineage instance/schema unavailable')
    configuration=validate_input_configuration(row.get('configuration'))
    state=row.get('state')
    if (not isinstance(state,dict) or type(state.get('profile_index')) is not int or state['profile_index']<0 or
        type(state.get('soh_elapsed_s')) not in (int,float) or not math.isfinite(state['soh_elapsed_s']) or state['soh_elapsed_s']<0):
        raise ValueError('ECU input lineage state unavailable')
    if row['start_intent']!='resume' and (state['profile_index'] or state['soh_elapsed_s']):
        raise ValueError('fresh ECU input must begin at the initial position')
    if configuration['source_mode']=='random_walk' and (not isinstance(state.get('rng_state_sha256'),str) or
        not re.fullmatch('[0-9a-f]{64}',state['rng_state_sha256'])):
        raise ValueError('ECU restored random state identity unavailable')
    json.dumps(row,allow_nan=False)
    return row


def startup_identities(actors,manager,receiver,observers,attacker,config,run_id):
    def digest(value):
        if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):
            raise CaseFailure('remote executable/source fingerprint unavailable')
        return value
    def record(child,result):
        row=wait_record(actors,child,lambda row:row.get('result')==result,10)
        matching=[r for r in child.snapshot() if r.get('result')==result]
        if len(matching)!=1:raise CaseFailure('multiple startup identities for owned actor')
        return row
    def python_actor(child):
        row=record(child,'READY')
        identity=row.get('execution_identity')
        if (row.get('run_id')!=run_id or not isinstance(identity,dict) or
            identity.get('schema')!='python-actor-startup-v1' or not identity.get('python')):
            raise CaseFailure('Python actor startup identity unavailable')
        digest(identity.get('source_sha256'));digest(identity.get('interpreter',{}).get('sha256'))
        return identity
    iv=record(receiver,'REMOTE_START')
    if iv.get('run_id')!=run_id:raise CaseFailure('IVI executable run ID mismatch')
    ecu=record(manager,'REMOTE_START' if config==1 else 'ECU_PROCESS_STARTED')
    if config==1 and ecu.get('run_id')!=run_id:raise CaseFailure('ECU executable run ID mismatch')
    lineage=validate_input_lineage(record(manager,'ECU_INPUT_LINEAGE'))
    if lineage['start_intent']!=('standalone' if config==1 else 'fresh'):
        raise CaseFailure('campaign requires explicit new-case input state')
    identities={'schema':'session-execution-v1','ecu':{'executable_sha256':digest(ecu.get('executable_sha256')),
        'input_configuration':lineage['configuration']},
        'ivi':{'executable_sha256':digest(iv.get('executable_sha256'))},
        'observer_a':python_actor(observers[0]),'observer_b':python_actor(observers[1]),
        'attacker':python_actor(attacker)}
    if config>1:
        for name in ('supervisor_sha256','owned_ids_sha256'):identities['ecu'][name]=digest(ecu.get(name))
        if type(ecu.get('trace_can_tx')) is not bool:raise CaseFailure('CAN TX trace selection unavailable')
        identities['ecu']['trace_can_tx']=ecu['trace_can_tx']
    if config==3:
        owned=record(manager,'OWNED_IDS_READY');identity=owned.get('startup_identity')
        if (not isinstance(identity,dict) or identity.get('schema')!='ids-startup-v1'
            or identity.get('mode')!=owned.get('mode')):raise CaseFailure('managed IDS startup identity unavailable')
        digest(identity.get('source_sha256'));digest(identity.get('interpreter',{}).get('sha256'))
        if identity['mode']=='rules+if':
            digest(identity.get('trained_model_sha256'))
            if set(identity.get('normal_inputs',{}))!={'train_normal','normal_manifest','calibrate_normal','calibration_manifest'}:
                raise CaseFailure('IF training/calibration identities incomplete')
        identities['ids']=identity
    return identities


def validate_execution_identity(identity,config,mode):
    def fingerprint(value):
        return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None
    if not isinstance(identity,dict) or identity.get('schema')!='session-execution-v1':
        raise ValueError('missing session execution identity')
    expected={'schema','ecu','ivi','observer_a','observer_b','attacker'}|({'ids'} if config==3 else set())
    if set(identity)!=expected:raise ValueError('execution identity roles differ from defence configuration')
    for name in ('ecu','ivi'):
        if not isinstance(identity[name],dict) or not fingerprint(identity[name].get('executable_sha256')):
            raise ValueError('native executable identity missing')
    if 'display_owner_sha256' in identity['ivi'] and not fingerprint(identity['ivi']['display_owner_sha256']):
        raise ValueError('display owner identity missing')
    validate_input_configuration(identity['ecu'].get('input_configuration'))
    if config>1:
        for name in ('supervisor_sha256','owned_ids_sha256'):
            if not fingerprint(identity['ecu'].get(name)):raise ValueError('managed ECU script identity missing')
        if type(identity['ecu'].get('trace_can_tx')) is not bool:
            raise ValueError('CAN TX trace selection missing')
    for name in ('observer_a','observer_b','attacker'):
        actor=identity[name]
        if (not isinstance(actor,dict) or actor.get('schema')!='python-actor-startup-v1' or not actor.get('python') or
            not fingerprint(actor.get('source_sha256')) or not isinstance(actor.get('interpreter'),dict) or
            not fingerprint(actor['interpreter'].get('sha256'))):
            raise ValueError('Python actor identity missing')
    if config==3:
        ids=identity['ids']
        if (not isinstance(ids,dict) or ids.get('schema')!='ids-startup-v1' or ids.get('mode')!=mode or not ids.get('python') or
            not fingerprint(ids.get('source_sha256')) or not isinstance(ids.get('interpreter'),dict) or
            not fingerprint(ids['interpreter'].get('sha256')) or
            not isinstance(ids.get('config'),dict)):
            raise ValueError('IDS startup identity incomplete')
        inputs=ids.get('normal_inputs');dependencies=ids.get('dependencies')
        if mode=='rules+if':
            if (not fingerprint(ids.get('trained_model_sha256')) or not isinstance(inputs,dict) or
                set(inputs)!={'train_normal','normal_manifest','calibrate_normal','calibration_manifest'} or
                not isinstance(dependencies,dict) or set(dependencies)!={'numpy','scipy','scikit-learn'} or
                not all(isinstance(value,str) and value for value in dependencies.values())):
                raise ValueError('IF model/input/dependency identity incomplete')
            for value in inputs.values():
                if not isinstance(value,dict) or not fingerprint(value.get('sha256')) or type(value.get('bytes')) is not int or value['bytes']<=0:
                    raise ValueError('IF input fingerprint incomplete')
        elif inputs!={} or dependencies!={} or ids.get('trained_model_sha256') is not None:
            raise ValueError('rule-only identity must not claim IF inputs or model')
    # JSON strictness also excludes nonfinite config/threshold metadata.
    json.dumps(identity,allow_nan=False)
    return identity


def pilot_identities(root,metadata):
    identities={}
    for config in (1,2,3):
        for attack in CODES:
            for manifest,rows in history(root/f'C{config}-{attack}'):
                if manifest.get('status')!='COMPLETE' or not rows or any(
                        not row.get('trial_completed') or row.get('status')!='VALID' for row in rows):
                    raise ValueError('pilot must have no failed/incomplete execution sessions')
                identity=validate_execution_identity(manifest.get('execution_identity'),config,metadata['ids_mode'])
                if str(config) in identities and identities[str(config)]!=identity:
                    raise ValueError('pilot remote identities changed across attack cases')
                identities[str(config)]=identity
    if set(identities)!={'1','2','3'}:raise ValueError('pilot remote identities missing')
    for config in ('2','3'):
        if (identities[config]['ecu']['executable_sha256']!=identities['1']['ecu']['executable_sha256'] or
            identities[config]['ecu']['input_configuration']!=identities['1']['ecu']['input_configuration'] or
            identities[config]['ivi']!=identities['1']['ivi']):
            raise ValueError('pilot native binaries or inputs differ across defence configurations')
        for role in ('observer_a','observer_b','attacker'):
            if identities[config][role]!=identities['1'][role]:raise ValueError('pilot Python actors differ across configurations')
    if identities['2']['ecu']!=identities['3']['ecu']:raise ValueError('pilot managed ECU scripts differ')
    return identities


def run_case(settings,args,config,attack,start_trial,root):
    root.mkdir(mode=0o700)
    run_id=f'{args.run_id}-C{config}-{attack}-{root.name}'
    count=args.per_case-start_trial+1
    lifetime=math.ceil(120+count*(args.quiet_timeout+args.baseline+args.duration+args.post+10))
    values=dict(VALUES,run_id=run_id,lifetime_s=str(lifetime),lifetime_ms=str(lifetime*1000),
                interface=args.interface,sensor_mode=args.sensor_mode)
    commands=settings['commands'];actors=Actors();observers=[];receiver=attacker=manager=None
    pending=[];active=None;failure=None;interrupted_case=False;logs={};rows=[];display_owner=None
    manifest={'schema':'session-case-v1','run_id':run_id,'config':config,'attack_type':attack,
        'environment':settings['environment'],'ids_mode':settings['ids_mode'] if config==3 else 'off',
        'protocol':'raw-unprotected' if config==1 else 'session-v2','start_trial':start_trial,
        'cleanup_confirmed':False,'recoverable':False}
    try:
        if settings.get('display'):
            display_owner=actors.start(render(commands['display_owner'],values),root,'display_owner')
            display_owner.ready(run_id)
            ready=next(row for row in display_owner.snapshot() if row.get('result')=='READY')
            if ready.get('role')!='desktop-lease' or not re.fullmatch('[0-9a-f]{64}',ready.get('source_sha256','')):
                raise CaseFailure('display lease ownership unverified')
        check_health(commands,values,root)
        for role in ('observer_a','observer_b'):
            child=actors.start(render(commands[role],values),root,role);child.ready(run_id);observers.append(child)
        wait_seconds(actors,.3)
        if any(row.get('result')=='OBS_FRAME' for child in observers for row in child.snapshot()):
            raise CaseFailure('bus already active before owned ECU start')
        role='receiver_off' if config==1 else 'receiver_on'
        receiver=actors.start(render(commands[role],values),root,'ivi');receiver.ready(run_id)
        if next(row for row in receiver.snapshot() if row.get('result')=='READY').get('secoc_on')!=(config!=1):
            raise CaseFailure('IVI defence mode mismatch')
        if display_owner is not None:
            wait_record(actors,receiver,lambda row:row.get('result')=='WINDOW_PRESENTED' and
                row.get('run_id')==run_id and row.get('display_platform')=='wayland',20)
        role={1:'ecu_off',2:'ecu_on',3:'ecu_ids'}[config]
        manager=actors.start(render(commands[role],values),root,'ecu')
        if config==3:
            descriptor=wait_record(actors,manager,lambda row:row.get('result')=='OWNED_IDS_READY',60)
            if descriptor.get('mode')!=settings['ids_mode'] or descriptor.get('protocol')!='session-v2':
                raise CaseFailure('managed IDS mode mismatch')
        attacker=actors.start(render(commands['attacker'],values),root,'attacker');attacker.ready(run_id)
        if not any(row.get('role')=='keyless-can-attacker' and 'isolated-session-v1' in row.get('profiles',[])
                   for row in attacker.snapshot()):raise CaseFailure('session attack profile unavailable')
        manifest['execution_identity']=startup_identities(actors,manager,receiver,observers,attacker,config,run_id)
        if display_owner is not None:
            manifest['execution_identity']['ivi']['display_owner_sha256']=ready['source_sha256']
        validate_execution_identity(manifest['execution_identity'],config,settings['ids_mode'])
        if manifest['execution_identity']['ecu']['input_configuration']['source_mode']!=args.sensor_mode:
            raise CaseFailure('ECU input source differs from requested sensor mode; no attack injected')
        expected=getattr(args,'expected_identities',None)
        if expected is not None and manifest['execution_identity']!=expected[str(config)]:
            raise CaseFailure('remote executable/model identity differs from accepted pilot; no attack injected')
        for trial in range(start_trial,args.per_case+1):
            active=trial
            prepare(actors,receiver,config,args.quiet_timeout)
            offsets=[len(child.snapshot()) for child in observers]
            phase_barrier(observers,'baseline',actors);wait_seconds(actors,args.baseline)
            b_start=next(row['t'] for row in observers[1].snapshot()[offsets[1]:] if row.get('phase')=='baseline')
            if not any((row.get('result')=='SESSION_PUBLICATION' and row.get('valid') is True and row.get('stale') is False
                        and int(row['t2_published_ns'])/1e9>=b_start) if config>1 else
                       (row.get('result')=='FRAME' and row.get('can_id')==0x100 and row.get('process_result')==2
                        and int(row['timestamp_ns'])/1e9>=b_start) for row in receiver.snapshot()):
                raise CaseFailure('IVI baseline unavailable',True)
            phase_barrier(observers,'attack',actors)
            request={'trial':trial,'attack':attack,'rate':args.rate if attack=='flooding' else 5,
                     'duration':args.duration,'profile':'isolated-session-v1','seed':trial_seed(attack,trial),
                     'interface':args.interface,'secoc':config!=1}
            attacker.process.stdin.write(json.dumps(request)+'\n');attacker.process.stdin.flush()
            wait_record(actors,attacker,lambda row:row.get('result')=='ATTACK_DONE' and row.get('trial')==trial,args.duration+10)
            phase_barrier(observers,'post',actors);wait_seconds(actors,args.post)
            phase_barrier(observers,'idle',actors)
            pending.append((trial,[child.snapshot()[offset:] for child,offset in zip(observers,offsets)]));active=None
            print(json.dumps({'result':'TRIAL_COLLECTED','run_id':run_id,'config':config,'attack':attack,'trial':trial}),flush=True)
    except KeyboardInterrupt:interrupted_case=True
    except (OSError,ValueError,RuntimeError,TimeoutError,subprocess.SubprocessError) as error:
        failure=error;manifest['error']=str(error)
        manifest['recoverable']=getattr(error,'recoverable',False) or (isinstance(error,(RuntimeError,TimeoutError)) and
            any(text in str(error) for text in ('remote actor exited','observer phase timeout','child READY timeout')))
    finally:
        errors=actors.close()
        expected={'observer_a':'OBSERVER_STOPPED','observer_b':'OBSERVER_STOPPED','attacker':'ATTACKER_STOPPED',
                  'ivi':'REMOTE_STOPPED','ecu':'REMOTE_STOPPED','display_owner':'DISPLAY_LEASE_STOPPED'}
        acknowledgements=[]
        for child in actors.children:
            name=child.output.name if hasattr(child.output,'name') else ''
            role=Path(name).stem
            acknowledgements.append(any(row.get('result')==expected.get(role) and row.get('run_id')==run_id
                                        for row in child.snapshot()))
            if role=='display_owner':
                stopped=[row for row in child.snapshot() if row.get('result')=='DISPLAY_LEASE_STOPPED' and row.get('run_id')==run_id]
                restored=len(stopped)==1 and stopped[0].get('restored') is True
                acknowledgements.append(restored)
                manifest['display_restoration_confirmed']=restored
            if any(row.get('result')=='REMOTE_STOPPED' and row.get('exit_code',0)!=0 for row in child.snapshot()):
                failure=CaseFailure('owned remote child failed');manifest['error']=str(failure);manifest['recoverable']=False
        manifest['cleanup_confirmed']=not errors and all(acknowledgements)
        if any(row.get('result')=='ATTACKER_ERROR' and row.get('category')=='clock'
               for child in actors.children for row in child.snapshot()):
            failure=CaseFailure('attacker receive clock mapping changed; operator action required')
            manifest['error']=str(failure);manifest['recoverable']=False
        if not manifest['cleanup_confirmed']:
            manifest['error']='owned cleanup unconfirmed';manifest['cleanup_errors']=errors
            manifest['recoverable']=False;failure=CaseFailure(manifest['error'])
        if manager is not None and config>1 and manifest.get('execution_identity') and sum(
                row.get('result')=='ECU_PROCESS_STARTED' for row in manager.snapshot())!=1:
            failure=CaseFailure('ECU process generation changed during case')
            manifest['error']=str(failure);manifest['recoverable']=False
    if config==3 and manager is not None and manifest['cleanup_confirmed']:
        try:
            descriptors=[row for row in manager.snapshot() if row.get('result')=='OWNED_IDS_READY']
            if len(descriptors)!=1:raise CaseFailure('IDS generation changed or unavailable')
            windows=[]
            for _,captures in pending:
                try:
                    times=phases(captures[0],run_id);windows.append((times[0],times[-1]))
                except (ValueError,KeyError,TypeError,IndexError,OverflowError):pass
            logs=collect_ids(commands['ids_fetch'],values,descriptors,root,settings['ids_mode'],
                             settings.get('ids_collection'),windows)
        except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
            failure=error;manifest['error']=str(error);manifest['recoverable']=False
    for trial,captures in pending:
        ids=next(iter(logs.values()),None)
        row=evaluate(config=config,attack=attack,trial=trial,run_id=run_id,worker=attacker.snapshot(),
                     observers=captures,ivi=receiver.snapshot(),ids=ids,ids_mode=manifest['ids_mode'])
        row.update(trial_completed=True,seed=trial_seed(attack,trial));rows.append(row)
    if active is not None:
        rows.append({'trial':active,'trial_completed':False,'status':'INVALID','invalid_reasons':['EXECUTION_INCOMPLETE']})
    save(root/'trials.json',rows)
    manifest['status']='INTERRUPTED' if interrupted_case else 'ERROR' if failure else 'COMPLETE'
    manifest['files_sha256']={p.name:sha256(p) for p in root.iterdir() if p.is_file() and not p.name.endswith('.pending')}
    save(root/'manifest.json',manifest)
    return manifest,rows


def history(root):
    found=[]
    for path in sorted(root.glob('session-*')):
        if not (path/'manifest.json').is_file():raise ValueError('unsealed session; inspect remote cleanup before resuming')
        manifest=json.loads((path/'manifest.json').read_text())
        if manifest.get('schema')!='session-case-v1' or root.name!=f"C{manifest.get('config')}-{manifest.get('attack_type')}":
            raise ValueError('session manifest belongs to another case')
        if not manifest.get('cleanup_confirmed'):raise ValueError('remote cleanup unconfirmed; cannot resume')
        for name,digest in manifest['files_sha256'].items():
            if Path(name).name!=name or sha256(path/name)!=digest:raise ValueError('sealed artifact hash mismatch')
        if {p.name for p in path.iterdir() if p.is_file() and p.name!='manifest.json'}!=set(manifest['files_sha256']):
            raise ValueError('unsealed extra artifact')
        found.append((manifest,json.loads((path/'trials.json').read_text())))
    return found


def summary(root,metadata):
    groups=[];all_rows=[];sessions=errors=0
    for config in (1,2,3):
        for attack in CODES:
            records=history(root/f'C{config}-{attack}');completed=[]
            sessions+=len(records);errors+=sum(m['status']=='ERROR' for m,_ in records)
            for _,rows in records:completed += [row for row in rows if row.get('trial_completed')]
            if [row['trial'] for row in completed]!=list(range(1,len(completed)+1)):
                raise ValueError('duplicate or noncontiguous completed trial sequence')
            if len(completed)>metadata['per_case']:raise ValueError('completed beyond planned count')
            all_rows+=completed
            groups.append({'config':config,'attack':attack,'completed':len(completed),
                'valid':sum(row['status']=='VALID' for row in completed),
                'ids_results':dict(Counter(row.get('ecu_ids_type_result','INVALID') for row in completed)),
                'response_results':dict(Counter(row.get('attack_response',{}).get('status','NOT_RECORDED') for row in completed)),
                'ivi_results':dict(Counter(row.get('ivi_view_model_type_result','INVALID') for row in completed))})
    planned=12*metadata['per_case']
    return {'stage':metadata['stage'],'environment':metadata['environment'],'ids_mode':metadata['ids_mode'],
        'planned_trials':planned,'completed_trials':len(all_rows),'remaining_trials':planned-len(all_rows),
        'valid_trials':sum(row['status']=='VALID' for row in all_rows),
        'invalid_trials':sum(row['status']!='VALID' for row in all_rows),'process_sessions':sessions,
        'execution_error_sessions':errors,'groups':groups,
        'note':'Completed includes measured INVALID. Deferred/unperformed trials are not filled as observations. Type mismatches are measurements.'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('settings','out','run-id'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--stage',choices=('pilot','test360','official'),default='pilot')
    parser.add_argument('--pilot-dir')
    parser.add_argument('--interface',default='can0')
    parser.add_argument('--sensor-mode',choices=('constant','ads1115'),default='constant')
    parser.add_argument('--baseline',type=float,default=2)
    parser.add_argument('--duration',type=float,default=3)
    parser.add_argument('--post',type=float,default=2)
    parser.add_argument('--quiet-timeout',type=float,default=20)
    parser.add_argument('--rate',type=float,default=1000)
    parser.add_argument('--max-recoveries',type=int,choices=range(4),default=2)
    parser.add_argument('--continue-on-error',action='store_true')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--validate-only',action='store_true')
    parser.add_argument('--i-am-on-a-test-bus',action='store_true')
    args=parser.parse_args(argv)
    try:
        if not args.i_am_on_a_test_bus and not args.validate_only:raise ValueError('isolated test bus acknowledgement required')
        if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,23}',args.run_id):raise ValueError('run ID must be at most24 safe characters')
        if not re.fullmatch('(v?can)[0-9]+',args.interface):raise ValueError('explicit CAN interface required')
        for value in (args.baseline,args.duration,args.post):
            if not math.isfinite(value) or not 1<=value<=60:raise ValueError('phase duration must be1..60 seconds')
        if not math.isfinite(args.quiet_timeout) or not 6<=args.quiet_timeout<=60:raise ValueError('quiet timeout must be6..60 seconds')
        if not math.isfinite(args.rate) or not 1<=args.rate<=2000:raise ValueError('rate must be1..2000 fps')
        settings=json.loads(Path(args.settings).read_text());validate_settings(settings)
        if args.interface.startswith('vcan')!=(settings['environment']=='vcan'):raise ValueError('interface/environment mismatch')
        if args.stage=='official' and settings['ids_mode']!='rules+if':raise ValueError('official C3 requires rules+if')
        if args.validate_only:
            print(json.dumps({'status':'STATIC_VALID','environment':settings['environment'],'ids_mode':settings['ids_mode'],
                'note':'No SSH/CAN/keys read, process launch or result directory created. Runtime/software/model identity is not certified.'}))
            return 0
        args.per_case={'pilot':1,'test360':30,'official':100}[args.stage]
        metadata={'schema':'session-campaign-v1','run_id':args.run_id,'stage':args.stage,'per_case':args.per_case,
            'settings_sha256':sha256(args.settings),'environment':settings['environment'],'ids_mode':settings['ids_mode'],
            'phases':{name:getattr(args,name) for name in ('baseline','duration','post','quiet_timeout','rate','sensor_mode','interface')},
            'source_sha256':{p.relative_to(Path(__file__).resolve().parents[2]).as_posix():sha256(p)
                for pattern in ('security/**/*.py','adaptive_ecu/scripts/*.py')
                for p in sorted(Path(__file__).resolve().parents[2].glob(pattern))}}
        if args.stage=='official':
            if not args.pilot_dir:raise ValueError('official requires matching clean pilot')
            pilot=Path(args.pilot_dir);prior=json.loads((pilot/'campaign.json').read_text());measured=summary(pilot,prior)
            if prior['stage']!='pilot' or measured['valid_trials']!=12 or json.loads((pilot/'summary.json').read_text())['status']!='COMPLETE':
                raise ValueError('12 valid fully completed pilot trials required')
            if any(prior[key]!=metadata[key] for key in ('settings_sha256','environment','ids_mode','phases','source_sha256')):
                raise ValueError('pilot sources/settings/phases differ')
            args.expected_identities=pilot_identities(pilot,prior)
            metadata['reference_execution_identities']=args.expected_identities
            metadata['pilot_identity_sha256']=hashlib.sha256(json.dumps(args.expected_identities,
                sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        root=Path(args.out)
        if args.resume:
            if json.loads((root/'campaign.json').read_text())!=metadata or sha256(root/'settings.json')!=metadata['settings_sha256']:
                raise ValueError('resume requires identical sources/settings/phases/run ID')
        else:root.mkdir(mode=0o700,parents=True,exist_ok=False)
    except (OSError,ValueError,KeyError,TypeError) as error:parser.error(str(error))
    with (root/'campaign.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:parser.error('campaign already running')
        if not args.resume:
            with (root/'settings.json').open('xb') as saved:
                os.fchmod(saved.fileno(),0o600);saved.write(Path(args.settings).read_bytes());saved.flush();os.fsync(saved.fileno())
            save(root/'campaign.json',metadata)
        status='COMPLETE';error=None;allowances={}
        previous=signal.signal(signal.SIGTERM,interrupted)
        try:
            summary(root,metadata) # Refuse uncertain or altered previous sessions before SSH.
            for config in (1,2,3):
                for attack in CODES:
                    group=root/f'C{config}-{attack}';group.mkdir(exist_ok=True,mode=0o700)
                    while True:
                        prior=history(group);done=sum(row.get('trial_completed',False) for _,rows in prior for row in rows)
                        if done==args.per_case:break
                        used=len(prior)
                        # --resume grants a new bounded recovery budget for remaining trials.
                        allowance=allowances.setdefault(str(group),used+args.max_recoveries+1)
                        manifest,_=run_case(settings,args,config,attack,done+1,group/f'session-{used+1:03d}')
                        if manifest['status']=='INTERRUPTED':raise KeyboardInterrupt
                        if not manifest['cleanup_confirmed']:raise CaseFailure('remote cleanup unconfirmed')
                        if manifest['status']=='ERROR':
                            if manifest['recoverable'] and used+1<allowance:continue
                            if not manifest['recoverable'] or not args.continue_on_error:raise CaseFailure(manifest.get('error','case failed'))
                            status='PARTIAL';break
            measured=summary(root,metadata)
            if measured['remaining_trials']:status='PARTIAL'
            elif measured['invalid_trials']:status='COMPLETE_WITH_INVALID'
        except KeyboardInterrupt:status='INTERRUPTED'
        except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as failure:
            status='ERROR';error=str(failure)
        finally:signal.signal(signal.SIGTERM,previous)
        try:result=summary(root,metadata)
        except (OSError,ValueError,KeyError) as failure:
            result={'stage':args.stage,'evidence_status':'UNVERIFIED','error':str(failure)};status='ERROR'
        result['status']=status
        if error:result['error']=error
        save(root/'summary.json',result);print(json.dumps(result),flush=True)
    return 0 if status in ('COMPLETE','COMPLETE_WITH_INVALID') else 2


if __name__=='__main__':raise SystemExit(main())
