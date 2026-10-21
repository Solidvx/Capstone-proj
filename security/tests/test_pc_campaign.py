import base64
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from security.experiments import pc_campaign as pc
from security.experiments import live_three_node_test360 as scheduler
from security.experiments import can_attack_worker as worker
from security.experiments import retire_pi3_ssh as retire
from security.tests.test_live_three_node_test360 import install_fake


def settings():
    path=Path(__file__).parents[1]/'experiments/pc-campaign-settings.template.json'
    return json.loads(path.read_text().replace('REPLACE_','dummy_'))


def argv(tmp_path,stage='test360'):
    cfg=tmp_path/'settings.json';cfg.write_text(json.dumps(settings()))
    return ['--settings',str(cfg),'--out',str(tmp_path/'run'),'--run-id','dummy',
            '--stage',stage,'--i-am-on-a-test-bus']


def test_pc_template_roles_no_local_health_or_attacker_key():
    cfg=settings();targets=pc.validate_pc_settings(cfg)
    assert len(set((targets['ecu'],targets['receiver_on'],targets['attacker'])))==3
    assert all(cfg[r][0]=='ssh' for r in ('attacker','health_a','health_b','health_c'))
    cfg['attacker'][-1]+=' --key /dummy/key'
    with pytest.raises(ValueError,match='SecOC'):pc.validate_pc_settings(cfg)


@pytest.mark.parametrize('stage,count',[('pilot',1),('test360',30)])
def test_pc_runs_from_controller_without_key_or_local_can(tmp_path,monkeypatch,stage,count):
    calls,health=install_fake(monkeypatch)
    monkeypatch.setattr(pc,'run_case',scheduler.live.run_case)
    monkeypatch.setattr(scheduler.live,'inspect_interface',Mock(side_effect=AssertionError('PC has no CAN')))
    assert pc.main(argv(tmp_path,stage))==0
    assert len(calls)==12 and {c[3] for c in calls}=={count}
    result=json.loads((tmp_path/'run/summary.json').read_text())
    assert result['completed_trials']==12*count
    with pytest.raises(SystemExit):pc.main(argv(tmp_path,stage)+['--key','forbidden'])


def test_pc_official_requires_clean_pc_pilot(tmp_path,monkeypatch):
    calls,health=install_fake(monkeypatch)
    monkeypatch.setattr(pc,'run_case',scheduler.live.run_case)
    pilot_args=argv(tmp_path,'pilot')
    assert pc.main(pilot_args)==0
    official=argv(tmp_path,'official')
    official[official.index('--out')+1]=str(tmp_path/'official')
    assert pc.main(official+['--pilot-dir',str(tmp_path/'run')])==0
    assert {c[3] for c in calls[12:]}=={100}
    assert len(calls)==24


def captures(code=4,arrival=True):
    out=[{'result':'PHASE','phase':'baseline','t':1.,'rx_dropped':0},
         {'result':'OBS_FRAME','phase':'baseline','can_id':0x100,'data':'00'*8},
         {'result':'PHASE','phase':'attack','t':2.,'rx_dropped':0},
         {'result':'PHASE','phase':'idle','t':5.,'rx_dropped':0}]
    if arrival:out.append({'result':'OBS_FRAME','phase':'attack','can_id':0,'data':'00'*8})
    if code:out.append({'result':'OBS_FRAME','phase':'post','can_id':0x200,'data':f'{code:02x}'+'00'*7})
    return out


def iviframes():
    return [{'result':'FRAME','can_id':0x102,'data':'00'*8,'timestamp_ns':'1500000000','process_result':2},
            {'result':'FRAME','can_id':0x200,'data':'04'+'00'*7,'timestamp_ns':'3000000000','process_result':2},
            {'result':'FRAME','can_id':0x200,'data':'01'+'00'*7,'timestamp_ns':'9000000000','process_result':2}]


def idsevents():
    return [{'result':'ANOMALY','timestamp':3.,'attack_type':4},
            {'result':'ALERT_SENT','timestamp':3.,'data':'04'+'00'*7,'attack_type':4}]


