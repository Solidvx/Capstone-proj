"""Protocol and per-host clock boundaries; fixtures are synthetic, not rates."""
from copy import deepcopy
import json
import uuid

import pytest

from security.experiments.session_campaign_evidence import evaluate, IndexedIdsLog
from security.ids.observation_status import ObservationStatus

RUN='dummy-session-trial'
CONTEXT='ab'*16
SOURCE=uuid.UUID('00000000-0000-4000-8000-000000000001')


def observer(offset):
    rows=[{'result':'PHASE','phase':phase,'run_id':RUN,'t':offset+t,'rx_dropped':0}
          for phase,t in zip(('baseline','attack','post','idle'),(0,2,4,6))]
    rows += [{'result':'OBS_FRAME','t':offset+.1,'can_id':0x100,'data':'64'+'00'*7,'error':False,'rx_dropped':0},
             {'result':'OBS_FRAME','t':offset+2.1,'can_id':0x080,'data':'00'*8,'error':False,'rx_dropped':0}]
    return rows


def fixture():
    # A's clock is near10000; B's near100. Neither is the worker's clock.
    worker=[{'result':'TX','trial':1,'t':300000.,'can_id':0x80,'data':'00'*8},
            {'result':'ATTACK_DONE','trial':1,'sent':1,'tx_errors':0}]
    node=bytearray(56);node[:16]=SOURCE.bytes;node[32:35]=bytes((2,1,2));node[53]=1
    def diagnostic(kind,body,t,seq):
        return {'result':'AUTHENTICATED_DIAGNOSTIC','kind':kind,'body_hex':bytes(body).hex(),
            'session_id':CONTEXT,'sequence':str(seq),'received_monotonic_ms':str(round(t*1000)),
            'verified_monotonic_ms':str(round(t*1000)+1),'observation_ready':True,
            'condition_mask':body[48] if kind==7 else 0}
    ivi=[diagnostic(1,node,100.8,1)]
    for seq,t,title in [(1,100.25,'새 보안 알림 없음'),(2,103.,'Flooding')]:
        stamps={'measurement_sequence':str(seq),'t1_received_ns':str(round((t-.001)*1e9)),
                't2_published_ns':str(round(t*1e9))}
        ivi += [{'result':'SESSION_PUBLICATION',**stamps,'run_id':RUN,'session_generation':'1','valid':True,'stale':False},
                {'result':'VIEW_MODEL_PUBLICATION',**stamps,'t3_view_model_ns':str(round((t+.001)*1e9)),'security':title}]
    ids=[{'result':'START','protocol':'session-v2','mode':'rules-only'},
         {'result':'ANOMALY','timestamp':10002.2,'attack_type':4}]
    producer=ObservationStatus(SOURCE,started_ms=0)
    for index,t in enumerate((99.5,100.5,101.5,102.5,103.5,104.5,105.5),1):
        body,_=producer.update(start_ms=(index-1)*1000,end_ms=index*1000,frames=20,dropped=0,
                               condition_mask=8 if 102<=t<105 else 0)
        ivi.append(diagnostic(7,body,t,index+1))
        ids.append({'result':'DIAGNOSTIC_IPC','kind':7,'body_hex':body.hex(),'timestamp':t+9900,'local_accepted':True})
    return dict(config=3,attack='flooding',trial=1,run_id=RUN,worker=worker,
                observers=[observer(10000),observer(100)],ivi=ivi,ids=ids,ids_mode='rules-only')


def test_independent_node_clocks_and_diagnostic_delivery_match():
    row=evaluate(**fixture())
    assert row['status']=='VALID',row
    assert [row[name] for name in ('ecu_ids_type_result','ivi_diagnostic_type_result','ivi_view_model_type_result')]==['MATCH']*3
    assert row['ivi_baseline_publications']==1 and row['ivi_attack_post_publications']==1
    assert row['blocked'] is None and row['detect_latency_s'] is None and not row['screen_pixels_evaluated']


def test_initial_diagnostic_sequence_zero_matches_the_wire_sender():
    f=fixture();f['ivi'][0]['sequence']='0'
    assert evaluate(**f)['status']=='VALID'
    f['ivi'][0]['sequence']=str(2**32)
    assert evaluate(**f)['status']=='INVALID'


