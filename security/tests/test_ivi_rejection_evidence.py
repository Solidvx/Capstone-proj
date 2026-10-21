import json
from security.experiments import inspect_ivi_rejections as report


def test_replay_source_publication_is_not_declared_attack_success(tmp_path,monkeypatch):
    p=tmp_path/'C3-replay/attempt-001';p.mkdir(parents=True)
    monkeypatch.setattr(report,'read_run',lambda _:({'cleanup_confirmed':True},[{'trial_completed':True,'config':3,'attack_type':'replay','trial':1}]))
    files={'attacker.jsonl':[{'result':'TX','trial':1,'can_id':258,'data':'dummy'}],
           'observer_b.jsonl':[{'result':'PHASE','phase':'attack','t':1},{'result':'PHASE','phase':'idle','t':4}],
           'ivi.jsonl':[{'result':'FRAME','can_id':258,'data':'dummy','timestamp_ns':str(t*10**9),'process_result':result,'message':'dummy'} for t,result in [(2,2),(3,3),(5,3)]]}
    for name,rows in files.items():(p/name).write_text(''.join(json.dumps(r)+'\n' for r in rows))
    row=report.inspect(tmp_path)['trials'][0]
    assert row['published']==1 and row['rejected']==1 and row['candidate_frames']==2
    assert row['blocking_rate'] is None