def attackrecords():
    return [{'result':'TX','trial':1,'can_id':0,'data':'00'*8},
            {'result':'ATTACK_DONE','trial':1,'sent':1,'tx_errors':0}]


def test_ivi_same_host_window_and_unmeasured_blocking():
    row=pc.evaluate(3,'flooding',1,attackrecords(),[captures(),captures()],iviframes(),idsevents())
    assert row['status']=='VALID' and row['ivi_type_result']=='MATCH'
    assert row['ivi_published_attack_codes']==[4]  # later trial's alert excluded
    assert row['blocked'] is None and row['attack_success'] is None


def test_local_transmit_does_not_substitute_remote_arrival():
    row=pc.evaluate(3,'flooding',1,attackrecords(),[captures(arrival=False),captures()],iviframes(),idsevents())
    assert row['status']=='INVALID' and 'ECU_ARRIVAL_UNVERIFIED' in row['invalid_reason']


def test_ivi_baseline_auth_failure_is_invalid():
    row=pc.evaluate(3,'flooding',1,attackrecords(),[captures(),captures()],[],idsevents())
    assert 'IVI_BASELINE_NOT_PUBLISHED' in row['invalid_reason']


def test_replay_copies_observed_raw_auth_without_key():
    raw=SimpleNamespace(can_id=0x100,data=b'rawbytes',t=1.)
    auth=SimpleNamespace(can_id=0x102,data=b'macbytes',t=1.01)
    assert worker.replay_pair([raw,auth],True)==[(0x100,b'rawbytes'),(0x102,b'macbytes')]
    assert worker.replay_pair([raw],False)==[(0x100,b'rawbytes')]
    with pytest.raises(RuntimeError):worker.replay_pair([auth,raw],True)


def test_worker_injects_on_can_and_stops_on_controller_loss(monkeypatch):
    bus=Mock(dropped=0);bus.receive.return_value=None
    control=Mock();control.poll.side_effect=EOFError('disconnected')
    req={'attack':'flooding','rate':1000,'duration':1,'trial':1,'seed':1,'interface':'can0','secoc':True}
    with pytest.raises(EOFError):worker.inject(bus,req,control,worker.time.monotonic()+5,True)
    bus.send.assert_not_called()
    control.poll.return_value=None;control.poll.side_effect=None
    ticks=iter([0,0,0,.1,.1,.1,2])
    monkeypatch.setattr(worker.time,'monotonic',lambda:next(ticks))
    worker.inject(bus,req,control,5,True)
    bus.send.assert_called_once_with(0,bytes(8))


def public(blob=b'dedicated-test-key'):
    return 'ssh-ed25519 '+base64.b64encode(blob).decode()+' capstone-experiment\n'


def test_cleanup_preview_and_exact_key_only(tmp_path):
    ssh=tmp_path/'.ssh';ssh.mkdir()
    path=ssh/'authorized_keys'
    target=public();other=public(b'other').replace('capstone-experiment','other')
    path.write_text(other+target+'restrict '+target)
    result=retire.remove_authorization(tmp_path,target)
    assert result['matching_lines']==2 and path.read_text()==other+target+'restrict '+target
    result=retire.remove_authorization(tmp_path,target,True)
    assert path.read_text()==other
    assert Path(result['backup']).read_text()==other+target+'restrict '+target


def test_cleanup_rejects_symlink_and_wrong_key(tmp_path):
    ssh=tmp_path/'.ssh';ssh.mkdir()
    path=ssh/'authorized_keys';outside=tmp_path/'outside';outside.write_text(public())
    path.symlink_to(outside)
    with pytest.raises(ValueError,match='symlink'):retire.remove_authorization(tmp_path,public(),True)
    with pytest.raises(ValueError):retire.public_identity(public().replace('capstone-experiment','personal'))


