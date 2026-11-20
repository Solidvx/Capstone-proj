"""Controller scheduling/ownership tests; no SSH connection or CAN device."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from security.experiments import session_campaign as campaign
from security.experiments import can_attack_worker as worker
from security.tests.test_session_campaign_evidence import fixture


def settings():
    path=Path(__file__).parents[1]/'experiments/session-campaign-settings.template.json'
    value=json.loads(path.read_text().replace('REPLACE_','dummy_'))
    value.pop('display');value['commands'].pop('display_owner')
    return value


def argv(tmp_path,stage='pilot'):
    config=tmp_path/'settings.json';config.write_text(json.dumps(settings()))
    return ['--settings',str(config),'--out',str(tmp_path/'run'),'--run-id','DUMMY',
            '--stage',stage,'--i-am-on-a-test-bus']


def execution_identity(config,mode='rules+if'):
    actor={'schema':'python-actor-startup-v1','python':'dummy','source_sha256':'c'*64,'interpreter':{'sha256':'b'*64}}
    result={'schema':'session-execution-v1','ecu':{'executable_sha256':'d'*64,
        'input_configuration':input_lineage()['configuration']},'ivi':{'executable_sha256':'d'*64},
        'observer_a':actor,'observer_b':deepcopy(actor),'attacker':deepcopy(actor)}
    if config>1:result['ecu'].update(supervisor_sha256='e'*64,owned_ids_sha256='f'*64,trace_can_tx=False)
    if config==3:
        result['ids']={'schema':'ids-startup-v1','mode':mode,'python':'dummy','source_sha256':'a'*64,
            'interpreter':{'sha256':'b'*64},'config':{},'normal_inputs':{},'dependencies':{},'trained_model_sha256':None}
        if mode=='rules+if':
            result['ids'].update(trained_model_sha256='9'*64,
                dependencies={'numpy':'dummy','scipy':'dummy','scikit-learn':'dummy'},
                normal_inputs={name:{'sha256':'8'*64,'bytes':10} for name in
                    ('train_normal','normal_manifest','calibrate_normal','calibration_manifest')})
    return result


def input_lineage():
    return {'result':'ECU_INPUT_LINEAGE','schema':'ecu-input-lineage-v1',
        'instance_id':'00000000000040008000000000000001','start_intent':'fresh',
        'configuration':{'source_mode':'constant','ground_truth_label':'unattested','calculation_dt_s':.1,
            'sensor_units':{'voltage':'V','current':'A','temperature':'degC'},
            'voltage_semantics':'product_interprets_as_pack_voltage',
            'sensor':{'origin':'virtual_constant','values':[42,-2,25]},
            'soh':{'origin':'virtual_capacity_scenario','initial_capacity_ah':50,'input':None,'steps':1,
                'units':{'elapsed':'s','capacity':'Ah'},'step_policy':'previous_step_hold_last',
                'clock':'steady_elapsed_plus_restored_offset'}},
        'state':{'profile_index':0,'soh_elapsed_s':0}}


def seal(root,config,attack,rows,status='COMPLETE',cleanup=True,recoverable=False):
    root.mkdir(mode=0o700)
    campaign.save(root/'trials.json',rows)
    manifest={'schema':'session-case-v1','config':config,'attack_type':attack,'status':status,
        'cleanup_confirmed':cleanup,'recoverable':recoverable,
        'execution_identity':execution_identity(config),
        'files_sha256':{'trials.json':campaign.sha256(root/'trials.json')}}
    campaign.save(root/'manifest.json',manifest)
    return manifest,rows


def runner(calls,fail=None):
    def run(settings,args,config,attack,start,root):
        calls.append((config,attack,start,args.per_case,root.name))
        if fail is not None:
            failure=fail(calls,config,attack)
            if failure:return seal(root,config,attack,**failure)
        rows=[{'trial':trial,'trial_completed':True,'status':'VALID','ecu_ids_type_result':'MATCH' if config==3 else 'NOT_EVALUATED',
               'ivi_view_model_type_result':'MATCH' if config==3 else 'NOT_EVALUATED'} for trial in range(start,args.per_case+1)]
        return seal(root,config,attack,rows)
    return run


def test_template_resolves_three_targets_and_only_c3_manages_ids():
    s=settings();targets=campaign.validate_settings(s)
    assert len({targets[r] for r in ('ecu_on','receiver_on','attacker')})==3
    s['commands']['attacker'][-1]+=' --secoc-key /dummy/forbidden'
    with pytest.raises(ValueError,match='keyless'):campaign.validate_settings(s)


def streaming_settings():
    s=settings();s['ids_collection']={'mode':'stream-v2','max_event_bytes':123456789}
    s['commands']['ids_fetch'][-1]+=' --stream --max-total-bytes {ids_max_bytes}'
    return s


def test_streaming_settings_require_explicit_matching_budget():
    campaign.validate_settings(streaming_settings())
    for budget in (True,0,-1,'REPLACE_EVENT_BYTES',1.5):
        s=streaming_settings();s['ids_collection']['max_event_bytes']=budget
        with pytest.raises(ValueError,match='budget'):campaign.validate_settings(s)
    s=streaming_settings();s.pop('ids_collection')
    with pytest.raises(ValueError,match='ids_collection'):campaign.validate_settings(s)
    s=streaming_settings();s['commands']['ids_fetch'][-1]=s['commands']['ids_fetch'][-1].replace('{ids_max_bytes}','999999999')
    with pytest.raises(ValueError,match='placeholder'):campaign.validate_settings(s)


@pytest.mark.parametrize('stream_name,bound',[('stdout',1000),('stderr',65536)])
def test_pc_bounds_even_incompatible_remote_output_and_reaps_child(tmp_path,stream_name,bound):
    import subprocess,sys
    out=tmp_path/'received';err=tmp_path/'metadata'
    code='import os,time;os.write('+('1' if stream_name=='stdout' else '2')+',b"x"*'+str(bound+1)+');time.sleep(30)'
    with out.open('wb') as stdout,err.open('wb') as stderr:
        with pytest.raises(ValueError,match='PC collection bound'):
            campaign.fetch_ids([sys.executable,'-c',code],stdout=stdout,stderr=stderr,max_bytes=1000,timeout=2)
    assert (out if stream_name=='stdout' else err).stat().st_size==bound


def test_pc_deadline_and_nonzero_exit_remain_collection_failures(tmp_path):
    import subprocess,sys
    with (tmp_path/'received').open('wb') as stdout,(tmp_path/'metadata').open('wb') as stderr:
        with pytest.raises(subprocess.TimeoutExpired):
            campaign.fetch_ids([sys.executable,'-c','import time;time.sleep(30)'],
                stdout=stdout,stderr=stderr,max_bytes=1000,timeout=.1)
        result=campaign.fetch_ids([sys.executable,'-c','import sys;sys.exit(7)'],
            stdout=stdout,stderr=stderr,max_bytes=1000)
    assert result.returncode==7


def test_static_validation_does_not_create_output_or_launch(tmp_path,monkeypatch):
    remote=Mock(side_effect=AssertionError('static check cannot start actors'))
    monkeypatch.setattr(campaign.subprocess,'run',remote)
    args=argv(tmp_path);args.remove('--i-am-on-a-test-bus')
    assert campaign.main(args+['--validate-only'])==0
    remote.assert_not_called();assert not (tmp_path/'run').exists()


@pytest.mark.parametrize('role',['ecu_on','receiver_on'])
def test_mixed_protocol_is_rejected_before_any_ssh(tmp_path,monkeypatch,role):
    args=argv(tmp_path);s=settings()
    s['commands'][role][-1]=s['commands'][role][-1].replace('--protocol session-v2','--protocol legacy-v1')
    (tmp_path/'settings.json').write_text(json.dumps(s))
    remote=Mock(side_effect=AssertionError('must not launch SSH'))
    monkeypatch.setattr(campaign.subprocess,'run',remote)
    with pytest.raises(SystemExit):campaign.main(args)
    remote.assert_not_called();assert not (tmp_path/'run').exists()


@pytest.mark.parametrize('stage,count',[('pilot',1),('test360',30)])
def test_one_process_session_per_case_and_completed_count(tmp_path,monkeypatch,stage,count):
    calls=[];monkeypatch.setattr(campaign,'run_case',runner(calls))
    assert campaign.main(argv(tmp_path,stage))==0
    result=json.loads((tmp_path/'run/summary.json').read_text())
    assert len(calls)==12 and all(call[3]==count for call in calls)
    assert result['completed_trials']==12*count and result['process_sessions']==12


def test_recoverable_failure_retries_only_within_budget_then_defers(tmp_path,monkeypatch):
    calls=[]
    fail=lambda calls,c,a:dict(rows=[],status='ERROR',recoverable=True) if c==1 and a=='fuzzy' else None
    monkeypatch.setattr(campaign,'run_case',runner(calls,fail))
    assert campaign.main(argv(tmp_path)+['--max-recoveries','1','--continue-on-error'])==2
    result=json.loads((tmp_path/'run/summary.json').read_text())
    assert len(calls)==13 and result['completed_trials']==11 and result['remaining_trials']==1
    assert result['status']=='PARTIAL' and result['execution_error_sessions']==2


def test_unknown_failure_is_not_silently_skipped(tmp_path,monkeypatch):
    calls=[]
    monkeypatch.setattr(campaign,'run_case',runner(calls,lambda *_:dict(rows=[],status='ERROR',recoverable=False)))
    assert campaign.main(argv(tmp_path)+['--continue-on-error'])==2
    assert len(calls)==1


def test_resume_refuses_cleanup_uncertainty_or_changed_artifact_before_ssh(tmp_path,monkeypatch):
    args=argv(tmp_path);calls=[]
    monkeypatch.setattr(campaign,'run_case',runner(calls,lambda *_:dict(rows=[],status='ERROR',cleanup=False)))
    assert campaign.main(args)==2
    calls.clear()
    assert campaign.main(args+['--resume'])==2 and not calls
    root=tmp_path/'run/C1-fuzzy/session-001'
    manifest=json.loads((root/'manifest.json').read_text());manifest['cleanup_confirmed']=True
    campaign.save(root/'manifest.json',manifest)
    (root/'trials.json').write_text('[]\nchanged')
    assert campaign.main(args+['--resume'])==2 and not calls


def test_interruption_resumes_remaining_trials_without_duplicate(tmp_path,monkeypatch):
    args=argv(tmp_path,'test360');calls=[]
    def first(calls,c,a):
        if len(calls)==1:return dict(rows=[{'trial':1,'trial_completed':True,'status':'VALID'}],status='INTERRUPTED')
    monkeypatch.setattr(campaign,'run_case',runner(calls,first))
    assert campaign.main(args)==2
    monkeypatch.setattr(campaign,'run_case',runner(calls))
    assert campaign.main(args+['--resume'])==0
    assert calls[1][2]==2
    assert json.loads((tmp_path/'run/summary.json').read_text())['completed_trials']==360


def test_official_requires_complete_pilot_with_remote_identities_and_pins_reference(tmp_path,monkeypatch):
    calls=[];monkeypatch.setattr(campaign,'run_case',runner(calls))
    args=argv(tmp_path)
    assert campaign.main(args)==0
    official=argv(tmp_path,'official');official[official.index('--out')+1]=str(tmp_path/'official')
    with pytest.raises(SystemExit):campaign.main(official)
    path=tmp_path/'run/C1-fuzzy/session-001/manifest.json'
    manifest=json.loads(path.read_text());identity=manifest.pop('execution_identity');campaign.save(path,manifest)
    with pytest.raises(SystemExit):campaign.main(official+['--pilot-dir',str(tmp_path/'run')])
    assert len(calls)==12 and not (tmp_path/'official').exists()
    manifest['execution_identity']=identity;campaign.save(path,manifest)
    assert campaign.main(official+['--pilot-dir',str(tmp_path/'run')])==0
    metadata=json.loads((tmp_path/'official/campaign.json').read_text())
    assert set(metadata['reference_execution_identities'])=={'1','2','3'}
    assert len(metadata['pilot_identity_sha256'])==64
    assert json.loads((tmp_path/'official/summary.json').read_text())['completed_trials']==1200 # mock scheduling only


@pytest.mark.parametrize('damage',['source','model','data','dependencies','missing','cross_config_binary','input','missing_input','trace','missing_trace'])
def test_pilot_refuses_mixed_remote_sources_models_data_or_unknown_provenance(tmp_path,monkeypatch,damage):
    monkeypatch.setattr(campaign,'run_case',runner([]));assert campaign.main(argv(tmp_path))==0
    root=tmp_path/'run';path=root/'C3-fuzzy/session-001/manifest.json'
    manifest=json.loads(path.read_text());identity=manifest['execution_identity']
    if damage=='missing':identity.pop('ids')
    elif damage=='source':identity['attacker']['source_sha256']='1'*64
    elif damage=='model':identity['ids']['trained_model_sha256']='1'*64
    elif damage=='data':identity['ids']['normal_inputs']['train_normal']['sha256']='1'*64
    elif damage=='dependencies':identity['ids']['dependencies'].pop('scipy')
    elif damage=='input':identity['ecu']['input_configuration']['sensor']['values'][0]=41
    elif damage=='missing_input':identity['ecu'].pop('input_configuration')
    elif damage=='trace':identity['ecu']['trace_can_tx']=True
    elif damage=='missing_trace':identity['ecu'].pop('trace_can_tx')
    else:identity['ecu']['executable_sha256']='1'*64
    campaign.save(path,manifest)
    with pytest.raises(ValueError):campaign.pilot_identities(root,json.loads((root/'campaign.json').read_text()))


def test_session_fuzzy_never_injects_public_control_ids():
    import random
    from security.ids.session_detector import SESSION_IDS
    assert worker.SESSION_IDS==SESSION_IDS
    rng=random.Random(7)
    frames=[worker.injection_frames('fuzzy',rng,i,None,'isolated-session-v1')[0] for i in range(1000)]
    assert all(cid not in SESSION_IDS and len(data)==8 for cid,data in frames)


@pytest.mark.parametrize('clock_error,identity_mismatch,source_mismatch,visible,restored',[
    (False,False,False,False,True),(True,False,False,False,True),
    (False,True,False,False,True),(False,False,True,False,True),
    (False,False,False,True,True),(False,False,False,True,False)])
def test_case_cleans_before_collecting_and_uses_new_evaluator(tmp_path,monkeypatch,clock_error,identity_mismatch,source_mismatch,visible,restored):
    s=settings();s['ids_mode']='rules-only'
    if visible:
        s['display']={'mode':'wayland-single-owner'};s['commands']['display_owner']=['dummy-owned-display']
    f=fixture();run_id='DUMMY-C3-flooding-session-001'
    for rows in f['observers']:
        for row in rows:
            if row.get('result')=='PHASE':row['run_id']=run_id
    for row in f['ivi']:
        if 'run_id' in row:row['run_id']=run_id
    generation='00000000000040008000000000000001'
    ids_identity=execution_identity(3,'rules-only')['ids']
    actor_identity={'schema':'python-actor-startup-v1','python':'dummy','source_sha256':'c'*64,'interpreter':{'sha256':'b'*64}}
    class FakeChild:
        def __init__(self,name):
            self.name=name;self.output=SimpleNamespace(name=str(tmp_path/(name+'.jsonl')))
            self.records=deepcopy(f['ivi']) if name=='ivi' else []
            if name=='ecu':self.records=[input_lineage(),{'result':'OWNED_IDS_READY','generation':generation,'mode':'rules-only','protocol':'session-v2',
                'startup_identity':ids_identity},{'result':'ECU_PROCESS_STARTED','executable_sha256':'d'*64,
                    'supervisor_sha256':'e'*64,'owned_ids_sha256':'f'*64,'trace_can_tx':False}]
            if name.startswith('observer_'):self.records=[{'result':'READY','run_id':run_id,'execution_identity':actor_identity}]
            if name=='attacker':self.records=[{'result':'READY','run_id':run_id,'execution_identity':actor_identity,
                'role':'keyless-can-attacker','profiles':['isolated-session-v1']}]
            if name=='display_owner':self.records=[{'result':'READY','run_id':run_id,
                'role':'desktop-lease','source_sha256':'c'*64}]
            self.process=SimpleNamespace(stdin=SimpleNamespace(write=self.write,flush=lambda:None))
        def write(self,line):
            request=json.loads(line);assert request['profile']=='isolated-session-v1'
            self.records+=deepcopy(f['worker'])
        def ready(self,run_id):
            if self.name=='ivi':self.records[:0]=[{'result':'READY','secoc_on':True,'run_id':run_id},
                {'result':'REMOTE_START','run_id':run_id,'executable_sha256':'d'*64},
                {'result':'WINDOW_PRESENTED','run_id':run_id,'display_platform':'wayland'}]
        def snapshot(self):return self.records.copy()
    class FakeActors:
        instance=None
        def __init__(self):self.children=[];self.closed=False;FakeActors.instance=self
        def start(self,command,root,name):
            child=FakeChild(name);self.children.append(child);return child
        def check(self):pass
        def close(self):
            self.closed=True
            for child in self.children:
                kind='OBSERVER_STOPPED' if child.name.startswith('observer_') else 'ATTACKER_STOPPED' if child.name=='attacker' else 'REMOTE_STOPPED'
                child.records.append({'result':'DISPLAY_LEASE_STOPPED' if child.name=='display_owner' else kind,
                                      'run_id':run_id,'exit_code':0,'restored':restored})
                if child.name=='attacker' and clock_error:
                    child.records.append({'result':'ATTACKER_ERROR','run_id':run_id,'category':'clock'})
            return []
    phases=[]
    def barrier(observers,phase,actors):
        phases.append(phase)
        if phase=='baseline':
            for child,records in zip(observers,f['observers']):child.records+=deepcopy(records)
    def collect(*_):
        assert FakeActors.instance.closed
        return {generation:f['ids']}
    monkeypatch.setattr(campaign,'Actors',FakeActors)
    monkeypatch.setattr(campaign,'check_health',lambda *_:None)
    monkeypatch.setattr(campaign,'wait_seconds',lambda *_:None)
    monkeypatch.setattr(campaign,'prepare',lambda *_:None)
    monkeypatch.setattr(campaign,'phase_barrier',barrier)
    monkeypatch.setattr(campaign,'collect_ids',collect)
    args=SimpleNamespace(run_id='DUMMY',per_case=1,quiet_timeout=20,baseline=2,duration=3,post=2,
                         interface='can0',sensor_mode='constant',rate=1000)
    args.expected_identities={'3':execution_identity(3,'rules-only')}
    if visible:args.expected_identities['3']['ivi']['display_owner_sha256']='c'*64
    if source_mismatch:args.sensor_mode='ads1115'
    if identity_mismatch:args.expected_identities['3']['ecu']['executable_sha256']='1'*64
    root=tmp_path/'session-001'
    manifest,rows=campaign.run_case(s,args,3,'flooding',1,root)
    assert manifest['status']==('ERROR' if clock_error or identity_mismatch or source_mismatch or not restored else 'COMPLETE')
    assert manifest['cleanup_confirmed']==restored
    if visible:assert manifest['display_restoration_confirmed']==restored
    assert manifest['execution_identity']['ids']==ids_identity
    if clock_error:assert not manifest['recoverable'] and 'clock mapping' in manifest['error']
    if identity_mismatch or source_mismatch:
        assert not rows and not phases and not manifest['recoverable']
        assert 'no attack injected' in manifest['error']
        return
    assert phases==['baseline','attack','post','idle']
    if not restored:
        assert rows[0]['status']=='INVALID' and 'cleanup unconfirmed' in manifest['error']
        return
    assert rows[0]['status']=='VALID' and rows[0]['ivi_diagnostic_type_result']=='MATCH'


@pytest.mark.parametrize('damage',['missing','units','dt','label','mode','origin','field','soh_file','soh_units',
    'uuid','fresh_position','fresh_elapsed','nonfinite','intent'])
def test_missing_or_malformed_input_lineage_is_not_an_accepted_identity(damage):
    row=input_lineage();value=row['configuration']
    if damage=='missing':row.pop('configuration')
    elif damage=='units':value['sensor_units']['temperature']='K'
    elif damage=='dt':value['calculation_dt_s']=True
    elif damage=='label':value['ground_truth_label']='normal'
    elif damage=='mode':value['source_mode']='unknown'
    elif damage=='origin':value['sensor']['origin']='real_sensor'
    elif damage=='field':value['sensor']['private_path']='/DUMMY/DO-NOT-ACCEPT'
    elif damage=='soh_file':value['soh']['input']={'bytes':10,'sha256':'not-a-fingerprint'}
    elif damage=='soh_units':value['soh']['units']['capacity']='mAh'
    elif damage=='uuid':row['instance_id']='0'*32
    elif damage=='fresh_position':row['state']['profile_index']=1
    elif damage=='fresh_elapsed':row['state']['soh_elapsed_s']=.1
    elif damage=='nonfinite':value['sensor']['values'][0]=float('nan')
    elif damage=='intent':row['start_intent']='implicit'
    with pytest.raises(ValueError):campaign.validate_input_lineage(row)


def test_process_specific_lineage_changes_do_not_change_input_configuration():
    a=input_lineage();b=deepcopy(a)
    b['instance_id']='00000000000040008000000000000002'
    b['start_intent']='resume';b['state']['soh_elapsed_s']=2.5
    assert campaign.validate_input_lineage(a)['configuration']==campaign.validate_input_lineage(b)['configuration']


def test_worker_clock_fault_is_structured_and_still_closes(monkeypatch):
    messages=[];bus=Mock();bus.receive.side_effect=RuntimeError('capture clock mapping changed by more than 10ms')
    control=Mock();control.poll.return_value=None
    monkeypatch.setattr(worker,'healthy',lambda *_:None)
    monkeypatch.setattr(worker,'CaptureSocket',lambda *_,**__:bus)
    monkeypatch.setattr(worker,'emit',messages.append)
    with pytest.raises(RuntimeError,match='clock mapping'):
        worker.run('vcan0',1,'dummy',True,control=control,environment='vcan')
    assert any(row.get('result')=='ATTACKER_ERROR' and row['category']=='clock' for row in messages)
    assert messages[-1]['result']=='ATTACKER_STOPPED';bus.close.assert_called_once()


@pytest.mark.parametrize('tamper',[False,True])
def test_collected_ids_start_must_match_actual_ready_identity(tmp_path,monkeypatch,tamper):
    import hashlib
    generation='00000000000040008000000000000001'
    identity={'schema':'ids-startup-v1','mode':'rules-only','source_sha256':'a'*64}
    descriptor={'generation':generation,'mode':'rules-only','protocol':'session-v2','startup_identity':identity}
    def fetch(command,stdout,stderr,**_):
        kind=command[0]
        row={'result':'START','run_id':'owned-ids-'+generation,'protocol':'session-v2','mode':'rules-only',
             'startup_identity':dict(identity,source_sha256='b'*64) if tamper else identity}
        data=(json.dumps(row)+'\n').encode() if kind=='events' else b'dummy stdout\n'
        stdout.write(data);stderr.write((json.dumps({'schema':'owned-ids-log-v1','status':'COMPLETE',
            'generation':generation,'file':'events.jsonl' if kind=='events' else 'process.log',
            'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})+'\n').encode())
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(campaign,'fetch_ids',fetch)
    if tamper:
        with pytest.raises(campaign.CaseFailure,match='differs between READY'):
            campaign.collect_ids(['{log_kind}'],{},[descriptor],tmp_path,'rules-only')
    else:
        result=campaign.collect_ids(['{log_kind}'],{},[descriptor],tmp_path,'rules-only')
        assert result[generation].first['startup_identity']==identity


@pytest.mark.parametrize('stream',[False,True])
@pytest.mark.parametrize('measured',[False,True])
def test_actual_collector_cli_to_pc_disk_and_index_roundtrip(tmp_path,stream,measured):
    import sys
    from security.tests.test_session_ids_log import store,GEN
    root,_,events=store(tmp_path)
    identity=execution_identity(3,'rules-only')['ids']
    rows=[json.loads(line) for line in events.read_text().splitlines()]
    rows[0]['startup_identity']=identity
    if measured:
        from security.ids.resource_metrics import RuntimeMetrics
        metrics=RuntimeMetrics('owned-ids-'+GEN,'session-v2','live')
        metrics.start({'storage':'disabled','file_bytes':None,'file_sha256':None,'state_sha256':None})
        identity['resource_measurement']=True
        rows[0]['resource_measurement']=True
        rows.append(metrics.report('INTERRUPTED',final=True))
    events.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    descriptor={'generation':GEN,'protocol':'session-v2','mode':'rules-only','startup_identity':identity}
    if measured:descriptor['resource_measurement']=True
    command=[sys.executable,'-m','security.experiments.session_ids_log','--log-root',str(root),
        '--generation','{ids_generation}','--kind','{log_kind}']
    policy=None
    if stream:
        # Explicit fixture budget, not an adopted operational default.
        policy={'mode':'stream-v2','max_event_bytes':events.stat().st_size}
        command+=['--stream','--max-total-bytes','{ids_max_bytes}']
    output=tmp_path/'received';output.mkdir(mode=0o700)
    logs=campaign.collect_ids(command,{},[descriptor],output,'rules-only',policy,[(0.,2.)])
    assert list(logs[GEN].window(0.,2.))==[row for row in rows if row.get('result')!='RESOURCE_SUMMARY']
    assert list(logs[GEN].rows())==rows
    assert logs[GEN].sha256==campaign.sha256(events)
    assert all(p.stat().st_mode&0o077==0 for p in output.iterdir())
    report=output/('ids-'+GEN+'-resources.json')
    if measured:
        value=json.loads(report.read_text())
        assert value['status']=='INTERRUPTED' and value['final_summary_available']
        assert value['official_acceptance'] is False
    else:assert not report.exists()


def test_remote_start_identifies_launched_executable_without_logging_arguments(tmp_path):
    import hashlib,subprocess,sys
    result=subprocess.run([sys.executable,'-m','security.experiments.remote_process','--duration','1',
        '--run-id','dummy','--',sys.executable,'-c','import time;time.sleep(3)'],input='',capture_output=True,text=True,timeout=5)
    rows=[json.loads(line) for line in result.stdout.splitlines()]
    start=next(row for row in rows if row.get('result')=='REMOTE_START')
    assert start['pid']>0 and start['executable_sha256']==hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
    assert 'arguments' not in start and rows[-1]['result']=='REMOTE_STOPPED'


def test_visible_template_requires_IVI_owned_lease_and_never_offscreen_or_root():
    path=Path(__file__).parents[1]/'experiments/session-campaign-settings.template.json'
    visible=json.loads(path.read_text().replace('REPLACE_','dummy_'))
    campaign.validate_settings(visible)
    for damage in ('offscreen','sudo','target','missing_owner','unknown_mode'):
        s=deepcopy(visible)
        if damage=='offscreen':s['commands']['receiver_on'][-1]+=' QT_QPA_PLATFORM=offscreen'
        if damage=='sudo':s['commands']['receiver_on'][-1]='sudo '+s['commands']['receiver_on'][-1]
        if damage=='target':s['commands']['display_owner'][-2]='dummy@other-node'
        if damage=='missing_owner':s['commands'].pop('display_owner')
        if damage=='unknown_mode':s['display']['mode']='guess'
        with pytest.raises(ValueError):campaign.validate_settings(s)
