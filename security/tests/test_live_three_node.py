import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from security.experiments import live_three_node as live
from security.experiments.live_receiver import parse_failsafe_ok, Outcome
from security.experiments.live_trial import Record, TrialWindows, judge_trial
from security.ids.runtime_detector import RuntimeDetector, Observation


def settings():
    path=Path(__file__).parents[1]/'experiments/live-three-node-settings.template.json'
    return json.loads(path.read_text().replace('REPLACE_','test_'))


def test_template_separates_ecu_ids_from_ivi():
    live.validate_settings(settings())
    bad=settings();bad['ids'][4]=bad['receiver_on'][3]
    with pytest.raises(ValueError):live.validate_settings(bad)
    bad=settings();bad['ids'][-1]=bad['ids'][-1].replace('--calibrate-normal','--wrong-option')
    with pytest.raises(ValueError):live.validate_settings(bad)


def test_undefined_failsafe_reason_consistent_with_ids():
    for reason in range(9):
        payload=bytes([0,1,reason,150,65,0,0,0])
        events=RuntimeDetector().observe(Observation(0,0x101,payload))
        rejected=any(e.reason=='FAILSAFE_RANGE' for e in events)
        assert parse_failsafe_ok(payload)==(1<=reason<=7)
        assert rejected==(not parse_failsafe_ok(payload))


def test_live_type_detection_distinguishes_first_and_expected():
    records=[Record(2.1,0x200,bytes([1,100,0,0,0,0,0,1]),False),
             Record(2.2,0x200,bytes([4,100,0,0,0,0,0,1]),False)]
    row=judge_trial(3,'flooding',records,TrialWindows(0,2,5,6,2),1,0)
    assert row['first_alert_attack_code']==1
    assert row['observed_attack_codes']==[1,4]
    assert row['expected_type_detected'] is True
    assert row['expected_type_latency_s']==pytest.approx(.2)


def test_case_failure_stops_owned_actors_and_seals_evidence(tmp_path,monkeypatch):
    key=tmp_path/'dummy.key';key.write_bytes(bytes(32))
    config=tmp_path/'settings.json';config.write_text('{}')
    args=SimpleNamespace(run_id='test',trials=1,rate=1000,baseline=2,duration=3,post=1,
                         sensor_mode='constant',settings=str(config),key=str(key),interface='can0')
    bus=Mock();bus.receive.return_value=(object(),False)
    monkeypatch.setattr(live,'CaptureSocket',lambda *a,**k:bus)
    actors=Mock();actors.close.return_value=[]
    monkeypatch.setattr(live,'Actors',lambda:actors)
    root=tmp_path/'case'
    assert live.run_case(settings(),args,3,'flooding',root)=='ERROR'
    actors.close.assert_called_once();bus.close.assert_called_once()
    manifest=json.loads((root/'manifest.json').read_text())
    assert manifest['status']=='ERROR'
    assert 'attempts.jsonl' in manifest['files_sha256']
    assert not (root/'ecu.jsonl').exists()


def test_official_campaign_invokes_twelve_cases_of_100(tmp_path,monkeypatch):
    cfg=tmp_path/'settings.json';cfg.write_text(json.dumps(settings()))
    key=tmp_path/'dummy.key';key.write_bytes(bytes(32))
    pilot=tmp_path/'pilot';pilot.mkdir()
    phases={'rate':1000.,'duration':3.,'baseline':2.,'post':1.,'sensor_mode':'constant','interface':'can0'}
    (pilot/'campaign.json').write_text(json.dumps({'trials':1,'settings_sha256':live.sha256(cfg),'phases':phases}))
    monkeypatch.setattr(live,'summarize_campaign',lambda root:{'valid_trials':12 if root==pilot else 1200,'complete_cases':12})
    monkeypatch.setattr(live,'inspect_interface',lambda *a:None)
    cases=[]
    def run(settings,args,config,attack,root):
        cases.append((config,attack,args.trials));return 'COMPLETE'
    monkeypatch.setattr(live,'run_case',run)
    assert live.main(['--settings',str(cfg),'--out',str(tmp_path/'full'),'--run-id','full',
                      '--key',str(key),'--stage','official','--pilot-dir',str(pilot),
                      '--i-am-on-a-test-bus'])==0
    assert len(cases)==len(set(cases))==12
    assert sum(count for _,_,count in cases)==1200


