"""Historical endpoint attribution must not become invented model metrics."""
import json

import pytest
from tools.quality import legacy_if_history as history


def fixture(root,if_time=162.9):
    for attack,code in zip(('flooding','fuzzy','replay','spoofing'),(4,1,2,3)):
        folder=root/('C3-'+attack)/'attempt-001';folder.mkdir(parents=True)
        run_id='DUMMY-'+attack
        for name in history.FILES:(folder/name).write_text('')
        phases=[];events=[{'result':'START','mode':'rules+if','run_id':run_id},
            {'result':'READY','classification_version':'evidence-v2','mode':'rules+if','run_id':run_id}]
        for trial in range(1,31):
            start=(trial-1)*6
            phases += [{'result':'PHASE','run_id':run_id,'phase':phase,'t':start+offset}
                for phase,offset in zip(('baseline','attack','post','idle'),(0,2,4,5))]
            events.append({'result':'ANOMALY','reason':'DUMMY_RULE','timestamp':start+2.5,'attack_type':code})
        if attack=='flooding':events.append({'result':'ANOMALY','reason':'IF_ANOMALY','timestamp':if_time,'attack_type':0,'anomaly_score':2.38})
        (folder/'observer_a.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in phases))
        (folder/'ids-events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in events))
        (folder/'attempts.jsonl').write_text(''.join(json.dumps({'trial':i,'trial_completed':True,'status':'VALID'})+'\n' for i in range(1,31)))
        manifest={'status':'COMPLETE','cleanup_confirmed':True,'config':3,'ids_mode':'rules+if','run_id':run_id,
            'files_sha256':{name:history.sha256(folder/name) for name in history.FILES}}
        (folder/'manifest.json').write_text(json.dumps(manifest))


@pytest.mark.parametrize('endpoint,phase',[(162.9,'baseline'),(164.,'attack'),(166.,'post'),(167.,'outside_trial')])
def test_endpoints_obey_half_open_phases_without_inventing_window_rates(tmp_path,endpoint,phase):
    fixture(tmp_path,endpoint);report=history.analyze(tmp_path)
    assert report['verified_trials']==120 and report['if_positive_endpoint_total']==1
    event=report['groups'][0]['if_positive_endpoints'][0]
    assert event['endpoint_phase']==phase
    assert all(g['model_evaluation_records']==0 for g in report['groups'])
    assert 'window FPR/recall' in report['not_established'] and 'fpr' not in report


def test_altered_or_mixed_version_history_is_not_accepted(tmp_path):
    fixture(tmp_path);folder=tmp_path/'C3-flooding/attempt-001';events=folder/'ids-events.jsonl'
    events.write_text(events.read_text().replace('evidence-v2','evidence-v3'))
    with pytest.raises(ValueError,match='hash'):history.analyze(tmp_path)
    manifest=folder/'manifest.json';row=json.loads(manifest.read_text());row['files_sha256'][events.name]=history.sha256(events)
    manifest.write_text(json.dumps(row))
    with pytest.raises(ValueError,match='evidence-v2'):history.analyze(tmp_path)