@pytest.mark.parametrize('damage',['none','epoch','ipc','if','bad_timestamp_outside_window'])
def test_file_index_matches_whole_log_evaluation_without_hiding_bad_evidence(tmp_path,damage):
    f=fixture()
    if damage=='epoch':f['ids'].append({'result':'RECEIVE_EPOCH_RESET','timestamp':10003.})
    if damage=='ipc':f['ids'][-2]['local_accepted']=False
    if damage=='if':
        f['ids_mode']='rules+if';f['ids'][0]['mode']='rules+if'
        f['ids'].append({'result':'MODEL_EVALUATION','timestamp':10003.,'input_complete':False,'anomaly_score':-.1})
    if damage=='bad_timestamp_outside_window':f['ids'].append({'result':'NORMAL','timestamp':'nan'})
    # Deliberately scramble timestamps and add both exact interval boundaries.
    f['ids'][1:]=list(reversed(f['ids'][1:]))
    f['ids'] += [{'result':'ANOMALY','timestamp':9999.,'attack_type':1},
                 {'result':'ANOMALY','timestamp':10006.,'attack_type':1}]
    expected=evaluate(**f)
    path=tmp_path/'events.jsonl';path.write_text(''.join(json.dumps(row)+'\n' for row in f['ids']))
    index=IndexedIdsLog(path,[(10000.,10006.)])
    assert evaluate(**dict(f,ids=index))==expected


def test_index_uses_trial_ranges_and_preserves_overlaps_and_out_of_order_rows(tmp_path,monkeypatch):
    import security.experiments.session_campaign_evidence as evidence
    rows=[{'result':'START'}]
    rows += [{'result':'EVENT','timestamp':i+.5,'padding':'x'*500} for i in range(1000)]
    rows[101],rows[103]=rows[103],rows[101]
    path=tmp_path/'events.jsonl';path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    index=IndexedIdsLog(path,[(100.,106.),(102.,104.),(2000.,2001.)])
    loads=evidence.json.loads;calls=[]
    def counted(line):calls.append(len(line));return loads(line)
    monkeypatch.setattr(evidence.json,'loads',counted)
    for window in ((100.,106.),(102.,104.),(2000.,2001.)):
        expected=[rows[0]]+[row for row in rows[1:] if window[0]<=row['timestamp']<window[1]]
        view=index.window(*window)
        assert list(view)==expected and list(view)==expected
    assert len(calls)<30  # Repeated trial views do not decode the whole 1001-row file.


@pytest.mark.parametrize('change',['append','replace','remove'])
def test_index_refuses_file_changes_before_evaluation(tmp_path,change):
    f=fixture();path=tmp_path/'events.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in f['ids']))
    index=IndexedIdsLog(path,[(10000.,10006.)])
    if change=='append':
        with path.open('a') as stream:stream.write('{}\n')
    elif change=='replace':
        replacement=path.with_suffix('.new');replacement.write_text(path.read_text());replacement.replace(path)
    else:path.unlink()
    actual=evaluate(**dict(f,ids=index))
    assert actual['status']=='INVALID' and 'MALFORMED_OR_MISSING_EVIDENCE' in actual['invalid_reasons']


@pytest.mark.parametrize('data',[b'',b'{}\n',b'{"result":"START"}\n{}',
    b'{"result":"START"}\n{broken\n',b'{"result":"START"}\n{"result":"START"}\n'])
def test_bad_file_cannot_be_indexed_as_complete(tmp_path,data):
    path=tmp_path/'events.jsonl';path.write_bytes(data)
    with pytest.raises(ValueError):IndexedIdsLog(path)


@pytest.mark.parametrize('mutation,reason',[
    ('missing_completion','ATTACK_COMPLETION_UNVERIFIED'),('no_remote_arrival','IVI_ARRIVAL_UNVERIFIED'),
    ('drop','IVI_CAPTURE_ERROR'),('generation','SESSION_GENERATION_UNVERIFIED'),
    ('session','DIAGNOSTIC_SESSION_UNVERIFIED'),('view_link','VIEW_MODEL_LINK_UNVERIFIED'),
    ('prior_attack','IDS_BASELINE_NOT_QUIET'),('ipc','IDS_IPC_FAILURE'),
    ('epoch','IDS_CLOCK_RESET'),('missing_ipc','DIAGNOSTIC_IPC_LINK_UNVERIFIED'),
    ('gap','OBSERVATION_GAP'),('stale','PUBLICATION_QUALITY_INVALID'),
])
def test_incomplete_or_contaminated_evidence_is_invalid(mutation,reason):
    f=fixture()
    if mutation=='missing_completion':f['worker'].pop()
    if mutation=='no_remote_arrival':f['observers'][1]=[r for r in f['observers'][1] if r.get('can_id')!=0x80]
    if mutation=='drop':f['observers'][1][-1]['rx_dropped']=1
    if mutation=='generation':next(r for r in f['ivi'] if r.get('measurement_sequence')=='2')['session_generation']='2'
    if mutation=='session':f['ivi'][0]['session_id']='cd'*16
    if mutation=='view_link':next(r for r in f['ivi'] if r['result']=='VIEW_MODEL_PUBLICATION')['t1_received_ns']='1'
    if mutation=='prior_attack':f['ids'][1]['timestamp']=10001.
    if mutation=='ipc':f['ids'][-2]['local_accepted']=False
    if mutation=='epoch':f['ids'].append({'result':'RECEIVE_EPOCH_RESET','timestamp':10003.})
    if mutation=='missing_ipc':f['ids']=[r for r in f['ids'] if r.get('result')!='DIAGNOSTIC_IPC']
    if mutation=='gap':f['ivi']=[r for r in f['ivi'] if not (r.get('kind')==7 and int(r['received_monotonic_ms'])>=102000)]
    if mutation=='stale':next(r for r in f['ivi'] if r['result']=='SESSION_PUBLICATION')['stale']=True
    row=evaluate(**f)
    assert row['status']=='INVALID' and reason in row['invalid_reasons'],row
    assert row['ivi_diagnostic_type_result']=='INVALID'