@pytest.mark.parametrize('resilient', [False, True])
def test_successful_remote_case_links_ivi_and_seals_summary(tmp_path,monkeypatch,resilient):
    key=tmp_path/'dummy.key';key.write_bytes(bytes(32))
    cfg=tmp_path/'settings.json';cfg.write_text(json.dumps(settings()))
    root=tmp_path/'campaign';root.mkdir()
    (root/'settings.json').write_bytes(cfg.read_bytes())
    (root/'campaign.json').write_text(json.dumps({'trials':1,'settings_sha256':live.sha256(cfg)}))
    args=SimpleNamespace(run_id='test',trials=1,rate=1000,baseline=2,duration=3,post=1,
                         sensor_mode='constant',settings=str(cfg),key=str(key),interface='can0')
    bus=Mock();bus.receive.return_value=None;bus.dropped=0
    monkeypatch.setattr(live,'CaptureSocket',lambda *a,**k:bus)
    ivi_rows=[{'result':'READY','run_id':'test-C3-flooding','secoc_on':True}]
    ivi=Mock();ivi.snapshot.side_effect=lambda:list(ivi_rows)
    ids=Mock();ids.snapshot.return_value=[{'result':'READY','mode':'rules+if','send_alerts':True}]
    actors=Mock();actors.start.side_effect=[ivi,Mock(),ids];actors.close.return_value=[]
    if resilient:
        from security.experiments import test360_support
        observer=Mock();observer.snapshot.return_value=[{'result':'OBS_FRAME','phase':'attack','can_id':0,'data':bytes(8).hex()}]
        actors.start.side_effect=[observer,observer,ivi,Mock(),ids]
        actors.children=[]
        args.resilient=True
        monkeypatch.setattr(test360_support,'phase_barrier',lambda *a:None)
    monkeypatch.setattr(live,'Actors',lambda:actors)
    calls=[]
    raw=bytes.fromhex('96be1068ffec4100');alert=bytes.fromhex('0464000000000001')
    def collect(bus,receiver,duration,stream,actors,*attack_args):
        calls.append(duration)
        stream.write('{}\n')
        if len(calls)==1:return [],0,0,None,0,3
        if len(calls)==2:
            frames=[Record(3+i*.1,0x100,raw,False,[Outcome('PUBLISHED',0x100,payload=raw)]) for i in range(20)]
            return frames,0,0,None,3,5
        if len(calls)==3:
            publication={'result':'FRAME','can_id':0x200,'process_result':2,'data':alert.hex()}
            if resilient:
                def close():
                    ivi_rows.append(publication)
                    return []
                actors.close.side_effect=close
            else:
                ivi_rows.append(publication)
            return [Record(5,0,bytes(8),True),Record(5.1,0x200,alert,False)],1,0,5,5,8
        return [],0,0,None,8,9
    monkeypatch.setattr(live,'collect',collect)
    config_settings=settings()
    if resilient:
        config_settings.update(observer_a=['dummy'],observer_b=['dummy'])
    assert live.run_case(config_settings,args,3,'flooding',root/'C3-flooding')=='COMPLETE'
    manifest,rows=live.read_run(root/'C3-flooding')
    assert rows[0]['status']=='VALID'
    if resilient:
        assert rows[0]['ivi_type_result']=='MATCH'
        assert rows[0]['remote_arrival']['ivi']['matching_frames']==1
    assert rows[0]['expected_type_detected'] is True
    assert rows[0]['ivi_expected_type_published'] is True
    summary=live.summarize_campaign(root)
    assert summary['attempted_trials']==summary['valid_trials']==1
    group=next(r for r in summary['summary'] if r['config']==3 and r['attack']=='flooding')
    assert group['detection_rate']==1
    assert group['mean_detected_latency_s']==pytest.approx(.1)
    (root/'C3-flooding/flooding-001.jsonl').write_text('tampered')
    with pytest.raises(ValueError,match='hash'):live.summarize_campaign(root)