def test_cleanup_only_dedicated_pair(tmp_path,monkeypatch):
    ssh=tmp_path/'.ssh';ssh.mkdir()
    (ssh/'capstone_experiment.pub').write_text(public())
    (ssh/'capstone_experiment').write_text('dummy private')
    (ssh/'id_ed25519').write_text('unrelated')
    monkeypatch.setattr(retire,'inspect_local',lambda home:(public(),retire.public_identity(public())[2]))
    retire.remove_key(tmp_path,public(),False)
    assert (ssh/'capstone_experiment').exists()
    retire.remove_key(tmp_path,public(),True)
    assert not (ssh/'capstone_experiment').exists()
    assert (ssh/'id_ed25519').read_text()=='unrelated'


def test_pc_session_keeps_processes_alive_and_seals_all_logs(tmp_path,monkeypatch):
    cfg=tmp_path/'settings.json';cfg.write_text(json.dumps(settings()))
    args=SimpleNamespace(run_id='pc',trials=2,start_trial=1,baseline=2,duration=1,post=1,
                         sensor_mode='constant',interface='can0',rate=10,settings=str(cfg))
    rid='pc-C3-flooding'
    data={name:[] for name in ('observer_a','observer_b','ivi','ecu','ids-console','attacker')}
    data['ivi']=[{'result':'READY','secoc_on':True}]
    data['ids-console']=[{'result':'READY','mode':'rules+if','send_alerts':True}]
    data['attacker']=[{'result':'READY','role':'keyless-can-attacker'}]
    children={}
    root=tmp_path/'case'
    actors=pc.Actors()
    def start(command,directory,name):
        child=Mock();child.snapshot.side_effect=lambda:list(data[name]);child.ready.return_value=None
        def stop():
            data[name].append({'result':'ATTACKER_STOPPED' if name=='attacker' else 'OBSERVER_STOPPED' if name.startswith('observer') else 'REMOTE_STOPPED','run_id':rid})
            (directory/(name+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in data[name]))
        child.stop.side_effect=stop
        actors.children.append(child);children[name]=child
        return child
    actors.start=Mock(side_effect=start)
    monkeypatch.setattr(pc,'Actors',lambda:actors)
    current=[0]
    def wait(actors,duration,child=None,trial=None):
        if trial:
            current[0]=trial
            data['attacker'] += [{**r,'trial':trial} for r in attackrecords()]
            return data['attacker'][-1]
    monkeypatch.setattr(pc,'wait_for',wait)
    def phase(observers,label,actors):
        if label=='baseline':
            data['ivi'].append(iviframes()[0])
            for name in ('observer_a','observer_b'):data[name].extend(captures()[:2])
        if label=='attack':
            for name in ('observer_a','observer_b'):data[name].append(captures()[2])
        if label=='idle':
            for name in ('observer_a','observer_b'):data[name].extend(captures()[3:])
    monkeypatch.setattr(pc,'phase_barrier',phase)
    # Publish IVI frames only at shutdown: PC evaluation must use the drained log.
    original_close=actors.close
    def close():
        data['ivi'].extend(iviframes())
        return original_close()
    actors.close=Mock(side_effect=close)
    def fetch(command,stdout,stderr,**kwargs):
        stdout.write(json.dumps({'result':'START','run_id':rid})+'\n')
        for row in idsevents():stdout.write(json.dumps(row)+'\n')
    monkeypatch.setattr(pc.subprocess,'run',fetch)
    assert pc.run_case(settings(),args,3,'flooding',root)=='COMPLETE'
    manifest,rows=scheduler.live.read_run(root)
    assert len(rows)==2 and all(r['ivi_type_result']=='MATCH' for r in rows)
    assert actors.start.call_count==6
    actors.close.assert_called_once()
    assert 'ids-events.jsonl' in manifest['files_sha256']
    (root/'attacker.jsonl').write_text('tampered')
    with pytest.raises(ValueError,match='hash'):scheduler.live.read_run(root)


def test_ids_log_link_rejects_unattributed_ivi_alert():
    row=pc.evaluate(3,'flooding',1,attackrecords(),[captures(),captures()],iviframes(),[])
    assert row['status']=='VALID'
    assert row['ivi_published_attack_codes']==[4]
    assert row['ivi_type_result']=='MISSED'
    assert row['ecu_ids_type_result']=='MISSED'