def test_legacy_alert_cannot_replace_new_diagnostic_or_model_publication():
    f=fixture()
    f['ivi']=[{'result':'FRAME','can_id':0x200,'process_result':2,'timestamp_ns':'103000000000','data':'04'+'00'*7}]
    row=evaluate(**f)
    assert row['status']=='INVALID' and row['ivi_diagnostic_attack_codes']==[]


def test_if_mode_needs_actual_complete_inference_not_just_its_mode_label():
    f=fixture();f['ids_mode']='rules+if';f['ids'][0]['mode']='rules+if'
    assert 'IF_EVALUATION_UNVERIFIED' in evaluate(**f)['invalid_reasons']
    f['ids'].append({'result':'MODEL_EVALUATION','timestamp':10003.,'input_complete':True,'anomaly_score':-.1})
    assert evaluate(**f)['status']=='VALID'
    f['ids'][-1]['anomaly_score']=float('nan')
    assert evaluate(**f)['status']=='INVALID'


def test_model_and_conditions_that_arrive_after_trial_end_are_excluded():
    f=fixture();f['ids'].append({'result':'ANOMALY','timestamp':10006.,'attack_type':1})
    late=deepcopy(f['ivi'][-1]);late['received_monotonic_ms']='106000';late['body_hex']='not-hex'
    f['ivi'].append(late)
    assert evaluate(**f)['status']=='VALID'


@pytest.mark.parametrize('bad',['nan',float('inf'),True])
def test_malformed_phase_times_fail_closed(bad):
    f=fixture();f['observers'][0][0]['t']=bad
    assert 'MALFORMED_OR_MISSING_EVIDENCE' in evaluate(**f)['invalid_reasons']


def test_wrong_run_or_multiple_phase_sets_cannot_be_evaluated():
    f=fixture();f['observers'][0][0]['run_id']='other-run'
    assert evaluate(**f)['status']=='INVALID'
    f=fixture();f['observers'][1]+=deepcopy(f['observers'][1][:4])
    assert evaluate(**f)['status']=='INVALID'


def test_secoc_only_is_not_evaluated_as_ids_and_rejects_accidental_ids():
    f=fixture();f.update(config=2,ids=None,ids_mode='off')
    assert 'IDS_ENABLED_IN_OFF_CONFIG' in evaluate(**f)['invalid_reasons']
    f['ivi']=[r for r in f['ivi'] if r.get('kind')!=7]
    for row in f['ivi']:
        if row.get('result')=='VIEW_MODEL_PUBLICATION':row['security']='새 보안 알림 없음'
    row=evaluate(**f)
    assert row['status']=='VALID' and row['ecu_ids_type_result']=='NOT_EVALUATED'


def test_unprotected_config_requires_raw_publication_and_rejects_session_output():
    f=fixture();f.update(config=1,ids=None,ids_mode='off')
    assert evaluate(**f)['status']=='INVALID'
    f['ivi']=[{'result':'FRAME','can_id':0x100,'process_result':2,'timestamp_ns':'100500000000'}]
    row=evaluate(**f)
    assert row['status']=='VALID' and row['protocol']=='raw-unprotected'


def test_healthy_missed_detection_is_a_measurement_not_an_execution_error():
    f=fixture();f['ids']=[r for r in f['ids'] if r.get('result')!='ANOMALY']
    bodies={}
    for row in f['ivi']:
        if row.get('kind')==7:
            body=bytearray.fromhex(row['body_hex']);body[48]=0
            bodies[row['body_hex']]=body.hex();row['body_hex']=body.hex();row['condition_mask']=0
        if row.get('result')=='VIEW_MODEL_PUBLICATION':row['security']='새 보안 알림 없음'
    for row in f['ids']:
        if row.get('result')=='DIAGNOSTIC_IPC':row['body_hex']=bodies[row['body_hex']]
    result=evaluate(**f)
    assert result['status']=='VALID',result
    assert result['ecu_ids_type_result']==result['ivi_diagnostic_type_result']==result['ivi_view_model_type_result']=='MISSED'


def test_wrong_ui_type_remains_a_visible_mismatch_measurement():
    f=fixture()
    next(r for r in f['ivi'] if r.get('security')=='Flooding')['security']='Fuzzy'
    result=evaluate(**f)
    assert result['status']=='VALID' and result['ivi_view_model_type_result']=='MISMATCH'
    assert result['ivi_diagnostic_type_result']=='MATCH'