def test_secoc_raw_pending_is_not_authenticated_baseline():
    frames=iviframes();frames[0]['can_id']=0x100;frames[0]['process_result']=1
    row=pc.evaluate(3,'flooding',1,attackrecords(),[captures(),captures()],frames,idsevents())
    assert row['status']=='INVALID'
    assert 'IVI_BASELINE_NOT_PUBLISHED' in row['invalid_reason']


def test_cleanup_refuses_pc_using_the_retired_key(tmp_path,monkeypatch):
    cfg=settings();path=tmp_path/'settings.json';path.write_text(json.dumps(cfg))
    fp=retire.public_identity(public())[2]
    def run(command,**kwargs):
        if command[0]=='ssh-keygen':return SimpleNamespace(stdout='256 '+fp+' capstone-experiment (ED25519)')
        return SimpleNamespace(stdout=json.dumps({'public_key':public(),'fingerprint':fp}))
    monkeypatch.setattr(retire.subprocess,'run',run)
    destructive=Mock();monkeypatch.setattr(retire,'remote',destructive)
    with pytest.raises(ValueError,match='own key'):retire.main(['--settings',str(path),'--apply'])
    destructive.assert_not_called()


def test_evidence_collection_error_after_last_trial_blocks_resume(tmp_path,monkeypatch):
    calls,_=install_fake(monkeypatch)
    monkeypatch.setattr(pc,'run_case',scheduler.live.run_case)
    arguments=argv(tmp_path,'pilot')
    assert pc.main(arguments)==0
    manifest=next((tmp_path/'run').glob('C*/attempt-*/manifest.json'))
    content=json.loads(manifest.read_text());content['status']='ERROR'
    manifest.write_text(json.dumps(content))
    assert pc.main(arguments+['--resume'])==2
    assert len(calls)==12


def test_fuzzy_injected_alert_id_is_not_ids_off_failure():
    tx = attackrecords() + [{'result':'TX','trial':1,'can_id':0x200,'data':'e429935ca80f489d'}]
    records = captures(code=0) + [{'result':'OBS_FRAME','phase':'attack','can_id':0x200,'data':'e429935ca80f489d'}]
    baseline = [{'result':'FRAME','can_id':0x100,'timestamp_ns':'1500000000','process_result':2}]
    assert not pc.unexpected_off_alert(records,tx,1)
    assert pc.unexpected_off_alert(records,tx,2)
    row = pc.evaluate(1,'fuzzy',1,tx,[records,records],baseline)
    assert row['status'] == 'VALID'
    records.append({'result':'OBS_FRAME','phase':'post','can_id':0x200,'data':'0400000000000000'})
    assert pc.unexpected_off_alert(records,tx,1)
    assert 'ALERT_WITH_IDS_OFF' in pc.evaluate(1,'fuzzy',1,tx,[records,records],baseline)['invalid_reason']


def test_pc_deferred_case_does_not_stop_other_cases(tmp_path,monkeypatch):
    calls,health=install_fake(monkeypatch,[('ERROR',False,True)]*3)
    monkeypatch.setattr(pc,'run_case',scheduler.live.run_case)
    command=argv(tmp_path,'pilot')+['--continue-on-error','--no-can-reset']
    assert pc.main(command)==2
    result=json.loads((tmp_path/'run/summary.json').read_text())
    assert result['status']=='PARTIAL' and result['completed_trials']==11
    assert result['remaining_trials']==1 and len(calls)==14
    assert not any(c.kwargs.get('recover') for c in health.call_args_list)
    assert pc.main(command+['--resume'])==0
    assert len(calls)==15


def test_pc_continue_never_skips_terminal_errors(tmp_path,monkeypatch):
    calls,_=install_fake(monkeypatch,[('ERROR',False,False)])
    monkeypatch.setattr(pc,'run_case',scheduler.live.run_case)
    assert pc.main(argv(tmp_path,'pilot')+['--continue-on-error'])==2
    assert len(calls)==1
